"""
BidVerify AI - Local Embedding Service (STEP 5)

Manages local semantic embedding generation using Qwen/Qwen3-Embedding-0.6B.
Architecture principles:
  - Model loaded ONCE per process (thread-safe singleton).
  - SentenceTransformer with automatic device selection (CUDA if available, else CPU).
  - prompt_name="query" for tender requirements.
  - prompt_name="document" for vendor claims.
  - Embeddings are normalized for direct cosine similarity via matrix dot product.
  - Batch encoding with LRU text caching to avoid re-encoding across multiple vendor iterations.
  - Completely local: no external API, no Gemini/Hive calls, no API keys.
"""

import os
import time
import threading
import logging
from typing import List, Optional, Dict, Tuple
import numpy as np

logger = logging.getLogger("bidverify.embedding_service")

MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B")
MAX_CACHE_SIZE = int(os.getenv("EMBEDDING_CACHE_MAX_SIZE", "10000"))


class LocalEmbeddingService:
    """Thread-safe singleton service for Qwen local embedding retrieval."""
    _instance: Optional["LocalEmbeddingService"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._model = None
        self._device = None
        self._load_lock = threading.Lock()
        self._encode_lock = threading.Lock()
        self._model_load_time: float = 0.0
        self._is_loaded = False
        self._query_cache: Dict[str, np.ndarray] = {}
        self._doc_cache: Dict[str, np.ndarray] = {}
        self._cache_lock = threading.Lock()
        self._embedding_dim = 1024

    @classmethod
    def get_instance(cls) -> "LocalEmbeddingService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def model_load_time(self) -> float:
        return self._model_load_time

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def ensure_loaded(self) -> None:
        """Loads the SentenceTransformer model once if not already loaded."""
        if self._is_loaded and self._model is not None:
            return

        with self._load_lock:
            if self._is_loaded and self._model is not None:
                return

            start_t = time.time()
            try:
                import torch
                from sentence_transformers import SentenceTransformer

                if torch.cuda.is_available():
                    self._device = "cuda"
                else:
                    self._device = "cpu"

                print(f"[BidVerify Embedding] Loading local embedding model '{MODEL_NAME}' on device '{self._device}'...")
                model = SentenceTransformer(MODEL_NAME, device=self._device)
                
                self._model = model
                self._model_load_time = time.time() - start_t
                self._is_loaded = True
                print(f"[BidVerify Embedding] Model loaded successfully in {self._model_load_time:.2f}s (device: {self._device})")
            except Exception as e:
                self._model_load_time = time.time() - start_t
                logger.error(f"Failed to load embedding model '{MODEL_NAME}': {e}", exc_info=True)
                raise RuntimeError(
                    f"Failed to load local Qwen embedding model '{MODEL_NAME}'. "
                    f"Ensure sentence-transformers and PyTorch are installed. Error: {e}"
                ) from e

    def encode_queries(self, texts: List[str], batch_size: int = 32) -> Tuple[np.ndarray, float]:
        """
        Batch encodes tender requirements using prompt_name="query".
        Returns (embeddings_array, elapsed_time_seconds).
        """
        return self._encode_batch(texts, prompt_type="query", prompt_name="query", batch_size=batch_size)

    def encode_documents(self, texts: List[str], batch_size: int = 32) -> Tuple[np.ndarray, float]:
        """
        Batch encodes vendor claims using prompt_name="document".
        Returns (embeddings_array, elapsed_time_seconds).
        """
        return self._encode_batch(texts, prompt_type="doc", prompt_name="document", batch_size=batch_size)

    def _encode_batch(
        self,
        texts: List[str],
        prompt_type: str,
        prompt_name: str,
        batch_size: int = 32,
    ) -> Tuple[np.ndarray, float]:
        if not texts:
            return np.empty((0, self._embedding_dim), dtype=np.float32), 0.0

        self.ensure_loaded()
        t0 = time.time()

        cache = self._query_cache if prompt_type == "query" else self._doc_cache
        
        # Check cache before locking
        uncached_indices = []
        uncached_texts = []
        cached_results: Dict[int, np.ndarray] = {}

        with self._cache_lock:
            for idx, text in enumerate(texts):
                key = text.strip()
                if key in cache:
                    cached_results[idx] = cache[key]
                else:
                    uncached_indices.append(idx)
                    uncached_texts.append(text)

        # Batch encode uncached texts with double-checked locking
        if uncached_texts:
            with self._encode_lock:
                # Re-check cache inside encode lock
                still_uncached_indices = []
                still_uncached_texts = []
                with self._cache_lock:
                    for local_i, orig_i in enumerate(uncached_indices):
                        t_str = uncached_texts[local_i].strip()
                        if t_str in cache:
                            cached_results[orig_i] = cache[t_str]
                        else:
                            still_uncached_indices.append(orig_i)
                            still_uncached_texts.append(uncached_texts[local_i])

                if still_uncached_texts:
                    encoded_embs = self._model.encode(
                        still_uncached_texts,
                        prompt_name=prompt_name,
                        batch_size=batch_size,
                        normalize_embeddings=True,
                        convert_to_numpy=True,
                        show_progress_bar=False,
                    )
                    with self._cache_lock:
                        if len(cache) > MAX_CACHE_SIZE:
                            keys_to_evict = list(cache.keys())[: MAX_CACHE_SIZE // 4]
                            for k in keys_to_evict:
                                cache.pop(k, None)
                        for local_i, orig_i in enumerate(still_uncached_indices):
                            vec = encoded_embs[local_i]
                            cache[still_uncached_texts[local_i].strip()] = vec
                            cached_results[orig_i] = vec
                            if vec.shape[0] > 0:
                                self._embedding_dim = vec.shape[0]


        # Assemble result in original order
        final_list = [cached_results[i] for i in range(len(texts))]
        final_array = np.array(final_list, dtype=np.float32)
        elapsed = time.time() - t0
        return final_array, elapsed

    def compute_similarity_matrix(
        self,
        query_embeddings: np.ndarray,
        doc_embeddings: np.ndarray,
    ) -> np.ndarray:
        """
        Computes cosine similarity between normalized query and document embeddings.
        Result shape: (num_queries, num_documents).
        """
        if query_embeddings.size == 0 or doc_embeddings.size == 0:
            return np.empty((query_embeddings.shape[0], doc_embeddings.shape[0]), dtype=np.float32)
        
        # Vectors are already L2 normalized, so cosine similarity is the dot product
        return np.dot(query_embeddings, doc_embeddings.T)

    def clear_cache(self) -> None:
        """Clears in-memory embedding caches."""
        with self._cache_lock:
            self._query_cache.clear()
            self._doc_cache.clear()


# Module-level convenience functions
def get_embedding_service() -> LocalEmbeddingService:
    return LocalEmbeddingService.get_instance()

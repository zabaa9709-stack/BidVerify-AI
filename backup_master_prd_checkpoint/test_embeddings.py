from sentence_transformers import SentenceTransformer
import numpy as np
import time

MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"

print("Loading embedding model...")
start = time.time()

model = SentenceTransformer(MODEL_NAME)

print(f"Model loaded in {time.time() - start:.2f} seconds")

requirements = [
    "Minimum battery capacity shall be 40 Ah.",
    "LED luminaire must provide at least 12000 lumens.",
    "Operating temperature shall be -10°C to +50°C.",
]

vendor_claims = [
    "Battery capacity: 36 Ah.",
    "Luminous output: 12 klm.",
    "Operating temperature range: -20°C to +60°C.",
    "The system includes an aluminum enclosure.",
]

print("\nGenerating embeddings...")

requirement_embeddings = model.encode(
    requirements,
    prompt_name="query",
    normalize_embeddings=True,
    convert_to_numpy=True,
)

claim_embeddings = model.encode(
    vendor_claims,
    prompt_name="document",
    normalize_embeddings=True,
    convert_to_numpy=True,
)

# cosine similarity because vectors are normalized
similarities = requirement_embeddings @ claim_embeddings.T

print("\nRESULTS")
print("=" * 70)

for i, requirement in enumerate(requirements):
    print(f"\nRequirement: {requirement}")

    scores = similarities[i]

    ranked = np.argsort(scores)[::-1]

    for rank, idx in enumerate(ranked[:3], start=1):
        print(
            f"{rank}. {scores[idx]:.4f}  "
            f"{vendor_claims[idx]}"
        )

print("\nEmbedding dimensions:", requirement_embeddings.shape[1])
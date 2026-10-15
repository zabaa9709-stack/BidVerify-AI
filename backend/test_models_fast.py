import os
import time
from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options=types.HttpOptions(timeout=15000))
for m in ["gemini-2.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest"]:
    t0 = time.time()
    try:
        r = client.models.generate_content(model=m, contents='{"test": true}')
        print(f"SUCCESS: {m} in {time.time()-t0:.2f}s -> {r.text.strip()[:60]}", flush=True)
    except Exception as e:
        print(f"FAIL: {m} in {time.time()-t0:.2f}s -> {str(e)[:100]}", flush=True)

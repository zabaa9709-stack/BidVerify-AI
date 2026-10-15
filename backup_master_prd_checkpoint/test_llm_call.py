import os
import time
from dotenv import load_dotenv
load_dotenv()
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
try:
    resp = client.models.generate_content(
        model="gemini-3.6-flash",
        contents='Respond with valid JSON: {"status": "ok"}'
    )
    print("SUCCESS:", resp.text)
except Exception as e:
    print("ERROR:", type(e).__name__, e)

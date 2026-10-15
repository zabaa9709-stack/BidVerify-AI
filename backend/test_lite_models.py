import os
from dotenv import load_dotenv
load_dotenv()
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
for m in ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.7-flash", "gemini-3.8-flash"]:
    try:
        r = client.models.generate_content(model=m, contents='Respond with JSON: {"ok": true}')
        print("SUCCESS:", m, r.text.strip())
    except Exception as e:
        print("FAIL:", m, str(e)[:120])

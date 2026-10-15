import os
from dotenv import load_dotenv
load_dotenv()
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
try:
    for m in client.models.list():
        if "gemini" in m.name.lower():
            print(m.name, m.supported_actions if hasattr(m, "supported_actions") else "")
except Exception as e:
    print("Error listing models:", e)

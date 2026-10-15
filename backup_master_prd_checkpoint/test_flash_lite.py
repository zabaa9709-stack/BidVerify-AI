import os
from dotenv import load_dotenv
load_dotenv()
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
resp = client.models.generate_content(
    model="gemini-flash-lite-latest",
    contents='Respond with valid JSON: {"model_working": true}',
)
print("Response:", resp.text)

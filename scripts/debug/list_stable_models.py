import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
# .env 로드 가정
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

print("=== Available Models ===")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"ID: {m.name} | Display Name: {m.display_name}")

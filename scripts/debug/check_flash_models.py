import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
# .env에서 API 키를 로드했다고 가정
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

print("Searching for available Flash models...")
for m in genai.list_models():
    # 'flash'가 이름에 포함되고, 'generateContent'를 지원하는지 확인
    if 'flash' in m.name.lower() and 'generateContent' in m.supported_generation_methods:
        # Check if version attribute exists, otherwise print name only
        version = getattr(m, 'version', 'Unknown')
        print(f"Model Name: {m.name} | Version: {version}")

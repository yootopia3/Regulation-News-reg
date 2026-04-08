import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
print(f"Key loaded: {api_key[:5]}...")

genai.configure(api_key=api_key)

try:
    with open("models_list.txt", "w") as f:
        print("Listing models...", file=f)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(m.name, file=f)
                
    print("Models listed to models_list.txt")
except Exception as e:
    print(f"Error listing: {e}")

import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("--- Start Model List ---")
for m in genai.list_models():
    print(m.name)
print("--- End Model List ---")

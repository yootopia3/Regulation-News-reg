import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

candidates = [
    "gemini-2.0-flash-lite-preview-02-05", 
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash-001"
]

print("Testing candidates with new SDK...")
for model_name in candidates:
    print(f"\n--- Testing {model_name} ---")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents="Hello"
        )
        print(f"SUCCESS! {model_name} worked.")
        print(f"Response: {response.text}")
        break
    except Exception as e:
        print(f"Failed {model_name}: {e}")

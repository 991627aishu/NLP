"""
Verify Gemini API Models Against Live Account with Backoff Retries
"""
import os
import sys
import time
from pathlib import Path

# Load environment variables from .env
env_file = Path(".env")
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("\"'")
            if k not in os.environ:
                os.environ[k] = v

api_key = os.getenv("GEMINI_API_KEY")
print(f"API Key configured: {bool(api_key)}")

from google import genai
from google.genai import types

client = genai.Client(api_key=api_key)

models_to_test = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
]

print("\n--- Testing Generation Models with Retries ---")
for model_name in models_to_test:
    print(f"\nTesting model: {model_name}")
    success = False
    for attempt in range(1, 4):
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents="Say 'OK' in one word.",
            )
            text = getattr(resp, "text", str(resp)).strip()
            print(f"  Attempt {attempt}: SUCCESS -> {text!r}")
            success = True
            break
        except Exception as e:
            print(f"  Attempt {attempt}: Failed ({type(e).__name__}): {e}")
            if "503" in str(e) or "429" in str(e):
                time.sleep(2 * attempt)
            else:
                break

print("\n--- Testing Embedding Model: gemini-embedding-001 ---")
for attempt in range(1, 4):
    try:
        resp = client.models.embed_content(
            model="gemini-embedding-001",
            contents="Ayurveda is a traditional system of medicine.",
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        emb = getattr(resp, "embedding", None)
        values = getattr(emb, "values", []) if emb else []
        print(f"  Attempt {attempt}: SUCCESS -> Embedding vector dimension: {len(values)}")
        break
    except Exception as e:
        print(f"  Attempt {attempt}: Failed ({type(e).__name__}): {e}")
        time.sleep(2 * attempt)

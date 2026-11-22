import os
import sys

print("=== AUDIT: ENVIRONMENT & HARDWARE ===")
print("Python:", sys.version)
print("Torch / CUDA available?")
try:
    import torch
    print("  Torch version:", torch.__version__)
    print("  CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("  GPU:", torch.cuda.get_device_name(0))
except Exception as e:
    print("  Torch not installed or error:", e)

print("\n=== AUDIT: INSTALLED PACKAGES ===")
pkgs = ["transformers", "ctranslate2", "faster_whisper", "sentence_transformers", "openai", "anthropic", "requests", "edge_tts", "gtts", "playwright"]
for p in pkgs:
    try:
        mod = __import__(p)
        print(f"  {p}: INSTALLED ({getattr(mod, '__version__', 'no version')})")
    except Exception as e:
        print(f"  {p}: NOT INSTALLED ({e})")

print("\n=== AUDIT: ENVIRONMENT KEYS ===")
for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "SERPAPI_API_KEY"]:
    val = os.environ.get(k)
    print(f"  {k}: {'SET (len=' + str(len(val)) + ')' if val else 'NOT SET'}")

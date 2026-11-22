import os
import sys

print("Python executable:", sys.executable)
print("Environment keys:")
for k in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "OLLAMA_URL", "AYUR_OLLAMA_URL"]:
    v = os.environ.get(k)
    print(f"  {k}: {'[SET]' if v else '[NOT SET]'}")

try:
    import urllib.request
    # check if local ollama is running
    req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"User-Agent": "test"})
    with urllib.request.urlopen(req, timeout=1.0) as r:
        print("Ollama available:", r.status)
except Exception as e:
    print("Ollama not running:", e)

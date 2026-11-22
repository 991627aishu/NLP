import os
import json
import urllib.request

key = os.environ.get("OPENAI_API_KEY")
print("Key length:", len(key) if key else 0)
req = urllib.request.Request(
    "https://api.openai.com/v1/chat/completions",
    data=json.dumps({
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "What is machine learning in one sentence?"}],
        "max_tokens": 50
    }).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print("OpenAI GPT-4o-mini SUCCESS:", res["choices"][0]["message"]["content"])
except Exception as e:
    print("OpenAI error:", e)

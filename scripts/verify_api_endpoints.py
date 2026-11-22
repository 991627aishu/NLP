import json
import urllib.request

BASE_URL = "http://127.0.0.1:8000"

endpoints = [
    ("GET", "/", None),
    ("GET", "/api/health", None),
    ("GET", "/api/graph?center=Tridosha&depth=1", None),
    ("GET", "/api/graph/stats", None),
    ("GET", "/api/herbs/search?q=ashwagandha", None),
    ("GET", "/api/lifestyle", None),
    ("GET", "/api/research/results", None),
    ("POST", "/api/symptoms", {"text": "stiff joints, restless, dry skin"}),
    ("POST", "/api/ask", {"query": "What is Ayurveda?", "mode": "P2"})
]

print(f"Connecting to {BASE_URL}...")
all_ok = True

for method, path, body in endpoints:
    url = BASE_URL + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            print(f"[{status}] {method:4} {path:40} | {len(content):6} bytes | {content_type}")
            if status != 200:
                all_ok = False
            # Verify JSON payload where applicable
            if "application/json" in content_type:
                parsed = json.loads(content.decode("utf-8"))
                if not parsed.get("ok", True):
                    print(f"  WARNING: 'ok' not true in {path}")
                    all_ok = False
    except Exception as e:
        print(f"[FAIL] {method:4} {path:40} | Error: {e}")
        all_ok = False

if all_ok:
    print("\nALL API ENDPOINTS RETURNED HTTP 200 AND VALID CONTENT")
else:
    print("\nSOME API ENDPOINTS FAILED")


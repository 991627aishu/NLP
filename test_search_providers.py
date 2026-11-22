import requests

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
# Test DuckDuckGo HTML / Lite or Instant Answer
try:
    r = requests.get("https://api.duckduckgo.com/?q=current+prime+minister+of+india&format=json", headers=headers, timeout=5)
    print("DDG Status:", r.status_code)
    data = r.json()
    print("Heading:", data.get("Heading"))
    print("Abstract:", data.get("Abstract")[:150])
    print("AbstractURL:", data.get("AbstractURL"))
except Exception as e:
    print("DDG Error:", e)

try:
    # Test Wikipedia Current Events API
    r2 = requests.get("https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=current+prime+minister+of+india&format=json", headers=headers, timeout=5)
    print("Wiki status:", r2.status_code)
    hits = r2.json().get("query", {}).get("search", [])
    if hits:
        print("Top hit:", hits[0]["title"], hits[0]["snippet"][:100])
except Exception as e:
    print("Wiki Error:", e)

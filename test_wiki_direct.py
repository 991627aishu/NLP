import requests

headers = {"User-Agent": "AyurMitraAcademic/1.0"}
r = requests.get("https://en.wikipedia.org/w/api.php", params={
    "action": "query",
    "list": "search",
    "srsearch": "machine learning",
    "format": "json",
    "srlimit": 2
}, headers=headers)
print("Status:", r.status_code)
for item in r.json().get("query", {}).get("search", []):
    print("Title:", item.get("title"))
    print("Snippet:", item.get("snippet"))

import requests

try:
    r = requests.get("https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=Kushtha&format=json", headers={"User-Agent": "AyurMitra/1.0"}, timeout=5)
    print("Wiki status:", r.status_code)
    print("Wiki hits:", len(r.json().get("query", {}).get("search", [])))
    for h in r.json().get("query", {}).get("search", [])[:2]:
        print(" -", h["title"])
except Exception as e:
    print("Wiki err:", e)

try:
    r = requests.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=Kushtha&format=json", headers={"User-Agent": "AyurMitra/1.0"}, timeout=5)
    print("EuropePMC status:", r.status_code)
except Exception as e:
    print("EuropePMC err:", e)

import requests

url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
params = {"query": "Ayurveda Kushtha", "format": "json", "pageSize": 3, "resultType": "core"}
r = requests.get(url, params=params, headers={"User-Agent": "AyurMitra/1.0"}, timeout=5)
print("Hits:", len(r.json().get("resultList", {}).get("result", [])))
for item in r.json().get("resultList", {}).get("result", []):
    print("Title:", item.get("title"))
    print("Abstract len:", len(item.get("abstractText", "")))

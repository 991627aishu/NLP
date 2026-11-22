import requests

headers = {"User-Agent": "AyurMitraAcademic/1.0"}
queries = ["Machine learning", "Newton's laws of motion", "Cloud computing", "Photosynthesis", "Prime Minister of India"]

for q in queries:
    r = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(q)}", headers=headers, timeout=5)
    if r.status_code == 200:
        d = r.json()
        print(f"[{q}] -> Title: {d.get('title')} | Extract: {d.get('extract')[:150]}...")
    else:
        print(f"[{q}] -> Status {r.status_code}")

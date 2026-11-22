import sys
if sys.stdout.encoding.lower() != 'utf-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass

from app.core.symptom_mapper import EducationalSymptomMapper
from app.core.herbs import HerbService

mapper = EducationalSymptomMapper()
herbs = HerbService()

print("=== 1. Non-acute symptoms ===")
res1 = mapper.analyze_symptoms("stiff joints, restlessness, dry skin")
print("Non-acute:", "abstained:", res1.get("abstained"), "mappings:", len(res1.get("mappings", [])))
for m in res1.get("mappings", []):
    print(" ", m.get("symptom_phrase"), "->", m.get("associated_dosha"))

print("\n=== 2. Emergency symptoms ===")
res2 = mapper.analyze_symptoms("severe chest pain and sudden shortness of breath")
print("Emergency:", "reason:", res2.get("reason"), "message:", res2.get("message")[:100])

print("\n=== 3. Vague symptoms ===")
res3 = mapper.analyze_symptoms("I feel slightly weird today")
print("Vague:", "abstained:", res3.get("abstained"), "message:", res3.get("message")[:100])

print("\n=== 4. Multilingual (Hindi, Kannada, Hinglish, Kanglish) ===")
tests = [
    ("पेट में जलन और एसिडिटी", "Hindi"),
    ("ಹೊಟ್ಟೆಯಲ್ಲಿ ಉರಿ ಮತ್ತು ಅಜೀರ್ಣ", "Kannada"),
    ("pet me jalan ho rahi hai", "Hinglish"),
    ("hotteyalli uri ide", "Kanglish")
]
for q, label in tests:
    r = mapper.analyze_symptoms(q)
    print(f"[{label}] '{q}' -> lang: {r.get('target_language')} | mappings: {len(r.get('mappings', []))} | doshas: {[m.get('associated_dosha') for m in r.get('mappings', [])]}")

print("\n=== 5. Herb search and detail ===")
for query in ["ashwagandha", "ocimum", "azadirachta", "curcuma"]:
    sr = herbs.search(query, limit=3)
    results = sr.get("results", [])
    print(f"Search '{query}' -> {len(results)} hits")
    if results:
        h = results[0]
        det = herbs.detail(h["id"])
        print(f"  First hit: {det.get('botanical_name')} ({det.get('family')}) | Uses: {det.get('n_recorded_uses')} | Formulations: {len(det.get('formulations', []))}")
        print(f"  Dose-free check: {'dose' not in str(det).lower() or 'no dose' in str(det).lower()}")


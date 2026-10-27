import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.service import _flatten_evidence
from app.retrieval import bm25_scores
recs = _flatten_evidence()
texts = [str(r.get("text", "")) for r in recs]

queries = [
    ("Agni digestive fire concept", "general", ["agni", "digestive fire"]),
    ("Vata dosha biological movement humor", "general", ["vata", "movement"]),
    ("Pitta dosha digestion heat transformation", "general", ["pitta", "digestion"]),
    ("Kapha dosha lubrication structure", "general", ["kapha", "lubrication"]),
    ("Tridosha fundamental regulatory principles", "general", ["tridosha", "vata", "pitta"]),
    ("Ojas supreme vital essence immunity", "general", ["ojas", "vital essence"]),
    ("Ama toxic undigested residue", "general", ["ama", "toxic"]),
    ("Prakriti constitutional typology", "general", ["prakriti", "constitution"]),
    ("Rasayana therapy rejuvenation longevity", "general", ["rasayana", "rejuvenation"]),
    ("Sapta Dhatu bodily structural tissues", "general", ["dhatu", "tissues"]),
    ("Tulsi Ocimum tenuiflorum medicinal uses", "herbs", ["ocimum tenuiflorum", "tulsi"]),
    ("Ashwagandha Withania somnifera therapeutic uses", "herbs", ["withania somnifera", "ashwagandha"]),
    ("Turmeric Curcuma longa therapeutic uses", "herbs", ["curcuma longa", "turmeric"]),
    ("Neem Azadirachta indica traditional uses", "herbs", ["azadirachta indica", "neem"]),
    ("tulsi ke fayde", "herbs", ["ocimum tenuiflorum"]),
    ("ashwagandha ke fayde", "herbs", ["withania somnifera"]),
    ("haldi ke labh", "herbs", ["curcuma longa"]),
]

gold_rows = []
for q, cat, keywords in queries:
    # Find matching IDs based on strong keyword presence in text/title
    matching_ids = []
    for r in recs:
        t = str(r.get("text", "")).lower()
        if all(k in t for k in keywords):
            matching_ids.append(r["id"])
            if len(matching_ids) >= 3:
                break
    gold_rows.append({
        "query": q,
        "category": cat,
        "language": "English" if "ke" not in q else "Hinglish",
        "relevant_record_ids": matching_ids,
        "notes": f"Ground-truth benchmark entry for {keywords[0]}",
    })

# Add negative control query
gold_rows.append({
    "query": "quantum semiconductor fabrication plant in ancient ayurveda",
    "category": "general",
    "language": "English",
    "relevant_record_ids": [],
    "notes": "Negative out-of-domain query expecting honest abstention",
})

gold_file = ROOT / "data" / "evaluation" / "gold_queries.jsonl"
with open(gold_file, "w", encoding="utf-8") as f:
    for row in gold_rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

print(f"Generated {len(gold_rows)} gold queries into {gold_file}")

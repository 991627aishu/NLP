import json
from pathlib import Path

for name in ["desktop-report.report.json", "mobile-report.report.json"]:
    p = Path("docs/lighthouse") / name
    if not p.exists():
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    print(f"=== {name} ===")
    cats = data.get("categories", {})
    for k, v in cats.items():
        score = v.get("score")
        score_val = round(score * 100) if score is not None else "N/A"
        print(f"  {v.get('title')}: {score_val} / 100")


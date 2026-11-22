import json
from pathlib import Path

p = Path("Data/evaluation/experiment_results_v2.json")
if not p.exists():
    p = Path("data/evaluation/experiment_results_v2.json")

data = json.loads(p.read_text(encoding="utf-8"))
meta = data.get("meta", {})
print("META:", json.dumps(meta, indent=2))

systems = data.get("systems", {})
print("\nMAIN SYSTEMS METRICS:")
for name in ["B0", "B1", "P1", "P2"]:
    s = systems.get(name, {})
    m = s.get("metrics", {})
    r5 = m.get("recall_at_5", {})
    mrr = m.get("mrr", {})
    ndcg = m.get("ndcg_at_5", {})
    fa = m.get("false_abstention_rate", {})
    print(f"[{name}]")
    print(f"  Recall@5: {r5.get('mean'):.4f}  95% CI: {r5.get('ci')}")
    print(f"  MRR:      {mrr.get('mean'):.4f}  95% CI: {mrr.get('ci')}")
    print(f"  nDCG@5:   {ndcg.get('mean'):.4f}  95% CI: {ndcg.get('ci')}")
    print(f"  FalseAbst:{fa.get('mean'):.4f}  95% CI: {fa.get('ci')}")
    if "latency_ms" in m:
        lat = m.get("latency_ms", {})
        print(f"  Latency:  {lat.get('mean'):.1f} ms")

print("\nPAIRED DIFFERENCES:")
paired = data.get("paired", {})
for comp, p_info in paired.items():
    r_diff = p_info.get("recall_at_5", {})
    m_diff = p_info.get("mrr", {})
    print(f"[{comp}]")
    print(f"  Recall@5 diff: {r_diff.get('diff'):+.4f} (95% CI: {r_diff.get('ci')})")
    print(f"  MRR diff:      {m_diff.get('diff'):+.4f}")
    print(f"  Verdict:       {p_info.get('verdict')}")


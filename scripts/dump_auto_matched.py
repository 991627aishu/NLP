import pickle
from pathlib import Path

kg_path = Path("Data/processed/knowledge_graph_v2.pkl")
data = pickle.load(open(kg_path, "rb"))
g = data if not isinstance(data, dict) else data.get("graph", data)

matched = []
for u, v, d in g.edges(data=True):
    if d.get("review_status") == "auto_matched_by_code":
        matched.append((u, d.get("relation"), v, d.get("source_id"), d.get("locator"), d.get("confidence")))

print(f"Total auto_matched_by_code edges: {len(matched)}")
with open("docs/auto_matched_37.tsv", "w", encoding="utf-8") as f:
    f.write("Source Node\tRelation\tTarget Node\tSource Dataset\tLocator\tConfidence\n")
    for row in matched:
        f.write("\t".join(str(x) for x in row) + "\n")
print("Saved to docs/auto_matched_37.tsv")

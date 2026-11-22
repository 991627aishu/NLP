import json
with open("Data/processed/corpus_chunks.jsonl", "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if "ancient Indian system" in line:
            c = json.loads(line)
            print(f"Line {i}: ID={c.get('chunk_id')}, Source={c.get('source_id')}")
            print("Text:", repr(c.get("text")[:300]))


import json
with open("Data/processed/corpus_chunks.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        c = json.loads(line)
        if c.get("chunk_id") == "QA_PASSAGE_0198":
            print("=== QA_PASSAGE_0198 ===")
            print(c.get("text"))
            break


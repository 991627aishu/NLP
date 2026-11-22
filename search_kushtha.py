import json

count = 0
with open("Data/processed/corpus_chunks.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        text = data.get("text", "")
        if "kushtha" in text.lower() or "kushta" in text.lower():
            count += 1
            if count <= 5:
                print(f"[{data.get('chunk_id')}] Title: {data.get('title')}")
                print(f"  Snippet: {text[:200]}...")

print(f"Total chunks mentioning Kushtha/Kushta: {count}")

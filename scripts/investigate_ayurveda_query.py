import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from app.pipeline.rag_pipeline import AyurMitraPipeline

rag = AyurMitraPipeline()
res = rag.process_query("What is Ayurveda?")
print("=== QUERY: What is Ayurveda? ===")
print("Keys:", list(res.keys()))
print("Answer:\n", res.get("answer"))
print("\nExplanation:\n", res.get("explanation"))
print("\nPassages retrieved:")
for i, p in enumerate(res.get("retrieved_passages", res.get("passages", []))):
    print(f"[{i}] {p.get('chunk_id')} | {p.get('source_id')} | score: {p.get('score')}")
    print(f"    Text: {p.get('text', '')[:200]}")
    print()

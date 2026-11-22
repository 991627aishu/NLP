import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.rag_pipeline import AyurMitraPipeline
from app.pipeline.generator import EvidenceGroundedGenerator

rag = AyurMitraPipeline()
passages = rag.retriever.retrieve("What is Ayurveda?", top_k=5)
print(f"Retrieved {len(passages)} passages:")
for i, p in enumerate(passages):
    print(f"[{i}] ID: {p.get('chunk_id')}, Title: {p.get('title')}")
    print(f"    Text snippet: {repr(p.get('text', '')[:140])}")


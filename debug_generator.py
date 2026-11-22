from app.pipeline.rag_pipeline import AyurMitraPipeline

pipe = AyurMitraPipeline()
q = "ಕುಷ್ಠರೋಗ ಎಂದರೇನು?"
res = pipe.process_query(q, system_mode="P2")
print("Passages count:", len(res.get("retrieved_passages", [])))
print("Evidence check:", res.get("evidence_check"))
for p in res.get("retrieved_passages", []):
    print("Chunk:", p.get("chunk_id"), "Score:", p.get("rrf_score"), "Text:", p.get("text")[:100])

from app.pipeline.rag_pipeline import AyurMitraPipeline

pipe = AyurMitraPipeline()
q = "ಕುಷ್ಠರೋಗ ಎಂದರೇನು?"
res = pipe.answer(q, mode="P2")
print("Response text:", res.get("answer"))
print("Detected lang:", res.get("detected_language"))
print("Protected terms:", [t.get("term") for t in res.get("protected_terms", [])])
print("Retrieved chunks count:", len(res.get("retrieved_chunks", [])))
for c in res.get("retrieved_chunks", [])[:3]:
    print(" - Chunk:", c.get("chunk_id"), c.get("title"))

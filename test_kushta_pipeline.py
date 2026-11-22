from app.pipeline.rag_pipeline import AyurMitraPipeline

pipe = AyurMitraPipeline()
q = "ಕುಷ್ಠರೋಗ ಎಂದರೇನು?"
res = pipe.process_query(q, system_mode="P2", target_lang="auto")
print("Answer snippet:", res.get("answer")[:300])
print("Abstained:", res.get("abstained"))
print("Citations count:", len(res.get("citations", [])))
print("Terms:", [t.get("canonical_term") for t in res.get("detected_terms", [])])

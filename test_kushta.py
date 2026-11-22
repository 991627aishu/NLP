from app.pipeline.rag_pipeline import AyurMitraPipeline

pipe = AyurMitraPipeline()
q = "ಕುಷ್ಠರೋಗ ಎಂದರೇನು?"
res = pipe.process_query(q, system_mode="P2")
print("Answer:", res.get("answer"))
print("Abstention reason:", res.get("abstention_reason"))
print("Retrieved count:", len(res.get("retrieved_chunks", [])))
print("Clean query:", res.get("clean_query"))
print("Translated query:", res.get("translated_query"))
print("Protected query:", res.get("protected_query"))
print("Terms:", [t.get("term") for t in res.get("protected_terms", [])])

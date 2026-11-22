from app.pipeline.translator import MultilingualTranslator
from app.pipeline.hybrid_retriever import HybridRetriever

tr = MultilingualTranslator()
res = tr.translate_to_english("ಕುಷ್ಠರೋಗ ಎಂದರೇನು?", source_lang="kn")
print("Translation result:", res)

ret = HybridRetriever()
q1 = res.get("translated_text", "")
print("Searching for:", q1)
chunks1 = ret.retrieve(q1, top_k=5)
print("Chunks for translated query:", len(chunks1))
for c in chunks1[:3]:
    print(" - ", c.get("chunk_id"), c.get("title"))

print("\nSearching for 'Kushtha':")
chunks2 = ret.retrieve("Kushtha skin disease leprosy", top_k=5)
print("Chunks for Kushtha:", len(chunks2))
for c in chunks2[:3]:
    print(" - ", c.get("chunk_id"), c.get("title"))

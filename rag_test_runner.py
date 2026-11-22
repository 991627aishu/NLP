import requests
import json

BASE_URL = "http://127.0.0.1:8000"

rag_queries = [
    {"id": 1, "q": "What is Vata dosha?", "lang": "en"},
    {"id": 2, "q": "Explain the qualities of Pitta", "lang": "en"},
    {"id": 3, "q": "What is the difference between Vata and Pitta?", "lang": "en"},
    {"id": 4, "q": "What is Madhumeha?", "lang": "en"},
    {"id": 5, "q": "What is Agni?", "lang": "en"},
    {"id": 6, "q": "What is Ama?", "lang": "en"},
    {"id": 7, "q": "What is Ashwagandha traditionally used for?", "lang": "en"},
    {"id": 8, "q": "Which herbs are discussed in the dataset for indigestion?", "lang": "en"},
    {"id": 9, "q": "What is quantum computing and how do qubits work?", "lang": "en"},
    {"id": 10, "q": "Does Tulsi completely cure stage 4 lung cancer overnight?", "lang": "en"}
]

results = []

for item in rag_queries:
    try:
        r = requests.post(
            f"{BASE_URL}/api/ask",
            json={"query": item["q"], "force_mode": "p2", "language_preference": "auto"},
            timeout=30
        )
        if r.status_code == 200:
            data = r.json()
            ans = data.get("answer", "")
            chunks = data.get("retrieved_chunks", [])
            kg = data.get("knowledge_graph", {})
            sources = data.get("sources", [])
            abstain = ("cannot confirm" in ans.lower() or "not sufficient" in ans.lower() or "traditional literature does not" in ans.lower() or "insufficient" in ans.lower() or "not found" in ans.lower() or len(chunks) == 0 or "no specific" in ans.lower())
            
            results.append({
                "id": item["id"],
                "query": item["q"],
                "status_code": r.status_code,
                "detected_lang": data.get("detected_language"),
                "answer_snippet": ans[:300] + "..." if len(ans) > 300 else ans,
                "num_chunks": len(chunks),
                "top_chunks": [c.get("chunk_id", c.get("id")) for c in chunks[:3]],
                "sources": sources[:3],
                "kg_facts_count": len(kg.get("grounded_facts", [])) if isinstance(kg, dict) else 0,
                "abstained": abstain
            })
        else:
            results.append({"id": item["id"], "query": item["q"], "status_code": r.status_code, "error": r.text})
    except Exception as e:
        results.append({"id": item["id"], "query": item["q"], "error": str(e)})

with open("rag_10_eval_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("Finished 10 RAG evaluations!")
for r in results:
    print(f"[{r.get('id')}] Q: {r.get('query')[:40]} | Chunks: {r.get('num_chunks')} | Abstained: {r.get('abstained')}")

from fastapi.testclient import TestClient
from api.main import app
import json

client = TestClient(app)

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
        r = client.post(
            "/api/ask",
            json={"query": item["q"], "force_mode": "p2", "language_preference": "auto"}
        )
        if r.status_code == 200:
            data = r.json()
            ans = data.get("answer", "")
            # check the response fields
            chunks = data.get("sources", [])
            kg = data.get("knowledge_graph", {})
            citations = data.get("citations", [])
            
            # Abstention / ungrounded detection
            abstain = (
                "cannot confirm" in ans.lower() or 
                "not sufficient" in ans.lower() or 
                "traditional literature does not" in ans.lower() or 
                "insufficient" in ans.lower() or 
                "not found" in ans.lower() or 
                "no specific" in ans.lower() or
                "does not provide" in ans.lower() or
                len(chunks) == 0
            )
            
            results.append({
                "id": item["id"],
                "query": item["q"],
                "status_code": r.status_code,
                "detected_lang": data.get("detected_language"),
                "answer_snippet": ans[:300] + "..." if len(ans) > 300 else ans,
                "num_sources": len(chunks),
                "sources_sample": [c.get("title", c.get("source_id", str(c))) for c in chunks[:3]],
                "kg_facts_count": len(kg.get("grounded_facts", [])) if isinstance(kg, dict) else 0,
                "abstained": abstain,
                "full_data": {
                    "answer": ans,
                    "execution_trace": data.get("execution_trace", {}),
                    "protected_terms": [t.get("term") for t in data.get("protected_terms", [])]
                }
            })
        else:
            results.append({"id": item["id"], "query": item["q"], "status_code": r.status_code, "error": r.text})
    except Exception as e:
        results.append({"id": item["id"], "query": item["q"], "error": str(e)})

with open("rag_10_eval_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("Finished 10 in-process RAG evaluations!")
for r in results:
    print(f"[{r.get('id')}] Q: {r.get('query')[:40]} | Sources: {r.get('num_sources')} | Lang: {r.get('detected_lang')} | Abstained: {r.get('abstained')}")

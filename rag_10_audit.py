import requests
import json

BASE_URL = "http://127.0.0.1:8000"

rag_queries = [
    {"id": 1, "q": "What is Vata dosha?", "focus": "Vata qualities, no Madhumeha leakage"},
    {"id": 2, "q": "Explain the qualities of Pitta", "focus": "Pitta qualities"},
    {"id": 3, "q": "What is the difference between Vata and Pitta?", "focus": "Distinction between Vata & Pitta"},
    {"id": 4, "q": "What is Madhumeha?", "focus": "Prameha/Madhumeha grounding"},
    {"id": 5, "q": "What is Agni?", "focus": "Digestive fire / metabolic concept"},
    {"id": 6, "q": "What is Ama?", "focus": "Toxic metabolic residue"},
    {"id": 7, "q": "What is Ashwagandha traditionally used for?", "focus": "Withania somnifera therapeutic use"},
    {"id": 8, "q": "Which herbs are discussed in the dataset for indigestion?", "focus": "Herbs for Agnimandya / digestion"},
    {"id": 9, "q": "What is quantum computing and how do qubits work?", "focus": "Out-of-domain abstention"},
    {"id": 10, "q": "Does Tulsi completely cure stage 4 lung cancer overnight?", "focus": "Ungrounded / insufficient evidence abstention"}
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
                "focus": item["focus"],
                "status_code": r.status_code,
                "detected_lang": data.get("detected_language"),
                "answer_snippet": ans[:300] + "..." if len(ans) > 300 else ans,
                "num_sources": len(chunks),
                "top_sources": [c.get("title", c.get("source_id", str(c))) for c in chunks[:3]],
                "kg_facts": kg.get("grounded_facts", []) if isinstance(kg, dict) else [],
                "abstained": abstain,
                "full_answer": ans
            })
            print(f"[{item['id']}] Q: {item['q'][:35]} | Sources: {len(chunks)} | Abstained: {abstain}", flush=True)
        else:
            print(f"[{item['id']}] Error: {r.status_code}", flush=True)
            results.append({"id": item["id"], "query": item["q"], "status_code": r.status_code, "error": r.text})
    except Exception as e:
        print(f"[{item['id']}] Exception: {e}", flush=True)
        results.append({"id": item["id"], "query": item["q"], "error": str(e)})

with open("rag_10_eval_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\nALL 10 RAG EVALUATIONS COMPLETED SUCCESSFULLY!", flush=True)

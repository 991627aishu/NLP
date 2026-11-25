import sys
import time
import json
import concurrent.futures
import requests

BASE_URL = "http://127.0.0.1:8000"

TESTS = [
    {
        "id": 1,
        "name": "English Ayurvedic Query",
        "payload": {"query": "What is Vata dosha?", "mode": "P2", "target_lang": "auto"},
    },
    {
        "id": 2,
        "name": "Kannada Query",
        "payload": {"query": "ಕಾಮಣಿ ಎಂದರೇನು?", "mode": "P2", "target_lang": "auto"},
    },
    {
        "id": 3,
        "name": "Hindi Query",
        "payload": {"query": "वात दोष के मुख्य लक्षण क्या हैं?", "mode": "P2", "target_lang": "auto"},
    },
    {
        "id": 4,
        "name": "Hinglish Query",
        "payload": {"query": "Pitta badhne par kya symptoms hote hain?", "mode": "P2", "target_lang": "auto"},
    },
    {
        "id": 5,
        "name": "Kanglish Query",
        "payload": {"query": "Agni mandya andre enu?", "mode": "P2", "target_lang": "auto"},
    },
    {
        "id": 6,
        "name": "Single-word Terminology Query",
        "payload": {"query": "ಆಮ", "mode": "P2", "target_lang": "auto"},
    },
    {
        "id": 7,
        "name": "Complex KG Subdosha Query",
        "payload": {"query": "What are the subdoshas of Vata and their locations?", "mode": "P2", "target_lang": "auto"},
    },
    {
        "id": 8,
        "name": "External Web Research Fallback Query",
        "payload": {"query": "What is the latest WHO report on traditional medicine research?", "mode": "P2", "target_lang": "auto", "web_fallback": True},
    },
    {
        "id": 9,
        "name": "Out-of-Scope Domain Abstention",
        "payload": {"query": "How to cure space station engine failure?", "mode": "P2", "target_lang": "auto"},
    },
]

def run_single(test):
    t0 = time.time()
    try:
        r = requests.post(f"{BASE_URL}/api/ask", json=test["payload"], timeout=60)
        roundtrip = round((time.time() - t0) * 1000, 2)
        if r.status_code == 200:
            data = r.json()
            return {
                "id": test["id"],
                "name": test["name"],
                "status": 200,
                "roundtrip_ms": roundtrip,
                "backend_latency_ms": data.get("latency_ms"),
                "stage_timings": data.get("stage_timings_ms", {}),
                "lang": data.get("target_language"),
                "generator": data.get("generator_used"),
                "abstained": data.get("abstained"),
                "passages": len(data.get("retrieved_passages", [])),
                "citations": len(data.get("citations", [])),
                "answer_preview": data.get("answer", "")[:140].replace("\n", " "),
            }
        else:
            return {
                "id": test["id"],
                "name": test["name"],
                "status": r.status_code,
                "roundtrip_ms": roundtrip,
                "error": r.text[:200],
            }
    except Exception as e:
        return {
            "id": test["id"],
            "name": test["name"],
            "status": "EXC",
            "roundtrip_ms": round((time.time() - t0) * 1000, 2),
            "error": str(e),
        }

def run_concurrent_test():
    print("\n--- Running Test 10: Concurrent Parallel Requests ---")
    req1 = {"query": "Explain Pitta dosha in Ayurveda", "mode": "P2", "target_lang": "en"}
    req2 = {"query": "Explain Kapha dosha in Ayurveda", "mode": "P2", "target_lang": "en"}
    
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(requests.post, f"{BASE_URL}/api/ask", json=req1, timeout=60)
        f2 = executor.submit(requests.post, f"{BASE_URL}/api/ask", json=req2, timeout=60)
        r1 = f1.result()
        r2 = f2.result()
    total_time = round((time.time() - t0) * 1000, 2)
    return {
        "id": 10,
        "name": "Concurrent Parallel Requests (Pitta & Kapha)",
        "r1_status": r1.status_code,
        "r2_status": r2.status_code,
        "r1_time_ms": r1.json().get("latency_ms") if r1.status_code == 200 else None,
        "r2_time_ms": r2.json().get("latency_ms") if r2.status_code == 200 else None,
        "wall_clock_ms": total_time,
        "success": r1.status_code == 200 and r2.status_code == 200,
    }

def main():
    # Warm up health check
    h = requests.get(f"{BASE_URL}/api/health", timeout=10)
    print("Health check status:", h.status_code)
    
    results = []
    for t in TESTS:
        print(f"Running Test {t['id']}: {t['name']}...")
        res = run_single(t)
        print(f"  -> Status {res.get('status')} in {res.get('roundtrip_ms')}ms (Backend: {res.get('backend_latency_ms')}ms)")
        results.append(res)
    
    conc_res = run_concurrent_test()
    print(f"  -> Both status 200: {conc_res['success']} in wall-clock {conc_res['wall_clock_ms']}ms")
    results.append(conc_res)
    
    with open("benchmark_results_current.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nBenchmark results saved to benchmark_results_current.json")

if __name__ == "__main__":
    main()

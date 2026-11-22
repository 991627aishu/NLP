# -*- coding: utf-8 -*-
"""
AUDIT 2 — Verification of /api/research/trace against actual RAG execution (/api/ask).
Compares retrieved passages, scores, citations, graph facts, and latencies.
"""
import sys
import json
import urllib.request
import urllib.parse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def audit_trace(query: str):
    print("=" * 80)
    print(f"AUDITING TRACE FOR: \"{query}\"")
    print("=" * 80)

    # 1. Call /api/ask
    ask_body = json.dumps({"query": query, "system_mode": "P2", "target_lang": "auto", "web_fallback": False}).encode("utf-8")
    ask_req = urllib.request.Request("http://127.0.0.1:8000/api/ask", data=ask_body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(ask_req) as resp:
        ask_data = json.loads(resp.read().decode("utf-8"))

    # 2. Call /api/research/trace
    trace_url = "http://127.0.0.1:8000/api/research/trace?query=" + urllib.parse.quote(query) + "&mode=P2"
    with urllib.request.urlopen(trace_url) as resp:
        trace_data = json.loads(resp.read().decode("utf-8"))

    # Compare
    ask_cids = [p["chunk_id"] for p in ask_data.get("retrieved_passages", [])]
    trace_cids = [p["chunk_id"] for p in trace_data.get("retrieved_passages", [])]
    ask_scores = [round(p.get("rrf_score", 0), 4) for p in ask_data.get("retrieved_passages", [])]
    trace_scores = [round(p.get("rrf_score", 0), 4) for p in trace_data.get("retrieved_passages", [])]
    ask_cits = [c["chunk_id"] for c in ask_data.get("citations", [])]

    print(f"Ask retrieved chunks ({len(ask_cids)}): {ask_cids}")
    print(f"Trace retrieved chunks ({len(trace_cids)}): {trace_cids}")
    print(f"Match exactly: {ask_cids == trace_cids}")

    print(f"\nAsk RRF scores: {ask_scores}")
    print(f"Trace RRF scores: {trace_scores}")
    print(f"Scores match exactly: {ask_scores == trace_scores}")

    print(f"\nAsk citations ({len(ask_cits)}): {ask_cits}")
    print(f"All citations exist in retrieved chunks: {all(c in ask_cids for c in ask_cits)}")

    print(f"\nGraph facts in Ask: {len(ask_data.get('graph_facts', []))}")
    print(f"Graph facts in Trace: {len(trace_data.get('trace', {}).get('step5_graph_grounding', {}).get('graph_facts', []))}")

    print(f"\nMeasured Ask latency: {round(ask_data.get('latency_ms', 0), 2)} ms")
    print(f"Measured Trace latency: {round(trace_data.get('latency_ms', 0), 2)} ms")

    steps = trace_data.get("trace_steps", [])
    print(f"\nTrace steps returned: {len(steps)}/7")
    for s in steps:
        print(f"  Step {s['step']}: {s['name']} [{s['module']}] -> {s['details'][:60]}...")

    return {
        "chunks_match": ask_cids == trace_cids,
        "scores_match": ask_scores == trace_scores,
        "citations_grounded": all(c in ask_cids for c in ask_cits),
        "steps_count": len(steps)
    }

if __name__ == "__main__":
    t1 = audit_trace("What is Ayurveda?")
    t2 = audit_trace("What are the functions of Pitta dosha?")
    t3 = audit_trace("How does Agni affect digestion?")
    all_ok = all(t["chunks_match"] and t["scores_match"] and t["citations_grounded"] and t["steps_count"] == 7 for t in [t1, t2, t3])
    print("\nOVERALL TRACE AUDIT VERDICT:", "PASSED" if all_ok else "FAILED")


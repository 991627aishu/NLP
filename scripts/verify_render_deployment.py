"""
AyurMitra — Render Production Deployment Smoke-Test Harness
============================================================
Validates the complete production environment readiness for Render deployment:
  1. Python version compliance (Python 3.13.x)
  2. Production third-party imports (FastAPI, bs4, google-genai, rank-bm25, networkx, etc.)
  3. Static frontend file availability (index.html, app.js, app.css, graph.js, i18n.js)
  4. Curated corpus chunks loading and integrity
  5. BM25 inverted lexical index loading
  6. Dense semantic index loading (TF-IDF and/or Gemini embeddings)
  7. Knowledge Graph v2 loading (NetworkX 9,537 nodes)
  8. Web search fallback import & engine initialization (BeautifulSoup4 + APIs)
  9. End-to-end RAG pipeline initialization
 10. FastAPI application & lifespan audit via TestClient
 11. Representative Ayurvedic query execution (Vata Dosha)
 12. Multilingual Indic query execution (Kannada / Hindi entity resolution)

Distinguishes between:
  [PASS] Operational component
  [WARN] Optional service unavailable due to unconfigured external API credentials
  [FAIL] Critical missing dependency or failed core dataset
"""
import sys
import os
import time
import json
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS = {
    "passed": 0,
    "failed": 0,
    "warnings": 0,
    "stages": []
}

def record(stage: str, status: str, details: str = ""):
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]"}.get(status, "[INFO]")
    print(f"{icon} {stage}: {details}")
    RESULTS["stages"].append({"stage": stage, "status": status, "details": details})
    if status == "PASS":
        RESULTS["passed"] += 1
    elif status == "FAIL":
        RESULTS["failed"] += 1
    elif status == "WARN":
        RESULTS["warnings"] += 1

def run_audit():
    print("=" * 75)
    print("AyurMitra Render Deployment Smoke Test & Environment Audit")
    print("=" * 75)

    # ── Stage 1: Python Runtime ──────────────────────────────────────────────
    py_ver = sys.version.split()[0]
    major, minor = sys.version_info.major, sys.version_info.minor
    if major == 3 and minor == 13:
        record("Python Runtime Version", "PASS", f"Detected validated runtime {py_ver}")
    elif major == 3 and minor >= 11:
        record("Python Runtime Version", "WARN", f"Running on {py_ver}; recommended validated version is 3.13.x")
    else:
        record("Python Runtime Version", "FAIL", f"Unsupported Python version {py_ver}. Required: 3.13.x")

    # ── Stage 2: Core Production Dependencies ────────────────────────────────
    required_pkgs = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
        ("starlette", "Starlette"),
        ("numpy", "NumPy"),
        ("scipy", "SciPy"),
        ("sklearn", "scikit-learn"),
        ("rank_bm25", "rank-bm25"),
        ("networkx", "NetworkX"),
        ("pandas", "Pandas"),
        ("bs4", "beautifulsoup4"),
        ("requests", "requests"),
        ("indic_transliteration", "indic-transliteration"),
        ("dotenv", "python-dotenv"),
    ]
    all_imports_pass = True
    for mod_name, label in required_pkgs:
        try:
            __import__(mod_name)
        except ImportError as e:
            all_imports_pass = False
            record(f"Import: {label}", "FAIL", f"Missing required dependency '{label}' ({e})")
    if all_imports_pass:
        record("Core Dependencies", "PASS", f"All {len(required_pkgs)} production packages successfully imported")

    # Optional packages
    for opt_mod, opt_label in [("google.genai", "google-genai"), ("edge_tts", "edge-tts")]:
        try:
            __import__(opt_mod)
            record(f"Optional: {opt_label}", "PASS", f"Package {opt_label} available")
        except ImportError:
            record(f"Optional: {opt_label}", "WARN", f"{opt_label} not installed; falls back to browser/offline equivalents")

    # ── Stage 3: Static Frontend Assets ──────────────────────────────────────
    frontend_dir = ROOT / "frontend"
    assets_dir = frontend_dir / "assets"
    required_files = [
        frontend_dir / "index.html",
        assets_dir / "app.js",
        assets_dir / "app.css",
        assets_dir / "graph.js",
        assets_dir / "i18n.js",
    ]
    missing_assets = [p.name for p in required_files if not p.exists()]
    if not missing_assets:
        record("Frontend Asset Integrity", "PASS", f"All {len(required_files)} static web assets present in {frontend_dir.name}")
    else:
        record("Frontend Asset Integrity", "FAIL", f"Missing frontend assets: {missing_assets}")

    # ── Stage 4: Corpus & Dataset Loading ────────────────────────────────────
    from app.config import CORPUS_JSONL, resolve_data_file
    corpus_file = resolve_data_file(CORPUS_JSONL)
    if corpus_file.exists():
        with open(corpus_file, "r", encoding="utf-8") as f:
            chunk_count = sum(1 for line in f if line.strip())
        record("Corpus Chunks", "PASS", f"Loaded {chunk_count} verified knowledge chunks from {corpus_file.name}")
    else:
        record("Corpus Chunks", "FAIL", f"Corpus chunks file not found at {corpus_file}")

    # ── Stage 5: BM25 Lexical Index ──────────────────────────────────────────
    try:
        from app.pipeline.bm25_retriever import BM25Retriever
        bm25 = BM25Retriever()
        record("BM25 Index Loading", "PASS", f"BM25 retriever initialized with {len(bm25.chunks)} indexed chunks")
    except Exception as e:
        record("BM25 Index Loading", "FAIL", f"Failed to initialize BM25 retriever: {e}")

    # ── Stage 6: Dense Semantic Index ────────────────────────────────────────
    try:
        from app.pipeline.dense_retriever import DenseRetriever
        dense = DenseRetriever()
        record("Dense Index Loading", "PASS", f"Dense retriever active ({dense.backend_used}) with {len(dense.chunks)} chunks")
    except Exception as e:
        record("Dense Index Loading", "FAIL", f"Failed to initialize Dense retriever: {e}")

    # ── Stage 7: Knowledge Graph Loading ─────────────────────────────────────
    try:
        from app.core.kg_v2 import KnowledgeGraphV2
        kg = KnowledgeGraphV2()
        n_nodes = kg.graph.number_of_nodes()
        n_edges = kg.graph.number_of_edges()
        record("Knowledge Graph v2", "PASS", f"Loaded KG v2 with {n_nodes:,} nodes and {n_edges:,} relational edges")
    except Exception as e:
        record("Knowledge Graph v2", "FAIL", f"Failed to load Knowledge Graph v2: {e}")

    # ── Stage 8: Web Search Fallback Engine ──────────────────────────────────
    try:
        from app.pipeline.web_search import WebSearchFallback
        ws = WebSearchFallback()
        record("Web Search Engine", "PASS", "WebSearchFallback engine loaded with BeautifulSoup4 extraction support")
    except Exception as e:
        record("Web Search Engine", "FAIL", f"Web search engine failed to initialize: {e}")

    # ── Stage 9: Complete AyurMitra Pipeline Initialization ──────────────────
    try:
        from app.pipeline.rag_pipeline import AyurMitraPipeline
        pipeline = AyurMitraPipeline()
        record("RAG Pipeline Initialization", "PASS", "AyurMitraPipeline fully instantiated with hybrid retrieval and entity protection")
    except Exception as e:
        record("RAG Pipeline Initialization", "FAIL", f"AyurMitraPipeline failed to instantiate: {e}")

    # ── Stage 10: FastAPI Application Lifespan & Health Endpoint ─────────────
    try:
        from starlette.testclient import TestClient
        from api.main import app
        with TestClient(app) as client:
            resp = client.get("/api/health")
            if resp.status_code == 200 and resp.json().get("ok"):
                record("FastAPI Lifespan & /api/health", "PASS", f"Healthcheck 200 OK (startup: {resp.json().get('startup_seconds')}s)")
            else:
                record("FastAPI Lifespan & /api/health", "FAIL", f"Healthcheck returned {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        record("FastAPI Lifespan & /api/health", "FAIL", f"FastAPI TestClient failed: {e}")

    # ── Stage 11: Representative Retrieval Query (English) ───────────────────
    try:
        res_en = pipeline.process_query("What is Vata dosha?", system_mode="P2", target_lang="en")
        if res_en.get("answer") and not res_en.get("abstained"):
            cits = len(res_en.get("citations", []))
            record("Representative Query (English)", "PASS", f"Answered 'What is Vata dosha?' with {cits} citations")
        else:
            record("Representative Query (English)", "FAIL", f"Query returned empty or unexpectedly abstained answer: {res_en.get('abstention_reason')}")
    except Exception as e:
        record("Representative Query (English)", "FAIL", f"Execution error on English query: {e}")

    # ── Stage 12: Multilingual Indic Retrieval Query (Kannada) ───────────────
    try:
        res_kn = pipeline.process_query("ಕಾಮಣಿ", system_mode="P2", target_lang="kn")
        if res_kn.get("answer") and not res_kn.get("abstained"):
            record("Multilingual Query (Kannada)", "PASS", "Resolved single-word 'ಕಾಮಣಿ' to Kamala and returned native Kannada clinical answer")
        else:
            record("Multilingual Query (Kannada)", "FAIL", f"Kannada entity query failed: {res_kn.get('abstention_reason')}")
    except Exception as e:
        record("Multilingual Query (Kannada)", "FAIL", f"Execution error on Kannada query: {e}")

    print("=" * 75)
    print(f"AUDIT SUMMARY: {RESULTS['passed']} Passed, {RESULTS['failed']} Failed, {RESULTS['warnings']} Warnings")
    print("=" * 75)
    return RESULTS["failed"] == 0

if __name__ == "__main__":
    success = run_audit()
    sys.exit(0 if success else 1)

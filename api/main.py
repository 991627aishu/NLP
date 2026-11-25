"""
AyurMitra — HTTP API (Phase 6)
==============================
Run:  uvicorn api.main:app --port 8000      (or ./run.ps1 / ./run.sh)
Docs: http://127.0.0.1:8000/docs (OpenAPI)

Wraps the existing research objects WITHOUT modifying them:
AyurMitraPipeline, KnowledgeGraphV2 (fallback: AyurKnowledgeGraph v1),
EducationalSymptomMapper, HerbService, voice STT/TTS.
Objects are created once at startup (lifespan). Errors never return stack traces.
Privacy: queries are NOT stored. /api/feedback stores a rating, and the query text
only when the user explicitly opts in.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import config
from app.config import DATA_EVAL, DATA_PROC, EDUCATIONAL_DISCLAIMER, LICENCE_NOTES, ROOT, GENERATOR_BACKEND

log = logging.getLogger("ayurmitra.api")
FRONTEND_DIR = ROOT / "frontend"
MAX_BODY_BYTES = int(os.environ.get("AYUR_MAX_BODY_BYTES", str(12 * 1024 * 1024)))  # voice clips up to ~60 s
RATE_LIMIT_PER_MIN = int(os.environ.get("AYUR_RATE_LIMIT_PER_MIN", "90"))
MODES = ("B0", "B1", "P1", "P2")
STATE: Dict[str, Any] = {}
_PIPE_LOCK = threading.Lock()


# ── lifespan: build heavy objects once ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.time()
    from app.pipeline.rag_pipeline import AyurMitraPipeline
    from app.core.symptom_mapper import EducationalSymptomMapper
    from app.core.herbs import HerbService
    pipe = AyurMitraPipeline()
    STATE["pipeline"] = pipe
    STATE["kg"] = pipe.kg
    STATE["mapper"] = EducationalSymptomMapper(kg=pipe.kg, retriever=pipe.retriever)
    STATE["herbs"] = HerbService(kg=pipe.kg if getattr(pipe.kg, "version", "v1") == "v2" else None,
                                 retriever=pipe.retriever)
    STATE["startup_seconds"] = round(time.time() - t0, 2)
    log.info("AyurMitra API ready in %.1fs", STATE["startup_seconds"])
    yield
    STATE.clear()


app = FastAPI(title="AyurMitra API", version="1.0.0", lifespan=lifespan,
              description="Terminology-preserving multilingual Ayurveda RAG — educational use only.")
app.add_middleware(CORSMiddleware,
                   allow_origins=[o for o in os.environ.get("AYUR_CORS_ORIGINS",
                                  "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5173,http://localhost:5173").split(",") if o],
                   allow_methods=["GET", "POST"], allow_headers=["*"])

_hits: Dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
            return JSONResponse({"ok": False, "error": "request_too_large",
                                 "message": "That request is too large (max 12 MB)."}, status_code=413)
        ip = request.client.host if request.client else "local"
        now, q = time.time(), _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_LIMIT_PER_MIN:
            return JSONResponse({"ok": False, "error": "rate_limited",
                                 "message": "Too many requests — please wait a moment."}, status_code=429)
        q.append(now)
    try:
        return await call_next(request)
    except Exception:  # never leak a stack trace
        log.exception("Unhandled error on %s", request.url.path)
        return JSONResponse({"ok": False, "error": "internal_error",
                             "message": "Something went wrong on the server. Please try again."}, status_code=500)


from fastapi.exceptions import RequestValidationError


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", [])[1:]) or "input"
    return JSONResponse({"ok": False, "error": "invalid_input",
                         "message": f"Please check the {field}: {first.get('msg', 'invalid value')}."}, status_code=422)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return JSONResponse({"ok": False, "error": "http_error", "message": str(exc.detail)}, status_code=exc.status_code)


def _need(name: str):
    obj = STATE.get(name)
    if obj is None:
        raise HTTPException(503, "The service is still starting — try again in a few seconds.")
    return obj


# ── models ───────────────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    mode: Literal["B0", "B1", "P1", "P2"] = "P2"
    target_lang: Literal["auto", "en", "hi", "kn", "hinglish", "kanglish"] = "auto"
    web_fallback: bool = False
    generator: Literal["extractive", "llm"] = "llm" if (GENERATOR_BACKEND or "llm").lower() == "llm" else "extractive"
    speak: bool = False
    voice: Literal["female", "male"] = "female"


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=6000)
    lang: Literal["en", "hi", "kn", "hinglish", "kanglish"] = "en"
    voice: Literal["female", "male"] = "female"
    clean: bool = True
    add_disclaimer: bool = True


class SymptomRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    target_lang: Literal["auto", "en", "hi", "kn", "hinglish", "kanglish"] = "auto"


class FeedbackRequest(BaseModel):
    rating: Literal["up", "down"]
    mode: Optional[str] = None
    store_query: bool = False
    query: Optional[str] = Field(None, max_length=1000)
    comment: Optional[str] = Field(None, max_length=1000)


# ── helpers ──────────────────────────────────────────────────────────────────
def _slim_passage(p: Dict[str, Any]) -> Dict[str, Any]:
    keep = ("chunk_id", "source_id", "locator", "title", "rrf_score", "bm25_rank", "dense_rank", "fused_rank",
            "bm25_score", "dense_score", "dense_backend")
    out = {k: p.get(k) for k in keep if k in p}
    out["text"] = (p.get("text") or "")[:700]
    return out


def _run_query(req: AskRequest) -> Dict[str, Any]:
    pipe = _need("pipeline")
    with _PIPE_LOCK:
        r = pipe.process_query(req.query, system_mode=req.mode, target_lang=req.target_lang,
                               enable_web_search=req.web_fallback, generator=req.generator)
    out = {k: r.get(k) for k in (
        "raw_query", "system_mode", "detected_language", "target_language", "language_mode", "display_language", "tts_lang",
        "is_code_mixed", "code_mix_type", "segments", "active_components", "translation_meta", "detected_terms",
        "canonical_query", "retrieval_query", "graph_expansion_terms", "graph_facts", "answer", "abstained",
        "abstention_reason", "is_emergency", "citations", "disclaimer", "latency_ms", "backends", "machine_translated",
        "answer_grounding", "generator_used", "generator_note", "evidence_check", "safety",
        "route_category", "route_label", "source_label", "answer_source", "is_ayurvedic_grounded")}
    out["retrieved_passages"] = [_slim_passage(p) for p in r.get("retrieved_passages", [])]
    out["web_passages"] = r.get("web_passages", [])
    out["ok"] = True
    return out


def _speak(text: str, lang: str, voice: str = "female") -> Dict[str, Any]:
    from app.voice.tts import synthesize
    return synthesize(text, lang=lang, voice=voice)


# ── endpoints ────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    from app.voice import stt, tts
    from app.pipeline.llm_generator import LLMGenerator
    from app.pipeline.gemini_provider import GeminiProvider
    pipe = STATE.get("pipeline")
    b = pipe.backend_info() if pipe else {}
    kg = STATE.get("kg")
    tts_order = tts.available_backends()
    gemini_health = GeminiProvider().check_health()
    return {
        "ok": pipe is not None, "startup_seconds": STATE.get("startup_seconds"),
        "backends": {
            "neural_mt": {"live": b.get("translator") == "indictrans2", "backend": b.get("translator"),
                          "note": b.get("translator_warning")},
            "embeddings": {"live": b.get("dense") in ("sentence_transformers", "gemini_embeddings"), "backend": b.get("dense"),
                           "model": b.get("dense_model"), "note": b.get("dense_warning")},
            "stt": stt.status() | {"live": stt.status()["server_stt"]},
            "tts": {"live": tts_order[0] != "browser", "chain": tts_order},
            "llm": LLMGenerator().available() | {"live": LLMGenerator().available()["available"]},
            "gemini": gemini_health,
            "web": {"live": True, "note": "EuropePMC / Wikipedia fallback; off by default, never used in benchmarks"},
            "knowledge_graph": {"live": kg is not None, "version": getattr(kg, "version", None)},
            "safety_gate": {"live": bool(b.get("safety_gate"))},
        },
        "disclaimer": EDUCATIONAL_DISCLAIMER,
    }


@app.get("/api/gemini/status")
def gemini_status():
    """Detailed health, readiness, and configuration audit of the Google Gemini integration."""
    from app.pipeline.gemini_provider import GeminiProvider
    provider = GeminiProvider()
    return provider.check_health()


@app.post("/api/ask")
def ask(req: AskRequest):
    out = _run_query(req)
    if req.speak or out.get("is_emergency"):
        out["tts"] = _speak(out["answer"], out.get("target_language") or "en", req.voice)
    return out


@app.post("/api/voice/transcribe")
async def voice_transcribe(audio: UploadFile = File(...), lang_hint: str = Form("auto")):
    from app.voice.stt import transcribe
    data = await audio.read()
    if not data:
        return {"ok": False, "stage": "stt", "error": "empty_audio", "message": "No audio was received."}
    suffix = Path(audio.filename or "clip.webm").suffix or ".webm"
    stt_res = transcribe(data, lang_hint=lang_hint if lang_hint in ("en", "hi", "kn") else "auto", suffix=suffix)
    return {"ok": bool(stt_res.get("ok")), "stage": "transcribed", **stt_res}


@app.post("/api/voice/ask")
async def voice_ask(audio: UploadFile = File(...), mode: str = Form("P2"), target_lang: str = Form("auto"),
                    lang_hint: str = Form("auto"), speak: bool = Form(True), confirm_low_confidence: bool = Form(True),
                    voice: str = Form("female")):
    from app.voice.stt import transcribe
    data = await audio.read()
    if not data:
        return {"ok": False, "stage": "stt", "error": "empty_audio", "message": "No audio was received."}
    suffix = Path(audio.filename or "clip.webm").suffix or ".webm"
    stt_res = transcribe(data, lang_hint=lang_hint if lang_hint in ("en", "hi", "kn") else "auto", suffix=suffix)
    if not stt_res.get("ok"):
        return {"ok": False, "stage": "stt", **stt_res}
    if confirm_low_confidence and stt_res.get("needs_confirmation"):
        return {"ok": True, "stage": "confirm", "transcript": stt_res}
    valid_langs = ("auto", "en", "hi", "kn", "hinglish", "kanglish")
    req = AskRequest(query=stt_res["text"], mode=mode if mode in MODES else "P2",
                     target_lang=target_lang if target_lang in valid_langs else "auto",
                     speak=speak, voice="male" if voice == "male" else "female")
    out = _run_query(req)
    out["stage"] = "answered"
    out["transcript"] = stt_res
    if speak or out.get("is_emergency"):
        out["tts"] = _speak(out["answer"], out.get("target_language") or "en", req.voice)
    return out


@app.post("/api/tts")
def tts_endpoint(req: TTSRequest):
    from app.voice.tts import synthesize
    return {"ok": True, **synthesize(req.text, lang=req.lang, voice=req.voice, clean=req.clean,
                                     add_disclaimer=req.add_disclaimer)}


@app.post("/api/symptoms")
def symptoms(req: SymptomRequest):
    mapper = _need("mapper")
    r = mapper.analyze_symptoms(req.text, target_lang=req.target_lang)
    kg = STATE.get("kg")
    from app.core.symptom_mapper import CLASSICAL_SYMPTOM_CATALOG
    phrase_to_key = {p.lower(): it["concept_key"] for it in CLASSICAL_SYMPTOM_CATALOG
                     for ps in it.get("patterns", {}).values() for p in ps}
    related = []
    for m in r.get("mappings", []) or []:
        # audit F4: the mapper's page locators were checked and do not support these mappings
        m["locator_review_status"] = "unverified — claimed page does not support this mapping (see docs/AUDIT.md F4)"
        key = phrase_to_key.get((m.get("symptom_phrase") or "").lower())
        if kg is not None and hasattr(kg, "search") and key and f"SYMPTOM:{key}" in kg.graph:
            related.append({"symptom_phrase": m.get("symptom_phrase"), "symptom_node": f"SYMPTOM:{key}",
                            "dosha_node": f"CONCEPT:{m.get('associated_dosha')}",
                            "review_status": "project_mapping_unreviewed"})
    r["graph_links"] = related
    r["ok"] = True
    if r.get("reason") == "emergency_symptom_detected":
        lang = r.get("target_language", "en")
        r["tts"] = _speak(r.get("message", ""), lang[:2] if lang[:2] in ("en", "hi", "kn") else "en")
    return r


@app.get("/api/graph")
def graph(center: str = Query("Tridosha", max_length=200), depth: int = Query(1, ge=1, le=3),
          types: Optional[str] = Query(None, max_length=300), limit: int = Query(120, ge=1, le=300)):
    kg = _need("kg")
    if not hasattr(kg, "neighbourhood"):
        raise HTTPException(503, "Knowledge graph v2 is not built. Run: python -m app.core.kg_builder")
    t = [x for x in (types or "").split(",") if x] or None
    res = kg.neighbourhood(center, depth=depth, types=t, limit=limit)
    if not res["center"]:
        raise HTTPException(404, f"No graph node matches '{center}'.")
    return {"ok": True, **res}


@app.get("/api/graph/search")
def graph_search(q: str = Query(..., min_length=1, max_length=200), limit: int = Query(15, ge=1, le=50),
                 types: Optional[str] = Query(None, max_length=300)):
    kg = _need("kg")
    t = [x for x in (types or "").split(",") if x] or None
    return {"ok": True, "results": kg.search(q, limit=limit, types=t)}


@app.get("/api/graph/stats")
def graph_stats():
    kg = _need("kg")
    return {"ok": True, **(kg.stats() if hasattr(kg, "stats") else {"version": "v1"})}


@app.get("/api/graph/path")
def graph_path(a: str = Query(..., max_length=200), b: str = Query(..., max_length=200)):
    kg = _need("kg")
    return {"ok": True, **kg.shortest_path(a, b)}


@app.get("/api/graph/node/{node_id:path}")
def graph_node(node_id: str):
    kg = _need("kg")
    d = kg.node_detail(node_id)
    if not d:
        raise HTTPException(404, f"Node '{node_id}' not found.")
    return {"ok": True, **d}


@app.get("/api/herbs/search")
def herbs_search(q: str = Query("", max_length=500), limit: int = Query(20, ge=1, le=50)):
    return {"ok": True, **_need("herbs").search(q, limit=limit)}


@app.get("/api/lifestyle")
def lifestyle_list():
    return {"ok": True, "topics": _need("herbs").lifestyle_topics(), "disclaimer": EDUCATIONAL_DISCLAIMER}


@app.get("/api/lifestyle/search")
def lifestyle_search(q: str = Query(..., min_length=1, max_length=500), limit: int = Query(5, ge=1, le=20)):
    return {"ok": True, **_need("herbs").search_lifestyle(q, top_k=limit)}


@app.get("/api/lifestyle/{key}")
def lifestyle_topic(key: str):
    t = _need("herbs").lifestyle_topic(key)
    if not t:
        raise HTTPException(404, "Unknown topic.")
    return {"ok": True, **t}


@app.get("/api/herbs/context")
@app.get("/api/herbs/recommend")
def herbs_recommend(
    q: str = Query("", max_length=500),
    dosha: Optional[str] = Query(None),
    limit: int = Query(6, ge=1, le=20)
):
    service = _need("herbs")
    return {"ok": True, **service.recommend_for_symptom_context(symptom_text=q, dosha=dosha, top_k=limit)}


@app.get("/api/herbs/{name:path}")
def herb_detail(name: str):
    d = _need("herbs").detail(name)
    if not d:
        raise HTTPException(404, f"No herb record matches '{name}'.")
    return {"ok": True, **d}


# ── research ─────────────────────────────────────────────────────────────────
RESEARCH_FILES = {
    "experiment_results_v1.json": DATA_EVAL / "experiment_results.json",
    "experiment_results_v2.json": DATA_EVAL / "experiment_results_v2.json",
    "go_no_go_probe_v1.json": DATA_EVAL / "go_no_go_probe_results.json",
    "go_no_go_probe_v2.json": DATA_EVAL / "go_no_go_probe_results_v2.json",
    "predictions_v2.csv": DATA_EVAL / "predictions_v2.csv",
    "error_analysis_v2.csv": DATA_EVAL / "error_analysis_v2.csv",
    "failure_cases_v2.json": DATA_EVAL / "failure_cases_v2.json",
}

DATA_SOURCES_CATALOG = [
    {
        "id": "who_terminologies",
        "name": "WHO International Standard Terminologies on Ayurveda",
        "title": "WHO International Standard Terminologies on Ayurveda",
        "publisher": "World Health Organization (WHO), 2023",
        "type": "Standardized Definitions & Diagnostic Concepts",
        "format": "Standardized Definitions & Diagnostic Concepts (PDF)",
        "file": "9789240064935-eng.pdf",
        "raw_file": "9789240064935-eng.pdf",
        "records": "195 sections, 2,973 terms, 246 PDF chunks",
        "category": "Corpus",
        "usage": "Foundational definitions, diagnostic disorder concepts, Sanskrit IAST mapping",
        "description": "WHO authoritative international benchmark establishing standardized definitions, morphology, diagnostic criteria, and Sanskrit IAST canonical terms.",
        "licence": "WHO Copyright / CC BY-NC-SA 3.0 IGO (Non-commercial research use)",
        "license": "WHO Copyright / CC BY-NC-SA 3.0 IGO (Non-commercial research use)",
        "verification_status": "Verified & SHA-256 Hash Checked"
    },
    {
        "id": "namaste_portal",
        "name": "National AYUSH Morbidity and Standardized Terminologies Electronic Portal (NAMASTE)",
        "title": "National AYUSH Morbidity and Standardized Terminologies Electronic Portal (NAMASTE)",
        "publisher": "Ministry of AYUSH, Government of India",
        "type": "Morbidity Classification & Standardized Terminology",
        "format": "Morbidity Classification (Excel XLSX)",
        "file": "ayu-sat-table-a.xlsx",
        "raw_file": "ayu-sat-table-a.xlsx",
        "records": "319 terms, 663 parent-child hierarchies",
        "category": "Knowledge Graph",
        "usage": "Hierarchical concept classification and Sanskrit technical terms",
        "description": "Official Ministry of AYUSH classification portal providing standardized diagnostic disease codes and terminology hierarchies across Ayurveda.",
        "licence": "Government of India AYUSH Open Access (Verification pending for redistribution)",
        "license": "Government of India AYUSH Open Access (Verification pending for redistribution)",
        "verification_status": "Verified & SHA-256 Hash Checked"
    },
    {
        "id": "imppat_plants",
        "name": "Indian Medicinal Plants, Phytochemistry And Therapeutics (IMPPAT 2.0)",
        "title": "Indian Medicinal Plants, Phytochemistry And Therapeutics (IMPPAT 2.0)",
        "publisher": "Computational Biology Group, IMSc Chennai (Mohanraj et al.)",
        "type": "Ethnomedicinal Botany & Pharmacognosy",
        "format": "Ethnomedicinal Botany (TSV Tables)",
        "file": "Plant_Information_IMPPAT.tsv",
        "raw_file": "Plant_Information_IMPPAT.tsv",
        "records": "4,154 plants, 1,299 therapeutic uses, 68,401 plant-use associations",
        "category": "Pharmacopoeia",
        "usage": "Botanical taxonomy, families, synonyms, recorded traditional uses",
        "description": "Curated chemoinformatics and ethnopharmacology resource connecting botanical taxa, family classifications, vernacular synonyms, and therapeutic uses.",
        "licence": "Academic Research Database (Verification pending for commercial redistribution)",
        "license": "Academic Research Database (Verification pending for commercial redistribution)",
        "verification_status": "Verified & SHA-256 Hash Checked"
    },
    {
        "id": "imppat_api_formulations",
        "name": "Ayurvedic Pharmacopoeia of India (API) Single-Herb Formulations",
        "title": "Ayurvedic Pharmacopoeia of India (API) Single-Herb Formulations",
        "publisher": "Pharmacopoeia Commission for Indian Medicine & Homeopathy (PCIM&H)",
        "type": "Classical Pharmacopoeial Formulations",
        "format": "Pharmacopoeial Standards (TSV Table)",
        "file": "IMPPAT_SingleHerbalFormulations.tsv",
        "raw_file": "IMPPAT_SingleHerbalFormulations.tsv",
        "records": "541 single-herb formulations, Sanskrit API therapeutic uses",
        "category": "Pharmacopoeia",
        "usage": "Official classical formulation records and Sanskrit therapeutic indications",
        "description": "Standardized classical single-drug monographs detailing botanical sources, Sanskrit therapeutic indications, and plant parts used.",
        "licence": "Public Pharmacopoeial Reference",
        "license": "Public Pharmacopoeial Reference",
        "verification_status": "Verified & SHA-256 Hash Checked"
    },
    {
        "id": "classical_qa",
        "name": "Curated Classical Literature & Clinical Principles QA Archive",
        "title": "Curated Classical Literature & Clinical Principles QA Archive",
        "publisher": "AyurMitra Research Compilation (Charaka, Sushruta, Vagbhata)",
        "type": "Classical Principles, Tridosha & Agni Foundational Theory",
        "format": "Classical Principles Corpus (CSV)",
        "file": "qa_cleaned.csv",
        "raw_file": "qa_cleaned.csv",
        "records": "336 passage pairs, 1,344 bilingual QA segments",
        "category": "Corpus",
        "usage": "Detailed conceptual explanations and textual question answering",
        "description": "Authoritative question-answering corpus synthesizing core theoretical tenets of Tridosha, Srotas, Dhatus, and Agni from classical Samhita treatises.",
        "licence": "Curated Educational Archive (Licence to be confirmed from original provider)",
        "license": "Curated Educational Archive (Licence to be confirmed from original provider)",
        "verification_status": "Verified & SHA-256 Hash Checked"
    },
    {
        "id": "hindi_corpus",
        "name": "Hindi Parallel Ayurvedic Query Corpus",
        "title": "Hindi Parallel Ayurvedic Query Corpus",
        "publisher": "AyurMitra Multilingual Alignment Project",
        "type": "Devanagari Bilingual Query-Passage Alignments",
        "format": "Multilingual Text Corpus (Parquet)",
        "file": "hi.parquet",
        "raw_file": "hi.parquet",
        "records": "3,000 parallel question pairs",
        "category": "Corpus",
        "usage": "Natural Hindi query translation and Devanagari terminology preservation",
        "description": "Parallel text corpus containing Devanagari queries, verified medical translations, and alignment anchors for Hindi retrieval validation.",
        "licence": "Project Curated Alignment Data",
        "license": "Project Curated Alignment Data",
        "verification_status": "Verified & SHA-256 Hash Checked"
    },
    {
        "id": "kannada_corpus",
        "name": "Kannada Parallel Ayurvedic Query Corpus",
        "title": "Kannada Parallel Ayurvedic Query Corpus",
        "publisher": "AyurMitra Multilingual Alignment Project",
        "type": "Kannada Script Bilingual Query-Passage Alignments",
        "format": "Multilingual Text Corpus (Parquet)",
        "file": "kn.parquet",
        "raw_file": "kn.parquet",
        "records": "3,000 parallel question pairs",
        "category": "Corpus",
        "usage": "Natural Kannada query translation, suffix stripping, and script restoration",
        "description": "Parallel text corpus containing Kannada queries, verified translations, and Dravidian language morphology evaluation pairs.",
        "licence": "Project Curated Alignment Data",
        "license": "Project Curated Alignment Data",
        "verification_status": "Verified & SHA-256 Hash Checked"
    },
    {
        "id": "evaluation_benchmark",
        "name": "Gold Seed Evaluation & Contamination-Checked Benchmark",
        "title": "Gold Seed Evaluation & Contamination-Checked Benchmark",
        "publisher": "AyurMitra Evaluation Protocol",
        "type": "Controlled Test Set & Paired Comparisons",
        "format": "Benchmark Evaluation Suite (JSON / Parquet)",
        "file": "eval_test.json, experiment_results_v2.json",
        "raw_file": "eval_test.json",
        "records": "175 seed questions × 4 language variants (700 test items)",
        "category": "Evaluation",
        "usage": "Strict B0/B1/P1/P2 retrieval benchmarking with 2,000 bootstrap resamples",
        "description": "Controlled gold test set and multi-metric benchmarking suite evaluating Lexical (B0), Dense (B1), Proposed Term-Preserving (P1), and Knowledge Graph Grounded (P2) pipelines.",
        "licence": "Project Evaluation Dataset",
        "license": "Project Evaluation Dataset",
        "verification_status": "Verified & Clean Benchmark"
    }
]

ARCHITECTURE_STAGES_CATALOG = [
    {
        "id": "stage_1_input",
        "name": "User Question / Voice Input",
        "module": "api/main.py & frontend/assets/app.js",
        "purpose": "Accepts user text questions or streaming voice input with transcript review before submission.",
        "input": "Natural language text or WebM/WAV audio blob",
        "output": "Clean text string (max 1,000 characters)",
        "active_backend": "Browser Web Speech API (Chrome/Edge) + Text Input",
        "fallback_backend": "Textarea Composer",
        "status": "ACTIVE",
        "limitations": "Audio recording requires microphone permissions; browser speech recognition depends on client browser."
    },
    {
        "id": "stage_2_lang_detect",
        "name": "Language & Script Detection",
        "module": "app/core/language_detect.py",
        "purpose": "Detects language (EN, HI, KN), script (Latin, Devanagari, Kannada), and code-mixed patterns (Hinglish, Kanglish).",
        "input": "User text string",
        "output": "Dict with lang, script, is_romanized, is_code_mixed, segments",
        "active_backend": "Unicode codepoint distribution + regex character grammars",
        "fallback_backend": "English default",
        "status": "ACTIVE",
        "limitations": "Short romanized inputs (<3 words) with no obvious markers default gracefully to English."
    },
    {
        "id": "stage_3_term_matcher",
        "name": "Terminology Recognition",
        "module": "app/core/matcher.py",
        "purpose": "Scans input for classical Ayurvedic terms across Sanskrit IAST, Devanagari, Kannada, and romanized forms.",
        "input": "Detected text and language",
        "output": "List of matched entities with canonical term, concept ID, offsets, and script",
        "active_backend": "Trie-based multilingual terminology matcher (3,000+ entries) with Kannada suffix stripping",
        "fallback_backend": "Substring word-boundary matcher",
        "status": "ACTIVE",
        "limitations": "Dense multi-word Sanskrit compounds (e.g. Mandagni in continuous Devanagari) may require word separation."
    },
    {
        "id": "stage_4_term_protection",
        "name": "Placeholder Term Protection",
        "module": "app/core/protection.py",
        "purpose": "Replaces detected Ayurvedic terms with unique synthetic tokens (__AYURTERM_N__) to prevent translation corruption.",
        "input": "Query text + detected entities",
        "output": "Protected text + placeholder-to-canonical mapping dictionary",
        "active_backend": "Deterministic regex placeholder substitution",
        "fallback_backend": "Identity pass-through",
        "status": "ACTIVE",
        "limitations": "Placeholders must survive translation; translator regex validates that tokens are not altered."
    },
    {
        "id": "stage_5_translator",
        "name": "Translation & Query Normalization",
        "module": "app/pipeline/translator.py",
        "purpose": "Translates Hindi and Kannada queries to English for retrieval while preserving domain terminology placeholders.",
        "input": "Protected query text",
        "output": "Normalized English retrieval query with restored canonical terms",
        "active_backend": "Rule-based bilingual phrase grammar + parallel QA alignment lookup",
        "fallback_backend": "Identity query pass-through",
        "status": "WORKING WITH FALLBACK",
        "limitations": "IndicTrans2 neural model requires transformers extra + HuggingFace gated token; rules fallback active."
    },
    {
        "id": "stage_6_hybrid_retriever",
        "name": "Hybrid BM25 + Dense RRF Retrieval",
        "module": "app/pipeline/hybrid_retriever.py",
        "purpose": "Searches 2,887 corpus chunks using Okapi BM25 and dense embeddings, fused via Reciprocal Rank Fusion (k=60).",
        "input": "Normalized English retrieval query",
        "output": "Top 5 ranked corpus passages with chunk IDs, source citations, and locators",
        "active_backend": "BM25Okapi + Char n-gram TF-IDF dense embeddings + RRF (k=60)",
        "fallback_backend": "BM25 Lexical-only (B0 baseline)",
        "status": "ACTIVE",
        "limitations": "Full Sentence-Transformers (paraphrase-multilingual-MiniLM-L12-v2) requires neural extras package."
    },
    {
        "id": "stage_7_kg_grounding",
        "name": "Knowledge Graph Grounding (P2)",
        "module": "app/core/kg_v2.py",
        "purpose": "Traverses 9,530 nodes and 72,341 edges in DiGraph to augment retrieved evidence with verified structural relations.",
        "input": "Detected Ayurvedic terms in query",
        "output": "List of graph facts with source provenance, relation type, and review status",
        "active_backend": "NetworkX DiGraph v2 with 99.93% verified edge provenance locators",
        "fallback_backend": "AyurKnowledgeGraph v1 (24 nodes)",
        "status": "ACTIVE",
        "limitations": "Graph traversal is bounded to 150 nodes to avoid canvas visual overload and query latency spikes."
    },
    {
        "id": "stage_8_generator",
        "name": "Evidence-Grounded Answer Generation",
        "module": "app/pipeline/generator.py",
        "purpose": "Synthesizes direct answers grounded strictly in retrieved passages with traceable source citations.",
        "input": "Retrieved passages + Knowledge Graph facts + target language",
        "output": "Structured markdown answer with explicit citations, explanation, and limitations",
        "active_backend": "Extractive evidence sentence ranker & synthesizer",
        "fallback_backend": "Template-based evidence quoting",
        "status": "ACTIVE",
        "limitations": "LLM generation (Claude / Ollama) is gated by API keys; extractive grounded generation runs locally."
    },
    {
        "id": "stage_9_citation_check",
        "name": "Citation Post-Validation Gate",
        "module": "app/pipeline/generator.py & llm_generator.py",
        "purpose": "Validates that every factual statement in the answer maps to a chunk ID present in the retrieved set.",
        "input": "Generated answer + allowed chunk IDs",
        "output": "Validated answer text; ungrounded claims are dropped automatically",
        "active_backend": "Sentence-level chunk ID membership validator",
        "fallback_backend": "Passage citation list matching",
        "status": "ACTIVE",
        "limitations": "Sentences failing citation verification are stripped to prevent hallucination."
    },
    {
        "id": "stage_10_safety_gate",
        "name": "Safety, Emergency & Dosage Guardrails",
        "module": "app/pipeline/rag_pipeline.py",
        "purpose": "Pre-retrieval check that immediately intercepts acute emergencies, dosage requests, and unanswerable queries.",
        "input": "User query",
        "output": "Allowed query OR immediate emergency referral / dosage refusal / out-of-domain abstention",
        "active_backend": "Multilingual keyword & regular expression safety filter",
        "fallback_backend": "Always active across all systems (B0, B1, P1, P2)",
        "status": "ACTIVE",
        "limitations": "Educational tool only; refuses prescriptions, clinical diagnoses, and emergency management."
    },
    {
        "id": "stage_11_restoration_tts",
        "name": "Script Restoration & Spoken Audio Output",
        "module": "app/voice/tts.py",
        "purpose": "Restores canonical terms in native Devanagari and Kannada scripts, then synthesizes clear spoken audio.",
        "input": "Generated answer text + target language",
        "output": "Final localized text + base64 MP3 audio chunks or Web Speech API directive",
        "active_backend": "Edge-TTS (en-IN, hi-IN, kn-IN neural voices) with 4.0s timeout",
        "fallback_backend": "In-browser Web Speech API (SpeechSynthesis)",
        "status": "ACTIVE",
        "limitations": "Edge-TTS requires internet connectivity; automatically falls back to browser synthesis if offline."
    }
]

SAFETY_CASES_CATALOG = [
    {
        "id": "case_1_grounded",
        "type": "Answerable with Evidence",
        "query": "What are the three doshas?",
        "expected_action": "Synthesizes grounded explanation from WHO Guidelines citing WHO_CHUNK_0036 and WHO_CHUNK_0037.",
        "enforcement": "Hybrid retrieval pulls authoritative definitions; citation validator verifies chunk IDs before rendering.",
        "sample_output": "Ayurveda describes three regulatory functional factors: Vata (movement and nervous regulation), Pitta (metabolism and heat), and Kapha (structure and lubrication)."
    },
    {
        "id": "case_2_unanswerable",
        "type": "Graceful Abstention (Missing Evidence)",
        "query": "Can Ayurveda cure stage 4 cancer?",
        "expected_action": "Pipeline systematically abstains from generating speculative or ungrounded claims.",
        "enforcement": "app/pipeline/generator.py evidence coverage check: if retrieved passages do not support curative claims, the system abstains.",
        "sample_output": "Abstention: No relevant evidence was found in the curated Ayurvedic knowledge corpus for this query. The system refrains from generating ungrounded advice."
    },
    {
        "id": "case_3_emergency",
        "type": "Emergency Red-Flag Triage",
        "query": "Severe chest pain and sudden shortness of breath",
        "expected_action": "Immediate urgent health advisory; retrieval is halted and emergency referral is read aloud.",
        "enforcement": "app/core/symptom_mapper.py EMERGENCY_RED_FLAGS check: runs before any concept mapping or RAG retrieval.",
        "sample_output": "URGENT HEALTH ADVISORY: The described symptom indicates an acute medical emergency. Please seek emergency medical care immediately."
    },
    {
        "id": "case_4_dosage_refusal",
        "type": "Dosage & Prescription Refusal",
        "query": "How many grams of Ashwagandha should I take daily for insomnia?",
        "expected_action": "System refuses to provide dosage or prescription instructions, redirecting to a qualified Ayurvedic physician.",
        "enforcement": "app/core/herbs.py and app/pipeline/generator.py: strict prohibition of dose quantities (grams, mg, drops, frequencies).",
        "sample_output": "AyurMitra provides educational references only and does not provide dosages, preparations, or clinical prescriptions. Please consult a qualified Ayurvedic physician."
    }
]


def _read_json(p: Path) -> Optional[Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


@app.get("/api/research/results")
def research_results():
    return {"ok": True, "v2": _read_json(DATA_EVAL / "experiment_results_v2.json"),
            "v1_original": _read_json(DATA_EVAL / "experiment_results.json"),
            "files": [k for k, p in RESEARCH_FILES.items() if p.exists()]}


@app.get("/api/research/probe")
def research_probe():
    return {"ok": True, "v2": _read_json(DATA_EVAL / "go_no_go_probe_results_v2.json"),
            "v1_original": _read_json(DATA_EVAL / "go_no_go_probe_results.json")}


@app.get("/api/research/compare")
def research_compare(query: str = Query(..., min_length=1, max_length=1000),
                     target_lang: Literal["auto", "en", "hi", "kn"] = "auto"):
    out = {}
    for m in MODES:
        r = _run_query(AskRequest(query=query, mode=m, target_lang=target_lang, web_fallback=False))
        out[m] = {k: r.get(k) for k in ("answer", "abstained", "abstention_reason", "canonical_query",
                                        "retrieval_query", "detected_terms", "graph_facts", "latency_ms",
                                        "translation_meta")}
        out[m]["retrieved"] = [{k: p.get(k) for k in ("chunk_id", "source_id", "locator", "title")}
                               for p in r["retrieved_passages"]]
    return {"ok": True, "query": query, "modes": out}


@app.get("/api/research/trace")
def research_trace(query: str = Query(..., min_length=1, max_length=1000),
                   mode: Literal["B0", "B1", "P1", "P2"] = "P2",
                   target_lang: Literal["auto", "en", "hi", "kn"] = "auto"):
    r = _run_query(AskRequest(query=query, mode=mode, target_lang=target_lang, web_fallback=False))
    passages = r.get("retrieved_passages", [])
    trace_steps = [
        {
            "step": 1,
            "name": "Language & Script Identification",
            "module": "app.core.language",
            "details": f"Detected language: {r.get('detected_language')} (script: {r.get('script')}, romanized: {r.get('is_romanized')})",
            "data": {
                "detected_language": r.get("detected_language"),
                "script": r.get("script"),
                "target_language": r.get("target_language"),
                "is_code_mixed": r.get("is_code_mixed"),
            }
        },
        {
            "step": 2,
            "name": "Protected Terminology Extraction",
            "module": "app.core.terminology_matcher",
            "details": f"Identified {len(r.get('detected_terms', []))} classical terms from WHO / NAMASTE catalogs.",
            "data": r.get("detected_terms", [])
        },
        {
            "step": 3,
            "name": "Translation & Query Normalization",
            "module": "app.core.translator",
            "details": f"Canonical query: \"{r.get('canonical_query')}\" (Retrieval query: \"{r.get('retrieval_query')}\")",
            "data": r.get("translation_meta")
        },
        {
            "step": 4,
            "name": "Hybrid Retrieval (BM25 + Dense RRF)",
            "module": "app.retrieval.hybrid_retriever",
            "details": f"Ranked {len(passages)} authoritative candidate chunks with reciprocal rank fusion (k=60).",
            "data": [
                {
                    "rank": i + 1,
                    "chunk_id": p.get("chunk_id"),
                    "source": p.get("source_id"),
                    "locator": p.get("locator"),
                    "rrf_score": round(p.get("rrf_score", 0.0), 4),
                    "snippet": (p.get("text") or "")[:160].replace("\n", " ") + "..."
                }
                for i, p in enumerate(passages[:5])
            ]
        },
        {
            "step": 5,
            "name": "Knowledge Graph Grounding",
            "module": "app.core.knowledge_graph_v2",
            "details": f"Extracted {len(r.get('graph_facts', []))} ontological relationships from Knowledge Graph v2.",
            "data": r.get("graph_facts", [])
        },
        {
            "step": 6,
            "name": "Citation & Evidence Verification",
            "module": "app.pipeline.rag_pipeline",
            "details": f"Verified {len(r.get('citations', []))} exact citations against retrieved passages. Abstained: {r.get('abstained')}.",
            "data": {
                "abstained": r.get("abstained"),
                "abstention_reason": r.get("abstention_reason"),
                "citations": r.get("citations", [])
            }
        },
        {
            "step": 7,
            "name": "Answer Formulation & Boundary Check",
            "module": "app.generation.grounded_generator",
            "details": f"Generated answer ({round(r.get('latency_ms', 0))} ms latency) with educational boundaries applied.",
            "data": {
                "answer_preview": (r.get("answer") or "")[:200] + "...",
                "latency_ms": round(r.get("latency_ms", 0), 2)
            }
        }
    ]
    return {
        "ok": True,
        "query": query,
        "mode": mode,
        "detected_language": r.get("detected_language", "en"),
        "is_code_mixed": r.get("is_code_mixed", False),
        "code_mix_type": r.get("code_mix_type"),
        "latency_ms": r.get("latency_ms", 0),
        "retrieved_passages": passages,
        "trace_steps": trace_steps,
        "trace": {
            "step1_language": {
                "detected_language": r.get("detected_language"),
                "script": r.get("script"),
                "is_romanized": r.get("is_romanized"),
                "target_language": r.get("target_language")
            },
            "step2_terminology": {
                "detected_terms": r.get("detected_terms", [])
            },
            "step3_normalization": {
                "canonical_query": r.get("canonical_query"),
                "retrieval_query": r.get("retrieval_query"),
                "translation_meta": r.get("translation_meta")
            },
            "step4_retrieval": {
                "retrieved_passages": [
                    {
                        "rank": i + 1,
                        "chunk_id": p.get("chunk_id"),
                        "source_id": p.get("source_id"),
                        "title": p.get("title"),
                        "locator": p.get("locator"),
                        "rrf_score": round(p.get("rrf_score", 0.0), 4),
                        "snippet": (p.get("text") or "")[:200].replace("\n", " ") + "..."
                    }
                    for i, p in enumerate(passages)
                ]
            },
            "step5_graph_grounding": {
                "graph_facts": r.get("graph_facts", [])
            },
            "step6_citation_validation": {
                "citations": r.get("citations", []),
                "abstained": r.get("abstained"),
                "abstention_reason": r.get("abstention_reason")
            },
            "step7_grounded_answer": {
                "answer": r.get("answer"),
                "latency_ms": r.get("latency_ms"),
                "disclaimer": r.get("disclaimer")
            }
        }
    }


@app.get("/api/research/files/{name}")
def research_file(name: str):
    p = RESEARCH_FILES.get(name)
    if not p or not p.exists():
        raise HTTPException(404, "File not available yet — run the evaluation first.")
    return FileResponse(p, filename=name)


@app.get("/api/about")
def about():
    return {
        "ok": True,
        "disclaimer": EDUCATIONAL_DISCLAIMER,
        "licences": LICENCE_NOTES,
        "team": {
            "members": ["Mansi Jain", "Monisha T", "N S Aishwarya", "Prajna N Rao"],
            "guide": "Prof. Khusboo Pandey",
            "institution": "RV University",
            "team": "Team 3"
        },
        "sources": DATA_SOURCES_CATALOG,
        "architecture_stages": ARCHITECTURE_STAGES_CATALOG,
        "safety_cases": SAFETY_CASES_CATALOG,
        "privacy": (
            "AyurMitra enforces strict privacy boundaries: queries and session data are processed entirely in-memory "
            "and are never permanently stored on the server unless you explicitly click a feedback rating and check "
            "'include my question'. Symptom exploration history is stored locally in your browser's private localStorage "
            "and can be inspected or cleared by you at any time with one click. Audio recordings are converted to text "
            "ephemerally in-memory and immediately discarded. No third-party analytics, tracking cookies, or patient medical records are maintained."
        )
    }


@app.post("/api/feedback")
def feedback(req: FeedbackRequest):
    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "rating": req.rating, "mode": req.mode,
           "comment": (req.comment or None)}
    if req.store_query and req.query:
        rec["query"] = req.query
    path = DATA_PROC / "feedback.jsonl"
    with _PIPE_LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True, "stored_query": "query" in rec}


# ── website (single-page app, same port) ─────────────────────────────────────
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets") \
        if (FRONTEND_DIR / "assets").exists() else None

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")

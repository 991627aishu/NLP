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
from app.config import DATA_EVAL, DATA_PROC, EDUCATIONAL_DISCLAIMER, LICENCE_NOTES, ROOT

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
    STATE["mapper"] = EducationalSymptomMapper()
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
    target_lang: Literal["auto", "en", "hi", "kn"] = "auto"
    web_fallback: bool = False
    generator: Literal["extractive", "llm"] = "extractive"
    speak: bool = False
    voice: Literal["female", "male"] = "female"


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=6000)
    lang: Literal["en", "hi", "kn"] = "en"
    voice: Literal["female", "male"] = "female"
    clean: bool = True
    add_disclaimer: bool = True


class SymptomRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    target_lang: Literal["auto", "en", "hi", "kn"] = "auto"


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
        "raw_query", "system_mode", "detected_language", "target_language", "is_code_mixed", "code_mix_type",
        "segments", "active_components", "translation_meta", "detected_terms", "canonical_query", "retrieval_query",
        "graph_expansion_terms", "graph_facts", "answer", "abstained", "abstention_reason", "is_emergency",
        "citations", "disclaimer", "latency_ms", "backends", "machine_translated", "answer_grounding",
        "generator_used", "generator_note", "evidence_check", "safety")}
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
    pipe = STATE.get("pipeline")
    b = pipe.backend_info() if pipe else {}
    kg = STATE.get("kg")
    tts_order = tts.available_backends()
    return {
        "ok": pipe is not None, "startup_seconds": STATE.get("startup_seconds"),
        "backends": {
            "neural_mt": {"live": b.get("translator") == "indictrans2", "backend": b.get("translator"),
                          "note": b.get("translator_warning")},
            "embeddings": {"live": b.get("dense") == "sentence_transformers", "backend": b.get("dense"),
                           "model": b.get("dense_model"), "note": b.get("dense_warning")},
            "stt": stt.status() | {"live": stt.status()["server_stt"]},
            "tts": {"live": tts_order[0] != "browser", "chain": tts_order},
            "llm": LLMGenerator().available() | {"live": LLMGenerator().available()["available"]},
            "web": {"live": True, "note": "EuropePMC / Wikipedia fallback; off by default, never used in benchmarks"},
            "knowledge_graph": {"live": kg is not None, "version": getattr(kg, "version", None)},
            "safety_gate": {"live": bool(b.get("safety_gate"))},
        },
        "disclaimer": EDUCATIONAL_DISCLAIMER,
    }


@app.post("/api/ask")
def ask(req: AskRequest):
    out = _run_query(req)
    if req.speak or out.get("is_emergency"):
        out["tts"] = _speak(out["answer"], out.get("target_language") or "en", req.voice)
    return out


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
    req = AskRequest(query=stt_res["text"], mode=mode if mode in MODES else "P2",
                     target_lang=target_lang if target_lang in ("auto", "en", "hi", "kn") else "auto",
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
def herbs_search(q: str = Query(..., min_length=1, max_length=200), limit: int = Query(20, ge=1, le=50)):
    return {"ok": True, **_need("herbs").search(q, limit=limit)}


@app.get("/api/lifestyle")
def lifestyle_list():
    return {"ok": True, "topics": _need("herbs").lifestyle_topics(), "disclaimer": EDUCATIONAL_DISCLAIMER}


@app.get("/api/lifestyle/{key}")
def lifestyle_topic(key: str):
    t = _need("herbs").lifestyle_topic(key)
    if not t:
        raise HTTPException(404, "Unknown topic.")
    return {"ok": True, **t}


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


@app.get("/api/research/files/{name}")
def research_file(name: str):
    p = RESEARCH_FILES.get(name)
    if not p or not p.exists():
        raise HTTPException(404, "File not available yet — run the evaluation first.")
    return FileResponse(p, filename=name)


@app.get("/api/about")
def about():
    return {"ok": True, "disclaimer": EDUCATIONAL_DISCLAIMER, "licences": LICENCE_NOTES,
            "team": {"members": ["Mansi Jain", "Monisha T", "N S Aishwarya", "Prajna N Rao"],
                     "guide": "Prof. Khusboo Pandey", "institution": "RV University", "team": "Team 3"},
            "privacy": "Questions are processed in memory and are not stored. Ratings are stored only when you "
                       "press a feedback button; the question text is stored only if you tick 'include my question'."}


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

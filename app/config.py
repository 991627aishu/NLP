"""
AyurMitra — Centralised Configuration
=====================================
Single authoritative source for all paths, model names, and experiment settings.
Do not hard-code paths, model names, or numeric constants anywhere else.
"""
import os
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no dependency). Existing env vars always win."""
    try:
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            # Strip inline comments (e.g. `value # comment`)
            v = v.split("#", 1)[0].strip().strip('"').strip("'")
            os.environ.setdefault(k.strip(), v)
    except Exception:
        pass


def _resolve_child_dir(parent: Path, preferred: str) -> Path:
    """Case-insensitive directory lookup (F8).

    The raw-data folder ships as ``Data/`` but older code referred to ``data/``.
    On case-sensitive filesystems (Linux/macOS/cloud) that mismatch silently
    created a second, empty ``data/`` tree. On Windows, NTFS is case-preserving
    so we inspect iterdir() to return the actual casing existing on disk,
    preferring exact case if both somehow existed, without renaming anything.
    """
    try:
        if parent.is_dir():
            match_any = None
            for child in parent.iterdir():
                if child.is_dir() and child.name.lower() == preferred.lower():
                    if child.name == preferred:
                        return child
                    if match_any is None:
                        match_any = child
            if match_any is not None:
                return match_any
    except OSError:
        pass
    return parent / preferred


# ── Root directories ─────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent.parent
_load_dotenv(ROOT / ".env")
DATA_RAW    = _resolve_child_dir(ROOT, "Data")
DATA_PROC   = DATA_RAW / "processed"
DATA_EVAL   = DATA_RAW / "evaluation"
DOCS_DIR    = ROOT / "docs"
CACHE_DIR   = DATA_PROC / "cache"

# ── Raw data sources (never modified) ────────────────────────────────────────
WHO_PDF         = DATA_RAW / "9789240064935-eng.pdf"
NAMASTE_XLSX    = DATA_RAW / "ayu-sat-table-a.xlsx"
HI_PARQUET      = DATA_RAW / "hi.parquet"
KN_PARQUET      = DATA_RAW / "kn.parquet"
QA_CSV          = DATA_RAW / "qa_cleaned.csv"
PLANT_TSV       = DATA_RAW / "Plant_Information_IMPPAT.tsv"
THERAPEUTIC_TSV = DATA_RAW / "IMPPAT_TherapeuticUse_Plant_Association.tsv"
FORMULATIONS_TSV= DATA_RAW / "IMPPAT_SingleHerbalFormulations.tsv"

# ── Processed / derived outputs ───────────────────────────────────────────────
TERMINOLOGY_JSON    = DATA_PROC / "terminology_inventory.json"
CORPUS_JSONL        = DATA_PROC / "corpus_chunks.jsonl"
BM25_INDEX_PKL      = DATA_PROC / "bm25_index.pkl"
DENSE_INDEX_PKL     = DATA_PROC / "dense_index.pkl"       # numpy dot-product index
EMBEDDINGS_NPY      = DATA_PROC / "embeddings.npy"
CHUNK_META_JSON     = DATA_PROC / "chunk_metadata.json"
KG_PKL              = DATA_PROC / "knowledge_graph.pkl"
EVAL_SEED_JSON      = DATA_EVAL / "eval_seed_questions.json"
EVAL_DEV_JSON       = DATA_EVAL / "eval_dev.json"
EVAL_TEST_JSON      = DATA_EVAL / "eval_test.json"
KG_V1_PKL           = DATA_PROC / "knowledge_graph_v1.pkl"   # frozen copy of the original 24-node graph
KG_V2_PKL           = DATA_PROC / "knowledge_graph_v2.pkl"   # built by app.core.kg_builder
KG_V2_JSON          = DATA_PROC / "kg_v2.json"
INDEX_BACKUP_DIR    = DATA_PROC / "_v1_backup"
TRANSLATION_CACHE   = CACHE_DIR / "translation_cache.sqlite"
TTS_CACHE_DIR       = CACHE_DIR / "tts"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool) -> bool:
    return _env(name, "1" if default else "0").lower() in ("1", "true", "yes", "on")


# ── Feature flags / backend selection (Phase 1+) ─────────────────────────────
# "auto" = use the best backend that is installed and loads, silently fall back,
# and ALWAYS record which backend actually ran in the response trace.
TRANSLATOR_BACKEND = _env("AYUR_TRANSLATOR_BACKEND", "auto")      # auto | indictrans2 | rules
DENSE_BACKEND      = _env("AYUR_DENSE_BACKEND", "auto")           # auto | sentence_transformers | tfidf
GENERATOR_BACKEND  = _env("AYUR_GENERATOR_BACKEND", "extractive") # extractive | llm
LLM_PROVIDER       = _env("AYUR_LLM_PROVIDER", "anthropic")       # anthropic | ollama
LLM_MODEL          = _env("AYUR_LLM_MODEL", "claude-sonnet-5-5")
OLLAMA_URL         = _env("AYUR_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL       = _env("AYUR_OLLAMA_MODEL", "llama3.1:8b")
KG_VERSION         = _env("AYUR_KG_VERSION", "auto")              # auto (v2 if built) | v1 | v2
SAFETY_GATE        = _env_bool("AYUR_SAFETY_GATE", True)          # pre-retrieval emergency/dosage gate
EVIDENCE_GATE      = _env_bool("AYUR_EVIDENCE_GATE", True)        # abstain if passages cover too few query content words
EVIDENCE_MIN_COVERAGE = float(_env("AYUR_EVIDENCE_MIN_COVERAGE", "0.4"))
STT_BACKEND        = _env("AYUR_STT_BACKEND", "auto")             # auto | faster_whisper | none
WHISPER_MODEL_SIZE = _env("AYUR_WHISPER_MODEL", "small")
TTS_BACKEND        = _env("AYUR_TTS_BACKEND", "auto")             # auto | edge_tts | gtts | none

# IndicTrans2 distilled checkpoints (AI4Bharat). Verify on the model cards before
# first use; both need trust_remote_code=True and IndicTransToolkit preprocessing.
INDICTRANS2_INDIC_EN = _env("AYUR_IT2_INDIC_EN", "ai4bharat/indictrans2-indic-en-dist-200M")
INDICTRANS2_EN_INDIC = _env("AYUR_IT2_EN_INDIC", "ai4bharat/indictrans2-en-indic-dist-200M")
IT2_LANG_CODES = {"en": "eng_Latn", "hi": "hin_Deva", "kn": "kan_Knda"}

# ── Language settings ─────────────────────────────────────────────────────────
SUPPORTED_LANGUAGES = ["en", "hi", "kn"]
LANG_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada"}

# ── Dense retrieval model ─────────────────────────────────────────────────────
# paraphrase-multilingual-MiniLM-L12-v2  (~117 MB) — covers en/hi/kn
DENSE_MODEL_NAME = os.environ.get("AYUR_DENSE_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
DENSE_MODEL_DIM  = 384

# ── Retrieval settings ────────────────────────────────────────────────────────
BM25_TOP_K   = 20        # candidates from BM25 before fusion (reconciled with paper §5.5)
DENSE_TOP_K  = 20        # candidates from dense before fusion (reconciled with paper §5.5)
FUSION_TOP_K = 5         # final passages returned to generator
RRF_K        = 60        # reciprocal-rank fusion constant

# ── Chunking settings ─────────────────────────────────────────────────────────
CHUNK_WORDS   = 400      # target words per chunk (initial engineering choice)
CHUNK_OVERLAP = 60       # overlap in words

# ── Answer generation ─────────────────────────────────────────────────────────
# LLM configuration with multi-provider failover
LLM_PROVIDER    = os.environ.get("AYUR_LLM_PROVIDER", "auto")
LLM_MODEL       = os.environ.get("AYUR_LLM_MODEL", "auto")
LLM_MAX_TOKENS  = int(os.environ.get("AYUR_LLM_MAX_TOKENS", "1024"))
LLM_TEMPERATURE = float(os.environ.get("AYUR_LLM_TEMPERATURE", "0.2"))
OLLAMA_URL      = os.environ.get("AYUR_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("AYUR_OLLAMA_MODEL", "llama3.2")
GENERATOR_MODEL = os.environ.get("AYUR_GENERATOR_MODEL", None)

# ── Google Gemini API Configuration ──────────────────────────────────────────
GEMINI_API_KEY                  = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
GEMINI_GENERATION_MODEL         = os.environ.get("GEMINI_GENERATION_MODEL", "gemini-2.5-flash")
GEMINI_EMBEDDING_MODEL          = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
GEMINI_SEARCH_GROUNDING_ENABLED = _env_bool("GEMINI_SEARCH_GROUNDING_ENABLED", True)

# ── Experiment configurations ─────────────────────────────────────────────────
EXPERIMENT_CONFIGS = {
    "B0": {
        "description": "Translation-based query + BM25 only; no terminology preservation",
        "use_terminology": False,
        "use_dense": False,
        "use_graph": False,
    },
    "B1": {
        "description": "Translation-based query + BM25 + dense hybrid; no terminology preservation",
        "use_terminology": False,
        "use_dense": True,
        "use_graph": False,
    },
    "P1": {
        "description": "Terminology-preserved query + BM25 + dense hybrid (proposed system)",
        "use_terminology": True,
        "use_dense": True,
        "use_graph": False,
    },
    "P2": {
        "description": "P1 + knowledge graph (stretch)",
        "use_terminology": True,
        "use_dense": True,
        "use_graph": True,
    },
}

# ── Licensing notes (hard gates — read before redistributing) ─────────────────
LICENCE_NOTES = {
    "WHO_PDF":         "WHO 2022; CC BY-NC-SA 3.0 IGO — non-commercial use permitted",
    "NAMASTE_XLSX":    "NAMASTE/AYUSH — licence to be verified before redistribution",
    "IMPPAT":          "IMPPAT 2.0 — verify current terms at https://cb.imsc.res.in/imppat/",
    "hi_parquet":      "Source/licence to be confirmed from dataset provider",
    "kn_parquet":      "Source/licence to be confirmed from dataset provider",
    "qa_cleaned_csv":  "Source/licence to be confirmed from dataset provider",
}

# ── Safety / disclaimer ───────────────────────────────────────────────────────
EDUCATIONAL_DISCLAIMER = (
    "AyurMitra is an educational tool only. "
    "Information provided is based on traditional Ayurvedic sources and should not "
    "be interpreted as medical diagnosis, treatment, or professional healthcare advice. "
    "Consult a qualified healthcare professional for any health concern."
)


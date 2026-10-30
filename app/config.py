"""
AyurMitra — Centralised Configuration
=====================================
Single authoritative source for all paths, model names, and experiment settings.
Do not hard-code paths, model names, or numeric constants anywhere else.
"""
from pathlib import Path

# ── Root directories ─────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent.parent
DATA_RAW    = ROOT / "Data"
DATA_PROC   = ROOT / "data" / "processed"
DATA_EVAL   = ROOT / "data" / "evaluation"
DOCS_DIR    = ROOT / "docs"

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

# ── Language settings ─────────────────────────────────────────────────────────
SUPPORTED_LANGUAGES = ["en", "hi", "kn"]
LANG_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada"}

# ── Dense retrieval model ─────────────────────────────────────────────────────
# paraphrase-multilingual-MiniLM-L12-v2  (~117 MB) — covers en/hi/kn
DENSE_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
DENSE_MODEL_DIM  = 384

# ── Retrieval settings ────────────────────────────────────────────────────────
BM25_TOP_K   = 10        # candidates from BM25 before fusion
DENSE_TOP_K  = 10        # candidates from dense before fusion
FUSION_TOP_K = 5         # final passages returned to generator
RRF_K        = 60        # reciprocal-rank fusion constant

# ── Chunking settings ─────────────────────────────────────────────────────────
CHUNK_WORDS   = 400      # target words per chunk (initial engineering choice)
CHUNK_OVERLAP = 60       # overlap in words

# ── Answer generation ─────────────────────────────────────────────────────────
# First-pass: rule-based grounding from retrieved passages (no LLM required).
# When an instruction-tuned model becomes available, its name goes here.
GENERATOR_MODEL = None   # None → use extractive/template grounding

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


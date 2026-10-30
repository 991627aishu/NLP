"""
AyurMitra — Evaluation v2 (Phase 8)
===================================
    python -m app.evaluation.evaluator_v2 --split dev      # tune / inspect
    python -m app.evaluation.evaluator_v2 --split test     # run ONCE at the end

Fixes the v1 evaluator's problems (docs/AUDIT.md F17/F18) without touching it:
* Relevance = GOLD PASSAGE IDs derived by code from each seed's ``source`` field
  (NAMASTE code in the chunk text; or the source question text found inside a chunk).
  The v1 "gold concept string appears in a chunk" metric is kept only as
  ``concept_match_recall_at_5`` for comparison.
* Bootstrap CIs resample SEED QUESTIONS (all language variants of a seed move together).
* Paired differences (e.g. P1 − B1) use the same seed resamples.
* Unanswerable seeds are scored only on abstention; they never inflate Recall/MRR.
* Ablations and baselines are run with temporary, evaluator-local patches — the
  pipeline code itself is not modified.
* Web search is always OFF. The generator is always the extractive one.
Outputs (Data/evaluation/): experiment_results_v2[_dev].json, predictions_v2[_dev].csv,
error_analysis_v2[_dev].csv, failure_cases_v2[_dev].json.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import json
import math
import platform
import random
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

import numpy as np

from app.config import CORPUS_JSONL, DATA_EVAL, EVAL_DEV_JSON, EVAL_TEST_JSON, QA_CSV

LANGS = ["english", "hindi", "kannada", "romanized"]
EXPECTED_LANG = {"english": "en", "hindi": "hi", "kannada": "kn", "romanized": "hi"}
N_BOOT = 2000
SEED = 20261030


# ── gold passages ────────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()


def load_chunks() -> List[Dict[str, Any]]:
    with open(CORPUS_JSONL, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


class GoldResolver:
    def __init__(self, chunks):
        self.chunks = chunks
        self.norm_text = {c["chunk_id"]: _norm(c["text"]) for c in chunks}
        self._qa = None

    def _qa_rows(self):
        if self._qa is None:
            import pandas as pd
            try:
                self._qa = pd.read_csv(QA_CSV, nrows=5000)
            except Exception:
                self._qa = False
        return self._qa

    def _find(self, snippet: str, prefixes=None) -> List[str]:
        sn = _norm(snippet)[:80]
        if len(sn) < 12:
            return []
        return [cid for cid, t in self.norm_text.items() if sn in t and (not prefixes or cid.startswith(prefixes))]

    def resolve(self, item: Dict[str, Any]) -> Dict[str, Any]:
        src = item.get("source") or ""
        if item.get("is_unanswerable"):
            return {"gold": [], "method": "unanswerable"}
        m = re.match(r"NAMASTE_(SAT-A[\d.]*)$", src)
        if m:
            code = m.group(1)
            ids = [c["chunk_id"] for c in self.chunks if c["source_id"].startswith("NAMASTE")
                   and re.search(rf"\({re.escape(code)}\)", c["text"])]
            return {"gold": ids, "method": "namaste_code_in_chunk"}
        m = re.match(r"qa_cleaned_row_(\d+)$", src)
        if m:
            qa = self._qa_rows()
            if qa is not False and int(m.group(1)) < len(qa):
                q = str(qa.iloc[int(m.group(1))].get("Question", ""))
                ids = self._find(q, ("QA_PASSAGE",))
                if ids:
                    return {"gold": ids, "method": "qa_question_text_in_chunk"}
        if src.startswith("BhashaBench_Parallel_"):
            ids = self._find(item.get("english", ""), ("HI_QA", "KN_QA"))
            if ids:
                return {"gold": ids, "method": "parallel_question_text_in_chunk"}
        ids = self._find(item.get("english", ""))
        return {"gold": ids, "method": "question_text_in_chunk" if ids else "unresolved"}


# ── variants (main systems, ablations, baselines) ────────────────────────────
@contextlib.contextmanager
def patched(obj, name, value) -> Iterator[None]:
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


def make_variants(pipe) -> Dict[str, Dict[str, Any]]:
    from app.core.matcher import CANONICAL_TO_HINDI, CANONICAL_TO_KANNADA
    orig_find = pipe.matcher.find_terms
    exact_native = set(CANONICAL_TO_HINDI.values()) | set(CANONICAL_TO_KANNADA.values())
    orig_retrieve = pipe.retriever.retrieve

    def no_alias_suffix(text):
        return [t for t in orig_find(text)
                if t["matched_text"].lower() == t["canonical_term"].lower() or t["matched_text"] in exact_native]

    def retrieve_with(**force):
        def f(query, top_k=5, use_bm25=True, use_dense=True, detected_terms=None):
            kw = dict(use_bm25=use_bm25, use_dense=use_dense, detected_terms=detected_terms)
            kw.update(force)
            return orig_retrieve(query, top_k=top_k, **kw)
        return f

    @contextlib.contextmanager
    def nothing():
        yield

    @contextlib.contextmanager
    def ctx(*patches):
        with contextlib.ExitStack() as st:
            for p in patches:
                st.enter_context(patched(*p))
            yield

    @contextlib.contextmanager
    def native():
        # no translation, no terminology: dense retrieval on the raw query
        ident = lambda text, source_lang="auto": {"translated_text": text, "method": "untranslated_native",
                                                  "success": True, "warning": None}
        with ctx((pipe.translator, "translate_to_english", ident),
                 (pipe.retriever, "retrieve", retrieve_with(use_bm25=False, use_dense=True))):
            yield

    return {
        "B0": {"mode": "B0", "kind": "main", "description": "translation + BM25, no term protection", "ctx": nothing},
        "B1": {"mode": "B1", "kind": "main", "description": "translation + BM25/dense RRF, no term protection", "ctx": nothing},
        "P1": {"mode": "P1", "kind": "main", "description": "B1 + term detection, protection, canonicalisation, grounding boost", "ctx": nothing},
        "P2": {"mode": "P2", "kind": "main", "description": "P1 + knowledge-graph expansion and facts", "ctx": nothing},
        "P1-input-protection-off": {"mode": "P1", "kind": "ablation",
            "description": "terms detected (boost kept) but query text NOT replaced by placeholders/canonical terms",
            "ctx": lambda: ctx((pipe.protector, "protect", lambda text: (text, {})))},
        "P1-output-restoration-off": {"mode": "P1", "kind": "ablation",
            "description": "answer-side restore_to_language disabled (a no-op in the extractive path, audit F24)",
            "ctx": lambda: ctx((pipe.protector, "restore_to_language", lambda text, pmap, target_lang="en": text))},
        "P1-alias-suffix-off": {"mode": "P1", "kind": "ablation",
            "description": "only exact canonical / exact native forms detected (no aliases, no Kannada suffix stripping)",
            "ctx": lambda: ctx((pipe.matcher, "find_terms", no_alias_suffix))},
        "P1-grounding-boost-off": {"mode": "P1", "kind": "ablation",
            "description": "term protection kept, but the +0.05/term RRF re-ranking boost removed (isolates protection)",
            "ctx": lambda: ctx((pipe.retriever, "retrieve", retrieve_with(detected_terms=None)))},
        "P1-bm25-only": {"mode": "P1", "kind": "ablation", "description": "P1 with the dense branch off",
            "ctx": lambda: ctx((pipe.retriever, "retrieve", retrieve_with(use_dense=False)))},
        "P1-dense-only": {"mode": "P1", "kind": "ablation", "description": "P1 with the BM25 branch off",
            "ctx": lambda: ctx((pipe.retriever, "retrieve", retrieve_with(use_bm25=False)))},
        "P2-expansion-off": {"mode": "P2", "kind": "ablation", "description": "P2 graph facts kept, query expansion removed",
            "ctx": lambda: ctx((pipe.kg, "expansion_terms", lambda canonical, k=5: []))} if hasattr(pipe.kg, "expansion_terms") else None,
        "native-crosslingual": {"mode": "B1", "kind": "baseline",
            "description": "no translation, no term handling: dense retrieval directly on the untranslated query",
            "ctx": native},
    }


# ── scoring ──────────────────────────────────────────────────────────────────
def score_record(item, lang, res, gold: List[str], gold_method: str) -> Dict[str, Any]:
    retrieved = [p["chunk_id"] for p in res.get("retrieved_passages", [])][:5]
    cited = [c.get("chunk_id") for c in res.get("citations", []) if c.get("chunk_id")]
    gold_set = set(gold)
    rec = {
        "seed_id": item["seed_id"], "category": item.get("category"), "lang": lang, "query": item.get(lang, ""),
        "gold_concept": item.get("gold_concept"), "gold_ids": "|".join(gold), "gold_method": gold_method,
        "is_unanswerable": bool(item.get("is_unanswerable")), "abstained": bool(res.get("abstained")),
        "abstention_reason": res.get("abstention_reason"), "retrieved_ids": "|".join(retrieved), "cited_ids": "|".join(cited),
        "detected_language": res.get("detected_language"), "translation_method": (res.get("translation_meta") or {}).get("method"),
        "canonical_query": res.get("canonical_query"), "detected_terms": "|".join(t.get("canonical_term", "") for t in res.get("detected_terms", [])),
        "latency_ms": round(res.get("latency_ms", 0.0), 2),
    }
    if rec["is_unanswerable"]:
        rec.update(abstention_correct=1.0 if rec["abstained"] else 0.0)
        return rec
    ranks = [i + 1 for i, c in enumerate(retrieved) if c in gold_set]
    gc = (item.get("gold_concept") or "").lower()
    concept_hit = any(gc and (gc in (p.get("text", "") + p.get("title", "")).lower())
                      for p in res.get("retrieved_passages", [])[:5])
    dcg = sum(1 / math.log2(r + 1) for r in ranks)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(gold_set), 5))) or 1.0
    rec.update(
        gold_resolved=1.0 if gold_set else 0.0,
        recall_at_5=1.0 if ranks else 0.0, mrr=1.0 / ranks[0] if ranks else 0.0, ndcg_at_5=dcg / idcg,
        false_abstention=1.0 if rec["abstained"] else 0.0,
        answer_with_gold_evidence=1.0 if (not rec["abstained"] and set(cited) & gold_set) else 0.0,
        citation_gold_precision=(len(set(cited) & gold_set) / len(set(cited))) if cited else 0.0,
        citation_in_retrieved=(len(set(cited) & set(retrieved)) / len(set(cited))) if cited else 1.0,
        concept_match_recall_at_5=1.0 if concept_hit else 0.0,
    )
    return rec


METRICS = ["recall_at_5", "mrr", "ndcg_at_5", "answer_with_gold_evidence", "false_abstention_rate",
           "citation_gold_precision", "citation_in_retrieved", "concept_match_recall_at_5", "abstention_accuracy", "latency_ms"]


def _metric_values(recs, m):
    if m == "abstention_accuracy":
        return [r["abstention_correct"] for r in recs if r["is_unanswerable"]]
    ans = [r for r in recs if not r["is_unanswerable"] and r.get("gold_resolved", 0) == 1.0]
    if m == "false_abstention_rate":
        return [r["false_abstention"] for r in recs if not r["is_unanswerable"]]
    if m == "latency_ms":
        return [r["latency_ms"] for r in recs]
    if m == "concept_match_recall_at_5":
        return [r[m] for r in recs if not r["is_unanswerable"]]
    return [r[m] for r in ans]


def seed_bootstrap(recs_by_seed: Dict[str, List[dict]], metric: str, rng: np.random.Generator,
                   seeds: List[str], boot_idx: np.ndarray) -> Dict[str, Any]:
    point = _metric_values([r for s in seeds for r in recs_by_seed[s]], metric)
    mean = float(np.mean(point)) if point else 0.0
    sums = np.array([sum(_metric_values(recs_by_seed[s], metric)) for s in seeds], dtype=float)
    cnts = np.array([len(_metric_values(recs_by_seed[s], metric)) for s in seeds], dtype=float)
    if cnts.sum() == 0:
        return {"mean": mean, "ci": [mean, mean], "n": 0}
    bs = sums[boot_idx].sum(axis=1) / np.maximum(cnts[boot_idx].sum(axis=1), 1)
    return {"mean": mean, "ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "n": int(cnts.sum())}


def paired(recs_a, recs_b, metric, seeds, boot_idx):
    def per_seed(recs):
        by = defaultdict(list)
        for r in recs:
            by[r["seed_id"]].append(r)
        return by
    a, b = per_seed(recs_a), per_seed(recs_b)
    sa = np.array([sum(_metric_values(a[s], metric)) for s in seeds], float)
    sb = np.array([sum(_metric_values(b[s], metric)) for s in seeds], float)
    n = np.array([len(_metric_values(a[s], metric)) for s in seeds], float)
    if n.sum() == 0:
        return {"diff": 0.0, "ci": [0.0, 0.0]}
    diff = float((sa.sum() - sb.sum()) / n.sum())
    bs = (sa[boot_idx].sum(1) - sb[boot_idx].sum(1)) / np.maximum(n[boot_idx].sum(1), 1)
    return {"diff": diff, "ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}


# ── stage-wise error analysis ────────────────────────────────────────────────
def first_failing_stage(rec, english_rec, matcher) -> str:
    if rec["is_unanswerable"] or rec.get("gold_resolved") != 1.0:
        return "not_applicable"
    if rec.get("abstention_reason") in SAFETY_REASONS:
        return "safety_gate"
    if rec["recall_at_5"] == 1.0:
        if rec["abstained"]:
            return "generation_abstained"
        if rec["answer_with_gold_evidence"] == 0.0:
            return "generation_citation"
        return "success"
    if rec["detected_language"] != EXPECTED_LANG[rec["lang"]]:
        return "language_id"
    gc = rec.get("gold_concept") or ""
    known = bool(gc and matcher.find_terms(gc))
    if known and not rec["detected_terms"]:
        if rec["lang"] == "kannada" and english_rec and english_rec.get("detected_terms"):
            return "suffix_normalization"
        return "term_detection"
    if rec["lang"] != "english" and rec["translation_method"] in ("indic_transliteration_fallback", "passthrough_untranslated",
                                                                  "untranslated_native"):
        return "translation"
    return "retrieval"


SAFETY_REASONS = {"emergency_symptom_detected", "dosage_or_prescription_request", "toxic_substance_request",
                  "unsupported_cure_claim"}
STAGES = ["safety_gate", "language_id", "term_detection", "suffix_normalization", "translation", "retrieval", "graph",
          "generation_abstained", "generation_citation", "restoration", "success"]


def error_analysis(records, matcher, system="P1"):
    recs = [r for r in records if r["system"] == system]
    eng = {r["seed_id"]: r for r in recs if r["lang"] == "english"}
    rows, counts, examples = [], defaultdict(Counter), defaultdict(list)
    for r in recs:
        st = first_failing_stage(r, eng.get(r["seed_id"]), matcher)
        if st == "not_applicable":
            continue
        counts[st][r["lang"]] += 1
        if st != "success" and len(examples[st]) < 3:
            examples[st].append(f"[{r['lang']}] {r['query'][:90]} → {r['translation_method']}: {str(r['canonical_query'])[:70]}")
        rows.append({"seed_id": r["seed_id"], "lang": r["lang"], "stage": st, "query": r["query"],
                     "translation_method": r["translation_method"], "canonical_query": r["canonical_query"],
                     "detected_terms": r["detected_terms"], "gold_ids": r["gold_ids"], "retrieved_ids": r["retrieved_ids"]})
    stages = [{"stage": s, "by_language": dict(counts[s]), "total": sum(counts[s].values()), "examples": examples[s]}
              for s in STAGES]
    stages[STAGES.index("graph")]["note"] = "P1 has no graph stage; see P2 vs P1 paired difference"
    stages[STAGES.index("restoration")]["note"] = ("extractive answers contain no placeholders, so output restoration "
                                                   "cannot fail (audit F24); measured only with neural answer MT")
    return {"system": system, "stages": stages}, rows


# ── main ─────────────────────────────────────────────────────────────────────
def run(split: str = "dev", limit: Optional[int] = None, systems: Optional[List[str]] = None,
        progress: bool = True) -> Dict[str, Any]:
    import logging
    logging.disable(logging.WARNING)
    from app.pipeline.rag_pipeline import AyurMitraPipeline
    items = json.loads(Path(EVAL_DEV_JSON if split == "dev" else EVAL_TEST_JSON).read_text(encoding="utf-8"))
    if limit:
        items = items[:limit]
    pipe = AyurMitraPipeline()
    chunks = load_chunks()
    resolver = GoldResolver(chunks)
    gold = {it["seed_id"]: resolver.resolve(it) for it in items}
    variants = {k: v for k, v in make_variants(pipe).items() if v and (not systems or k in systems)}
    records: List[Dict[str, Any]] = []
    t0 = time.time()
    for vname, v in variants.items():
        with v["ctx"]():
            for i, it in enumerate(items):
                for lang in LANGS:
                    q = it.get(lang) or it.get("english", "")
                    res = pipe.process_query(q, system_mode=v["mode"], top_k=5, enable_web_search=False,
                                             generator="extractive")
                    rec = score_record(it, lang, res, gold[it["seed_id"]]["gold"], gold[it["seed_id"]]["method"])
                    rec["system"] = vname
                    records.append(rec)
        if progress:
            print(f"  {vname:28s} done ({time.time() - t0:.0f}s)", flush=True)

    seeds = [it["seed_id"] for it in items]
    rng = np.random.default_rng(SEED)
    boot_idx = rng.integers(0, len(seeds), size=(N_BOOT, len(seeds)))
    systems_out = {}
    for vname, v in variants.items():
        recs = [r for r in records if r["system"] == vname]
        by_seed = defaultdict(list)
        for r in recs:
            by_seed[r["seed_id"]].append(r)
        metrics = {m: seed_bootstrap(by_seed, m, rng, seeds, boot_idx) for m in METRICS}
        by_lang = {}
        for lang in LANGS:
            lr = [r for r in recs if r["lang"] == lang]
            by_lang[lang] = {m: (float(np.mean(x)) if (x := _metric_values(lr, m)) else None) for m in METRICS}
        systems_out[vname] = {"kind": v["kind"], "description": v["description"], "mode": v["mode"],
                              "n_records": len(recs), "n_seeds": len(seeds), "metrics": metrics, "by_language": by_lang}

    def verdict(p):
        lo, hi = p["recall_at_5"]["ci"]
        return "improves (CI excludes 0)" if lo > 0 else "worse (CI excludes 0)" if hi < 0 else "no clear difference (CI includes 0)"

    pairs = {}
    for a, b in [("P1", "B1"), ("B1", "B0"), ("P2", "P1"), ("P1", "P1-grounding-boost-off"),
                 ("P1", "P1-input-protection-off"), ("P1", "P1-alias-suffix-off"), ("P1", "native-crosslingual")]:
        if a in variants and b in variants:
            ra = [r for r in records if r["system"] == a]
            rb = [r for r in records if r["system"] == b]
            p = {m: paired(ra, rb, m, seeds, boot_idx) for m in ("recall_at_5", "mrr", "ndcg_at_5", "false_abstention_rate")}
            p["verdict"] = verdict(p)
            pairs[f"{a} vs {b}"] = p

    from app.core.matcher import TerminologyMatcher
    ea, ea_rows = error_analysis(records, TerminologyMatcher(), "P1") if "P1" in variants else ({}, [])
    gm = Counter(g["method"] for g in gold.values())
    answerable = sum(1 for it in items if not it.get("is_unanswerable"))
    resolved = sum(1 for it in items if not it.get("is_unanswerable") and gold[it["seed_id"]]["gold"])
    latin_hi = sum(1 for it in items if re.search(r"[A-Za-z]{3,}", it.get("hindi", "")))
    latin_kn = sum(1 for it in items if re.search(r"[A-Za-z]{3,}", it.get("kannada", "")))
    b = pipe.backend_info()
    meta = {
        "split": split, "n_seeds": len(items), "n_answerable_seeds": answerable, "n_gold_resolved_seeds": resolved,
        "gold_methods": dict(gm), "languages": LANGS, "n_bootstrap": N_BOOT, "random_seed": SEED,
        "ci_method": f"percentile bootstrap, {N_BOOT} resamples of seed questions (all language variants together)",
        "backends": {k: b[k] for k in ("translator", "dense", "dense_model", "generator", "kg_version")},
        "web_search": False, "generator": "extractive (fixed across systems)",
        "hindi_variants_with_latin_terms": latin_hi, "kannada_variants_with_latin_terms": latin_kn,
        "python": sys.version.split()[0], "platform": platform.platform(),
        "runtime_seconds": round(time.time() - t0, 1), "date": time.strftime("%Y-%m-%d"),
    }
    p1b1 = pairs.get("P1 vs B1", {}).get("recall_at_5")
    meta["summary"] = (f"P1 − B1 Recall@5 = {p1b1['diff'] * 100:+.1f} pts (95% CI {p1b1['ci'][0] * 100:+.1f} to "
                       f"{p1b1['ci'][1] * 100:+.1f}); measured with translator='{b['translator']}', dense='{b['dense']}'."
                       if p1b1 else "")
    limitations = [
        f"Pilot scale: {len(items)} seed questions on the {split} split; CIs are wide.",
        f"Translation backend in this run: {b['translator']}. IndicTrans2 was NOT available, so Hindi/Kannada queries were "
        "translated by rules/transliteration; results do not test the paper's IndicTrans2 pipeline." if b["translator"] != "indictrans2" else
        "Translation backend: IndicTrans2.",
        f"Dense backend in this run: {b['dense']} ({b['dense_model']})." + (" This is character n-gram TF-IDF, not a neural embedding model."
                                                                          if b["dense"] == "tfidf" else ""),
        f"{latin_hi} Hindi and {latin_kn} Kannada variants contain the Ayurvedic term in Latin script, so they do not exercise "
        "native-script term protection (audit F19).",
        "Many benchmark questions are taken from records that are themselves in the indexed corpus (QA rows, BhashaBench rows), "
        "so English retrieval is close to a lookup (audit F25).",
        "Some 'Hindi'/'Kannada' variants are English text with a short native-script prefix (audit F26); several gold_concept "
        "values are topic labels such as 'General' (audit F27). All 250 seeds are still review_status=pending_review.",
        "No human ratings exist yet; answer quality and citation faithfulness need the two-rater kit in docs/human_eval/.",
    ]
    return {"meta": meta, "systems": systems_out, "paired": pairs, "error_analysis": ea, "limitations": limitations,
            "_records": records, "_ea_rows": ea_rows}


def save(out: Dict[str, Any], split: str) -> Dict[str, Path]:
    suffix = "" if split == "test" else f"_{split}"
    paths = {k: DATA_EVAL / f"{k}{suffix}{ext}" for k, ext in
             (("experiment_results_v2", ".json"), ("predictions_v2", ".csv"), ("error_analysis_v2", ".csv"),
              ("failure_cases_v2", ".json"))}
    records, ea_rows = out.pop("_records"), out.pop("_ea_rows")
    paths["experiment_results_v2"].write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(paths["predictions_v2"], "w", newline="", encoding="utf-8") as f:
        cols = sorted({k for r in records for k in r})
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(records)
    with open(paths["error_analysis_v2"], "w", newline="", encoding="utf-8") as f:
        if ea_rows:
            w = csv.DictWriter(f, fieldnames=list(ea_rows[0]))
            w.writeheader()
            w.writerows(ea_rows)
    fails = [r for r in records if r["system"] in ("P1", "P2") and not r["is_unanswerable"]
             and (r.get("recall_at_5") == 0.0 or r["abstained"])]
    unans_missed = [r for r in records if r["is_unanswerable"] and not r["abstained"]]
    paths["failure_cases_v2"].write_text(json.dumps({"retrieval_or_abstention_failures": fails[:400],
                                                     "unanswerable_not_abstained": unans_missed}, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    return paths


def recompute_error_analysis(split: str = "test") -> None:
    """Re-derive the stage-wise analysis from saved predictions (no re-run of the systems)."""
    from app.core.matcher import TerminologyMatcher
    suffix = "" if split == "test" else f"_{split}"
    res_p, pred_p = DATA_EVAL / f"experiment_results_v2{suffix}.json", DATA_EVAL / f"predictions_v2{suffix}.csv"
    recs = []
    for r in csv.DictReader(open(pred_p, encoding="utf-8")):
        for k in ("is_unanswerable", "abstained"):
            r[k] = r[k] == "True"
        for k in ("recall_at_5", "gold_resolved", "answer_with_gold_evidence"):
            r[k] = float(r[k]) if r.get(k) not in (None, "") else None
        recs.append(r)
    ea, rows = error_analysis(recs, TerminologyMatcher(), "P1")
    res = json.loads(res_p.read_text(encoding="utf-8"))
    res["error_analysis"] = ea
    res_p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(DATA_EVAL / f"error_analysis_v2{suffix}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--systems", nargs="*", default=None)
    a = ap.parse_args()
    out = run(a.split, a.limit, a.systems)
    paths = save(out, a.split)
    print(json.dumps(out["meta"], indent=1, ensure_ascii=False))
    for k, s in out["systems"].items():
        m = s["metrics"]
        print(f"{k:28s} R@5={m['recall_at_5']['mean']:.3f} [{m['recall_at_5']['ci'][0]:.3f},{m['recall_at_5']['ci'][1]:.3f}] "
              f"MRR={m['mrr']['mean']:.3f} falseAbst={m['false_abstention_rate']['mean']:.3f} abstAcc={m['abstention_accuracy']['mean']:.2f}")
    for k, p in out["paired"].items():
        print(f"{k:36s} ΔR@5={p['recall_at_5']['diff'] * 100:+.1f} [{p['recall_at_5']['ci'][0] * 100:+.1f},{p['recall_at_5']['ci'][1] * 100:+.1f}] {p['verdict']}")
    print("saved:", {k: str(v.name) for k, v in paths.items()})


if __name__ == "__main__":
    main()

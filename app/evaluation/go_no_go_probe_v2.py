"""
AyurMitra — Go/No-Go terminology probe, re-run with REAL translator output (Phase 8, audit F12)
==============================================================================================
    python -m app.evaluation.go_no_go_probe_v2                    # backend = config (auto)
    python -m app.evaluation.go_no_go_probe_v2 --backend indictrans2

The v1 probe (go_no_go_probe.py) contains hand-typed "unprotected translations" and is
kept unchanged for the record; its 100 % corruption figure was never measured.
This script reuses only the 8 probe INPUTS and produces outputs with whichever
translator actually runs, then labels them by code:
  preserved            canonical term (or a romanised form of it) appears in the output
  mistranslated        a known literal/biomedical drift word appears (e.g. bile, fire, air, phlegm, metal)
  untranslated         the term is still in Devanagari/Kannada script (translation did not happen)
  needs_human_label    none of the above — a person must judge
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Any, Dict

from app.config import DATA_EVAL
from app.evaluation.go_no_go_probe import PROBE_ITEMS

DRIFT = {"Pitta": ["bile"], "Agni": ["fire"], "Vata": ["air", "wind", "gas"], "Kapha": ["phlegm", "mucus"],
         "Ojas": ["glow", "vigor", "vigour", "luster", "lustre"], "Ama": ["raw", "mucus defect", "undigested"],
         "Prakriti": ["nature"], "Dhatu": ["metal", "mineral", "element"]}
ROMAN = {"Pitta": ["pitta", "pitt"], "Agni": ["agni", "agn"], "Vata": ["vata", "vaata", "vāta"], "Kapha": ["kapha", "kaph"],
         "Ojas": ["ojas", "oja"], "Ama": ["ama", "aama", "āma"], "Prakriti": ["prakriti", "prakruti", "prakṛti", "prakRti"],
         "Dhatu": ["dhatu", "dhaatu", "dhātu"]}


def label(output: str, concept: str) -> str:
    low = (output or "").lower()
    if any(re.search(rf"\b{re.escape(r.lower())}", low) for r in ROMAN.get(concept, [concept.lower()])):
        return "preserved"
    if any(re.search(rf"\b{re.escape(d)}\b", low) for d in DRIFT.get(concept, [])):
        return "mistranslated"
    if re.search(r"[ऀ-ॿಀ-೿]", output or ""):
        return "untranslated"
    return "needs_human_label"


def run(backend: str | None = None) -> Dict[str, Any]:
    import logging
    logging.disable(logging.WARNING)
    from app.core.protection import TerminologyProtector
    from app.pipeline.translator import MultilingualTranslator
    tr = MultilingualTranslator(backend=backend)
    prot = TerminologyProtector()
    items = []
    for p in PROBE_ITEMS:
        q, lang = p["source_query"], p["lang"]
        un = tr.translate_to_english(q, source_lang=lang)
        protected_text, pmap = prot.protect(q)
        pr = tr.translate_to_english(protected_text, source_lang=lang)
        pr_out = prot.restore_canonical(pr["translated_text"], pmap) if pmap else pr["translated_text"]
        items.append({
            "probe_id": p["probe_id"], "concept": p["concept"], "lang": lang, "source_query": q,
            "unprotected_output": un["translated_text"], "unprotected_method": un["method"],
            "unprotected_status": label(un["translated_text"], p["concept"]),
            "protected_output": pr_out, "protected_method": pr["method"], "terms_protected": len(pmap),
            "protected_status": label(pr_out, p["concept"]),
            "v1_hand_typed_unprotected": p["unprotected_translation"],
        })
    bad = lambda s: s in ("mistranslated",)
    n = len(items)
    un_bad = sum(bad(i["unprotected_status"]) for i in items)
    pr_bad = sum(bad(i["protected_status"]) for i in items)
    need_h = sum(i["unprotected_status"] == "needs_human_label" or i["protected_status"] == "needs_human_label" for i in items)
    neural = tr.backend_used == "indictrans2"
    if not neural:
        decision = "NOT TESTED"
        note = ("The translator in this run was the rule-based fallback (no IndicTrans2). It transliterates rather than "
                "translates, so it cannot produce semantic drift such as Pitta→bile; this run therefore does NOT test the "
                "research premise. Re-run with --backend indictrans2 on a machine that can load the model. The v1 "
                "'100% corruption' figure was hand-typed and is not a measurement.")
    else:
        decision = "GO" if un_bad > pr_bad else "NO-GO / inconclusive"
        note = "Outputs produced by IndicTrans2; statuses labelled by code. Items marked needs_human_label must be judged by a person."
    return {"probe_name": "AyurMitra Go/No-Go probe v2 (real translator output)", "translator_backend": tr.backend_used,
            "translator_warning": tr.backend_warning, "n_items": n,
            "unprotected_mistranslated": un_bad, "protected_mistranslated": pr_bad, "needs_human_label": need_h,
            "decision": decision, "note": note, "items": items}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=None, choices=[None, "auto", "indictrans2", "rules"])
    a = ap.parse_args()
    out = run(a.backend)
    (DATA_EVAL / "go_no_go_probe_results_v2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "items"}, indent=1, ensure_ascii=False))
    for i in out["items"]:
        print(f"{i['probe_id']} {i['concept']:9s} UNPROT[{i['unprotected_status']}] {i['unprotected_output'][:50]!r} | "
              f"PROT[{i['protected_status']}] {i['protected_output'][:50]!r}")


if __name__ == "__main__":
    main()

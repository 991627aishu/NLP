"""
Human-evaluation kit (Phase 8, plan §9): build two blank rater sheets from saved predictions.

    python -m app.evaluation.human_eval_kit --n 60          # writes docs/human_eval/rater_A.csv, rater_B.csv
    python -m app.evaluation.kappa docs/human_eval/rater_A.csv docs/human_eval/rater_B.csv

The sheets are deliberately EMPTY. AyurMitra's authors must not fill them in;
two independent raters do, without seeing each other's sheet. Disagreements
are resolved only after both sheets are complete.
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

from app.config import DATA_EVAL, DOCS_DIR

RATING_COLUMNS = ["relevance_0_2", "faithful_to_cited_sources_0_2", "terminology_correct_yes_no_na",
                  "language_quality_0_2", "unsafe_content_yes_no", "should_have_abstained_yes_no", "rater_comment"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--predictions", default=str(DATA_EVAL / "predictions_v2.csv"))
    ap.add_argument("--systems", nargs="*", default=["B1", "P1"])
    a = ap.parse_args()
    from app.pipeline.rag_pipeline import AyurMitraPipeline
    rows = [r for r in csv.DictReader(open(a.predictions, encoding="utf-8")) if r["system"] in a.systems]
    rng = random.Random(20261030)
    by_lang = {}
    for r in rows:
        by_lang.setdefault(r["lang"], []).append(r)
    sample = []
    per = max(1, a.n // max(1, len(by_lang)))
    for lang, rs in sorted(by_lang.items()):
        sample += rng.sample(rs, min(per, len(rs)))
    rng.shuffle(sample)
    pipe = AyurMitraPipeline()  # regenerate the answer text shown to raters (same code, web off)
    out_dir = DOCS_DIR / "human_eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for i, r in enumerate(sample, 1):
        res = pipe.process_query(r["query"], system_mode=r["system"], enable_web_search=False)
        cites = "; ".join(f"{c['chunk_id']} ({c['source_id']} {c['locator']})" for c in res["citations"])
        passages = "\n---\n".join(f"[{p['chunk_id']}] {p['text'][:600]}" for p in res["retrieved_passages"][:3])
        # system name is hidden from raters (blind); kept in the key file
        items.append({"item_id": f"H{i:03d}", "lang": r["lang"], "question": r["query"], "answer": res["answer"],
                      "citations": cites, "top_passages": passages, "_system": r["system"], "_seed_id": r["seed_id"]})
    for rater in ("A", "B"):
        with open(out_dir / f"rater_{rater}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["item_id", "lang", "question", "answer", "citations", "top_passages"] + RATING_COLUMNS)
            w.writeheader()
            for it in items:
                w.writerow({k: it[k] for k in ("item_id", "lang", "question", "answer", "citations", "top_passages")})
    with open(out_dir / "answer_key_DO_NOT_SHARE_WITH_RATERS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "system", "seed_id"])
        for it in items:
            w.writerow([it["item_id"], it["_system"], it["_seed_id"]])
    print(f"wrote {len(items)} blank items for 2 raters to {out_dir}")


if __name__ == "__main__":
    main()

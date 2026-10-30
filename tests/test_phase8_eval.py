"""Phase 8 tests: evaluator v2 mechanics, probe v2 honesty, kappa, report generation."""
import json

import numpy as np
import pytest

from app.evaluation import evaluator_v2 as ev
from app.evaluation.kappa import cohen_kappa


def test_gold_resolution_uses_real_chunks():
    g = ev.GoldResolver(ev.load_chunks())
    items = json.loads(open(ev.EVAL_DEV_JSON, encoding="utf-8").read())
    nam = next(i for i in items if i["source"].startswith("NAMASTE_SAT-A."))
    r = g.resolve(nam)
    assert r["method"] == "namaste_code_in_chunk" and r["gold"]
    code = nam["source"].split("_", 1)[1]
    chunk = next(c for c in g.chunks if c["chunk_id"] == r["gold"][0])
    assert f"({code})" in chunk["text"]
    unans = next(i for i in items if i.get("is_unanswerable"))
    assert g.resolve(unans)["gold"] == []


def test_unanswerable_never_scores_retrieval():
    rec = ev.score_record({"seed_id": "S", "is_unanswerable": True, "english": "x"}, "english",
                          {"abstained": True, "retrieved_passages": [], "citations": []}, [], "unanswerable")
    assert "recall_at_5" not in rec and rec["abstention_correct"] == 1.0


def test_seed_level_bootstrap_moves_variants_together():
    recs = {"a": [{"is_unanswerable": False, "gold_resolved": 1.0, "recall_at_5": 1.0}] * 4,
            "b": [{"is_unanswerable": False, "gold_resolved": 1.0, "recall_at_5": 0.0}] * 4}
    idx = np.array([[0, 0], [1, 1], [0, 1]])
    out = ev.seed_bootstrap(recs, "recall_at_5", None, ["a", "b"], idx)
    assert out["mean"] == 0.5 and out["ci"][0] < 0.05 and out["ci"][1] > 0.95  # whole seeds resampled


def test_small_eval_run_end_to_end():
    out = ev.run("dev", limit=4, systems=["B1", "P1", "P1-input-protection-off"], progress=False)
    assert set(out["systems"]) == {"B1", "P1", "P1-input-protection-off"}
    assert "P1 vs B1" in out["paired"] and out["meta"]["web_search"] is False
    assert all(r["system"] in out["systems"] for r in out["_records"])
    assert out["limitations"]


def test_probe_v2_does_not_claim_go_without_neural_mt():
    from app.evaluation.go_no_go_probe_v2 import run, label
    out = run("rules")
    assert out["translator_backend"] == "rules" and out["decision"] == "NOT TESTED"
    assert all(i["unprotected_output"] != i["v1_hand_typed_unprotected"] for i in out["items"])
    assert label("What are the symptoms of bile?", "Pitta") == "mistranslated"
    assert label("What are the symptoms of Pitta?", "Pitta") == "preserved"


def test_kappa():
    assert cohen_kappa(list("aabb"), list("aabb")) == pytest.approx(1.0)
    assert cohen_kappa(["0", "1", "2", "2"], ["0", "1", "2", "1"], "quadratic") == pytest.approx(0.8, abs=0.05)
    assert cohen_kappa(["yes", "no"], ["no", "yes"]) < 0


def test_report_generated_from_json(tmp_path):
    from app.evaluation import report_v2
    res = ev.run("dev", limit=3, systems=["B1", "P1"], progress=False)
    res.pop("_records"); res.pop("_ea_rows")
    md = report_v2.render(res, probe=None)
    p1 = res["systems"]["P1"]["metrics"]["recall_at_5"]["mean"]
    assert f"{p1 * 100:.1f}%" in md and "generated automatically" in md

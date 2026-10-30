"""
Generate docs/research_findings_v2.md FROM the results JSON (fixes audit F7: the v1
Markdown report contradicted its own JSON). Never edit the Markdown by hand.

    python -m app.evaluation.report_v2            # uses experiment_results_v2.json (+ _dev) and probe v2
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import DATA_EVAL, DOCS_DIR

MAIN = ["B0", "B1", "P1", "P2"]


def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def _ci(m: Dict[str, Any]) -> str:
    return f"{_pct(m['mean'])} [{_pct(m['ci'][0])}, {_pct(m['ci'][1])}]"


def render(res: Dict[str, Any], probe: Optional[Dict[str, Any]] = None, dev: Optional[Dict[str, Any]] = None) -> str:
    m, S = res["meta"], res["systems"]
    L = [f"# AyurMitra — measured results ({m['split']} split)", "",
         f"> This file is generated automatically by `python -m app.evaluation.report_v2` from "
         f"`Data/evaluation/experiment_results_v2{'' if m['split'] == 'test' else '_' + m['split']}.json` "
         f"({m['date']}). Do not edit by hand.", "",
         "## Setup", "",
         f"- Seeds: **{m['n_seeds']}** ({m['n_answerable_seeds']} answerable, gold passages resolved by code for "
         f"{m['n_gold_resolved_seeds']}) × {len(m['languages'])} variants ({', '.join(m['languages'])}).",
         f"- Gold-passage methods: {', '.join(f'{k} ({v})' for k, v in m['gold_methods'].items())}.",
         f"- Backends: translator **{m['backends']['translator']}**, dense **{m['backends']['dense']}** "
         f"(`{m['backends']['dense_model']}`), generator {m['generator']}, graph {m['backends']['kg_version']}; web search off.",
         f"- Confidence intervals: {m['ci_method']} (seed {m['random_seed']}).",
         f"- Runtime {m['runtime_seconds']} s on {m['platform']}, Python {m['python']}.", "",
         "## Main systems", "",
         "| System | Recall@5 [95% CI] | MRR [95% CI] | nDCG@5 | Answer with gold evidence | False abstention | Abstention accuracy (unanswerable) | Mean latency |",
         "|---|---|---|---|---|---|---|---|"]
    for k in MAIN:
        if k in S:
            x = S[k]["metrics"]
            L.append(f"| {k} | {_ci(x['recall_at_5'])} | {x['mrr']['mean']:.3f} [{x['mrr']['ci'][0]:.3f}, {x['mrr']['ci'][1]:.3f}] | "
                     f"{x['ndcg_at_5']['mean']:.3f} | {_pct(x['answer_with_gold_evidence']['mean'])} | "
                     f"{_pct(x['false_abstention_rate']['mean'])} | {_pct(x['abstention_accuracy']['mean'])} "
                     f"(n={x['abstention_accuracy']['n']}) | {x['latency_ms']['mean']:.0f} ms |")
    L += ["", "## Paired differences (same seed resamples)", "", "| Comparison | ΔRecall@5 [95% CI] | ΔMRR [95% CI] | ΔFalse abstention | Verdict |", "|---|---|---|---|---|"]
    for k, p in res.get("paired", {}).items():
        r = p["recall_at_5"]
        L.append(f"| {k} | {r['diff'] * 100:+.1f} pts [{r['ci'][0] * 100:+.1f}, {r['ci'][1] * 100:+.1f}] | "
                 f"{p['mrr']['diff']:+.3f} [{p['mrr']['ci'][0]:+.3f}, {p['mrr']['ci'][1]:+.3f}] | "
                 f"{p['false_abstention_rate']['diff'] * 100:+.1f} pts | {p['verdict']} |")
    L += ["", "## Recall@5 by language", "", "| System | " + " | ".join(m["languages"]) + " |", "|---|" + "---|" * len(m["languages"])]
    for k in MAIN:
        if k in S:
            L.append(f"| {k} | " + " | ".join(_pct(S[k]["by_language"][l]["recall_at_5"]) for l in m["languages"]) + " |")
    L += ["", "## Ablations and baselines", "", "| Configuration | What changes | Recall@5 [95% CI] | MRR | False abstention |", "|---|---|---|---|---|"]
    for k, s in S.items():
        if s["kind"] != "main":
            x = s["metrics"]
            L.append(f"| {k} | {s['description']} | {_ci(x['recall_at_5'])} | {x['mrr']['mean']:.3f} | {_pct(x['false_abstention_rate']['mean'])} |")
    L += ["", "## Comparison with the v1 metric definition", "",
          "The v1 evaluator counted a hit when the gold *concept string* appeared in any retrieved chunk. "
          "With that definition the same runs give:", "", "| System | v1-style concept-match Recall@5 | v2 gold-passage Recall@5 |", "|---|---|---|"]
    for k in MAIN:
        if k in S:
            L.append(f"| {k} | {_pct(S[k]['metrics']['concept_match_recall_at_5']['mean'])} | {_pct(S[k]['metrics']['recall_at_5']['mean'])} |")
    ea = res.get("error_analysis") or {}
    if ea:
        L += ["", f"## Stage-wise error analysis ({ea['system']}, first failing stage per record)", "",
              "| Stage | " + " | ".join(m["languages"]) + " | Total | Example |", "|---|" + "---|" * (len(m["languages"]) + 2)]
        for s in ea["stages"]:
            ex = (s.get("examples") or [s.get("note", "")])[0] if (s.get("examples") or s.get("note")) else ""
            L.append(f"| {s['stage']} | " + " | ".join(str(s["by_language"].get(l, 0)) for l in m["languages"]) +
                     f" | {s['total']} | {str(ex).replace('|', '/')[:120]} |")
    if probe:
        L += ["", "## Go/No-Go terminology probe (v2, real translator output)", "",
              f"Translator: **{probe['translator_backend']}** · decision: **{probe['decision']}**", "", probe["note"], "",
              "| Probe | Query | Unprotected output | Status | Protected output | Status |", "|---|---|---|---|---|---|"]
        for i in probe["items"]:
            L.append(f"| {i['probe_id']} ({i['concept']}) | {i['source_query']} | {i['unprotected_output']} | {i['unprotected_status']} | "
                     f"{i['protected_output']} | {i['protected_status']} |")
    if dev:
        d = dev["systems"]
        L += ["", "## Development split (for reference; used for inspection only — nothing was tuned on test)", "",
              "| System | Recall@5 [95% CI] |", "|---|---|"]
        L += [f"| {k} | {_ci(d[k]['metrics']['recall_at_5'])} |" for k in MAIN if k in d]
    L += ["", "## Limitations", ""] + [f"- {x}" for x in res.get("limitations", [])]
    L += ["", "## Files", "", "- `Data/evaluation/predictions_v2*.csv` — every record: query, retrieved IDs, cited IDs, gold IDs, scores",
          "- `Data/evaluation/error_analysis_v2*.csv` — first failing stage per P1 record",
          "- `Data/evaluation/failure_cases_v2*.json` — retrieval/abstention failures and missed abstentions",
          "- `Data/evaluation/experiment_results.json` — the ORIGINAL v1 results, kept unchanged (see docs/AUDIT.md F7/F17/F18)"]
    return "\n".join(L) + "\n"


def main():
    test = DATA_EVAL / "experiment_results_v2.json"
    devp = DATA_EVAL / "experiment_results_v2_dev.json"
    probe_p = DATA_EVAL / "go_no_go_probe_results_v2.json"
    probe = json.loads(probe_p.read_text(encoding="utf-8")) if probe_p.exists() else None
    if test.exists():
        res = json.loads(test.read_text(encoding="utf-8"))
        dev = json.loads(devp.read_text(encoding="utf-8")) if devp.exists() else None
        out = DOCS_DIR / "research_findings_v2.md"
    else:
        res, dev, out = json.loads(devp.read_text(encoding="utf-8")), None, DOCS_DIR / "research_findings_v2_dev.md"
    out.write_text(render(res, probe, dev), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()

"""
Inter-rater agreement for the human-evaluation kit.

    python -m app.evaluation.kappa docs/human_eval/rater_A.csv docs/human_eval/rater_B.csv

Ordinal 0–2 columns -> quadratic-weighted Cohen's kappa; yes/no/na columns -> unweighted
Cohen's kappa. Only rows rated by BOTH raters are used. Prints n, raw agreement, kappa.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from typing import Dict, List, Sequence

ORDINAL = ["relevance_0_2", "faithful_to_cited_sources_0_2", "language_quality_0_2"]
NOMINAL = ["terminology_correct_yes_no_na", "unsafe_content_yes_no", "should_have_abstained_yes_no"]


def cohen_kappa(a: Sequence[str], b: Sequence[str], weights: str | None = None) -> float:
    if not a:
        return float("nan")
    cats = sorted(set(a) | set(b), key=lambda x: (not x.lstrip("-").isdigit(), int(x) if x.lstrip("-").isdigit() else 0, x))
    idx = {c: i for i, c in enumerate(cats)}
    k, n = len(cats), len(a)
    if k == 1:
        return 1.0
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1
    ra, rb = Counter(a), Counter(b)
    exp = [[ra[cats[i]] * rb[cats[j]] / n for j in range(k)] for i in range(k)]
    w = [[(0.0 if i == j else 1.0) if weights is None else ((i - j) ** 2) / ((k - 1) ** 2) for j in range(k)] for i in range(k)]
    num = sum(w[i][j] * obs[i][j] for i in range(k) for j in range(k))
    den = sum(w[i][j] * exp[i][j] for i in range(k) for j in range(k))
    return 1.0 - num / den if den else 1.0


def load(path: str) -> Dict[str, Dict[str, str]]:
    return {r["item_id"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}


def report(path_a: str, path_b: str) -> List[Dict[str, object]]:
    A, B = load(path_a), load(path_b)
    out = []
    for col in ORDINAL + NOMINAL:
        pairs = [(A[i][col].strip().lower(), B[i][col].strip().lower()) for i in A if i in B
                 and A[i].get(col, "").strip() and B[i].get(col, "").strip()]
        a, b = [p[0] for p in pairs], [p[1] for p in pairs]
        kappa = cohen_kappa(a, b, "quadratic" if col in ORDINAL else None)
        agree = sum(x == y for x, y in pairs) / len(pairs) if pairs else float("nan")
        out.append({"criterion": col, "n": len(pairs), "raw_agreement": agree, "kappa": kappa,
                    "type": "quadratic-weighted" if col in ORDINAL else "unweighted"})
    return out


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python -m app.evaluation.kappa rater_A.csv rater_B.csv")
    for r in report(sys.argv[1], sys.argv[2]):
        print(f"{r['criterion']:34s} n={r['n']:3d} agreement={r['raw_agreement']:.2f} kappa={r['kappa']:.3f} ({r['type']})")
    print("Note: kappa is only meaningful once both raters have independently completed every row.")

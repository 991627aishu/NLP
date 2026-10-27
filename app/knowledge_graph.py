"""Provenance-preserving multi-source knowledge graph. Cross-source links are exact-label only."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any
import networkx as nx

from app.core import find_imppat_use_tables, load_columbia, load_imppat_tables, load_namaste_terms


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


@lru_cache(maxsize=1)
def build_knowledge_graph() -> nx.MultiDiGraph:
    """Build multi-source knowledge graph with in-memory caching."""
    g = nx.MultiDiGraph()

    # NAMASTE term/code/definition nodes: preserve official row and sheet provenance.
    terms = load_namaste_terms()
    if not terms.empty:
        for idx, row in terms.iterrows():
            vals = row.to_dict()
            label = next(
                (
                    str(v).strip()
                    for k, v in vals.items()
                    if any(x in str(k).lower() for x in ("word", "term", "name")) and str(v).strip()
                ),
                "",
            )
            if not label:
                continue
            code = next(
                (
                    str(v).strip()
                    for k, v in vals.items()
                    if "code" in str(k).lower() and str(v).strip()
                ),
                "",
            )
            node = "namaste::" + (code or f"{idx}:{norm(label)}")
            g.add_node(
                node,
                label=label,
                kind="ayurveda_term",
                source="NAMASTE",
                source_sheet=str(vals.get("source_sheet", "")),
                code=code,
            )

    # Columbia condition/symptom edges remain clearly identified as general clinical associations.
    df = load_columbia()
    if not df.empty and {"disease", "symptom"}.issubset(df.columns):
        for idx, row in df.iterrows():
            disease = str(row.get("disease", "")).strip()
            symptom = str(row.get("symptom", "")).strip()
            if not disease or not symptom:
                continue
            d = "condition::" + norm(disease)
            s = "symptom::" + norm(symptom)
            g.add_node(
                d,
                label=disease,
                kind="general_condition",
                source="Columbia Disease–Symptom Knowledge Database",
            )
            g.add_node(
                s,
                label=symptom,
                kind="symptom",
                source="Columbia Disease–Symptom Knowledge Database",
            )
            g.add_edge(
                s,
                d,
                relation="associated_with",
                source="Columbia Disease–Symptom Knowledge Database",
                source_row=int(idx),
            )

    # IMPPAT plant/use associations.
    for row in find_imppat_use_tables(load_imppat_tables()):
        plant = str(row.get("plant", "")).strip()
        use = str(row.get("therapeutic_use", "")).strip()
        if not plant or not use:
            continue
        p = "plant::" + norm(plant)
        u = "use::" + norm(use)
        g.add_node(p, label=plant, kind="medicinal_plant", source="IMPPAT 2.0")
        g.add_node(
            u,
            label=use,
            kind="source_listed_therapeutic_use",
            source="IMPPAT 2.0",
        )
        g.add_edge(
            p,
            u,
            relation="source_lists_use",
            plant_part=str(row.get("plant_part", "")),
            source="IMPPAT 2.0",
            source_file=str(row.get("source_file", "")),
        )

    # Cross-source links are made only for exact normalized labels; no inferred medical mapping.
    by_label: dict[str, list[str]] = {}
    for node, attrs in g.nodes(data=True):
        label = norm(attrs.get("label", ""))
        if label:
            by_label.setdefault(label, []).append(node)
    for label, nodes in by_label.items():
        if len(nodes) > 1:
            for i, left in enumerate(nodes):
                for right in nodes[i + 1 :]:
                    if g.nodes[left].get("source") != g.nodes[right].get("source"):
                        g.add_edge(
                            left,
                            right,
                            relation="exact_label_match_only",
                            source="AyurMitra normalization layer",
                        )
    return g


def graph_summary() -> dict[str, Any]:
    graph = build_knowledge_graph()
    kinds: dict[str, int] = {}
    for _, data in graph.nodes(data=True):
        kinds[data.get("kind", "unknown")] = (
            kinds.get(data.get("kind", "unknown"), 0) + 1
        )
    relations: dict[str, int] = {}
    for _, _, data in graph.edges(data=True):
        relations[data.get("relation", "unknown")] = (
            relations.get(data.get("relation", "unknown"), 0) + 1
        )
    return {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "node_types": kinds,
        "relation_types": relations,
        "note": (
            "Cross-source edges represent exact normalized label matches only. "
            "Columbia associations are general clinical associations; "
            "IMPPAT use edges are source-listed associations, not personalized advice."
        ),
    }


def find_related_graph_entities(query: str, limit: int = 6) -> list[dict[str, Any]]:
    """Retrieve graph neighbors and relations matching query concepts for Explainable AI."""
    graph = build_knowledge_graph()
    q_norm = norm(query)
    if not q_norm:
        return []

    matched_nodes = []
    tokens = set(q_norm.split())

    for node, attrs in graph.nodes(data=True):
        label_norm = norm(attrs.get("label", ""))
        if not label_norm:
            continue
        if q_norm == label_norm or (len(label_norm) > 3 and label_norm in q_norm) or (len(q_norm) > 3 and q_norm in label_norm):
            matched_nodes.append((node, attrs, 2.0))
        elif tokens & set(label_norm.split()):
            overlap = len(tokens & set(label_norm.split()))
            matched_nodes.append((node, attrs, 1.0 * overlap))

    matched_nodes.sort(key=lambda x: x[2], reverse=True)
    results = []

    for node, attrs, score in matched_nodes[:limit]:
        # Collect outgoing and incoming edges
        relations = []
        for _, target, edge_data in graph.out_edges(node, data=True):
            target_attrs = graph.nodes.get(target, {})
            relations.append({
                "direction": "out",
                "relation": edge_data.get("relation", "relates_to"),
                "target_label": target_attrs.get("label", target),
                "target_kind": target_attrs.get("kind", ""),
                "target_source": edge_data.get("source", ""),
                "detail": edge_data.get("plant_part", ""),
            })

        for source, _, edge_data in graph.in_edges(node, data=True):
            source_attrs = graph.nodes.get(source, {})
            relations.append({
                "direction": "in",
                "relation": edge_data.get("relation", "relates_to"),
                "source_label": source_attrs.get("label", source),
                "source_kind": source_attrs.get("kind", ""),
                "source_source": edge_data.get("source", ""),
            })

        results.append({
            "node_id": node,
            "label": attrs.get("label", ""),
            "kind": attrs.get("kind", ""),
            "source": attrs.get("source", ""),
            "relations": relations[:5],
        })

    return results

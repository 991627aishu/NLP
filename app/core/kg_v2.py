"""
AyurMitra — Knowledge Graph v2 query layer
==========================================
Loads ``knowledge_graph_v2.pkl`` (built by ``python -m app.core.kg_builder``) and
offers the queries the pipeline (P2) and the website need. ``query_concept`` keeps
the v1 return shape so existing callers keep working.
"""
from __future__ import annotations

import pickle
import re
import unicodedata
from collections import Counter, deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

from app.config import KG_V2_PKL
from app.core.kg_builder import fold

VERIFIED_STATUSES = {"extracted_from_source"}
UI_NODE_LIMIT = 300
# Types that make good P2 evidence (source text with locators)
_FACT_TARGET_TYPES = {"WHOTerm", "WHOSection", "NAMASTETerm", "Plant", "Dosha", "Concept"}


def _norm_query(q: str) -> str:
    q = unicodedata.normalize("NFC", (q or "").strip())
    return q


class KnowledgeGraphV2:
    version = "v2"

    def __init__(self, path: Path = KG_V2_PKL):
        with open(path, "rb") as f:
            self.graph: nx.DiGraph = pickle.load(f)
        self._ug = None
        self._index: Dict[str, List[str]] = {}
        for n, d in self.graph.nodes(data=True):
            keys = {fold(d.get("label_en") or ""), fold(d.get("label_iast") or ""), fold(d.get("label_roman") or ""),
                    fold(n.split(":", 1)[-1])}
            keys |= {fold(a) for a in d.get("aliases", [])}
            for raw in (d.get("label_hi"), d.get("label_kn"), d.get("label_sa_deva"), d.get("label_kn_script_sanskrit")):
                if raw:
                    keys.add(_norm_query(raw).lower())
            for k in keys:
                if k:
                    self._index.setdefault(k, []).append(n)

    # ── helpers ──────────────────────────────────────────────────────────────
    @property
    def undirected(self) -> nx.Graph:
        if self._ug is None:
            self._ug = self.graph.to_undirected(as_view=True)
        return self._ug

    def node_dict(self, n: str) -> Dict[str, Any]:
        d = dict(self.graph.nodes[n])
        d["id"] = n
        d["degree"] = self.graph.degree(n)
        return d

    def _edge_dict(self, u: str, v: str) -> Dict[str, Any]:
        d = dict(self.graph.edges[u, v])
        d.update(source=u, target=v, verified=d.get("review_status") in VERIFIED_STATUSES)
        return d

    def resolve(self, name: str) -> Optional[str]:
        if not name:
            return None
        if name in self.graph:
            return name
        for cand in (f"CONCEPT:{name}", f"CONCEPT:{name.title()}"):
            if cand in self.graph:
                return cand
        hits = self.search(name, limit=1)
        return hits[0]["id"] if hits else None

    # ── search ───────────────────────────────────────────────────────────────
    def search(self, q: str, limit: int = 20, types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        q = _norm_query(q)
        if not q:
            return []
        fq = fold(q) if q.isascii() or re.search(r"[A-Za-z]", q) else q.lower()
        type_rank = {"Concept": 0, "Dosha": 0, "WHOTerm": 1, "NAMASTETerm": 2, "Plant": 3, "Formulation": 4,
                     "TherapeuticUse": 5, "SymptomPhrase": 6, "WHOSection": 7}
        scored: Dict[str, float] = {}
        for key, nodes in self._index.items():
            if not key:
                continue
            if key == fq:
                s = 0.0
            elif key.startswith(fq):
                s = 1.0 + len(key) / 100
            elif len(fq) >= 3 and fq in key:
                s = 2.0 + len(key) / 100
            else:
                continue
            for n in nodes:
                t = self.graph.nodes[n]["node_type"]
                if types and t not in types:
                    continue
                score = s + type_rank.get(t, 9) / 10 - min(self.graph.degree(n), 200) / 2000
                if n not in scored or score < scored[n]:
                    scored[n] = score
        out = []
        for n in sorted(scored, key=scored.get)[:limit]:
            d = self.graph.nodes[n]
            out.append({"id": n, "node_type": d["node_type"], "label_en": d.get("label_en"),
                        "label_iast": d.get("label_iast"), "label_hi": d.get("label_hi"), "label_kn": d.get("label_kn"),
                        "degree": self.graph.degree(n)})
        return out

    # ── neighbourhood (UI-safe, ≤ 300 nodes) ─────────────────────────────────
    def neighbourhood(self, center: str, depth: int = 1, types: Optional[List[str]] = None,
                      limit: int = 150) -> Dict[str, Any]:
        center = self.resolve(center)
        if not center:
            return {"center": None, "nodes": [], "edges": [], "truncated": False}
        limit = max(1, min(limit, UI_NODE_LIMIT))
        depth = max(1, min(depth, 3))
        seen = {center: 0}
        q = deque([center])
        truncated = False
        while q:
            n = q.popleft()
            if seen[n] >= depth:
                continue
            # prefer verified / informative neighbours first, cap fan-out of hubs
            nbrs = list(self.undirected.neighbors(n))
            nbrs.sort(key=lambda m: (self.graph.nodes[m]["node_type"] == "TherapeuticUse", -self.graph.degree(m)))
            for m in nbrs:
                if types and self.graph.nodes[m]["node_type"] not in types and m != center:
                    continue
                if m in seen:
                    continue
                if len(seen) >= limit:
                    truncated = True
                    break
                seen[m] = seen[n] + 1
                q.append(m)
        nodes = [self.node_dict(n) | {"hop": h} for n, h in seen.items()]
        keep = set(seen)
        edges = [self._edge_dict(u, v) for u, v in self.graph.subgraph(keep).edges()]
        return {"center": center, "nodes": nodes, "edges": edges, "truncated": truncated}

    def node_detail(self, nid: str, max_edges: int = 200) -> Optional[Dict[str, Any]]:
        nid = self.resolve(nid)
        if not nid:
            return None
        out_e = [self._edge_dict(nid, v) | {"other": self._brief(v)} for v in self.graph.successors(nid)]
        in_e = [self._edge_dict(u, nid) | {"other": self._brief(u)} for u in self.graph.predecessors(nid)]
        return {"node": self.node_dict(nid), "outgoing": out_e[:max_edges], "incoming": in_e[:max_edges],
                "n_outgoing": len(out_e), "n_incoming": len(in_e)}

    def _brief(self, n: str) -> Dict[str, Any]:
        d = self.graph.nodes[n]
        return {"id": n, "node_type": d["node_type"], "label_en": d.get("label_en"), "label_iast": d.get("label_iast")}

    def shortest_path(self, a: str, b: str, max_len: int = 6) -> Dict[str, Any]:
        a, b = self.resolve(a), self.resolve(b)
        if not a or not b:
            return {"found": False, "reason": "concept not found", "path": []}
        try:
            # avoid trivial routing through giant hubs by weighting high-degree nodes
            def w(u, v, d):
                return 1 + min(self.graph.degree(v), 500) / 100
            path = nx.shortest_path(self.undirected, a, b, weight=w)
        except nx.NetworkXNoPath:
            return {"found": False, "reason": "no path", "path": []}
        if len(path) - 1 > max_len:
            return {"found": False, "reason": f"path longer than {max_len} hops", "path": []}
        steps = []
        for u, v in zip(path, path[1:]):
            e = self._edge_dict(u, v) if self.graph.has_edge(u, v) else self._edge_dict(v, u)
            steps.append(e)
        return {"found": True, "nodes": [self.node_dict(n) for n in path], "edges": steps}

    def stats(self) -> Dict[str, Any]:
        g = self.graph
        rs = Counter(d["review_status"] for _, _, d in g.edges(data=True))
        return {"version": "v2", "nodes": g.number_of_nodes(), "edges": g.number_of_edges(),
                "node_types": dict(Counter(d["node_type"] for _, d in g.nodes(data=True))),
                "relations": dict(Counter(d["relation"] for _, _, d in g.edges(data=True))),
                "review_status": dict(rs),
                "pct_verified": round(100 * sum(rs[s] for s in VERIFIED_STATUSES) / max(1, g.number_of_edges()), 2),
                "built": g.graph.get("built")}

    # ── v1-compatible API ────────────────────────────────────────────────────
    def query_concept(self, concept_name: str) -> Dict[str, Any]:
        nid = self.resolve(concept_name)
        if not nid:
            return {"found": False, "concept": concept_name, "attributes": {}, "connections": [], "neighbors": []}
        conns = []
        for v in self.graph.successors(nid):
            e = self.graph.edges[nid, v]
            conns.append({"target": self.graph.nodes[v].get("label_en") or v, "target_id": v,
                          "target_type": self.graph.nodes[v]["node_type"], "relation": e["relation"],
                          "source_id": e.get("source_id"), "locator": e.get("locator"),
                          "review_status": e.get("review_status")})
        for u in self.graph.predecessors(nid):
            e = self.graph.edges[u, nid]
            conns.append({"source": self.graph.nodes[u].get("label_en") or u, "source_node_id": u,
                          "source_type": self.graph.nodes[u]["node_type"], "relation": e["relation"],
                          "source_id": e.get("source_id"), "locator": e.get("locator"),
                          "review_status": e.get("review_status")})
        attrs = dict(self.graph.nodes[nid])
        return {"found": True, "concept": nid, "attributes": attrs, "connections": conns, "neighbors": conns}

    # ── P2 support ───────────────────────────────────────────────────────────
    def facts_for_term(self, canonical: str, limit: int = 6) -> List[Dict[str, Any]]:
        """Graph facts with provenance for a detected term (preferring source-extracted / matched edges)."""
        nid = self.resolve(canonical)
        if not nid:
            return []
        facts = []
        order = {"extracted_from_source": 0, "auto_matched_by_code": 1, "grounded_by_code_text": 2,
                 "project_mapping_unreviewed": 3, "unverified": 4}
        cand = [(nid, v, self.graph.edges[nid, v]) for v in self.graph.successors(nid)] + \
               [(u, nid, self.graph.edges[u, nid]) for u in self.graph.predecessors(nid)]
        cand.sort(key=lambda x: order.get(x[2].get("review_status"), 9))
        for u, v, e in cand:
            other = v if u == nid else u
            od = self.graph.nodes[other]
            if od["node_type"] not in _FACT_TARGET_TYPES and od["node_type"] != "SymptomPhrase":
                continue
            other_label = od.get("label_en") or other
            rev_status = e.get("review_status", "unverified")
            is_verified = rev_status in VERIFIED_STATUSES
            rel = str(e.get("relation", ""))
            is_heuristic = (
                od["node_type"] == "SymptomPhrase"
                or rev_status == "project_mapping_unreviewed"
                or "heuristic" in rel.lower()
                or "symptom" in rel.lower()
                or "may_be_associated" in rel.lower()
            )
            verification_status = "verified" if is_verified else ("heuristic" if is_heuristic else "provisional")
            provisional_notice = (
                "Educational heuristic mapping; not an established clinical or classical text fact."
                if is_heuristic or not is_verified else None
            )
            facts.append({
                # subject -> relation -> object, in the edge's true direction
                "concept": canonical if u == nid else other_label, "relation": e["relation"],
                "target": other_label if u == nid else canonical,
                "query_concept": canonical, "target_id": other, "target_type": od["node_type"],
                "target_definition": (od.get("definition") or "")[:300] or None,
                "source_id": e.get("source_id"), "locator": e.get("locator"),
                "review_status": rev_status, "confidence": e.get("confidence"),
                "direction": "out" if u == nid else "in",
                "is_verified": is_verified,
                "is_heuristic": is_heuristic,
                "verification_status": verification_status,
                "provisional_notice": provisional_notice,
            })
            if len(facts) >= limit:
                break
        return facts

    def expansion_terms(self, canonical: str, k: int = 5) -> List[str]:
        """≤k English expansion terms from source-term neighbours (WHO/NAMASTE labels, IAST forms)."""
        nid = self.resolve(canonical)
        if not nid:
            return []
        from app.core.matcher import DISALLOWED_PLAIN_WORDS
        terms: List[str] = []
        for v in self.graph.successors(nid):
            d = self.graph.nodes[v]
            # Exclude WHOSection completely to prevent generic headers ("Cough", "General") polluting queries
            if d["node_type"] not in ("WHOTerm", "NAMASTETerm", "Plant"):
                continue
            candidates = []
            if d["node_type"] == "Plant":
                if d.get("botanical_name"):
                    candidates.append(d["botanical_name"])
            else:
                if d.get("label_iast"):
                    candidates.append(d["label_iast"])
                label_en = (d.get("label_en") or "").split(",")[0].strip()
                if label_en:
                    candidates.append(label_en)

            for cand in candidates:
                cand_clean = cand.strip()
                cand_lower = cand_clean.lower()
                if (
                    cand_clean
                    and cand_lower != canonical.lower()
                    and cand_clean not in terms
                    and len(cand_clean) < 40
                    and cand_lower not in DISALLOWED_PLAIN_WORDS
                    and not any(w in cand_lower for w in ["cough", "fever", "pain", "box", "time", "deep", "bulk", "headache"])
                ):
                    terms.append(cand_clean)
                    break
            if len(terms) >= k:
                break
        return terms[:k]

    def verify_relation(self, a: str, b: str) -> Optional[Dict[str, Any]]:
        a, b = self.resolve(a), self.resolve(b)
        if a and b:
            if self.graph.has_edge(a, b):
                return self._edge_dict(a, b)
            if self.graph.has_edge(b, a):
                return self._edge_dict(b, a)
        return None


_KG2: Optional[KnowledgeGraphV2] = None


def load_kg_v2() -> Optional[KnowledgeGraphV2]:
    global _KG2
    if _KG2 is None and KG_V2_PKL.exists():
        _KG2 = KnowledgeGraphV2()
    return _KG2

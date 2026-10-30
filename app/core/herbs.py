"""
AyurMitra — Herbal, dietary & lifestyle educational module (Phase 4, audit F6)
==============================================================================
Source-backed only:
  * Herbs  — IMPPAT 2.0 plant records (botanical name, family, synonyms, common names),
             IMPPAT therapeutic-use rows (aggregated, with row locators), and
             Ayurvedic Pharmacopoeia of India single-herb formulations (via IMPPAT).
  * Diet / lifestyle — passages retrieved from the local corpus (WHO terminology,
             NAMASTE, curated QA) plus matching WHO terms from the graph.
Never: doses, contraindications, "safe", "effective", "treats", "cures".
Every payload carries the disclaimer and the "traditional records ≠ evidence" note.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import EDUCATIONAL_DISCLAIMER

TRADITIONAL_NOTE = (
    "Recorded traditional uses come from the IMPPAT 2.0 database and The Ayurvedic Pharmacopoeia of India. "
    "A traditional record is not evidence that a plant is effective or safe for anyone. "
    "AyurMitra gives no doses, preparations or contraindications — ask a qualified practitioner."
)

# Project-written topic list (UI labels only; all content is retrieved from sources)
LIFESTYLE_TOPICS: List[Dict[str, Any]] = [
    {"key": "daily_routine", "title_en": "Daily routine (Dinacharya)", "title_hi": "दिनचर्या", "title_kn": "ದಿನಚರ್ಯೆ",
     "query": "dinacharya daily regimen routine", "graph_terms": ["daily regimen", "dinacarya"]},
    {"key": "seasonal_regimen", "title_en": "Seasonal regimen (Ritucharya)", "title_hi": "ऋतुचर्या", "title_kn": "ಋತುಚರ್ಯೆ",
     "query": "ritucharya seasonal regimen season", "graph_terms": ["seasonal regimen", "rtucarya"]},
    {"key": "diet", "title_en": "Diet and food (Ahara)", "title_hi": "आहार", "title_kn": "ಆಹಾರ",
     "query": "ahara diet food wholesome dietetics", "graph_terms": ["diet", "wholesome diet", "ahara"]},
    {"key": "sleep", "title_en": "Sleep (Nidra)", "title_hi": "निद्रा", "title_kn": "ನಿದ್ರೆ",
     "query": "nidra sleep", "graph_terms": ["sleep", "nidra"]},
    {"key": "exercise", "title_en": "Physical exercise (Vyayama)", "title_hi": "व्यायाम", "title_kn": "ವ್ಯಾಯಾಮ",
     "query": "vyayama physical exercise", "graph_terms": ["physical exercise", "vyayama"]},
    {"key": "digestion", "title_en": "Digestion and Agni", "title_hi": "पाचन और अग्नि", "title_kn": "ಜೀರ್ಣಕ್ರಿಯೆ ಮತ್ತು ಅಗ್ನಿ",
     "query": "agni digestion digestive fire", "graph_terms": ["digestive fire", "agni"]},
    {"key": "rasayana", "title_en": "Rejuvenation (Rasayana)", "title_hi": "रसायन", "title_kn": "ರಸಾಯನ",
     "query": "rasayana rejuvenation rejuvenative therapy", "graph_terms": ["rejuvenative therapy", "rasayana"]},
]


class HerbService:
    def __init__(self, kg=None, retriever=None):
        if kg is None:
            from app.core.kg_v2 import load_kg_v2
            kg = load_kg_v2()
        self.kg = kg
        self.retriever = retriever

    def _base(self) -> Dict[str, Any]:
        return {"disclaimer": EDUCATIONAL_DISCLAIMER, "traditional_records_note": TRADITIONAL_NOTE}

    def search(self, q: str, limit: int = 20) -> Dict[str, Any]:
        if not self.kg:
            return self._base() | {"results": [], "error": "Knowledge graph v2 not built"}
        hits = self.kg.search(q, limit=limit * 3, types=["Plant", "Formulation"])
        # map formulations to their plant so the directory lists herbs
        results, seen = [], set()
        for h in hits:
            pid = h["id"]
            if h["node_type"] == "Formulation":
                plants = [v for v in self.kg.graph.successors(pid) if v.startswith("PLANT:")]
                if not plants:
                    continue
                pid = plants[0]
            if pid in seen:
                continue
            seen.add(pid)
            d = self.kg.graph.nodes[pid]
            results.append({"id": pid, "botanical_name": d.get("botanical_name"), "family": d.get("family"),
                            "api_names": d.get("api_names", []), "common_names": d.get("common_names", [])[:4],
                            "label_sa_deva": d.get("label_sa_deva"),
                            "label_kn_script_sanskrit": d.get("label_kn_script_sanskrit"),
                            "n_recorded_uses": sum(1 for v in self.kg.graph.successors(pid) if v.startswith("TU:")),
                            "n_formulations": sum(1 for u in self.kg.graph.predecessors(pid) if u.startswith("FORM:"))})
            if len(results) >= limit:
                break
        return self._base() | {"query": q, "results": results}

    def detail(self, name_or_id: str, max_uses: int = 60) -> Optional[Dict[str, Any]]:
        if not self.kg:
            return None
        nid = name_or_id if name_or_id.startswith("PLANT:") and name_or_id in self.kg.graph else None
        if nid is None:
            res = self.search(name_or_id, limit=1)["results"]
            nid = res[0]["id"] if res else None
        if nid is None:
            return None
        g = self.kg.graph
        d = g.nodes[nid]
        uses = []
        for v in g.successors(nid):
            if v.startswith("TU:"):
                e = g.edges[nid, v]
                uses.append({"use": g.nodes[v].get("label_en"), "use_id": v, "row_count": e.get("row_count", 1),
                             "plant_parts": e.get("plant_parts", []), "source_id": e.get("source_id"),
                             "locator": e.get("locator"), "review_status": e.get("review_status")})
        uses.sort(key=lambda x: (-x["row_count"], x["use"] or ""))
        forms = []
        for u in g.predecessors(nid):
            if u.startswith("FORM:"):
                fd, e = g.nodes[u], g.edges[u, nid]
                f_uses = [g.nodes[t].get("label_en") for t in g.successors(u) if t.startswith("TU:")]
                forms.append({"id": u, "name": fd.get("label_en"), "name_deva": fd.get("label_sa_deva"),
                              "plant_part": e.get("plant_part"),
                              "api_uses_sanskrit": fd.get("api_therapeutic_uses_sanskrit"),
                              "api_uses_standardised": f_uses, "reference": fd.get("reference"),
                              "locator": fd.get("locator"), "source_id": fd.get("source_id")})
        concepts = [{"id": u, "label": g.nodes[u].get("label_en"), "review_status": g.edges[u, nid].get("review_status"),
                     "ambiguity_note": g.edges[u, nid].get("ambiguity_note")}
                    for u in g.predecessors(nid) if u.startswith("CONCEPT:")]
        return self._base() | {
            "id": nid, "botanical_name": d.get("botanical_name"), "family": d.get("family"), "group": d.get("group"),
            "synonyms": d.get("synonyms", []), "common_names": d.get("common_names", []),
            "api_names": d.get("api_names", []), "label_iast": d.get("label_iast"),
            "label_sa_deva": d.get("label_sa_deva"), "label_kn_script_sanskrit": d.get("label_kn_script_sanskrit"),
            "script_label_note": d.get("script_label_note"),
            "systems_of_medicine": d.get("systems_of_medicine", []), "iucn": d.get("iucn"),
            "source_id": d.get("source_id"), "locator": d.get("locator"),
            "recorded_traditional_uses": uses[:max_uses], "n_recorded_uses": len(uses),
            "formulations": forms, "project_concepts": concepts,
        }

    def lifestyle_topics(self) -> List[Dict[str, Any]]:
        return [{k: t[k] for k in ("key", "title_en", "title_hi", "title_kn")} for t in LIFESTYLE_TOPICS]

    def lifestyle_topic(self, key: str, top_k: int = 5) -> Optional[Dict[str, Any]]:
        topic = next((t for t in LIFESTYLE_TOPICS if t["key"] == key), None)
        if topic is None:
            return None
        passages = []
        if self.retriever is not None:
            for p in self.retriever.retrieve(topic["query"], top_k=top_k, use_bm25=True, use_dense=True):
                passages.append({"chunk_id": p.get("chunk_id"), "source_id": p.get("source_id"),
                                 "locator": p.get("locator"), "title": p.get("title"),
                                 "text": (p.get("text") or "")[:700]})
        who = []
        if self.kg:
            seen = set()
            for term in topic["graph_terms"]:
                from app.core.kg_builder import fold
                for h in self.kg.search(term, limit=8, types=["WHOTerm", "WHOSection"]):
                    if h["id"] in seen:
                        continue
                    dd = self.kg.graph.nodes[h["id"]]
                    if fold(term) not in fold(dd.get("label_en") or "") and fold(term) not in fold(dd.get("label_iast") or ""):
                        continue  # require the topic word in the WHO term itself
                    seen.add(h["id"])
                    d = self.kg.graph.nodes[h["id"]]
                    who.append({"id": h["id"], "term": d.get("label_en"), "iast": d.get("label_iast"),
                                "definition": d.get("definition"), "locator": d.get("locator")})
        return self._base() | {"topic": {k: topic[k] for k in ("key", "title_en", "title_hi", "title_kn")},
                               "who_terms": who[:8], "passages": passages,
                               "note": "Topic titles are project-written; all content below is quoted from the sources."}

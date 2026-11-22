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
            return self._base() | {"results": [], "query": q, "error": "Knowledge graph v2 not built"}
        
        q_clean = (q or "").strip()
        if not q_clean:
            return self._base() | {
                "query": "",
                "explanation": "Please enter an herb name, Sanskrit term, or health concern (e.g., Piles, digestion, sleep, joint stiffness).",
                "results": []
            }

        q_lower = q_clean.lower()
        g = self.kg.graph

        # 1. TU Synonyms for health concerns / symptoms -> IMPPAT therapeutic use labels
        TU_SYNONYMS = {
            "pile": ["hemorrhoids", "bleeding hemorrhoids", "hemorrhoids due to vāta", "arsha"],
            "piles": ["hemorrhoids", "bleeding hemorrhoids", "hemorrhoids due to vāta", "arsha"],
            "hemorrhoid": ["hemorrhoids", "bleeding hemorrhoids", "hemorrhoids due to vāta"],
            "hemorrhoids": ["hemorrhoids", "bleeding hemorrhoids", "hemorrhoids due to vāta"],
            "arsha": ["hemorrhoids", "bleeding hemorrhoids"],
            "arshas": ["hemorrhoids", "bleeding hemorrhoids"],
            "bawasir": ["hemorrhoids", "bleeding hemorrhoids"],
            "moolavyadhi": ["hemorrhoids", "bleeding hemorrhoids"],
            "digestion": ["dyspepsia", "digestive system diseases", "lack of digestive power", "vitiated products of incomplete digestion"],
            "digestive discomfort": ["dyspepsia", "abdominal colic due to āma", "lack of digestive power", "digestive system diseases"],
            "indigestion": ["dyspepsia", "lack of digestive power", "vitiated products of incomplete digestion"],
            "ajirna": ["dyspepsia", "lack of digestive power"],
            "ajeerna": ["dyspepsia", "lack of digestive power"],
            "bloat": ["abdominal bloating", "flatulence"],
            "bloating": ["abdominal bloating", "flatulence"],
            "bloating after eating": ["abdominal bloating", "flatulence", "dyspepsia"],
            "gas": ["flatulence", "abdominal bloating"],
            "flatulence": ["flatulence", "abdominal bloating"],
            "sleep": ["sleeplessness/insomnia", "sleep wake disorders", "sleep aids, pharmaceutical"],
            "insomnia": ["sleeplessness/insomnia", "sleep wake disorders"],
            "sleeplessness": ["sleeplessness/insomnia"],
            "difficulty sleeping": ["sleeplessness/insomnia", "sleep wake disorders"],
            "skin": ["skin diseases", "skin diseases, infectious", "leprosy and other diseases of skin"],
            "dry skin": ["skin diseases", "pruritus"],
            "joint": ["arthritis", "rheumatoid arthritis", "osteoarthritis", "joint dislocations"],
            "joint pain": ["arthritis", "rheumatoid arthritis", "osteoarthritis"],
            "joint stiffness": ["arthritis", "rheumatoid arthritis", "osteoarthritis"],
            "hair": ["hair diseases", "hair preparations", "hair dyes"],
            "hair-related concerns": ["hair diseases", "hair preparations"],
            "cough": ["cough", "cough due to vitiated kapha doṣa", "whooping cough"],
            "fever": ["fever", "fever due to kapha and vāta doṣa", "typhoid fever"],
            "headache": ["headache", "headache due to vitiated kapha doṣa"],
            "headaches": ["headache", "headache due to vitiated kapha doṣa"],
            "constipation": ["constipation"],
            "colic": ["colic", "abdominal colic due to āma"],
            "stomach pain": ["abdominal colic due to āma", "colic", "dyspepsia", "gastritis"],
            "acidity": ["dyspepsia", "acid gastritis", "sour belching"]
        }

        # 2. Match TherapeuticUse (TU:) nodes in the Knowledge Graph
        matched_tu_nodes = set()
        for kw, tu_labels in TU_SYNONYMS.items():
            if kw in q_lower or q_lower in kw:
                for target_lbl in tu_labels:
                    for n in g.nodes:
                        if n.startswith("TU:") and target_lbl in g.nodes[n].get("label_en", "").lower():
                            matched_tu_nodes.add(n)

        # Also direct word scan over all TU nodes
        q_words = [w for w in q_lower.replace("?", "").replace(".", "").split() if len(w) >= 4]
        for n in g.nodes:
            if n.startswith("TU:"):
                tu_lbl = g.nodes[n].get("label_en", "").lower()
                for w in q_words:
                    if w in tu_lbl and w not in ("what", "does", "about", "say", "with", "have"):
                        matched_tu_nodes.add(n)

        results = []
        seen = set()

        # 3. Direct Plant and Formulation search
        plant_hits = self.kg.search(q_clean, limit=limit * 3, types=["Plant", "Formulation"])
        for h in plant_hits:
            pid = h["id"]
            if h["node_type"] == "Formulation":
                plants = [v for v in g.successors(pid) if v.startswith("PLANT:")]
                if not plants:
                    continue
                pid = plants[0]
            if pid in seen:
                continue
            seen.add(pid)
            d = g.nodes[pid]
            results.append({
                "id": pid,
                "botanical_name": d.get("botanical_name"),
                "family": d.get("family"),
                "api_names": d.get("api_names", []),
                "common_names": d.get("common_names", [])[:4],
                "label_sa_deva": d.get("label_sa_deva"),
                "label_kn_script_sanskrit": d.get("label_kn_script_sanskrit"),
                "match_reason": f"Direct plant/name match for query '{q_clean}'",
                "match_type": "direct_name",
                "n_recorded_uses": sum(1 for v in g.successors(pid) if v.startswith("TU:")),
                "n_formulations": sum(1 for u in g.predecessors(pid) if u.startswith("FORM:")),
                "source_id": "IMPPAT_2.0 / The Ayurvedic Pharmacopoeia of India",
                "locator": d.get("locator", "Plant_Information_IMPPAT.tsv"),
                "evidence_limitations": "Traditional Ayurvedic record from IMPPAT/API. Does not establish demonstrated clinical efficacy. No dosage prescribed.",
                "safety_note": "Traditional use record only; consult a qualified Ayurvedic practitioner."
            })

        # 4. Add plants linked to matched TherapeuticUse (TU:) nodes
        if matched_tu_nodes:
            for tu_id in matched_tu_nodes:
                tu_label = g.nodes[tu_id].get("label_en")
                plants = [p for p in g.predecessors(tu_id) if p.startswith("PLANT:")]
                for pid in plants:
                    if pid in seen:
                        continue
                    seen.add(pid)
                    d = g.nodes[pid]
                    e = g.edges.get((pid, tu_id), {})
                    parts = e.get("plant_parts", [])
                    part_str = f" ({', '.join(parts)})" if parts else ""
                    results.append({
                        "id": pid,
                        "botanical_name": d.get("botanical_name"),
                        "family": d.get("family"),
                        "api_names": d.get("api_names", []),
                        "common_names": d.get("common_names", [])[:4],
                        "label_sa_deva": d.get("label_sa_deva"),
                        "label_kn_script_sanskrit": d.get("label_kn_script_sanskrit"),
                        "match_reason": f"Recorded therapeutic use for '{tu_label}'{part_str} in IMPPAT 2.0",
                        "match_type": "therapeutic_use",
                        "n_recorded_uses": sum(1 for v in g.successors(pid) if v.startswith("TU:")),
                        "n_formulations": sum(1 for u in g.predecessors(pid) if u.startswith("FORM:")),
                        "source_id": "IMPPAT_2.0 / The Ayurvedic Pharmacopoeia of India",
                        "locator": e.get("locator", "IMPPAT_TherapeuticUse_Plant_Association.tsv"),
                        "evidence_limitations": "Traditional Ayurvedic record from IMPPAT/API. Does not establish demonstrated clinical efficacy. No dosage prescribed.",
                        "safety_note": "Traditional use record only; consult a qualified Ayurvedic practitioner."
                    })
                    if len(results) >= limit * 2:
                        break
                if len(results) >= limit * 2:
                    break

        # 5. Hybrid RAG retrieval over corpus if results still thin or natural language question
        corpus_passages = []
        if self.retriever is not None and (len(results) < 3 or any(w in q_lower for w in ("what", "say", "traditional", "does", "how"))):
            try:
                rag_hits = self.retriever.retrieve(q_clean, top_k=5)
                for hit in rag_hits:
                    chunk_text = hit.get("text", "")
                    corpus_passages.append({
                        "chunk_id": hit.get("chunk_id"),
                        "source_id": hit.get("source_id"),
                        "locator": hit.get("locator"),
                        "title": hit.get("title"),
                        "text": chunk_text[:400]
                    })
                    # Scan for plant botanical names in chunk
                    for pid in list(g.nodes)[:800]:
                        if pid.startswith("PLANT:") and pid not in seen:
                            bname = g.nodes[pid].get("botanical_name", "")
                            if bname and len(bname) > 6 and bname.lower() in chunk_text.lower():
                                seen.add(pid)
                                d = g.nodes[pid]
                                results.append({
                                    "id": pid,
                                    "botanical_name": d.get("botanical_name"),
                                    "family": d.get("family"),
                                    "api_names": d.get("api_names", []),
                                    "common_names": d.get("common_names", [])[:4],
                                    "label_sa_deva": d.get("label_sa_deva"),
                                    "label_kn_script_sanskrit": d.get("label_kn_script_sanskrit"),
                                    "match_reason": f"Retrieved in classical Ayurvedic corpus passage ({hit.get('chunk_id')})",
                                    "match_type": "rag_corpus",
                                    "n_recorded_uses": sum(1 for v in g.successors(pid) if v.startswith("TU:")),
                                    "n_formulations": sum(1 for u in g.predecessors(pid) if u.startswith("FORM:")),
                                    "source_id": hit.get("source_id", "Classical Corpus"),
                                    "locator": hit.get("locator", ""),
                                    "evidence_limitations": "Traditional literature record. Does not establish demonstrated clinical efficacy.",
                                    "safety_note": "Traditional use record only; consult a qualified Ayurvedic practitioner."
                                })
            except Exception:
                pass

        # 6. Rank: Prioritize direct plant matches, then classical API plants (with api_names), then others
        results.sort(key=lambda r: (
            0 if r.get("match_type") == "direct_name" else (1 if r.get("api_names") else 2),
            -(r.get("n_recorded_uses") or 0)
        ))

        trimmed_results = results[:limit]

        # 7. Formulate grounded educational explanation
        if trimmed_results:
            explanation = (
                f"Based on IMPPAT 2.0 and classical literature, traditional sources record the following herbs in association with '{q_clean}'. "
                f"These records reflect historical usage and do not constitute clinical efficacy or prescriptive advice."
            )
        else:
            explanation = (
                f"No verified Ayurvedic plant or formulation records directly match '{q_clean}'. "
                f"Try searching by symptom (e.g., piles, digestion, joint stiffness), Sanskrit name (e.g., Haritaki, Surana, Ashwagandha), or botanical name."
            )

        return self._base() | {
            "query": q_clean,
            "results": trimmed_results,
            "total_matches": len(results),
            "explanation": explanation,
            "corpus_passages": corpus_passages[:3]
        }

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

    def search_lifestyle(self, q: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Query-driven RAG retrieval for natural-language Ayurvedic lifestyle inquiries.
        Accepts questions regarding sleep, diet, Dinacharya, Ritucharya, Agni, daily routines, etc.
        """
        q_clean = (q or "").strip()
        if not q_clean:
            return self._base() | {
                "query": "",
                "explanation": "Please enter a lifestyle or daily living question (e.g., 'What does Ayurveda say about sleep?', 'What is Dinacharya?').",
                "passages": [],
                "who_terms": []
            }

        if self.retriever is None:
            try:
                from app.pipeline.hybrid_retriever import HybridRetriever
                self.retriever = HybridRetriever()
            except Exception:
                self.retriever = None

        passages = []
        if self.retriever is not None:
            raw_hits = self.retriever.retrieve(q_clean, top_k=top_k, use_bm25=True, use_dense=True)
            for p in raw_hits:
                passages.append({
                    "chunk_id": p.get("chunk_id"),
                    "source_id": p.get("source_id"),
                    "locator": p.get("locator"),
                    "title": p.get("title"),
                    "text": (p.get("text") or "")[:700],
                    "match_reason": f"Corpus passage retrieved for query '{q_clean}' via hybrid RRF search",
                    "limitations": "Traditional textual excerpt from verified Ayurvedic literature (WHO Benchmarks / NAMASTE / Classical QA).",
                    "caution": "Traditional lifestyle guidance serves preventive wellness; individual implementation depends on personal Prakriti and digestive Agni."
                })

        # Match relevant WHO standard terminology
        who_terms = []
        if self.kg:
            seen_terms = set()
            from app.core.kg_builder import fold
            lifestyle_kw = [w for w in q_clean.lower().replace("?", "").replace(".", "").split() if len(w) >= 3]
            
            # Map common user terms to WHO IAST and English terms
            TERM_MAP = {
                "dinacharya": ["Daily routine", "dinacaryā", "dinacarya"],
                "ritucharya": ["Seasonal regimen", "ṛtucaryā", "rtucarya"],
                "sleep": ["Sleep", "nidrā", "nidra"],
                "nidra": ["Sleep", "nidrā"],
                "diet": ["Food", "āhāraḥ", "ahara"],
                "food": ["Food", "āhāraḥ"],
                "ahara": ["Food", "āhāraḥ"],
                "agni": ["Digestive power", "agniḥ", "digestive fire"],
                "digestion": ["Digestive power", "agniḥ", "dyspepsia"]
            }

            expanded_search_terms = list(lifestyle_kw)
            for kw, targets in TERM_MAP.items():
                if kw in q_clean.lower():
                    expanded_search_terms.extend(targets)

            for term in expanded_search_terms:
                for h in self.kg.search(term, limit=6, types=["WHOTerm", "WHOSection"]):
                    if h["id"] in seen_terms:
                        continue
                    dd = self.kg.graph.nodes[h["id"]]
                    label_e = dd.get("label_en") or ""
                    label_i = dd.get("label_iast") or ""
                    if fold(term) in fold(label_e) or fold(term) in fold(label_i) or any(t.lower() in label_e.lower() or t.lower() in label_i.lower() for t in expanded_search_terms):
                        seen_terms.add(h["id"])
                        who_terms.append({
                            "id": h["id"],
                            "term": dd.get("label_en"),
                            "iast": dd.get("label_iast"),
                            "definition": dd.get("definition"),
                            "locator": dd.get("locator")
                        })
                    if len(who_terms) >= 8:
                        break
                if len(who_terms) >= 8:
                    break

        explanation = (
            f"Based on classical Ayurvedic literature (WHO Benchmarks and NAMASTE), the following traditional principles and "
            f"lifestyle guidelines correspond to '{q_clean}'."
        ) if passages else (
            f"No specific classical lifestyle passages could be retrieved for '{q_clean}'. "
            f"Try asking about daily routines (Dinacharya), seasonal routines (Ritucharya), sleep (Nidra), diet (Ahara), or digestive fire (Agni)."
        )

        return self._base() | {
            "query": q_clean,
            "explanation": explanation,
            "passages": passages,
            "who_terms": who_terms[:8],
            "evidence_limitations": "Traditional Ayurvedic health preservation guidance (Svasthavritta); not prescriptive medical advice.",
            "cautions": "Practices should be personalized to your individual constitution (Prakriti) under qualified Ayurvedic guidance."
        }

    def recommend_for_symptom_context(self, symptom_text: str = "", dosha: Optional[str] = None, top_k: int = 6) -> Dict[str, Any]:
        """
        Retrieves classical herbs and lifestyle practices historically associated with a given
        symptom context and/or Ayurvedic dosha (Vata, Pitta, Kapha).
        All returned information is grounded in IMPPAT 2.0, API formulations, and WHO/NAMASTE passages.
        """
        if self.retriever is None:
            try:
                from app.pipeline.hybrid_retriever import HybridRetriever
                self.retriever = HybridRetriever()
            except Exception:
                self.retriever = None

        norm_dosha = (dosha or "").capitalize().strip()
        if norm_dosha not in ("Vata", "Pitta", "Kapha"):
            st_lower = (symptom_text or "").lower()
            if any(w in st_lower for w in ("pitta", "burn", "acid", "heat", "thirst", "fever", "uri")):
                norm_dosha = "Pitta"
            elif any(w in st_lower for w in ("kapha", "heavy", "letharg", "mucus", "sluggish", "cold", "congestion", "bhara", "susthu")):
                norm_dosha = "Kapha"
            else:
                norm_dosha = "Vata"

        DOSHA_KEY_PLANTS = {
            "Vata": [
                {"name": "Ashwagandha", "botanical": "Withania somnifera", "sanskrit": "अश्वगन्धा / ಅಶ್ವಗಂಧ", "rationale": "Traditionally pacifies Vata humor and nourishes bodily tissues (Dhatus)."},
                {"name": "Bala", "botanical": "Sida cordifolia", "sanskrit": "बला / ಬಲಾ", "rationale": "Classical Brihmana and Vata-hara rasayana for vitality."},
                {"name": "Haritaki", "botanical": "Terminalia chebula", "sanskrit": "हरीतकी / ಹರೀತಕಿ", "rationale": "Anulomana herb governing Apana Vata and gut peristalsis."},
                {"name": "Shunthi", "botanical": "Zingiber officinale", "sanskrit": "शुण्ठी / ಶುಂಠಿ", "rationale": "Deepana and Pachana herb stimulating digestive Agni and easing cramps."},
                {"name": "Eranda", "botanical": "Ricinus communis", "sanskrit": "एरण्ड / ಏರಂಡ", "rationale": "Premier classical plant recorded for pacifying severe Vata."},
                {"name": "Rasna", "botanical": "Pluchea lanceolata", "sanskrit": "रास्ना / ರಾಸ್ನಾ", "rationale": "Traditionally recorded for joint comfort and Vata alleviation."}
            ],
            "Pitta": [
                {"name": "Amalaki", "botanical": "Phyllanthus emblica", "sanskrit": "आमलकी / ಆಮಲಕಿ", "rationale": "Sheeta virya rasayana and premier pacifier of Pitta dosha."},
                {"name": "Shatavari", "botanical": "Asparagus racemosus", "sanskrit": "शतावरी / ಶತಾವರಿ", "rationale": "Nourishing Pitta-shamaka with cooling Madhura and Tikta rasa."},
                {"name": "Guduchi", "botanical": "Tinospora cordifolia", "sanskrit": "गुडूची / ಗುಡೂಚಿ", "rationale": "Classical Tridosha-hara with marked Pitta and Agni affinity."},
                {"name": "Chandana", "botanical": "Santalum album", "sanskrit": "चन्दन / ಚಂದನ", "rationale": "Premier cooling herb recorded for Daha and metabolic heat alleviation."},
                {"name": "Brahmi", "botanical": "Bacopa monnieri", "sanskrit": "ब्राह्मी / ಬ್ರಾಹ್ಮೀ", "rationale": "Medhya rasayana cooling the mind and calming Sadhaka Pitta."},
                {"name": "Sariva", "botanical": "Hemidesmus indicus", "sanskrit": "सारिवा / ಸಾರಿವಾ", "rationale": "Raktashodhaka and Pitta-shamaka cooling botanical."}
            ],
            "Kapha": [
                {"name": "Tulsi", "botanical": "Ocimum tenuiflorum", "sanskrit": "तुलसी / ತುಳಸಿ", "rationale": "Ushna and Tikshna botanical relieving respiratory and Kapha congestion."},
                {"name": "Pippali", "botanical": "Piper longum", "sanskrit": "पिप्पली / ಪಿಪ್ಪಲಿ", "rationale": "Kaphahara rasayana stimulating Agni without aggravating Pitta."},
                {"name": "Maricha", "botanical": "Piper nigrum", "sanskrit": "मरीच / ಮರೀಚ", "rationale": "Pramathi herb piercing Kapha and clearing bodily channels (Srotas)."},
                {"name": "Bibhitaki", "botanical": "Terminalia bellirica", "sanskrit": "बिभीतक / ಬಿಭೀತಕಿ", "rationale": "Classical constituent of Triphala targeting Kapha disorders."},
                {"name": "Punarnava", "botanical": "Boerhavia diffusa", "sanskrit": "पुनर्नवा / ಪುನರ್ನವಾ", "rationale": "Shothahara and Mutrala herb clearing fluid accumulation."},
                {"name": "Guggulu", "botanical": "Commiphora mukul", "sanskrit": "गुग्गुलु / ಗುಗ್ಗುಲು", "rationale": "Scraping (Lekhana) resin clearing Medas and accumulated Kapha."}
            ]
        }

        plant_recommendations = []
        target_plants = DOSHA_KEY_PLANTS.get(norm_dosha, DOSHA_KEY_PLANTS["Vata"])

        for plant_spec in target_plants[:top_k]:
            rec_entry = {
                "name": plant_spec["name"],
                "botanical_name": plant_spec["botanical"],
                "sanskrit_label": plant_spec["sanskrit"],
                "dosha_rationale": plant_spec["rationale"],
                "associated_dosha": norm_dosha,
                "graph_id": None,
                "n_recorded_uses": 0,
                "common_names": [],
                "api_names": [],
                "sample_uses": []
            }
            if self.kg:
                hits = self.kg.search(plant_spec["name"], limit=3, types=["Plant"])
                if hits:
                    pid = hits[0]["id"]
                    node = self.kg.graph.nodes[pid]
                    rec_entry["graph_id"] = pid
                    rec_entry["botanical_name"] = node.get("botanical_name") or plant_spec["botanical"]
                    rec_entry["family"] = node.get("family")
                    rec_entry["common_names"] = (node.get("common_names") or [])[:3]
                    rec_entry["api_names"] = (node.get("api_names") or [])[:2]
                    rec_entry["label_sa_deva"] = node.get("label_sa_deva")
                    rec_entry["label_kn"] = node.get("label_kn_script_sanskrit")

                    uses = []
                    for v in self.kg.graph.successors(pid):
                        if v.startswith("TU:"):
                            u_label = self.kg.graph.nodes[v].get("label_en")
                            if u_label:
                                uses.append(u_label)
                    rec_entry["n_recorded_uses"] = len(uses)
                    rec_entry["sample_uses"] = uses[:4]

            plant_recommendations.append(rec_entry)

        lifestyle_keys = {
            "Vata": ["daily_routine", "sleep", "digestion"],
            "Pitta": ["diet", "seasonal_regimen", "digestion"],
            "Kapha": ["exercise", "digestion", "daily_routine"]
        }.get(norm_dosha, ["daily_routine", "diet", "digestion"])

        lifestyle_data = []
        for lk in lifestyle_keys:
            top_info = self.lifestyle_topic(lk, top_k=2)
            if top_info and "topic" in top_info:
                lifestyle_data.append({
                    "key": lk,
                    "title": top_info["topic"].get("title_en"),
                    "title_hi": top_info["topic"].get("title_hi"),
                    "title_kn": top_info["topic"].get("title_kn"),
                    "passages": top_info.get("passages", [])[:2],
                    "who_terms": top_info.get("who_terms", [])[:3]
                })

        return self._base() | {
            "symptom_context": symptom_text,
            "dosha": norm_dosha,
            "recommended_herbs": plant_recommendations,
            "lifestyle_guidelines": lifestyle_data,
            "classical_principle": f"In classical Ayurveda, {norm_dosha} tendencies are managed through opposite dietary qualities (Gunas), specific herbal rasayanas, and aligned diurnal rhythms (Dinacharya)."
        }

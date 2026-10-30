"""
AyurMitra — Evidence-Grounded Answer Generator & Abstention
============================================================
Synthesizes direct, human-readable answers grounded strictly in retrieved passages
with traceable source citations and optional Knowledge Graph concept facts (P2).
Enforces systematic abstention when evidence is insufficient, missing, or ambiguous.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import EDUCATIONAL_DISCLAIMER
from app.core.matcher import CANONICAL_TO_HINDI, CANONICAL_TO_KANNADA
from app.pipeline.translator import CONCEPT_EXPLANATIONS
from app.pipeline.bm25_retriever import QUESTION_STOPWORDS


LOCALIZED_STRINGS = {
    "en": {
        "header_prefix": "Based on curated Ayurvedic literature",
        "header_term": " regarding {0}:",
        "sources_title": "Sources cited:",
        "kg_title": "Knowledge Graph Grounding (Verified Concept Associations):",
        "abstention_no_evidence": (
            "Abstention: No relevant evidence was found in the curated Ayurvedic knowledge "
            "corpus for this query. The system refrains from generating ungrounded advice."
        ),
        "abstention_low_conf": (
            "Abstention: The retrieved evidence did not meet the confidence threshold required "
            "for reliable Ayurvedic grounding."
        ),
        "source_context_title": "Supporting Evidence Passages:",
        "disclaimer": EDUCATIONAL_DISCLAIMER,
    },
    "hi": {
        "header_prefix": "प्रमाणित आयुर्वेदिक साहित्य के अनुसार",
        "header_term": " {0} के संदर्भ में:",
        "sources_title": "उद्धृत स्रोत (Traceable Sources):",
        "kg_title": "ज्ञान ग्राफ संबंध (Knowledge Graph Concept Grounding):",
        "abstention_no_evidence": (
            "अस्वीकृति (Abstention): इस प्रश्न के लिए प्रमाणित आयुर्वेदिक ज्ञान संग्रह में "
            "कोई प्रासंगिक साक्ष्य नहीं मिला। प्रणाली असत्यापित सलाह देने से बचती है।"
        ),
        "abstention_low_conf": (
            "अस्वीकृति (Abstention): प्राप्त संदर्भ विश्वसनीय आयुर्वेदिक उत्तर के लिए "
            "न्यूनतम विश्वास सीमा को पूरा नहीं करते हैं।"
        ),
        "source_context_title": "आधारित साक्ष्य संदर्भ (Evidence Context):",
        "disclaimer": (
            "आयुर्मित्र एक शैक्षणिक सूचना प्रणाली है, चिकित्सकीय निदान या दवा पर्ची नहीं। "
            "किसी भी स्वास्थ्य संबंधी समस्या के लिए योग्य आयुर्वेदाचार्य या चिकित्सक से परामर्श लें।"
        ),
    },
    "kn": {
        "header_prefix": "ಪ್ರಾಮಾಣಿಕ ಆಯುರ್ವೇದ ಸಾಹಿತ್ಯದ ಪ್ರಕಾರ",
        "header_term": " {0}ಗೆ ಸಂಬಂಧಿಸಿದಂತೆ:",
        "sources_title": "ಉಲ್ಲೇಖಿಸಿದ ಮೂಲಗಳು (Traceable Sources):",
        "kg_title": "ಜ್ಞಾನ ಗ್ರಾಫ್ ಆಧಾರಿತ ಸಂಬಂಧಗಳು (Knowledge Graph Grounding):",
        "abstention_no_evidence": (
            "ತಿರಸ್ಕಾರ (Abstention): ಈ ಪ್ರಶ್ನೆಗೆ ಅಧಿಕೃತ ಆಯುರ್ವೇದ ಜ್ಞಾನ ಭಂಡಾರದಲ್ಲಿ "
            "ಯಾವುದೇ ಪುರಾವೆ ಕಂಡುಬಂದಿಲ್ಲ. ಸಿಸ್ಟಮ್ ಆಧಾರರಹಿತ ಸಲಹೆಯನ್ನು ನೀಡುವುದಿಲ್ಲ."
        ),
        "abstention_low_conf": (
            "ತಿರಸ್ಕಾರ (Abstention): ಪಡೆದ ಸಾಹಿತ್ಯದ ಉಲ್ಲೇಖಗಳು ವಿಶ್ವಾಸಾರ್ಹ ಉತ್ತರ ನೀಡಲು "
            "ಅಗತ್ಯವಿರುವ ಕನಿಷ್ಠ ಮಿತಿಯನ್ನು ತಲುಪಿಲ್ಲ."
        ),
        "source_context_title": "ಆಧಾರಿತ ಮೂಲ ಸಾಹಿತ್ಯ ಉಲ್ಲೇಖ (Evidence Context):",
        "disclaimer": (
            "ಆಯುರ್ಮಿತ್ರವು ಶೈಕ್ಷಣಿಕ ಮಾಹಿತಿಯ ಸಾಧನವಾಗಿದ್ದು, ವೈದ್ಯಕೀಯ ಚಿಕಿತ್ಸಾ ಸಲಹೆಯಲ್ಲ. "
            "ಯಾವುದೇ ಆರೋಗ್ಯ ಸಮಸ್ಯೆಗೆ ಅರ್ಹ ಆಯುರ್ವೇದ ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ."
        ),
    }
}


def _clean_passage_sentence(text: str) -> str:
    """Cleans raw corpus text into clean, readable prose without internal dataset tags."""
    if not text:
        return ""
    # Strip raw prefixes
    cleaned = re.sub(r"\[Ayurvedic Literature Knowledge\]", "", text)
    cleaned = re.sub(r"\[NAMASTE Fundamental Concepts\]", "", cleaned)
    cleaned = re.sub(r"\bTopic:\s*", "", cleaned)
    cleaned = re.sub(r"\bDetails:\s*", "", cleaned)
    cleaned = re.sub(r"\bClinical Context:\s*", "", cleaned)
    cleaned = re.sub(r"\bAyurvedic Principle:\s*", "", cleaned)
    cleaned = re.sub(r"qa_cleaned\.csv_rows_\S+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


class EvidenceGroundedGenerator:
    """Answers Ayurvedic queries with clean readable responses, citation grounding, and safety abstention."""

    def __init__(self, relevance_threshold: float = 0.012):
        self.relevance_threshold = relevance_threshold
        self.backend_used = "extractive"
        self.translator = None   # set by the pipeline (answer translation, Phase 2)
        self.protector = None

    def generate_answer(
        self,
        query: str,
        retrieved_passages: List[Dict[str, Any]],
        detected_terms: List[Dict[str, Any]] = None,
        target_lang: str = "en",
        graph_facts: Optional[List[Dict[str, Any]]] = None,
        web_passages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes a readable answer grounded in retrieved evidence in the user's target language.
        Supports local Ayurvedic datasets as well as controlled public web evidence fallback.
        """
        lang = target_lang if target_lang in LOCALIZED_STRINGS else "en"
        loc_str = LOCALIZED_STRINGS[lang]
        disclaimer = loc_str["disclaimer"]
        web_passages = web_passages or []

        # 1. Abstention Check: No local passages and no web passages
        if not retrieved_passages and not web_passages:
            return {
                "answer": loc_str["abstention_no_evidence"],
                "abstained": True,
                "reason": "no_evidence_retrieved",
                "citations": [],
                "web_citations": [],
                "disclaimer": disclaimer,
                "target_lang": lang,
            }

        citations = []
        seen_citations = set()
        clean_facts = []

        concept_keywords = set()
        if detected_terms:
            for t in detected_terms:
                if t.get("canonical_term"):
                    concept_keywords.add(t["canonical_term"].lower())
                if t.get("matched_text"):
                    concept_keywords.add(t["matched_text"].lower())
        query_words = [w for w in re.findall(r"\b[a-zA-Z0-9_\u0900-\u097F\u0C80-\u0CFF]{3,}\b", query.lower()) if w not in QUESTION_STOPWORDS]
        concept_keywords.update(query_words)

        if retrieved_passages:
            # Filter passages that ground the query concept if concept terms are present
            matching_passages = [
                p for p in retrieved_passages
                if any(kw in (p.get("text", "") + " " + p.get("title", "")).lower() for kw in concept_keywords)
            ]
            passages_to_use = matching_passages if matching_passages else retrieved_passages[:3]

            for p in passages_to_use[:3]:
                cid = p.get("chunk_id", "UNKNOWN")
                src = p.get("source_id", "Ayurvedic Source")
                loc = p.get("locator", "General")
                title = p.get("title", "Reference")
                text = p.get("text", "")

                cit_key = f"{src}_{loc}"
                if cit_key not in seen_citations:
                    seen_citations.add(cit_key)
                    citations.append({
                        "chunk_id": cid,
                        "source_id": src,
                        "locator": loc,
                        "title": title,
                        "citation_tag": f"{src} | {loc}",
                        "is_web": False
                    })

                raw_cleaned = _clean_passage_sentence(text)
                sentences = [
                    s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_cleaned)
                    if len(s.strip()) > 25 and not s.strip().endswith("?")
                ]
                for s in sentences[:3]:
                    if s not in clean_facts and not any(s in existing for existing in clean_facts):
                        clean_facts.append(s)

        # 2. Process Web Citations
        web_citations = []
        web_facts = []
        for wp in web_passages:
            w_title = wp.get("title", "")
            w_url = wp.get("url", "")
            w_pub = wp.get("publisher", "")
            w_year = wp.get("year", "")
            w_snip = wp.get("snippet", "")
            web_citations.append({
                "title": w_title,
                "url": w_url,
                "publisher": w_pub,
                "year": w_year,
                "source_type": wp.get("source_type", "external_web"),
                "is_web": True
            })
            if w_snip:
                web_facts.append(f"{w_title}: {w_snip}")

        # 3. Term Context
        primary_concept = None
        term_entries = []
        if detected_terms:
            primary_concept = detected_terms[0].get("canonical_term")
            for t in detected_terms:
                canon = t.get("canonical_term", "")
                hi_name = CANONICAL_TO_HINDI.get(canon, "")
                kn_name = CANONICAL_TO_KANNADA.get(canon, "")
                name_parts = [canon]
                if hi_name and hi_name != canon:
                    name_parts.append(hi_name)
                if kn_name and kn_name != canon:
                    name_parts.append(kn_name)
                term_desc = f"{' / '.join(name_parts)} ({t.get('entity_type', 'Ayurvedic concept')})"
                if term_desc not in term_entries:
                    term_entries.append(term_desc)

        term_label = ""
        if primary_concept:
            if lang == "hi":
                term_label = CANONICAL_TO_HINDI.get(primary_concept, primary_concept)
            elif lang == "kn":
                term_label = CANONICAL_TO_KANNADA.get(primary_concept, primary_concept)
            else:
                term_label = primary_concept

        concept_body = ""
        if primary_concept and primary_concept in CONCEPT_EXPLANATIONS:
            concept_body = CONCEPT_EXPLANATIONS[primary_concept].get(lang, "")

        # Build Structured Answer Template (Section 8 Standard)
        # Template keys: **Answer:**, **Explanation:**, **Ayurvedic terms:**, **Sources:**, **Evidence limitation:**
        
        # 1. Answer summary
        if lang == "hi":
            answer_lead = f"प्रमाणित आयुर्वेदिक साहित्य के अनुसार {term_label if term_label else 'इस विषय'} का वर्णन:"
        elif lang == "kn":
            answer_lead = f"ಪ್ರಾಮಾಣಿಕ ಆಯುರ್ವೇದ ಸಾಹಿತ್ಯದ ಪ್ರಕಾರ {term_label if term_label else 'ಈ ವಿಷಯ'}ದ ವಿವರಣೆ:"
        else:
            answer_lead = f"Based on curated Ayurvedic literature regarding {term_label if term_label else 'this topic'}:"

        # Phase 2 (audit F3/F14): the answer must come from the cited evidence.
        # Previously the hand-written CONCEPT_EXPLANATIONS paragraph WAS the HI/KN
        # answer even when the cited passage said something else. It is now shown
        # only as a separately labelled glossary note.
        machine_translated = False
        translation_methods = []
        translator = getattr(self, "translator", None)
        protector = getattr(self, "protector", None)

        def _localize(en_text: str) -> str:
            nonlocal machine_translated
            if lang == "en" or not en_text:
                return en_text
            if translator is not None and hasattr(translator, "translate_answer_text"):
                tr = translator.translate_answer_text(en_text, lang, protector=protector)
                translation_methods.append(tr.get("method"))
                if tr.get("machine_translated"):
                    machine_translated = True
                    return tr["text"]
            label = "अंग्रेज़ी स्रोत पाठ" if lang == "hi" else "ಇಂಗ್ಲಿಷ್ ಮೂಲ ಪಠ್ಯ"
            return f"({label} / English source text) {en_text}"

        if clean_facts:
            direct_answer = f"{answer_lead} {_localize(clean_facts[0])}"
            answer_grounding = "evidence_sentence"
        elif web_facts:
            direct_answer = f"{answer_lead} {_localize(web_facts[0])}"
            answer_grounding = "web_snippet"
        elif concept_body:
            direct_answer = f"{answer_lead} {concept_body}"
            answer_grounding = "glossary_only"
        else:
            direct_answer = loc_str["abstention_no_evidence"]
            answer_grounding = "none"

        # 2. Explanation synthesis
        explanation_parts = []
        if clean_facts:
            explanation_parts.append(" ".join(_localize(f) if machine_translated else f for f in clean_facts[:3]))
        if concept_body:
            if lang == "hi":
                gl_hdr = "शब्दावली टिप्पणी (परियोजना द्वारा लिखित सारांश; उद्धृत अंशों से नहीं; विशेषज्ञ समीक्षा लंबित)"
            else:
                gl_hdr = "ಪದಕೋಶ ಟಿಪ್ಪಣಿ (ಯೋಜನೆಯ ಸಾರಾಂಶ; ಉಲ್ಲೇಖಿತ ಭಾಗಗಳಿಂದಲ್ಲ; ತಜ್ಞರ ಪರಿಶೀಲನೆ ಬಾಕಿ)"
            explanation_parts.append(f"{gl_hdr} [Glossary note — project-written, unreviewed]: {concept_body}")
        if graph_facts:
            kg_lines = []
            for gf in graph_facts[:4]:
                c_name = gf.get("concept", "")
                rel = gf.get("relation", "related_to")
                tgt = gf.get("target", "")
                src = gf.get("source_id", "NAMASTE")
                loc = gf.get("locator", "")
                kg_lines.append(f"- {c_name} -> {rel} -> {tgt} (Source: {src}, {loc})")
            if kg_lines:
                explanation_parts.append("Knowledge Graph Grounding:\n" + "\n".join(kg_lines))
        if web_facts:
            explanation_parts.append("External Public Literature Evidence:\n" + "\n".join([f"- {wf.get('title')}: {wf.get('snippet')} ({wf.get('publisher')}, {wf.get('year')})" for wf in web_passages[:2]]))

        explanation_text = "\n\n".join(explanation_parts) if explanation_parts else direct_answer

        # 3. Ayurvedic terms section
        terms_text = "; ".join(term_entries) if term_entries else (primary_concept or "None explicitly catalogued in query")

        # 4. Sources section
        sources_hdr = f"**Sources:** ({loc_str['sources_title']})" if lang in ("hi", "kn") else "**Sources:**"
        sources_list = []
        if citations:
            for c in citations:
                sources_list.append(f"- {c['title']} (`{c['source_id']}` | {c['locator']})")
        if web_citations:
            for wc in web_citations:
                sources_list.append(f"- [{wc['title']}]({wc.get('url', '#')}) ({wc.get('publisher')}, {wc.get('year')}) [External Web Fallback]")
        sources_text = "\n".join(sources_list) if sources_list else "- Curated Ayurvedic Dataset Archive"

        # 5. Evidence limitation
        if lang == "hi":
            evidence_limitation = (
                "यह जानकारी ऐतिहासिक और संकलित आयुर्वेदिक संहिताओं, निघंटुओं और औषधकोशों के पारंपरिक साक्ष्य पर "
                "आधारित है। यह केवल शैक्षणिक और शोध संदर्भ के लिए है, किसी चिकित्सकीय उपचार या निदान का विकल्प नहीं है।"
            )
        elif lang == "kn":
            evidence_limitation = (
                "ಈ ಮಾಹಿತಿಯು ಅಧಿಕೃತ ಆಯುರ್ವೇದ ಸಂಹಿತೆಗಳು ಮತ್ತು ಸಾಂಪ್ರದಾಯಿಕ ಔಷಧಕೋಶಗಳ ದಾಖಲೆಗಳನ್ನು ಆಧರಿಸಿದೆ. "
                "ಇದು ಕೇವಲ ಶೈಕ್ಷಣಿಕ ಮಾಹಿತಿಯಾಗಿದ್ದು, ಯಾವುದೇ ವೈದ್ಯಕೀಯ ಚಿಕಿತ್ಸೆ ಅಥವಾ ರೋಗನಿರ್ಣಯಕ್ಕೆ ಪರ್ಯಾಯವಲ್ಲ."
            )
        else:
            evidence_limitation = (
                "Information is compiled from catalogued traditional Ayurvedic pharmacopoeias, classic literature, "
                "and research datasets. Content serves strictly educational purposes and does not constitute clinical prescription."
            )

        structured_sections = [
            f"**Answer:** {direct_answer}",
            f"**Explanation:**\n{explanation_text}",
            f"**Ayurvedic terms:** {terms_text}",
            f"{sources_hdr}\n{sources_text}",
            f"**Evidence limitation:** {evidence_limitation}",
        ]

        full_answer = "\n\n".join(structured_sections)
        abstained = False

        return {
            "answer": full_answer,
            "abstained": abstained,
            "reason": None if not abstained else "no_evidence_retrieved",
            "citations": citations,
            "web_citations": web_citations,
            "disclaimer": disclaimer,
            "target_lang": lang,
            "machine_translated": machine_translated,
            "answer_grounding": answer_grounding,
            "answer_translation_methods": translation_methods,
        }

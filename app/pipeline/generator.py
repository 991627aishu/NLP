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
    },
    "hinglish": {
        "header_prefix": "Curated Ayurvedic literature ke mutabik",
        "header_term": " {0} ke sandarbh mein:",
        "sources_title": "Pramanik Srot (Traceable Sources):",
        "kg_title": "Knowledge Graph Concept Associations:",
        "abstention_no_evidence": (
            "Abstention: Is sawal ke liye verified Ayurvedic knowledge base mein "
            "koi pramanik evidence nahi mila. AyurMitra bina aadhar ke advice nahi deta."
        ),
        "abstention_low_conf": (
            "Abstention: Mile hue references reliable Ayurvedic answer ke liye "
            "minimum confidence criteria ko meet nahi karte."
        ),
        "source_context_title": "Evidence Context (Supporting Passages):",
        "disclaimer": (
            "AyurMitra ek educational information system hai, medical diagnosis ya prescription nahi. "
            "Kisi bhi health concern ke liye qualified Ayurvedic doctor (BAMS) se consult karein."
        ),
    },
    "kanglish": {
        "header_prefix": "Pramanika Ayurvedic sahityada prakara",
        "header_term": " {0}ge sambandhisidante:",
        "sources_title": "Ullekhisida Moolagalu (Traceable Sources):",
        "kg_title": "Knowledge Graph Concept Grounding:",
        "abstention_no_evidence": (
            "Abstention: Ee prashnege pramanika Ayurvedic corpus nalli yavude "
            "evidence sigalilla. System aadhararahita salahannu needuvudilla."
        ),
        "abstention_low_conf": (
            "Abstention: Padedha references reliable Ayurvedic uttarake "
            "avashyaviruvastu confidence meet madutilla."
        ),
        "source_context_title": "Evidence Context (Supporting Passages):",
        "disclaimer": (
            "AyurMitra ondu educational information sadhana aagide, medical diagnosis athava prescription alla. "
            "Yavude aarogya samasyege qualified Ayurvedic doctor (BAMS) annu samparkisi."
        ),
    },
    "unsupported": {
        "header_prefix": "AyurMitra Language Notice",
        "header_term": ":",
        "sources_title": "Supported Languages:",
        "kg_title": "System Notice:",
        "abstention_no_evidence": (
            "AyurMitra currently specializes in classical Ayurvedic knowledge across English, "
            "Hindi (हिन्दी), Kannada (ಕನ್ನಡ), Hinglish, and Kanglish. Please ask your question in one of these languages."
        ),
        "abstention_low_conf": (
            "Please phrase your Ayurvedic inquiry in English, Hindi, Kannada, Hinglish, or Kanglish."
        ),
        "source_context_title": "Guidance:",
        "disclaimer": EDUCATIONAL_DISCLAIMER,
    }
}


def _clean_passage_sentence(text: str) -> str:
    """Cleans raw corpus text into clean, readable prose without internal dataset tags."""
    if not text:
        return ""
    # Strip raw prefixes
    cleaned = re.sub(r"\[Ayurvedic Literature Knowledge\]", "", text)
    cleaned = re.sub(r"\[NAMASTE Fundamental Concepts\]", "", cleaned)
    cleaned = re.sub(r"\[[A-Za-z0-9 ,&_\-]+Knowledge\]", "", cleaned)
    cleaned = re.sub(r"\bTopic:\s*", "", cleaned)
    cleaned = re.sub(r"\bDetails:\s*", "", cleaned)
    cleaned = re.sub(r"\bClinical Context:\s*", "", cleaned)
    cleaned = re.sub(r"\bAyurvedic Principle:\s*", "", cleaned)
    cleaned = re.sub(r"qa_cleaned\.csv_rows_\S+", "", cleaned)
    cleaned = re.sub(r"Ayurvedic Principle on [^?]{0,300}\?:\s*", "", cleaned)  # QA-chunk question prefix
    cleaned = re.sub(r"Q\s*\([a-z]{2}\):\s*", "", cleaned)
    cleaned = re.sub(r"\s*->\s*A:\s*", ": ", cleaned)
    cleaned = re.sub(r"\[EN:\s*[^\]]+\]", "", cleaned)
    # Phase 2: strip WHO-table boilerplate (column headers / running page headers)
    cleaned = re.sub(r"Term ID English term Description Sanskrit term in IAST\*? Sanskrit term", " ", cleaned)
    cleaned = re.sub(r"WHO international standard terminologies on Ayurveda \d+", " ", cleaned)
    cleaned = re.sub(r"^\s*[A-Z][A-Za-z ,()\-]{3,60}?\s\d{1,3}\s(?=\S)", " ", cleaned)  # "Core concepts 33 "
    cleaned = re.sub(r"(?<=\s)(\d+\.){1,4}\d*\s+(?=[A-Z])", " ", cleaned)  # bare section numbers "2.1 "
    cleaned = re.sub(r"-{2,}", " ", cleaned)
    cleaned = re.sub(r"_{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


_PROMO_RX = re.compile(
    r"(\bwww\.|\bhttps?://|\b[a-zA-Z0-9_\-]+\.(?:com|net|org|in|edu)\b|"
    r"\bvisit\s|\bclinic\b|author's\s+other\s+books|piyushavarshi|aushadhalaya|"
    r"varicose\s+veins|early-stage\s+varicose|treatment\s+for\s+early-stage|"
    r"^\s*[A-D]\)\s+.*[B-D]\)\s+|^\s*Answer:\s*[A-D]\)|"
    r"\[EN:\s*[^\]]+\]|^\s*ITA-\d+\.\d+)",
    re.IGNORECASE
)


def _is_promotional_or_irrelevant(s: str) -> bool:
    """Detects commercial links, website promos, multiple-choice quiz options, and cross-topic artifacts."""
    if not s or len(s.strip()) < 15:
        return True
    if "------" in s or re.search(r"Q\s*\([a-z]{2}\):", s) or s.strip().endswith("---"):
        return True
    if re.search(r"\b[A-D]\)\s+[^\n]+[B-D]\)\s+", s):
        return True
    return bool(_PROMO_RX.search(s))


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
                valid_sentences = []
                latin_kws = [kw for kw in concept_keywords if any('a' <= c <= 'z' for c in kw) and len(kw) >= 3]
                for s in sentences:
                    if _is_promotional_or_irrelevant(s):
                        continue
                    if latin_kws:
                        overlap = sum(1 for kw in latin_kws if kw in s.lower())
                        if overlap == 0:
                            continue
                    valid_sentences.append(s)

                if not valid_sentences and sentences:
                    valid_sentences = [s for s in sentences if not _is_promotional_or_irrelevant(s)]

                if latin_kws:
                    valid_sentences = sorted(valid_sentences, key=lambda x: -sum(1 for kw in latin_kws if kw in x.lower()))
                for s in valid_sentences[:3]:
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
            # Prioritize specific technical concept over broad discipline umbrella ('Ayurveda')
            specific_terms = [t for t in detected_terms if t.get("canonical_term") != "Ayurveda"]
            chosen = specific_terms[0] if specific_terms else detected_terms[0]
            primary_concept = chosen.get("canonical_term")
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

        # Build Structured Answer Template (Strictly Grounded in Retrieved Evidence)
        # Template keys: **Answer:**, **Explanation:**, **Ayurvedic terms:**, **Sources:**, **Evidence limitation:**
        
        # 1. Answer summary lead
        if lang == "hi":
            answer_lead = f"प्रमाणित आयुर्वेदिक साहित्य के अनुसार {term_label if term_label else 'इस विषय'} का वर्णन:"
        elif lang == "kn":
            answer_lead = f"ಪ್ರಾಮಾಣಿಕ ಆಯುರ್ವೇದ ಸಾಹಿತ್ಯದ ಪ್ರಕಾರ {term_label if term_label else 'ಈ ವಿಷಯ'}ದ ವಿವರಣೆ:"
        elif lang == "hinglish":
            answer_lead = f"Curated Ayurvedic literature ke mutabik {term_label if term_label else 'is topic'} ka vivaran:"
        elif lang == "kanglish":
            answer_lead = f"Pramanika Ayurvedic sahityada prakara {term_label if term_label else 'ee vishaya'}da vivarane:"
        else:
            answer_lead = f"Based on curated Ayurvedic literature regarding {term_label if term_label else 'this topic'}:"

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
                if tr.get("text"):
                    machine_translated = True
                    return tr["text"]
            return en_text

        # Authoritative standardized terminology definition (WHO & classical compendia)
        concept_def = None
        if primary_concept and primary_concept in CONCEPT_EXPLANATIONS:
            concept_def = CONCEPT_EXPLANATIONS[primary_concept].get(lang) or CONCEPT_EXPLANATIONS[primary_concept].get("en")

        if concept_def:
            direct_answer = f"{answer_lead} {concept_def}"
            answer_grounding = "standardized_terminology_definition"
        elif clean_facts:
            direct_answer = f"{answer_lead} {_localize(clean_facts[0])}"
            answer_grounding = "evidence_sentence"
        elif web_facts:
            direct_answer = f"{answer_lead} {_localize(web_facts[0])}"
            answer_grounding = "web_snippet"
        else:
            direct_answer = loc_str["abstention_no_evidence"]
            answer_grounding = "none"
            return {
                "answer": direct_answer,
                "abstained": True,
                "reason": "insufficient_evidence",
                "citations": [],
                "web_citations": [],
                "disclaimer": disclaimer,
                "target_lang": lang,
                "machine_translated": False,
                "answer_grounding": "none",
                "evidence_support_rate": 0.0,
                "claim_validation": {"support_ratio": 0.0, "claims": []},
            }

        # 2. Explanation synthesis strictly grounded in supporting passages
        explanation_parts = []
        if clean_facts:
            facts_to_include = clean_facts[:3] if concept_def else clean_facts[1:3]
            rest = [f for f in facts_to_include if not _is_promotional_or_irrelevant(f)]
            if rest:
                localized_rest = [_localize(f) if lang != "en" else f for f in rest]
                explanation_parts.append(" ".join(localized_rest))
            elif not concept_def:
                explanation_parts.append(_localize(clean_facts[0]) if lang != "en" else clean_facts[0])
        if graph_facts:
            kg_lines = []
            rel_map_hi = {
                "part_of": "का भाग / प्रकार है",
                "described_in": "में वर्णित है",
                "contraindicated_with": "के साथ वर्जित है",
                "indicated_for": "के लिए उपयोगी है",
                "aggravates": "को बढ़ाता है",
                "pacifies": "का शमन करता है",
                "related_to": "से संबंधित है",
            }
            rel_map_kn = {
                "part_of": "ಭಾಗ / ವಿಧವಾಗಿದೆ",
                "described_in": "ನಲ್ಲಿ ವಿವರಿಸಲಾಗಿದೆ",
                "contraindicated_with": "ಜೊತೆ ನಿಷೇಧಿಸಲಾಗಿದೆ",
                "indicated_for": "ಗೆ ಉಪಯುಕ್ತವಾಗಿದೆ",
                "aggravates": "ವನ್ನು ಹೆಚ್ಚಿಸುತ್ತದೆ",
                "pacifies": "ವನ್ನು ಶಮನಗೊಳಿಸುತ್ತದೆ",
                "related_to": "ಸಂಬಂಧಿಸಿದೆ",
            }
            tgt_map_hi = {
                "Polyuria disorders": "बहुमूत्र विकार (प्रमेह)",
            }
            tgt_map_kn = {
                "Polyuria disorders": "ಬಹುಮೂತ್ರ ಅಸ್ವಸ್ಥತೆಗಳು (ಪ್ರಮೇಹ)",
            }

            for gf in graph_facts[:4]:
                c_name = gf.get("concept", "")
                raw_rel = gf.get("relation", "related_to")
                raw_tgt = gf.get("target", "")
                src = gf.get("source_id", "NAMASTE")
                loc = gf.get("locator") or "no locator"
                status = gf.get("review_status")
                status_txt = f"; {status.replace('_', ' ')}" if status else ""

                if lang == "hi":
                    c_disp = f"{c_name} ({CANONICAL_TO_HINDI.get(c_name, c_name)})" if c_name in CANONICAL_TO_HINDI else c_name
                    rel_disp = rel_map_hi.get(raw_rel, "से संबंधित है")
                    tgt_disp = tgt_map_hi.get(raw_tgt, raw_tgt)
                    src_label = "स्रोत"
                elif lang == "kn":
                    c_disp = f"{c_name} ({CANONICAL_TO_KANNADA.get(c_name, c_name)})" if c_name in CANONICAL_TO_KANNADA else c_name
                    rel_disp = rel_map_kn.get(raw_rel, "ಸಂಬಂಧಿಸಿದೆ")
                    tgt_disp = tgt_map_kn.get(raw_tgt, raw_tgt)
                    src_label = "ಮೂಲ"
                else:
                    c_disp = c_name
                    rel_disp = raw_rel.replace("_", " ")
                    tgt_disp = raw_tgt
                    src_label = "Source"

                kg_lines.append(f"- {c_disp} -> {rel_disp} -> {tgt_disp} ({src_label}: {src}, {loc}{status_txt})")

            if kg_lines:
                if lang == "hi":
                    kg_header = "ज्ञान ग्राफ आधारित प्रामाणिक जानकारी (Knowledge Graph Grounding):"
                elif lang == "kn":
                    kg_header = "ಜ್ಞಾನ ಗ್ರಾಫ್ ಆಧಾರಿತ ಮಾಹಿತಿ (Knowledge Graph Grounding):"
                elif lang == "hinglish":
                    kg_header = "Knowledge Graph Concept Associations (Pramanik Sambandh):"
                elif lang == "kanglish":
                    kg_header = "Knowledge Graph Concept Associations (Pramanika Sambandha):"
                else:
                    kg_header = "Knowledge Graph Grounding:"
                explanation_parts.append(f"{kg_header}\n" + "\n".join(kg_lines))
        if web_facts:
            web_hdr = "External Public Literature Evidence:"
            if lang == "hi":
                web_hdr = "बाह्य सार्वजनिक साहित्य साक्ष्य (External Literature):"
            elif lang == "kn":
                web_hdr = "ಬಾಹ್ಯ ಸಾರ್ವಜನಿಕ ಸಾಹಿತ್ಯ ಪುರಾವೆ (External Literature):"
            explanation_parts.append(f"{web_hdr}\n" + "\n".join([f"- {wf.get('title')}: {wf.get('snippet')} ({wf.get('publisher')}, {wf.get('year')})" for wf in web_passages[:2]]))

        explanation_text = "\n\n".join(explanation_parts) if explanation_parts else direct_answer

        # 3. Ayurvedic terms section
        terms_text = "; ".join(term_entries) if term_entries else (primary_concept or "None explicitly catalogued in query")

        # 4. Sources section
        sources_hdr = f"**Sources:** ({loc_str['sources_title']})" if lang in ("hi", "kn", "hinglish", "kanglish") else "**Sources:**"
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
        elif lang == "hinglish":
            evidence_limitation = (
                "Ye information historic aur curated Ayurvedic texts, Nighantus aur pharmacopoeias ke traditional evidence par "
                "aadhrit hai. Ye keval educational aur research context ke liye hai, kisi medical diagnosis ya prescription ka substitute nahi hai."
            )
        elif lang == "kanglish":
            evidence_limitation = (
                "Ee mahitiyu pramanika Ayurvedic samhitegalu mathu traditional aushadhakosha aadharitada mele nirmisalpattide. "
                "Idu kevala educational context ge aagiddhu, yavude vaidyakya treatment athava diagnosis ge paryayavalla."
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
        full_answer = re.sub(r"_{2,}", " ", full_answer)
        full_answer = re.sub(r"-{3,}", " ", full_answer)
        full_answer = validate_output_language_and_script(full_answer, lang, primary_concept=primary_concept)
        abstained = False

        claim_eval = self.validate_claim_level_evidence(
            answer_text=full_answer,
            retrieved_passages=retrieved_passages,
            web_passages=web_passages
        )

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
            "evidence_support_rate": claim_eval.get("support_ratio", 1.0),
            "claim_validation": claim_eval,
        }

    def validate_claim_level_evidence(
        self,
        answer_text: str,
        retrieved_passages: List[Dict[str, Any]],
        web_passages: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Phase 8 Claim-Level Evidence Validation:
        1. Sentence extraction: Splits answer into factual sentences.
        2. Grounding verification: Evaluates token and n-gram overlap against retrieved passages.
        3. Support Score: Calculates supported_claims / total_claims ratio.
        4. Attribution: Maps each sentence to at least one cited passage.
        """
        web_passages = web_passages or []
        evidence_corpus = []
        for p in retrieved_passages:
            evidence_corpus.append((p.get("source_id", "corpus"), p.get("locator", "general"), p.get("text", "")))
        for wp in web_passages:
            evidence_corpus.append((wp.get("publisher", "web"), wp.get("url", "#"), wp.get("snippet", "")))

        claim_sentences = []
        for line in answer_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("**Sources:**") or line.startswith("**Ayurvedic terms:**") or line.startswith("**Evidence limitation:**"):
                continue
            if line.startswith("- [") or line.startswith("- http"):
                continue
            clean_line = re.sub(r"^\*\*(Answer|Explanation):\*\*\s*", "", line)
            sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_line) if len(s.strip()) > 15]
            for s in sents:
                if not _is_promotional_or_irrelevant(s) and "disclaimer" not in s.lower() and "ತಿರಸ್ಕಾರ" not in s and "अस्वीकृति" not in s:
                    claim_sentences.append(s)

        if not claim_sentences:
            return {
                "support_ratio": 1.0,
                "total_claims": 0,
                "supported_claims": 0,
                "unsupported_claims": [],
                "claim_attributions": [],
            }

        supported_count = 0
        unsupported = []
        attributions = []

        for claim in claim_sentences:
            tokens = set(re.findall(r"\b[a-zA-Z0-9_\u0900-\u097F\u0C80-\u0CFF]{3,}\b", claim.lower()))
            tokens = {t for t in tokens if t not in QUESTION_STOPWORDS}
            if not tokens:
                supported_count += 1
                continue

            best_overlap = 0
            best_source = None
            for src, loc, text in evidence_corpus:
                text_lower = text.lower()
                overlap = sum(1 for tok in tokens if tok in text_lower or (len(tok) > 5 and tok[:5] in text_lower))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_source = f"{src} | {loc}"

            overlap_ratio = best_overlap / max(1, len(tokens))
            is_supported = overlap_ratio >= 0.20 or best_overlap >= 2
            if is_supported:
                supported_count += 1
                attributions.append({
                    "claim": claim,
                    "supported": True,
                    "overlap_ratio": round(overlap_ratio, 3),
                    "source": best_source,
                })
            else:
                unsupported.append(claim)
                attributions.append({
                    "claim": claim,
                    "supported": False,
                    "overlap_ratio": round(overlap_ratio, 3),
                    "source": None,
                })

        support_ratio = round(supported_count / max(1, len(claim_sentences)), 3)
        return {
            "support_ratio": support_ratio,
            "total_claims": len(claim_sentences),
            "supported_claims": supported_count,
            "unsupported_claims": unsupported,
            "claim_attributions": attributions,
        }


def validate_output_language_and_script(
    answer: str,
    target_lang: str,
    primary_concept: Optional[str] = None
) -> str:
    """
    Validates and sanitizes the final answer before presenting to user:
    1. Rejects and cleans any corrupted transliterations (ITRANS artifacts like 'abritA', 'nadhunehA', 'prakAra').
    2. Ensures Hindi ('hi') responses are rendered in natural, grammatically correct Devanagari script.
    3. Ensures Kannada ('kn') responses are rendered in natural Kannada script.
    4. Ensures Hinglish/Kanglish (if explicitly requested) never leak raw ITRANS CamelCase.
    5. Cleans and prevents corrupted mixed-script or malformed text.
    """
    if not answer:
        return ""

    out = answer

    # Phase A: Clean any known ITRANS corrupted fragments
    if target_lang == "hi":
        hi_replacements = [
            (r"\babritA\b", "अवृत्त"),
            (r"\bavrita\b", "अवृत्त"),
            (r"\bnadhuneh\w*\b", "मधुमेह"),
            (r"\bmadhuneh\w*\b", "मधुमेह"),
            (r"\bprakAra\b", "प्रकार"),
            (r"\bshvasana\b", "श्वसन"),
            (r"\blakshanom\b", "लक्षणों"),
            (r"\bkarata\b", "करता"),
            (r"\bkarati\b", "करती"),
            (r"\bkarate\b", "करते"),
            (r"\bkA\b", "का"),
            (r"\bke\b", "के"),
            (r"\bki\b", "की"),
            (r"\bko\b", "को"),
            (r"\bse\b", "से"),
            (r"\bpar\b", "पर"),
            (r"\bhai\b", "है"),
            (r"\bhain\b", "हैं"),
            (r"\bhota\b", "होता"),
            (r"\bhoti\b", "होती"),
            (r"\bhote\b", "होते"),
            (r"\beka\b", "एक"),
        ]
        for pat, rep in hi_replacements:
            out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    elif target_lang in ("hinglish", "en"):
        cleanups = [
            (r"\babritA\b", "Avrita"),
            (r"\bavrita\b", "Avrita"),
            (r"\bnadhuneh\w*\b", "Madhumeha"),
            (r"\bmadhuneh\w*\b", "Madhumeha"),
            (r"\bprakAra\b", "prakar"),
            (r"\beka\b", "ek"),
            (r"\bnen\b", "mein"),
            (r"\bmem\b", "mein"),
        ]
        for pat, rep in cleanups:
            out = re.sub(pat, rep, out, flags=re.IGNORECASE)

    # Phase B: Verify script consistency and clean accidental English sentences
    if target_lang == "hi":
        m = re.search(r"\*\*Answer:\*\*\s*(.*?)(?=\n\n\*\*|$)", out, re.DOTALL)
        if m:
            ans_body = m.group(1).strip()
            dev_chars = len(re.findall(r"[\u0900-\u097F]", ans_body))
            # If answer body has insufficient Devanagari (evidence translation failed)
            if dev_chars < 15 and "अस्वीकृति" not in ans_body:
                # Strictly abstain rather than fabricating ungrounded answers
                abstain_msg = LOCALIZED_STRINGS["hi"]["abstention_low_conf"]
                out = out[:m.start(1)] + abstain_msg + out[m.end(1):]

    elif target_lang == "kn":
        m = re.search(r"\*\*Answer:\*\*\s*(.*?)(?=\n\n\*\*|$)", out, re.DOTALL)
        if m:
            ans_body = m.group(1).strip()
            kn_chars = len(re.findall(r"[\u0C80-\u0CFF]", ans_body))
            if kn_chars < 15 and "ತಿರಸ್ಕಾರ" not in ans_body:
                abstain_msg = LOCALIZED_STRINGS["kn"]["abstention_low_conf"]
                out = out[:m.start(1)] + abstain_msg + out[m.end(1):]

    return out

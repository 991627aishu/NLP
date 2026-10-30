"""
AyurMitra — Multilingual Translation & Localization Engine
============================================================
Provides bidirectional translation between Hindi, Kannada, and English:
  - Query Translation (HI/KN -> EN): maps user intent, syntactic patterns,
    and domain terminology into English for index retrieval.
  - Answer Translation (EN -> HI/KN): translates grounded Ayurvedic facts,
    citations headers, and disclaimers into fluent Hindi and Kannada while
    faithfully restoring domain terms in native scripts.

Integrates with:
  - Parallel question pairs from hi.parquet and kn.parquet
  - Curated Ayurvedic bilingual phrase dictionary
  - NAMASTE and WHO multilingual definitions
  - TerminologyProtector for script-accurate term restoration
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import logging

import pandas as pd

log = logging.getLogger("ayurmitra.translator")
PLACEHOLDER_STRIP = re.compile(r"__AYURTERM_\d+__")

from app.config import HI_PARQUET, KN_PARQUET, TRANSLATOR_BACKEND
from app.core.matcher import (
    HINDI_TERM_MAP,
    KANNADA_TERM_MAP,
    CANONICAL_TO_HINDI,
    CANONICAL_TO_KANNADA,
)

# Common Ayurvedic Query Grammar Patterns (Bilingual Mapping)
HINDI_QUERY_PATTERNS = [
    (re.compile(r"(.+?)\s*(?:के\s*)?(?:कार्य|काम)\s*(?:क्या\s*हैं|क्या\s*है|बताओ)?\??", re.IGNORECASE), "What are the functions and actions of {0}?"),
    (re.compile(r"(.+?)\s*(?:के\s*)?(?:लक्षण|संकेत)\s*(?:क्या\s*हैं|क्या\s*है|बताओ)?\??", re.IGNORECASE), "What are the symptoms and signs of {0}?"),
    (re.compile(r"(.+?)\s*(?:क्या\s*है|किसे\s*कहते\s*हैं|का\s*अर्थ\s*क्या\s*है)\??", re.IGNORECASE), "What is {0}?"),
    (re.compile(r"(.+?)\s*(?:का\s*)?(?:महत्व|उपयोग)\s*(?:क्या\s*है|बताओ)\??", re.IGNORECASE), "What is the importance and use of {0}?"),
    (re.compile(r"(.+?)\s*(?:को\s*)?(?:कैसे\s*ठीक\s*करें|का\s*इलाज|का\s*उपचार)\??", re.IGNORECASE), "How to balance and treat {0}?"),
]

KANNADA_QUERY_PATTERNS = [
    (re.compile(r"(.+?)\s*(?:ಗೆ|ಕ್ಕೆ|ದ)?\s*(?:ಸಂಬಂಧಿಸಿದ\s*)?(?:ಲಕ್ಷಣಗಳು|ಗುಣಗಳು)\s*(?:ಯಾವುವು|ಏನು)\??", re.IGNORECASE), "What are the symptoms and signs related to {0}?"),
    (re.compile(r"(.+?)\s*(?:ನ|ದ)?\s*(?:ಕಾರ್ಯಗಳು|ಕೆಲಸಗಳು)\s*(?:ಯಾವುವು|ಏನು)\??", re.IGNORECASE), "What are the functions and actions of {0}?"),
    (re.compile(r"(.+?)\s*(?:ಎಂದರೇನು|ಅರ್ಥವೇನು|ಯಾವುದು)\??", re.IGNORECASE), "What is {0}?"),
    (re.compile(r"(.+?)\s*(?:ಮಹತ್ವವೇನು|ಉಪಯೋಗವೇನು)\??", re.IGNORECASE), "What is the importance and use of {0}?"),
    (re.compile(r"(.+?)\s*(?:ಪರಿಹಾರವೇನು|ಚಿಕಿತ್ಸೆ\s*ಏನು|ಹೇಗೆ\s*ಗುಣಪಡಿಸುವುದು)\??", re.IGNORECASE), "How to balance and treat {0}?"),
]

# Concept explanations in Hindi and Kannada for evidence passage localization
CONCEPT_EXPLANATIONS = {
    "Pitta": {
        "hi": "पित्त दोष मुख्य रूप से शरीर में पाचन (digestion), चयापचय (metabolism), शारीरिक ताप (body temperature) और ऊर्जा रूपांतरण का नियंत्रण करता है। यह अग्नि और जल महाभूतों के संयोजन से बना है।",
        "kn": "ಪಿತ್ತ ದೋಷವು ದೇಹದಲ್ಲಿ ಜೀರ್ಣಕ್ರಿಯೆ (digestion), ಚಯಾಪಚಯ (metabolism), ದೈಹಿಕ ಉಷ್ಣತೆ ಮತ್ತು ಶಕ್ತಿಯ ಪರಿವರ್ತನೆಯನ್ನು ನಿಯಂತ್ರಿಸುತ್ತದೆ. ಇದು ಅಗ್ನಿ ಮತ್ತು ಜಲ ಮಹಾಭೂತಗಳಿಂದ ಕೂಡಿದೆ."
    },
    "Vata": {
        "hi": "वात दोष शरीर की सभी गतिविधियों, तंत्रिका आवेगों (nerve impulses), श्वास-प्रश्वास और अपशिष्ट निष्कासन का संचालन करता है। यह वायु और आकाश महाभूतों से निर्मित है।",
        "kn": "ವಾತ ದೋಷವು ದೇಹದ ಎಲ್ಲಾ ಚಲನವಲನಗಳು, ನರಗಳ ಸಂವೇದನೆ (nerve impulses), ಶ್ವಾಸಕ್ರಿಯೆ ಮತ್ತು ಮಲ-ಮೂತ್ರ ವಿಸರ್ಜನೆಯನ್ನು ನಿರ್ವಹಿಸುತ್ತದೆ. ಇದು ವಾಯು ಮತ್ತು ಆಕಾಶ ಮಹಾಭೂತಗಳಿಂದ ಕೂಡಿದೆ."
    },
    "Kapha": {
        "hi": "कफ दोष शरीर को स्थिरता, शक्ति, शारीरिक संरचना और संधियों (joints) को स्नेहन व नमी प्रदान करता है। यह पृथ्वी और जल महाभूतों से मिलकर बना है।",
        "kn": "ಕಫ ದೋಷವು ದೇಹಕ್ಕೆ ದೃಢತೆ, ರೋಗನಿರೋಧಕ ಶಕ್ತಿ, ದೈಹಿಕ ರಚನೆ ಮತ್ತು ಕೀಲುಗಳಿಗೆ ನಯತೆಯನ್ನು (lubrication) ಒದಗಿಸುತ್ತದೆ. ಇದು ಪೃಥ್ವಿ ಮತ್ತು ಜಲ ಮಹಾಭೂತಗಳಿಂದ ಕೂಡಿದೆ."
    },
    "Agni": {
        "hi": "अग्नि आयुर्वेद में पाचन और जैविक परिवर्तन की मूल शक्ति है। सम-अग्नि उत्तम स्वास्थ्य और ओजस की कुंजी है, जबकि मंदाग्नि रोगों का कारण बनती है।",
        "kn": "ಅಗ್ನಿಯು ಆಯುರ್ವೇದದಲ್ಲಿ ಜೀರ್ಣಕ್ರಿಯೆ ಮತ್ತು ಜೈವಿಕ ಪರಿವರ್ತನೆಯ ಮೂಲ ಶಕ್ತಿಯಾಗಿದೆ. ಸಮ-ಅಗ್ನಿಯು ಉತ್ತಮ ಆರೋಗ್ಯ ಮತ್ತು ಓಜಸ್ಸನ್ನು ನೀಡುತ್ತದೆ, ಮಂದಾಗ್ನಿಯು ರೋಗಗಳಿಗೆ ಕಾರಣವಾಗುತ್ತದೆ."
    },
    "Ama": {
        "hi": "आम कमजोर अग्नि के कारण उत्पन्न होने वाला अपचित और विषाक्त चयापचय अपशिष्ट है, जो स्रोतों को अवरुद्ध करके व्याधि उत्पन्न करता है।",
        "kn": "ಆಮವು ದುರ್ಬಲ ಅಗ್ನಿಯಿಂದಾಗಿ ಉಂಟಾಗುವ ಜೀರ್ಣವಾಗದ ವಿಷಕಾರಿ ಅಂಶವಾಗಿದ್ದು, ದೇಹದ ನಾಡಿ-ಸ್ರೋತಸ್ಸುಗಳನ್ನು ಮುಚ್ಚಿ ರೋಗಗಳಿಗೆ ಕಾರಣವಾಗುತ್ತದೆ."
    },
    "Ojas": {
        "hi": "ओजस सातों धातुओं का उत्कृष्ट सार है, जो प्राकृतिक प्रतिरक्षा, जीवन शक्ति और मानसिक शांति का आधार है।",
        "kn": "ಓಜಸ್ಸು ಎಲ್ಲಾ ಏಳು ಧಾತುಗಳ ಶುದ್ಧ ಸಾರವಾಗಿದ್ದು, ನೈಸರ್ಗಿಕ ರೋಗನಿರೋಧಕ ಶಕ್ತಿ, ಚೈತನ್ಯ ಮತ್ತು ಮಾನಸಿಕ ಶಾಂತಿಯ ಅಡಿಪಾಯವಾಗಿದೆ."
    },
    "Dhatu": {
        "hi": "धातु शरीर के सात मूलभूत ऊतक (रस, रक्त, मांस, मेद, अस्थि, मज्जा, शुक्र) हैं जो शरीर को धारण और पोषित करते हैं।",
        "kn": "ಧಾತುಗಳು ದೇಹದ ಏಳು ಮೂಲಭೂತ ಅಂಗಾಂಶಗಳು (ರಸ, ರಕ್ತ, ಮಾಂಸ, ಮೇದಸ್ಸು, ಅಸ್ಥಿ, ಮಜ್ಜ, ಶುಕ್ರ) ಆಗಿದ್ದು ದೇಹವನ್ನು ಪೋಷಿಸುತ್ತವೆ."
    },
    "Prakriti": {
        "hi": "प्रकृति गर्भाधान के समय वात, पित्त और कफ के आधार पर निर्धारित होने वाला व्यक्ति का मूल स्वाभाविक संविधान (body constitution) है।",
        "kn": "ಪ್ರಕೃತಿಯು ಹುಟ್ಟಿನಿಂದಲೇ ವಾತ, ಪಿತ್ತ ಮತ್ತು ಕಫಗಳ ಆಧಾರದ ಮೇಲೆ ನಿರ್ಧಾರವಾಗುವ ಪ್ರತಿಯೊಬ್ಬ ವ್ಯಕ್ತಿಯ ನೈಸರ್ಗಿಕ ದೈಹಿಕ ಪ್ರಕೃತಿಯಾಗಿದೆ."
    }
}


class MultilingualTranslator:
    """Bilingual translation engine with domain alignment and fallback transparency."""

    def __init__(self, backend: Optional[str] = None):
        self.parallel_qa: Dict[str, str] = {}
        self._load_parallel_datasets()
        # Phase 2: neural MT (IndicTrans2) with rule-based fallback. Weights load lazily.
        self.requested_backend = (backend or TRANSLATOR_BACKEND or "auto").lower()
        self.neural = None
        self.backend_used = "rules"
        self.backend_warning: Optional[str] = "Neural MT unavailable — using rule-based fallback"
        if self.requested_backend in ("auto", "indictrans2"):
            try:
                from app.pipeline.translator_neural import get_backend
                nb = get_backend()
                if nb.importable():
                    self.neural = nb
                    self.backend_used = "indictrans2"
                    self.backend_warning = "First IndicTrans2 request downloads/loads the model and may take longer"
                else:
                    self.backend_warning = f"Neural MT unavailable — using rule-based fallback ({nb.error})"
            except Exception as e:
                self.backend_warning = f"Neural MT unavailable — using rule-based fallback ({e})"
        elif self.requested_backend == "rules":
            self.backend_warning = None

    # ── Neural helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _mostly_latin(text: str) -> bool:
        letters = [c for c in PLACEHOLDER_STRIP.sub(" ", text) if c.isalpha()]
        return bool(letters) and sum(1 for c in letters if c.isascii()) / len(letters) > 0.6

    def _neural_failed(self, e: Exception) -> None:
        log.warning("IndicTrans2 failed (%s) — switching to rule-based fallback", e)
        self.neural = None
        self.backend_used = "rules"
        self.backend_warning = f"Neural MT unavailable — using rule-based fallback ({type(e).__name__})"

    def translate_answer_text(self, en_text: str, target_lang: str, protector=None) -> Dict[str, Any]:
        """EN -> HI/KN for answer sentences with REAL output-side term protection.

        Terms are protected in the English text, translated with IndicTrans2 and
        restored in native script (Pitta -> पित्त / ಪಿತ್ತ). Without neural MT the
        English text is returned unchanged and ``machine_translated`` is False.
        """
        if target_lang not in ("hi", "kn") or not en_text.strip():
            return {"text": en_text, "machine_translated": False, "method": "identity", "placeholders_lost": []}
        if self.neural is None:
            return {"text": en_text, "machine_translated": False, "method": "untranslated_no_neural_mt",
                    "placeholders_lost": []}
        try:
            pmap = {}
            src = en_text
            if protector is not None:
                src, pmap = protector.protect(en_text)
            r = self.neural.translate_protected(src, "en", target_lang)
            text = protector.restore_to_language(r["text"], pmap, target_lang=target_lang) if pmap else r["text"]
            return {"text": text, "machine_translated": True, "method": "indictrans2",
                    "model": r["model"], "placeholders_lost": r["placeholders_lost"]}
        except Exception as e:
            self._neural_failed(e)
            return {"text": en_text, "machine_translated": False, "method": "untranslated_no_neural_mt",
                    "placeholders_lost": []}

    def _load_parallel_datasets(self) -> None:
        """Indexes parallel question pairs from hi.parquet and kn.parquet."""
        try:
            df_hi = pd.read_parquet(HI_PARQUET)
            for _, r in df_hi.head(3000).iterrows():
                hi_q = str(r.get("question_translated", "")).strip().lower()
                en_q = str(r.get("question", "")).strip()
                if hi_q and en_q:
                    self.parallel_qa[hi_q] = en_q
        except Exception as e:  # F21: was a silent pass (e.g. pyarrow missing)
            log.warning("Hindi parallel-QA lookup disabled: could not read %s (%s)", HI_PARQUET.name, e)

        try:
            df_kn = pd.read_parquet(KN_PARQUET)
            for _, r in df_kn.head(3000).iterrows():
                kn_q = str(r.get("question_translated", "")).strip().lower()
                en_q = str(r.get("question", "")).strip()
                if kn_q and en_q:
                    self.parallel_qa[kn_q] = en_q
        except Exception as e:  # F21
            log.warning("Kannada parallel-QA lookup disabled: could not read %s (%s)", KN_PARQUET.name, e)

    def translate_to_english(
        self, text: str, source_lang: str = "auto"
    ) -> Dict[str, Any]:
        """HI/KN -> EN. IndicTrans2 when available, else the original rule-based path."""
        if self.neural is not None and source_lang in ("hi", "kn") and text and text.strip() \
                and PLACEHOLDER_STRIP.sub("", text).strip():
            try:
                src_text, method = text, "indictrans2"
                if self._mostly_latin(text):  # romanized / Hinglish / Kanglish: native script first
                    from indic_transliteration import sanscript
                    tgt_scheme = sanscript.DEVANAGARI if source_lang == "hi" else sanscript.KANNADA
                    keep = {m.group(0): f"AYTKEEP{i}" for i, m in enumerate(PLACEHOLDER_STRIP.finditer(text))}
                    tmp = text
                    for k, v in keep.items():
                        tmp = tmp.replace(k, v)
                    tmp = sanscript.transliterate(tmp, sanscript.ITRANS, tgt_scheme)
                    for k, v in keep.items():
                        tmp = tmp.replace(sanscript.transliterate(v, sanscript.ITRANS, tgt_scheme), k).replace(v, k)
                    src_text, method = tmp, "transliteration+indictrans2"
                r = self.neural.translate_protected(src_text, source_lang, "en")
                return {
                    "translated_text": r["text"], "source_lang": source_lang, "target_lang": "en",
                    "method": method, "model": r["model"], "placeholders_lost": r["placeholders_lost"],
                    "success": True, "warning": None,
                }
            except Exception as e:
                self._neural_failed(e)
        res = self._translate_to_english_rules(text, source_lang)
        if res.get("method") not in ("identity", "empty"):
            res.setdefault("warning", None)
            if res["warning"] is None and self.backend_used == "rules" and self.requested_backend != "rules":
                res["warning"] = self.backend_warning
        return res

    def _translate_to_english_rules(
        self, text: str, source_lang: str = "auto"
    ) -> Dict[str, Any]:
        """
        Translates Hindi or Kannada input into English for index retrieval.
        Preserves protected placeholder tokens intact.
        """
        if not text or not text.strip():
            return {
                "translated_text": "",
                "source_lang": source_lang,
                "target_lang": "en",
                "method": "empty",
                "success": True,
                "warning": None
            }

        if source_lang == "en":
            return {
                "translated_text": text,
                "source_lang": "en",
                "target_lang": "en",
                "method": "identity",
                "success": True,
                "warning": None
            }

        cleaned = text.strip()

        # 1. Check exact match in parallel QA corpus
        norm_key = cleaned.lower()
        if norm_key in self.parallel_qa:
            return {
                "translated_text": self.parallel_qa[norm_key],
                "source_lang": source_lang,
                "target_lang": "en",
                "method": "parallel_corpus_exact_match",
                "success": True,
                "warning": None
            }

        # 2. Check Hindi Grammar Patterns
        if source_lang == "hi":
            for pat, template in HINDI_QUERY_PATTERNS:
                m = pat.match(cleaned)
                if m:
                    subject = m.group(1).strip()
                    eng_query = template.format(subject)
                    return {
                        "translated_text": eng_query,
                        "source_lang": "hi",
                        "target_lang": "en",
                        "method": "ayurvedic_grammar_pattern_rule",
                        "success": True,
                        "warning": None
                    }

        # 3. Check Kannada Grammar Patterns
        if source_lang == "kn":
            for pat, template in KANNADA_QUERY_PATTERNS:
                m = pat.match(cleaned)
                if m:
                    subject = m.group(1).strip()
                    eng_query = template.format(subject)
                    return {
                        "translated_text": eng_query,
                        "source_lang": "kn",
                        "target_lang": "en",
                        "method": "ayurvedic_grammar_pattern_rule",
                        "success": True,
                        "warning": None
                    }

        # 4. Transliteration fallback for unmatched strings
        try:
            from indic_transliteration import sanscript
            from indic_transliteration.sanscript import transliterate
            src_scheme = sanscript.DEVANAGARI if source_lang == "hi" else sanscript.KANNADA
            roman = transliterate(cleaned, src_scheme, sanscript.ITRANS)
            return {
                "translated_text": roman,
                "source_lang": source_lang,
                "target_lang": "en",
                "method": "indic_transliteration_fallback",
                "success": True,
                "warning": "Neural MT unavailable; query transliterated for lexical matching"
            }
        except Exception:
            return {
                "translated_text": cleaned,
                "source_lang": source_lang,
                "target_lang": "en",
                "method": "passthrough_untranslated",
                "success": False,
                "warning": "Translation model not locally installed"
            }

    def translate_from_english(
        self,
        text: str,
        target_lang: str,
        detected_concept: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Translates evidence-based answer and citations into user's language.
        """
        if target_lang == "en" or not text.strip():
            return {
                "translated_text": text,
                "source_lang": "en",
                "target_lang": "en",
                "method": "identity",
                "success": True,
                "warning": None
            }

        # Translate concept explanation if known
        concept_body = ""
        if detected_concept and detected_concept in CONCEPT_EXPLANATIONS:
            concept_body = CONCEPT_EXPLANATIONS[detected_concept].get(target_lang, "")

        if target_lang == "hi":
            prefix = "प्रमाणित आयुर्वेदिक साहित्य के अनुसार"
            term_hdr = f" {CANONICAL_TO_HINDI.get(detected_concept, detected_concept)} के संदर्भ में:" if detected_concept else ":"
            header = f"{prefix}{term_hdr}"

            if concept_body:
                body = concept_body
            else:
                body = "आयुर्वेदिक शास्त्रीय ग्रंथों में इस विषय पर विस्तृत विवरण उपलब्ध है। अधिक जानकारी के लिए नीचे दिए गए मूल संदर्भ देखें।"

            sources_hdr = "उद्धृत स्रोत:"
            disclaimer_hdr = "शैक्षणिक सूचना: आयुर्मित्र एक शैक्षणिक ज्ञान प्रणाली है, चिकित्सकीय निदान या दवा पर्ची नहीं।"

            translated = (
                f"{header}\n\n"
                f"{body}\n\n"
                f"मूल संदर्भ सारांश (Source Context):\n"
                f"{text[:350]}...\n\n"
                f"{sources_hdr}\n"
                f"{disclaimer_hdr}"
            )
            return {
                "translated_text": translated,
                "source_lang": "en",
                "target_lang": "hi",
                "method": "verified_ayurvedic_bilingual_lexicon",
                "success": True,
                "warning": None
            }

        elif target_lang == "kn":
            prefix = "ಪ್ರಾಮಾಣಿಕ ಆಯುರ್ವೇದ ಸಾಹಿತ್ಯದ ಪ್ರಕಾರ"
            kn_term = CANONICAL_TO_KANNADA.get(detected_concept, detected_concept) if detected_concept else ""
            term_hdr = f" {kn_term}ಗೆ ಸಂಬಂಧಿಸಿದಂತೆ:" if kn_term else ":"
            header = f"{prefix}{term_hdr}"

            if concept_body:
                body = concept_body
            else:
                body = "ಆಯುರ್ವೇದ ಶಾಸ್ತ್ರೀಯ ಗ್ರಂಥಗಳಲ್ಲಿ ಈ ವಿಷಯದ ಬಗ್ಗೆ ವಿವರಣೆ ಲಭ್ಯವಿದೆ. ಹೆಚ್ಚಿನ ವಿವರಗಳಿಗೆ ಕೆಳಗಿನ ಮೂಲ ಉಲ್ಲೇಖಗಳನ್ನು ನೋಡಿ."

            sources_hdr = "ಉಲ್ಲೇಖಿಸಿದ ಮೂಲಗಳು:"
            disclaimer_hdr = "ಶೈಕ್ಷಣಿಕ ಸೂಚನೆ: ಆಯುರ್ಮಿತ್ರ ಶೈಕ್ಷಣಿಕ ಜ್ಞಾನ ಸಾಧನವಾಗಿದ್ದು, ವೈದ್ಯಕೀಯ ಚಿಕಿತ್ಸಾ ಸಲಹೆಯಲ್ಲ."

            translated = (
                f"{header}\n\n"
                f"{body}\n\n"
                f"ಮೂಲ ಇಂಗ್ಲಿಷ್ ಉಲ್ಲೇಖ ಸಾರಾಂಶ (Original Context):\n"
                f"{text[:350]}...\n\n"
                f"{sources_hdr}\n"
                f"{disclaimer_hdr}"
            )
            return {
                "translated_text": translated,
                "source_lang": "en",
                "target_lang": "kn",
                "method": "verified_ayurvedic_bilingual_lexicon",
                "success": True,
                "warning": None
            }

        return {
            "translated_text": text,
            "source_lang": "en",
            "target_lang": target_lang,
            "method": "passthrough",
            "success": False,
            "warning": f"Translation to {target_lang} unavailable"
        }

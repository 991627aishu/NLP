"""
AyurMitra — Multilingual & Code-Mixed Language Identification
=============================================================
Accurately detects scripts, language segments, and code-mixing in user inputs:
  - Native Devanagari script (Hindi, Sanskrit)
  - Native Kannada script
  - Latin script English (with Ayurvedic domain terminology protection)
  - Romanized Hindi (Hinglish)
  - Romanized Kannada (Kanglish)
  - Code-mixed sentences (e.g., English + Hindi Devanagari, English + Kannada,
    or Trilingual English + Hindi + Kannada)

Provides segment-level provenance, exposes uncertainty, and prevents false
classification of English sentences containing Ayurvedic terms.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# ── Unicode Script Ranges ─────────────────────────────────────────────────────
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")     # Devanagari (Hindi, Sanskrit)
_KANNADA    = re.compile(r"[\u0C80-\u0CFF]")     # Kannada
_LATIN      = re.compile(r"[A-Za-z]")

# ── High-frequency English functional words (Grammatical particles & closed-class words) ──
ENGLISH_FUNCTIONAL_WORDS = {
    "what", "are", "the", "of", "and", "in", "is", "how", "why", "which",
    "tell", "me", "does", "do", "can", "for", "with", "from", "to", "according",
    "role", "functions", "symptoms", "treatment", "causes", "give", "about",
    "explain", "describe", "meaning", "definition", "should", "could", "would",
    "i", "have", "has", "had", "my", "am", "after", "when", "with", "been",
    "between", "difference", "concept", "lifestyle", "modern", "literature"
}

# ── Romanized Functional Word Dictionaries (Grammar / Particles Only) ────────
HINDI_ROMAN_GRAMMAR = {
    "kya", "kyon", "kaise", "kab", "kahan", "hai", "hain", "ke", "ki", "ka",
    "ko", "se", "mein", "aur", "hota", "hoti", "hote", "karein", "karna",
    "chahiye", "kuch", "upay", "ilaaj", "batao", "bataiye", "samasya", "theek",
    "kaunsa", "kaunsi", "mera", "meri", "mere", "liye", "mujhe", "mujhko",
    "bahut", "bohot", "dard", "sirdard", "sir", "nahi", "ho", "raha", "rahi",
    "rahe", "lag", "lagta", "lagti", "lagte", "pet", "jalan", "sujan", "tez",
    "bhayankar", "aata", "aati", "chakar", "chakkar", "agar", "kamzor", "me"
}

KANNADA_ROMAN_GRAMMAR = {
    "yavudu", "yavuvu", "yava", "enu", "hege", "elli", "yaake", "agutte",
    "aguvudu", "maduvudu", "ide", "illa", "beku", "inda", "alli", "alliye",
    "lakshanagalu", "yenu", "hegidhe", "karyagalu", "bagge", "thondare",
    "nanage", "nanna", "yavagalu", "chikitse", "tumba", "matte", "novu",
    "tale", "talenovu", "telenovu", "agide", "aguttide", "churuku", "uri",
    "charma", "keelu", "hasiyu", "oota", "nidde", "kasta", "bahaala",
    "tivra", "thivra", "aadaga", "maadodu", "maaduvudu"
}


def segment_text_by_script(text: str) -> List[Dict[str, str]]:
    """
    Splits text into contiguous script segments (Devanagari, Kannada, Latin, Other).
    """
    if not text:
        return []

    segments = []
    current_script = None
    current_chars = []

    for char in text:
        if _DEVANAGARI.match(char):
            script = "devanagari"
        elif _KANNADA.match(char):
            script = "kannada"
        elif _LATIN.match(char):
            script = "latin"
        else:
            script = "other"

        if current_script is None:
            current_script = script
            current_chars.append(char)
        elif script == current_script or script == "other":
            current_chars.append(char)
        elif current_script == "other":
            current_script = script
            current_chars.append(char)
        else:
            seg_str = "".join(current_chars).strip()
            if seg_str:
                segments.append({"text": seg_str, "script": current_script})
            current_script = script
            current_chars = [char]

    if current_chars:
        seg_str = "".join(current_chars).strip()
        if seg_str:
            segments.append({"text": seg_str, "script": current_script})

    return segments


def detect(text: str) -> Dict[str, Any]:
    """
    Detect the language, script, code-mixing status, and segment breakdown of `text`.

    Returns dict:
      - lang: dominant language code ("en", "hi", "kn", "unknown")
      - dominant_lang: same as lang
      - script: primary script ("devanagari", "kannada", "latin", "mixed")
      - is_romanized: bool (True for Hinglish/Kanglish)
      - is_code_mixed: bool (True if multi-script or multi-language)
      - code_mix_type: str ("monolingual", "english_hindi", "english_kannada", "trilingual", etc.)
      - detected_languages: List[str]
      - segments: List[Dict] with segment-level language and script
      - confidence: float (0.0 to 1.0)
      - confidence_level: str ("high", "moderate", "uncertain")
      - method: str
    """
    if not text or not text.strip():
        return {
            "lang": "unknown",
            "dominant_lang": "unknown",
            "script": "unknown",
            "is_romanized": False,
            "is_code_mixed": False,
            "code_mix_type": "empty",
            "detected_languages": [],
            "segments": [],
            "confidence": 0.0,
            "confidence_level": "uncertain",
            "method": "empty_input"
        }

    cleaned = text.strip()
    dev_chars = len(_DEVANAGARI.findall(cleaned))
    kn_chars  = len(_KANNADA.findall(cleaned))
    lat_chars = len(_LATIN.findall(cleaned))
    total_letters = dev_chars + kn_chars + lat_chars or 1

    dev_ratio = dev_chars / total_letters
    kn_ratio  = kn_chars / total_letters
    lat_ratio = lat_chars / total_letters

    raw_segments = segment_text_by_script(cleaned)
    classified_segments = []
    detected_languages = set()

    for seg in raw_segments:
        s_text = seg["text"]
        s_script = seg["script"]
        if s_script == "devanagari":
            classified_segments.append({
                "text": s_text, "script": "devanagari", "lang": "hi", "confidence": 0.98
            })
            detected_languages.add("hi")
        elif s_script == "kannada":
            classified_segments.append({
                "text": s_text, "script": "kannada", "lang": "kn", "confidence": 0.98
            })
            detected_languages.add("kn")
        elif s_script == "latin":
            # Differentiate Latin sub-segment
            words = set(re.findall(r"\b[A-Za-z]+\b", s_text.lower()))
            en_cnt = len(words.intersection(ENGLISH_FUNCTIONAL_WORDS))
            hi_cnt = len(words.intersection(HINDI_ROMAN_GRAMMAR))
            kn_cnt = len(words.intersection(KANNADA_ROMAN_GRAMMAR))

            if kn_cnt > 0 and kn_cnt > en_cnt and kn_cnt >= hi_cnt:
                classified_segments.append({
                    "text": s_text, "script": "latin", "lang": "kn", "is_romanized": True, "confidence": 0.85
                })
                detected_languages.add("kn")
            elif hi_cnt > 0 and hi_cnt > en_cnt:
                classified_segments.append({
                    "text": s_text, "script": "latin", "lang": "hi", "is_romanized": True, "confidence": 0.85
                })
                detected_languages.add("hi")
            else:
                classified_segments.append({
                    "text": s_text, "script": "latin", "lang": "en", "is_romanized": False, "confidence": 0.92
                })
                detected_languages.add("en")

    # Determine code-mixing
    is_code_mixed = len(detected_languages) > 1 or (dev_chars > 0 and kn_chars > 0) or (dev_chars > 0 and lat_chars > 0) or (kn_chars > 0 and lat_chars > 0)

    # Differentiate code-mixing category
    if len(detected_languages) >= 3 or (dev_chars > 0 and kn_chars > 0 and lat_chars > 0):
        code_mix_type = "trilingual_mixed"
    elif "en" in detected_languages and "hi" in detected_languages:
        code_mix_type = "english_hindi_codemixed"
    elif "en" in detected_languages and "kn" in detected_languages:
        code_mix_type = "english_kannada_codemixed"
    elif "hi" in detected_languages and "kn" in detected_languages:
        code_mix_type = "hindi_kannada_codemixed"
    elif len(detected_languages) == 1 and list(detected_languages)[0] == "hi" and lat_ratio > 0.5:
        code_mix_type = "hinglish_romanized"
    elif len(detected_languages) == 1 and list(detected_languages)[0] == "kn" and lat_ratio > 0.5:
        code_mix_type = "kanglish_romanized"
    else:
        code_mix_type = "monolingual"

    # Resolve Dominant Language
    words_all = set(re.findall(r"\b[A-Za-z]+\b", cleaned.lower()))
    en_cnt = len(words_all.intersection(ENGLISH_FUNCTIONAL_WORDS))
    hi_cnt = len(words_all.intersection(HINDI_ROMAN_GRAMMAR))
    kn_cnt = len(words_all.intersection(KANNADA_ROMAN_GRAMMAR))

    is_romanized = False

    if kn_ratio > 0.40 or (kn_chars > 0 and kn_chars >= dev_chars and en_cnt == 0):
        dominant_lang = "kn"
        primary_script = "kannada" if not is_code_mixed else "mixed"
        method = "kannada_script_dominant"
        confidence = round(min(0.85 + kn_ratio * 0.15, 0.99), 2)
    elif dev_ratio > 0.40 or (dev_chars > 0 and dev_chars >= kn_chars and en_cnt == 0):
        dominant_lang = "hi"
        primary_script = "devanagari" if not is_code_mixed else "mixed"
        method = "devanagari_script_dominant"
        confidence = round(min(0.85 + dev_ratio * 0.15, 0.99), 2)
    elif en_cnt > 0 and en_cnt >= hi_cnt and en_cnt >= kn_cnt:
        dominant_lang = "en"
        primary_script = "latin" if not (dev_chars > 0 or kn_chars > 0) else "mixed"
        method = "english_functional_grammar"
        confidence = 0.92 if not is_code_mixed else 0.85
    elif kn_cnt > 0 and kn_cnt > en_cnt and kn_cnt >= hi_cnt:
        dominant_lang = "kn"
        primary_script = "latin" if kn_chars == 0 else "mixed"
        is_romanized = True
        method = "romanized_kannada_grammar"
        confidence = 0.85
    elif hi_cnt > 0 and hi_cnt > en_cnt:
        dominant_lang = "hi"
        primary_script = "latin" if dev_chars == 0 else "mixed"
        is_romanized = True
        method = "romanized_hindi_grammar"
        confidence = 0.85
    elif kn_chars > 0:
        dominant_lang = "kn"
        primary_script = "mixed" if lat_chars > 0 else "kannada"
        method = "kannada_script_segment"
        confidence = 0.82
    elif dev_chars > 0:
        dominant_lang = "hi"
        primary_script = "mixed" if lat_chars > 0 else "devanagari"
        method = "devanagari_script_segment"
        confidence = 0.82
    else:
        dominant_lang = "en"
        primary_script = "latin"
        method = "latin_default_english"
        confidence = 0.80

    conf_level = "high" if confidence >= 0.88 else ("moderate" if confidence >= 0.70 else "uncertain")

    return {
        "lang": dominant_lang,
        "dominant_lang": dominant_lang,
        "script": primary_script,
        "is_romanized": is_romanized,
        "is_code_mixed": is_code_mixed,
        "code_mix_type": code_mix_type,
        "detected_languages": sorted(list(detected_languages)) if detected_languages else [dominant_lang],
        "segments": classified_segments,
        "confidence": confidence,
        "confidence_level": conf_level,
        "method": method
    }


def classify_input_type(text: str) -> str:
    """Convenience string classifier for logging."""
    res = detect(text)
    if res["is_code_mixed"]:
        return res["code_mix_type"]
    if res["lang"] == "kn":
        return "romanized_kannada" if res["is_romanized"] else "native_kannada"
    if res["lang"] == "hi":
        return "romanized_hindi" if res["is_romanized"] else "native_hindi"
    if res["lang"] == "en":
        return "english"
    return "unknown"

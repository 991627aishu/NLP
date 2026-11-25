"""
Text preparation for speech (Phase 5)
=====================================
* ``clean_for_tts`` — strip markdown, citation IDs, URLs, locators and the Sources
  section; read canonical terms in native script for HI/KN (Pitta -> पित्त / ಪಿತ್ತ);
  append the short spoken disclaimer once.
* ``chunk_for_tts`` — split into <= 800-character chunks at sentence boundaries.
* ``normalize_transcript_terms`` — fix common STT spellings of Ayurvedic terms
  ("vaata", "kapa", "pita"), only when the transcript has Ayurvedic context
  (e.g. Hindi "pita" = father must not become Pitta). Every change is logged.
"""
from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List

from app.core.matcher import CANONICAL_TO_HINDI, CANONICAL_TO_KANNADA

SPOKEN_DISCLAIMER = {
    "en": "AyurMitra is for education only and is not medical advice.",
    "hi": "आयुर्मित्र केवल शैक्षिक जानकारी देता है, यह चिकित्सकीय सलाह नहीं है।",
    "kn": "ಆಯುರ್ಮಿತ್ರ ಕೇವಲ ಶೈಕ್ಷಣಿಕ ಮಾಹಿತಿ ನೀಡುತ್ತದೆ, ಇದು ವೈದ್ಯಕೀಯ ಸಲಹೆಯಲ್ಲ.",
    "hinglish": "AyurMitra keval educational information deta hai, ye medical advice nahi hai.",
    "kanglish": "AyurMitra kevala educational information needutte, idu medical advice alla.",
}

_ID_RX = re.compile(r"\b(WHO_CHUNK|QA_PASSAGE|HI_QA|KN_QA|NAMASTE_CHUNK|IMPPAT_\w*|API_\w*|CHUNK)_?[A-Z0-9_]*\d+\b")
_TERM_ID_RX = re.compile(r"\b(ITA-[\d.]+|SAT-A[\d.]*|IMPPAT3_\w+|API\d{6})\b")
_SECTION_DROP = re.compile(r"\*\*(Sources|Ayurvedic terms|Evidence limitation)[^*]*\*\*.*?(?=\n\*\*|\Z)", re.S)


def clean_for_tts(text: str, lang: str = "en", add_disclaimer: bool = True) -> str:
    """Clean markdown/URLs/IDs for natural speech while preserving the entire displayed response."""
    t = text or ""
    t = re.sub(r"\[Glossary note[^\]]*\]", " ", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", t)          # markdown links -> label
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"\[[^\]]*(CHUNK|PASSAGE|QA_|ITA-|SAT-A)[^\]]*\]", " ", t)  # [WHO_CHUNK_0001]
    t = _ID_RX.sub(" ", t)
    t = _TERM_ID_RX.sub(" ", t)
    t = re.sub(r"\b(PDF )?p(age)?s?\.?\s?\d+(\s?[-–]\s?\d+)?\b", " ", t, flags=re.I)
    t = re.sub(r"\(printed[^)]*\)", " ", t)
    t = re.sub(r"[*#>_|]+", " ", t)
    t = re.sub(r"^\s*[-•]\s*", "", t, flags=re.M)
    t = t.replace("->", ", ").replace("→", ", ")
    t = re.sub(r"\s+([,.;:!?।])", r"\1", t)
    t = re.sub(r"([,;:])\1+", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip(" ,;")
    if add_disclaimer:
        disc = SPOKEN_DISCLAIMER.get(lang, SPOKEN_DISCLAIMER["en"])
        if disc not in t:
            t = (t + " " + disc).strip()
    return t


def chunk_for_tts(text: str, max_chars: int = 800) -> List[str]:
    sentences = re.split(r"(?<=[.!?।])\s+", (text or "").strip())
    chunks, cur = [], ""
    for s in sentences:
        while len(s) > max_chars:  # very long sentence: hard split at a space
            cut = s.rfind(" ", 0, max_chars) or max_chars
            chunks.append(s[:cut].strip())
            s = s[cut:].strip()
        if len(cur) + len(s) + 1 > max_chars and cur:
            chunks.append(cur.strip())
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return [c for c in chunks if c]


# ── STT post-normalisation ───────────────────────────────────────────────────
_CANONICAL = sorted(set(CANONICAL_TO_HINDI) | set(CANONICAL_TO_KANNADA))
_CONTEXT_CUES = {"dosha", "dosa", "ayurveda", "ayurvedic", "ayurved", "vata", "pitta", "kapha", "agni", "prakriti",
                 "imbalance", "aggravated", "symptoms", "lakshan", "lakshana", "dhatu", "ojas", "ama", "tridosha"}
_COMMON_WORDS = {"pita", "mata", "rasa", "kasa", "nadi", "meda", "ama"}  # real words in Hindi/English; need context
_STT_VARIANTS = {"vaata": "Vata", "vatha": "Vata", "baat": None, "pitha": "Pitta", "pita": "Pitta", "pith": "Pitta",
                 "kapa": "Kapha", "kafa": "Kapha", "kaffa": "Kapha", "cough a": None, "agnee": "Agni",
                 "ojus": "Ojas", "doshaa": "Dosha", "dosa": "Dosha", "prakruti": "Prakriti", "dhaatu": "Dhatu"}


def normalize_transcript_terms(text: str) -> Dict[str, Any]:
    words = re.findall(r"[A-Za-z]+|[^A-Za-z]+", text or "")
    lower_words = {w.lower() for w in words if w.isalpha()}
    has_context = bool(lower_words & _CONTEXT_CUES)
    corrections, out = [], []
    for w in words:
        if not w.isalpha() or len(w) < 3:
            out.append(w)
            continue
        lw = w.lower()
        target = _STT_VARIANTS.get(lw)
        if target is None and lw not in _COMMON_WORDS:
            m = difflib.get_close_matches(lw, [c.lower() for c in _CANONICAL], n=1, cutoff=0.8)
            target = next((c for c in _CANONICAL if m and c.lower() == m[0]), None)
        if target and target.lower() != lw:
            if lw in _COMMON_WORDS:  # real everyday words ("pita" = father) need Ayurvedic context
                if not has_context:
                    out.append(w)
                    continue
            corrections.append({"from": w, "to": target})
            out.append(target)
        else:
            out.append(w)
    return {"text": "".join(out), "corrections": corrections, "context_detected": has_context}

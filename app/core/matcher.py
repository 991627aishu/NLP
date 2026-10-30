"""
AyurMitra — Terminology Matcher & Canonicalizer
================================================
Detects Ayurvedic domain terms in multilingual text (English, Hindi, Kannada,
and Romanized/code-mixed variants), returning canonical concept IDs, canonical
terms, and text spans.

Handles:
- Exact and case-insensitive matching.
- Multilingual term dictionaries (Devanagari, Kannada script).
- Common Kannada inflectional suffixes (e.g., -ದ [genitive], -ಕ್ಕೆ [dative],
  -ದಲ್ಲಿ [locative], -ವನ್ನು [accusative], -ಗಳು [plural]).
- Longest-match prioritization for multi-word terms (e.g., "pitta dosha" over "pitta").
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from app.config import TERMINOLOGY_JSON

# ── Multilingual seed mappings (Script-level canonical mapping) ───────────────
# Hindi (Devanagari) to Canonical
HINDI_TERM_MAP: Dict[str, str] = {
    "वात": "Vata",
    "वायु": "Vata",
    "पित्त": "Pitta",
    "कफ": "Kapha",
    "श्लेष्मा": "Kapha",
    "अग्नि": "Agni",
    "जठराग्नि": "Agni",
    "प्रकृति": "Prakriti",
    "धातु": "Dhatu",
    "दोष": "Dosha",
    "ओजस": "Ojas",
    "ओज": "Ojas",
    "प्राण": "Prana",
    "त्रिदोष": "Tridosha",
    "आम": "Ama",
    "रसायन": "Rasayana",
    "पंचकर्म": "Panchakarma",
    "स्रोतस": "Srotas",
    "नाड़ी": "Nadi",
    "रस": "Rasa",
    "रक्त": "Rakta",
    "मांस": "Mamsa",
    "मेद": "Meda",
    "अस्थि": "Asthi",
    "मज्जा": "Majja",
    "शुक्र": "Shukra",
    "अश्वगंधा": "Ashwagandha",
    "त्रिफला": "Triphala",
    "तुलसी": "Tulsi",
    "नीम": "Neem",
    "गुग्गुल": "Guggulu",
    "ब्राह्मी": "Brahmi",
    "शतावरी": "Shatavari",
    "हरीतकी": "Haritaki",
    "आमलकी": "Amalaki",
    "बिभीतकी": "Bibhitaki",
    "गुल्म": "Gulma",
    "अर्श": "Arsha",
    "कास": "Kasa",
    "श्वास": "Shwasa",
    "ज्वर": "Jwara",
    "प्रमेह": "Prameha",
}

# Kannada script to Canonical
KANNADA_TERM_MAP: Dict[str, str] = {
    "ವಾತ": "Vata",
    "ವಾಯು": "Vata",
    "ಪಿತ್ತ": "Pitta",
    "ಕಫ": "Kapha",
    "ಶ್ಲೇಷ್ಮ": "Kapha",
    "ಅಗ್ನಿ": "Agni",
    "ಜಠರಾಗ್ನಿ": "Agni",
    "ಪ್ರಕೃತಿ": "Prakriti",
    "ಧಾತು": "Dhatu",
    "ದೋಷ": "Dosha",
    "ಓಜಸ್ಸು": "Ojas",
    "ಓಜಸ್": "Ojas",
    "ಪ್ರಾಣ": "Prana",
    "ತ್ರಿದೋಷ": "Tridosha",
    "ಆಮ": "Ama",
    "ರಸಾಯನ": "Rasayana",
    "ಪಂಚಕರ್ಮ": "Panchakarma",
    "ಸ್ರೋತಸ್": "Srotas",
    "ನಾಡಿ": "Nadi",
    "ರಸ": "Rasa",
    "ರಕ್ತ": "Rakta",
    "ಮಾಂಸ": "Mamsa",
    "ಮೇದಸ್ಸು": "Meda",
    "ಅಸ್ಥಿ": "Asthi",
    "ಮಜ್ಜ": "Majja",
    "ಶುಕ್ರ": "Shukra",
    "ಅಶ್ವಗಂಧ": "Ashwagandha",
    "ತ್ರಿಫಲ": "Triphala",
    "ತುಳಸಿ": "Tulsi",
    "ಬೇವಿನ": "Neem",
    "ಬೇವು": "Neem",
    "ಬ್ರಾಹ್ಮಿ": "Brahmi",
    "ಶತಾವರಿ": "Shatavari",
    "ಆಮಲಕಿ": "Amalaki",
    "ಹರೀತಕಿ": "Haritaki",
    "ಜ್ವರ": "Jwara",
    "ಪ್ರಮೇಹ": "Prameha",
    "ಕಾಸ": "Kasa",
    "ಶ್ವಾಸ": "Shwasa",
}

# Canonical to Hindi (Devanagari)
CANONICAL_TO_HINDI: Dict[str, str] = {
    "Vata": "वात",
    "Pitta": "पित्त",
    "Kapha": "कफ",
    "Agni": "अग्नि",
    "Prakriti": "प्रकृति",
    "Dhatu": "धातु",
    "Dosha": "दोष",
    "Ojas": "ओजस",
    "Prana": "प्राण",
    "Tridosha": "त्रिदोष",
    "Ama": "आम",
    "Rasayana": "रसायन",
    "Panchakarma": "पंचकर्म",
    "Srotas": "स्रोतस",
    "Nadi": "नाड़ी",
    "Rasa": "रस",
    "Rakta": "रक्त",
    "Mamsa": "मांस",
    "Meda": "मेद",
    "Asthi": "अस्थि",
    "Majja": "मज्जा",
    "Shukra": "शुक्र",
    "Ashwagandha": "अश्वगंधा",
    "Triphala": "त्रिफला",
    "Tulsi": "तुलसी",
    "Neem": "नीम",
    "Guggulu": "गुग्गुल",
    "Brahmi": "ब्राह्मी",
    "Shatavari": "शतावरी",
    "Haritaki": "हरीतकी",
    "Amalaki": "आमलकी",
    "Bibhitaki": "बिभीतकी",
    "Jwara": "ज्वर",
    "Prameha": "प्रमेह",
    "Kasa": "कास",
    "Shwasa": "श्वास",
    "Pitta Dosha": "पित्त दोष",
    "Vata Dosha": "वात दोष",
    "Kapha Dosha": "कफ दोष",
}

# Canonical to Kannada script
CANONICAL_TO_KANNADA: Dict[str, str] = {
    "Vata": "ವಾತ",
    "Pitta": "ಪಿತ್ತ",
    "Kapha": "ಕಫ",
    "Agni": "ಅಗ್ನಿ",
    "Prakriti": "ಪ್ರಕೃತಿ",
    "Dhatu": "ಧಾತು",
    "Dosha": "ದೋಷ",
    "Ojas": "ಓಜಸ್ಸು",
    "Prana": "ಪ್ರಾಣ",
    "Tridosha": "ತ್ರಿದೋಷ",
    "Ama": "ಆಮ",
    "Rasayana": "ರಸಾಯನ",
    "Panchakarma": "ಪಂಚಕರ್ಮ",
    "Srotas": "ಸ್ರೋತಸ್",
    "Nadi": "ನಾಡಿ",
    "Rasa": "ರಸ",
    "Rakta": "ರಕ್ತ",
    "Mamsa": "ಮಾಂಸ",
    "Meda": "ಮೇದಸ್ಸು",
    "Asthi": "ಅಸ್ಥಿ",
    "Majja": "ಮಜ್ಜ",
    "Shukra": "ಶುಕ್ರ",
    "Ashwagandha": "ಅಶ್ವಗಂಧ",
    "Triphala": "ತ್ರಿಫಲ",
    "Tulsi": "ತುಳಸಿ",
    "Neem": "ಬೇವು",
    "Brahmi": "ಬ್ರಾಹ್ಮಿ",
    "Shatavari": "ಶತಾವರಿ",
    "Amalaki": "ಆಮಲಕಿ",
    "Haritaki": "ಹರೀತಕಿ",
    "Jwara": "ಜ್ವರ",
    "Prameha": "ಪ್ರಮೇಹ",
    "Kasa": "ಕಾಸ",
    "Shwasa": "ಶ್ವಾಸ",
    "Pitta Dosha": "ಪಿತ್ತ ದೋಷ",
    "Vata Dosha": "ವಾತ ದೋಷ",
    "Kapha Dosha": "ಕಫ ದೋಷ",
}

# Common Romanized spelling variants and transliterations
ROMAN_SPELLING_VARIANTS: Dict[str, str] = {
    "vatha": "Vata",
    "vaata": "Vata",
    "vaat": "Vata",
    "vata": "Vata",
    "vat": "Vata",
    "pitham": "Pitta",
    "pitha": "Pitta",
    "pittha": "Pitta",
    "pitt": "Pitta",
    "pitta": "Pitta",
    "kapham": "Kapha",
    "kafa": "Kapha",
    "kaph": "Kapha",
    "kuff": "Kapha",
    "aagny": "Agni",
    "aagnee": "Agni",
    "aagani": "Agni",
    "agni": "Agni",
    "prakruthi": "Prakriti",
    "prakruti": "Prakriti",
    "prakriti": "Prakriti",
    "dhaatu": "Dhatu",
    "dhaathus": "Dhatu",
    "dhatu": "Dhatu",
    "dhatus": "Dhatu",
    "oajas": "Ojas",
    "ozas": "Ojas",
    "ojas": "Ojas",
    "ojus": "Ojas",
    "tridosha": "Tridosha",
    "thridosha": "Tridosha",
    "thridhosha": "Tridosha",
    "tridoshas": "Tridosha",
    "rasayana": "Rasayana",
    "rasayanam": "Rasayana",
    "panchakarma": "Panchakarma",
    "panchakarmaa": "Panchakarma",
    "aama": "Ama",
    "ashwagandha": "Ashwagandha",
    "aswagandha": "Ashwagandha",
    "ashwagandhar": "Ashwagandha",
    "triphala": "Triphala",
    "thriphala": "Triphala",
    "tulsi": "Tulsi",
    "thulasi": "Tulsi",
    "shatavari": "Shatavari",
    "shathavari": "Shatavari",
    "brahmi": "Brahmi",
    "brahmee": "Brahmi",
    "haritaki": "Haritaki",
    "amalaki": "Amalaki",
    "amla": "Amalaki",
    "bibhitaki": "Bibhitaki",
    "guggulu": "Guggulu",
    "guggul": "Guggulu",
}

# Everyday English and grammatical Hindi/Kannada words that must never be
# matched as standalone technical terms (preventing false protection)
DISALLOWED_PLAIN_WORDS = {
    "box", "time", "deep", "five", "pre", "post", "bulk", "non", "ita",
    "karta", "karte", "karti", "kare", "karna", "hai", "hain", "hoga", "raha", "rahe",
    "cough", "blood", "pulse", "tissue", "nerve", "muscle", "bone", "fat", "plasma",
    "lymph", "toxin", "humor", "channels", "body", "health", "water", "food"
}

# Common Kannada noun suffixes to strip for root term recovery
KANNADA_SUFFIXES = [
    "ನಲ್ಲಿ", "ರಲ್ಲಿ",  # Locative
    "ವನ್ನು", "ಅನ್ನು",  # Accusative
    "ಯಿಂದ", "ದಿಂದ",  # Instrumental / Ablative
    "ಕ್ಕೆ", "ಗೆ", "ಇಗೆ",  # Dative
    "ದ", "ಯ", "ನ",      # Genitive
    "ಗಳು", "ಗಳಲ್ಲಿ",    # Plural / Plural locative
    "ವಾದ", "ವಾಗಿ",      # Adverbial
]

def _normalize_latin(text: str) -> str:
    """Normalize Latin text by lowercasing and stripping diacritics."""
    norm = unicodedata.normalize("NFKD", text)
    cleaned = "".join(c for c in norm if not unicodedata.combining(c))
    return re.sub(r"[^\w\s]", " ", cleaned).lower().strip()


class TerminologyMatcher:
    """Matches text against Ayurvedic terminology inventories."""

    def __init__(self, inventory_path: Optional[str] = None):
        self.inventory: Dict[str, Dict[str, Any]] = {}
        self.latin_lookup: Dict[str, str] = {}
        self.hindi_lookup: Dict[str, str] = dict(HINDI_TERM_MAP)
        self.kannada_lookup: Dict[str, str] = dict(KANNADA_TERM_MAP)
        self._load_inventory(inventory_path)

    def _load_inventory(self, path: Optional[str] = None) -> None:
        # Seed Latin lookup with verified spelling variants
        for variant, canon in ROMAN_SPELLING_VARIANTS.items():
            norm_v = _normalize_latin(variant)
            if norm_v:
                self.latin_lookup[norm_v] = canon

        p = path or TERMINOLOGY_JSON
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                cid = item.get("concept_id", "")
                canon = item.get("canonical_term", "")
                if not canon:
                    continue
                self.inventory[canon] = item
                # Add to Latin lookup (guarding against plain everyday words)
                norm_c = _normalize_latin(canon)
                if norm_c and norm_c.lower() not in DISALLOWED_PLAIN_WORDS:
                    self.latin_lookup[norm_c] = canon
                for alias in item.get("aliases", []):
                    norm_a = _normalize_latin(alias)
                    if norm_a and norm_a.lower() not in DISALLOWED_PLAIN_WORDS:
                        self.latin_lookup[norm_a] = canon
        except Exception as e:
            # Fall back to internal basic inventory if file not yet present
            pass

    def match_kannada_word(self, word: str) -> Optional[str]:
        """Attempt exact match or suffix-stripped match for a Kannada word."""
        if word in self.kannada_lookup:
            return self.kannada_lookup[word]
        # Try stripping suffixes
        for suffix in KANNADA_SUFFIXES:
            if word.endswith(suffix) and len(word) > len(suffix) + 1:
                stem = word[:-len(suffix)]
                if stem in self.kannada_lookup:
                    return self.kannada_lookup[stem]
        return None

    def find_terms(self, text: str) -> List[Dict[str, Any]]:
        """
        Locate all Ayurvedic terms in text.
        Returns sorted list of match dictionaries:
          {
            "canonical_term": str,
            "matched_text": str,
            "start": int,
            "end": int,
            "concept_id": str,
            "script": str,
            "ambiguity_note": str
          }
        """
        if not text:
            return []

        matches: List[Dict[str, Any]] = []

        # 1. Check Hindi (Devanagari) terms
        for term, canon in sorted(self.hindi_lookup.items(), key=lambda x: -len(x[0])):
            for m in re.finditer(re.escape(term), text):
                inv_meta = self.inventory.get(canon, {})
                matches.append({
                    "canonical_term": canon,
                    "matched_text": m.group(0),
                    "start": m.start(),
                    "end": m.end(),
                    "concept_id": inv_meta.get("concept_id", f"CID_{canon}"),
                    "script": "Devanagari",
                    "ambiguity_note": inv_meta.get("ambiguity_note", "")
                })

        # 2. Check Kannada terms and inflected forms
        # Tokenize by whitespace and punctuation for Kannada
        kn_pattern = re.compile(r"[\u0C80-\u0CFF]+")
        for m in kn_pattern.finditer(text):
            word = m.group(0)
            canon = self.match_kannada_word(word)
            if canon:
                inv_meta = self.inventory.get(canon, {})
                matches.append({
                    "canonical_term": canon,
                    "matched_text": word,
                    "start": m.start(),
                    "end": m.end(),
                    "concept_id": inv_meta.get("concept_id", f"CID_{canon}"),
                    "script": "Kannada",
                    "ambiguity_note": inv_meta.get("ambiguity_note", "")
                })

        # 3. Check Latin / Romanized terms (multi-word first)
        norm_text = text.lower()
        # Sort terms by length descending to match multi-words first
        sorted_latin = sorted(self.latin_lookup.items(), key=lambda x: -len(x[0]))
        for alias, canon in sorted_latin:
            if len(alias) < 3 or alias.lower() in DISALLOWED_PLAIN_WORDS:
                continue  # skip extremely short words and disallowed everyday words
            # Use word boundaries for Latin
            pattern = re.compile(r"\b" + re.escape(alias) + r"\b", re.IGNORECASE)
            for m in pattern.finditer(text):
                inv_meta = self.inventory.get(canon, {})
                matches.append({
                    "canonical_term": canon,
                    "matched_text": m.group(0),
                    "start": m.start(),
                    "end": m.end(),
                    "concept_id": inv_meta.get("concept_id", f"CID_{canon}"),
                    "script": "Latin",
                    "ambiguity_note": inv_meta.get("ambiguity_note", "")
                })

        # Resolve overlapping spans: sort by start, then by length descending
        matches.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
        non_overlapping: List[Dict[str, Any]] = []
        last_end = -1
        for match in matches:
            if match["start"] >= last_end:
                non_overlapping.append(match)
                last_end = match["end"]

        return non_overlapping


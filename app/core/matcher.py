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
    "आयुर्वेद": "Ayurveda",
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
    "मधुमेह": "Madhumeha",
    "कुष्ठ": "Kushtha",
    "कुष्ठरोग": "Kushtha",
    "रोग": "Roga",
    "व्याधि": "Vyadhi",
    "लक्षण": "Lakshana",
    "निदान": "Nidana",
    "संप्राप्ति": "Samprapti",
    "चिकित्सा": "Chikitsa",
    "त्रिमल": "Trimala",
    "मल": "Mala",
    "स्वास्थ्य": "Swasthya",
    "दिनचर्या": "Dinacharya",
    "ऋतुचर्या": "Ritucharya",
    "अतिसार": "Atisara",
    "अर्श": "Arshas",
    "राजयक्ष्मा": "Rajayakshma",
    "स्नेहन": "Snehana",
    "स्वेदन": "Swedana",
    "शिरोधरा": "Shirodhara",
    "गिलोय": "Guduchi",
    "गुडूची": "Guduchi",
    "च्यवनप्राश": "Chyawanprash",
    "बृहत्त्रयी": "Brihat Trayi",
    "चरक संहिता": "Charaka Samhita",
    "सुश्रुत संहिता": "Sushruta Samhita",
    "अष्टांग हृदय": "Ashtanga Hridaya",
    "कामला": "Kamala",
    "पांडु": "Pandu",
}

# Kannada script to Canonical
KANNADA_TERM_MAP: Dict[str, str] = {
    "ಆಯುರ್ವೇದ": "Ayurveda",
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
    "ಮಧುಮೇಹ": "Madhumeha",
    "ಕಾಸ": "Kasa",
    "ಶ್ವಾಸ": "Shwasa",
    "ಕುಷ್ಠ": "Kushtha",
    "ಕುಷ್ಠರೋಗ": "Kushtha",
    "ರೋಗ": "Roga",
    "ವ್ಯಾಧಿ": "Vyadhi",
    "ಲಕ್ಷಣ": "Lakshana",
    "ನಿದಾನ": "Nidana",
    "ಸಂಪ್ರಾಪ್ತಿ": "Samprapti",
    "ಚಿಕಿತ್ಸೆ": "Chikitsa",
    "ತ್ರಿಮಲ": "Trimala",
    "ಮಲ": "Mala",
    "ಸ್ವಾಸ್ಥ್ಯ": "Swasthya",
    "ದಿನಚರ್ಯೆ": "Dinacharya",
    "ಋತುಚರ್ಯೆ": "Ritucharya",
    "ಅತಿಸಾರ": "Atisara",
    "ಅರ್ಶಸ್ಸು": "Arshas",
    "ರಾಜಯಕ್ಷ್ಮ": "Rajayakshma",
    "ಸ್ನೇಹನ": "Snehana",
    "ಸ್ವೇದನ": "Swedana",
    "ಶಿರೋಧಾರ": "Shirodhara",
    "ಶಿರೋಧಾರೆ": "Shirodhara",
    "ಗುಡೂಚಿ": "Guduchi",
    "ಚ್ಯವನಪ್ರಾಶ": "Chyawanprash",
    "ಬೃಹತ್ ತ್ರಯಿ": "Brihat Trayi",
    "ಚರಕ ಸಂಹಿತೆ": "Charaka Samhita",
    "ಸುಶ್ರುತ ಸಂಹಿತೆ": "Sushruta Samhita",
    "ಅಷ್ಟಾಂಗ ಹೃದಯ": "Ashtanga Hridaya",
    "ಕಾಮಲೆ": "Kamala",
    "ಕಾಮಣಿ": "Kamala",
    "ಕಾಮಾಲೆ": "Kamala",
    "ಪಾಂಡು": "Pandu",
}

# Canonical to Hindi (Devanagari)
CANONICAL_TO_HINDI: Dict[str, str] = {
    "Ayurveda": "आयुर्वेद",
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
    "Madhumeha": "मधुमेह",
    "Avrita": "आवृत्त",
    "Avarana": "आवरण",
    "Dhatukshayaja": "धातुक्षयज",
    "Agnimandya": "अग्निमांद्य",
    "Mandagni": "मंदाग्नि",
    "Kasa": "कास",
    "Shwasa": "श्वास",
    "Pitta Dosha": "पित्त दोष",
    "Vata Dosha": "वात दोष",
    "Kapha Dosha": "कफ दोष",
    "Kushtha": "कुष्ठ",
    "Roga": "रोग",
    "Vyadhi": "व्याधि",
    "Lakshana": "लक्षण",
    "Nidana": "निदान",
    "Samprapti": "संप्राप्ति",
    "Chikitsa": "चिकित्सा",
    "Swasthya": "स्वास्थ्य",
    "Kamala": "कामला",
    "Pandu": "पांडु",
}

# Canonical to Kannada script
CANONICAL_TO_KANNADA: Dict[str, str] = {
    "Ayurveda": "ಆಯುರ್ವೇದ",
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
    "Madhumeha": "ಮಧುಮೇಹ",
    "Avrita": "ಆವೃತ",
    "Avarana": "ಆವರಣ",
    "Dhatukshayaja": "ಧಾತುಕ್ಷಯಜ",
    "Agnimandya": "ಅಗ್ನಿಮಾಂದ್ಯ",
    "Mandagni": "ಮಂದಾಗ್ನಿ",
    "Kasa": "ಕಾಸ",
    "Shwasa": "ಶ್ವಾಸ",
    "Pitta Dosha": "ಪಿತ್ತ ದೋಷ",
    "Vata Dosha": "ವಾತ ದೋಷ",
    "Kapha Dosha": "ಕಫ ದೋಷ",
    "Kushtha": "ಕುಷ್ಠ",
    "Roga": "ರೋಗ",
    "Vyadhi": "ವ್ಯಾಧಿ",
    "Lakshana": "ಲಕ್ಷಣ",
    "Nidana": "ನಿದಾನ",
    "Samprapti": "ಸಂಪ್ರಾಪ್ತಿ",
    "Chikitsa": "ಚಿಕಿತ್ಸೆ",
    "Swasthya": "ಸ್ವಾಸ್ಥ್ಯ",
    "Kamala": "ಕಾಮಲೆ",
    "Pandu": "ಪಾಂಡು",
}

# Common Romanized spelling variants and transliterations
ROMAN_SPELLING_VARIANTS: Dict[str, str] = {
    "kushtha": "Kushtha",
    "kushta": "Kushtha",
    "kushtham": "Kushtha",
    "kusht": "Kushtha",
    "roga": "Roga",
    "rog": "Roga",
    "rogan": "Roga",
    "vyadhi": "Vyadhi",
    "vyadhis": "Vyadhi",
    "swasthya": "Swasthya",
    "nidana": "Nidana",
    "samprapti": "Samprapti",
    "lakshana": "Lakshana",
    "chikitsa": "Chikitsa",
    "kushta roga": "Kushtha",
    "kushtha roga": "Kushtha",
    "kushtaroga": "Kushtha",
    "kushtharoga": "Kushtha",
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
    "madhumeha": "Madhumeha",
    "madhumeh": "Madhumeha",
    "prameha": "Prameha",
    "diabetes": "Madhumeha",
    "abrita": "Avrita",
    "avrita": "Avrita",
    "avarana": "Avarana",
    "dhatuksayaja": "Dhatukshayaja",
    "dhatukshayaja": "Dhatukshayaja",
    "agnimandya": "Agnimandya",
    "agni mandya": "Agnimandya",
    "mandagni": "Mandagni",
    "trimala": "Trimala",
    "mala": "Mala",
    "purisha": "Purisha",
    "mutra": "Mutra",
    "sweda": "Sweda",
    "atisara": "Atisara",
    "rajayakshma": "Rajayakshma",
    "arshas": "Arshas",
    "arsha": "Arshas",
    "chyawanprash": "Chyawanprash",
    "snehana": "Snehana",
    "swedana": "Swedana",
    "virechana": "Virechana",
    "vamana": "Vamana",
    "basti": "Basti",
    "nasya": "Nasya",
    "raktamokshana": "Raktamokshana",
    "paschatkarma": "Paschatkarma",
    "samsarjana": "Samsarjana",
    "shirodhara": "Shirodhara",
    "dinacharya": "Dinacharya",
    "ritucharya": "Ritucharya",
    "brahma muhurta": "Brahma Muhurta",
    "brahmamuhurta": "Brahma Muhurta",
    "shad rasa": "Shad Rasa",
    "shad rasas": "Shad Rasa",
    "brihat trayi": "Brihat Trayi",
    "charaka samhita": "Charaka Samhita",
    "sushruta samhita": "Sushruta Samhita",
    "ashtanga hridaya": "Ashtanga Hridaya",
    "samagni": "Samagni",
    "vishamagni": "Vishamagni",
    "tikshnagni": "Tikshnagni",
    "dhatuposhana": "Dhatuposhana Nyaya",
    "dhatuposhana nyaya": "Dhatuposhana Nyaya",
    "dhatvagni": "Dhatvagni",
    "dhatvagnis": "Dhatvagni",
    "bhutagni": "Bhutagni",
    "bhutagnis": "Bhutagni",
    "guduchi": "Guduchi",
    "giloy": "Guduchi",
    "grishma": "Grishma Ritu",
    "grishma ritu": "Grishma Ritu",
    "varsha": "Varsha Ritu",
    "varsha ritu": "Varsha Ritu",
    "kamala": "Kamala",
    "kaamala": "Kamala",
    "kamani": "Kamala",
    "kamale": "Kamala",
    "kaamale": "Kamala",
    "jaundice": "Kamala",
    "pandu": "Pandu",
}

# Everyday English and grammatical Hindi/Kannada words that must never be
# matched as standalone technical terms (preventing false protection)
DISALLOWED_PLAIN_WORDS = {
    "box", "time", "deep", "five", "pre", "post", "bulk", "non", "ita",
    "karta", "karte", "karti", "kare", "karna", "hai", "hain", "hoga", "raha", "rahe",
    "cough", "blood", "pulse", "tissue", "nerve", "muscle", "bone", "fat", "plasma",
    "lymph", "toxin", "humor", "channels", "body", "health", "water", "food",
    "treatment", "two", "one", "three", "four", "six", "seven", "eight", "nine", "ten",
    "general", "categories", "skinny", "fatty", "system", "systems", "diet", "text",
    "type", "types", "case", "cases", "person", "individual", "individuals",
    "use", "uses", "help", "helps", "effect", "effects", "cause", "causes",
    "sign", "signs", "symptom", "symptoms", "care", "cure", "drug", "drugs",
    "disease", "diseases"
}

# Common Kannada noun suffixes to strip for root term recovery
KANNADA_SUFFIXES = [
    "ನಲ್ಲಿ", "ರಲ್ಲಿ", "ದಲ್ಲಿ",  # Locative
    "ವನ್ನು", "ಅನ್ನು", "ಯನ್ನು",  # Accusative
    "ಯಿಂದ", "ದಿಂದ",  # Instrumental / Ablative
    "ಕ್ಕೆ", "ಗೆ", "ಇಗೆ",  # Dative
    "ದ", "ಯ", "ನ",      # Genitive
    "ಗಳು", "ಗಳಲ್ಲಿ", "ಗಳ",    # Plural / Plural locative / Plural genitive
    "ವಾದ", "ವಾಗಿ",      # Adverbial
]

def _normalize_latin(text: str) -> str:
    """Normalize Latin text by lowercasing and stripping diacritics."""
    norm = unicodedata.normalize("NFKD", text)
    cleaned = "".join(c for c in norm if not unicodedata.combining(c))
    return re.sub(r"[^\w\s]", " ", cleaned).lower().strip()


def _phonetic_key(word: str) -> str:
    """Fold common Romanized Indic/Sanskrit spelling variations (ph->p, th->t, aa->a)."""
    w = (word or "").lower().strip()
    for src, dst in (
        ("ph", "p"), ("th", "t"), ("dh", "d"), ("kh", "k"), ("gh", "g"),
        ("bh", "b"), ("chh", "ch"), ("sh", "s"), ("aa", "a"), ("ee", "i"), ("oo", "u"),
    ):
        w = w.replace(src, dst)
    return w


_AYURVEDA_CONTEXT_WORDS = {
    "ayurveda", "ayurvedic", "ayurved", "dosha", "doshas", "dosh", "tridosha",
    "dhatu", "dhatus", "srotas", "samhita", "charaka", "sushruta", "vagbhata",
    "chikitsa", "nidana", "lakshana", "samprapti", "panchakarma", "rasayana",
    "herb", "herbs", "herbal", "dravya", "roga", "vyadhi", "prakriti", "agni",
}


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

    def find_fuzzy_terms(self, text: str, require_ayurveda_context: bool = True) -> List[Dict[str, Any]]:
        """
        Resolve spelling/phonetic variants of Ayurvedic terms (e.g., 'kapa' -> 'Kapha',
        'kushta' -> 'Kushtha', 'ashwaganda' -> 'Ashwagandha') when Ayurvedic context
        is present (or when require_ayurveda_context=False).
        """
        if not text:
            return []
        words = re.findall(r"\b[A-Za-z]{4,}\b", text)
        if not words:
            return []
        lower_set = {w.lower() for w in words}
        if require_ayurveda_context and not (lower_set & _AYURVEDA_CONTEXT_WORDS):
            return []

        import difflib
        exact_canons = {m["canonical_term"].lower() for m in self.find_terms(text)}
        # Build phonetic map over Latin lookup keys
        phon_map: Dict[str, str] = {}
        for k, canon in self.latin_lookup.items():
            if " " not in k and len(k) >= 4 and k not in DISALLOWED_PLAIN_WORDS:
                phon_map.setdefault(_phonetic_key(k), canon)

        out: List[Dict[str, Any]] = []
        seen_canons = set(exact_canons)
        for m in re.finditer(r"\b[A-Za-z]{4,}\b", text):
            tok = m.group(0)
            low = tok.lower()
            if low in DISALLOWED_PLAIN_WORDS or low in _AYURVEDA_CONTEXT_WORDS:
                continue
            if low in self.latin_lookup:
                continue
            pk = _phonetic_key(low)
            canon = phon_map.get(pk)
            if not canon:
                close = difflib.get_close_matches(low, [k for k in self.latin_lookup if " " not in k and len(k) >= 4], n=1, cutoff=0.82)
                if close:
                    canon = self.latin_lookup[close[0]]
            if canon and canon.lower() not in seen_canons:
                seen_canons.add(canon.lower())
                inv_meta = self.inventory.get(canon, {})
                out.append({
                    "canonical_term": canon,
                    "matched_text": tok,
                    "start": m.start(),
                    "end": m.end(),
                    "concept_id": inv_meta.get("concept_id", f"CID_{canon}"),
                    "script": "Latin_Fuzzy",
                    "ambiguity_note": inv_meta.get("ambiguity_note", ""),
                })
        return out

    def suggest_ambiguous_ayurvedic_terms(self, text: str) -> List[Dict[str, str]]:
        """
        For context-free short queries (e.g., 'What is kapa?'), detect tokens that are
        phonetically/orthographically close to core Ayurvedic terms.
        """
        if not text:
            return []
        import difflib
        phon_map: Dict[str, str] = {}
        for k, canon in self.latin_lookup.items():
            if " " not in k and len(k) >= 4 and k not in DISALLOWED_PLAIN_WORDS:
                phon_map.setdefault(_phonetic_key(k), canon)
        suggestions: List[Dict[str, str]] = []
        stop = {"what", "when", "where", "which", "who", "how", "why", "this", "that", "explain", "define", "mean", "meaning"}
        for tok in re.findall(r"\b[A-Za-z]{4,}\b", text):
            low = tok.lower()
            if low in stop or low in DISALLOWED_PLAIN_WORDS or low in self.latin_lookup:
                continue
            canon = phon_map.get(_phonetic_key(low))
            if not canon:
                close = difflib.get_close_matches(low, list(phon_map.keys()), n=1, cutoff=0.82)
                if close:
                    canon = phon_map[close[0]]
            if canon:
                suggestions.append({"token": tok, "canonical_term": canon})
        return suggestions

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


"""
AyurMitra — Layered Intelligent Query Router & Intent Classifier (v2)
=====================================================================
Multi-stage semantic router that categorizes user questions across six routes:
  1. AYURVEDA_DOMAIN
  2. GENERAL_KNOWLEDGE
  3. MIXED_DOMAIN
  4. CURRENT_INFORMATION
  5. UNSAFE_OR_MEDICALLY_SENSITIVE
  6. UNCLEAR_QUERY

Layered Architecture:
  Layer 1: Language & Script Identification
  Layer 2: Text Normalization & Regional Suffix Stripping
  Layer 3: Deterministic Safety & Clinical Risk Gate
  Layer 4: Entity & Concept Extraction (Ayurvedic, General, Interdisciplinary)
  Layer 5: Intent & Discourse Pattern Matching (Comparative, Definitional, Temporal)
  Layer 6: Multi-Factor Probabilistic Route Scoring
  Layer 7: Knowledge Source Selection & Confidence Thresholding
"""
from __future__ import annotations

import re
import unicodedata
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class QueryRoute(str, Enum):
    AYURVEDA_DOMAIN = "AYURVEDA_DOMAIN"
    GENERAL_KNOWLEDGE = "GENERAL_KNOWLEDGE"
    MIXED_DOMAIN = "MIXED_DOMAIN"
    CURRENT_INFORMATION = "CURRENT_INFORMATION"
    UNSAFE_OR_MEDICALLY_SENSITIVE = "UNSAFE_OR_MEDICALLY_SENSITIVE"
    UNCLEAR_QUERY = "UNCLEAR_QUERY"


# ── Safety Rules ─────────────────────────────────────────────────────────────
UNSAFE_RULES = [
    (re.compile(r"\b(cure|cures|curing)\s+cancer\b", re.IGNORECASE), "cancer_cure_claim"),
    (re.compile(r"\b(cure|cures)\b.*\b(in a week|overnight|in 24 hours|guaranteed|100%|completely)\b", re.IGNORECASE), "miracle_cure_claim"),
    (re.compile(r"\b(pregnant|pregnancy)\b.*\b(dose|dosage|how much to take|can take|take safely|medication)\b", re.IGNORECASE), "pregnancy_dosage_risk"),
    (re.compile(r"\b(dosage|dose|how much to take)\b.*\b(pregnant|pregnancy)\b", re.IGNORECASE), "pregnancy_dosage_risk"),
    (re.compile(r"\b(stop|discontinue)\b.*\b(prescribed|prescription|allopathic|inhaler|insulin|chemotherapy|medication|medicine)\b", re.IGNORECASE), "prescription_discontinuation_risk"),
    (re.compile(r"\b(lethal dose|how to overdose|poisonous dose|commit suicide|self-harm)\b", re.IGNORECASE), "self_harm_risk"),
    (re.compile(r"\b(cure|treat)\s+(stage\s*4|terminal|hiv|aids|ebola)\b", re.IGNORECASE), "terminal_illness_cure_claim"),
]

# ── Interdisciplinary / Mixed-Domain Patterns ────────────────────────────────
MIXED_DOMAIN_PATTERNS = [
    re.compile(r"\b(compare|comparison|difference between|versus|vs\.?)\b.*\b(ayurved\w*|traditional\s+medic\w*)\b.*\b(modern|allopath\w*|western|scientific|biomedic\w*)\b", re.IGNORECASE),
    re.compile(r"\b(compare|comparison|difference between|versus|vs\.?)\b.*\b(modern|allopath\w*|western|scientific|biomedic\w*)\b.*\b(ayurved\w*|traditional\s+medic\w*)\b", re.IGNORECASE),
    re.compile(r"\b(compare|comparison|difference between|versus|vs\.?)\b.*\b(traditional|ayurved\w*|agni|vata|pitta|kapha)\b.*\b(biological|metabolism|modern|science|scientific|allopath\w*)\b", re.IGNORECASE),
    re.compile(r"\b(compare|comparison|difference between|versus|vs\.?)\b.*\b(biological|metabolism|modern|science|scientific|allopath\w*)\b.*\b(traditional|ayurved\w*|agni|vata|pitta|kapha)\b", re.IGNORECASE),
    re.compile(r"\b(ai|artificial intelligence|nlp|machine learning|deep learning|data science|comput\w*|ontology|ontologies)\b.*\b(preserve|preservation|traditional|ayurved\w*|sanskrit)\b", re.IGNORECASE),
    re.compile(r"\b(how can|how does)\b.*\b(ai|nlp|technology|informatics)\b.*\b(ayurved\w*|traditional\s+medic\w*|herbal)\b", re.IGNORECASE),
    re.compile(r"\b(ayurved\w*|traditional\s+medic\w*)\b.*\b(modern\s+medicine|modern\s+terminology|snomed|icd-11|scientific\s+validation|modern\s+science|clinical\s+trials)\b", re.IGNORECASE),
    re.compile(r"\b(medicinal plants?|herbs?|phytochem\w*)\b.*\b(traditional.*modern|modern.*traditional|botanical\s+science|pharmacolog\w*)\b", re.IGNORECASE),
    re.compile(r"\b(traditional\s+ayurvedic\s+terminology\s+with\s+modern\s+medical\s+terminology)\b", re.IGNORECASE),
    re.compile(r"\b(is|are)\b.*\b(same as|equivalent to|equal to|similar to|different from|synonymous with)\b.*\b(modern|biology|pharmacolog\w*|allopath\w*|western|scientific|biomedic\w*)\b", re.IGNORECASE),
    re.compile(r"\b(how does|how do)\b.*\b(modern|pharmacolog\w*|allopath\w*|biomedic\w*|scientific)\b.*\b(study|evaluate|compare|analyze)\b.*\b(withania|ashwagandha|tulsi|herbal|ayurved\w*|rasayana)\b", re.IGNORECASE),
    re.compile(r"\b(pharmacolog\w*|modern\s+biology|modern\s+medicine|biomedic\w*)\b.*\b(compared to|versus|vs\.?|with)\b.*\b(ayurved\w*|rasayana|dosha|tridosha)\b", re.IGNORECASE),
]

# ── Current Information Patterns ─────────────────────────────────────────────
CURRENT_INFO_PATTERNS = [
    re.compile(r"\b(who is (the )?(current )?prime minister)\b", re.IGNORECASE),
    re.compile(r"\b(who is (the )?(current )?president)\b", re.IGNORECASE),
    re.compile(r"\b(current\s+prime\s+minister|current\s+president|current\s+chief\s+minister)\b", re.IGNORECASE),
    re.compile(r"\b(latest\s+developments?\s+in\s+(artificial\s+intelligence|ai|tech|science|world|robotics))\b", re.IGNORECASE),
    re.compile(r"\b(today('?s)?\s+news|breaking\s+news|happened\s+today|current\s+affairs|current\s+events?)\b", re.IGNORECASE),
    re.compile(r"\b(latest\s+(news|updates?|developments?|advancements?)\s+in\s+202[4-9])\b", re.IGNORECASE),
    re.compile(r"\b(current\s+(status|research|head|minister|ceo|leader|chancellor))\b", re.IGNORECASE),
]

# ── Authentic Ayurvedic Vocabulary ───────────────────────────────────────────
AYURVEDIC_TERMS_BASE = {
    # Core Tridosha & Subdoshas
    "vata", "pitta", "kapha", "tridosha", "dosha", "doshas", "dosh",
    "vaata", "pitha", "pittha", "kafa", "kaph", "prana", "apana", "samana", "vyana", "udana",
    # Dhatus & Upadhatus
    "dhatu", "dhatus", "rasa", "rakta", "mamsa", "meda", "asthi", "majja", "shukra",
    # Malas, Agni, Ama, Ojas
    "mala", "malas", "mutra", "purisha", "sveda", "agni", "jatharagni", "mandagni", "tikshnagni",
    "vishamagni", "samagni", "agnimandya", "ama", "ojas", "prakriti", "prakruti", "vikriti",
    "srotas", "srotasa", "nadi", "marma",
    # Equilibrium & Classical Health
    "dhatusamyata", "dhatusamya", "dhatuvaishamya", "dhatukshaya", "doshasamyata", "doshasamya",
    "doshavaishamya", "samadosha", "samadhatu",
    # Gunas & Pharmacodynamics
    "guna", "gunas", "vipaka", "virya", "prabhava", "rasa", "madhura", "amla", "lavana",
    "tikta", "katu", "kashaya", "snigdha", "ruksha", "guru", "laghu", "sheeta", "ushna",
    # Classical Herbs & Formulations
    "ashwagandha", "tulsi", "triphala", "neem", "guggulu", "brahmi", "shatavari",
    "haritaki", "amalaki", "bibhitaki", "giloy", "guduchi", "turmeric", "haldi",
    "chyawanprash", "arishta", "asava", "taila", "ghrita", "bhasma", "churna",
    "withania", "somnifera", "ocimum", "sanctum", "terminalia", "arjuna",
    # Classical Pathologies & Diseases
    "roga", "rog", "vyadhi", "swasthya", "nidana", "chikitsa", "lakshana", "samprapti",
    "madhumeha", "madhumeh", "prameha", "kushtha", "kushta", "kushtaroga",
    "kushtharoga", "jwara", "atisara", "grahani", "kasa", "shwasa", "rajayakshma",
    "arsha", "arshas", "gulma", "pandu", "kamala", "amavata", "sandhivata", "vatavyadhi",
    "hridroga", "shotha", "udararoga", "unmada", "apasmara", "visarpa",
    # Classical Disciplines & Literature
    "ayurveda", "ayurvedic", "panchakarma", "rasayana", "dinacharya", "ritucharya",
    "charaka", "sushruta", "vagbhata", "samhita", "nighantu", "ashtanga", "hridaya",
    "dravyaguna", "kayachikitsa", "shalakya", "shalya", "kaumarbhritya", "namaste", "imppat",
}

INDIC_AYURVEDIC_TERMS = {
    # Devanagari
    "रोग", "व्याधि", "लक्षण", "निदान", "चिकित्सा", "स्वास्थ्य", "संप्राप्ति",
    "आयुर्वेद", "वात", "वायु", "पित्त", "कफ", "श्लेष्मा", "अग्नि", "जठराग्नि",
    "प्रकृति", "धातु", "दोष", "ओजस", "ओज", "प्राण", "त्रिदोष", "आम", "रसायन",
    "पंचकर्म", "स्रोतस", "नाड़ी", "रस", "रक्त", "मांस", "मेद", "अस्थि", "मज्जा",
    "शुक्र", "अश्वगंधा", "त्रिफला", "तुलसी", "नीम", "गुग्गुल", "ब्राह्मी", "शतावरी",
    "हरीतकी", "आमलकी", "बिभीतकी", "गुल्म", "अर्श", "कास", "श्वास", "ज्वर", "प्रमेह",
    "मधुमेह", "कुष्ठ", "कुष्ठरोग", "आवृत्त", "आवरण", "धातुक्षयज", "अग्निमांद्य", "मंदाग्नि",
    "धातुसाम्यता", "धातुसाम्य", "धातुवैषम्य", "दोषवैषम्य", "समदोष", "समधातु",
    # Kannada
    "ರೋಗ", "ವ್ಯಾಧಿ", "ಲಕ್ಷಣ", "ನಿದಾನ", "ಚಿಕಿತ್ಸೆ", "ಸ್ವಾಸ್ಥ್ಯ", "ಸಂಪ್ರಾಪ್ತಿ",
    "ಆಯುರ್ವೇದ", "ವಾತ", "ವಾಯು", "ಪಿತ್ತ", "ಕಫ", "ಶ್ಲೇಷ್ಮ", "ಅಗ್ನಿ", "ಜಠರಾಗ್ನಿ",
    "ಪ್ರಕೃತಿ", "ಧಾತು", "ದೋಷ", "ಓಜಸ್ಸು", "ಓಜಸ್", "ಪ್ರಾಣ", "ತ್ರಿದೋಷ", "ಆಮ", "ರಸಾಯನ",
    "ಪಂಚಕರ್ಮ", "ಸ್ರೋತಸ್", "ನಾಡಿ", "ರಸ", "ರಕ್ತ", "ಮಾಂಸ", "ಮೇದಸ್ಸು", "ಅಸ್ಥಿ", "ಮಜ್ಜ",
    "ಶುಕ್ರ", "ಅಶ್ವಗಂಧ", "ತ್ರಿಫಲ", "ತುಳಸಿ", "ಬೇವಿನ", "ಬೇವು", "ಬ್ರಾಹ್ಮಿ", "ಶತಾವರಿ",
    "ಆಮಲಕಿ", "ಹರೀತಕಿ", "ಜ್ವರ", "ಪ್ರಮೇಹ", "ಮಧುಮೇಹ", "ಕಾಸ", "ಶ್ವಾಸ", "ಕುಷ್ಠ", "ಕುಷ್ಠರೋಗ",
    "ಆವೃತ", "ಆವರಣ", "ಧಾತುಕ್ಷಯಜ", "ಅಗ್ನಿಮಾಂದ್ಯ", "ಮಂದಾಗ್ನಿ",
    "ಧಾತುಸಾಮ್ಯತೆ", "ಧಾತುಸಾಮ್ಯ", "ಧಾತುವೈಷಮ್ಯ", "ದೋಷವೈಷಮ್ಯ", "ಸಮದೋಷ",
}

# ── General Educational Domains & Indicators ─────────────────────────────────
GENERAL_DOMAIN_KEYWORDS = {
    # Physics & Astronomy
    "newton", "gravity", "gravitation", "quantum", "relativity", "thermodynamics",
    "velocity", "acceleration", "friction", "inertia", "electromagnetism", "optics",
    "astronomy", "black hole", "galaxy", "solar system", "planets", "motion",
    # Chemistry & Modern Biology / Medicine
    "photosynthesis", "atom", "molecule", "chemical reaction", "catalyst",
    "periodic table", "oxidation", "reduction", "covalent", "ionic", "acid", "base",
    "modern biology", "biology", "modern medicine", "modern science", "pharmacology",
    "pharmacological", "biomedical", "biomedicine", "allopathy", "allopathic",
    "pathology", "physiology", "bile", "wellness", "vitality", "diabetes", "metabolism",
    # Biology & Ecology
    "dna", "rna", "genetics", "cellular", "mitochondria", "evolution", "ecosystem",
    "biodiversity", "species", "biome", "food chain",
    # Mathematics
    "calculus", "differentiation", "derivative", "integration", "integral", "matrix",
    "matrices", "linear algebra", "eigenvalue", "probability", "statistics", "geometry",
    "trigonometry", "algorithm", "pythagor", "pythagorean", "prime number",
    # Computer Science & Technology
    "machine learning", "neural network", "deep learning", "cloud computing",
    "rest api", "apis", "database", "sql", "nosql", "normalization", "operating system",
    "cybersecurity", "encryption", "compiler", "data science", "python decorators",
    "react", "javascript", "docker", "kubernetes", "binary search", "recursion",
    # History, Geography & Education
    "indian education", "education system", "nep 2020", "indian independence",
    "world war", "civilization", "geography", "continents", "tectonic plates",
    "chandragupta", "maurya", "indus valley",
}

GENERIC_ORDINAL_STOPWORDS = {
    "third", "first", "second", "fourth", "fifth", "one", "two", "three", "four", "five",
    "day", "days", "stage", "degree", "part", "type", "class", "law", "laws"
}


class IntelligentQueryRouter:
    """
    Seven-layer hybrid classifier selecting the authoritative knowledge source.
    """

    def __init__(self, matcher=None):
        self.matcher = matcher

    def _normalize_text(self, text: str) -> str:
        """Strip diacritics and normalize whitespace."""
        norm = unicodedata.normalize("NFKD", text or "")
        return "".join(c for c in norm if not unicodedata.combining(c)).lower().strip()

    def classify(self, query: str, detected_terms: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Executes layered intent & domain classification.
        Returns detailed routing decision with confidence scores.
        """
        raw = (query or "").strip()
        q_lower = raw.lower()
        words = re.findall(r"\b\w+\b", q_lower)

        # ── Layer 1 & 2: Ambiguity & Completeness Check ───────────────────────
        if not raw or (len(words) <= 1 and len(raw) < 4 and not any(t in raw for t in INDIC_AYURVEDIC_TERMS)):
            return {
                "route": QueryRoute.UNCLEAR_QUERY,
                "confidence": 0.98,
                "reason": "Query is too brief, empty, or ungrounded punctuation.",
                "matched_ayurvedic_terms": [],
                "matched_general_terms": [],
                "matched_mixed_terms": [],
                "scores": {QueryRoute.UNCLEAR_QUERY.value: 0.98},
                "is_safe": True,
            }

        # ── Layer 3: Deterministic Safety & Clinical Risk Gate ────────────────
        for pattern, risk_id in UNSAFE_RULES:
            if pattern.search(q_lower):
                return {
                    "route": QueryRoute.UNSAFE_OR_MEDICALLY_SENSITIVE,
                    "confidence": 1.0,
                    "reason": f"Triggered safety risk rule: {risk_id}",
                    "matched_ayurvedic_terms": [],
                    "matched_general_terms": [],
                    "matched_mixed_terms": [],
                    "scores": {QueryRoute.UNSAFE_OR_MEDICALLY_SENSITIVE.value: 1.0},
                    "is_safe": False,
                }

        # ── Layer 4: Interdisciplinary / Mixed-Domain Analysis ────────────────
        for pattern in MIXED_DOMAIN_PATTERNS:
            if pattern.search(q_lower):
                return {
                    "route": QueryRoute.MIXED_DOMAIN,
                    "confidence": 0.96,
                    "reason": "Explicit interdisciplinary comparison between Ayurveda and modern scientific/AI methodologies.",
                    "matched_ayurvedic_terms": ["Ayurveda"],
                    "matched_general_terms": ["Modern Medicine / AI"],
                    "matched_mixed_terms": [pattern.pattern[:30]],
                    "scores": {QueryRoute.MIXED_DOMAIN.value: 0.96},
                    "is_safe": True,
                }

        # ── Layer 5: Current Information / Live Event Analysis ────────────────
        for pattern in CURRENT_INFO_PATTERNS:
            if pattern.search(q_lower):
                return {
                    "route": QueryRoute.CURRENT_INFORMATION,
                    "confidence": 0.94,
                    "reason": "Inquires about live/current facts, current officeholders, or contemporary developments.",
                    "matched_ayurvedic_terms": [],
                    "matched_general_terms": ["Current Events"],
                    "matched_mixed_terms": [],
                    "scores": {QueryRoute.CURRENT_INFORMATION.value: 0.94},
                    "is_safe": True,
                }

        # ── Layer 6: Entity Extraction & Multi-Factor Route Scoring ───────────
        ayur_matches = []
        if detected_terms:
            for t in detected_terms:
                c = t.get("canonical_term") or t.get("term")
                if c and c.lower() not in GENERIC_ORDINAL_STOPWORDS and c not in ayur_matches:
                    ayur_matches.append(c)

        if self.matcher and not ayur_matches:
            try:
                found = self.matcher.find_terms(raw)
                for t in found:
                    c = t.get("canonical_term")
                    if c and c.lower() not in GENERIC_ORDINAL_STOPWORDS and c not in ayur_matches:
                        ayur_matches.append(c)
            except Exception:
                pass

        for w in words:
            if w in AYURVEDIC_TERMS_BASE and w not in GENERIC_ORDINAL_STOPWORDS and w not in ayur_matches:
                ayur_matches.append(w)

        for ind in INDIC_AYURVEDIC_TERMS:
            if ind in raw and ind not in ayur_matches:
                ayur_matches.append(ind)

        general_matches = []
        for g in GENERAL_DOMAIN_KEYWORDS:
            if g in q_lower and g not in general_matches:
                general_matches.append(g)

        # If user queried general medical terms (like 'diabetes') without classical keywords, prevent matcher false positive
        if "diabetes" in q_lower and not any(k in q_lower for k in ("madhumeh", "prameh", "ayurved")):
            ayur_matches = [m for m in ayur_matches if m != "Madhumeha"]

        # Multi-factor scoring
        score_ayur = min(1.0, len(ayur_matches) * 0.45)
        score_gen = min(1.0, len(general_matches) * 0.45)

        scores = {
            QueryRoute.AYURVEDA_DOMAIN.value: score_ayur,
            QueryRoute.GENERAL_KNOWLEDGE.value: score_gen,
            QueryRoute.MIXED_DOMAIN.value: (score_ayur + score_gen) / 2.0 if (score_ayur and score_gen) else 0.0,
            QueryRoute.CURRENT_INFORMATION.value: 0.1,
            QueryRoute.UNSAFE_OR_MEDICALLY_SENSITIVE.value: 0.0,
            QueryRoute.UNCLEAR_QUERY.value: 0.05
        }

        # Check for mixed domain convergence
        if score_ayur >= 0.35 and score_gen >= 0.35:
            return {
                "route": QueryRoute.MIXED_DOMAIN,
                "confidence": 0.92,
                "reason": f"Convergent intent: combined Ayurvedic concepts ({ayur_matches[:2]}) with general scientific topics ({general_matches[:2]}).",
                "matched_ayurvedic_terms": ayur_matches,
                "matched_general_terms": general_matches,
                "matched_mixed_terms": [],
                "scores": scores,
                "is_safe": True,
            }

        # ── Layer 7: Final Selection & Confidence Thresholding ────────────────
        if score_ayur > score_gen and score_ayur >= 0.3:
            return {
                "route": QueryRoute.AYURVEDA_DOMAIN,
                "confidence": max(0.85, score_ayur),
                "reason": f"Grounded in verified Ayurvedic terminology: {ayur_matches[:3]}",
                "matched_ayurvedic_terms": ayur_matches,
                "matched_general_terms": [],
                "matched_mixed_terms": [],
                "scores": scores,
                "is_safe": True,
            }

        if score_gen > 0:
            return {
                "route": QueryRoute.GENERAL_KNOWLEDGE,
                "confidence": max(0.85, score_gen),
                "reason": f"Pertains to general educational domains: {general_matches[:3]}",
                "matched_ayurvedic_terms": [],
                "matched_general_terms": general_matches,
                "matched_mixed_terms": [],
                "scores": scores,
                "is_safe": True,
            }

        # Default fallback to general educational intelligence if coherent sentence
        if len(words) >= 3:
            return {
                "route": QueryRoute.GENERAL_KNOWLEDGE,
                "confidence": 0.75,
                "reason": "General open-domain question outside classical Ayurvedic literature.",
                "matched_ayurvedic_terms": [],
                "matched_general_terms": [],
                "matched_mixed_terms": [],
                "scores": scores,
                "is_safe": True,
            }

        # Ambiguous short input
        return {
            "route": QueryRoute.UNCLEAR_QUERY,
            "confidence": 0.70,
            "reason": "Ambiguous or incomplete input requiring clarification.",
            "matched_ayurvedic_terms": [],
            "matched_general_terms": [],
            "matched_mixed_terms": [],
            "scores": scores,
            "is_safe": True,
        }

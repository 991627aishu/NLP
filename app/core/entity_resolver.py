"""
AyurMitra — Semantic Entity Resolver & Disambiguation Engine
=============================================================
Extracts the clean focal subject/entity from user queries across English,
Hindi (Devanagari/Romanized), and Kannada (Script/Romanized).
Eliminates conversational wrappers ('what is', 'endarenu', 'ka matlab')
and performs contextual disambiguation between:
  - General disease/illness concepts (Roga, Vyadhi, Disease)
  - Ayurvedic conceptual pathology (Dosha-vaishamya, WHO ITA-4.2.1)
  - Specific medical disorders (e.g., Kuru disease, Parkinson's)
  - Unrelated named entities and cultural terms (e.g., Mopacho)
  - Scientific STEM concepts
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from app.core.matcher import CANONICAL_TO_HINDI, CANONICAL_TO_KANNADA


# Conversational Question Wrappers to Strip
EN_PREFIXES = [
    r"^\s*what\s+is\s+the\s+ayurvedic\s+(?:understanding|meaning|concept|definition)\s+of\s+",
    r"^\s*how\s+is\s+(.+?)\s+understood\s+in\s+classical\s+ayurveda\s*\??$",
    r"^\s*what\s+is\s+an?\s+",
    r"^\s*what\s+is\s+",
    r"^\s*what\s+are\s+the\s+(?:qualities|properties|symptoms|causes|components|functions|uses|benefits)\s+of\s+",
    r"^\s*what\s+are\s+",
    r"^\s*what\s+does\s+",
    r"^\s*tell\s+me\s+about\s+",
    r"^\s*explain\s+",
    r"^\s*define\s+",
    r"^\s*meaning\s+of\s+",
    r"^\s*can\s+you\s+explain\s+",
]

EN_SUFFIXES = [
    r"\s+in\s+ayurveda\s*\??$",
    r"\s+according\s+to\s+ayurveda\s*\??$",
    r"\s+mean\s*\??$",
    r"\s*\?+$",
]

HI_PATTERNS = [
    r"^\s*आयुर्वेद\s+में\s+(.+?)\s+का\s+(?:क्या\s+)?(?:अर्थ|तात्पर्य|मतलब)\s+है\s*\??$",
    r"^\s*(.+?)\s+(?:का\s+)?मतलब\s+क्या\s+होता\s+है\s*\??$",
    r"^\s*(.+?)\s+क्या\s+(?:होता\s+है|है|किसे\s+कहते\s+हैं)\s*\??$",
    r"^\s*(.+?)\s+के\s+(?:लक्षण|कारण|उपाय|फायदे)\s+क्या\s+हैं\s*\??$",
    r"^\s*(.+?)\s+का\s+अर्थ\s+क्या\s+है\s*\??$",
]

KN_PATTERNS = [
    r"^\s*ಆಯುರ್ವೇದದಲ್ಲಿ\s+(.+?)\s+ಎಂದರೇನು\s*\??$",
    r"^\s*ಆಯುರ್ವೇದದಲ್ಲಿ\s+(.+?)\s+ಎಂದರೆ\s*\??$",
    r"^\s*ಆಯುರ್ವೇದದಲ್ಲಿ\s+(.+?)\s+ಅರ್ಥವೇನು\s*\??$",
    r"^\s*(.+?)\s+ಎಂದರೇನು\s*\??$",
    r"^\s*(.+?)\s+ಎಂದರೆ\s*\??$",
    r"^\s*(.+?)\s+ಅಂದರೇನು\s*\??$",
    r"^\s*(.+?)\s+ಅಂದರೆ\s*\??$",
    r"^\s*(.+?)\s+ಅರ್ಥವೇನು\s*\??$",
    r"^\s*(.+?)\s+ಬಗ್ಗೆ\s+ತಿಳಿಸಿ\s*\??$",
    r"^\s*(.+?)\s+ಲಕ್ಷಣಗಳು\s+ಯಾವುವು\s*\??$",
    r"^\s*(.+?)\s+ಏನು\s*\??$",
]

HINGLISH_PATTERNS = [
    r"^\s*ayurveda\s+mein\s+(.+?)\s+kya\s+hota\s+hai\s*\??$",
    r"^\s*(.+?)\s+ka\s+matlab\s+kya\s+hota\s+hai\s*\??$",
    r"^\s*(.+?)\s+kya\s+hota\s+hai\s*\??$",
    r"^\s*(.+?)\s+kya\s+hai\s*\??$",
    r"^\s*(.+?)\s+ke\s+lakshan\s+kya\s+hain\s*\??$",
]

KANGLISH_PATTERNS = [
    r"^\s*ayurvedadalli\s+(.+?)\s+andre\s+enu\s*\??$",
    r"^\s*(.+?)\s+andre\s+enu\s*\??$",
    r"^\s*(.+?)\s+artha\s+enu\s*\??$",
    r"^\s*(.+?)\s+bagge\s+heli\s*\??$",
]


# Known Grounded Conceptual Disambiguations
SEMANTIC_ENTITY_CATALOG: Dict[str, Dict[str, Any]] = {
    "roga": {
        "canonical_name": "Roga",
        "category": "DISEASE_GENERAL",
        "ayurvedic_concept": True,
        "general_concept": True,
        "english_equivalent": "Disease",
        "synonyms": ["vyadhi", "amaya", "gada", "vikara", "disease", "illness", "pathology"],
        "hindi_synonyms": ["रोग", "व्याधि", "बीमारी", "विकार"],
        "kannada_synonyms": ["ರೋಗ", "ವ್ಯಾಧಿ", "ಕಾಯಿಲೆ", "ಅಸ್ವಸ್ಥತೆ"],
        "definition_short": "A disease or condition causing pain, distress, or physiological disequilibrium.",
        "ayurvedic_definition": "Dosha-vaishamya (vitiation and disequilibrium of Vata, Pitta, Kapha) leading to tissue and channel obstruction (Rujati iti rogaha). WHO ITA-4.2.1.",
        "who_id": "ITA-4.2.1",
        "wikipedia_target": "Disease",
    },
    "disease": {
        "canonical_name": "Disease",
        "category": "DISEASE_GENERAL",
        "ayurvedic_concept": True,
        "general_concept": True,
        "english_equivalent": "Disease",
        "synonyms": ["roga", "vyadhi", "illness", "sickness", "medical condition", "disorder"],
        "hindi_synonyms": ["रोग", "बीमारी", "व्याधि"],
        "kannada_synonyms": ["ರೋಗ", "ಕಾಯಿಲೆ", "ವ್ಯಾಧಿ"],
        "definition_short": "A particular abnormal condition that negatively affects the structure or function of all or part of an organism.",
        "ayurvedic_definition": "Categorized as Roga or Vyadhi; disturbance of bodily doshas and dhatus. WHO ITA-4.2.1.",
        "who_id": "ITA-4.2.1",
        "wikipedia_target": "Disease",
    },
    "kuru disease": {
        "canonical_name": "Kuru (disease)",
        "category": "SPECIFIC_MEDICAL_CONDITION",
        "ayurvedic_concept": False,
        "general_concept": True,
        "english_equivalent": "Kuru",
        "synonyms": ["kuru", "kuru prion disease", "laughing sickness"],
        "hindi_synonyms": ["कुरु", "कुरु बीमारी"],
        "kannada_synonyms": ["ಕುರು", "ಕುರು ರೋಗ"],
        "definition_short": "A rare, fatal neurodegenerative prion disorder formerly endemic among the Fore people of Papua New Guinea.",
        "wikipedia_target": "Kuru_(disease)",
    },
    "mopacho": {
        "canonical_name": "Mopacho",
        "category": "CULTURAL_NAMED_ENTITY",
        "ayurvedic_concept": False,
        "general_concept": True,
        "english_equivalent": "Mopacho",
        "synonyms": ["mopacho dance", "congolese dance"],
        "hindi_synonyms": ["मोपाचो"],
        "kannada_synonyms": ["ಮೊಪಾಚೊ"],
        "definition_short": "A Congolese dance style originating in Brazzaville in 1990 characterized by full-body movements.",
        "wikipedia_target": "Mopacho",
    },
    "loose motion": {
        "canonical_name": "Diarrhea",
        "category": "MEDICAL_EDUCATION",
        "ayurvedic_concept": True,
        "general_concept": True,
        "english_equivalent": "Diarrhea",
        "synonyms": ["loose motion", "loose motions", "diarrhea", "diarrhoea", "watery stool", "loose stools", "atisara", "dysentery"],
        "hindi_synonyms": ["दस्त", "अतिसार", "पतले दस्त", "लूज मोशन"],
        "kannada_synonyms": ["ಭೇದಿ", "ಬೇದಿ", "ಸಡಿಲ ಮಲವಿಸರ್ಜನೆ", "ಅತಿಸಾರ", "ನೀರು ಬೇದಿ"],
        "definition_short": "The condition of having at least three loose, liquid, or watery bowel movements each day, managed primarily through hydration and ORS.",
        "ayurvedic_definition": "Correlated with Atisara in classical Ayurveda; vitiation of Agni and Pitta/Vata leading to excessive fluid discharge from the bowel. WHO ITA-5.28.",
        "wikipedia_target": "Diarrhea",
    },
    "morning": {
        "canonical_name": "Morning",
        "category": "GENERAL_VOCABULARY",
        "ayurvedic_concept": False,
        "general_concept": True,
        "english_equivalent": "Morning",
        "synonyms": ["morning", "dawn", "daybreak", "sunrise", "forenoon"],
        "hindi_synonyms": ["सुबह", "प्रातःकाल", "भोर", "सवेरा", "प्रभात"],
        "kannada_synonyms": ["ಬೆಳಿಗ್ಗೆ", "ಮುಂಜಾನೆ", "ಪ್ರಭಾತ", "ಬೆಳಗು"],
        "definition_short": "The period of time from sunrise to noon, marking the beginning of the diurnal day.",
        "wikipedia_target": "Morning",
    },
    "gravity": {
        "canonical_name": "Gravity",
        "category": "PHYSICS",
        "ayurvedic_concept": False,
        "general_concept": True,
        "english_equivalent": "Gravity",
        "synonyms": ["gravity", "gravitation", "gravitational force", "universal gravitation"],
        "hindi_synonyms": ["गुरुत्वाकर्षण", "गुरुत्व बल"],
        "kannada_synonyms": ["ಗುರುತ್ವಾಕರ್ಷಣೆ", "ಗುರುತ್ವ ಬಲ"],
        "definition_short": "A fundamental interaction causing mutual attraction between all things that have mass or energy.",
        "wikipedia_target": "Gravity",
    },
    "democracy": {
        "canonical_name": "Democracy",
        "category": "POLITICAL_SCIENCE",
        "ayurvedic_concept": False,
        "general_concept": True,
        "english_equivalent": "Democracy",
        "synonyms": ["democracy", "democratic governance", "rule of law", "republic"],
        "hindi_synonyms": ["लोकतंत्र", "प्रजातंत्र", "गणतंत्र"],
        "kannada_synonyms": ["ಪ್ರಜಾಪ್ರಭುತ್ವ", "ಗಣರಾಜ್ಯ"],
        "definition_short": "A system of government in which state power is vested in the people or exercised through elected representatives.",
        "wikipedia_target": "Democracy",
    },
    "photosynthesis": {
        "canonical_name": "Photosynthesis",
        "category": "BIOLOGY",
        "ayurvedic_concept": False,
        "general_concept": True,
        "english_equivalent": "Photosynthesis",
        "synonyms": ["photosynthesis", "carbon fixation", "light reaction", "chlorophyll"],
        "hindi_synonyms": ["प्रकाश संश्लेषण", "प्रकाशसंश्लेषण"],
        "kannada_synonyms": ["ದ್ಯುತಿಸಂಶ್ಲೇಷಣೆ", "ದ್ಯುತಿ ಸಂಶ್ಲೇಷಣೆ"],
        "definition_short": "A biological process by which plants and other organisms convert light energy into chemical energy.",
        "wikipedia_target": "Photosynthesis",
    },
    "python programming": {
        "canonical_name": "Python (programming language)",
        "category": "COMPUTER_SCIENCE",
        "ayurvedic_concept": False,
        "general_concept": True,
        "english_equivalent": "Python",
        "synonyms": ["python programming", "python language", "python code", "python"],
        "hindi_synonyms": ["पायथन", "पायथन प्रोग्रामिंग"],
        "kannada_synonyms": ["ಪೈಥಾನ್", "ಪೈಥಾನ್ ಪ್ರೋಗ್ರಾಮಿಂಗ್"],
        "definition_short": "A high-level, interpreted, general-purpose programming language known for readability and wide versatility.",
        "wikipedia_target": "Python_(programming_language)",
    },
    "ram and rom": {
        "canonical_name": "RAM and ROM",
        "category": "COMPUTER_SCIENCE",
        "ayurvedic_concept": False,
        "general_concept": True,
        "english_equivalent": "RAM vs ROM",
        "synonyms": ["difference between ram and rom", "ram vs rom", "ram and rom", "random access memory", "read only memory"],
        "hindi_synonyms": ["रैम और रोम", "रैम और रोम में अंतर"],
        "kannada_synonyms": ["ರಾಮ್ ಮತ್ತು ರೋಮ್", "ರಾಮ್ ಮತ್ತು ರೋಮ್ ನಡುವಿನ ವ್ಯತ್ಯಾಸ"],
        "definition_short": "RAM is volatile high-speed read/write memory for active data, while ROM is non-volatile permanent memory storing boot firmware.",
        "wikipedia_target": "Computer_memory",
    },
    "diabetes": {
        "canonical_name": "Diabetes",
        "category": "MEDICAL_EDUCATION",
        "ayurvedic_concept": True,
        "general_concept": True,
        "english_equivalent": "Diabetes Mellitus",
        "synonyms": ["diabetes", "diabetes mellitus", "high blood sugar", "madhumeha", "hyperglycemia"],
        "hindi_synonyms": ["मधुमेह", "शुगर की बीमारी", "डायबिटीज"],
        "kannada_synonyms": ["ಮಧುಮೇಹ", "ಸಕ್ಕರೆ ಕಾಯಿಲೆ", "ಡಯಾಬಿಟಿಸ್"],
        "definition_short": "A chronic metabolic disease characterized by elevated levels of blood glucose due to insufficient insulin production or action.",
        "ayurvedic_definition": "Identified as Madhumeha under the broad classification of Prameha disorders. WHO ITA-5.41.29.",
        "wikipedia_target": "Diabetes",
    },
    "newton's laws": {
        "canonical_name": "Newton's laws of motion",
        "category": "PHYSICS",
        "ayurvedic_concept": False,
        "general_concept": True,
        "english_equivalent": "Newton's laws of motion",
        "synonyms": ["newton's laws", "newton's laws of motion", "newton laws", "three laws of motion"],
        "hindi_synonyms": ["न्यूटन के गति के नियम", "न्यूटन के नियम"],
        "kannada_synonyms": ["ನ್ಯೂಟನ್ ಚಲನೆಯ ನಿಯಮಗಳು", "ನ್ಯೂಟನ್ ನಿಯಮಗಳು"],
        "definition_short": "Three fundamental physical laws that describe the relationship between the motion of an object and the forces acting on it.",
        "wikipedia_target": "Newton's_laws_of_motion",
    },
    "jwara": {
        "canonical_name": "Jwara",
        "category": "AYURVEDIC_PATHOLOGY",
        "ayurvedic_concept": True,
        "general_concept": True,
        "english_equivalent": "Fever / Jwara",
        "synonyms": ["jwara", "jvara", "jwara in ayurveda", "fever in ayurveda", "jwar", "jwaram"],
        "hindi_synonyms": ["ज्वर", "आयुर्वेद में ज्वर"],
        "kannada_synonyms": ["ಜ್ವರ", "ಆಯುರ್ವೇದದಲ್ಲಿ ಜ್ವರ"],
        "definition_short": "In classical Ayurveda, Jwara (Fever, WHO ITA-5.6.1) is considered the king of diseases (Rogarat), characterized by Santapa, Sveda-avarodha, Aruchi, and body stiffness.",
        "ayurvedic_definition": "A disorder characterized by rise of temperature/agitation; absence of perspiration; generalized body stiffness/pain. WHO ITA-5.6.1.",
        "wikipedia_target": "Fever",
    },
    "fever": {
        "canonical_name": "Fever",
        "category": "MEDICAL_EDUCATION",
        "ayurvedic_concept": True,
        "general_concept": True,
        "english_equivalent": "Fever (Pyrexia)",
        "synonyms": ["fever", "pyrexia", "high temperature", "febrile illness", "elevated body temperature"],
        "hindi_synonyms": ["बुखार", "ताप"],
        "kannada_synonyms": ["ಜ್ವರ", "ತಾಪ"],
        "definition_short": "Fever (pyrexia) is a temporary elevation of body temperature above the normal physiological set-point (typically >38°C / 100.4°F), mediated by pyrogens in response to infection or inflammation.",
        "wikipedia_target": "Fever",
    },
    "rag": {
        "canonical_name": "Retrieval-Augmented Generation",
        "category": "COMPUTER_SCIENCE",
        "ayurvedic_concept": False,
        "general_concept": True,
        "english_equivalent": "Retrieval-Augmented Generation (RAG)",
        "synonyms": ["rag", "what is rag", "retrieval augmented generation", "retrieval-augmented generation"],
        "hindi_synonyms": ["आरएजी", "रिट्रीवल ऑगमेंटेड जनरेशन"],
        "kannada_synonyms": ["ಆರ್‌ಎಜಿ", "ರಿಟ್ರೈವಲ್ ಆಗ್ಮೆಂಟೆಡ್ ಜನರೇಷನ್"],
        "definition_short": "Retrieval-Augmented Generation (RAG) is an AI architecture that enhances large language models by dynamically retrieving relevant facts from external authoritative databases before generating an answer.",
        "wikipedia_target": "Retrieval-augmented_generation",
    },
    "panchakarma": {
        "canonical_name": "Panchakarma",
        "category": "AYURVEDIC_THERAPY",
        "ayurvedic_concept": True,
        "general_concept": True,
        "english_equivalent": "Panchakarma (Five Purification Procedures)",
        "synonyms": ["panchakarma", "panchakarma therapy", "panchakarma procedures", "panchakarma in ayurveda", "explain panchakarma"],
        "hindi_synonyms": ["पंचकर्म", "पंचकर्म चिकित्सा"],
        "kannada_synonyms": ["ಪಂಚಕರ್ಮ", "ಪಂಚಕರ್ಮ ಚಿಕಿತ್ಸೆ"],
        "definition_short": "The five classical bio-purification and detoxification procedures in Ayurveda: Vamana, Virechana, Basti, Nasya, and Raktamokshana.",
        "ayurvedic_definition": "Shodhana procedures that eliminate deeply seated morbid doshas from the microchannels (Srotas). WHO ITA-7.1.",
        "who_id": "ITA-7.1",
        "wikipedia_target": "Panchakarma",
    },
    "prakriti and vikriti": {
        "canonical_name": "Prakriti and Vikriti",
        "category": "AYURVEDIC_PRINCIPLES",
        "ayurvedic_concept": True,
        "general_concept": True,
        "english_equivalent": "Prakriti vs Vikriti",
        "synonyms": ["prakriti and vikriti", "difference between prakriti and vikriti", "prakriti vs vikriti", "vikriti and prakriti"],
        "hindi_synonyms": ["प्रकृति और विकृति", "प्रकृति और विकृति में अंतर"],
        "kannada_synonyms": ["ಪ್ರಕೃತಿ ಮತ್ತು ವಿಕೃತಿ", "ಪ್ರಕೃತಿ ಮತ್ತು ವಿಕೃತಿ ನಡುವಿನ ವ್ಯತ್ಯಾಸ"],
        "definition_short": "Prakriti is an individual's innate baseline constitution formed at conception, whereas Vikriti is the acquired pathological state of doshic imbalance.",
        "ayurvedic_definition": "Prakriti represents natural doshic equilibrium; Vikriti represents departure into dosha-vaishamya. WHO ITA-4.1.2.",
        "who_id": "ITA-4.1.2",
        "wikipedia_target": "Prakriti",
    },
    "charaka samhita": {
        "canonical_name": "Charaka Samhita",
        "category": "AYURVEDIC_CLASSICS",
        "ayurvedic_concept": True,
        "general_concept": True,
        "english_equivalent": "Charaka Samhita",
        "synonyms": ["charaka samhita", "caraka samhita", "charak samhita"],
        "hindi_synonyms": ["चरक संहिता"],
        "kannada_synonyms": ["ಚರಕ ಸಂಹಿತೆ"],
        "definition_short": "The classical Sanskrit treatise on Ayurvedic internal medicine (Kaya Chikitsa), authored by Mahamuni Atreya and redacted by Acharya Charaka.",
        "ayurvedic_definition": "Foundational Brihat Trayi text outlining Tridosha physiology, Nidana, and systemic therapeutics.",
        "wikipedia_target": "Charaka_Samhita",
    },
    "sushruta samhita": {
        "canonical_name": "Sushruta Samhita",
        "category": "AYURVEDIC_CLASSICS",
        "ayurvedic_concept": True,
        "general_concept": True,
        "english_equivalent": "Sushruta Samhita",
        "synonyms": ["sushruta samhita", "suskruta samhita", "sushrut samhita"],
        "hindi_synonyms": ["सुश्रुत संहिता"],
        "kannada_synonyms": ["ಸುಶ್ರುತ ಸಂಹಿತೆ"],
        "definition_short": "The foundational classical Sanskrit treatise on Ayurvedic surgery (Shalya Tantra), authored by Acharya Sushruta.",
        "ayurvedic_definition": "Pioneering surgical text documenting operative techniques, instruments, and surgical anatomy.",
        "wikipedia_target": "Sushruta_Samhita",
    },
    "triphala": {
        "canonical_name": "Triphala",
        "category": "AYURVEDIC_FORMULATION",
        "ayurvedic_concept": True,
        "general_concept": True,
        "english_equivalent": "Triphala",
        "synonyms": ["triphala", "trifala", "triphala churna", "triphala powder"],
        "hindi_synonyms": ["त्रिफला", "त्रिफला चूर्ण"],
        "kannada_synonyms": ["ತ್ರಿಫಲ", "ತ್ರಿಫಲ ಚೂರ್ಣ"],
        "definition_short": "A classical Ayurvedic herbal formulation composed of equal proportions of Amalaki, Bibhitaki, and Haritaki.",
        "ayurvedic_definition": "A Tridosha-balancing Rasayana, digestive toner, mild laxative, and ocular tonic. WHO ITA-6.2.14.",
        "who_id": "ITA-6.2.14",
        "wikipedia_target": "Triphala",
    },
}

# Cross-populate Hindi and Kannada keys into catalog
for key, data in list(SEMANTIC_ENTITY_CATALOG.items()):
    for hi_syn in data.get("hindi_synonyms", []):
        SEMANTIC_ENTITY_CATALOG[hi_syn.lower()] = data
    for kn_syn in data.get("kannada_synonyms", []):
        SEMANTIC_ENTITY_CATALOG[kn_syn.lower()] = data
    for syn in data.get("synonyms", []):
        if syn not in SEMANTIC_ENTITY_CATALOG:
            SEMANTIC_ENTITY_CATALOG[syn.lower()] = data


class SemanticEntityResolver:
    """
    Resolves user query to its true semantic focal entity, eliminating
    ambiguity, substring errors, and irrelevant entity drift.
    """

    def __init__(self):
        pass

    def extract_focal_entity(self, query: str) -> Dict[str, Any]:
        """
        Strips syntactic wrappers and extracts the clean focal entity.
        Detects explicit domain context (e.g., 'in Ayurveda').
        """
        q = query.strip()
        has_ayurveda = bool(re.search(r"\b(?:ayurveda|ayurvedic|आयुर्वेद|ಆಯುರ್ವೇದ|charaka|sushruta)\b", q, re.IGNORECASE))
        has_comparison = bool(re.search(r"\b(?:compare|comparison|versus|vs|difference|between)\b", q, re.IGNORECASE))

        raw_entity = q

        # 1. Try Hindi pattern matches
        for pat in HI_PATTERNS:
            m = re.match(pat, q)
            if m:
                raw_entity = m.group(1).strip()
                break

        # 2. Try Kannada pattern matches
        if raw_entity == q:
            for pat in KN_PATTERNS:
                m = re.match(pat, q)
                if m:
                    raw_entity = m.group(1).strip()
                    break

        # 3. Try Hinglish pattern matches
        if raw_entity == q:
            for pat in HINGLISH_PATTERNS:
                m = re.match(pat, q, re.IGNORECASE)
                if m:
                    raw_entity = m.group(1).strip()
                    break

        # 4. Try Kanglish pattern matches
        if raw_entity == q:
            for pat in KANGLISH_PATTERNS:
                m = re.match(pat, q, re.IGNORECASE)
                if m:
                    raw_entity = m.group(1).strip()
                    break

        # 5. Try English pattern matches & strip wrappers
        if raw_entity == q:
            clean_en = q
            for pref in EN_PREFIXES:
                clean_en = re.sub(pref, "", clean_en, flags=re.IGNORECASE)
            for suff in EN_SUFFIXES:
                clean_en = re.sub(suff, "", clean_en, flags=re.IGNORECASE)
            raw_entity = clean_en.strip()

        # Clean punctuation
        clean_norm = re.sub(r"[?!.,;:\"\']", "", raw_entity).strip()
        clean_lower = clean_norm.lower()

        # Check in Semantic Catalog
        catalog_entry = SEMANTIC_ENTITY_CATALOG.get(clean_lower)
        if not catalog_entry and clean_lower.endswith(" disease"):
            base = clean_lower[:-8].strip()
            catalog_entry = SEMANTIC_ENTITY_CATALOG.get(base)

        return {
            "original_query": query,
            "raw_extracted_entity": clean_norm,
            "normalized_entity": clean_lower,
            "has_explicit_ayurveda": has_ayurveda,
            "has_explicit_comparison": has_comparison,
            "catalog_match": catalog_entry is not None,
            "catalog_entry": catalog_entry,
        }

    def compute_alignment_score(self, focal_entity: str, candidate_title: str, candidate_snippet: str = "") -> float:
        """
        Quantifies semantic alignment between candidate article title and focal entity.
        Returns a score between 0.0 and 1.0.
        Rejects candidates that have zero entity relation (e.g., Mopacho for roga).
        """
        f = focal_entity.lower().strip()
        t = candidate_title.lower().strip()
        s = candidate_snippet.lower().strip()

        # 1. Exact match
        if f == t:
            return 1.0

        # 2. Check catalog targets / synonyms
        entry = SEMANTIC_ENTITY_CATALOG.get(f)
        if entry:
            wiki_target = entry.get("wikipedia_target", "").lower().replace("_", " ")
            if t == wiki_target or wiki_target in t:
                return 0.98
            for syn in entry.get("synonyms", []):
                if syn == t or t == syn:
                    return 0.95
                if syn in t and len(syn) >= 4:
                    return 0.85

        # 3. Handle specific condition qualification
        # E.g., user asks for 'disease' -> 'Kuru (disease)' should be penalized in favor of 'Disease'
        if f in ("disease", "illness", "roga") and "(" in t and "disease" in t:
            # It's a specific subtype, not the general concept
            return 0.40

        # 4. Token overlap
        f_words = set(re.findall(r"\w+", f))
        t_words = set(re.findall(r"\w+", t))
        if f_words and t_words:
            overlap = len(f_words.intersection(t_words))
            jaccard = overlap / len(f_words.union(t_words))
            if overlap == len(f_words):
                return 0.90
            if jaccard > 0.4:
                return jaccard

        # 5. Check if candidate snippet contains the focal entity as a primary subject
        if f in s[:120]:
            return 0.50

        # Unrelated entity
        return 0.0

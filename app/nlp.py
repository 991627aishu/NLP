"""Natural Language Processing, Ayurvedic glossary, multilingual normalization, intent routing, and clinical safety triage."""
from __future__ import annotations

import re
from typing import Any
from app.language import detect_language

# --- Canonical Ayurvedic Terminology Dictionary ---
# Covers major Ayurvedic concepts across English, IAST, Devanagari, Kannada, Telugu, and Romanized forms.
AYURVEDA_GLOSSARY: dict[str, dict[str, Any]] = {
    "agni": {
        "canonical": "Agni",
        "category": "Fundamental Concept",
        "description": "Biological fire, digestive capacity, metabolic transformation.",
        "devanagari": "अग्नि",
        "kannada": "ಅಗ್ನಿ",
        "telugu": "అగ్ని",
        "aliases": ["digestive fire", "metabolic fire", "jatharagni", "kosthagni", "digestive power", "jataragni"],
    },
    "vata": {
        "canonical": "Vata",
        "category": "Dosha",
        "description": "Biological humor governing movement, nervous system, respiration, and circulation.",
        "devanagari": "वात",
        "kannada": "ವಾತ",
        "telugu": "వాత",
        "aliases": ["vayu", "vata dosha", "wind humor", "vaatha", "vatham"],
    },
    "pitta": {
        "canonical": "Pitta",
        "category": "Dosha",
        "description": "Biological humor governing heat, metabolism, digestion, biochemical transformation.",
        "devanagari": "पित्त",
        "kannada": "ಪಿತ್ತ",
        "telugu": "పిత్త",
        "aliases": ["pitta dosha", "bile humor", "bile", "pittha", "pittham"],
    },
    "kapha": {
        "canonical": "Kapha",
        "category": "Dosha",
        "description": "Biological humor governing structure, lubrication, cohesion, immunity, and fluid balance.",
        "devanagari": "कफ",
        "kannada": "ಕಫ",
        "telugu": "కఫ",
        "aliases": ["shleshma", "kapha dosha", "phlegm humor", "kaf", "shleshma dosha"],
    },
    "tridosha": {
        "canonical": "Tridosha",
        "category": "Fundamental Concept",
        "description": "The triad of regulatory biological energies: Vata, Pitta, and Kapha.",
        "devanagari": "त्रिदोष",
        "kannada": "ತ್ರಿದೋಷ",
        "telugu": "త్రిదోషాలు",
        "aliases": ["tri-dosha", "three doshas", "doshas", "tridoshas", "thridosha"],
    },
    "ama": {
        "canonical": "Ama",
        "category": "Pathological Factor",
        "description": "Undigested or improperly metabolized toxic residue that obstructs bodily channels.",
        "devanagari": "आम",
        "kannada": "ಆಮ",
        "telugu": "ఆమ",
        "aliases": ["metabolic toxins", "undigested food residue", "toxic residue", "aama", "amadosha"],
    },
    "ojas": {
        "canonical": "Ojas",
        "category": "Vital Essence",
        "description": "Supreme essence of all bodily tissues (dhatus), underlying immunity, vigor, and vitality.",
        "devanagari": "ओजस",
        "kannada": "ಓಜಸ್ಸು",
        "telugu": "ఓజస్సు",
        "aliases": ["vital essence", "immunity essence", "vital energy", "balam", "ojus"],
    },
    "prakriti": {
        "canonical": "Prakriti",
        "category": "Constitutional Typology",
        "description": "Individual psychophysiological constitution established at conception.",
        "devanagari": "प्रकृति",
        "kannada": "ಪ್ರಕೃತಿ",
        "telugu": "ప్రకృతి",
        "aliases": ["constitution", "body type", "ayurvedic constitution", "mind-body type", "prakruti"],
    },
    "vikriti": {
        "canonical": "Vikriti",
        "category": "Pathological State",
        "description": "Current state of doshic imbalance deviating from innate Prakriti.",
        "devanagari": "विकृति",
        "kannada": "ವಿಕೃತಿ",
        "telugu": "వికృతి",
        "aliases": ["imbalance", "doshic imbalance", "state of disease", "vikruti"],
    },
    "rasayana": {
        "canonical": "Rasayana",
        "category": "Therapeutic Discipline",
        "description": "Rejuvenation therapy, tissue nourishment, promoting longevity and optimal cellular health.",
        "devanagari": "रसायन",
        "kannada": "ರಸಾಯನ",
        "telugu": "రసాయన",
        "aliases": ["rejuvenation", "longevity therapy", "rejuvenative therapy", "anti-aging therapy"],
    },
    "dhatu": {
        "canonical": "Dhatu",
        "category": "Anatomy/Physiology",
        "description": "Seven structural bodily tissues: Rasa, Rakta, Mamsa, Meda, Asthi, Majja, and Shukra.",
        "devanagari": "धातु",
        "kannada": "ಧಾತು",
        "telugu": "ధాతు",
        "aliases": ["tissues", "seven tissues", "sapta dhatu", "body tissues", "dhatus"],
    },
    "srotas": {
        "canonical": "Srotas",
        "category": "Anatomy/Physiology",
        "description": "Micro and macro channels carrying nutrients, wastes, and biological fluids.",
        "devanagari": "स्रोतस",
        "kannada": "ಸ್ರೋತಸ್",
        "telugu": "స్రోతస్సులు",
        "aliases": ["body channels", "microchannels", "circulation channels", "channels"],
    },
}

# --- Medicinal Plant & Botanical Cross-Reference Dictionary ---
HERB_CROSS_REFERENCE: dict[str, dict[str, Any]] = {
    "tulsi": {
        "botanical": "Ocimum tenuiflorum",
        "sanskrit": "Tulasi / Surasa",
        "common": "Holy Basil",
        "hindi": "तुलसी",
        "kannada": "ತುಳಸಿ",
        "telugu": "తులసి",
        "aliases": [
            "tulsi", "tulasi", "holy basil", "surasa", "shyama tulsi", "rama tulsi",
            "thulasi", "ocimum sanctum", "ತುಳಸಿ", "ತುಳಸಿಯ", "तुलसी", "తులసి", "తులసిని",
        ],
    },
    "ashwagandha": {
        "botanical": "Withania somnifera",
        "sanskrit": "Ashwagandha",
        "common": "Indian Ginseng / Winter Cherry",
        "hindi": "अश्वगंधा",
        "kannada": "ಅಶ್ವಗಂಧ",
        "telugu": "అశ్వగంధ",
        "aliases": [
            "ashwagandha", "asgandh", "withania", "winter cherry", "indian ginseng",
            "vajigandha", "asvagandha", "ಅಶ್ವಗಂಧ", "ಅಶ್ವಗಂಧದ", "अश्वगंधा", "అశ్వగంధ",
        ],
    },
    "turmeric": {
        "botanical": "Curcuma longa",
        "sanskrit": "Haridra",
        "common": "Turmeric",
        "hindi": "हल्दी",
        "kannada": "ಅರಿಶಿನ",
        "telugu": "పసుపు",
        "aliases": [
            "turmeric", "haldi", "haridra", "curcuma", "curcuma longa", "yellow root",
            "arishina", "pasupu", "हल्दी", "ಅರಿಶಿನ", "పసుపు",
        ],
    },
    "neem": {
        "botanical": "Azadirachta indica",
        "sanskrit": "Nimba",
        "common": "Neem",
        "hindi": "नीम",
        "kannada": "ಬೇವು",
        "telugu": "వేప",
        "aliases": [
            "neem", "nimba", "azadirachta indica", "margosa", "indian lilac",
            "bevu", "vepa", "नीम", "ಬೇವು", "ವೇಪ",
        ],
    },
    "amla": {
        "botanical": "Phyllanthus emblica",
        "sanskrit": "Amalaki",
        "common": "Indian Gooseberry",
        "hindi": "आंवला",
        "kannada": "ನೆಲ್ಲಿಕಾಯಿ",
        "telugu": "ఉసిరి",
        "aliases": [
            "amla", "amalaki", "phyllanthus emblica", "emblica officinalis", "dhatri",
            "indian gooseberry", "nellikai", "usiri", "usirikaya", "आंवला", "ನೆಲ್ಲಿಕಾಯಿ", "ఉసిరి",
        ],
    },
    "giloy": {
        "botanical": "Tinospora cordifolia",
        "sanskrit": "Guduchi",
        "common": "Heart-leaved Moonseed",
        "hindi": "गिलोय",
        "kannada": "ಅಮೃತಬಳ್ಳಿ",
        "telugu": "తిప్పతీగ",
        "aliases": [
            "giloy", "guduchi", "tinospora cordifolia", "amrita", "amrutha balli",
            "tippateega", "गिलोय", "ಅಮೃತಬಳ್ಳಿ", "తిప్పతీగ",
        ],
    },
    "ginger": {
        "botanical": "Zingiber officinale",
        "sanskrit": "Shunthi / Ardraka",
        "common": "Ginger",
        "hindi": "अदरक / सोंठ",
        "kannada": "ಶುಂಠಿ",
        "telugu": "అల్లం",
        "aliases": [
            "ginger", "adrak", "sonth", "shunthi", "ardraka", "zingiber officinale",
            "shunti", "allam", "sonti", "अदरक", "ಶುಂಠಿ", "అల్లం",
        ],
    },
    "brahmi": {
        "botanical": "Bacopa monnieri",
        "sanskrit": "Brahmi",
        "common": "Water Hyssop",
        "hindi": "ब्राह्मी",
        "kannada": "ಬ್ರಾಹ್ಮಿ",
        "telugu": "బ్రహ్మి",
        "aliases": [
            "brahmi", "bacopa monnieri", "water hyssop", "ondelaga", "saraswathi",
            "ब्राह्मी", "ಬ್ರಾಹ್ಮಿ", "బ్రహ్మి",
        ],
    },
    "triphala": {
        "botanical": "Emblica officinalis, Terminalia bellirica, Terminalia chebula",
        "sanskrit": "Triphala",
        "common": "Three Fruits Formula",
        "hindi": "त्रिफला",
        "kannada": "ತ್ರಿಫಲ",
        "telugu": "త్రిఫల",
        "aliases": ["triphala", "three fruits", "त्रिफला", "ತ್ರಿಫಲ", "త్రిఫల"],
    },
}

# --- Multilingual Symptom Synonyms Mapping ---
SYMPTOM_SYNONYM_MAP: dict[str, list[str]] = {
    "fever": [
        "fever", "high temperature", "febrile", "pyrexia", "jwara", "jwar", "bukhar",
        "kaichala", "boodi", "taapa", "ज्वर", "बुखार", "ಜ್ವರ", "ಬಿಸಿ ಮೈ", "జ్వరం", "jwaram", "jvara",
    ],
    "cough": [
        "cough", "coughing", "kasa", "khansi", "kemmu", "khechara", "kasa roga",
        "कास", "खांसी", "ಕೆಮ್ಮು", "ಕಫದ ಕೆಮ್ಮು", "దగ్గు", "daggu", "daggina",
    ],
    "headache": [
        "headache", "head pain", "migraine", "shirashula", "shiroroga", "shira shula",
        "sir dard", "sar dard", "matha dard", "thale novu", "talenovu", "thale bharavaguvudu",
        "सिरदर्द", "सर दर्द", "ತಲೆನೋವು", "ತಲೆ ನೋವು", "తలనొప్పి", "thalanopii", "talanopi",
    ],
    "digestive disorder / indigestion": [
        "indigestion", "dyspepsia", "ajirna", "agnimandya", "acid reflux", "bloating",
        "gas", "heartburn", "pet kharab", "hazma", "badhazmi", "hotte novu", "jeerna samasye",
        "hotte ubbara", "अजीर्ण", "पेट खराब", "बदहजमी", "ಅಜೀರ್ಣ", "ಹೊಟ್ಟೆ ನೋವು", "అజీర్ణం", "ajeernam", "kadupunoppi", "కడుపునొప్పి",
    ],
    "constipation": [
        "constipation", "vibandha", "malabaddhata", "kabz", "pet saaf na hona",
        "mala baddhata", "malamutra krichhra", "baddhavarchas", "मलबद्धता", "कब्ज",
        "ಮಲಬದ್ಧತೆ", "ಮಲ ಕಟ್ಟುವಿಕೆ", "మలబద్ధకం", "malabaddhakam",
    ],
    "joint pain / arthritis": [
        "joint pain", "arthralgia", "arthritis", "sandhivata", "amavata", "joint stiffness",
        "jodo ka dard", "sandhi shula", "gathiya", "keelu novu", "sandhi novu",
        "ಸಂಧಿವಾತ", "ಕೀಲು ನೋವು", "संधिवात", "जोड़ों का दर्द", "కీళ్ల నొప్పులు", "keella noppulu",
    ],
    "cold / rhinitis": [
        "cold", "common cold", "rhinitis", "pratishyaya", "runny nose", "congestion",
        "nazla", "zukam", "sardi", "sheetha", "shardi", "peenasi", "neergattu",
        "प्रतिश्याय", "जुकाम", "ಶೀತ", "ನೆಗಡಿ", "జలుబు", "jalubu",
    ],
    "shortness of breath": [
        "shortness of breath", "dyspnea", "breathlessness", "difficulty breathing",
        "shwasa", "shwasa krichhra", "saans lene me takleef", "dammukattuvudu",
        "saans phoolna", "ಉಸಿರಾಟದ ತೊಂದರೆ", "ಉಬ್ಬಸ", "सांस फूलना", "श्वास", "శ్వాస తీసుకోవడంలో ఇబ్బంది", "oopiri aadaka",
    ],
    "insomnia": [
        "insomnia", "sleeplessness", "sleep disorder", "anidra", "nidranasha",
        "neend na aana", "nidde baradilla", "nidre baralla", "nidde samasye",
        "अनिद्रा", "नींद न आना", "ನಿದ್ರಾಹೀನತೆ", "ನಿದ್ದೆ ಬಾರದಿರುವುದು", "నిద్రలేమి", "nidralemi",
    ],
    "skin rash": [
        "skin rash", "itching", "pruritus", "kandu", "kushtha", "tvak roga",
        "khujli", "daana", "daddalu", "kandu roga", "khaj",
        "खुजली", "चकत्ते", "ತುರಿಕೆ", "ದದ್ದು", "దురద", "గజ్జి", "durada",
    ],
}

# --- Red-Flag Emergency Symptoms for Immediate Triage ---
RED_FLAG_PATTERNS: list[dict[str, Any]] = [
    {
        "pattern": (
            r"\b(?:severe\s+chest\s+pain|chest\s+(?:pain|tightness|pressure|discomfort)|"
            r"crushing\s+(?:pressure|chest)|pressure\s+(?:in|on)\s+(?:my\s+|the\s+)?chest|"
            r"pain\s+radiating\s+to\s+(?:arm|jaw)|hridshula|hridroga|"
            r"sine\s+me\s+(?:tez\s+)?dard|chhati\s+me\s+dard|ede\s+(?:novu|bhaara)|"
            r"గుండె\s*నొప్పి|తీవ్రమైన\s*రొమ్ము\s*నొప్పి|రొమ్ము\s*నొప్పి|gunde\s+noppi)\b"
        ),
        "urgency": "EMERGENCY",
        "warning": (
            "EMERGENCY MEDICAL WARNING: Acute or severe chest pain, tightness, or pain spreading to the arm or jaw "
            "can be a sign of a life-threatening cardiovascular emergency (such as a heart attack). "
            "Please call emergency services (112, 102/108, or local emergency number) or proceed to the nearest emergency room immediately."
        ),
    },
    {
        "pattern": (
            r"\b(?:cannot\s+breathe|unable\s+to\s+breathe|hard\s+to\s+breathe|difficulty\s+(?:in\s+)?breathing|"
            r"trouble\s+breathing|severe\s+shortness\s+of\s+breath|gasping\s+for\s+air|turning\s+blue|"
            r"stridor|asphyxia|severe\s+breathlessness|breathlessness|"
            r"ಉಸಿರಾಡಲು\s*ಆಗುತ್ತಿಲ್ಲ|ಉಸಿರಾಟ\s*ಕಷ್ಟ|ಉಸಿರಾಟದ\s*ತೊಂದರೆ|ಉಸಿರು\s*ಕಟ್ಟುತ್ತಿದೆ|"
            r"శ్వాస\s*తీసుకోలేకపోవడం|శ్వాస\s*కష్టం|ఊపిరి\s*ఆడటం\s*లేదు|oopiri\s+aadakapovadam|"
            r"saans\s+(?:phoolna|rukna|nahi\s+aa\s+rahi))\b"
        ),
        "urgency": "EMERGENCY",
        "warning": (
            "EMERGENCY MEDICAL WARNING: Severe breathing difficulty or sudden inability to breathe is a medical emergency. "
            "Seek immediate emergency medical intervention."
        ),
    },
    {
        "pattern": r"\b(?:sudden\s+paralysis|facial\s+droop|slurred\s+speech|stroke|sudden\s+weakness\s+on\s+one\s+side|loss\s+of\s+consciousness|fainting\s+sudden|ಪಾರ್ಶ್ವವಾಯು|పక్షవాతం|మూతి\s*వంకర|pakshavatham)\b",
        "urgency": "EMERGENCY",
        "warning": (
            "EMERGENCY MEDICAL WARNING: Sudden facial drooping, arm weakness, slurred speech, or acute neurological deficits "
            "are critical signs of a stroke. Time is vital—contact emergency medical services immediately."
        ),
    },
    {
        "pattern": r"\b(?:severe\s+uncontrolled\s+bleeding|coughing\s+up\s+blood|vomiting\s+blood|hematemesis|hemoptysis|రక్తం\s*వాంతి|రక్తం\s*పడటం)\b",
        "urgency": "EMERGENCY",
        "warning": (
            "EMERGENCY MEDICAL WARNING: Coughing up blood, vomiting blood, or severe uncontrolled bleeding requires "
            "immediate hospital emergency care."
        ),
    },
    {
        "pattern": r"\b(?:suicid|kill\s+myself|end\s+my\s+life|self\s*harm|ಆತ್ಮಹತ್ಯೆ|ఆత్మహత్య|chavalanukuntunna|atmahatya)\b",
        "urgency": "CRISIS",
        "warning": (
            "CRISIS SUPPORT: If you or someone you know is in distress or experiencing thoughts of self-harm, please reach out "
            "immediately to a crisis lifeline (National Tele-MANAS helpline in India: 14416 or 1800-891-4416; USA: 988; UK: 111). "
            "Compassionate professional support is available 24/7."
        ),
    },
]


def check_emergency_symptoms(text: str) -> str | None:
    """Evaluate if user text contains red-flag emergency symptoms requiring immediate triage across scripts."""
    cleaned = text.lower()
    has_indic = any(ord(c) > 127 for c in cleaned)
    for item in RED_FLAG_PATTERNS:
        pat = item["pattern"]
        if re.search(pat, cleaned) or (has_indic and re.search(pat.replace(r"\b", ""), cleaned)):
            return item["warning"]
    return None


def _clean_multilingual_text(text: str) -> str:
    """Clean text by stripping punctuation while strictly preserving Indic matras, viramas, and diacritics."""
    import unicodedata
    chars = []
    for char in text:
        cat = unicodedata.category(char)
        if cat.startswith(('P', 'S')):
            chars.append(' ')
        else:
            chars.append(char)
    return " " + " ".join("".join(chars).split()).lower() + " "


def _match_term(term: str, clean_text: str) -> bool:
    """Accurately match terms with ASCII word boundaries, or Indic subword matching for inflected forms."""
    t = term.lower().strip()
    if not t:
        return False
    if t.isascii():
        return bool(re.search(r"(?<![a-zA-Z0-9])" + re.escape(t) + r"(?![a-zA-Z0-9])", clean_text))
    return t in clean_text


def extract_ayurvedic_concepts(text: str) -> list[dict[str, Any]]:
    """Identify recognized Ayurvedic concepts, doshas, and fundamental principles in query."""
    text_clean = _clean_multilingual_text(text)
    found = []
    seen = set()

    for key, data in AYURVEDA_GLOSSARY.items():
        all_terms = [key, data["canonical"].lower()] + [a.lower() for a in data["aliases"]]
        if data.get("devanagari"):
            all_terms.append(data["devanagari"].lower())
        if data.get("kannada"):
            all_terms.append(data["kannada"].lower())
        if data.get("telugu"):
            all_terms.append(data["telugu"].lower())

        for term in all_terms:
            if _match_term(term, text_clean) and key not in seen:
                seen.add(key)
                found.append({
                    "id": key,
                    "canonical": data["canonical"],
                    "category": data["category"],
                    "description": data["description"],
                    "devanagari": data.get("devanagari", ""),
                    "kannada": data.get("kannada", ""),
                    "telugu": data.get("telugu", ""),
                })
                break
    return found


def extract_herbs(text: str) -> list[dict[str, Any]]:
    """Detect mentions of medicinal plants across botanical, Sanskrit, Hindi, Kannada, Telugu, and Romanized aliases."""
    text_clean = _clean_multilingual_text(text)
    found = []
    seen = set()

    for herb_key, herb_data in HERB_CROSS_REFERENCE.items():
        all_names = [herb_key, herb_data["botanical"].lower(), herb_data["common"].lower()] + [
            a.lower() for a in herb_data["aliases"]
        ]
        if herb_data.get("hindi"):
            all_names.append(herb_data["hindi"].lower())
        if herb_data.get("kannada"):
            all_names.append(herb_data["kannada"].lower())
        if herb_data.get("telugu"):
            all_names.append(herb_data["telugu"].lower())

        for name in all_names:
            if _match_term(name, text_clean) and herb_key not in seen:
                seen.add(herb_key)
                found.append({
                    "herb_id": herb_key,
                    "botanical": herb_data["botanical"],
                    "sanskrit": herb_data["sanskrit"],
                    "common": herb_data["common"],
                    "hindi": herb_data.get("hindi", ""),
                    "kannada": herb_data.get("kannada", ""),
                    "telugu": herb_data.get("telugu", ""),
                })
                break
    return found


def extract_symptoms(text: str) -> list[str]:
    """Map user query words (including Hindi/Kannada/Telugu script and Hinglish/Kanglish) to canonical symptoms."""
    text_clean = _clean_multilingual_text(text)
    matched_canonical = []

    for canonical, synonyms in SYMPTOM_SYNONYM_MAP.items():
        for syn in synonyms:
            if _match_term(syn, text_clean):
                matched_canonical.append(canonical)
                break

    return matched_canonical


def is_ambiguous_query(text: str) -> tuple[bool, str]:
    """Detect overly vague, single-word, or ambiguous medical queries that need clarification."""
    cleaned = re.sub(r"[^\w\s]", "", text.strip().lower())
    words = cleaned.split()

    if len(words) <= 1:
        single = words[0] if words else ""
        vague_terms = {
            "pain", "help", "cure", "medicine", "doctor", "ayurveda", "disease",
            "treatment", "illness", "symptom", "problem", "dawa", "ilaj", "dard",
            "aushadhi", "beemari", "roga", "chikitsa", "upachara", "mandulu", "nopi",
        }
        if single in vague_terms:
            return True, (
                f"Your query '{text}' is very broad. To provide grounded evidence, could you specify which "
                "symptom (e.g., 'fever and cough'), medicinal herb (e.g., 'Tulsi traditional uses'), "
                "or Ayurvedic concept (e.g., 'What is Agni?') you are exploring?"
            )

    return False, ""


def classify_query_intent(
    query: str,
    detected_herbs: list[dict[str, Any]],
    detected_symptoms: list[str],
    detected_concepts: list[dict[str, Any]],
) -> str:
    """
    Intelligently classify user intent into:
    - 'herbs': user asks about medicinal plants, traditional uses, preparation, parts.
    - 'disease': user describes health complaints/symptoms or asks condition matching.
    - 'general': user asks about fundamental Ayurvedic principles (Doshas, Agni, Ama, Ojas).
    - 'diet_lifestyle': user asks about dinacharya, pathya, apathya, dietary guidance.
    - 'ambiguous': broad single-word query requiring clarification.
    """
    low = " " + query.lower() + " "

    # 1. Broad ambiguous query check
    is_ambig, _ = is_ambiguous_query(query)
    if is_ambig:
        return "ambiguous"

    # 2. Herb Query Pattern: Herb is present AND user asks about uses, benefits, properties
    use_keywords = {
        "use", "uses", "upayoga", "upayogagalu", "upayogam", "upayogalu", "fayde", "fayda",
        "labh", "benefit", "benefits", "properties", "how to use", "prepare", "powder",
        "leaf", "leaves", "root", "stem", "decoction", "kashaya", "kadha", "tea", "oil",
        "dose", "dosage", "side effects", "what is", "what are", "उಪಯೋಗ", "ಪ್ರಯೋಜನ",
        "फायदे", "लाभ", "उपयोग", "ఉపయోగాలు", "ఉపయోగం", "ప్రయోజనాలు", "వినియోగం",
    }
    has_use_keyword = any(kw in low for kw in use_keywords)

    if detected_herbs and (has_use_keyword or not detected_symptoms):
        return "herbs"

    # 3. Symptom Query Pattern: User describes suffering or lists clinical symptoms
    symptom_cues = {
        "i have", "suffering", "feeling", "pain", "fever", "cough", "sir dard", "bukhar",
        "thale novu", "kemmu", "hotte novu", "jwaram", "daggu", "thalanopii", "complaint",
        "treatment for", "cure for", "how to treat", "illness", "disease", "condition",
        "ನೋವು", "ಜ್ವರ", "ಕೆಮ್ಮು", "दर्द", "बुखार", "खांसी", "నొప్పి", "జ్వరం", "దగ్గు",
    }
    has_symptom_cue = any(cue in low for cue in symptom_cues)
    if detected_symptoms or has_symptom_cue:
        return "disease"

    # 4. General Ayurveda Principles Pattern (Agni, Doshas, Ama, Ojas, etc.)
    if detected_concepts:
        return "general"

    # 5. Herb Mention fallback
    if detected_herbs:
        return "herbs"

    # 6. Default to general knowledge
    return "general"


def normalize_query_for_retrieval(query: str) -> dict[str, Any]:
    """
    Comprehensive query understanding pipeline.
    Preserves original text, identifies language & script (English, Hindi, Kannada, Telugu),
    extracts herbs, symptoms, concepts, classifies intent, and constructs expanded retrieval query.
    """
    original = str(query or "").strip()
    lang_info = detect_language(original)
    emergency_warning = check_emergency_symptoms(original)
    is_ambiguous, clarification_prompt = is_ambiguous_query(original)

    detected_herbs = extract_herbs(original)
    detected_concepts = extract_ayurvedic_concepts(original)
    detected_symptoms = extract_symptoms(original)

    # Classify Intent
    intent = classify_query_intent(
        original, detected_herbs, detected_symptoms, detected_concepts
    )

    # Build expanded search tokens
    expansion_terms = set()
    for herb in detected_herbs:
        expansion_terms.add(herb["botanical"].lower())
        expansion_terms.add(herb["common"].lower())

    for symptom in detected_symptoms:
        expansion_terms.add(symptom)

    for concept in detected_concepts:
        expansion_terms.add(concept["canonical"].lower())

    # Build clean retrieval query
    retrieval_query = original
    if expansion_terms:
        clean_norm = original.lower()
        additions = [term for term in expansion_terms if term not in clean_norm]
        if additions:
            retrieval_query = f"{original} {' '.join(additions[:4])}"

    return {
        "original_query": original,
        "retrieval_query": retrieval_query,
        "detected_language": lang_info["language"],
        "detected_script": lang_info["script"],
        "language_info": lang_info,
        "intent": intent,
        "emergency_warning": emergency_warning,
        "is_ambiguous": is_ambiguous,
        "clarification_prompt": clarification_prompt,
        "detected_herbs": detected_herbs,
        "detected_concepts": detected_concepts,
        "detected_symptoms": detected_symptoms,
    }

"""
AyurMitra — Pre-retrieval Safety Gate (fixes audit F15 / F16)
==============================================================
Before Phase 1 the chat pipeline abstained ONLY when zero passages were
retrieved, so emergencies ("sudden severe headache"), dosage requests and the
benchmark's unanswerable prompts were answered normally (0/16 abstained).

This gate runs before retrieval in every configuration (B0/B1/P1/P2), so it does
not bias the B1-vs-P1 comparison. It is deliberately conservative and
rule-based; it does not diagnose anything. Categories:

* ``emergency_symptom_detected`` — acute red flags (reuses
  ``symptom_mapper.EMERGENCY_RED_FLAGS`` + intensity patterns). Always wins.
* ``dosage_or_prescription_request`` — "how much/how many … should I take",
  dose/dosage/mg, "prescribe me …".
* ``toxic_substance_request`` — ingesting raw mercury/arsenic/lead/poison.
* ``unsupported_cure_claim`` — "can X cure cancer/HIV/diabetes…".

Design honesty note: the rules were written knowing the 3 *dev-split*
unanswerable seeds; the 2 *test-split* unanswerable seeds were not inspected.

Hindi/Kannada message text below is project-written UI text and should be
reviewed by a native speaker (see docs/KNOWN_LIMITATIONS.md).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional

from app.core.symptom_mapper import EMERGENCY_RED_FLAGS, EMERGENCY_ADVISORIES

NUKTA = "़"


def normalize_for_matching(text: str) -> str:
    """NFC, lower-case, strip Devanagari nukta (ज़ → ज), unify chandrabindu/anusvara, squeeze spaces."""
    t = unicodedata.normalize("NFC", text or "")
    t = unicodedata.normalize("NFD", t).replace(NUKTA, "")
    t = unicodedata.normalize("NFC", t)
    t = t.replace("ँ", "ं")  # chandrabindu → anusvara (सांस / साँस)
    t = t.replace("‌", "").replace("‍", "")  # ZWNJ/ZWJ (common in Kannada typing)
    return re.sub(r"\s+", " ", t.lower()).strip()


# ── Additional emergency patterns (generic intensity + symptom) ──────────────
_EMERGENCY_REGEXES = [
    re.compile(r"\b(sudden|severe|worst|extreme|unbearable|intense|excruciating)\b(\W+\w+){0,3}\W+(headache|head ache|chest pain|abdominal pain|stomach pain|bleeding)"),
    re.compile(r"\b(can'?t|cannot|unable to|trouble|difficulty)\s+(breathe|breathing)\b"),
    re.compile(r"\b(heart attack|stroke|seizure|convulsion|unconscious|passed out|overdose|poisoning|anaphyla\w*|suicid\w*|kill myself|self[- ]harm)\b"),
    re.compile(r"\b(blood in (vomit|stool|urine)|vomiting blood|coughing (up )?blood)\b"),
    # Hindi (Devanagari, nukta-normalised)
    re.compile(r"(अचानक|तेज|गंभीर|भयंकर|असहनीय)\s*(\S+\s+){0,2}(सिरदर्द|सिर दर्द|सीने में दर्द|छाती में दर्द|पेट में दर्द|खून)"),
    re.compile(r"(सांस नहीं|सांस लेने में (तकलीफ|दिक्कत|परेशानी)|बेहोश|दिल का दौरा|आत्महत्या|जहर खा)"),
    # Kannada
    re.compile(r"(ಹಠಾತ್|ತೀವ್ರ|ವಿಪರೀತ|ಅತಿಯಾದ)\s*(\S+\s+){0,2}(ತಲೆನೋವು|ತಲೆ ನೋವು|ಎದೆ ನೋವು|ಹೊಟ್ಟೆ ನೋವು|ರಕ್ತಸ್ರಾವ)"),
    re.compile(r"(ಉಸಿರಾಡಲು ಆಗುತ್ತಿಲ್ಲ|ಉಸಿರಾಟದ ತೊಂದರೆ|ಪ್ರಜ್ಞೆ ತಪ್ಪಿ|ಹೃದಯಾಘಾತ|ಆತ್ಮಹತ್ಯೆ)"),
    # Romanized Hindi / Kannada
    re.compile(r"\b(achanak|tez|bahut tez|bhayankar)\s+(sir ?dard|seene (me|mein) dard)\b"),
    re.compile(r"\b(saans nahi|saans lene (me|mein) (takleef|dikkat)|behosh)\b"),
]

_MEDICINE = (r"(medicine|medication|drug|tablet|capsule|pill|churna|churnam|powder|herb|herbal|supplement|kashay\w*|decoction|"
             r"arishta|asava|bhasma|vati|guggul\w*|ashwagandha|triphala|tulsi|giloy|guduchi|brahmi|shatavari|neem|turmeric|"
             r"haldi|amla|amalaki|mercury|parad|rasa ?aushadhi|formulation|remedy)")

_DOSAGE_REGEXES = [
    re.compile(r"\b(dose|doses|dosage|dosing|posology)\b"),
    re.compile(r"\bhow (much|many)\b(?=.{0,80}\b(take|consume|eat|drink|ingest|give|use|have)\b)(?=.{0,80}" + _MEDICINE + r")"),
    re.compile(r"\b\d+(\.\d+)?\s*(mg|mcg|ml|g|gm|grams?|tablets?|capsules?|teaspoons?|tsp|tbsp)\b.{0,30}\b(per day|daily|a day|times)\b"),
    re.compile(r"\b(prescribe|prescription|write me (a )?medicine|which (medicine|drug|tablet) should i take|what (medicine|drug|tablet) should i take)\b"),
    # Hindi
    re.compile(r"(खुराक|डोज|नुस्खा|नुस्खे|दवा लिख|दवाएं लिख|दवाई लिख|कितनी मात्रा|कितना \S+ (लेना|खाना|पीना|सेवन)|कितनी \S+ (लेनी|खानी|पीनी)|कितनी बार)"),
    # Kannada
    re.compile(r"(ಡೋಸ್|ಡೋಸೇಜ್|ಪ್ರಿಸ್ಕ್ರಿಪ್ಷನ್|ಔಷಧಿ ಬರೆದು|ಎಷ್ಟು (ಪ್ರಮಾಣ|ಗ್ರಾಂ|ಮಾತ್ರೆ|ಚಮಚ)|ಎಷ್ಟು \S+ (ಸೇವಿಸ|ತೆಗೆದುಕೊಳ್ಳ|ಕುಡಿಯ|ತಿನ್ನ))"),
    # Romanized
    re.compile(r"\b(khurak|khuraak|kitna (khana|lena|peena|khaye|le|lu)|kitni (goli|matra)|eshtu (tegedukolla|sevisa))\b"),
]

_TOXIC_REGEXES = [
    re.compile(r"\b(raw|pure|liquid|elemental)\s+(mercury|quicksilver|arsenic|lead)\b"),
    re.compile(r"\b(ingest|eat|drink|swallow|consume)\w*\b.{0,40}\b(mercury|arsenic|cyanide|lead|poison|bleach|kerosene|pesticide)\b"),
    re.compile(r"\b(mercury|arsenic|cyanide|poison|bleach|kerosene|pesticide)\b.{0,40}\b(ingest|eat|drink|swallow|consume)\w*"),
    re.compile(r"(कच्चा पारा|पारा (खा|पी|सेवन)|आर्सेनिक|संखिया|जहर (खा|पी))"),
    re.compile(r"(ಕಚ್ಚಾ ಪಾದರಸ|ಪಾದರಸವನ್ನು ಸೇವಿಸ|ವಿಷ ಕುಡಿ)"),
    re.compile(r"\b(raw mercury|parad khana|para khana)\b"),
]

_SERIOUS_DISEASE = r"(cancer|tumou?r|hiv|aids|tuberculosis|\btb\b|covid|diabetes|kidney failure|heart disease|stroke|appendicitis|hepatitis|malaria|dengue|sepsis)"
_CURE_REGEXES = [
    re.compile(r"\b(cure|cures|curing|permanently treat|reverse|eliminate|get rid of)\b.{0,60}" + _SERIOUS_DISEASE),
    re.compile(_SERIOUS_DISEASE + r".{0,60}\b(cured|cure|curable|reversed)\b"),
    re.compile(r"(कैंसर|मधुमेह|डायबिटीज|टीबी|एड्स).{0,40}(ठीक|इलाज|खत्म)"),
    re.compile(r"(ಕ್ಯಾನ್ಸರ್|ಮಧುಮೇಹ|ಕ್ಷಯ|ಏಡ್ಸ್).{0,40}(ಗುಣ|ವಾಸಿ)"),
]

MESSAGES: Dict[str, Dict[str, str]] = {
    "dosage_or_prescription_request": {
        "en": ("AyurMitra cannot provide doses, quantities or prescriptions. Dosage depends on the individual, the "
               "preparation and the clinical situation, and must be decided by a qualified Ayurveda practitioner (BAMS) "
               "or doctor who has examined you. I can explain the related Ayurvedic concepts in general, educational terms."),
        "hi": ("आयुर्मित्र खुराक, मात्रा या दवा का नुस्खा नहीं दे सकता। खुराक व्यक्ति, औषधि-निर्माण और स्वास्थ्य स्थिति पर निर्भर "
               "करती है और इसे आपकी जाँच करने वाले योग्य आयुर्वेद चिकित्सक (BAMS) या डॉक्टर को ही तय करना चाहिए। "
               "मैं संबंधित आयुर्वेदिक अवधारणाओं को सामान्य, शैक्षिक रूप में समझा सकता हूँ।"),
        "kn": ("ಆಯುರ್ಮಿತ್ರವು ಡೋಸ್, ಪ್ರಮಾಣ ಅಥವಾ ಔಷಧಿ ಚೀಟಿಯನ್ನು ನೀಡಲು ಸಾಧ್ಯವಿಲ್ಲ. ಡೋಸ್ ವ್ಯಕ್ತಿ, ಔಷಧ ತಯಾರಿಕೆ ಮತ್ತು ಆರೋಗ್ಯ "
               "ಸ್ಥಿತಿಯನ್ನು ಅವಲಂಬಿಸಿರುತ್ತದೆ; ನಿಮ್ಮನ್ನು ಪರೀಕ್ಷಿಸಿದ ಅರ್ಹ ಆಯುರ್ವೇದ ವೈದ್ಯರು (BAMS) ಅಥವಾ ವೈದ್ಯರು ಮಾತ್ರ ಇದನ್ನು "
               "ನಿರ್ಧರಿಸಬೇಕು. ಸಂಬಂಧಿತ ಆಯುರ್ವೇದ ಪರಿಕಲ್ಪನೆಗಳನ್ನು ನಾನು ಸಾಮಾನ್ಯ, ಶೈಕ್ಷಣಿಕ ರೂಪದಲ್ಲಿ ವಿವರಿಸಬಲ್ಲೆ."),
    },
    "toxic_substance_request": {
        "en": ("AyurMitra will not give guidance on ingesting mercury, arsenic, lead or other toxic substances. Raw heavy "
               "metals are poisonous. If someone has swallowed one, contact a poison-control centre or emergency services now."),
        "hi": ("आयुर्मित्र पारा, आर्सेनिक, सीसा या अन्य विषैले पदार्थ खाने के बारे में कोई मार्गदर्शन नहीं देगा। कच्ची भारी धातुएँ "
               "विषैली होती हैं। यदि किसी ने इन्हें निगल लिया है, तो तुरंत आपातकालीन सेवा या विष-नियंत्रण केंद्र से संपर्क करें।"),
        "kn": ("ಪಾದರಸ, ಆರ್ಸೆನಿಕ್, ಸೀಸ ಅಥವಾ ಇತರ ವಿಷಕಾರಿ ವಸ್ತುಗಳನ್ನು ಸೇವಿಸುವ ಬಗ್ಗೆ ಆಯುರ್ಮಿತ್ರ ಯಾವುದೇ ಮಾರ್ಗದರ್ಶನ ನೀಡುವುದಿಲ್ಲ. "
               "ಕಚ್ಚಾ ಭಾರ ಲೋಹಗಳು ವಿಷಕಾರಿ. ಯಾರಾದರೂ ಅವನ್ನು ನುಂಗಿದ್ದರೆ, ತಕ್ಷಣ ತುರ್ತು ಸೇವೆ ಅಥವಾ ವಿಷ ನಿಯಂತ್ರಣ ಕೇಂದ್ರವನ್ನು ಸಂಪರ್ಕಿಸಿ."),
    },
    "unsupported_cure_claim": {
        "en": ("AyurMitra cannot say that any herb, food or practice cures this condition. Traditional records describe "
               "historical use; they are not proof of efficacy or safety. Serious illnesses need care from a qualified "
               "doctor. I can explain related Ayurvedic concepts in an educational way."),
        "hi": ("आयुर्मित्र यह नहीं कह सकता कि कोई जड़ी-बूटी, आहार या उपाय इस रोग को ठीक कर देता है। पारंपरिक ग्रंथ ऐतिहासिक उपयोग "
               "बताते हैं; वे प्रभावशीलता या सुरक्षा का प्रमाण नहीं हैं। गंभीर रोगों में योग्य डॉक्टर से उपचार लें। "
               "मैं संबंधित आयुर्वेदिक अवधारणाएँ शैक्षिक रूप में समझा सकता हूँ।"),
        "kn": ("ಯಾವುದೇ ಗಿಡಮೂಲಿಕೆ, ಆಹಾರ ಅಥವಾ ಪದ್ಧತಿ ಈ ಕಾಯಿಲೆಯನ್ನು ಗುಣಪಡಿಸುತ್ತದೆ ಎಂದು ಆಯುರ್ಮಿತ್ರ ಹೇಳಲಾರದು. ಸಾಂಪ್ರದಾಯಿಕ "
               "ದಾಖಲೆಗಳು ಐತಿಹಾಸಿಕ ಬಳಕೆಯನ್ನು ವಿವರಿಸುತ್ತವೆ; ಅವು ಪರಿಣಾಮಕಾರಿತ್ವ ಅಥವಾ ಸುರಕ್ಷತೆಯ ಪುರಾವೆಯಲ್ಲ. ಗಂಭೀರ ಕಾಯಿಲೆಗಳಿಗೆ "
               "ಅರ್ಹ ವೈದ್ಯರಿಂದ ಚಿಕಿತ್ಸೆ ಪಡೆಯಿರಿ."),
    },
    "insufficient_evidence": {
        "en": ("I could not find passages in AyurMitra's sources that address this question, so I won't guess. "
               "Try rephrasing with a specific Ayurvedic concept, or consult a qualified practitioner."),
        "hi": ("आयुर्मित्र के स्रोतों में इस प्रश्न से संबंधित अंश नहीं मिले, इसलिए मैं अनुमान नहीं लगाऊँगा। किसी विशिष्ट "
               "आयुर्वेदिक अवधारणा के साथ प्रश्न दोबारा पूछें, या योग्य चिकित्सक से परामर्श लें।"),
        "kn": ("ಆಯುರ್ಮಿತ್ರದ ಮೂಲಗಳಲ್ಲಿ ಈ ಪ್ರಶ್ನೆಗೆ ಸಂಬಂಧಿಸಿದ ಭಾಗಗಳು ಸಿಗಲಿಲ್ಲ, ಆದ್ದರಿಂದ ನಾನು ಊಹಿಸುವುದಿಲ್ಲ. ನಿರ್ದಿಷ್ಟ "
               "ಆಯುರ್ವೇದ ಪರಿಕಲ್ಪನೆಯೊಂದಿಗೆ ಮತ್ತೆ ಕೇಳಿ, ಅಥವಾ ಅರ್ಹ ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ."),
    },
}

_RED_FLAG_SET: List[str] = sorted({normalize_for_matching(f) for flags in EMERGENCY_RED_FLAGS.values() for f in flags},
                                  key=len, reverse=True)


def _first_match(regexes, text: str) -> Optional[str]:
    for rx in regexes:
        m = rx.search(text)
        if m:
            return m.group(0)
    return None


def check_query_safety(query: str) -> Dict[str, Any]:
    """Return {'blocked': bool, 'reason': str|None, 'matched': str|None, 'severity': 'emergency'|'refuse'|None}."""
    t = normalize_for_matching(query)
    if not t:
        return {"blocked": False, "reason": None, "matched": None, "severity": None}

    for flag in _RED_FLAG_SET:
        if flag and flag in t:
            return {"blocked": True, "reason": "emergency_symptom_detected", "matched": flag, "severity": "emergency"}
    m = _first_match(_EMERGENCY_REGEXES, t)
    if m:
        return {"blocked": True, "reason": "emergency_symptom_detected", "matched": m, "severity": "emergency"}
    m = _first_match(_TOXIC_REGEXES, t)
    if m:
        return {"blocked": True, "reason": "toxic_substance_request", "matched": m, "severity": "refuse"}
    m = _first_match(_DOSAGE_REGEXES, t)
    if m:
        return {"blocked": True, "reason": "dosage_or_prescription_request", "matched": m, "severity": "refuse"}
    m = _first_match(_CURE_REGEXES, t)
    if m:
        return {"blocked": True, "reason": "unsupported_cure_claim", "matched": m, "severity": "refuse"}
    return {"blocked": False, "reason": None, "matched": None, "severity": None}


def safety_message(reason: str, lang: str = "en") -> str:
    lang = lang if lang in ("en", "hi", "kn") else "en"
    if reason == "emergency_symptom_detected":
        return EMERGENCY_ADVISORIES.get(lang, EMERGENCY_ADVISORIES["en"])
    return MESSAGES.get(reason, MESSAGES["insufficient_evidence"]).get(lang, MESSAGES["insufficient_evidence"]["en"])

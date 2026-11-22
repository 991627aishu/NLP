"""
AyurMitra — Multilingual Educational Symptom-to-Concept Mapper
===============================================================
Maps user-reported symptom descriptions across English, Hindi (Devanagari),
Kannada script, Hinglish, and Kanglish to classical Ayurvedic physiological
concepts (Doshas: Vata, Pitta, Kapha; Agni status) without asserting medical
diagnosis or clinical certainty.

Strict safety & governance rules:
  1. Educational reference only; strictly non-diagnostic.
  2. Immediate emergency red-flag safety check before concept mapping:
     severe/sudden headache, chest pain, breathing distress, stroke/neurological
     signs must NEVER be assigned to a Dosha. They trigger urgent care advisories.
  3. Safe abstention on ambiguous, vague, or unverified symptom inputs.
  4. Traceable source provenance (WHO Benchmark, NAMASTE Table A) for every mapping.
  5. Language-consistent localized responses:
     - English input -> English output
     - Hindi (Devanagari) -> Hindi output
     - Kannada script -> Kannada output
     - Hinglish (Romanized Hindi) -> Hinglish output
     - Kanglish (Romanized Kannada) -> Kanglish output
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import EDUCATIONAL_DISCLAIMER
from app.core.knowledge_graph import AyurKnowledgeGraph
from app.core.language_detect import detect

# ─────────────────────────────────────────────────────────────────────────────
# 1. EMERGENCY RED-FLAG SYMPTOM LISTS (Multilingual)
# ─────────────────────────────────────────────────────────────────────────────
EMERGENCY_RED_FLAGS = {
    "en": [
        "severe headache", "sudden headache", "worst headache", "thunderclap headache",
        "chest pain", "tightness in chest", "difficulty breathing", "shortness of breath",
        "unconscious", "loss of consciousness", "fainting", "vomiting blood", "coughing blood",
        "severe bleeding", "paralysis", "stroke", "sudden numbness", "facial droop",
        "convulsions", "seizures", "severe head injury", "head injury", "blurred vision sudden"
    ],
    "hi": [
        "तेज सिरदर्द", "गंभीर सिरदर्द", "सिर में तेज दर्द", "अचानक सिरदर्द", "भयंकर सिरदर्द",
        "सीने में दर्द", "छाती में दर्द", "सांस लेने में तकलीफ", "दम फूलना", "खून की उल्टी",
        "अत्यधिक रक्तस्राव", "बेहोशी", "दौरा", "पक्षाघात", "लकवा", "सिर में गंभीर चोट"
    ],
    "kn": [
        "ತೀವ್ರ ತಲೆನೋವು", "ಅತಿಯಾದ ತಲೆನೋವು", "ತೀವ್ರವಾದ ತಲೆನೋವು", "ಹಠಾತ್ ತಲೆನೋವು",
        "ಎದೆ ನೋವು", "ಉಸಿರಾಟದ ತೊಂದರೆ", "ಉಸಿರುಗಟ್ಟುವುದು", "ರಕ್ತ ವಾಂತಿ", "ತೀವ್ರ ರಕ್ತಸ್ರಾವ",
        "ಪ್ರಜ್ಞಾಹೀನತೆ", "ಪಾರ್ಶ್ವವಾಯು", "ಸೆಳೆತ", "ಫಿಟ್ಸ್", "ತಲೆಗೆ ತೀವ್ರ ಗಾಯ"
    ],
    "hi_roman": [
        "severe headache", "tez sirdard", "tez sir dard", "bhayankar sir dard", "bhayankar sirdard",
        "seene me dard", "chhati me dard", "saans lene me takleef", "khoon ki ulti",
        "behoshi", "daura", "lakwa", "sir me chot"
    ],
    "kn_roman": [
        "severe headache", "tivra tale novu", "tumba tale novu", "severe tale novu", "ede novu",
        "usiratada tondare", "rakta vaanti", "prajnaheenate", "seleta"
    ]
}

# ─────────────────────────────────────────────────────────────────────────────
# 2. LOCALIZED EMERGENCY ADVISORIES
# ─────────────────────────────────────────────────────────────────────────────
EMERGENCY_ADVISORIES = {
    "en": (
        "URGENT HEALTH ADVISORY: The described symptom (such as severe/sudden headache, chest distress, "
        "or breathing difficulty) may indicate an acute or severe medical emergency requiring immediate professional "
        "medical evaluation. Please seek emergency medical care promptly. "
        "AyurMitra is an educational tool and does not manage or diagnose acute emergencies."
    ),
    "hi": (
        "तत्काल स्वास्थ्य परामर्श चेतावनी: वर्णित लक्षण (जैसे तेज या अचानक गंभीर सिरदर्द, सीने में दर्द, "
        "या सांस लेने में तकलीफ) किसी गंभीर चिकित्सीय आपातकालीन स्थिति का संकेत हो सकते हैं। "
        "कृपया बिना किसी देरी के तत्काल आपातकालीन चिकित्सा सहायता या चिकित्सक से संपर्क करें। "
        "आयुर्मित्र एक शैक्षिक प्रणाली है और आपातकालीन स्थितियों का निदान या उपचार नहीं करती है।"
    ),
    "kn": (
        "ತುರ್ತು ಆರೋಗ್ಯ ಸಲಹಾ ಎಚ್ಚರಿಕೆ: ವಿವರಿಸಲಾದ ಲಕ್ಷಣಗಳು (ತೀವ್ರ ಅಥವಾ ಹಠಾತ್ ತಲೆನೋವು, ಎದೆ ನೋವು, "
        "ಅಥವಾ ಉಸಿರಾಟದ ತೊಂದರೆಯಂತಹವು) ತುರ್ತು ವೃತ್ತಿಪರ ಮೌಲ್ಯಮಾಪನದ ಅಗತ್ಯವಿರುವ ಗಂಭೀರ ವೈದ್ಯಕೀಯ ಸ್ಥಿತಿಯನ್ನು ಸೂಚಿಸಬಹುದು. "
        "ದಯವಿಟ್ಟು ತಕ್ಷಣವೇ ತುರ್ತು ವೈದ್ಯಕೀಯ ನೆರವನ್ನು ಪಡೆಯಿರಿ. "
        "ಆಯುರ್ಮಿತ್ರವು ಕೇವಲ ಶೈಕ್ಷಣಿಕ ಸಾಧನವಾಗಿದ್ದು, ತುರ್ತು ಸಂದರ್ಭಗಳನ್ನು ನಿರ್ವಹಿಸುವುದಿಲ್ಲ ಅಥವಾ ರೋಗನಿರ್ಣಯ ಮಾಡುವುದಿಲ್ಲ."
    ),
    "hi_roman": (
        "URGENT HEALTH ADVISORY: Yeh symptoms (jaise tez sirdard / severe headache, seene me dard, "
        "ya saans lene me takleef) kisi acute medical emergency ka sanket ho sakte hain. "
        "Kripya turant qualified doctor ya emergency healthcare service se sampark karein. "
        "AyurMitra keval educational tool hai aur emergency medical conditions ko manage nahi karta."
    ),
    "kn_roman": (
        "URGENT HEALTH ADVISORY: Ee lakshanagalu (severe tale novu, ede novu, athava usiratada tondare) "
        "gambhira vaidyakeeya thondareyannu suchisabahudu. "
        "Dayavittu thakshana qualified doctor athava emergency hospitalannu samparkisi. "
        "AyurMitra kevala educational tool aagiddu, emergency situationsannu treat maduvudilla."
    )
}

# ─────────────────────────────────────────────────────────────────────────────
# 3. LOCALIZED ABSTENTION MESSAGES
# ─────────────────────────────────────────────────────────────────────────────
ABSTENTION_MESSAGES = {
    "en": (
        "Abstention: The provided description could not be reliably mapped to catalogued Ayurvedic concepts "
        "in the verified source literature (WHO Benchmark / NAMASTE). Please describe specific non-acute sensations "
        "(such as dry skin, burning sensation, or sluggish digestion), or consult a qualified physician."
    ),
    "hi": (
        "अस्वीकरण (Abstention): दिया गया विवरण प्रमाणित आयुर्वेदिक साहित्य (WHO Benchmark / NAMASTE) में "
        "सूचीबद्ध शास्त्रीय अवधारणाओं से विश्वसनीय रूप से मेल नहीं खाता है। कृपया स्पष्ट गैर-आपातकालीन अनुभूतियों "
        "(जैसे रूखी त्वचा, सीने में जलन, या मंद पाचन) का वर्णन करें अथवा चिकित्सक से परामर्श लें।"
    ),
    "kn": (
        "ತಿರಸ್ಕಾರ ಸೂಚನೆ (Abstention): ಒದಗಿಸಲಾದ ವಿವರಣೆಯು ಪರಿಶೀಲಿಸಿದ ಆಯುರ್ವೇದ ಮೂಲ ಸಾಹಿತ್ಯದಲ್ಲಿನ (WHO Benchmark / NAMASTE) "
        "ಪರಿಕಲ್ಪನೆಗಳಿಗೆ ವಿಶ್ವಾಸಾರ್ಹವಾಗಿ ಹೊಂದಿಕೆಯಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ನಿರ್ದಿಷ್ಟ ಲಕ್ಷಣಗಳನ್ನು ವಿವರಿಸಿ "
        "(ಉದಾಹರಣೆಗೆ ಒಣ ಚರ್ಮ, ಎದೆಯುರಿ, ಅಥವಾ ಮಂದ ಜೀರ್ಣಕ್ರಿಯೆ), ಅಥವಾ ಅರ್ಹ ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ."
    ),
    "hi_roman": (
        "Abstention: Diya gaya description verified Ayurvedic literature (WHO / NAMASTE) ke classical concepts se "
        "reliably match nahi hota hai. Kripya specific non-acute sensations (jaise dry skin, burning sensation, "
        "ya sluggish digestion) describe karein ya physician se consult karein."
    ),
    "kn_roman": (
        "Abstention: Vivarisiruva details verified Ayurvedic literature (WHO / NAMASTE) conceptsge reliably match aaguttilla. "
        "Dayavittu specific sensations (dry skin, uri, athava sluggish digestion) vivarisi athava doctor consult maadi."
    )
}

# ─────────────────────────────────────────────────────────────────────────────
# 4. CLASSICAL SYMPTOM CATALOG WITH MULTILINGUAL PROVENANCE
# ─────────────────────────────────────────────────────────────────────────────
# Each symptom item defines:
#   - dosha: "Vata" | "Pitta" | "Kapha"
#   - source_id: Primary classical source citation
#   - locator: Page / Section code
#   - patterns: Dict of language keys -> list of lowercase symptom phrases
#   - notes: Dict of language keys -> educational explanation
CLASSICAL_SYMPTOM_CATALOG: List[Dict[str, Any]] = [
    # ── VATA SYMPTOMS ────────────────────────────────────────────────────────
    {
        "concept_key": "dry_skin",
        "dosha": "Vata",
        "source_id": "WHO_9789240064935",
        "locator": "page 45",
        "patterns": {
            "en": ["dry skin", "rough skin", "skin dryness", "chapped skin"],
            "hi": ["रूखी त्वचा", "सूखी त्वचा", "त्वचा का रूखापन", "त्वचा में सूखापन"],
            "kn": ["ಒಣ ಚರ್ಮ", "ಚರ್ಮದ ಒಣಗುವಿಕೆ", "ಚರ್ಮ ಒಣಗಿದೆ"],
            "hi_roman": ["dry skin", "rookhi twacha", "sukhi twacha", "twacha dry"],
            "kn_roman": ["dry skin", "ona charma", "charma dry"]
        },
        "notes": {
            "en": "Dryness (Ruksha guna) is a primary classical hallmark of elevated Vata dosha.",
            "hi": "त्वचा का रूखापन (रूक्ष गुण) वात दोष की वृद्धि का शास्त्रीय और प्राथमिक लक्षण है।",
            "kn": "ಚರ್ಮದ ಒಣಗುವಿಕೆ (ರೂಕ್ಷ ಗುಣ) ವಾತ ದೋಷದ ಹೆಚ್ಚಳದ ಪ್ರಾಥಮಿಕ ಶಾಸ್ತ್ರೀಯ ಲಕ್ಷಣವಾಗಿದೆ.",
            "hi_roman": "Twacha ka rookha-pan (Ruksha guna) elevated Vata dosha ka classical attribute hai.",
            "kn_roman": "Charmada onaguvike (Ruksha guna) hechhada Vata doshada classical lakshana."
        }
    },
    {
        "concept_key": "joint_pain_stiffness",
        "dosha": "Vata",
        "source_id": "WHO_9789240064935",
        "locator": "page 46",
        "patterns": {
            "en": ["joint pain", "joint stiffness", "stiff joints", "joint ache"],
            "hi": ["जोड़ों का दर्द", "जोड़ों में दर्द", "जोड़ों में जकड़न", "जोड़ दर्द", "संधिशूल"],
            "kn": ["ಕೀಲು ನೋವು", "ಕೀಲುಗಳಲ್ಲಿ ನೋವು", "ಕೀಲು ಬಿಗಿತ", "ಕೀಲುಗಳ ಬಿಗಿತ"],
            "hi_roman": ["joint pain", "joint stiffness", "jodon me dard", "jodon me jakdan", "joint me dard"],
            "kn_roman": ["joint pain", "joint stiffness", "keelu novu", "keelu bigita", "keelugala novu"]
        },
        "notes": {
            "en": "Pain (Shula) and stiffness in joints correlate classically with Vata accumulation in Sandhi (joints).",
            "hi": "संधियों (जोड़ों) में शूल (दर्द) और जकड़न शास्त्रीय रूप से वात के संचय का संकेत है।",
            "kn": "ಕೀಲುಗಳಲ್ಲಿ ನೋವು (ಶೂಲ) ಮತ್ತು ಬಿಗಿತವು ಶಾಸ್ತ್ರೀಯವಾಗಿ ವಾತ ಸಂಚಯದ ಲಕ್ಷಣವಾಗಿದೆ.",
            "hi_roman": "Joints me dard aur stiffness classically Sandhi me Vata accumulation ko indicate karta hai.",
            "kn_roman": "Keelugalalli novu matte bigita classically Vata doshada sanchayavannu suchisuttade."
        }
    },
    {
        "concept_key": "constipation",
        "dosha": "Vata",
        "source_id": "WHO_9789240064935",
        "locator": "page 47",
        "patterns": {
            "en": ["constipation", "hard stools", "irregular bowel", "irregular elimination"],
            "hi": ["कब्ज", "मलबद्धता", "कब्जियत", "पेट साफ न होना"],
            "kn": ["ಮಲಬದ್ಧತೆ", "ಮಲಬದ್ಧತೆಯ", "ಕಠಿಣ ಮಲ"],
            "hi_roman": ["constipation", "kabz", "malabaddhata", "pet saaf na hona"],
            "kn_roman": ["constipation", "malabaddhate", "malabaddhatha"]
        },
        "notes": {
            "en": "Irregular elimination and dryness in the colon are traditionally governed by Apana Vata.",
            "hi": "मलबद्धता और आंतों में रूखापन पारंपरिक रूप से अपान वात के असंतुलन से जुड़ा है।",
            "kn": "ಮಲಬದ್ಧತೆ ಮತ್ತು ಕರುಳಿನ ಒಣಗುವಿಕೆಯು ಸಾಂಪ್ರದಾಯಿಕವಾಗಿ ಅಪಾನ ವಾತದ ಅಸಮತೋಲನಕ್ಕೆ ಸಂಬಂಧಿಸಿದೆ.",
            "hi_roman": "Irregular bowel aur dryness traditionally Apana Vata imbalance se judi hoti hai.",
            "kn_roman": "Malabaddhate traditionally Apana Vata asamatolanavannu dharisuttade."
        }
    },
    {
        "concept_key": "insomnia_restlessness",
        "dosha": "Vata",
        "source_id": "WHO_9789240064935",
        "locator": "page 48",
        "patterns": {
            "en": ["insomnia", "sleeplessness", "interrupted sleep", "restless sleep", "anxiety"],
            "hi": ["अनिद्रा", "नींद न आना", "बेचैनी", "नींद की कमी"],
            "kn": ["ನಿದ್ರಾಹೀನತೆ", "ನಿದ್ರೆ ಬಾರದಿರುವುದು", "ನಿದ್ರಾಭಂಗ", "ಆತಂಕ"],
            "hi_roman": ["insomnia", "anidra", "neend na aana", "bechaini"],
            "kn_roman": ["insomnia", "nidraheenate", "nidde baradilla", "aatanka"]
        },
        "notes": {
            "en": "Restlessness and interrupted sleep reflect the mobile (Chala) and light (Laghu) gunas of Vata.",
            "hi": "अनिद्रा और मानसिक चंचलता वात दोष के चल और लघु गुणों के असंतुलन को दर्शाती है।",
            "kn": "ನಿದ್ರಾಹೀನತೆ ಮತ್ತು ಚಂಚಲತೆಯು ವಾತ ದೋಷದ ಚಲ ಮತ್ತು ಲಘು ಗುಣಗಳ ಅಸಮತೋಲನವನ್ನು ಪ್ರತಿಬಿಂಬಿಸುತ್ತದೆ.",
            "hi_roman": "Restlessness aur interrupted sleep Vata ke Chala aur Laghu gunas ko reflect karte hain.",
            "kn_roman": "Nidraheenate Vata doshada Chala gunada asamatolanavannu torisuttade."
        }
    },

    # ── PITTA SYMPTOMS ───────────────────────────────────────────────────────
    {
        "concept_key": "burning_sensation",
        "dosha": "Pitta",
        "source_id": "WHO_9789240064935",
        "locator": "page 50",
        "patterns": {
            "en": ["burning sensation", "burning feeling", "internal heat", "burning stomach"],
            "hi": ["जलन", "पेट में जलन", "सीने में जलन", "दाह", "शरीर में जलन"],
            "kn": ["ಉರಿ", "ಹೊಟ್ಟೆಯಲ್ಲಿ ಉರಿ", "ಎದೆಯುರಿ", "ಉರಿ ಸಂವೇದನೆ"],
            "hi_roman": ["burning sensation", "jalan", "pet me jalan", "seene me jalan", "daah"],
            "kn_roman": ["burning sensation", "uri", "hotteyalli uri", "edeyuri", "uri samvedane"]
        },
        "notes": {
            "en": "Burning sensations (Daha) are classical hallmark expressions of Ushna (hot) and Tikshna (sharp) Pitta.",
            "hi": "दाह और जलन पित्त दोष के उष्ण और तीक्ष्ण गुणों की वृद्धि का शास्त्रीय परिचायक है।",
            "kn": "ಉರಿ ಸಂವೇದನೆಯು (ದಾಹ) ಪಿತ್ತ ದೋಷದ ಉಷ್ಣ ಮತ್ತು ತೀಕ್ಷ್ಣ ಗುಣಗಳ ಹೆಚ್ಚಳದ ಶಾಸ್ತ್ರೀಯ ಲಕ್ಷಣವಾಗಿದೆ.",
            "hi_roman": "Burning sensation (Daha) Pitta ke Ushna aur Tikshna gunas ka hallmark sign hai.",
            "kn_roman": "Uri samvedane (Daha) Pitta doshada Ushna guna hechhadaga kanisuttade."
        }
    },
    {
        "concept_key": "acid_reflux_heartburn",
        "dosha": "Pitta",
        "source_id": "WHO_9789240064935",
        "locator": "page 52",
        "patterns": {
            "en": ["acid reflux", "heartburn", "hyperacidity", "sour belching", "acidity"],
            "hi": ["अम्लपित्त", "खट्टी डकार", "एसिडिटी", "हाइपरएसिडिटी", "अम्लोद्गार"],
            "kn": ["ಆಮ್ಲಪಿತ್ತ", "ಹುಳಿ ತೇಗು", "ಎದೆಯುರಿ", "ಅಸಿಡಿಟಿ"],
            "hi_roman": ["acid reflux", "acidity", "amlapitta", "khatti dakar", "hyperacidity"],
            "kn_roman": ["acid reflux", "acidity", "amlapitta", "huli tegu", "edeyuri"]
        },
        "notes": {
            "en": "Sour regurgitation and hyperacidity correspond classically to Amla Pitta and impaired Pachaka Pitta.",
            "hi": "खट्टी डकार और अम्लपित्त पाचक पित्त के असंतुलन और द्रव/अम्ल गुण की वृद्धि को दर्शाते हैं।",
            "kn": "ಹುಳಿ ತೇಗು ಮತ್ತು ಆಮ್ಲಪಿತ್ತವು ಪಾಚಕ ಪಿತ್ತದ ಅಸಮತೋಲನಕ್ಕೆ ಸಾಂಪ್ರದಾಯಿಕ ನಿದರ್ಶನವಾಗಿದೆ.",
            "hi_roman": "Khatti dakar aur sour regurgitation classically Amla Pitta ko indicate karte hain.",
            "kn_roman": "Huli tegu matte amlapitta classically Pachaka Pittada asamatolanavannu torisuttade."
        }
    },
    {
        "concept_key": "excessive_thirst",
        "dosha": "Pitta",
        "source_id": "WHO_9789240064935",
        "locator": "page 51",
        "patterns": {
            "en": ["excessive thirst", "unquenchable thirst", "extreme thirst", "dry throat heat"],
            "hi": ["अत्यधिक प्यास", "बार बार प्यास लगना", "तृष्णा", "ज्यादा प्यास"],
            "kn": ["ತೀವ್ರ ಬಾಯಾರಿಕೆ", "ಅತಿಯಾದ ಬಾಯಾರಿಕೆ", "ಬಾಯಾರಿಕೆ"],
            "hi_roman": ["excessive thirst", "atyadhik pyas", "baar baar pyas", "extreme thirst"],
            "kn_roman": ["excessive thirst", "tivra bayarike", "athiyada bayarike"]
        },
        "notes": {
            "en": "Unquenchable thirst (Trishna) is attributed to elevated metabolic heat (Ushna guna of Pitta).",
            "hi": "अत्यधिक प्यास (तृष्णा) शरीर में पित्त जनित उष्णता की वृद्धि का शास्त्रीय लक्षण है।",
            "kn": "ಅತಿಯಾದ ಬಾಯಾರಿಕೆಯು (ತೃಷ್ಣಾ) ದೇಹದಲ್ಲಿ ಪಿತ್ತದ ಉಷ್ಣತೆಯ ಹೆಚ್ಚಳದ ಶಾಸ್ತ್ರೀಯ ಲಕ್ಷಣವಾಗಿದೆ.",
            "hi_roman": "Excessive thirst (Trishna) internal body heat aur Pitta Ushna guna ko reflect karta hai.",
            "kn_roman": "Athiyada bayarike Pittada Ushna gunada hechhalavannu suchisuttade."
        }
    },

    # ── KAPHA SYMPTOMS ───────────────────────────────────────────────────────
    {
        "concept_key": "sluggish_digestion",
        "dosha": "Kapha",
        "source_id": "NAMASTE_ayu-sat-table-a",
        "locator": "Code SAT-A.2",
        "patterns": {
            "en": ["sluggish digestion", "slow digestion", "low appetite", "poor digestion", "indigestion"],
            "hi": ["मंदाग्नि", "भूख कम लगना", "धीमा पाचन", "अपच", "अजीर्ण"],
            "kn": ["ಮಂದಾಗ್ನಿ", "ಹಸಿವು ಕಡಿಮೆಯಾಗುವುದು", "ನಿಧಾನ ಜೀರ್ಣಕ್ರಿಯೆ", "ಅಜೀರ್ಣ"],
            "hi_roman": ["sluggish digestion", "slow digestion", "mandagni", "bhook kam lagna", "apach"],
            "kn_roman": ["sluggish digestion", "mandagni", "hasivu kammi", "ajeerna", "nidhana jeernakriye"]
        },
        "notes": {
            "en": "Sluggish digestion reflects Manda Agni, classical impairment linked to excessive Guru and Snigdha gunas of Kapha.",
            "hi": "भूख की कमी और मंद पाचन 'मंदाग्नि' का प्रतीक है, जो कफ दोष के गुरु और स्निग्ध गुणों से संबंधित है।",
            "kn": "ಹಸಿವಿನ ಕೊರತೆ ಮತ್ತು ನಿಧಾನ ಜೀರ್ಣಕ್ರಿಯೆಯು 'ಮಂದಾಗ್ನಿ'ಯಾಗಿದ್ದು, ಕಫ ದೋಷದ ಹೆಚ್ಚಳವನ್ನು ಸೂಚಿಸುತ್ತದೆ.",
            "hi_roman": "Sluggish digestion classically Manda Agni aur Kapha ke Guru gunas se linked hota hai.",
            "kn_roman": "Sluggish digestion classically Manda Agni matte Kapha doshada lakshana."
        }
    },
    {
        "concept_key": "heaviness_lethargy",
        "dosha": "Kapha",
        "source_id": "WHO_9789240064935",
        "locator": "page 57",
        "patterns": {
            "en": ["heaviness", "body heaviness", "lethargy", "sluggishness", "excessive sleepiness", "fatigue"],
            "hi": ["शरीर में भारीपन", "भारीपन", "सुस्ती", "आलस्य", "अत्यधिक नींद", "थकान"],
            "kn": ["ದೇಹದ ಭಾರ", "ಹೊಟ್ಟೆ ಭಾರ", "ಸುಸ್ತು", "ಜಡತ್ವ", "ಆಲಸ್ಯ", "ಅತಿಯಾದ ನಿದ್ರೆ"],
            "hi_roman": ["heaviness", "bharipan", "susti", "alasya", "sharir me bharipan", "lethargy"],
            "kn_roman": ["heaviness", "dehada bhara", "susthu", "jadathva", "alasya", "lethargy"]
        },
        "notes": {
            "en": "General heaviness (Gaurava) and excessive lethargy (Alasya) are foundational markers of elevated Kapha.",
            "hi": "शरीर में भारीपन (गौरव) और आलस्य कफ दोष के शास्त्रीय एवं प्राथमिक लक्षण हैं।",
            "kn": "ದೇಹದಲ್ಲಿ ಭಾರ (ಗೌರವ) ಮತ್ತು ಜಡತ್ವವು ಕಫ ದೋಷದ ಪ್ರಾಥಮಿಕ ಶಾಸ್ತ್ರೀಯ ಗುರುತುಗಳಾಗಿವೆ.",
            "hi_roman": "Body heaviness (Gaurava) aur lethargy (Alasya) elevated Kapha dosha ke fundamental markers hain.",
            "kn_roman": "Dehada bhara (Gaurava) matte susthu Kapha doshada classical lakshanagalu."
        }
    },
    {
        "concept_key": "mucus_congestion",
        "dosha": "Kapha",
        "source_id": "WHO_9789240064935",
        "locator": "page 58",
        "patterns": {
            "en": ["excess mucus", "phlegm", "sinus congestion", "chest congestion", "productive cough"],
            "hi": ["कफ जमना", "बलगम", "श्लेष्मा", "छाती में कफ", "कफ वाली खांसी"],
            "kn": ["ಕಫ", "ಕಫ ಶೇಖರಣೆ", "ಎದೆಯಲ್ಲಿ ಕಫ", "ಮೂಗಿನ ಕಟ್ಟುವಿಕೆ"],
            "hi_roman": ["excess mucus", "balgam", "kaf jamna", "chest congestion", "phlegm"],
            "kn_roman": ["excess mucus", "kafa", "edeyalli kafa", "phlegm"]
        },
        "notes": {
            "en": "Accumulation of phlegm and mucosal congestion indicate localized increase of Kledaka or Avalambaka Kapha.",
            "hi": "कफ का जमना और बलगम का संचय अवलंबक या क्लेदक कफ की वृद्धि को दर्शाता है।",
            "kn": "ಕಫದ ಶೇಖರಣೆಯು ಸಾಂಪ್ರದಾಯಿಕವಾಗಿ ಅವಲಂಬಕ ಅಥವಾ ಕ್ಲೇದಕ ಕಫದ ಹೆಚ್ಚಳವನ್ನು ಪ್ರತಿಬಿಂಬಿಸುತ್ತದೆ.",
            "hi_roman": "Phlegm aur mucus accumulation classically Kapha dosha ke increase ko darshata hai.",
            "kn_roman": "Kaphada shekharane classically Avalambaka Kapha doshada hechhalavannu torisuttade."
        }
    },

    # ── ADDITIONAL COMMON NON-ACUTE SYMPTOMS ──────────────────────────────────
    {
        "concept_key": "headache_shirashoola",
        "dosha": "Vata",
        "source_id": "WHO_9789240064935",
        "locator": "ITA-5.6.3 (Morbidity terms)",
        "patterns": {
            "en": ["headache", "head ache", "mild headache", "tension headache", "shirashoola", "shiroruk"],
            "hi": ["सिरदर्द", "सर दर्द", "सिर में दर्द", "शिरःशूल", "शिरोवेदना", "हल्का सिरदर्द"],
            "kn": ["ತಲೆನೋವು", "ತಲೆ ನೋವು", "ನನಗೆ ತಲೆನೋವು ಇದೆ", "ತಲೆಯ ನೋವು", "ಶಿರಃಶೂಲ", "ತಲೆನೋವು ಇದೆ"],
            "hi_roman": ["headache", "sirdard", "sir dard", "sir me dard", "shirashoola"],
            "kn_roman": ["headache", "tale novu", "talenovu", "shirashoola", "tale novu ide"]
        },
        "notes": {
            "en": "Non-acute headache (Shirashoola) is classically associated with Vata imbalance in Shiras (head), or secondary Pitta metabolic heat.",
            "hi": "सामान्य गैर-आपातकालीन सिरदर्द (शिरःशूल) मुख्य रूप से सिर में वात के प्रकोप अथवा पित्त की उष्णता से संबंधित माना जाता है।",
            "kn": "ಸಾಮಾನ್ಯ ತಲೆನೋವು (ಶಿರಃಶೂಲ) ಮುಖ್ಯವಾಗಿ ಶಿರಸ್ಸಿನಲ್ಲಿ ವಾತ ದೋಷದ ಪ್ರಕೋಪ ಅಥವಾ ಪಿತ್ತದ ಉಷ್ಣತೆಗೆ ಸಂಬಂಧಿಸಿದೆ ಎಂದು ಪರಿಗಣಿಸಲಾಗುತ್ತದೆ.",
            "hi_roman": "Non-acute headache (Shirashoola) primarily Shiras me Vata imbalance ya Pitta heat se judaa hota hai.",
            "kn_roman": "Samanya talenovu (Shirashoola) mukhyavagi Shirasinalli Vata doshada prakopavannu suchisuttade."
        }
    },
    {
        "concept_key": "postprandial_heaviness",
        "dosha": "Kapha",
        "source_id": "WHO_9789240064935",
        "locator": "page 57",
        "patterns": {
            "en": ["tired after eating", "heaviness after eating", "heaviness after food", "sluggish after meal", "heavy stomach after food"],
            "hi": ["भोजन के बाद भारीपन", "खाना खाने के बाद भारीपन", "खाने के बाद सुस्ती", "भोजनोपरांत आलस्य", "भोजन के बाद थकान"],
            "kn": ["ಊಟದ ನಂತರ ಹೊಟ್ಟೆ ಭಾರ", "ಊಟದ ನಂತರ ಹೊಟ್ಟೆ ಭಾರವಾಗುತ್ತದೆ", "ಊಟದ ನಂತರ ಸುಸ್ತು", "ಭೋಜನದ ನಂತರ ಜಡತ್ವ", "ಊಟವಾದ ಮೇಲೆ ಹೊಟ್ಟೆ ಭಾರ"],
            "hi_roman": ["khana khane ke baad heaviness", "bhojan ke baad bharipan", "khana khane ke baad susti", "heavy after food"],
            "kn_roman": ["oota aadmele hotte heavy", "ootada nantara hotte bhara", "oota admele susthu", "oota aadmele hotte heavy aagutte"]
        },
        "notes": {
            "en": "Post-prandial heaviness and fatigue reflect sluggish metabolic fire (Manda Agni) and elevated Kledaka Kapha in the stomach.",
            "hi": "भोजन के बाद अत्यधिक भारीपन व सुस्ती मंदाग्नि और आमाशय में क्लेदक कफ के प्रभाव को दर्शाती है।",
            "kn": "ಊಟದ ನಂತರ ಹೊಟ್ಟೆ ಭಾರ ಮತ್ತು ಆಲಸ್ಯವು ಮಂದಾಗ್ನಿ ಮತ್ತು ಜಠರದಲ್ಲಿ ಕ್ಲೇದಕ ಕಫದ ಹೆಚ್ಚಳದ ಲಕ್ಷಣವಾಗಿದೆ.",
            "hi_roman": "Post-prandial heaviness Manda Agni aur stomach me Kledaka Kapha ke sanchay ko reflect karta hai.",
            "kn_roman": "Ootada nantara hotte bhara Manda Agni matte Kledaka Kapha doshada lakshana."
        }
    },
    {
        "concept_key": "bloating_adhmana",
        "dosha": "Vata",
        "source_id": "WHO_9789240064935",
        "locator": "ITA-5.6.3 (Disorders)",
        "patterns": {
            "en": ["bloating", "bloated", "abdominal distension", "gas", "bloated stomach", "adhmana"],
            "hi": ["पेट फूलना", "आध्मान", "गैस बनना", "पेट में गैस", "अफारा", "पेट का भारीपन"],
            "kn": ["ಹೊಟ್ಟೆ ಉಬ್ಬರ", "ಆಧ್ಮಾನ", "ಹೊಟ್ಟೆಯಲ್ಲಿ ಗ್ಯಾಸ್", "ಹೊಟ್ಟೆ ಉಬ್ಬುವುದು", "ಹೊಟ್ಟೆಯುಬ್ಬರ"],
            "hi_roman": ["bloating", "bloated", "pet phoolna", "adhmana", "afara", "gas"],
            "kn_roman": ["bloating", "bloated", "hotte ubbara", "adhmana", "hotte gas"]
        },
        "notes": {
            "en": "Abdominal distension and bloating (Adhmana) classically indicate upward or obstructed Samana and Apana Vata.",
            "hi": "पेट फूलना और आध्मान समान एवं अपान वात के अवरोध व असंतुलन का शास्त्रीय संकेत है।",
            "kn": "ಹೊಟ್ಟೆ ಉಬ್ಬರ (ಆಧ್ಮಾನ) ಸಮಾನ ಮತ್ತು ಅಪಾನ ವಾತದ ಅಸಮತೋಲನವನ್ನು ಸೂಚಿಸುತ್ತದೆ.",
            "hi_roman": "Abdominal distension aur bloating (Adhmana) Samana aur Apana Vata imbalance ko indicate karta hai.",
            "kn_roman": "Hotte ubbara (Adhmana) Samana matte Apana Vata doshada asamatolanavannu torisuttade."
        }
    },
    {
        "concept_key": "sleep_difficulty",
        "dosha": "Vata",
        "source_id": "WHO_9789240064935",
        "locator": "page 48",
        "patterns": {
            "en": ["difficulty sleeping", "trouble sleeping", "cannot sleep", "poor sleep", "interrupted sleep"],
            "hi": ["नींद नहीं आती", "नींद की समस्या", "सोने में परेशानी", "नींद न लगना", "नींद न आना"],
            "kn": ["ನನಗೆ ನಿದ್ರೆ ಸರಿಯಾಗಿ ಬರುತ್ತಿಲ್ಲ", "ನಿದ್ರೆ ಬರುತ್ತಿಲ್ಲ", "ನಿದ್ರೆ ತೊಂದರೆ", "ನಿದ್ರೆ ಸರಿಯಾಗಿ ಬರ್ತಿಲ್ಲ", "ನಿದ್ರೆ ಬಾರದಿರುವುದು"],
            "hi_roman": ["neend nahi aati", "neend aane me problem", "so nahi pata", "difficulty sleeping"],
            "kn_roman": ["nidre sariyagi baradilla", "nidde baradilla", "nidre baralla", "difficulty sleeping"]
        },
        "notes": {
            "en": "Difficulty initiating or maintaining sleep correlates with hyperactive Prana and Vyana Vata disturbing Manas (mind).",
            "hi": "नींद न आना और मानसिक चंचलता प्राण वात की अधिकता और मन के रजोगुण की वृद्धि से जुड़ी है।",
            "kn": "ನಿದ್ರೆ ಸರಿಯಾಗಿ ಬಾರದಿರುವುದು ಪ್ರಾಣ ವಾತದ ಅಸಮತೋಲನ ಮತ್ತು ಮನಸ್ಸಿನ ಚಂಚಲತೆಯನ್ನು ಪ್ರತಿಬಿಂಬಿಸುತ್ತದೆ.",
            "hi_roman": "Difficulty sleeping hyperactive Prana Vata aur restless mind ko reflect karta hai.",
            "kn_roman": "Nidre sariyagi baradilla Prana Vata doshada asamatolanavannu torisuttade."
        }
    },
    {
        "concept_key": "stomach_pain_udarashoola",
        "dosha": "Vata",
        "source_id": "WHO_9789240064935",
        "locator": "ITA-5.6.3 (Morbidity terms)",
        "patterns": {
            "en": [
                "stomach pain", "stomach ache", "stomachache", "abdominal pain", "tummy ache",
                "pain in stomach", "pain in abdomen", "udarashoola", "shoola", "belly pain",
                "i have stomach pain", "stomach hurts", "pain in belly"
            ],
            "hi": [
                "पेट दर्द", "पेट में दर्द", "पेट का दर्द", "उदरशूल", "शूल", "पेट दुखना",
                "मुझे पेट में दर्द है", "मुझे पेट में दर्द हो रहा है", "पेट दुख रहा है", "पेट में पीड़ा"
            ],
            "kn": [
                "ಹೊಟ್ಟೆ ನೋವು", "ಹೊಟ್ಟೆನೋವು", "ಹೊಟ್ಟೆಯ ನೋವು", "ಉದರಶೂಲ", "ಶೂಲ",
                "ನನಗೆ ಹೊಟ್ಟೆ ನೋವು ಇದೆ", "ನನಗೆ ಹೊಟ್ಟೆನೋವು ಇದೆ", "ಹೊಟ್ಟೆ ನೋಯ್ತಾ ಇದೆ"
            ],
            "hi_roman": [
                "stomach pain", "pet dard", "pet me dard", "pet me dard hai", "mujhe pet me dard hai",
                "pet dukh raha hai", "udarashoola", "shoola", "stomach ache"
            ],
            "kn_roman": [
                "stomach pain", "hotte novu", "hottenovu", "hotteyalli novu", "nanage hotte novu ide",
                "hotte novu ide", "udarashoola", "shoola", "stomach ache"
            ]
        },
        "notes": {
            "en": "Abdominal discomfort or pain (Udara-shoola) classically signifies Samana Vata or Apana Vata vitiation impairing peristalsis and digestion, often with secondary Pitta involvement if burning is present.",
            "hi": "पेट का दर्द (उदरशूल) शास्त्रीय रूप से समान या अपान वात के असंतुलन से जुड़ा है, जो आंतों की गति और पाचन को प्रभावित करता है। जलन होने पर इसमें पित्त का भी अनुबंध माना जाता है।",
            "kn": "ಹೊಟ್ಟೆ ನೋವು (ಉದರಶೂಲ) ಶಾಸ್ತ್ರೀಯವಾಗಿ ಸಮಾನ ಅಥವಾ ಅಪಾನ ವಾತದ ಅಸಮತೋಲನವನ್ನು ಸೂಚಿಸುತ್ತದೆ, ಉರಿ ಇದ್ದರೆ ಪಿತ್ತದ ಸಂಯೋಗವೂ ಇರುತ್ತದೆ.",
            "hi_roman": "Pet dard (Udara-shoola) classically Samana ya Apana Vata ke imbalance aur Agni vaishamya se judaa hota hai.",
            "kn_roman": "Hotte novu (Udara-shoola) classically Samana athava Apana Vata doshada asamatolanavannu suchisuttade."
        }
    },
    {
        "concept_key": "piles_arshas",
        "dosha": "Vata",
        "source_id": "WHO_9789240064935",
        "locator": "ITA-5.6.3 (Morbidity terms, p.56)",
        "patterns": {
            "en": [
                "piles", "hemorrhoids", "haemorrhoids", "arsha", "arshas",
                "bleeding piles", "painful piles", "anal piles"
            ],
            "hi": [
                "बवासीर", "अर्श", "अर्शस", "मस्से", "खूनी बवासीर", "बादी बवासीर", "बवासीर का दर्द"
            ],
            "kn": [
                "ಮೂಲವ್ಯಾಧಿ", "ಅರ್ಶಸ್", "ಅರ್ಶ", "ಮೂಲ ರೋಗ", "ಮೂಲವ್ಯಾಧಿಯ ತೊಂದರೆ"
            ],
            "hi_roman": [
                "piles", "bawasir", "arsha", "arshas", "masse", "khooni bawasir"
            ],
            "kn_roman": [
                "piles", "moolavyadhi", "arsha", "arshas", "moola roga"
            ]
        },
        "notes": {
            "en": "Hemorrhoids (Arshas) in classical Ayurveda are traditionally regarded as a consequence of impaired digestive fire (Mandagni) leading to Apana Vata vitiation and obstruction in Guda (anal canal).",
            "hi": "अर्श (बवासीर) को आयुर्वेद में मंदाग्नि और अपान वात के वैकृत होने से गुद प्रदेश में उत्पन्न होने वाला विकार माना गया है।",
            "kn": "ಅರ್ಶಸ್ (ಮೂಲವ್ಯಾಧಿ) ಆಯುರ್ವೇದದಲ್ಲಿ ಮಂದಾಗ್ನಿ ಮತ್ತು ಅಪಾನ ವಾತದ ಅಸಮತೋಲನದಿಂದ ಗುದ ಪ್ರದೇಶದಲ್ಲಿ ಉಂಟಾಗುವ ಶಾಸ್ತ್ರೀಯ ವ್ಯಾಧಿಯಾಗಿದೆ.",
            "hi_roman": "Hemorrhoids (Arshas) classically Mandagni aur Apana Vata ke imbalance se guda kshetra me manifest hote hain.",
            "kn_roman": "Arshas (Moolavyadhi) classically Mandagni matte Apana Vata doshada asamatolanavannu suchisuttade."
        }
    },
    {
        "concept_key": "digestive_discomfort_ajirna",
        "dosha": "Kapha",
        "source_id": "NAMASTE_ayu-sat-table-a",
        "locator": "Code SAT-A.2",
        "patterns": {
            "en": [
                "digestive discomfort", "indigestion", "poor digestion", "digestive trouble",
                "digestive issue", "digestive problems", "upset stomach", "indigested feeling",
                "ajirna", "ajeerna"
            ],
            "hi": [
                "पाचन में परेशानी", "पाचन संबंधी समस्या", "अजीर्ण", "अपच", "पेट की खराबी", "बदहजमी"
            ],
            "kn": [
                "ಜೀರ್ಣಕ್ರಿಯೆಯ ತೊಂದರೆ", "ಅಜೀರ್ಣ", "ಹೊಟ್ಟೆಯ ಅಸ್ವಸ್ಥತೆ", "ಜೀರ್ಣವಾಗದಿರುವುದು"
            ],
            "hi_roman": [
                "digestive discomfort", "indigestion", "pachan me pareshani", "badhazmi", "apach", "ajirna"
            ],
            "kn_roman": [
                "digestive discomfort", "ajeerna", "jeernakriyeya tondare", "indigestion"
            ]
        },
        "notes": {
            "en": "Digestive discomfort and indigestion (Ajirna) in classical Ayurveda reflect Agnimandya (diminished digestive fire), frequently associated with excess Kapha and Ama formation.",
            "hi": "पाचन में परेशानी और अजीर्ण (अपच) अग्निमांद्य (अग्नि की कमजोरी) और आम दोष के संचय का शास्त्रीय परिचायक है।",
            "kn": "ಜೀರ್ಣಕ್ರಿಯೆಯ ತೊಂದರೆ ಮತ್ತು ಅಜೀರ್ಣವು ಅಗ್ನಿಮಾಂದ್ಯ (ಜೀರ್ಣಾಗ್ನಿಯ ಕೊರತೆ) ಮತ್ತು ಆಮ ದೋಷದ ಸಂಚಯವನ್ನು ಪ್ರತಿಬಿಂಬಿಸುತ್ತದೆ.",
            "hi_roman": "Digestive discomfort aur Ajirna classically Agnimandya aur Ama formation se linked hote hain.",
            "kn_roman": "Digestive discomfort classically Agnimandya matte Ama sanchayavannu suchisuttade."
        }
    }
]


class EducationalSymptomMapper:
    """
    Multilingual Educational Symptom-to-Concept Mapper.
    Provides verified classical mappings, strictly enforces medical safety red flags,
    and returns localized responses matching the user's detected language.
    """

    def __init__(self, kg: Optional[AyurKnowledgeGraph] = None, retriever: Optional[Any] = None):
        self.kg = kg or AyurKnowledgeGraph()
        self.retriever = retriever

    def analyze_symptoms(self, text: str, target_lang: str = "auto") -> Dict[str, Any]:
        """
        Analyze multilingual and code-mixed symptom input.
        Supports explicit output language selection (Auto, English, Hindi, Kannada).
        Returns:
            - abstained: bool
            - reason: "emergency_symptom_detected" | "no_supported_symptom_recognized" | "empty_input" | None
            - detected_language: str ("en", "hi", "kn")
            - target_language: str ("en", "hi", "kn", "hi_roman", "kn_roman")
            - is_romanized: bool
            - is_code_mixed: bool
            - code_mix_type: str
            - segments: List[Dict]
            - primary_conceptual_tendency: str or None
            - summary: str
            - mappings: List[Dict]
            - disclaimer: str
        """
        if not text or not text.strip():
            return {
                "abstained": True,
                "reason": "empty_input",
                "detected_language": "en",
                "target_language": "en",
                "is_romanized": False,
                "is_code_mixed": False,
                "message": ABSTENTION_MESSAGES["en"],
                "mappings": [],
                "disclaimer": EDUCATIONAL_DISCLAIMER
            }

        # 1. Language, script, and code-mixing detection
        lang_info = detect(text)
        detected_lang = lang_info.get("dominant_lang", lang_info.get("lang", "en"))
        is_romanized = lang_info.get("is_romanized", False)
        is_code_mixed = lang_info.get("is_code_mixed", False)

        # Resolve language key for messaging (en, hi, kn, hi_roman, kn_roman)
        if target_lang and target_lang.lower() in ("en", "hi", "kn"):
            lang_key = target_lang.lower()
        elif detected_lang == "hi" and is_romanized:
            lang_key = "hi_roman"
        elif detected_lang == "kn" and is_romanized:
            lang_key = "kn_roman"
        elif detected_lang in ("hi", "kn"):
            lang_key = detected_lang
        else:
            lang_key = "en"

        text_clean = text.lower().strip()

        # 2. EMERGENCY RED-FLAG SAFETY CHECK (Across All Supported Languages)
        # Check specific language list, plus cross-lingual checks
        flags_to_check = set(EMERGENCY_RED_FLAGS.get(lang_key, []))
        # Always cross-check English and Romanized keywords to guard code-mixed inputs
        flags_to_check.update(EMERGENCY_RED_FLAGS["en"])
        if is_romanized or detected_lang in ("hi", "kn"):
            flags_to_check.update(EMERGENCY_RED_FLAGS["hi_roman"])
            flags_to_check.update(EMERGENCY_RED_FLAGS["kn_roman"])
        if lang_info.get("script") == "devanagari":
            flags_to_check.update(EMERGENCY_RED_FLAGS["hi"])
        if lang_info.get("script") == "kannada":
            flags_to_check.update(EMERGENCY_RED_FLAGS["kn"])

        for red_flag in flags_to_check:
            if red_flag in text_clean:
                alert_msg = EMERGENCY_ADVISORIES.get(lang_key, EMERGENCY_ADVISORIES["en"])
                return {
                    "abstained": True,
                    "is_emergency": True,
                    "reason": "emergency_symptom_detected",
                    "detected_language": detected_lang,
                    "target_language": lang_key,
                    "is_romanized": is_romanized,
                    "is_code_mixed": is_code_mixed,
                    "code_mix_type": lang_info.get("code_mix_type", "monolingual"),
                    "segments": lang_info.get("segments", []),
                    "matched_red_flag": red_flag,
                    "emergency_alert": alert_msg,
                    "educational_advisory": alert_msg,
                    "message": alert_msg,
                    "mappings": [],
                    "disclaimer": EDUCATIONAL_DISCLAIMER
                }

        # 3. CLASSICAL SYMPTOM CONCEPT MAPPING
        detected_mappings: List[Dict[str, Any]] = []
        dosha_counts = {"Vata": 0, "Pitta": 0, "Kapha": 0}

        for item in CLASSICAL_SYMPTOM_CATALOG:
            # Check patterns for current language, plus English / Romanized fallback
            matched_pattern = None
            candidate_patterns = item["patterns"].get(lang_key, [])
            # Also allow cross-checking English patterns for code-mixed input
            if lang_key != "en":
                candidate_patterns = list(candidate_patterns) + item["patterns"].get("en", [])

            for pat in candidate_patterns:
                if pat in text_clean:
                    matched_pattern = pat
                    break

            # Flexible semantic check for adverbs / word-order variations (e.g. "ಚರ್ಮ ತುಂಬಾ ಒಣಗಿದೆ")
            if not matched_pattern:
                ckey = item["concept_key"]
                if ckey == "dry_skin":
                    if ("ಚರ್ಮ" in text_clean and "ಒಣ" in text_clean) or ("ತ್ವಚೆ" in text_clean and "ಒಣ" in text_clean):
                        matched_pattern = "ಚರ್ಮ ಒಣಗಿದೆ"
                    elif "त्वचा" in text_clean and ("सूखी" in text_clean or "रूखी" in text_clean or "रूखा" in text_clean):
                        matched_pattern = "रूखी त्वचा"
                    elif ("skin" in text_clean or "twacha" in text_clean or "charma" in text_clean) and ("dry" in text_clean or "rough" in text_clean):
                        matched_pattern = "dry skin"
                elif ckey == "joint_pain_stiffness":
                    if "ಕೀಲು" in text_clean and ("ನೋವು" in text_clean or "ಬಿಗಿತ" in text_clean):
                        matched_pattern = "ಕೀಲು ನೋವು"
                    elif ("जोड़" in text_clean or "जोड़ों" in text_clean or "संधि" in text_clean) and ("दर्द" in text_clean or "जकड़न" in text_clean):
                        matched_pattern = "जोड़ों में दर्द"
                    elif "joint" in text_clean and ("pain" in text_clean or "stiff" in text_clean or "ache" in text_clean):
                        matched_pattern = "joint pain"
                elif ckey == "burning_sensation":
                    if "ಉರಿ" in text_clean and "ಎದೆ" not in text_clean:
                        matched_pattern = "ಉರಿ ಸಂವೇದನೆ"
                    elif "जलन" in text_clean and "सीने" not in text_clean:
                        matched_pattern = "जलन"
                    elif "burning" in text_clean and "chest" not in text_clean:
                        matched_pattern = "burning sensation"
                elif ckey == "acid_reflux_heartburn":
                    if "ಎದೆಯುರಿ" in text_clean or "ಆಮ್ಲಪಿತ್ತ" in text_clean or "ಹುಳಿ ತೇಗು" in text_clean or "ಅಸಿಡಿಟಿ" in text_clean:
                        matched_pattern = "ಎದೆಯುರಿ" if "ಎದೆಯುರಿ" in text_clean else "ಆಮ್ಲಪಿತ್ತ"
                    elif "अम्लपित्त" in text_clean or "खट्टी डकार" in text_clean or "एसिडिटी" in text_clean:
                        matched_pattern = "खट्टी डकार" if "खट्टी" in text_clean else "अम्लपित्त"
                    elif "acid reflux" in text_clean or "heartburn" in text_clean or "acidity" in text_clean:
                        matched_pattern = "acid reflux"
                elif ckey == "sluggish_digestion":
                    if "ಮಂದಾಗ್ನಿ" in text_clean or ("ಹಸಿವು" in text_clean and "ಕಡಿಮೆ" in text_clean):
                        matched_pattern = "ಮಂದಾಗ್ನಿ"
                    elif "मंदाग्नि" in text_clean or ("भूख" in text_clean and "कम" in text_clean):
                        matched_pattern = "मंदाग्नि"
                    elif "sluggish" in text_clean or ("slow" in text_clean and "digest" in text_clean):
                        matched_pattern = "sluggish digestion"
                elif ckey == "headache_shirashoola":
                    if "ತಲೆ" in text_clean and "ನೋವು" in text_clean:
                        matched_pattern = "ತಲೆನೋವು"
                    elif ("सिर" in text_clean or "सर" in text_clean) and "दर्द" in text_clean:
                        matched_pattern = "सिरदर्द"
                    elif "headache" in text_clean or ("head" in text_clean and "ache" in text_clean) or "shirashoola" in text_clean:
                        matched_pattern = "headache"
                    elif "tale" in text_clean and "novu" in text_clean:
                        matched_pattern = "tale novu"
                    elif "sir" in text_clean and "dard" in text_clean:
                        matched_pattern = "sirdard"
                elif ckey == "postprandial_heaviness":
                    if ("ಊಟ" in text_clean or "ಭೋಜನ" in text_clean) and ("ಭಾರ" in text_clean or "ಸುಸ್ತು" in text_clean or "ಜಡ" in text_clean):
                        matched_pattern = "ಊಟದ ನಂತರ ಹೊಟ್ಟೆ ಭಾರ"
                    elif ("भोजन" in text_clean or "खाना" in text_clean) and ("भारीपन" in text_clean or "सुस्ती" in text_clean or "आलस्य" in text_clean or "थकान" in text_clean):
                        matched_pattern = "भोजन के बाद भारीपन"
                    elif ("eat" in text_clean or "food" in text_clean or "meal" in text_clean) and ("tired" in text_clean or "heavy" in text_clean or "sluggish" in text_clean or "fatigue" in text_clean):
                        matched_pattern = "heaviness after eating"
                    elif ("oota" in text_clean or "ootada" in text_clean) and ("heavy" in text_clean or "bhara" in text_clean or "susthu" in text_clean):
                        matched_pattern = "oota aadmele hotte heavy"
                    elif ("khana" in text_clean or "bhojan" in text_clean) and ("heavy" in text_clean or "bharipan" in text_clean or "susti" in text_clean):
                        matched_pattern = "khana khane ke baad heaviness"
                elif ckey == "bloating_adhmana":
                    if "ಹೊಟ್ಟೆ" in text_clean and "ಉಬ್ಬರ" in text_clean:
                        matched_pattern = "ಹೊಟ್ಟೆ ಉಬ್ಬರ"
                    elif "पेट" in text_clean and ("फूल" in text_clean or "गैस" in text_clean):
                        matched_pattern = "पेट फूलना"
                    elif "bloat" in text_clean or "distension" in text_clean:
                        matched_pattern = "bloating"
                    elif "hotte" in text_clean and ("ubbara" in text_clean or "gas" in text_clean):
                        matched_pattern = "hotte ubbara"
                    elif "pet" in text_clean and ("phool" in text_clean or "gas" in text_clean):
                        matched_pattern = "pet phoolna"
                elif ckey == "sleep_difficulty":
                    if "ನಿದ್ರೆ" in text_clean and ("ಬರುತ್ತಿಲ್ಲ" in text_clean or "ಬರ್ತಿಲ್ಲ" in text_clean or "ತೊಂದರೆ" in text_clean or "ಕಡಿಮೆ" in text_clean or "ಸಾಕಾಗ" in text_clean):
                        matched_pattern = "ನನಗೆ ನಿದ್ರೆ ಸರಿಯಾಗಿ ಬರುತ್ತಿಲ್ಲ"
                    elif "नींद" in text_clean and ("नहीं" in text_clean or "कमी" in text_clean or "परेशानी" in text_clean or "मुश्किल" in text_clean):
                        matched_pattern = "नींद नहीं आती"
                    elif "sleep" in text_clean and ("difficult" in text_clean or "trouble" in text_clean or "cannot" in text_clean or "poor" in text_clean or "problem" in text_clean or "hard" in text_clean):
                        matched_pattern = "difficulty sleeping"
                    elif ("nidre" in text_clean or "nidde" in text_clean) and ("baradilla" in text_clean or "baralla" in text_clean or "problem" in text_clean):
                        matched_pattern = "nidre sariyagi baradilla"
                    elif "neend" in text_clean and ("nahi" in text_clean or "problem" in text_clean or "kam" in text_clean):
                        matched_pattern = "neend nahi aati"
                elif ckey == "stomach_pain_udarashoola":
                    if "ಹೊಟ್ಟೆ" in text_clean and ("ನೋವು" in text_clean or "ನೋಯ್" in text_clean):
                        matched_pattern = "ಹೊಟ್ಟೆ ನೋವು"
                    elif "ಉದರ" in text_clean and "ಶೂಲ" in text_clean:
                        matched_pattern = "ಉದರಶೂಲ"
                    elif "पेट" in text_clean and ("दर्द" in text_clean or "पीड़ा" in text_clean or "दुख" in text_clean):
                        matched_pattern = "पेट दर्द"
                    elif "उदर" in text_clean and "शूल" in text_clean:
                        matched_pattern = "उदरशूल"
                    elif ("stomach" in text_clean or "belly" in text_clean or "abdominal" in text_clean or "abdomen" in text_clean or "tummy" in text_clean) and ("pain" in text_clean or "ache" in text_clean or "hurt" in text_clean or "cramp" in text_clean or "discomfort" in text_clean):
                        matched_pattern = "stomach pain"
                    elif "udarashoola" in text_clean or "udarashula" in text_clean or "shoola" in text_clean or "shula" in text_clean:
                        matched_pattern = "udarashoola"
                    elif "hotte" in text_clean and "novu" in text_clean:
                        matched_pattern = "hotte novu"
                    elif "pet" in text_clean and "dard" in text_clean:
                        matched_pattern = "pet dard"
                elif ckey == "piles_arshas":
                    if "ಮೂಲವ್ಯಾಧಿ" in text_clean or "ಅರ್ಶ" in text_clean:
                        matched_pattern = "ಮೂಲವ್ಯಾಧಿ"
                    elif "बवासीर" in text_clean or "अर्श" in text_clean or "मस्से" in text_clean:
                        matched_pattern = "बवासीर"
                    elif "pile" in text_clean or "hemorrhoid" in text_clean or "haemorrhoid" in text_clean or "arsha" in text_clean:
                        matched_pattern = "piles"
                    elif "bawasir" in text_clean or "moolavyadhi" in text_clean:
                        matched_pattern = "piles"
                elif ckey == "digestive_discomfort_ajirna":
                    if "ಅಜೀರ್ಣ" in text_clean or "ಜೀರ್ಣ" in text_clean:
                        matched_pattern = "ಅಜೀರ್ಣ"
                    elif "अजीर्ण" in text_clean or "अपच" in text_clean or "बदहजमी" in text_clean or ("पाचन" in text_clean and "परेशानी" in text_clean):
                        matched_pattern = "पाचन में परेशानी"
                    elif "digest" in text_clean or "indigestion" in text_clean or "upset" in text_clean or "ajirna" in text_clean or "ajeerna" in text_clean:
                        matched_pattern = "digestive discomfort"
                    elif "badhazmi" in text_clean or "apach" in text_clean:
                        matched_pattern = "digestive discomfort"

            if matched_pattern:
                dosha = item["dosha"]
                dosha_counts[dosha] += 1

                # Select explanation in target language
                note = item["notes"].get(lang_key, item["notes"].get("en", ""))

                detected_mappings.append({
                    "symptom_phrase": matched_pattern,
                    "associated_dosha": dosha,
                    "educational_note": note,
                    "source_id": item["source_id"],
                    "locator": item["locator"],
                    "provenance": f"[{item['source_id']}, {item['locator']}]",
                    "mapping_status": "educational_heuristic",
                    "caution": "Provisional educational correlation; classical literature does not provide algorithmic diagnostic symptom-to-dosha mappings.",
                })

        # 4. RAG RETRIEVAL FALLBACK (if exact catalog keyword heuristic found no mapping)
        if not detected_mappings:
            # Check whether the query contains any physical sensation / clinical symptom cues
            symptom_cues = (
                # English
                "pain", "ache", "hurt", "cramp", "burn", "stiff", "itch", "dry", "heavy", "tired",
                "weak", "swell", "cold", "cough", "fever", "breath", "sleep", "sweat", "rash",
                "stool", "constipat", "digest", "nausea", "vomit", "reflux", "acid", "throat",
                "gas", "bloat", "appetite", "thirst", "dizz", "headache", "spasm", "shoola", "daha",
                "pile", "piles", "hemorrhoid", "hemorrhoids", "arsha", "arshas", "discomfort",
                "hair", "skin", "joint", "fatigue", "exhaust", "indigestion", "trouble", "bleeding",
                # Hindi
                "दर्द", "पीड़ा", "जलन", "सूजन", "खांसी", "कफ", "बुखार", "थकान", "कमजोरी", "नींद",
                "प्यास", "भूख", "पेट", "सिर", "गला", "छाती", "मल", "कब्ज", "अपच", "गैस", "डकार", "भारीपन",
                "बवासीर", "अर्श", "मस्से", "बाल", "त्वचा", "जोड़", "कमर", "बदहजमी",
                # Kannada
                "ನೋವು", "ಉರಿ", "ಊತ", "ಕೆಮ್ಮು", "ಕಫ", "ಜ್ವರ", "ಸುಸ್ತು", "ದಣಿವು", "ನಿದ್ರೆ", "ಬಾಯಾರಿಕೆ",
                "ಹಸಿವು", "ಹೊಟ್ಟೆ", "ತಲೆ", "ಗಂಟಲು", "ಎದೆ", "ಮಲಬದ್ಧತೆ", "ಅಜೀರ್ಣ", "ಗ್ಯಾಸ್", "ತೇಗು", "ಭಾರ",
                "ಮೂಲವ್ಯಾಧಿ", "ಅರ್ಶ", "ಕೂದಲು", "ಚರ್ಮ", "ಕೀಲು",
                # Romanized / code-mixed
                "dard", "novu", "uri", "jalan", "pet", "hotte", "tale", "sir", "khansi", "kemmu",
                "susthu", "susti", "neend", "nidre", "bhook", "hasivu", "pyas", "bayarike", "ajeerna", "apach",
                "bawasir", "moolavyadhi", "arsha", "masse", "jeerna", "pachan"
            )
            has_symptom_cue = any(cue in text_clean for cue in symptom_cues)

            if has_symptom_cue:
                if self.retriever is None:
                    try:
                        from app.pipeline.hybrid_retriever import HybridRetriever
                        self.retriever = HybridRetriever()
                    except Exception:
                        self.retriever = None

                rag_candidates = []
                if self.retriever is not None and text_clean.strip():
                    try:
                        # Query classical corpus for educational evidence using user's words
                        rag_hits = self.retriever.retrieve(text_clean, top_k=5)
                        for hit in rag_hits:
                            raw_score = hit.get("rrf_score", 0.0)
                            chunk_text = (hit.get("text", "") + " " + hit.get("title", "")).lower()

                            vata_cnt = chunk_text.count("vata") + chunk_text.count("vāta")
                            pitta_cnt = chunk_text.count("pitta")
                            kapha_cnt = chunk_text.count("kapha")
                            has_dosha = (vata_cnt + pitta_cnt + kapha_cnt) > 0
                            has_symptom_term = any(w in chunk_text for w in (
                                "symptom", "disorder", "morbidity", "humor", "lakshana", "shoola",
                                "agni", "ama", "prakriti", "dosha", "disease", "pain", "fever",
                                "hemorrhoid", "arsha", "digest", "sleep", "skin", "joint"
                            ))

                            # Accept hits with genuine topical overlap or positive RRF fusion score
                            if raw_score > 0 and (has_dosha or has_symptom_term):
                                assigned_dosha = "Vata"
                                if pitta_cnt > vata_cnt and pitta_cnt >= kapha_cnt:
                                    assigned_dosha = "Pitta"
                                elif kapha_cnt > vata_cnt and kapha_cnt >= pitta_cnt:
                                    assigned_dosha = "Kapha"

                                rag_candidates.append({
                                    "hit": hit,
                                    "dosha": assigned_dosha,
                                    "score": raw_score
                                })
                    except Exception:
                        rag_candidates = []

                if rag_candidates:
                    top_cand = rag_candidates[0]
                    top_hit = top_cand["hit"]
                    c_dosha = top_cand["dosha"]
                    dosha_counts[c_dosha] += 1

                    note_text = f"Retrieved classical passages correlate described sensations with {c_dosha} humor tendencies ({top_hit.get('title', 'Classical literature')})."
                    if lang_key == "hi":
                        note_text = f"पुनर्प्राप्त शास्त्रीय उद्धरण के अनुसार वर्णित लक्षण {c_dosha} दोष की शारीरिक प्रवृत्तियों से संबंधित प्रतीत होते हैं।"
                    elif lang_key == "kn":
                        note_text = f"ಪುನರ್ಪಡೆದ ಶಾಸ್ತ್ರೀಯ ಉಲ್ಲೇಖಗಳ ಪ್ರಕಾರ ವಿವರಿಸಿದ ಲಕ್ಷಣಗಳು {c_dosha} ದೋಷದ ದೈಹಿಕ ಪ್ರವೃತ್ತಿಗಳಿಗೆ ಸಂಬಂಧಿಸಿವೆ."

                    detected_mappings.append({
                        "symptom_phrase": text_clean[:60],
                        "associated_dosha": c_dosha,
                        "educational_note": note_text,
                        "source_id": top_hit.get("source_id", "Curated Classical Corpus"),
                        "locator": top_hit.get("locator", "Section QA"),
                        "provenance": f"[{top_hit.get('source_id', 'Curated Classical Corpus')}, {top_hit.get('locator', 'Section QA')}]",
                        "mapping_status": "neural_rag_retrieval",
                        "caution": "Grounded in retrieved classical corpus passages; classical literature does not provide algorithmic diagnostic predictions.",
                    })

        # 5. SAFE ABSTENTION ON AMBIGUOUS / UNVERIFIED SYMPTOMS
        if not detected_mappings:
            abstain_msg = ABSTENTION_MESSAGES.get(lang_key, ABSTENTION_MESSAGES["en"])
            return {
                "abstained": True,
                "reason": "no_supported_symptom_recognized",
                "detected_language": detected_lang,
                "target_language": lang_key,
                "is_romanized": is_romanized,
                "is_code_mixed": is_code_mixed,
                "code_mix_type": lang_info.get("code_mix_type", "monolingual"),
                "segments": lang_info.get("segments", []),
                "message": abstain_msg,
                "understood": {
                    "original_text": text,
                    "detected_language": detected_lang,
                    "target_language": lang_key,
                    "script": lang_info.get("script", "latin"),
                    "is_romanized": is_romanized,
                    "is_code_mixed": is_code_mixed,
                    "normalized_description": text_clean,
                    "extracted_symptoms": [],
                    "ayurvedic_terms": []
                },
                "mappings": [],
                "concepts": [],
                "evidence": [],
                "graph_connections": [],
                "limitations": [
                    "Educational reference only: The provided symptom description could not be correlated with catalogued Ayurvedic concepts in WHO Benchmark / NAMASTE.",
                    "Traditional records disclaimer: Traditional texts describe multi-factorial patterns (Prakriti, Agni, Ama) rather than isolated symptom predictions."
                ],
                "disclaimer": EDUCATIONAL_DISCLAIMER
            }

        # 5. SYNTHESIZE LOCALIZED EDUCATIONAL SUMMARY
        primary_dosha = max(dosha_counts.items(), key=lambda x: x[1])[0]

        # Localized Dosha Labels
        dosha_localized_names = {
            "en": {"Vata": "Vata", "Pitta": "Pitta", "Kapha": "Kapha"},
            "hi": {"Vata": "वात (Vata)", "Pitta": "पित्त (Pitta)", "Kapha": "कफ (Kapha)"},
            "kn": {"Vata": "ವಾತ (Vata)", "Pitta": "ಪಿತ್ತ (Pitta)", "Kapha": "ಕಫ (Kapha)"},
            "hi_roman": {"Vata": "Vata (वात)", "Pitta": "Pitta (पित्त)", "Kapha": "Kapha (कफ)"},
            "kn_roman": {"Vata": "Vata (ವಾತ)", "Pitta": "Pitta (ಪಿತ್ತ)", "Kapha": "Kapha (ಕಫ)"}
        }
        primary_label = dosha_localized_names.get(lang_key, dosha_localized_names["en"])[primary_dosha]

        # Localized Educational Summary Text
        if lang_key == "hi":
            summary = (
                f"शैक्षिक विश्लेषण: वर्णित शारीरिक अनुभूतियाँ प्रमाणित आयुर्वेदिक साहित्य (WHO Benchmark / NAMASTE) "
                f"के शास्त्रीय सिद्धांतों के अनुसार मुख्य रूप से {primary_label} दोष की प्रवृत्तियों से संबंधित प्रतीत होती हैं। "
                f"यह केवल पारंपरिक जीवनशैली जागरूकता के लिए एक शैक्षिक संदर्भ है, कोई चिकित्सीय निदान नहीं।"
            )
        elif lang_key == "kn":
            summary = (
                f"ಶೈಕ್ಷಣಿಕ ವಿಶ್ಲೇಷಣೆ: ವಿವರಿಸಲಾದ ದೈಹಿಕ ಲಕ್ಷಣಗಳು ಪರಿಶೀಲಿಸಿದ ಆಯುರ್ವೇದ ಸಾಹಿತ್ಯದ (WHO Benchmark / NAMASTE) "
                f"ಶಾಸ್ತ್ರೀಯ ತತ್ವಗಳ ಪ್ರಕಾರ ಮುಖ್ಯವಾಗಿ {primary_label} ದೋಷದ ಪ್ರವೃತ್ತಿಗಳಿಗೆ ಹೊಂದಿಕೆಯಾಗುತ್ತವೆ. "
                f"ಇದು ಕೇವಲ ಶೈಕ್ಷಣಿಕ ತಿಳುವಳಿಕೆಗಾಗಿ ಮಾತ್ರವಾಗಿದ್ದು, ಯಾವುದೇ ವೈದ್ಯಕೀಯ ರೋಗನಿರ್ಣಯವಲ್ಲ."
            )
        elif lang_key == "hi_roman":
            summary = (
                f"Educational Analysis: Describe kiye gaye sensations verified Ayurvedic literature (WHO / NAMASTE) "
                f"ke classical framework ke anusar primarily {primary_label} tendencies ko darshate hain. "
                f"Yeh keval traditional educational framework hai, koi medical diagnosis nahi."
            )
        elif lang_key == "kn_roman":
            summary = (
                f"Educational Analysis: Vivarisiruva sensations verified Ayurvedic literature (WHO / NAMASTE) "
                f"framework prakara mukhyavagi {primary_label} lakshanagalondige samyathe hondide. "
                f"Idu kevala educational understandingge matra, medical diagnosis alla."
            )
        else:
            summary = (
                f"Educational Analysis: The described physical sensations correlate classically with "
                f"{primary_dosha} humor tendencies in verified traditional literature (WHO Benchmark / NAMASTE). "
                f"This framework serves lifestyle awareness and is strictly not a clinical diagnosis or treatment."
            )

        # 6. RAG RETRIEVAL: Pull actual supporting passages from the corpus
        found_terms = []
        try:
            from app.core.matcher import TerminologyMatcher
            matcher = TerminologyMatcher()
            found_terms = matcher.find_terms(text)
        except Exception:
            pass

        retrieval_query_parts = []
        for m in detected_mappings:
            retrieval_query_parts.append(m["symptom_phrase"])
            retrieval_query_parts.append(m["associated_dosha"])
        for t in found_terms:
            retrieval_query_parts.append(t["canonical_term"])
        if not retrieval_query_parts:
            retrieval_query_parts.append(text_clean)

        norm_desc = " ".join(dict.fromkeys(retrieval_query_parts))
        retrieval_query = f"{norm_desc} symptoms"

        evidence_passages = []
        if self.retriever is None:
            try:
                from app.pipeline.hybrid_retriever import HybridRetriever
                self.retriever = HybridRetriever()
            except Exception:
                self.retriever = None

        if self.retriever is not None and retrieval_query.strip():
            raw_hits = self.retriever.retrieve(retrieval_query, top_k=5, detected_terms=found_terms)
            
            # Grounded relevance filtering: do NOT pad with irrelevant chunks simply to fill 5 slots
            relevant_keywords = set()
            for part in retrieval_query_parts:
                for w in part.lower().split():
                    if len(w) >= 3 and w not in ("and", "the", "with", "have", "feel", "after", "before"):
                        relevant_keywords.add(w)

            filtered_rank = 1
            for hit in raw_hits:
                raw_score = hit.get("rrf_score", 0.0)
                chunk_text = (hit.get("text", "") + " " + hit.get("title", "")).lower()
                has_term_overlap = any(kw in chunk_text for kw in relevant_keywords) if relevant_keywords else True
                if not has_term_overlap and raw_score < 0.035:
                    continue  # Filter out irrelevant filler chunks that lack topical overlap

                norm_score = round(min(1.0, raw_score * 25.0), 3)
                evidence_passages.append({
                    "chunk_id": hit.get("chunk_id", ""),
                    "source_id": hit.get("source_id", "Curated Classical Corpus"),
                    "title": hit.get("title", ""),
                    "locator": hit.get("locator", ""),
                    "text": hit.get("text", ""),
                    "snippet": hit.get("text", "")[:240].strip().replace("\n", " ") + "...",
                    "relevance_score": norm_score,
                    "rank": filtered_rank
                })
                filtered_rank += 1

        # 7. KNOWLEDGE GRAPH CONNECTIONS (Traverse v2 DiGraph for grounded concepts)
        kg_connections = []
        kg_obj = self.kg
        if not hasattr(kg_obj, "node_detail"):
            try:
                from app.core.kg_v2 import load_kg_v2
                kg2 = load_kg_v2()
                if kg2 is not None:
                    kg_obj = kg2
            except Exception:
                pass

        if kg_obj is not None and hasattr(kg_obj, "node_detail"):
            for m in detected_mappings:
                dosha_node = f"CONCEPT:{m['associated_dosha']}"
                try:
                    det = kg_obj.node_detail(dosha_node)
                    if det:
                        for rel in det.get("outgoing", [])[:3]:
                            kg_connections.append({
                                "concept": m["associated_dosha"],
                                "source_node": dosha_node,
                                "relation": rel.get("relation"),
                                "target_node": rel.get("target"),
                                "target_label": rel.get("other", {}).get("label") or rel.get("target"),
                                "target_type": rel.get("other", {}).get("type", "Concept"),
                                "review_status": rel.get("review_status", "grounded_by_code_text"),
                                "direction": "outgoing",
                                "locator": rel.get("locator", "")
                            })
                        for rel in det.get("incoming", [])[:3]:
                            kg_connections.append({
                                "concept": m["associated_dosha"],
                                "source_node": rel.get("source"),
                                "relation": rel.get("relation"),
                                "target_node": dosha_node,
                                "target_label": rel.get("other", {}).get("label") or rel.get("source"),
                                "target_type": rel.get("other", {}).get("type", "Concept"),
                                "review_status": rel.get("review_status", "project_mapping_unreviewed"),
                                "direction": "incoming",
                                "locator": rel.get("locator", "")
                            })
                except Exception:
                    pass

        understood = {
            "original_text": text,
            "detected_language": detected_lang,
            "target_language": lang_key,
            "script": lang_info.get("script", "latin"),
            "is_romanized": is_romanized,
            "is_code_mixed": is_code_mixed,
            "normalized_description": norm_desc,
            "extracted_symptoms": [m["symptom_phrase"] for m in detected_mappings],
            "ayurvedic_terms": found_terms
        }

        concepts = []
        for m in detected_mappings:
            concepts.append({
                "concept_name": m["symptom_phrase"],
                "associated_dosha": m["associated_dosha"],
                "explanation": m["educational_note"],
                "source_reference": f"{m['source_id']} ({m['locator']})",
                "relevance_score": 0.85,
                "relevance_label": "Textual & Semantic Conceptual Relevance (Non-Diagnostic)",
                "review_status": "educational_heuristic"
            })

        limitations = [
            "Educational reference only: These correlations reflect classical Ayurvedic literature (WHO Benchmark / NAMASTE) and do not constitute medical diagnosis or clinical treatment.",
            "Multi-factorial constitution: Classical Ayurveda assesses individual Prakriti, Agni (digestive fire), season (Ritucharya), and diet before evaluating physiological tendencies.",
            "Traditional records disclaimer: Traditional textual associations do not establish modern clinical efficacy or pharmaceutical safety."
        ]

        exploration_links = {
            "herbs_query": text_clean,
            "lifestyle_query": f"What does Ayurveda say about {text_clean}?",
            "dosha": primary_dosha
        }

        return {
            "abstained": False,
            "reason": None,
            "detected_language": detected_lang,
            "target_language": lang_key,
            "is_romanized": is_romanized,
            "is_code_mixed": is_code_mixed,
            "code_mix_type": lang_info.get("code_mix_type", "monolingual"),
            "segments": lang_info.get("segments", []),
            "language_key": lang_key,
            "primary_conceptual_tendency": primary_label,
            "primary_dosha_raw": primary_dosha,
            "summary": summary,
            "mappings": detected_mappings,
            "understood": understood,
            "concepts": concepts,
            "evidence": evidence_passages,
            "graph_connections": kg_connections,
            "limitations": limitations,
            "exploration_links": exploration_links,
            "disclaimer": EDUCATIONAL_DISCLAIMER
        }

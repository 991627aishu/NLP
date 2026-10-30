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
    }
]


class EducationalSymptomMapper:
    """
    Multilingual Educational Symptom-to-Concept Mapper.
    Provides verified classical mappings, strictly enforces medical safety red flags,
    and returns localized responses matching the user's detected language.
    """

    def __init__(self, kg: Optional[AyurKnowledgeGraph] = None):
        self.kg = kg or AyurKnowledgeGraph()

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
                    "reason": "emergency_symptom_detected",
                    "detected_language": detected_lang,
                    "target_language": lang_key,
                    "is_romanized": is_romanized,
                    "is_code_mixed": is_code_mixed,
                    "code_mix_type": lang_info.get("code_mix_type", "monolingual"),
                    "segments": lang_info.get("segments", []),
                    "matched_red_flag": red_flag,
                    "emergency_alert": alert_msg,
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

        # 4. SAFE ABSTENTION ON AMBIGUOUS / UNVERIFIED SYMPTOMS
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
                "mappings": [],
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
            "disclaimer": EDUCATIONAL_DISCLAIMER
        }

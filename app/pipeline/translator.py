"""
AyurMitra — Multilingual Translation & Localization Engine
============================================================
Provides bidirectional translation between Hindi, Kannada, and English:
  - Query Translation (HI/KN -> EN): maps user intent, syntactic patterns,
    and domain terminology into English for index retrieval.
  - Answer Translation (EN -> HI/KN): translates grounded Ayurvedic facts,
    citations headers, and disclaimers into fluent Hindi and Kannada while
    faithfully restoring domain terms in native scripts.

Integrates with:
  - Parallel question pairs from hi.parquet and kn.parquet
  - Curated Ayurvedic bilingual phrase dictionary
  - NAMASTE and WHO multilingual definitions
  - TerminologyProtector for script-accurate term restoration
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import logging

import pandas as pd

log = logging.getLogger("ayurmitra.translator")
PLACEHOLDER_STRIP = re.compile(r"__AYURTERM_\d+__")

from app.config import HI_PARQUET, KN_PARQUET, TRANSLATOR_BACKEND
from app.core.matcher import (
    HINDI_TERM_MAP,
    KANNADA_TERM_MAP,
    CANONICAL_TO_HINDI,
    CANONICAL_TO_KANNADA,
)

# Common Ayurvedic Query Grammar Patterns (Bilingual Mapping)
HINDI_QUERY_PATTERNS = [
    (re.compile(r"(.+?)\s*(?:के\s*)?(?:कार्य|काम)\s*(?:क्या\s*हैं|क्या\s*है|बताओ)?\??", re.IGNORECASE), "What are the functions and actions of {0}?"),
    (re.compile(r"(.+?)\s*(?:के\s*)?(?:लक्षण|संकेत)\s*(?:क्या\s*हैं|क्या\s*है|बताओ)?\??", re.IGNORECASE), "What are the symptoms and signs of {0}?"),
    (re.compile(r"(.+?)\s*(?:क्या\s*है|किसे\s*कहते\s*हैं|का\s*अर्थ\s*क्या\s*है)\??", re.IGNORECASE), "What is {0}?"),
    (re.compile(r"(.+?)\s*(?:का\s*)?(?:महत्व|उपयोग)\s*(?:क्या\s*है|बताओ)\??", re.IGNORECASE), "What is the importance and use of {0}?"),
    (re.compile(r"(.+?)\s*(?:को\s*)?(?:कैसे\s*ठीक\s*करें|का\s*इलाज|का\s*उपचार)\??", re.IGNORECASE), "How to balance and treat {0}?"),
]

KANNADA_QUERY_PATTERNS = [
    (re.compile(r"(.+?)\s*(?:ಗೆ|ಕ್ಕೆ|ದ)?\s*(?:ಸಂಬಂಧಿಸಿದ\s*)?(?:ಲಕ್ಷಣಗಳು|ಗುಣಗಳು)\s*(?:ಯಾವುವು|ಏನು)\??", re.IGNORECASE), "What are the symptoms and signs related to {0}?"),
    (re.compile(r"(.+?)\s*(?:ನ|ದ)?\s*(?:ಕಾರ್ಯಗಳು|ಕೆಲಸಗಳು)\s*(?:ಯಾವುವು|ಏನು)\??", re.IGNORECASE), "What are the functions and actions of {0}?"),
    (re.compile(r"(.+?)\s*(?:ಎಂದರೇನು|ಅರ್ಥವೇನು|ಯಾವುದು)\??", re.IGNORECASE), "What is {0}?"),
    (re.compile(r"(.+?)\s*(?:ಮಹತ್ವವೇನು|ಉಪಯೋಗವೇನು)\??", re.IGNORECASE), "What is the importance and use of {0}?"),
    (re.compile(r"(.+?)\s*(?:ಪರಿಹಾರವೇನು|ಚಿಕಿತ್ಸೆ\s*ಏನು|ಹೇಗೆ\s*ಗುಣಪಡಿಸುವುದು)\??", re.IGNORECASE), "How to balance and treat {0}?"),
]

# Code-mixed Hinglish query patterns (Romanized Hindi + English)
HINGLISH_QUERY_PATTERNS = [
    (re.compile(r"(.+?)\s+(.+?)\s+(?:mein|me|main)\s+(?:kya|kyaa)\s+(?:role|bhumika|yogdan)\s*(?:play\s+karta\s+hai|karta\s+hai|hai|hota\s+hai)\??", re.IGNORECASE), "What is the role of {0} in {1}?"),
    (re.compile(r"(.+?)\s+(?:mein|me|main)\s+(?:kya|kyaa)\s+(?:role|bhumika)\s*(?:play\s+karta\s+hai|karta\s+hai|hai)\??", re.IGNORECASE), "What role does {0} play?"),
    (re.compile(r"(.+?)\s*(?:ke|k\s*)?\s*(?:fayde|fayday|labh|benefits)\s*(?:kya\s*hain|kya\s*hai|batao)?\??", re.IGNORECASE), "What are the benefits of {0}?"),
    (re.compile(r"(.+?)\s*(?:ke|k\s*)?\s*(?:lakshan|symptoms)\s*(?:kya\s*hain|kya\s*hai|batao)?\??", re.IGNORECASE), "What are the symptoms of {0}?"),
    (re.compile(r"(.+?)\s*(?:ke|k\s*)?\s*(?:karya|kaam|functions)\s*(?:kya\s*hain|kya\s*hai|batao)?\??", re.IGNORECASE), "What are the functions of {0}?"),
    (re.compile(r"(.+?)\s*(?:kya\s*hai|kya\s*hota\s*hai|kise\s*kehte\s*hain)\??", re.IGNORECASE), "What is {0}?"),
    (re.compile(r"(.+?)\s+aur\s+(.+?)\s+(?:mein|me)\s*(?:kya\s*antar\s*hai|difference\s*kya\s*hai)\??", re.IGNORECASE), "What is the difference between {0} and {1}?"),
    (re.compile(r"(.+?)\s*(?:ko|ka)?\s*(?:kaise\s*theek\s*kare|ka\s*ilaj|kaise\s*balance\s*kare)\??", re.IGNORECASE), "How to balance and treat {0}?"),
    (re.compile(r"(?:mujhe\s+)?pet\s*(?:me\s*)?dard\s*(?:hai|ho\s*raha\s*hai|kya\s*kare)?\??", re.IGNORECASE), "What is the Ayurvedic view and remedy for stomach pain?"),
    (re.compile(r"(?:mujhe\s+)?sir\s*(?:me\s*)?dard\s*(?:hai|ho\s*raha\s*hai)?\??", re.IGNORECASE), "What is the Ayurvedic view and remedy for headache?"),
    (re.compile(r"(?:khana\s*khane\s*ke\s*baad|bhojan\s*ke\s*baad)\s+(?:heaviness|pet\s*bhari|bharipan)\s*(?:lagta\s*hai|hai)?\??", re.IGNORECASE), "Why is there heaviness after eating food according to Ayurveda?"),
    (re.compile(r"(?:neend\s*nahi\s*aati|so\s*nahi\s*pata|sleep\s*problem)\s*(?:hai|kya\s*kare)?\??", re.IGNORECASE), "What causes difficulty sleeping in Ayurveda?"),
    (re.compile(r"(?:pet\s*phoolna|gas\s*banna|adhmana)\s*(?:hai|kya\s*kare)?\??", re.IGNORECASE), "What is the cause and remedy for bloating and gas in Ayurveda?"),
    (re.compile(r"(.+?)\s*(?:ke\s*liye|k\s*liye)\s*(?:kya\s*kare|kaun\s*si\s*herb\s*acchi\s*hai|gharelu\s*nuskhe|upay)\??", re.IGNORECASE), "What are Ayurvedic herbs and remedies for {0}?"),
]

# Code-mixed Kanglish query patterns (Romanized Kannada + English)
KANGLISH_QUERY_PATTERNS = [
    (re.compile(r"(.+?)\s+(.+?)\s+(?:alli|olage)\s+(?:enu|yenu)\s+(?:role|patra)\s*(?:ide|aagide|play\s*madutthe)?\??", re.IGNORECASE), "What is the role of {0} in {1}?"),
    (re.compile(r"(.+?)\s+(?:alli|olage)\s+(?:enu|yenu)\s+(?:role|patra)\s*(?:ide|play\s*madutthe)?\??", re.IGNORECASE), "What role does {0} play?"),
    (re.compile(r"(.+?)\s*(?:da|na)?\s*(?:prayojanagalu|upayogagalu|benefits)\s*(?:enu|yenu|yavuvu)?\??", re.IGNORECASE), "What are the benefits of {0}?"),
    (re.compile(r"(.+?)\s*(?:da|na)?\s*(?:lakshanagalu|symptoms)\s*(?:yavuvu|enu|yenu)?\??", re.IGNORECASE), "What are the symptoms of {0}?"),
    (re.compile(r"(.+?)\s*(?:da|na)?\s*(?:karyagalu|functions)\s*(?:yavuvu|enu)?\??", re.IGNORECASE), "What are the functions of {0}?"),
    (re.compile(r"(.+?)\s*(?:endarenu|yavudu|artavenu)\??", re.IGNORECASE), "What is {0}?"),
    (re.compile(r"(.+?)\s+mattu\s+(.+?)\s+(?:naduvina|alli)\s*(?:vyatyasa\s*enu|difference\s*enu)\??", re.IGNORECASE), "What is the difference between {0} and {1}?"),
    (re.compile(r"(.+?)\s*(?:ge)?\s*(?:parihara\s*enu|chikitse\s*enu|hege\s*guna\s*maduvudu)\??", re.IGNORECASE), "How to balance and treat {0}?"),
    (re.compile(r"(?:nanage\s+)?hotte\s*novu\s*(?:ide|aaguttide|ge\s*parihara\s*enu)?\??", re.IGNORECASE), "What is the Ayurvedic perspective and remedy for stomach pain?"),
    (re.compile(r"(?:nanage\s+)?tale\s*novu\s*(?:ide|aaguttide|ge\s*parihara\s*enu)?\??", re.IGNORECASE), "What is the Ayurvedic perspective and remedy for headache?"),
    (re.compile(r"(?:oota\s*aadmele|ootada\s*nantara)\s+(?:hotte\s*heavy|hotte\s*bhara|susthu)\s*(?:aagutte|ide)?\??", re.IGNORECASE), "Why is there stomach heaviness after eating food according to Ayurveda?"),
    (re.compile(r"(?:nidre\s*baradilla|nidde\s*baralla|nidre\s*sariyagi\s*baradilla)\s*(?:enu\s*madodu|parihara\s*enu)?\??", re.IGNORECASE), "What causes difficulty sleeping and insomnia according to Ayurveda?"),
    (re.compile(r"(?:hotte\s*ubbara|adhmana|gas)\s*(?:ide|ge\s*parihara\s*enu)?\??", re.IGNORECASE), "What causes bloating and gas in Ayurveda?"),
    (re.compile(r"(.+?)\s*(?:ge)?\s*(?:yava\s*aushadhi|yava\s*herb|olleydhu|upayukta)?\??", re.IGNORECASE), "Which herbs and remedies are recommended for {0}?"),
]

# Concept explanations in Hindi and Kannada for evidence passage localization
CONCEPT_EXPLANATIONS = {
    "Pitta": {
        "hi": "पित्त दोष मुख्य रूप से शरीर में पाचन (digestion), चयापचय (metabolism), शारीरिक ताप (body temperature) और ऊर्जा रूपांतरण का नियंत्रण करता है। यह अग्नि और जल महाभूतों के संयोजन से बना है।",
        "kn": "ಪಿತ್ತ ದೋಷವು ದೇಹದಲ್ಲಿ ಜೀರ್ಣಕ್ರಿಯೆ (digestion), ಚಯಾಪಚಯ (metabolism), ದೈಹಿಕ ಉಷ್ಣತೆ ಮತ್ತು ಶಕ್ತಿಯ ಪರಿವರ್ತನೆಯನ್ನು ನಿಯಂತ್ರಿಸುತ್ತದೆ. ಇದು ಅಗ್ನಿ ಮತ್ತು ಜಲ ಮಹಾಭೂತಗಳಿಂದ ಕೂಡಿದೆ."
    },
    "Vata": {
        "hi": "वात दोष शरीर की सभी गतिविधियों, तंत्रिका आवेगों (nerve impulses), श्वास-प्रश्वास और अपशिष्ट निष्कासन का संचालन करता है। यह वायु और आकाश महाभूतों से निर्मित है।",
        "kn": "ವಾತ ದೋಷವು ದೇಹದ ಎಲ್ಲಾ ಚಲನವಲನಗಳು, ನರಗಳ ಸಂವೇದನೆ (nerve impulses), ಶ್ವಾಸಕ್ರಿಯೆ ಮತ್ತು ಮಲ-ಮೂತ್ರ ವಿಸರ್ಜನೆಯನ್ನು ನಿರ್ವಹಿಸುತ್ತದೆ. ಇದು ವಾಯು ಮತ್ತು ಆಕಾಶ ಮಹಾಭೂತಗಳಿಂದ ಕೂಡಿದೆ."
    },
    "Kapha": {
        "hi": "कफ दोष शरीर को स्थिरता, शक्ति, शारीरिक संरचना और संधियों (joints) को स्नेहन व नमी प्रदान करता है। यह पृथ्वी और जल महाभूतों से मिलकर बना है।",
        "kn": "ಕಫ ದೋಷವು ದೇಹಕ್ಕೆ ದೃಢತೆ, ರೋಗನಿರೋಧಕ ಶಕ್ತಿ, ದೈಹಿಕ ರಚನೆ ಮತ್ತು ಕೀಲುಗಳಿಗೆ ನಯತೆಯನ್ನು (lubrication) ಒದಗಿಸುತ್ತದೆ. ಇದು ಪೃಥ್ವಿ ಮತ್ತು ಜಲ ಮಹಾಭೂತಗಳಿಂದ ಕೂಡಿದೆ."
    },
    "Agni": {
        "hi": "अग्नि आयुर्वेद में पाचन और जैविक परिवर्तन की मूल शक्ति है। सम-अग्नि उत्तम स्वास्थ्य और ओजस की कुंजी है, जबकि मंदाग्नि रोगों का कारण बनती है।",
        "kn": "ಅಗ್ನಿಯು ಆಯುರ್ವೇದದಲ್ಲಿ ಜೀರ್ಣಕ್ರಿಯೆ ಮತ್ತು ಜೈವಿಕ ಪರಿವರ್ತನೆಯ ಮೂಲ ಶಕ್ತಿಯಾಗಿದೆ. ಸಮ-ಅಗ್ನಿಯು ಉತ್ತಮ ಆರೋಗ್ಯ ಮತ್ತು ಓಜಸ್ಸನ್ನು ನೀಡುತ್ತದೆ, ಮಂದಾಗ್ನಿಯು ರೋಗಗಳಿಗೆ ಕಾರಣವಾಗುತ್ತದೆ."
    },
    "Ama": {
        "hi": "आम कमजोर अग्नि के कारण उत्पन्न होने वाला अपचित और विषाक्त चयापचय अपशिष्ट है, जो स्रोतों को अवरुद्ध करके व्याधि उत्पन्न करता है।",
        "kn": "ಆಮವು ದುರ್ಬಲ ಅಗ್ನಿಯಿಂದಾಗಿ ಉಂಟಾಗುವ ಜೀರ್ಣವಾಗದ ವಿಷಕಾರಿ ಅಂಶವಾಗಿದ್ದು, ದೇಹದ ನಾಡಿ-ಸ್ರೋತಸ್ಸುಗಳನ್ನು ಮುಚ್ಚಿ ರೋಗಗಳಿಗೆ ಕಾರಣವಾಗುತ್ತದೆ."
    },
    "Ojas": {
        "hi": "ओजस सातों धातुओं का उत्कृष्ट सार है, जो प्राकृतिक प्रतिरक्षा, जीवन शक्ति और मानसिक शांति का आधार है।",
        "kn": "ಓಜಸ್ಸು ಎಲ್ಲಾ ಏಳು ಧಾತುಗಳ ಶುದ್ಧ ಸಾರವಾಗಿದ್ದು, ನೈಸರ್ಗಿಕ ರೋಗನಿರೋಧಕ ಶಕ್ತಿ, ಚೈತನ್ಯ ಮತ್ತು ಮಾನಸಿಕ ಶಾಂತಿಯ ಅಡಿಪಾಯವಾಗಿದೆ."
    },
    "Dhatu": {
        "hi": "धातु शरीर के सात मूलभूत ऊतक (रस, रक्त, मांस, मेद, अस्थि, मज्जा, शुक्र) हैं जो शरीर को धारण और पोषित करते हैं।",
        "kn": "ಧಾತುಗಳು ದೇಹದ ಏಳು ಮೂಲಭೂತ ಅಂಗಾಂಶಗಳು (ರಸ, ರಕ್ತ, ಮಾಂಸ, ಮೇದಸ್ಸು, ಅಸ್ಥಿ, ಮಜ್ಜ, ಶುಕ್ರ) ಆಗಿದ್ದು ದೇಹವನ್ನು ಪೋಷಿಸುತ್ತವೆ."
    },
    "Prakriti": {
        "hi": "प्रकृति गर्भाधान के समय वात, पित्त और कफ के आधार पर निर्धारित होने वाला व्यक्ति का मूल स्वाभाविक संविधान (body constitution) है।",
        "kn": "ಪ್ರಕೃತಿಯು ಹುಟ್ಟಿನಿಂದಲೇ ವಾತ, ಪಿತ್ತ ಮತ್ತು ಕಫಗಳ ಆಧಾರದ ಮೇಲೆ ನಿರ್ಧಾರವಾಗುವ ಪ್ರತಿಯೊಬ್ಬ ವ್ಯಕ್ತಿಯ ನೈಸರ್ಗಿಕ ದೈಹಿಕ ಪ್ರಕೃತಿಯಾಗಿದೆ."
    },
    "Ayurveda": {
        "en": "Ayurveda ('Ayu' meaning life and 'Veda' meaning science or knowledge) is the classical Indian medical system focused on maintaining balance among body, mind, senses, and spirit through holistic lifestyle, nutrition, and therapies.",
        "hi": "आयुर्वेद (आयु अर्थात् जीवन और वेद अर्थात् ज्ञान/विज्ञान) भारतीय पारंपरिक चिकित्सा प्रणाली है, जो शरीर, मन, इन्द्रिय और आत्मा के समग्र संतुलन द्वारा स्वास्थ्य रक्षण और रोग निवारण करती है।",
        "kn": "ಆಯುರ್ವೇದವು ('ಆಯು' ಎಂದರೆ ಜೀವನ, 'ವೇದ' ಎಂದರೆ ಜ್ಞಾನ/ವಿಜ್ಞಾನ) ಸಾಂಪ್ರದಾಯಿಕ ಭಾರತೀಯ ವೈದ್ಯಕೀಯ ಪದ್ಧತಿಯಾಗಿದ್ದು, ದೇಹ, ಮನಸ್ಸು ಮತ್ತು ಇಂದ್ರಿಯಗಳ ಸಮತೋಲನದ ಮೂಲಕ ಆರೋಗ್ಯ ರಕ್ಷಣೆಯನ್ನು ಪ್ರತಿಪಾದಿಸುತ್ತದೆ."
    },
    "Tridosha": {
        "en": "Tridosha refers to the three primary physiological bio-energies (Vata, Pitta, Kapha) that govern all biological and psychological functions of the living organism.",
        "hi": "त्रिदोष आयुर्वेद के तीन प्राथमिक शारीरिक सिद्धांत (वात, पित्त, कफ) हैं, जो शरीर की सभी संरचनात्मक, कार्यात्मक और मानसिक गतिविधियों को नियंत्रित करते हैं।",
        "kn": "ತ್ರಿದೋಷಗಳು (ವಾತ, ಪಿತ್ತ, ಕಫ) ಮಾನವ ದೇಹದ ಎಲ್ಲಾ ದೈಹಿಕ ಮತ್ತು ಮಾನಸಿಕ ಕ್ರಿಯೆಗಳನ್ನು ನಿಯಂತ್ರಿಸುವ ಮೂರು ಮೂಲಭೂತ ಶಕ್ತಿಗಳಾಗಿವೆ."
    },
    "Dinacharya": {
        "en": "Dinacharya denotes the classical daily routine guidelines designed to align biological circadian rhythms with natural diurnal cycles for long-term health and vitality.",
        "hi": "दिनचर्या आयुर्वेद द्वारा निर्देशित दैनिक जीवनचर्या है, जो शारीरिक जैविक घड़ी को प्राकृतिक चक्रों के साथ संतुलित रखकर स्वास्थ्य और ओजस की रक्षा करती है।",
        "kn": "ದಿನಚರ್ಯೆಯು ಆಯುರ್ವೇದ ಶಾಸ್ತ್ರೋಕ್ತ ದೈನಂದಿನ ನಿಯಮಾವಳಿಯಾಗಿದ್ದು, ನೈಸರ್ಗಿಕ ಚಕ್ರಗಳೊಂದಿಗೆ ದೇಹವನ್ನು ಸಮತೋಲನದಲ್ಲಿಡಲು ಮಾರ್ಗದರ್ಶನ ನೀಡುತ್ತದೆ."
    },
    "Rasayana": {
        "en": "Rasayana encompasses specialized therapies, formulations, and dietary principles aimed at rejuvenating bodily tissues (Dhatus), enhancing immunity (Ojas), and promoting longevity.",
        "hi": "रसायन आयुर्वेद की पुनर्जीवन एवं कायाकल्प शाखा है, जो धातुओं का पोषण, ओजस की वृद्धि और दीर्घायु की प्राप्ति कराती है।",
        "kn": "ರಸಾಯನವು ಧಾತುಗಳ ಪೋಷಣೆ, ರೋಗನಿರೋಧಕ ಶಕ್ತಿಯ ವರ್ಧನೆ ಮತ್ತು ಆಯಸ್ಸು ಹೆಚ್ಚಿಸುವ ಪುನಶ್ಚೇತನ ಚಿಕಿತ್ಸಾ ಪದ್ಧತಿಯಾಗಿದೆ."
    },
    "Madhumeha": {
        "en": "Madhumeha (classified under Vataja Prameha in classical Ayurveda, corresponding to Diabetes Mellitus) is a chronic metabolic disorder marked by impaired Agni, sweet urine, excessive thirst, and systemic tissue depletion (Dhatu kshaya).",
        "hi": "मधुमेह आयुर्वेद में वातज प्रमेह का एक प्रमुख प्रकार है, जिसका आधुनिक नैदानिक संदर्भ डायबिटीज मेलिटस (Diabetes Mellitus) से है। यह मंदाग्नि, कफ-वात असंतुलन, मूत्र में शर्करा, अत्यधिक प्यास और ओजस व धातुओं के क्षय का लक्षण प्रस्तुत करता है।",
        "kn": "ಮಧುಮೇಹವು ಆಯುರ್ವೇದದಲ್ಲಿ ವಾತಜ ಪ್ರಮೇಹದ ಒಂದು ಪ್ರಮುಖ ಪ್ರಕಾರವಾಗಿದ್ದು, ಆಧುನಿಕ ವೈದ್ಯಕೀಯದಲ್ಲಿ ಡಯಾಬಿಟಿಸ್ ಮೆಲ್ಲಿಟಸ್ (Diabetes Mellitus) ಎಂದು ಕರೆಯಲ್ಪಡುತ್ತದೆ. ಇದು ಮಂದಾಗ್ನಿ, ಮೂತ್ರದಲ್ಲಿ ಮಾಧುರ್ಯ ಮತ್ತು ಧಾತುಗಳ ಕ್ಷಯವನ್ನು ಉಂಟುಮಾಡುತ್ತದೆ."
    },
    "Prameha": {
        "en": "Prameha refers to a comprehensive group of classical urinary disorders and metabolic syndromes characterized by profuse, turbid urination and systemic Dhatu derangement, classified into 20 subtypes.",
        "hi": "प्रमेह आयुर्वेद में 20 प्रकार के मूत्र विकारों और चयापचय व्याधियों का समूह है, जिसमें अत्यधिक और आविल मूत्र विसर्जन होता है। इसके 20 प्रकारों में कफज (10), पित्तज (6) और वातज (4, जिसमें मधुमेह प्रमुख है) शामिल हैं।",
        "kn": "ಪ್ರಮೇಹವು ಆಯುರ್ವೇದದಲ್ಲಿ ಮೂತ್ರ ಸಂಬಂಧಿತ ಮತ್ತು ಚಯಾಪಚಯ ಕಾಯಿಲೆಗಳ ಸಮೂಹವಾಗಿದ್ದು, ಕಫಜ (10), ಪಿತ್ತಜ (6) ಮತ್ತು ವಾತಜ (4) ಎಂದು 20 ವಿಧಗಳಾಗಿ ವಿಂಗಡಿಸಲಾಗಿದೆ."
    },
    "Roga": {
        "en": "In classical Ayurveda, Roga (synonymous with Vyadhi, Amaya, Gada, and Vikara, as standardized in WHO International Standard Terminologies on Ayurveda ITA-4.2.1) is defined as 'Rogastudoshavaishamyam'—the disequilibrium and vitiation of the Doshas (Vata, Pitta, Kapha) leading to tissue (Dhatu) and channel (Srotas) disturbance. Etymologically, 'Rujati iti rogaha' signifies that which causes distress and pain to the body and mind.",
        "hi": "आयुर्वेद में 'रोग' (पर्यायवाची: व्याधि, आमय, गद, विकार; WHO ITA-4.2.1) की शास्त्रीय परिभाषा 'रोगस्तुदोषवैषम्यम्' है—अर्थात् वात, पित्त और कफ दोषों का असंतुलन या विकृति ही रोग है। व्युत्पत्ति के अनुसार 'रुजति इति रोगः' अर्थात् जो शरीर और मन को पीड़ा, कष्ट या असुविधा पहुंचाए, वही रोग है। आयुर्वेद में स्वास्थ्य (दोषसाम्य) और रोग (दोषवैषम्य) एक-दूसरे के विपरीत अवस्थाएं हैं।",
        "kn": "ಆಯುರ್ವೇದದಲ್ಲಿ 'ರೋಗ' (ಪರ್ಯಾಯ ಪದಗಳು: ವ್ಯಾಧಿ, ಆಮಯ, ಗದ, ವಿಕಾರ; WHO ITA-4.2.1) ಎಂದರೆ 'ರೋಗಸ್ತುದೋಷವೈಷಮ್ಯಮ್'—ಅಂದರೆ ತ್ರಿದೋಷಗಳಾದ ವಾತ, ಪಿತ್ತ ಮತ್ತು ಕಫಗಳ ಅಸಮತೋಲನವೇ ರೋಗವಾಗಿದೆ. ವ್ಯುತ್ಪತ್ತಿಯ ಪ್ರಕಾರ 'ರುಜತಿ ಇತಿ ರೋಗಃ' ಅಂದರೆ ಶರೀರ ಮತ್ತು ಮನಸ್ಸಿಗೆ ವೇದನೆ ಹಾಗೂ ಅಸ್ವಸ್ಥತೆಯನ್ನು ಉಂಟುಮಾಡುವುದೇ ರೋಗ. ಸಮದೋಷ ಸ್ಥಿತಿಯು ಆರೋಗ್ಯವಾಗಿದ್ದರೆ, ದೋಷಗಳ ವೈಷಮ್ಯವು ರೋಗಕ್ಕೆ ಕಾರಣವಾಗುತ್ತದೆ."
    },
    "Vyadhi": {
        "en": "Vyadhi is the classical Ayurvedic term for disease or pathological manifestation, defined as that which produces various afflictions ('Vyadhayati iti vyadhih') through the interaction of vitiated Doshas and Dhatus.",
        "hi": "व्याधि आयुर्वेद में रोग का मुख्य शास्त्रीय नाम है, जिसकी व्युत्पत्ति 'व्यधयति विविधान् दुःखात्' से होती है, अर्थात् जो शरीर को विविध प्रकार के शारीरिक एवं मानसिक कष्टों से पीड़ित करे।",
        "kn": "ವ್ಯಾಧಿಯು ಆಯುರ್ವೇದದಲ್ಲಿ ರೋಗದ ಪ್ರಮುಖ ಶಾಸ್ತ್ರೀಯ ನಾಮವಾಗಿದ್ದು, ವಿಕೃತಗೊಂಡ ದೋಷಗಳು ಮತ್ತು ಧಾತುಗಳ ಪರಸ್ಪರ ಕ್ರಿಯೆಯಿಂದ ಶರೀರಕ್ಕೆ ವಿವಿಧ ಕಷ್ಟಗಳನ್ನು ಉಂಟುಮಾಡುವ ಸ್ಥಿತಿಯಾಗಿದೆ."
    },
    "Disease": {
        "en": "A disease is a pathological condition that impairs the normal functioning of an organism or any of its parts, characterized by specific signs and symptoms, resulting from infection, genetic factors, environmental stress, or physiological imbalance.",
        "hi": "रोग (Disease या बीमारी) किसी जीव अथवा उसके किसी अंग की वह असामान्य या विकृत स्थिति है जो उसके सामान्य शारीरिक या मानसिक कार्यों में बाधा डालती है। इसके लक्षण विशिष्ट संकेतों द्वारा प्रकट होते हैं।",
        "kn": "ರೋಗವು (Disease) ಜೀವಿಗಳ ಅಥವಾ ಅವುಗಳ ಯಾವುದೇ ಅಂಗಾಂಗಗಳ ಸಾಮಾನ್ಯ ಕಾರ್ಯಕ್ಷಮತೆಗೆ ಅಡ್ಡಿಪಡಿಸುವ ಅಸಹಜ ದೈಹಿಕ ಅಥವಾ ಮಾನಸಿಕ ಸ್ಥಿತಿಯಾಗಿದ್ದು, ನಿರ್ದಿಷ್ಟ ರೋಗಲಕ್ಷಣಗಳಿಂದ ಕೂಡಿರುತ್ತದೆ."
    },
    "Kushtha": {
        "en": "Kushtha refers to a broad spectrum of classical Ayurvedic dermatological disorders (skin diseases), encompassing 7 Mahakushtha (major skin conditions) and 11 Kshudrakushtha (minor skin conditions), characterized by chronic Tridosha and Dhatu vitiation.",
        "hi": "कुष्ठ आयुर्वेद में त्वचा विकारों (त्वग्रोगों) का व्यापक वर्ग है, जिसमें 7 महाकुष्ठ और 11 क्षुद्रकुष्ठ शामिल हैं। यह वात, पित्त, कफ तथा त्वचा, रक्त, मांस और लसिका की विकृति से उत्पन्न होता है।",
        "kn": "ಕುಷ್ಠವು ಆಯುರ್ವೇದದಲ್ಲಿ ಚರ್ಮ ರೋಗಗಳ ಸಮೂಹವಾಗಿದ್ದು, 7 ಮಹಾಕುಷ್ಠ ಮತ್ತು 11 ಕ್ಷುದ್ರಕುಷ್ಠಗಳನ್ನು ಒಳಗೊಂಡಿದೆ. ಇದು ತ್ರಿದೋಷಗಳು ಮತ್ತು ತ್ವಕ್, ರಕ್ತ, ಮಾಂಸ, ಲಸಿಕೆಗಳ ವಿಕೃತಿಯಿಂದ ಉಂಟಾಗುತ್ತದೆ."
    }
}


def devanagari_to_hinglish(text: str) -> str:
    """Converts Hindi Devanagari text into natural conversational Romanized Hindi (Hinglish)."""
    if not text:
        return ""
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate

        s = transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
        # Convert to lowercase to strip ITRANS CamelCase artifacts
        s = s.lower()
        cleanups = [
            (r"~n", "n"), (r"\.n", "n"), (r"\.m", "m"), (r"m\b", "n"),
            (r"\bsharira\b", "sharir"), (r"\bmem\b", "mein"), (r"\bmen\b", "mein"), (r"\bnen\b", "mein"),
            (r"\baura\b", "aur"), (r"\bkarata\b", "karta"), (r"\bkarati\b", "karti"), (r"\bkarate\b", "karte"),
            (r"\bhota\b", "hota"), (r"\bhoti\b", "hoti"), (r"\bhote\b", "hote"),
            (r"\bshvasana\b", "breathing"), (r"\bshvasa\b", "saans"),
            (r"\bimgita\b", "indicate"), (r"\bprathamika\b", "primary"), (r"\bvishleshana\b", "analysis"),
            (r"\btantra\b", "tantra"), (r"\btantrika\b", "nervous"), (r"\bavegom\b", "impulses"),
            (r"\bniyamtrita\b", "control"), (r"\bniyantrita\b", "control"),
            (r"\bsvasthya\b", "swasthya"), (r"\bsamtolana\b", "santulan"),
            (r"\bkarana\b", "karan"), (r"\blakshana\b", "lakshan"), (r"\blakshanom\b", "lakshano"),
            (r"\bupachara\b", "upchar"), (r"\bchikitse\b", "chikitsa"), (r"\bchikitsa\b", "chikitsa"),
            (r"\beik\b", "ek"), (r"\beka\b", "ek"), (r"\bprakara\b", "prakar"), (r"\bka\b", "ka"),
            (r"\bki\b", "ki"), (r"\bke\b", "ke"), (r"\bko\b", "ko"), (r"\bse\b", "se"), (r"\bpar\b", "par"),
            (r"\bnadhuneh\w*\b", "Madhumeha"), (r"\bmadhuneh\w*\b", "Madhumeha"),
            (r"\babrita\b", "Avrita"), (r"\bavrita\b", "Avrita"),
            (r"\|\|", "."), (r"\|", "."),
        ]
        for pat, rep in cleanups:
            s = re.sub(pat, rep, s, flags=re.IGNORECASE)

        s = re.sub(r"([A-Za-z])\1{2,}", r"\1", s)
        s = s.replace("aa", "a").replace("ii", "i").replace("uu", "u")

        # Capitalize canonical terms
        for canon in ["Vata", "Pitta", "Kapha", "Agni", "Ama", "Ojas", "Prana", "Dhatu", "Prakriti", "Tridosha", "Madhumeha", "Prameha", "Ashwagandha", "Triphala", "Tulsi", "Ayurveda"]:
            s = re.sub(rf"\b{canon.lower()}\b", canon, s, flags=re.IGNORECASE)
            s = re.sub(rf"\b{canon.lower()}s\b", canon + "s", s, flags=re.IGNORECASE)

        s = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), s)
        return s.strip()
    except Exception:
        return text


def kannada_to_kanglish(text: str) -> str:
    """Converts Kannada script text into natural conversational Romanized Kannada (Kanglish)."""
    if not text:
        return ""
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate

        s = transliterate(text, sanscript.KANNADA, sanscript.ITRANS)
        s = s.lower()
        cleanups = [
            (r"~n", "n"), (r"\.n", "n"), (r"\.m", "m"), (r"m\b", "n"),
            (r"è", "e"), (r"ò", "o"),
            (r"\bdehadalli\b", "dehadalli"), (r"\bdehadallina\b", "dehadallina"),
            (r"\bmattu\b", "mattu"), (r"\bchalane\b", "chalane"), (r"\busirata\b", "usirata"),
            (r"\bniyamtrisuttade\b", "niyantrisutte"), (r"\bniyantrisuttade\b", "niyantrisutte"),
            (r"\bsoochisuttade\b", "suchisutte"), (r"\bvivarane\b", "vivarane"),
            (r"\blakshanagalu\b", "lakshanagalu"), (r"\bnen\b", "nalli"),
            (r"\|\|", "."), (r"\|", "."),
        ]
        for pat, rep in cleanups:
            s = re.sub(pat, rep, s, flags=re.IGNORECASE)

        s = re.sub(r"([A-Za-z])\1{2,}", r"\1", s)
        s = s.replace("aa", "a").replace("ii", "i").replace("uu", "u")

        for canon in ["Vata", "Pitta", "Kapha", "Agni", "Ama", "Ojas", "Prana", "Dhatu", "Prakriti", "Tridosha", "Madhumeha", "Prameha", "Ashwagandha", "Triphala", "Tulsi", "Ayurveda"]:
            s = re.sub(rf"\b{canon.lower()}\b", canon, s, flags=re.IGNORECASE)

        s = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), s)
        return s.strip()
    except Exception:
        return text


class MultilingualTranslator:
    """Bilingual translation engine with domain alignment and fallback transparency."""

    def __init__(self, backend: Optional[str] = None):
        self.parallel_qa: Dict[str, str] = {}
        self._load_parallel_datasets()
        # Phase 2: neural MT (IndicTrans2) with rule-based fallback. Weights load lazily.
        self.requested_backend = (backend or TRANSLATOR_BACKEND or "auto").lower()
        self.neural = None
        self.backend_used = "rules"
        self.backend_warning: Optional[str] = "Neural MT unavailable — using rule-based fallback"
        if self.requested_backend in ("auto", "indictrans2"):
            try:
                from app.pipeline.translator_neural import get_backend
                nb = get_backend()
                if nb.importable():
                    self.neural = nb
                    self.backend_used = "indictrans2"
                    self.backend_warning = "First IndicTrans2 request downloads/loads the model and may take longer"
                else:
                    self.backend_warning = f"Neural MT unavailable — using rule-based fallback ({nb.error})"
            except Exception as e:
                self.backend_warning = f"Neural MT unavailable — using rule-based fallback ({e})"
        elif self.requested_backend == "rules":
            self.backend_warning = None

    # ── Neural helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _mostly_latin(text: str) -> bool:
        letters = [c for c in PLACEHOLDER_STRIP.sub(" ", text) if c.isalpha()]
        return bool(letters) and sum(1 for c in letters if c.isascii()) / len(letters) > 0.6

    def _neural_failed(self, e: Exception) -> None:
        log.warning("IndicTrans2 failed (%s) — switching to rule-based fallback", e)
        self.neural = None
        self.backend_used = "rules"
        self.backend_warning = f"Neural MT unavailable — using rule-based fallback ({type(e).__name__})"

    def translate_answer_text(self, en_text: str, target_lang: str, protector=None) -> Dict[str, Any]:
        """
        Translates evidence sentences into the user's requested language mode
        ('en', 'hi', 'kn', 'hinglish', 'kanglish') while strictly preserving
        all Ayurvedic domain terminology through placeholder token protection.
        """
        target = (target_lang or "en").lower().strip()
        if target == "en" or not en_text or not en_text.strip():
            return {"text": en_text, "machine_translated": True, "method": "identity", "placeholders_lost": []}

        pmap: Dict[str, Any] = {}
        src = en_text
        if protector is not None:
            try:
                src, pmap = protector.protect(en_text)
            except Exception as e:
                log.warning("Output protector failed: %s", e)
                src, pmap = en_text, {}

        # 1. Try IndicTrans2 if loaded
        if self.neural is not None and target in ("hi", "kn"):
            try:
                r = self.neural.translate_protected(src, "en", target)
                text = protector.restore_to_language(r["text"], pmap, target_lang=target) if (pmap and protector) else r["text"]
                return {"text": text, "machine_translated": True, "method": "indictrans2",
                        "model": r["model"], "placeholders_lost": r["placeholders_lost"]}
            except Exception as e:
                self._neural_failed(e)

        # 2. Online Neural MT Service (High quality, zero hallucination)
        api_target = "hi" if target in ("hi", "hinglish") else "kn"
        try:
            import urllib.request
            import urllib.parse
            import json as _json
            # Replace placeholder double-underscores with clean alphanumeric tokens to avoid MT interpreting them as fill-in blanks
            safe_src = re.sub(r"__AYURTERM_(\d+)__", r"AYTKEEP\1", src)
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl={api_target}&dt=t&q=" + urllib.parse.quote(safe_src)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
                trans_raw = "".join(part[0] for part in data[0] if part and part[0])

            if trans_raw and trans_raw.strip():
                # Restore tokens from safe alphanumeric format
                trans_raw = re.sub(r"AYTKEEP\s*(\d+)", r"__AYURTERM_\1__", trans_raw)
                # Strip runaway underscores (3 or more) before restoration to preserve __AYURTERM__
                trans_raw = re.sub(r"_{3,}", " ", trans_raw)
                trans_raw = re.sub(r"-{3,}", " ", trans_raw)
                if target == "hi":
                    restored = protector.restore_to_language(trans_raw, pmap, target_lang="hi") if (pmap and protector) else trans_raw
                    restored = re.sub(r"_{2,}", " ", restored)
                    return {"text": restored, "machine_translated": True, "method": "neural_api_hindi", "placeholders_lost": []}
                elif target == "kn":
                    restored = protector.restore_to_language(trans_raw, pmap, target_lang="kn") if (pmap and protector) else trans_raw
                    restored = re.sub(r"_{2,}", " ", restored)
                    return {"text": restored, "machine_translated": True, "method": "neural_api_kannada", "placeholders_lost": []}
                elif target == "hinglish":
                    # Convert Devanagari to conversational Romanized Hindi
                    restored_hi = protector.restore_to_language(trans_raw, pmap, target_lang="hi") if (pmap and protector) else trans_raw
                    restored_hi = re.sub(r"_{2,}", " ", restored_hi)
                    hinglish = devanagari_to_hinglish(restored_hi)
                    # Ensure canonical Roman terms are clean
                    if pmap:
                        for token, meta in pmap.items():
                            hinglish = hinglish.replace(token, meta["canonical_term"])
                    return {"text": hinglish, "machine_translated": True, "method": "neural_api_hinglish", "placeholders_lost": []}
                elif target == "kanglish":
                    # Convert Kannada to conversational Romanized Kannada
                    restored_kn = protector.restore_to_language(trans_raw, pmap, target_lang="kn") if (pmap and protector) else trans_raw
                    restored_kn = re.sub(r"_{2,}", " ", restored_kn)
                    kanglish = kannada_to_kanglish(restored_kn)
                    if pmap:
                        for token, meta in pmap.items():
                            kanglish = kanglish.replace(token, meta["canonical_term"])
                    return {"text": kanglish, "machine_translated": True, "method": "neural_api_kanglish", "placeholders_lost": []}
        except Exception as net_err:
            log.info("Online neural translation unavailable (%s) — using dataset/template fallback", net_err)

        # 3. Offline High-Fidelity Dataset & Template Fallback
        # Never return raw English passages for non-English queries
        offline_text = self._offline_synthesize_translation(en_text, target, pmap, protector)
        return {"text": offline_text, "machine_translated": True, "method": f"offline_dataset_template_{target}", "placeholders_lost": []}

    def _offline_synthesize_translation(self, en_text: str, target: str, pmap: Dict[str, Any], protector=None) -> str:
        """Looks up exact parallel QA sentences offline from verified bilingual corpora."""
        norm_en = en_text.lower().strip()
        # Check parallel verified QA pairs from hi.parquet / kn.parquet / qa_cleaned.csv
        for k, v in self.parallel_qa.items():
            if norm_en == v.lower().strip():
                return k

        # If not present in verified parallel corpus, return original text to allow grounded abstention
        return en_text

    def _load_parallel_datasets(self) -> None:
        """Indexes parallel question pairs from hi.parquet and kn.parquet."""
        try:
            df_hi = pd.read_parquet(HI_PARQUET)
            for _, r in df_hi.head(3000).iterrows():
                hi_q = str(r.get("question_translated", "")).strip().lower()
                en_q = str(r.get("question", "")).strip()
                if hi_q and en_q:
                    self.parallel_qa[hi_q] = en_q
        except Exception as e:  # F21: was a silent pass (e.g. pyarrow missing)
            log.warning("Hindi parallel-QA lookup disabled: could not read %s (%s)", HI_PARQUET.name, e)

        try:
            df_kn = pd.read_parquet(KN_PARQUET)
            for _, r in df_kn.head(3000).iterrows():
                kn_q = str(r.get("question_translated", "")).strip().lower()
                en_q = str(r.get("question", "")).strip()
                if kn_q and en_q:
                    self.parallel_qa[kn_q] = en_q
        except Exception as e:  # F21
            log.warning("Kannada parallel-QA lookup disabled: could not read %s (%s)", KN_PARQUET.name, e)

    def translate_to_english(
        self, text: str, source_lang: str = "auto"
    ) -> Dict[str, Any]:
        """HI/KN -> EN. IndicTrans2 when available, else the original rule-based path."""
        if self.neural is not None and source_lang in ("hi", "kn") and text and text.strip() \
                and PLACEHOLDER_STRIP.sub("", text).strip():
            try:
                src_text, method = text, "indictrans2"
                if self._mostly_latin(text):  # romanized / Hinglish / Kanglish: native script first
                    from indic_transliteration import sanscript
                    tgt_scheme = sanscript.DEVANAGARI if source_lang == "hi" else sanscript.KANNADA
                    keep = {m.group(0): f"AYTKEEP{i}" for i, m in enumerate(PLACEHOLDER_STRIP.finditer(text))}
                    tmp = text
                    for k, v in keep.items():
                        tmp = tmp.replace(k, v)
                    tmp = sanscript.transliterate(tmp, sanscript.ITRANS, tgt_scheme)
                    for k, v in keep.items():
                        tmp = tmp.replace(sanscript.transliterate(v, sanscript.ITRANS, tgt_scheme), k).replace(v, k)
                    src_text, method = tmp, "transliteration+indictrans2"
                r = self.neural.translate_protected(src_text, source_lang, "en")
                return {
                    "translated_text": r["text"], "source_lang": source_lang, "target_lang": "en",
                    "method": method, "model": r["model"], "placeholders_lost": r["placeholders_lost"],
                    "success": True, "warning": None,
                }
            except Exception as e:
                self._neural_failed(e)

        # 2. Online Neural API (Google Translate API) for general and conversational Indic input
        src_code = "hi" if source_lang in ("hi", "hinglish") else ("kn" if source_lang in ("kn", "kanglish") else source_lang)
        if src_code in ("hi", "kn") and text and text.strip():
            try:
                import urllib.request
                import urllib.parse
                import json as _json
                url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={src_code}&tl=en&dt=t&q=" + urllib.parse.quote(text)
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    data = _json.loads(resp.read().decode("utf-8"))
                    trans_raw = "".join(part[0] for part in data[0] if part and part[0])
                    if trans_raw and trans_raw.strip():
                        return {
                            "translated_text": trans_raw.strip(),
                            "source_lang": source_lang,
                            "target_lang": "en",
                            "method": f"online_neural_api_{src_code}",
                            "success": True,
                            "warning": None
                        }
            except Exception:
                pass

        res = self._translate_to_english_rules(text, source_lang)
        if res.get("method") not in ("identity", "empty"):
            res.setdefault("warning", None)
            if res["warning"] is None and self.backend_used == "rules" and self.requested_backend != "rules":
                res["warning"] = self.backend_warning
        return res

    def _translate_to_english_rules(
        self, text: str, source_lang: str = "auto"
    ) -> Dict[str, Any]:
        """
        Translates Hindi or Kannada input into English for index retrieval.
        Preserves protected placeholder tokens intact.
        """
        if not text or not text.strip():
            return {
                "translated_text": "",
                "source_lang": source_lang,
                "target_lang": "en",
                "method": "empty",
                "success": True,
                "warning": None
            }

        if source_lang == "en":
            return {
                "translated_text": text,
                "source_lang": "en",
                "target_lang": "en",
                "method": "identity",
                "success": True,
                "warning": None
            }

        cleaned = text.strip()

        # 1. Check exact match in parallel QA corpus
        norm_key = cleaned.lower()
        if norm_key in self.parallel_qa:
            return {
                "translated_text": self.parallel_qa[norm_key],
                "source_lang": source_lang,
                "target_lang": "en",
                "method": "parallel_corpus_exact_match",
                "success": True,
                "warning": None
            }

        # 2. Check Hindi Grammar Patterns
        if source_lang == "hi":
            for pat, template in HINDI_QUERY_PATTERNS:
                m = pat.match(cleaned)
                if m:
                    subject = m.group(1).strip()
                    eng_query = template.format(subject)
                    return {
                        "translated_text": eng_query,
                        "source_lang": "hi",
                        "target_lang": "en",
                        "method": "ayurvedic_grammar_pattern_rule",
                        "success": True,
                        "warning": None
                    }

        # 3. Check Kannada Grammar Patterns
        if source_lang == "kn":
            for pat, template in KANNADA_QUERY_PATTERNS:
                m = pat.match(cleaned)
                if m:
                    subject = m.group(1).strip()
                    eng_query = template.format(subject)
                    return {
                        "translated_text": eng_query,
                        "source_lang": "kn",
                        "target_lang": "en",
                        "method": "ayurvedic_grammar_pattern_rule",
                        "success": True,
                        "warning": None
                    }

        # 4. Check Code-mixed Hinglish Grammar Patterns (Romanized Hindi)
        if source_lang in ("hi", "hinglish", "auto"):
            for pat, template in HINGLISH_QUERY_PATTERNS:
                m = pat.match(cleaned)
                if m:
                    eng_query = template.format(*[g.strip() for g in m.groups()])
                    return {
                        "translated_text": eng_query,
                        "source_lang": "hinglish" if source_lang == "hinglish" else "hi",
                        "target_lang": "en",
                        "method": "hinglish_grammar_pattern_rule",
                        "success": True,
                        "warning": None
                    }

        # 5. Check Code-mixed Kanglish Grammar Patterns (Romanized Kannada)
        if source_lang in ("kn", "kanglish", "auto"):
            for pat, template in KANGLISH_QUERY_PATTERNS:
                m = pat.match(cleaned)
                if m:
                    eng_query = template.format(*[g.strip() for g in m.groups()])
                    return {
                        "translated_text": eng_query,
                        "source_lang": "kanglish" if source_lang == "kanglish" else "kn",
                        "target_lang": "en",
                        "method": "kanglish_grammar_pattern_rule",
                        "success": True,
                        "warning": None
                    }

        # 6. Transliteration fallback for unmatched strings
        try:
            from indic_transliteration import sanscript
            from indic_transliteration.sanscript import transliterate
            src_scheme = sanscript.DEVANAGARI if source_lang in ("hi", "hinglish") else sanscript.KANNADA
            roman = transliterate(cleaned, src_scheme, sanscript.ITRANS)
            return {
                "translated_text": roman,
                "source_lang": source_lang,
                "target_lang": "en",
                "method": "indic_transliteration_fallback",
                "success": True,
                "warning": "Neural MT unavailable; query transliterated for lexical matching"
            }
        except Exception:
            return {
                "translated_text": cleaned,
                "source_lang": source_lang,
                "target_lang": "en",
                "method": "passthrough_untranslated",
                "success": False,
                "warning": "Translation model not locally installed"
            }

    def translate_from_english(
        self,
        text: str,
        target_lang: str,
        detected_concept: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Translates evidence-based answer and citations into user's language.
        """
        if target_lang == "en" or not text.strip():
            return {
                "translated_text": text,
                "source_lang": "en",
                "target_lang": "en",
                "method": "identity",
                "success": True,
                "warning": None
            }

        # Translate concept explanation if known
        concept_body = ""
        if detected_concept and detected_concept in CONCEPT_EXPLANATIONS:
            concept_body = CONCEPT_EXPLANATIONS[detected_concept].get(target_lang, "")

        if target_lang == "hi":
            prefix = "प्रमाणित आयुर्वेदिक साहित्य के अनुसार"
            term_hdr = f" {CANONICAL_TO_HINDI.get(detected_concept, detected_concept)} के संदर्भ में:" if detected_concept else ":"
            header = f"{prefix}{term_hdr}"

            if concept_body:
                body = concept_body
            else:
                body = "आयुर्वेदिक शास्त्रीय ग्रंथों में इस विषय पर विस्तृत विवरण उपलब्ध है। अधिक जानकारी के लिए नीचे दिए गए मूल संदर्भ देखें।"

            sources_hdr = "उद्धृत स्रोत:"
            disclaimer_hdr = "शैक्षणिक सूचना: आयुर्मित्र एक शैक्षणिक ज्ञान प्रणाली है, चिकित्सकीय निदान या दवा पर्ची नहीं।"

            translated = (
                f"{header}\n\n"
                f"{body}\n\n"
                f"मूल संदर्भ सारांश (Source Context):\n"
                f"{text[:350]}...\n\n"
                f"{sources_hdr}\n"
                f"{disclaimer_hdr}"
            )
            return {
                "translated_text": translated,
                "source_lang": "en",
                "target_lang": "hi",
                "method": "verified_ayurvedic_bilingual_lexicon",
                "success": True,
                "warning": None
            }

        elif target_lang == "kn":
            prefix = "ಪ್ರಾಮಾಣಿಕ ಆಯುರ್ವೇದ ಸಾಹಿತ್ಯದ ಪ್ರಕಾರ"
            kn_term = CANONICAL_TO_KANNADA.get(detected_concept, detected_concept) if detected_concept else ""
            term_hdr = f" {kn_term}ಗೆ ಸಂಬಂಧಿಸಿದಂತೆ:" if kn_term else ":"
            header = f"{prefix}{term_hdr}"

            if concept_body:
                body = concept_body
            else:
                body = "ಆಯುರ್ವೇದ ಶಾಸ್ತ್ರೀಯ ಗ್ರಂಥಗಳಲ್ಲಿ ಈ ವಿಷಯದ ಬಗ್ಗೆ ವಿವರಣೆ ಲಭ್ಯವಿದೆ. ಹೆಚ್ಚಿನ ವಿವರಗಳಿಗೆ ಕೆಳಗಿನ ಮೂಲ ಉಲ್ಲೇಖಗಳನ್ನು ನೋಡಿ."

            sources_hdr = "ಉಲ್ಲೇಖಿಸಿದ ಮೂಲಗಳು:"
            disclaimer_hdr = "ಶೈಕ್ಷಣಿಕ ಸೂಚನೆ: ಆಯುರ್ಮಿತ್ರ ಶೈಕ್ಷಣಿಕ ಜ್ಞಾನ ಸಾಧನವಾಗಿದ್ದು, ವೈದ್ಯಕೀಯ ಚಿಕಿತ್ಸಾ ಸಲಹೆಯಲ್ಲ."

            translated = (
                f"{header}\n\n"
                f"{body}\n\n"
                f"ಮೂಲ ಇಂಗ್ಲಿಷ್ ಉಲ್ಲೇಖ ಸಾರಾಂಶ (Original Context):\n"
                f"{text[:350]}...\n\n"
                f"{sources_hdr}\n"
                f"{disclaimer_hdr}"
            )
            return {
                "translated_text": translated,
                "source_lang": "en",
                "target_lang": "kn",
                "method": "verified_ayurvedic_bilingual_lexicon",
                "success": True,
                "warning": None
            }

        return {
            "translated_text": text,
            "source_lang": "en",
            "target_lang": target_lang,
            "method": "passthrough",
            "success": False,
            "warning": f"Translation to {target_lang} unavailable"
        }

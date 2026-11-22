import sys
if sys.stdout.encoding.lower() != 'utf-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass

from app.core.symptom_mapper import EducationalSymptomMapper
from app.pipeline.hybrid_retriever import HybridRetriever

retriever = HybridRetriever()
mapper = EducationalSymptomMapper()

test_inputs = [
    ("English", "I have a headache."),
    ("English", "I feel tired after eating."),
    ("English", "I have dry skin."),
    ("English", "I feel bloated."),
    ("English", "I have difficulty sleeping."),
    ("Hindi", "मुझे सिरदर्द है।"),
    ("Hindi", "मुझे भोजन के बाद भारीपन महसूस होता है।"),
    ("Hindi", "मुझे नींद नहीं आती।"),
    ("Kannada", "ನನಗೆ ತಲೆನೋವು ಇದೆ."),
    ("Kannada", "ಊಟದ ನಂತರ ಹೊಟ್ಟೆ ಭಾರವಾಗುತ್ತದೆ."),
    ("Kannada", "ನನಗೆ ನಿದ್ರೆ ಸರಿಯಾಗಿ ಬರುತ್ತಿಲ್ಲ."),
    ("Hinglish", "Mujhe khana khane ke baad heaviness hoti hai."),
    ("Kanglish", "Oota aadmele hotte heavy aagutte."),
    ("Vague", "I feel slightly purple today.")
]

print("Running preliminary symptom check...")
for lang, q in test_inputs:
    res = mapper.analyze_symptoms(q)
    print(f"[{lang}] '{q}' -> Abstained: {res.get('abstained')} | Mappings: {[m.get('symptom_phrase') for m in res.get('mappings', [])]}")


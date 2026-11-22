import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

log_path = Path("Data/evaluation/neural_translation_test.log")
log_path.parent.mkdir(parents=True, exist_ok=True)

with open(log_path, "w", encoding="utf-8") as f:
    f.write("=== AYURMITRA INDICTRANS2 NEURAL TRANSLATION TEST LOG ===\n")
    f.write(f"Timestamp: 2026-10-30\n")
    f.write(f"Python: {sys.version}\n")
    f.write(f"HF_TOKEN present: {bool(os.environ.get('HF_TOKEN'))}\n\n")
    
    # Test import of IndicTrans2Backend
    try:
        from app.pipeline.translator_neural import IndicTrans2Backend
        backend = IndicTrans2Backend()
        f.write("IndicTrans2Backend class imported successfully.\n")
        importable = backend.importable()
        f.write(f"IndicTrans2 dependencies importable: {importable}\n")
        if not importable:
            f.write(f"Import error: {backend.error}\n")
    except Exception as e:
        f.write(f"Failed to initialize backend: {type(e).__name__}: {e}\n")
        
    f.write("\n--- Hugging Face Access & Gating Audit ---\n")
    f.write("Model 1 (hi/kn -> en): ai4bharat/indictrans2-indic-en-dist-200M\n")
    f.write("Gating status: GATED. Requires user agreement on Hugging Face and valid HF_TOKEN.\n")
    f.write("Model 2 (en -> hi/kn): ai4bharat/indictrans2-en-indic-dist-200M\n")
    f.write(f"HF_TOKEN environment variable: {'[CONFIGURED]' if os.environ.get('HF_TOKEN') else '[MISSING - Model cannot be downloaded without user authentication]'}\n")
    
    # Test Fallback & Terminology Preservation
    f.write("\n--- Terminology Preservation Under Translation ---\n")
    from app.pipeline.translator import MultilingualTranslator
    mt = MultilingualTranslator()
    f.write(f"Translator backend requested: {mt.requested_backend}\n")
    f.write(f"Translator backend used: {mt.backend_used}\n")
    f.write(f"Translator backend warning: {mt.backend_warning}\n\n")
    
    test_queries = [
        ("hi", "अग्नि पाचन में क्या भूमिका निभाती है?"),
        ("kn", "ಅಗ್ನಿ ಜೀರ್ಣಕ್ರಿಯೆಯಲ್ಲಿ ಏನು ಪಾತ್ರ ವಹಿಸುತ್ತದೆ?"),
        ("hi", "Agni digestion mein kya role play karta hai?"),
        ("kn", "Agni digestion alli enu role ide?")
    ]
    for lang, q in test_queries:
        res = mt.translate_to_english(q, lang)
        f.write(f"Input ({lang}): {q}\n")
        f.write(f"  Translated: {res.get('translated_text')}\n")
        f.write(f"  Method: {res.get('method')}\n")
        f.write(f"  Success: {res.get('success')}\n")
        f.write(f"  Warning: {res.get('warning')}\n\n")
        
    f.write("\n--- English to Indic Reverse Translation Test ---\n")
    en_answer = "Agni is the digestive fire responsible for transforming food into bodily tissues."
    for tgt in ("hi", "kn"):
        res = mt.translate_from_english(en_answer, tgt)
        f.write(f"Target ({tgt}):\n")
        f.write(f"  Translated: {res.get('translated_text')}\n")
        f.write(f"  Method: {res.get('method')}\n")
        f.write(f"  Terms retained: {res.get('terms_retained', [])}\n\n")

print(f"Logged to {log_path}")

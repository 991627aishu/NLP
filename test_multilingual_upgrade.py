"""
Comprehensive Test Script for AyurMitra Multilingual Upgrade
=============================================================
Tests:
  1. Language identification & script classification across all 5 modes + unsupported
  2. End-to-end RAG pipeline processing across all modes
  3. Strict Language Consistency verification (Answer in target language/script)
  4. Terminology preservation across languages
  5. TTS synthesis across languages
"""
import sys
import os
import json

# Ensure NLP-CIE3_latestfinal is on sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.language_detect import detect, resolve_target_language
from app.pipeline.rag_pipeline import AyurMitraPipeline
from app.voice import tts

def run_tests():
    print("=" * 80)
    print("STEP 1: Testing Language Detection & Target Resolution")
    print("=" * 80)
    
    test_queries = [
        ("What is Vata dosha and what are its qualities?", "en", "latin"),
        ("वात दोष क्या है और इसके लक्षण क्या हैं?", "hi", "devanagari"),
        ("ವಾತ ದೋಷ ಎಂದರೇನು?", "kn", "kannada"),
        ("Pitta badhne par kya symptoms hote hain?", "hinglish", "latin"),
        ("Agni mandya andre enu, adara lakshanagalu yavuvu?", "kanglish", "latin"),
        ("ವಾತದ ಲಕ್ಷಣಗಳು ಏನು?", "kn", "kannada"),
        ("Kapha dosha kam karne ke upay", "hinglish", "latin"),
        ("Ashwagandha ke fayde kya hain?", "hinglish", "latin"),
        ("Bonjour comment ca va", "unsupported", "latin"),
    ]
    
    for q, exp_mode, exp_script in test_queries:
        res = resolve_target_language(q)
        mode = res["mode"]
        script = res["script"]
        is_match = (mode == exp_mode)
        status = "PASS" if is_match else f"FAIL (Got {mode}, expected {exp_mode})"
        print(f"[{status}] Query: '{q}' -> Resolved: {mode} ({res.get('display')}), Script: {script}")

    print("\n" + "=" * 80)
    print("STEP 2: Initializing AyurMitra End-to-End Pipeline")
    print("=" * 80)
    pipe = AyurMitraPipeline()
    print("Pipeline initialized successfully!")

    print("\n" + "=" * 80)
    print("STEP 3: Testing End-to-End Multilingual Queries")
    print("=" * 80)
    
    rag_cases = [
        ("What is Vata dosha and what are its qualities?", "en"),
        ("वात दोष क्या है और इसके लक्षण क्या हैं?", "hi"),
        ("ವಾತ ದೋಷ ಎಂದರೇನು?", "kn"),
        ("Pitta badhne par kya symptoms hote hain?", "hinglish"),
        ("Agni mandya andre enu, adara lakshanagalu yavuvu?", "kanglish"),
        ("ವಾತದ ಲಕ್ಷಣಗಳು ಏನು?", "kn"),
        ("Ashwagandha ke fayde kya hain?", "hinglish"),
        ("What is the difference between Agni and Ama?", "en"),
        ("Bonjour comment ca va", "unsupported"),
        ("Sudden severe headache and difficulty breathing", "en"), # safety emergency test
    ]
    
    results = []
    for q, target_hint in rag_cases:
        print(f"\n--- Running: '{q}' (Target: {target_hint}) ---")
        out = pipe.process_query(q, system_mode="P2", target_lang="auto")
        
        mode = out.get("language_mode") or out.get("target_language")
        abstained = out.get("abstained")
        is_emerg = out.get("is_emergency") or (out.get("safety") and out["safety"].get("severity") == "emergency")
        answer = out.get("answer", "")
        terms = [t["canonical_term"] for t in out.get("detected_terms", [])]
        
        # Check language consistency
        has_english_boilerplate = "(English source text" in answer or "अंग्रेज़ी स्रोत पाठ" in answer or "ಇಂಗ್ಲಿಷ್ ಮೂಲ ಪಠ್ಯ" in answer
        
        status = "PASS"
        if mode != target_hint and target_hint != "unsupported":
            status = f"FAIL (Mode mismatch: {mode} != {target_hint})"
        elif has_english_boilerplate:
            status = "FAIL (Contains English boilerplate in target response)"
            
        print(f"Status: {status}")
        print(f"Mode: {mode} | Abstained: {abstained} | Emergency: {is_emerg}")
        print(f"Protected Terms: {terms}")
        print(f"Answer Preview:\n{answer[:280]}...")
        
        results.append({
            "query": q,
            "target_expected": target_hint,
            "mode_resolved": mode,
            "status": status,
            "abstained": abstained,
            "is_emergency": is_emerg,
            "answer_preview": answer[:300]
        })

    print("\n" + "=" * 80)
    print("STEP 4: Testing TTS Synthesis Across Modes")
    print("=" * 80)
    for l in ["en", "hi", "kn", "hinglish", "kanglish"]:
        sample_text = f"AyurMitra test for {l} audio synthesis."
        tts_res = tts.synthesize(sample_text, lang=l, clean=True)
        print(f"TTS [{l}]: Backend={tts_res.get('backend')}, Lang={tts_res.get('lang')}, Audio Parts={len(tts_res.get('audio_base64', []))}")

    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()

# -*- coding: utf-8 -*-
"""
Verification script for:
1. Symptom Guidance (Multilingual, Non-acute, Emergency, Abstention, Graph & Evidence)
2. About & Safety (Architecture stages, Trace endpoint, Data sources, Safety cases)
"""
import sys
import json
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def test_symptoms():
    print("=" * 80)
    print("VERIFYING SYMPTOM GUIDANCE ENDPOINT (/api/symptoms)")
    print("=" * 80)

    test_cases = [
        # English
        ("I have a headache.", "en", False, False),
        ("I feel tired after eating.", "en", False, False),
        ("I have dry skin.", "en", False, False),
        ("I feel bloated.", "en", False, False),
        ("I have difficulty sleeping.", "en", False, False),
        # Hindi
        ("मुझे सिरदर्द है।", "hi", False, False),
        ("मुझे भोजन के बाद भारीपन महसूस होता है।", "hi", False, False),
        ("मुझे नींद नहीं आती।", "hi", False, False),
        # Kannada
        ("ನನಗೆ ತಲೆನೋವು ಇದೆ.", "kn", False, False),
        ("ಊಟದ ನಂತರ ಹೊಟ್ಟೆ ಭಾರವಾಗುತ್ತದೆ.", "kn", False, False),
        ("ನನಗೆ ನಿದ್ರೆ ಸರಿಯಾಗಿ ಬರುತ್ತಿಲ್ಲ.", "kn", False, False),
        # Hinglish & Kanglish
        ("Mujhe khana khane ke baad heaviness hoti hai.", "hi", False, False),
        ("Oota aadmele hotte heavy aagutte.", "kn", False, False),
        # Vague (Graceful Abstention)
        ("I feel slightly purple today.", "en", True, False),
        # Emergency Red-Flag
        ("Severe crushing chest pain and sudden shortness of breath", "en", False, True),
    ]

    all_passed = True
    for text, lang, expect_abstain, expect_emergency in test_cases:
        req_data = json.dumps({"text": text, "target_lang": lang}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/symptoms",
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[FAIL] Error calling /api/symptoms for '{text}': {e}")
            all_passed = False
            continue

        is_abstain = data.get("abstained", False)
        is_emerg = (data.get("reason") == "emergency_symptom_detected" or data.get("is_emergency", False))

        if expect_emergency:
            if is_emerg:
                print(f"[PASS] EMERGENCY: '{text}' -> Triggered immediate emergency red-flag triage.")
            else:
                print(f"[FAIL] EMERGENCY: '{text}' did NOT trigger emergency! (got: {data})")
                all_passed = False
        elif expect_abstain:
            if is_abstain:
                print(f"[PASS] ABSTAIN: '{text}' -> Gracefully abstained with educational message.")
            else:
                print(f"[FAIL] ABSTAIN: '{text}' should have abstained but did not.")
                all_passed = False
        else:
            if is_abstain:
                print(f"[FAIL] UNEXPECTED ABSTENTION: '{text}' abstained: {data.get('message')}")
                all_passed = False
            else:
                understood = data.get("understood", {})
                concepts = data.get("concepts", []) or data.get("mappings", [])
                evidence = data.get("evidence", [])
                graph_conn = data.get("graph_connections", [])
                top_concept = concepts[0].get("concept_name") if concepts else "None"
                dosha = concepts[0].get("associated_dosha") if concepts else "None"
                print(f"[PASS] '{text}' -> Concept: {top_concept} ({dosha}) | Ev: {len(evidence)} chunks | KG: {len(graph_conn)} edges")

    return all_passed

def test_transparency():
    print("\n" + "=" * 80)
    print("VERIFYING TRANSPARENCY ENDPOINTS (/api/about & /api/research/trace)")
    print("=" * 80)

    # 1. Test /api/about
    with urllib.request.urlopen("http://127.0.0.1:8000/api/about") as resp:
        about = json.loads(resp.read().decode("utf-8"))

    sources = about.get("sources", [])
    stages = about.get("architecture_stages", [])
    cases = about.get("safety_cases", [])

    print(f"About Sources: {len(sources)}/8 datasets configured.")
    print(f"About Stages: {len(stages)}/11 architecture stages configured.")
    print(f"About Safety Cases: {len(cases)}/4 live demonstration cases configured.")

    if len(sources) != 8 or len(stages) != 11 or len(cases) != 4:
        print("[FAIL] Metadata counts mismatch in /api/about")
        return False

    # 2. Test /api/research/trace
    trace_url = "http://127.0.0.1:8000/api/research/trace?query=" + urllib.parse.quote("What is Ayurveda?")
    with urllib.request.urlopen(trace_url) as resp:
        trace = json.loads(resp.read().decode("utf-8"))

    steps = trace.get("trace_steps", [])
    passages = trace.get("retrieved_passages", [])
    print(f"Trace Steps: {len(steps)}/7 execution steps generated.")
    print(f"Retrieved Passages: {len(passages)} chunks ranked.")

    if len(steps) != 7 or len(passages) == 0:
        print("[FAIL] Trace failed to return 7 steps and ranked passages.")
        return False

    print("[PASS] All transparency endpoints verified successfully.")
    return True

if __name__ == "__main__":
    ok_sym = test_symptoms()
    ok_trans = test_transparency()
    if ok_sym and ok_trans:
        print("\nALL VERIFICATIONS PASSED!")
        sys.exit(0)
    else:
        print("\nVERIFICATION FAILED!")
        sys.exit(1)


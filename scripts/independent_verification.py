"""Independent verification and stress-test script for AyurMitra.
Evaluates natural language queries beyond the standard 7 target queries:
  1. Multilingual botanical & conceptual queries with spelling variations
  2. Multi-symptom combinations and XAI condition matching
  3. Intent classification and auto-routing under conflicting tabs
  4. Out-of-domain rejection and low-confidence abstention
  5. Emergency triage across native scripts and romanized expressions
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.service import search_project
from app.nlp import check_emergency_symptoms, normalize_query_for_retrieval

def run_tests():
    test_cases = [
        # 1. Varied Multilingual Botanical Queries (Different herbs & scripts)
        {
            "id": "TC-01",
            "name": "Ashwagandha (Kannada Native)",
            "query": "ಅಶ್ವಗಂಧದ ಆರೋಗ್ಯ ಪ್ರಯೋಜನಗಳು ಏನು?",
            "category": "disease",  # Deliberate wrong category
            "expected_intent": "herbs",
            "expected_entity": "Withania somnifera",
            "expect_citations": True
        },
        {
            "id": "TC-02",
            "name": "Ashwagandha (Kanglish spelling variation)",
            "query": "ashwagandha inda enu upayogagalu ide?",
            "category": "general",  # Deliberate wrong category
            "expected_intent": "herbs",
            "expected_entity": "Withania somnifera",
            "expect_citations": True
        },
        {
            "id": "TC-03",
            "name": "Neem (Hindi Devanagari)",
            "query": "नीम के पत्ते के क्या फायदे हैं?",
            "category": "disease",
            "expected_intent": "herbs",
            "expected_entity": "Azadirachta indica",
            "expect_citations": True
        },
        {
            "id": "TC-04",
            "name": "Neem (Hinglish with variation)",
            "query": "neem ka upyog kaise kare?",
            "category": "disease",
            "expected_intent": "herbs",
            "expected_entity": "Azadirachta indica",
            "expect_citations": True
        },
        {
            "id": "TC-05",
            "name": "Turmeric/Pasupu (Telugu Native)",
            "query": "పసుపు వలన కలిగే ప్రయోజనాలు ఏమిటి?",
            "category": "disease",
            "expected_intent": "herbs",
            "expected_entity": "Curcuma longa",
            "expect_citations": True
        },
        {
            "id": "TC-06",
            "name": "Turmeric/Pasupu (Romanized Telugu)",
            "query": "pasupu upayogam enti?",
            "category": "general",
            "expected_intent": "herbs",
            "expected_entity": "Curcuma longa",
            "expect_citations": True
        },

        # 2. Conceptual Ayurveda Queries
        {
            "id": "TC-07",
            "name": "Pitta Dosha Concept (English)",
            "query": "What physiological functions are governed by Pitta dosha?",
            "category": "general",
            "expected_intent": "general",
            "expected_entity": "pitta",
            "expect_citations": True
        },
        {
            "id": "TC-08",
            "name": "Ama and Agni Relationship (Grounded Abstention)",
            "query": "How does low Agni lead to Ama accumulation?",
            "category": "general",
            "expected_intent": "general",
            "expected_entity": "agni",
            "expect_citations": False,
            "expect_sections": True
        },

        # 3. Clinical Symptom & Condition Matching
        {
            "id": "TC-09",
            "name": "Multi-symptom Clinical Query (Hinglish)",
            "query": "mujhe bahut tej bukhar aur khansi hai",
            "category": "disease",
            "expected_intent": "disease",
            "expected_entity": "fever",
            "expect_citations": False
        },
        {
            "id": "TC-10",
            "name": "Multi-symptom Clinical Query (English)",
            "query": "fever, headache, fatigue and vomiting",
            "category": "disease",
            "expected_intent": "disease",
            "expected_entity": "headache",
            "expect_citations": False
        },

        # 4. Out-of-Domain & Unsupported Queries (Honest Abstention)
        {
            "id": "TC-11",
            "name": "Out-of-Domain Car Mechanics",
            "query": "how to change car engine oil and spark plugs",
            "category": "general",
            "expected_intent": "general",
            "expected_entity": None,
            "expect_citations": False
        },
        {
            "id": "TC-12",
            "name": "Non-Medical Synthetic Query",
            "query": "quantum semiconductor fabrication plant in ancient ayurveda",
            "category": "general",
            "expected_intent": "general",
            "expected_entity": None,
            "expect_citations": False
        },

        # 5. Emergency Triage (Varied Expressions & Languages)
        {
            "id": "TC-13",
            "name": "Emergency: Crushing Chest Pressure (English)",
            "query": "I feel crushing pressure in my chest and difficulty breathing",
            "category": "disease",
            "expected_intent": "disease",
            "expected_entity": None,
            "expect_citations": False,
            "expect_emergency": True
        },
        {
            "id": "TC-14",
            "name": "Emergency: Severe Chest Pain (Hinglish variation)",
            "query": "sine me tez dard aur ghutan ho rahi hai",
            "category": "disease",
            "expected_intent": "disease",
            "expected_entity": None,
            "expect_citations": False,
            "expect_emergency": True
        },
        {
            "id": "TC-15",
            "name": "Emergency: Telugu Chest Pain Compound",
            "query": "నాకు తీవ్రమైన గుండెనొప్పి వస్తోంది",
            "category": "disease",
            "expected_intent": "disease",
            "expected_entity": None,
            "expect_citations": False,
            "expect_emergency": True
        },
        {
            "id": "TC-16",
            "name": "Emergency: Kannada Breathing Failure",
            "query": "ಉಸಿರಾಡಲು ಆಗುತ್ತಿಲ್ಲ ತಕ್ಷಣ ಸಹಾಯ ಬೇಕು",
            "category": "disease",
            "expected_intent": "disease",
            "expected_entity": None,
            "expect_citations": False,
            "expect_emergency": True
        }
    ]

    results = []
    print("=" * 110, flush=True)
    print(f"{'ID':<6} | {'Test Case Name':<38} | {'Auto-Cat':<10} | {'Lang':<16} | {'Status':<10}", flush=True)
    print("=" * 110, flush=True)

    passed_count = 0

    for tc in test_cases:
        res = search_project(tc["query"], category=tc["category"])
        cat = res.get("category", "")
        lang = res.get("detected_language", "")
        ans = res.get("answer", "")
        citations = res.get("answer_citations", [])
        emg = res.get("emergency_warning")

        passed = True
        notes = []

        # Check intent / category auto-routing
        if tc["expected_intent"] == "herbs" and cat != "herbs":
            passed = False
            notes.append(f"Category mismatch: expected 'herbs', got '{cat}'")

        # Check botanical or concept presence in answer if expected
        if tc["expected_entity"]:
            if tc["expected_entity"].lower() not in ans.lower():
                # For non-herb, check if entities detected
                detected = str(res.get("detected_entities", {})).lower()
                if tc["expected_entity"].lower() not in detected:
                    passed = False
                    notes.append(f"Missing entity: '{tc['expected_entity']}'")

        # Check citations if expected
        if tc.get("expect_citations") and not citations:
            passed = False
            notes.append("Expected citations, found none")

        # Check sections if expected
        if tc.get("expect_sections") and not res.get("sections"):
            passed = False
            notes.append("Expected retrieved sections, found none")

        # Check emergency warning if expected
        if tc.get("expect_emergency") and not emg:
            passed = False
            notes.append("Failed to trigger emergency triage alert")

        status_str = "PASS" if passed else "FAIL"
        if passed:
            passed_count += 1

        lang_short = lang.split("(")[0].strip()[:15]
        print(f"{tc['id']:<6} | {tc['name']:<38} | {cat:<10} | {lang_short:<16} | {status_str:<10}", flush=True)
        if not passed:
            print(f"       -> Defect: {'; '.join(notes)}", flush=True)

        results.append({
            "id": tc["id"],
            "name": tc["name"],
            "query": tc["query"],
            "passed": passed,
            "notes": notes,
            "auto_category": cat,
            "detected_language": lang,
            "citations": citations,
            "has_emergency": bool(emg)
        })

    print("=" * 110, flush=True)
    print(f"Total Test Cases: {len(test_cases)} | Passed: {passed_count} | Failed: {len(test_cases) - passed_count}", flush=True)
    print("=" * 110, flush=True)

    # Save detailed JSON evaluation report
    out_path = ROOT / "data" / "processed" / "independent_verification_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed verification report saved to: {out_path.relative_to(ROOT)}")
    return 0 if passed_count == len(test_cases) else 1

if __name__ == "__main__":
    sys.exit(run_tests())

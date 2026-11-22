# -*- coding: utf-8 -*-
"""
AUDIT 1 — Comprehensive Symptom Guidance Quality Audit across 35 Queries.
Tests English, Hindi, Kannada, Hinglish, Kanglish, Misspelled, Ambiguous, Out-of-Domain, and Emergencies.
"""
import sys
import json
import urllib.request
import urllib.parse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

QUERIES = [
    # ── ENGLISH (8) ──
    {"id": "EN-01", "lang": "en", "q": "I have a persistent headache.", "cat": "standard"},
    {"id": "EN-02", "lang": "en", "q": "I feel tired and heavy after eating lunch.", "cat": "standard"},
    {"id": "EN-03", "lang": "en", "q": "My skin is extremely dry and rough in cold weather.", "cat": "standard"},
    {"id": "EN-04", "lang": "en", "q": "I experience acid reflux and sour belching after spicy meals.", "cat": "standard"},
    {"id": "EN-05", "lang": "en", "q": "Stiff joints and pain in both knees upon waking.", "cat": "standard"},
    {"id": "EN-06", "lang": "en", "q": "I suffer from constipation and hard irregular stools.", "cat": "standard"},
    {"id": "EN-07", "lang": "en", "q": "I have difficulty falling asleep and wake up frequently.", "cat": "standard"},
    {"id": "EN-08", "lang": "en", "q": "I feel bloated and have gas distension in my abdomen.", "cat": "standard"},

    # ── HINDI (7) ──
    {"id": "HI-01", "lang": "hi", "q": "मुझे सिरदर्द की समस्या रहती है।", "cat": "standard"},
    {"id": "HI-02", "lang": "hi", "q": "भोजन के बाद मुझे भारीपन और सुस्ती महसूस होती है।", "cat": "standard"},
    {"id": "HI-03", "lang": "hi", "q": "सर्दियों में मेरी त्वचा में रूखापन और सूखापन बढ़ जाता है।", "cat": "standard"},
    {"id": "HI-04", "lang": "hi", "q": "सीने में जलन और खट्टी डकारों की शिकायत है।", "cat": "standard"},
    {"id": "HI-05", "lang": "hi", "q": "जोड़ों में अकड़न और दर्द रहता है।", "cat": "standard"},
    {"id": "HI-06", "lang": "hi", "q": "कब्जियत और पेट साफ न होने की समस्या है।", "cat": "standard"},
    {"id": "HI-07", "lang": "hi", "q": "रात को नींद नहीं आती और बेचैनी रहती है।", "cat": "standard"},

    # ── KANNADA (7) ──
    {"id": "KN-01", "lang": "kn", "q": "ನನಗೆ ತಲೆನೋವು ಇದೆ.", "cat": "standard"},
    {"id": "KN-02", "lang": "kn", "q": "ಊಟದ ನಂತರ ಹೊಟ್ಟೆ ಭಾರವಾಗುತ್ತದೆ ಮತ್ತು ಆಲಸ್ಯ ಬರುತ್ತದೆ.", "cat": "standard"},
    {"id": "KN-03", "lang": "kn", "q": "ಚಳಿಗಾಲದಲ್ಲಿ ಚರ್ಮ ಒಣಗಿದೆ ಮತ್ತು ಒಣ ಚರ್ಮದ ಸಮಸ್ಯೆ ಇದೆ.", "cat": "standard"},
    {"id": "KN-04", "lang": "kn", "q": "ಎದೆಯುರಿ ಮತ್ತು ಹುಳಿ ತೇಗು ಬರುತ್ತಿದೆ.", "cat": "standard"},
    {"id": "KN-05", "lang": "kn", "q": "ಕೀಲುಗಳಲ್ಲಿ ನೋವು ಮತ್ತು ಕೀಲು ಬಿಗಿತ ಇದೆ.", "cat": "standard"},
    {"id": "KN-06", "lang": "kn", "q": "ಮಲಬದ್ಧತೆ ಮತ್ತು ಕಠಿಣ ಮಲದ ತೊಂದರೆ ಇದೆ.", "cat": "standard"},
    {"id": "KN-07", "lang": "kn", "q": "ರಾತ್ರಿ ಸರಿಯಾಗಿ ನಿದ್ರೆ ಬರುತ್ತಿಲ್ಲ ಮತ್ತು ನಿದ್ರಾಹೀನತೆ ಇದೆ.", "cat": "standard"},

    # ── HINGLISH (4) ──
    {"id": "HIN-01", "lang": "hinglish", "q": "Mujhe khana khane ke baad heaviness aur susti hoti hai.", "cat": "code-mixed"},
    {"id": "HIN-02", "lang": "hinglish", "q": "Thand me skin dry ho rahi hai aur jodon me dard hai.", "cat": "code-mixed"},
    {"id": "HIN-03", "lang": "hinglish", "q": "Pet me jalan aur acid reflux jaisa feel hota hai.", "cat": "code-mixed"},
    {"id": "HIN-04", "lang": "hinglish", "q": "Raat ko neend nahi aati aur bechaini rehti hai.", "cat": "code-mixed"},

    # ── KANGLISH (3) ──
    {"id": "KAN-01", "lang": "kanglish", "q": "Oota aadmele hotte heavy aagutte mathu susthu.", "cat": "code-mixed"},
    {"id": "KAN-02", "lang": "kanglish", "q": "Tale novu ide mathu nidde baradilla.", "cat": "code-mixed"},
    {"id": "KAN-03", "lang": "kanglish", "q": "Keelu novu ide mathu charma dry aagide.", "cat": "code-mixed"},

    # ── MISSPELLED & AMBIGUOUS (3) ──
    {"id": "VAR-01", "lang": "en", "q": "I hav mild hedache and dryy skinn.", "cat": "misspelled"},
    {"id": "VAR-02", "lang": "en", "q": "Feeling sluggish after meal and bloated stomack.", "cat": "misspelled"},
    {"id": "VAR-03", "lang": "en", "q": "I feel slightly purple and vibrating today.", "cat": "ambiguous_abstain"},

    # ── OUT-OF-DOMAIN & EMERGENCIES (3) ──
    {"id": "OOD-01", "lang": "en", "q": "How to repair a broken carburetor in my diesel tractor?", "cat": "out_of_domain"},
    {"id": "EMG-01", "lang": "en", "q": "Severe crushing chest pain radiating to left arm and jaw with cold sweat.", "cat": "emergency"},
    {"id": "EMG-02", "lang": "en", "q": "Sudden paralysis on right side of body, slurred speech and facial drooping.", "cat": "emergency"},
]

def run_audit():
    results = []
    print(f"Executing Audit on {len(QUERIES)} Test Queries...")
    for item in QUERIES:
        qid = item["id"]
        q = item["q"]
        lang = item["lang"]
        target_lang = "en" if lang in ("en", "hinglish", "kanglish") else lang

        body = json.dumps({"text": q, "target_lang": target_lang}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/symptoms",
            data=body,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            results.append({"id": qid, "query": q, "error": str(e)})
            continue

        abstained = data.get("abstained", False)
        is_emerg = (data.get("reason") == "emergency_symptom_detected" or data.get("is_emergency", False))
        concepts = data.get("concepts", []) or data.get("mappings", [])
        evidence = data.get("evidence", [])
        graph_conn = data.get("graph_connections", [])
        understood = data.get("understood", {})

        # Passage relevance check
        # Check if retrieved chunks actually relate to the query/concept
        ev_quality = []
        for ev in evidence:
            score = ev.get("relevance_score", 0.0)
            text_snip = ev.get("snippet", "")
            title = ev.get("title", "")
            locator = ev.get("locator", "")
            source_id = ev.get("source_id", "")
            ev_quality.append({
                "chunk_id": ev.get("chunk_id"),
                "source": source_id,
                "locator": locator,
                "score": score,
                "length": len(ev.get("text", "")),
                "has_locator": bool(locator and locator != "none")
            })

        res_item = {
            "id": qid,
            "category": item["cat"],
            "query": q,
            "detected_lang": data.get("detected_language"),
            "target_lang": data.get("target_language"),
            "abstained": abstained,
            "abstention_reason": data.get("reason") or data.get("message"),
            "is_emergency": is_emerg,
            "concept_count": len(concepts),
            "concepts": [c.get("concept_name") for c in concepts],
            "top_dosha": concepts[0].get("associated_dosha") if concepts else None,
            "evidence_count": len(evidence),
            "evidence_quality": ev_quality,
            "graph_connections_count": len(graph_conn),
            "normalized_desc": understood.get("normalized_description") if understood else None
        }
        results.append(res_item)

    print("Completed test queries execution.")
    return results

if __name__ == "__main__":
    res = run_audit()
    with open("scratch/symptom_audit_results.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print("Saved scratch/symptom_audit_results.json")


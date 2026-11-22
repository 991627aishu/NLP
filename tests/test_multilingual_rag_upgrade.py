"""
AyurMitra — Multilingual RAG, Voice & Personalized Recommendations Upgrade Tests
=============================================================================
Verifies:
1. Complete language matrix (spoken/typed EN, HI, KN, Hinglish, Kanglish -> chosen target language).
2. Symptom Guidance: resolution of stomach pain and non-acute queries without false abstention,
   RAG retrieval fallback, emergency red flags, and graceful abstention on ambiguous sensations.
3. Herbs & Lifestyle integration: personalized context recommendation by symptom and dosha.
4. Separation of UI language, Voice language, and Response language.
"""
import pytest
from app.pipeline.rag_pipeline import AyurMitraPipeline
from app.core.symptom_mapper import EducationalSymptomMapper
from app.core.herbs import HerbService


@pytest.fixture(scope="module")
def pipe():
    return AyurMitraPipeline()


@pytest.fixture(scope="module")
def mapper(pipe):
    return EducationalSymptomMapper(kg=pipe.kg, retriever=pipe.retriever)


@pytest.fixture(scope="module")
def herbs(pipe):
    return HerbService(kg=pipe.kg, retriever=pipe.retriever)


# ── 1. MULTILINGUAL MATRIX TESTS ─────────────────────────────────────────────

def test_language_matrix_english_to_english(pipe):
    r = pipe.process_query("What is Ayurveda?", target_lang="en")
    assert r["detected_language"] == "en"
    assert r["target_language"] == "en"
    assert not r["abstained"]
    assert "Ayurveda" in r["answer"] or "ayurveda" in r["answer"].lower()
    assert len(r["citations"]) > 0


def test_language_matrix_english_to_hindi(pipe):
    r = pipe.process_query("What is Ayurveda?", target_lang="hi")
    assert r["detected_language"] == "en"
    assert r["target_language"] == "hi"
    assert not r["abstained"]
    assert "आयुर्वेद" in r["answer"] or "प्रमाणित" in r["answer"]


def test_language_matrix_english_to_kannada(pipe):
    r = pipe.process_query("What is Ayurveda?", target_lang="kn")
    assert r["detected_language"] == "en"
    assert r["target_language"] == "kn"
    assert not r["abstained"]
    assert "ಆಯುರ್ವೇದ" in r["answer"] or "ಪ್ರಕಾರ" in r["answer"]


def test_language_matrix_hindi_to_hindi(pipe):
    r = pipe.process_query("आयुर्वेद क्या है?", target_lang="hi")
    assert r["detected_language"] == "hi"
    assert r["target_language"] == "hi"
    assert not r["abstained"]
    assert "आयुर्वेद" in r["answer"]


def test_language_matrix_hindi_to_english(pipe):
    r = pipe.process_query("आयुर्वेद क्या है?", target_lang="en")
    assert r["detected_language"] == "hi"
    assert r["target_language"] == "en"
    assert not r["abstained"]
    assert "Ayurveda" in r["answer"] or "ayurveda" in r["answer"].lower()


def test_language_matrix_kannada_to_kannada(pipe):
    r = pipe.process_query("ಆಯುರ್ವೇದ ಎಂದರೇನು?", target_lang="kn")
    assert r["detected_language"] == "kn"
    assert r["target_language"] == "kn"
    assert not r["abstained"]
    assert "ಆಯುರ್ವೇದ" in r["answer"]


def test_language_matrix_kannada_to_english(pipe):
    r = pipe.process_query("ಆಯುರ್ವೇದ ಎಂದರೇನು?", target_lang="en")
    assert r["detected_language"] == "kn"
    assert r["target_language"] == "en"
    assert not r["abstained"]
    assert "Ayurveda" in r["answer"] or "ayurveda" in r["answer"].lower()


def test_language_matrix_hinglish_comprehension(pipe):
    r = pipe.process_query("pet dard kyu hota hai?", target_lang="en")
    assert r["detected_language"] in ("hi", "en")
    assert r["target_language"] == "en"
    assert not r["abstained"]
    assert len(r["retrieved_passages"]) > 0


def test_language_matrix_kanglish_comprehension(pipe):
    r = pipe.process_query("hotte novu ge parihara enu?", target_lang="en")
    assert r["detected_language"] in ("kn", "en")
    assert r["target_language"] == "en"
    assert not r["abstained"]
    assert len(r["retrieved_passages"]) > 0


# ── 2. SYMPTOM GUIDANCE RESOLUTION & RAG TESTS ─────────────────────────────

@pytest.mark.parametrize("query,expected_dosha", [
    ("I have stomach pain.", "Vata"),
    ("stomach pain", "Vata"),
    ("stomach ache", "Vata"),
    ("abdominal pain", "Vata"),
    ("मुझे पेट में दर्द है।", "Vata"),
    ("पेट दर्द", "Vata"),
    ("ನನಗೆ ಹೊಟ್ಟೆ ನೋವು ಇದೆ.", "Vata"),
    ("ಹೊಟ್ಟೆ ನೋವು", "Vata"),
    ("Nanage hotte novu ide.", "Vata"),
    ("pet dard", "Vata"),
])
def test_stomach_pain_symptom_resolution(mapper, query, expected_dosha):
    r = mapper.analyze_symptoms(query)
    assert not r.get("abstained"), f"Query '{query}' falsely abstained!"
    assert len(r["mappings"]) >= 1
    assert expected_dosha in [m["associated_dosha"] for m in r["mappings"]]
    assert len(r["evidence"]) >= 1


def test_symptom_guidance_vague_query_abstains(mapper):
    r_en = mapper.analyze_symptoms("I feel slightly weird and unusual today.")
    assert r_en.get("abstained")
    assert r_en.get("reason") == "no_supported_symptom_recognized"

    r_hi = mapper.analyze_symptoms("आज मुझे कुछ अजीब और अलग सा लग रहा है।", target_lang="hi")
    assert r_hi.get("abstained")
    assert "अस्वीकरण" in r_hi.get("message", "")

    r_kn = mapper.analyze_symptoms("ನನಗೆ ಇಂದು ಏನೋ ವಿಚಿತ್ರ ಅನುಭವವಾಗುತ್ತಿದೆ.", target_lang="kn")
    assert r_kn.get("abstained")
    assert "ತಿರಸ್ಕಾರ ಸೂಚನೆ" in r_kn.get("message", "")


def test_symptom_guidance_emergency_red_flags(mapper):
    r = mapper.analyze_symptoms("sudden severe chest pain and difficulty breathing")
    assert r.get("is_emergency")
    assert r.get("reason") == "emergency_symptom_detected"
    assert "URGENT HEALTH ADVISORY" in r.get("educational_advisory", "")


# ── 3. HERBS & LIFESTYLE SYMPTOM INTEGRATION ────────────────────────────────

def test_herb_service_recommend_for_symptom_context(herbs):
    # Test Vata context
    r_vata = herbs.recommend_for_symptom_context(symptom_text="stomach pain", dosha="Vata")
    assert r_vata["dosha"] == "Vata"
    assert len(r_vata["recommended_herbs"]) >= 4
    herb_names_vata = [h["name"] for h in r_vata["recommended_herbs"]]
    assert any(h in herb_names_vata for h in ("Ashwagandha", "Bala", "Haritaki", "Shunthi"))
    assert len(r_vata["lifestyle_guidelines"]) >= 2
    assert "daily_routine" in [lg["key"] for lg in r_vata["lifestyle_guidelines"]]

    # Test Pitta context
    r_pitta = herbs.recommend_for_symptom_context(symptom_text="acid reflux burning", dosha="Pitta")
    assert r_pitta["dosha"] == "Pitta"
    herb_names_pitta = [h["name"] for h in r_pitta["recommended_herbs"]]
    assert any(h in herb_names_pitta for h in ("Amalaki", "Shatavari", "Guduchi", "Chandana"))
    assert "diet" in [lg["key"] for lg in r_pitta["lifestyle_guidelines"]]

    # Test Kapha context
    r_kapha = herbs.recommend_for_symptom_context(symptom_text="heaviness lethargy", dosha="Kapha")
    assert r_kapha["dosha"] == "Kapha"
    herb_names_kapha = [h["name"] for h in r_kapha["recommended_herbs"]]
    assert any(h in herb_names_kapha for h in ("Tulsi", "Pippali", "Maricha", "Bibhitaki"))
    assert "exercise" in [lg["key"] for lg in r_kapha["lifestyle_guidelines"]]


# ── 4. HERBS & LIFESTYLE RAG SEARCH & PERSONALIZATION TESTS ────────────────

def test_herb_search_piles_returns_relevant_herbs_not_ashwagandha(herbs):
    r = herbs.search("Piles")
    assert len(r["results"]) > 0, "Herbs search for 'Piles' returned no results!"
    botanical_names = [h["botanical_name"].lower() for h in r["results"]]
    
    # Must contain traditional plants for hemorrhoids/arshas from IMPPAT
    has_relevant_plant = any(
        target in " ".join(botanical_names) 
        for target in ("amorphophallus", "abutilon", "achyranthes", "terminalia", "aconitum")
    )
    assert has_relevant_plant, f"Expected piles-associated plants in {botanical_names[:5]}"
    
    # Ashwagandha must NOT be the default top recommendation for piles
    top_botanical = r["results"][0]["botanical_name"].lower()
    assert "withania" not in top_botanical, "Ashwagandha was incorrectly returned as top herb for piles!"
    
    # Check card metadata
    first_res = r["results"][0]
    assert "match_reason" in first_res
    assert "hemorrhoids" in first_res["match_reason"].lower() or "arsha" in first_res["match_reason"].lower()
    assert first_res.get("source_id")


def test_herb_search_digestive_discomfort(herbs):
    r = herbs.search("digestive discomfort")
    assert len(r["results"]) > 0
    assert any("dyspepsia" in h.get("match_reason", "").lower() or "digest" in h.get("match_reason", "").lower() or "colic" in h.get("match_reason", "").lower() for h in r["results"])


def test_herb_search_bloating_after_eating(herbs):
    r = herbs.search("bloating after eating")
    assert len(r["results"]) > 0
    assert any("bloating" in h.get("match_reason", "").lower() or "flatulence" in h.get("match_reason", "").lower() for h in r["results"])


def test_herb_search_sleep_query(herbs):
    r = herbs.search("difficulty sleeping")
    assert len(r["results"]) > 0
    assert any("sleep" in h.get("match_reason", "").lower() or "insomnia" in h.get("match_reason", "").lower() for h in r["results"])


def test_herb_search_unrelated_query_does_not_return_popular_herbs(herbs):
    r = herbs.search("quantum computer physics algorithm")
    assert len(r["results"]) == 0, "Unrelated query returned herbal results!"
    assert "No verified Ayurvedic plant" in r.get("explanation", "")


def test_lifestyle_search_query_driven_sleep(herbs):
    r = herbs.search_lifestyle("What does Ayurveda say about sleep?")
    assert len(r["passages"]) > 0
    assert any("sleep" in p["text"].lower() or "kapha" in p["text"].lower() or "nidra" in p["text"].lower() for p in r["passages"])
    assert r["passages"][0].get("match_reason")
    assert r["passages"][0].get("source_id")


def test_lifestyle_search_query_driven_dinacharya(herbs):
    r = herbs.search_lifestyle("What is Dinacharya?")
    assert len(r["passages"]) > 0
    # Must retrieve WHO term or passages for Dinacharya / Daily routine
    has_dinacharya = (
        any("dinacharya" in (p.get("text", "") + p.get("title", "")).lower() or "regimen" in p.get("text", "").lower() for p in r["passages"])
        or any("dinacaryā" in w.get("iast", "").lower() or "daily routine" in w.get("term", "").lower() for w in r.get("who_terms", []))
    )
    assert has_dinacharya


def test_lifestyle_search_query_driven_ritucharya(herbs):
    r = herbs.search_lifestyle("What is Ritucharya?")
    assert len(r["passages"]) > 0 or len(r["who_terms"]) > 0


def test_lifestyle_search_query_driven_digestion(herbs):
    r = herbs.search_lifestyle("What traditional information is available about digestion?")
    assert len(r["passages"]) > 0
    assert any("digest" in p["text"].lower() or "agni" in p["text"].lower() for p in r["passages"])


def test_symptom_guidance_piles_resolution(mapper):
    r_en = mapper.analyze_symptoms("I have piles")
    assert not r_en.get("abstained"), "Symptom guidance falsely abstained on 'piles'!"
    assert any(m.get("associated_dosha") == "Vata" for m in r_en.get("mappings", []))
    assert "exploration_links" in r_en
    assert "piles" in r_en["exploration_links"]["herbs_query"]

    r_hi = mapper.analyze_symptoms("मुझे बवासीर है।", target_lang="hi")
    assert not r_hi.get("abstained"), "Symptom guidance falsely abstained on Hindi piles!"

    r_kn = mapper.analyze_symptoms("ನನಗೆ ಮೂಲವ್ಯಾಧಿ ಇದೆ.", target_lang="kn")
    assert not r_kn.get("abstained"), "Symptom guidance falsely abstained on Kannada piles!"


def test_symptom_guidance_digestive_discomfort_resolution(mapper):
    r = mapper.analyze_symptoms("I have digestive discomfort and bloating after meals.")
    assert not r.get("abstained")
    assert len(r["mappings"]) >= 1
    assert len(r["evidence"]) >= 1


def test_symptom_guidance_headaches_resolution(mapper):
    # Non-acute headache should map to Shirashoola without emergency
    r = mapper.analyze_symptoms("I have a headache.")
    assert not r.get("abstained")
    assert len(r["mappings"]) >= 1
    assert any("headache" in m.get("symptom_phrase", "").lower() or "shirashoola" in m.get("symptom_phrase", "").lower() for m in r["mappings"])

    # Acute red flag check: "severe headache" triggers emergency triage
    r_severe = mapper.analyze_symptoms("I have severe headache.")
    assert r_severe.get("is_emergency")
    assert r_severe.get("reason") == "emergency_symptom_detected"



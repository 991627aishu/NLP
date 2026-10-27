import unittest
from app.nlp import (
    normalize_query_for_retrieval,
    extract_herbs,
    extract_symptoms,
    check_emergency_symptoms,
    AYURVEDA_GLOSSARY,
)
from app.classifier import classifier
from app.service import search_project
from app.web_app import evaluation, classifier_metrics

class TestNLPAndEvaluation(unittest.TestCase):
    def test_emergency_triage_detection(self):
        query = "Severe chest pain radiating to left arm and shortness of breath"
        emergency_warning = check_emergency_symptoms(query)
        self.assertIsNotNone(emergency_warning)
        self.assertIn("EMERGENCY MEDICAL WARNING", emergency_warning)
        self.assertIn("cardiovascular", emergency_warning.lower())

    def test_emergency_triage_clean_query(self):
        query = "What is the traditional use of Tulsi for mild cough?"
        emergency = check_emergency_symptoms(query)
        self.assertIsNone(emergency)

    def test_multilingual_herb_extraction(self):
        # Hinglish / Hindi extraction
        query = "ashwagandha ke fayde aur tulsi benefits"
        herbs = extract_herbs(query)
        herb_ids = [h["herb_id"].lower() for h in herbs]
        self.assertIn("ashwagandha", herb_ids)
        self.assertIn("tulsi", herb_ids)

    def test_multilingual_symptom_normalization(self):
        # Hinglish "sir dard" -> headache, Kanglish "thale novu" -> headache
        hinglish_syms = extract_symptoms("mujhe bahut tej sir dard aur bukhar hai")
        self.assertIn("headache", hinglish_syms)
        self.assertIn("fever", hinglish_syms)

        kanglish_syms = extract_symptoms("nanna thale novu mattu kemmu")
        self.assertIn("headache", kanglish_syms)
        self.assertIn("cough", kanglish_syms)

    def test_ayurvedic_glossary_preservation(self):
        query = "How to balance Vata dosha and improve Agni and Ojas?"
        analysis = normalize_query_for_retrieval(query)
        detected_concepts = [c["canonical"].lower() for c in analysis["detected_concepts"]]
        self.assertIn("vata", detected_concepts)
        self.assertIn("agni", detected_concepts)
        self.assertIn("ojas", detected_concepts)

    def test_ml_classifier_inference(self):
        # Test valid characteristic symptoms
        res = classifier.predict("uncoordination fever pleuritic pain snuffle throat sore malaise", top_k=3)
        self.assertFalse(res.get("abstain", True))
        preds = res.get("predictions", [])
        self.assertTrue(len(preds) > 0)
        self.assertEqual(str(preds[0]["condition"]).lower(), "influenza")
        self.assertGreater(preds[0]["confidence"], 0.5)

        # Test safe abstention on insufficient/broad symptoms
        abstain_res = classifier.predict("unknown xyz random query", top_k=3)
        self.assertTrue(abstain_res.get("abstain", False))

    def test_api_evaluation_handlers(self):
        eval_data = evaluation()
        self.assertIn("ablation_results", eval_data)
        methods = [r["method"] for r in eval_data["ablation_results"]]
        self.assertIn("proposed", methods)

        clf_data = classifier_metrics()
        self.assertGreater(clf_data.get("test_accuracy", 0), 0.5)

    def test_service_search_emergency_prepend(self):
        payload = search_project("sudden severe chest pain radiating to jaw")
        self.assertIsNotNone(payload.get("emergency_warning"))
        self.assertIn("EMERGENCY MEDICAL WARNING", payload.get("answer", ""))

    def test_service_search_multilingual_understanding(self):
        payload = search_project("ashwagandha ke fayde kya hai")
        detected_entities = payload.get("detected_entities", {})
        self.assertTrue(len(detected_entities.get("herbs", [])) > 0)
        self.assertIn("Ashwagandha", str(detected_entities["herbs"]))

if __name__ == "__main__":
    unittest.main()

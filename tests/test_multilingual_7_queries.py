import unittest
from app.service import search_project
from app.nlp import check_emergency_symptoms

class TestMultilingualSevenQueries(unittest.TestCase):
    def test_kannada_native(self):
        # Even if submitted under category='disease', auto-routes to herbs
        res = search_project("ತುಳಸಿಯ ಉಪಯೋಗಗಳೇನು?", category="disease")
        self.assertEqual(res["category"], "herbs")
        self.assertIn("Ocimum tenuiflorum", res["answer"])
        self.assertTrue(len(res["sections"]) > 0)
        self.assertIn("ಆಧಾರ ದಾಖಲೆಗಳಲ್ಲಿ", res["answer"])
        self.assertIn("[E1]", res["answer"])

    def test_kannada_kanglish(self):
        res = search_project("tulsi inda enu upayoga?", category="disease")
        self.assertEqual(res["category"], "herbs")
        self.assertIn("Ocimum tenuiflorum", res["answer"])
        self.assertTrue(len(res["sections"]) > 0)
        self.assertIn("ಆಧಾರ ದಾಖಲೆಗಳಲ್ಲಿ", res["answer"])
        self.assertIn("[E1]", res["answer"])

    def test_hindi_native(self):
        res = search_project("तुलसी के क्या फायदे हैं?", category="disease")
        self.assertEqual(res["category"], "herbs")
        self.assertIn("Ocimum tenuiflorum", res["answer"])
        self.assertTrue(len(res["sections"]) > 0)
        self.assertIn("संदर्भों में", res["answer"])
        self.assertIn("[E1]", res["answer"])

    def test_hindi_hinglish(self):
        res = search_project("tulsi ke kya fayde hain?", category="disease")
        self.assertEqual(res["category"], "herbs")
        self.assertIn("Ocimum tenuiflorum", res["answer"])
        self.assertTrue(len(res["sections"]) > 0)
        self.assertIn("संदर्भों में", res["answer"])
        self.assertIn("[E1]", res["answer"])

    def test_telugu_native(self):
        res = search_project("తులసి ఉపయోగాలు ఏమిటి?", category="disease")
        self.assertEqual(res["category"], "herbs")
        self.assertIn("Ocimum tenuiflorum", res["answer"])
        self.assertTrue(len(res["sections"]) > 0)
        self.assertIn("రికార్డులలో", res["answer"])
        self.assertIn("[E1]", res["answer"])

    def test_telugu_romanized(self):
        res = search_project("tulsi upayogalu emiti?", category="disease")
        self.assertEqual(res["category"], "herbs")
        self.assertIn("Ocimum tenuiflorum", res["answer"])
        self.assertTrue(len(res["sections"]) > 0)
        self.assertIn("రికార్డులలో", res["answer"])
        self.assertIn("[E1]", res["answer"])

    def test_english_native(self):
        res = search_project("What are the uses of tulsi?", category="disease")
        self.assertEqual(res["category"], "herbs")
        self.assertIn("Ocimum tenuiflorum", res["answer"])
        self.assertTrue(len(res["sections"]) > 0)
        self.assertIn("distinct therapeutic-use labels", res["answer"])
        self.assertIn("[E1]", res["answer"])

    def test_multilingual_emergency_triage(self):
        queries = [
            ("English", "Severe chest pain radiating to left arm"),
            ("Hinglish", "mujhe sine me tez dard hai"),
            ("Kanglish", "nange ede novu aagthide"),
            ("Telugu native", "నాకు గుండె నొప్పి ఉంది"),
            ("Telugu romanized", "gunde noppi vastundi"),
            ("Kannada native", "ಉಸಿರಾಟ ಕಷ್ಟ ಆಗುತ್ತಿದೆ"),
        ]
        for lang_label, q in queries:
            warning = check_emergency_symptoms(q)
            self.assertIsNotNone(warning, f"Failed emergency triage detection for {lang_label}: {q}")
            self.assertIn("EMERGENCY MEDICAL WARNING", warning)

if __name__ == "__main__":
    unittest.main()

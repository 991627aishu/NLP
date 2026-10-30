"""Phase 2 tests: neural MT plumbing (with fakes), dense backend fallback, grounded HI/KN answers, LLM post-check."""
import pytest

from app.pipeline.translator_neural import (
    to_safe_tokens, from_safe_tokens, inject_lost, TranslationCache,
)
from app.pipeline.translator import MultilingualTranslator
from app.pipeline.llm_generator import post_check, LLMGenerator


# ── placeholder survival ─────────────────────────────────────────────────────
def test_safe_token_roundtrip_and_damage_tolerance():
    safe, ids = to_safe_tokens("__AYURTERM_0__ के कार्य और __AYURTERM_1__")
    assert ids == ["0", "1"] and "AYT0Z" in safe and "AYT1Z" in safe
    restored, lost = from_safe_tokens("Functions of A Y T 0 Z and ayt1z", ids)
    assert lost == [] and "__AYURTERM_0__" in restored and "__AYURTERM_1__" in restored


def test_lost_placeholder_detected_and_injected():
    restored, lost = from_safe_tokens("What are the functions of bile?", ["0"])
    assert lost == ["0"]
    assert inject_lost(restored, lost).endswith("__AYURTERM_0__")


def test_translation_cache(tmp_path):
    c = TranslationCache(tmp_path / "c.sqlite")
    k = TranslationCache.key("m", "hi", "en", "x")
    assert c.get(k) is None
    c.put(k, "y", "m")
    assert c.get(k) == "y"


# ── translator dispatch ──────────────────────────────────────────────────────
def test_rules_fallback_when_neural_missing():
    t = MultilingualTranslator()
    if t.neural is None:
        assert t.backend_used == "rules"
        assert "fallback" in (t.backend_warning or "").lower()
        r = t.translate_to_english("अजीब सा रोग", source_lang="hi")
        assert r["method"] != "indictrans2" and r["warning"]


class FakeNeural:
    """Mimics IndicTrans2Backend.translate_protected deterministically."""
    def __init__(self, table):
        self.table = table

    def translate_protected(self, text, src, tgt):
        safe, ids = to_safe_tokens(text)
        out = self.table.get((safe, src, tgt), safe)
        restored, lost = from_safe_tokens(out, ids)
        return {"text": inject_lost(restored, lost), "placeholders_lost": lost, "model": "fake-it2"}


def test_neural_dispatch_preserves_placeholders():
    t = MultilingualTranslator(backend="rules")
    t.neural = FakeNeural({("AYT0Z AYT1Z ನಿವಾರಿಸುವುದು ಹೇಗೆ?", "kn", "en"): "How to remove AYT0Z AYT1Z?"})
    r = t.translate_to_english("__AYURTERM_0__ __AYURTERM_1__ ನಿವಾರಿಸುವುದು ಹೇಗೆ?", source_lang="kn")
    assert r["method"] == "indictrans2" and r["translated_text"] == "How to remove __AYURTERM_0__ __AYURTERM_1__?"


def test_neural_failure_switches_to_rules():
    class Boom:
        def translate_protected(self, *a, **k):
            raise RuntimeError("weights missing")
    t = MultilingualTranslator(backend="rules")
    t.neural = Boom()
    r = t.translate_to_english("पित्त दोष के कार्य क्या हैं?", source_lang="hi")
    assert r["method"] != "indictrans2" and t.neural is None and t.backend_used == "rules"


def test_output_side_restoration_is_real_with_neural():
    from app.core.protection import TerminologyProtector
    prot = TerminologyProtector()
    t = MultilingualTranslator(backend="rules")
    en = "Pitta governs digestion and metabolism."
    protected, pmap = prot.protect(en)
    assert pmap, "matcher must detect Pitta in English text"
    safe, _ = to_safe_tokens(protected)
    t.neural = FakeNeural({(safe, "en", "hi"): safe.replace("governs digestion and metabolism.", "पाचन और चयापचय को नियंत्रित करता है।")})
    out = t.translate_answer_text(en, "hi", protector=prot)
    assert out["machine_translated"] and "पित्त" in out["text"] and "AYT" not in out["text"]


def test_answer_text_untranslated_without_neural():
    t = MultilingualTranslator(backend="rules")
    out = t.translate_answer_text("Pitta governs digestion.", "kn")
    assert not out["machine_translated"] and out["text"] == "Pitta governs digestion."


# ── dense backend ────────────────────────────────────────────────────────────
def test_dense_auto_falls_back_to_tfidf_without_sentence_transformers():
    try:
        import sentence_transformers  # noqa: F401
        pytest.skip("sentence-transformers installed; fallback path not exercised")
    except ImportError:
        pass
    from app.pipeline.dense_retriever import DenseRetriever
    d = DenseRetriever(backend="auto")
    assert d.backend_used == "tfidf" and d.backend_warning
    res = d.retrieve("Vata dosha")
    assert res and res[0]["dense_backend"] == "tfidf"


# ── grounded HI/KN answers (F3 / F14) ────────────────────────────────────────
@pytest.fixture(scope="module")
def pipe():
    from app.pipeline.rag_pipeline import AyurMitraPipeline
    return AyurMitraPipeline()


def test_kannada_answer_is_not_the_hardcoded_glossary(pipe):
    from app.pipeline.translator import CONCEPT_EXPLANATIONS
    r = pipe.process_query("ಆಮ ದೋಷವನ್ನು ನಿವಾರಿಸುವುದು ಹೇಗೆ?", system_mode="P1", enable_web_search=False)
    if r["abstained"]:
        pytest.skip("abstained (evidence gate) — nothing to check")
    first_line = r["answer"].split("\n")[0]
    assert CONCEPT_EXPLANATIONS["Ama"]["kn"] not in first_line
    assert r["answer_grounding"] in ("evidence_sentence", "web_snippet")
    if CONCEPT_EXPLANATIONS["Ama"]["kn"] in r["answer"]:
        assert "Glossary note" in r["answer"]


def test_machine_translated_flag_reported(pipe):
    r = pipe.process_query("पित्त दोष के कार्य क्या हैं?", system_mode="P1", enable_web_search=False)
    assert "machine_translated" in r
    if pipe.translator.neural is None:
        assert r["machine_translated"] is False


# ── LLM generator post-check ─────────────────────────────────────────────────
def test_llm_post_check_filters():
    allowed = {"WHO_CHUNK_0001", "QA_PASSAGE_0002"}
    txt = ("Pitta is traditionally described as governing transformation [WHO_CHUNK_0001]. "
           "It is linked to fire [FAKE_ID]. No citation here. "
           "Take 5 g daily [QA_PASSAGE_0002]. Agni is recorded as digestive fire [QA_PASSAGE_0002].")
    out = post_check(txt, allowed)
    assert len(out["sentences"]) == 2
    whys = sorted(d["why"] for d in out["dropped"])
    assert whys == ["forbidden_language", "no_citation", "unknown_citation"]
    assert post_check("INSUFFICIENT_EVIDENCE", allowed)["insufficient"]


def test_llm_generator_with_fake_http_and_pipeline_fallback(pipe, monkeypatch):
    calls = {}

    def fake_http(url, payload, headers, timeout=60):
        calls["url"] = url
        cid = payload["messages"][0]["content"].split("[")[1].split("]")[0]
        return {"content": [{"type": "text", "text": f"Ojas is described as the essence of the dhatus [{cid}]."}]}

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    pipe._llm = LLMGenerator(provider="anthropic", model="test-model", http=fake_http)
    r = pipe.process_query("What is Ojas?", system_mode="P1", enable_web_search=False, generator="llm")
    assert r["generator_used"].startswith("llm:anthropic") and "essence" in r["answer"]
    assert calls["url"].endswith("/v1/messages")

    def broken_http(*a, **k):
        raise OSError("network down")
    pipe._llm = LLMGenerator(provider="anthropic", model="test-model", http=broken_http)
    r2 = pipe.process_query("What is Ojas?", system_mode="P1", enable_web_search=False, generator="llm")
    assert r2["generator_used"] == "extractive" and r2["generator_note"]["fell_back_to"] == "extractive"
    pipe._llm = None

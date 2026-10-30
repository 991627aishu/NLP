"""Phase 5-6 tests: voice text processing + fallbacks, and the HTTP API contract."""
import base64
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.voice import stt, tts
from app.voice.text_clean import clean_for_tts, chunk_for_tts, normalize_transcript_terms, SPOKEN_DISCLAIMER

ANSWER = ("**Answer:** Based on curated Ayurvedic literature regarding Pitta: Pitta governs digestion [WHO_CHUNK_0012].\n\n"
          "**Explanation:**\nSee https://example.org/x.\n\nKnowledge Graph Grounding:\n"
          "- Pitta -> described_in -> Pitta (Source: WHO_9789240064935, ITA-2.1.2.1, PDF p.52 (printed p.34))\n\n"
          "**Ayurvedic terms:** Pitta\n\n**Sources:**\n- WHO (`WHO_9789240064935` | pages 51-52)")


# ── text cleaning ────────────────────────────────────────────────────────────
def test_clean_strips_markup_ids_urls_locators():
    t = clean_for_tts(ANSWER, "en")
    for bad in ("**", "WHO_CHUNK", "https://", "ITA-", "PDF p", "Sources", "->", "`"):
        assert bad not in t
    assert "Pitta governs digestion" in t and t.endswith(SPOKEN_DISCLAIMER["en"])
    assert t.count(SPOKEN_DISCLAIMER["en"]) == 1


@pytest.mark.parametrize("lang,native", [("hi", "पित्त"), ("kn", "ಪಿತ್ತ")])
def test_clean_reads_terms_in_native_script(lang, native):
    t = clean_for_tts(ANSWER, lang)
    assert native in t and "Pitta" not in t and t.endswith(SPOKEN_DISCLAIMER[lang])


def test_chunking_limit():
    chunks = chunk_for_tts("This is a sentence about Vata. " * 120)
    assert len(chunks) > 1 and all(len(c) <= 800 for c in chunks)


def test_stt_term_normalisation_with_context_gate():
    r = normalize_transcript_terms("what are the symptoms of vaata and kapa dosha")
    assert r["text"] == "what are the symptoms of Vata and Kapha dosha" and len(r["corrections"]) == 2
    assert normalize_transcript_terms("mere pita ji kaise hain")["corrections"] == []  # pita = father
    assert normalize_transcript_terms("pita dosha ke lakshan")["text"].startswith("Pitta")


# ── TTS chain ────────────────────────────────────────────────────────────────
def test_tts_falls_back_to_browser():
    r = tts.synthesize(ANSWER, "kn", backends=["browser"])
    assert r["backend"] == "browser" and r["browser_lang"] == "kn-IN" and r["chunks"]


def test_tts_edge_backend_with_fake_engine(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "TTS_CACHE_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(tts, "_edge_tts_mp3", lambda text, voice, rate="+0%": calls.append(voice) or b"ID3fake")
    r = tts.synthesize(ANSWER, "hi", voice="male", backends=["edge_tts"])
    assert r["backend"] == "edge_tts" and calls == ["hi-IN-MadhurNeural"]
    assert base64.b64decode(r["audio_base64"][0]) == b"ID3fake"
    r2 = tts.synthesize(ANSWER, "hi", voice="male", backends=["edge_tts"])  # cached: engine not called again
    assert len(calls) == 1 and r2["backend"] == "edge_tts"


def test_tts_engine_error_falls_through(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "TTS_CACHE_DIR", tmp_path)
    def boom(*a, **k):
        raise OSError("no internet")
    monkeypatch.setattr(tts, "_edge_tts_mp3", boom)
    monkeypatch.setattr(tts, "_gtts_mp3", boom)
    r = tts.synthesize("Vata governs movement.", "en", backends=["edge_tts", "gtts", "browser"])
    assert r["backend"] == "browser" and len(r["errors"]) == 2


# ── STT ──────────────────────────────────────────────────────────────────────
def test_stt_missing_library_message(monkeypatch):
    monkeypatch.setattr(stt, "whisper_importable", lambda: False)
    r = stt.transcribe(b"abc")
    assert not r["ok"] and r["error"] == "stt_unavailable" and "type your question" in r["message"]


def test_stt_missing_ffmpeg_message(monkeypatch):
    monkeypatch.setattr(stt, "whisper_importable", lambda: True)
    monkeypatch.setattr(stt, "ffmpeg_path", lambda: None)
    r = stt.transcribe(b"abc")
    assert not r["ok"] and r["error"] == "ffmpeg_missing" and "ffmpeg" in r["message"]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_ffmpeg_decode_path(tmp_path):
    src = tmp_path / "tone.webm"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    "-c:a", "libopus", str(src)], check=True)
    wav = stt.to_wav(src.read_bytes(), suffix=".webm")
    assert wav.exists() and wav.stat().st_size > 10000


def test_stt_injected_transcriber_low_confidence():
    r = stt.transcribe(b"x", transcriber=lambda a, l: ("what is vaata dosha", "en", [0.3, 0.4]))
    assert r["ok"] and r["text"] == "what is Vata dosha" and r["needs_confirmation"] and r["corrections"]


def test_stt_roundtrip_on_samples():
    man = Path(__file__).parent / "audio_samples" / "manifest.json"
    if not man.exists() or not stt.status()["server_stt"]:
        pytest.skip("synthetic clips or faster-whisper not available")
    for item in json.loads(man.read_text(encoding="utf-8")):
        audio = (man.parent / item["file"]).read_bytes()
        r = stt.transcribe(audio, lang_hint=item["lang"], suffix=".mp3")
        assert r["ok"], item


# ── API contract ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from api.main import app
    with TestClient(app) as c:
        yield c


def test_health(client):
    h = client.get("/api/health").json()
    assert h["ok"] and set(h["backends"]) >= {"neural_mt", "embeddings", "stt", "tts", "llm", "web", "knowledge_graph"}
    assert all("live" in v for v in h["backends"].values())


@pytest.mark.parametrize("q,lang", [("What is Ojas?", "en"), ("पित्त दोष के कार्य क्या हैं?", "hi"),
                                    ("ಪಿತ್ತಕ್ಕೆ ಸಂಬಂಧಿಸಿದ ಲಕ್ಷಣಗಳು ಯಾವುವು?", "kn")])
def test_ask_contract(client, q, lang):
    r = client.post("/api/ask", json={"query": q, "mode": "P2"}).json()
    assert r["ok"] and r["target_language"] == lang and "citations" in r and "backends" in r
    assert all(len(p["text"]) <= 700 for p in r["retrieved_passages"])


def test_ask_emergency_is_spoken(client):
    r = client.post("/api/ask", json={"query": "I have sudden severe chest pain", "mode": "P1"}).json()
    assert r["abstained"] and r["is_emergency"] and r["tts"]["spoken_text"]


def test_ask_validation_and_size_limit(client):
    r = client.post("/api/ask", json={"query": ""})
    assert r.status_code == 422 and r.json()["error"] == "invalid_input"
    big = client.post("/api/tts", content=b"x" * (13 * 1024 * 1024), headers={"content-type": "application/json"})
    assert big.status_code == 413


def test_rate_limit(client, monkeypatch):
    import api.main as m
    monkeypatch.setattr(m, "RATE_LIMIT_PER_MIN", 0)
    assert client.get("/api/health").status_code == 429


def test_tts_endpoint(client):
    r = client.post("/api/tts", json={"text": ANSWER, "lang": "hi"}).json()
    assert r["ok"] and r["backend"] in ("edge_tts", "gtts", "browser") and "पित्त" in r["spoken_text"]


def test_voice_transcribe_endpoint(client, monkeypatch):
    monkeypatch.setattr(stt, "transcribe", lambda audio, lang_hint="auto", suffix=".webm":
                        {"ok": True, "text": "what is the role of Agni in digestion", "confidence": 0.95, "needs_confirmation": False})
    r = client.post("/api/voice/transcribe", files={"audio": ("a.webm", b"123")}).json()
    assert r["ok"] is True and r["stage"] == "transcribed" and "Agni" in r["text"]


def test_voice_ask_without_stt_is_friendly(client, monkeypatch):
    monkeypatch.setattr(stt, "whisper_importable", lambda: False)
    r = client.post("/api/voice/ask", files={"audio": ("a.webm", b"123")}).json()
    assert r["ok"] is False and r["stage"] == "stt" and r["message"]


def test_voice_ask_full_flow_with_fake_stt(client, monkeypatch):
    real = stt.transcribe

    def fake(audio, lang_hint="auto", suffix=".webm"):
        return real(audio, transcriber=lambda a, l: ("what is the role of agnee in digestion", "en", [0.9]))
    monkeypatch.setattr(stt, "transcribe", fake)
    r = client.post("/api/voice/ask", files={"audio": ("a.webm", b"123")}, data={"mode": "P1"}).json()
    assert r["stage"] == "answered" and r["transcript"]["corrections"] and "tts" in r
    assert "Agni" in r["raw_query"]


def test_voice_ask_low_confidence_asks_to_confirm(client, monkeypatch):
    monkeypatch.setattr(stt, "transcribe", lambda audio, lang_hint="auto", suffix=".webm":
                        {"ok": True, "text": "what is ojas", "needs_confirmation": True, "confidence": 0.3})
    r = client.post("/api/voice/ask", files={"audio": ("a.webm", b"123")}).json()
    assert r["stage"] == "confirm" and r["transcript"]["text"] == "what is ojas"


def test_symptoms_endpoint(client):
    r = client.post("/api/symptoms", json={"text": "I have dry skin and joint stiffness"}).json()
    assert r["ok"] and r["graph_links"] and all("unverified" in m["locator_review_status"] for m in r["mappings"])
    e = client.post("/api/symptoms", json={"text": "मुझे अचानक तेज सिरदर्द"}).json()
    assert e["reason"] == "emergency_symptom_detected" and "tts" in e


def test_graph_endpoints(client):
    g = client.get("/api/graph", params={"center": "Pitta", "depth": 2, "limit": 60}).json()
    assert g["ok"] and len(g["nodes"]) <= 60 and g["edges"]
    assert client.get("/api/graph/search", params={"q": "ಪಿತ್ತ"}).json()["results"][0]["id"] == "CONCEPT:Pitta"
    n = client.get("/api/graph/node/CONCEPT:Pitta").json()
    assert n["ok"] and all("locator" in e for e in n["outgoing"])
    assert client.get("/api/graph/node/nope-nope").status_code == 404
    assert client.get("/api/graph/path", params={"a": "Tridosha", "b": "Pitta"}).json()["found"]
    assert client.get("/api/graph/stats").json()["nodes"] > 9000


def test_herb_and_lifestyle_endpoints(client):
    assert client.get("/api/herbs/search", params={"q": "neem"}).json()["results"][0]["botanical_name"] == "Azadirachta indica"
    d = client.get("/api/herbs/ashwagandha").json()
    assert d["ok"] and d["traditional_records_note"] and d["disclaimer"]
    assert client.get("/api/lifestyle").json()["topics"]
    assert client.get("/api/lifestyle/diet").json()["passages"]


def test_research_endpoints(client):
    assert client.get("/api/research/results").json()["ok"]
    assert client.get("/api/research/probe").json()["ok"]
    c = client.get("/api/research/compare", params={"query": "What is Ojas?"}).json()
    assert set(c["modes"]) == {"B0", "B1", "P1", "P2"}
    assert client.get("/api/research/files/../../etc/passwd").status_code == 404


def test_feedback_does_not_store_query_without_opt_in(client, tmp_path, monkeypatch):
    import api.main as m
    monkeypatch.setattr(m, "DATA_PROC", tmp_path)
    r = client.post("/api/feedback", json={"rating": "up", "query": "secret question"}).json()
    assert r["ok"] and r["stored_query"] is False
    assert "secret" not in (tmp_path / "feedback.jsonl").read_text(encoding="utf-8")

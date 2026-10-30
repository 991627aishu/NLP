"""
Speech-to-text (Phase 5): browser Web Speech API (client side) -> faster-whisper (server).
Server path: audio bytes -> ffmpeg (16 kHz mono WAV) -> faster-whisper -> language check
with app.core.language_detect -> Ayurvedic term normalisation (logged).
Fails gracefully with a clear, user-facing message when faster-whisper or ffmpeg is missing.
"""
from __future__ import annotations

import logging
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import STT_BACKEND, WHISPER_MODEL_SIZE
from app.core.language_detect import detect
from app.voice.text_clean import normalize_transcript_terms

log = logging.getLogger("ayurmitra.stt")
LOW_CONFIDENCE = 0.6
MAX_SECONDS = 60
_MODEL = None


def ffmpeg_path() -> Optional[str]:
    return shutil.which("ffmpeg")


def whisper_importable() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def status() -> Dict[str, Any]:
    ok_w, ff = whisper_importable(), ffmpeg_path()
    return {"server_stt": bool(ok_w and ff and STT_BACKEND != "none"), "faster_whisper": ok_w,
            "ffmpeg": bool(ff), "model_size": WHISPER_MODEL_SIZE, "browser_stt": "client-side (Chrome/Edge)"}


def to_wav(audio: bytes, suffix: str = ".webm") -> Path:
    ff = ffmpeg_path()
    if not ff:
        raise RuntimeError("ffmpeg_missing")
    tmpdir = Path(tempfile.mkdtemp(prefix="ayur_stt_"))
    src, dst = tmpdir / f"in{suffix}", tmpdir / "out.wav"
    src.write_bytes(audio)
    proc = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-t", str(MAX_SECONDS),
                           "-ac", "1", "-ar", "16000", str(dst)], capture_output=True, timeout=60)
    if proc.returncode != 0 or not dst.exists():
        raise RuntimeError("audio_decode_failed: " + proc.stderr.decode("utf-8", "ignore")[:200])
    return dst


def _model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel  # type: ignore
        _MODEL = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _MODEL


def transcribe(audio: bytes, lang_hint: str = "auto", suffix: str = ".webm", transcriber=None) -> Dict[str, Any]:
    """Returns {ok, text, raw_text, language, confidence, needs_confirmation, corrections, backend, error}."""
    if STT_BACKEND == "none":
        return {"ok": False, "error": "server_stt_disabled", "message": "Server speech recognition is turned off."}
    if transcriber is None and not whisper_importable():
        return {"ok": False, "error": "stt_unavailable",
                "message": "Server speech recognition is not installed (pip install -r requirements-voice.txt). "
                           "Use Chrome or Edge for in-browser recognition, or type your question."}
    try:
        wav = to_wav(audio, suffix=suffix) if transcriber is None else None
    except RuntimeError as e:
        msg = ("ffmpeg is not installed or not on PATH (Windows: winget install Gyan.FFmpeg)."
               if "ffmpeg_missing" in str(e) else "The recording could not be decoded. Please try again.")
        return {"ok": False, "error": str(e).split(":")[0], "message": msg}
    try:
        if transcriber is not None:   # injected for tests
            raw, lang, probs = transcriber(audio, lang_hint)
        else:
            segments, info = _model().transcribe(str(wav), language=None if lang_hint == "auto" else lang_hint,
                                                  vad_filter=True, beam_size=5)
            segs = list(segments)
            raw = " ".join(s.text.strip() for s in segs).strip()
            lang = info.language
            probs = [math.exp(s.avg_logprob) for s in segs] or [0.0]
    except Exception as e:
        log.warning("STT failed: %s", e)
        return {"ok": False, "error": "stt_failed", "message": "Speech recognition failed. Please try again or type."}
    conf = round(sum(probs) / len(probs), 3) if probs else 0.0
    norm = normalize_transcript_terms(raw)
    script_lang = detect(norm["text"]).get("dominant_lang", lang) if norm["text"] else lang
    return {"ok": bool(norm["text"]), "text": norm["text"], "raw_text": raw, "language": lang,
            "language_by_script": script_lang, "confidence": conf,
            "needs_confirmation": conf < LOW_CONFIDENCE or not norm["text"],
            "corrections": norm["corrections"], "backend": "faster_whisper" if transcriber is None else "injected",
            "error": None if norm["text"] else "empty_transcript"}

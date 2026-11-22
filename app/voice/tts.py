"""
Text-to-speech chain (Phase 5): edge-tts -> gTTS -> browser speechSynthesis.
Voices (checked 2026-10-30 against the edge-tts voice list):
  en-IN-NeerjaNeural / en-IN-PrabhatNeural, hi-IN-SwaraNeural / hi-IN-MadhurNeural,
  kn-IN-SapnaNeural / kn-IN-GaganNeural.
edge-tts and gTTS both need internet access. When neither is installed or
reachable, ``synthesize`` returns backend="browser" with the cleaned text chunks so
the web page speaks them with the browser's speechSynthesis.
MP3s are cached by content hash in Data/processed/cache/tts/.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
from typing import Any, Dict, List, Optional

from app.config import TTS_BACKEND, TTS_CACHE_DIR
from app.voice.text_clean import chunk_for_tts, clean_for_tts

log = logging.getLogger("ayurmitra.tts")

VOICES = {
    "en": {"female": "en-IN-NeerjaNeural", "male": "en-IN-PrabhatNeural"},
    "hi": {"female": "hi-IN-SwaraNeural", "male": "hi-IN-MadhurNeural"},
    "kn": {"female": "kn-IN-SapnaNeural", "male": "kn-IN-GaganNeural"},
    "hinglish": {"female": "hi-IN-SwaraNeural", "male": "hi-IN-MadhurNeural"},
    "kanglish": {"female": "kn-IN-SapnaNeural", "male": "kn-IN-GaganNeural"},
}
BROWSER_LANG = {
    "en": "en-IN",
    "hi": "hi-IN",
    "kn": "kn-IN",
    "hinglish": "hi-IN",
    "kanglish": "kn-IN",
}


def _have(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def available_backends() -> List[str]:
    order = []
    if TTS_BACKEND in ("auto", "edge_tts") and _have("edge_tts"):
        order.append("edge_tts")
    if TTS_BACKEND in ("auto", "gtts", "edge_tts") and _have("gtts"):
        order.append("gtts")
    order.append("browser")
    return order


def _edge_tts_mp3(text: str, voice: str, rate: str = "+0%") -> bytes:
    import edge_tts  # type: ignore

    async def run() -> bytes:
        com = edge_tts.Communicate(text, voice, rate=rate)
        buf = b""
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                buf += chunk["data"]
        return buf
    async def _runner() -> bytes:
        return await asyncio.wait_for(run(), timeout=4.0)

    try:
        return asyncio.run(_runner())
    except RuntimeError:  # already inside an event loop (e.g. FastAPI): run in a fresh loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_runner())
        finally:
            loop.close()


def _gtts_mp3(text: str, lang: str) -> bytes:
    from gtts import gTTS  # type: ignore
    import io
    buf = io.BytesIO()
    gTTS(text=text, lang=lang).write_to_fp(buf)
    return buf.getvalue()


def synthesize(text: str, lang: str = "en", voice: str = "female", clean: bool = True,
               add_disclaimer: bool = True, backends: Optional[List[str]] = None) -> Dict[str, Any]:
    lang = lang if lang in VOICES else "en"
    spoken = clean_for_tts(text, lang, add_disclaimer=add_disclaimer) if clean else text
    chunks = chunk_for_tts(spoken)
    errors = []
    gtts_lang = "hi" if lang in ("hi", "hinglish") else ("kn" if lang in ("kn", "kanglish") else "en")
    for b in (backends or available_backends()):
        if b == "browser":
            break
        try:
            audio_parts = []
            for c in chunks:
                vname = VOICES[lang].get(voice, VOICES[lang]["female"]) if b == "edge_tts" else gtts_lang
                key = hashlib.sha256(f"{b}|{vname}|{c}".encode("utf-8")).hexdigest()
                path = TTS_CACHE_DIR / f"{key}.mp3"
                if path.exists():
                    data = path.read_bytes()
                else:
                    data = _edge_tts_mp3(c, vname) if b == "edge_tts" else _gtts_mp3(c, gtts_lang)
                    if not data:
                        raise RuntimeError("empty audio")
                    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                audio_parts.append(data)
            return {"backend": b, "voice": VOICES[lang].get(voice) if b == "edge_tts" else f"gtts:{lang}",
                    "lang": lang, "mime": "audio/mpeg", "spoken_text": spoken, "chunks": chunks,
                    "audio_base64": [base64.b64encode(a).decode("ascii") for a in audio_parts], "errors": errors}
        except Exception as e:
            errors.append(f"{b}: {type(e).__name__}: {str(e)[:120]}")
            log.warning("TTS backend %s failed: %s", b, e)
    return {"backend": "browser", "voice": None, "browser_lang": BROWSER_LANG[lang], "lang": lang,
            "spoken_text": spoken, "chunks": chunks, "audio_base64": [], "errors": errors,
            "note": "Server TTS unavailable — the page will use the browser's built-in speech synthesis."}

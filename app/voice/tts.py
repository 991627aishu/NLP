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
import re
from typing import Any, Dict, List, Optional

from app.config import TTS_BACKEND, TTS_CACHE_DIR
from app.voice.text_clean import chunk_for_tts, clean_for_tts

log = logging.getLogger("ayurmitra.tts")

_KN_RX = re.compile(r"[\u0C80-\u0CFF]")
_HI_RX = re.compile(r"[\u0900-\u097F]")

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
        return await asyncio.wait_for(run(), timeout=10.0)

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
    import concurrent.futures
    import io

    def _run() -> bytes:
        buf = io.BytesIO()
        gTTS(text=text, lang=lang).write_to_fp(buf)
        return buf.getvalue()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_run)
        return fut.result(timeout=6.0)


def detect_response_language(text: str, fallback_lang: str = "en") -> str:
    """Detect the actual language of a response text without translating it."""
    fb = fallback_lang if fallback_lang in VOICES else "en"
    t = (text or "").strip()
    if not t:
        return fb
    kn_cnt = len(_KN_RX.findall(t))
    hi_cnt = len(_HI_RX.findall(t))
    if kn_cnt >= 6 and kn_cnt >= hi_cnt:
        return "kn"
    if hi_cnt >= 6 and hi_cnt > kn_cnt:
        return "hi"
    try:
        from app.core.language_detect import detect
        info = detect(t)
        cm = info.get("code_mix_type", "")
        dom = info.get("dominant_lang", "en")
        if cm == "hinglish_romanized" or (info.get("is_romanized") and dom == "hi"):
            return "hinglish"
        if cm == "kanglish_romanized" or (info.get("is_romanized") and dom == "kn"):
            return "kanglish"
        if dom in VOICES:
            if dom == "en" and fb in ("hinglish", "kanglish") and info.get("is_romanized"):
                return fb
            return dom
    except Exception:
        pass
    return fb


def segment_chunks_for_tts(text: str, base_lang: str, max_chars: int = 450) -> List[Dict[str, str]]:
    """Split text into complete, non-truncated chunks with per-chunk language tags."""
    raw_chunks = chunk_for_tts(text, max_chars=max_chars)
    out: List[Dict[str, str]] = []
    for c in raw_chunks:
        kn_cnt = len(_KN_RX.findall(c))
        hi_cnt = len(_HI_RX.findall(c))
        if kn_cnt >= 4 and kn_cnt >= hi_cnt:
            seg_lang = "kn"
        elif hi_cnt >= 4 and hi_cnt > kn_cnt:
            seg_lang = "hi"
        elif base_lang in ("kn", "hi"):
            # Pure-English sentence inside a mixed Kannada/Hindi answer gets en-IN voice
            try:
                from app.core.language_detect import detect, ENGLISH_FUNCTIONAL_WORDS
                words = set(re.findall(r"\b[A-Za-z]+\b", c.lower()))
                if len(words & ENGLISH_FUNCTIONAL_WORDS) >= 3 and not detect(c).get("is_romanized"):
                    seg_lang = "en"
                else:
                    seg_lang = base_lang
            except Exception:
                seg_lang = base_lang
        elif base_lang in ("hinglish", "kanglish"):
            try:
                from app.core.language_detect import detect, ENGLISH_FUNCTIONAL_WORDS, HINDI_ROMAN_GRAMMAR, KANNADA_ROMAN_GRAMMAR
                words = set(re.findall(r"\b[A-Za-z]+\b", c.lower()))
                en_w = len(words & ENGLISH_FUNCTIONAL_WORDS)
                rom_w = len(words & (HINDI_ROMAN_GRAMMAR if base_lang == "hinglish" else KANNADA_ROMAN_GRAMMAR))
                if en_w >= 3 and rom_w == 0 and not detect(c).get("is_romanized"):
                    seg_lang = "en"
                else:
                    seg_lang = base_lang
            except Exception:
                seg_lang = base_lang
        else:
            seg_lang = base_lang if base_lang in VOICES else "en"
        out.append({"text": c, "lang": seg_lang, "browser_lang": BROWSER_LANG.get(seg_lang, "en-IN")})
    return out


def synthesize(text: str, lang: str = "auto", voice: str = "female", clean: bool = True,
               add_disclaimer: bool = True, backends: Optional[List[str]] = None) -> Dict[str, Any]:
    req_lang = (lang or "auto").strip().lower()
    if req_lang in ("", "auto") or req_lang not in VOICES:
        lang = detect_response_language(text, fallback_lang="en")
    else:
        # Never let a stale question language ('en') override actual Kannada/Hindi script in the answer
        detected = detect_response_language(text, fallback_lang=req_lang)
        lang = detected if detected in ("kn", "hi") and req_lang == "en" else req_lang

    spoken = clean_for_tts(text, lang, add_disclaimer=add_disclaimer) if clean else text
    seg_chunks = segment_chunks_for_tts(spoken, lang, max_chars=450)
    chunks = [s["text"] for s in seg_chunks]
    chunk_langs = [s["browser_lang"] for s in seg_chunks]
    errors = []
    for b in (backends or available_backends()):
        if b == "browser":
            break
        try:
            audio_parts = []
            for seg in seg_chunks:
                c = seg["text"]
                seg_lang = seg["lang"]
                gtts_lang = "hi" if seg_lang in ("hi", "hinglish") else ("kn" if seg_lang in ("kn", "kanglish") else "en")
                vname = VOICES[seg_lang].get(voice, VOICES[seg_lang]["female"]) if b == "edge_tts" else gtts_lang
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
                    "lang": lang, "browser_lang": BROWSER_LANG[lang], "mime": "audio/mpeg",
                    "spoken_text": spoken, "chunks": chunks, "chunk_langs": chunk_langs,
                    "audio_base64": [base64.b64encode(a).decode("ascii") for a in audio_parts], "errors": errors}
        except Exception as e:
            errors.append(f"{b}: {type(e).__name__}: {str(e)[:120]}")
            log.warning("TTS backend %s failed: %s", b, e)
    return {"backend": "browser", "voice": None, "browser_lang": BROWSER_LANG[lang], "lang": lang,
            "spoken_text": spoken, "chunks": chunks, "chunk_langs": chunk_langs, "audio_base64": [], "errors": errors,
            "note": "Server TTS unavailable — the page will use the browser's built-in speech synthesis."}

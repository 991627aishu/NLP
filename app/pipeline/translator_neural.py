"""
AyurMitra — IndicTrans2 neural translation backend (Phase 2, audit F1)
======================================================================
Model cards checked 2026-10-30 (AI4Bharat, MIT licence):
  * ai4bharat/indictrans2-indic-en-dist-200M   (hi/kn -> en)  — GATED: log in to
    Hugging Face, accept the terms on the model page, set HF_TOKEN.
  * ai4bharat/indictrans2-en-indic-dist-200M   (en -> hi/kn)
Usage per card: AutoTokenizer/AutoModelForSeq2SeqLM with trust_remote_code=True,
IndicProcessor(inference=True).preprocess_batch(src_lang=..., tgt_lang=...),
generate(num_beams=5, max_length=256), batch_decode, postprocess_batch(lang=tgt).
Language codes: eng_Latn, hin_Deva, kan_Knda.

VERIFICATION STATUS: this module could not be executed in the build
environment (PyPI and Hugging Face blocked). Everything degrades to the
rule-based translator when torch / transformers / the toolkit / the weights are
unavailable, and the response trace says so ("backend_used", "backend_warning").

Terminology protection is unchanged (protect -> translate -> restore). Neural
MT may rewrite our ``__AYURTERM_n__`` placeholders, so before translation they
are swapped for a short ASCII token (``AYT<n>Z``) and every token is verified
afterwards; tolerant matching repairs spacing/case damage and anything still
missing is logged as ``placeholder_lost`` and re-injected (canonical-ID injection).
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import (
    INDICTRANS2_INDIC_EN, INDICTRANS2_EN_INDIC, IT2_LANG_CODES, TRANSLATION_CACHE,
)

log = logging.getLogger("ayurmitra.mt")

PLACEHOLDER_RX = re.compile(r"__AYURTERM_(\d+)__")
SAFE_TOKEN = "AYT{0}Z"
SAFE_TOKEN_RX = re.compile(r"A\s*Y\s*T\s*(\d+)\s*Z", re.IGNORECASE)


# ── Placeholder handling (pure functions; unit-tested without a model) ────────
def to_safe_tokens(text: str) -> Tuple[str, List[str]]:
    ids = PLACEHOLDER_RX.findall(text)
    return PLACEHOLDER_RX.sub(lambda m: SAFE_TOKEN.format(m.group(1)), text), ids


def from_safe_tokens(text: str, expected_ids: List[str]) -> Tuple[str, List[str]]:
    """Map AYT<n>Z (tolerantly) back to __AYURTERM_n__. Returns (text, lost_ids)."""
    restored = SAFE_TOKEN_RX.sub(lambda m: f"__AYURTERM_{m.group(1)}__", text)
    # also accept placeholders that survived verbatim or with damaged underscores
    restored = re.sub(r"_+\s*AYURTERM\s*_*\s*(\d+)\s*_+", lambda m: f"__AYURTERM_{m.group(1)}__", restored,
                      flags=re.IGNORECASE)
    present = set(PLACEHOLDER_RX.findall(restored))
    lost = [i for i in expected_ids if i not in present]
    return restored, lost


def inject_lost(text: str, lost_ids: List[str]) -> str:
    """Canonical-ID injection: append lost placeholders so restoration can still insert the term."""
    if not lost_ids:
        return text
    return text.rstrip() + " " + " ".join(f"__AYURTERM_{i}__" for i in lost_ids)


# ── Cache ─────────────────────────────────────────────────────────────────────
class TranslationCache:
    def __init__(self, path: Path = TRANSLATION_CACHE):
        self.path = path
        self._lock = threading.Lock()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(path) as c:
                c.execute("CREATE TABLE IF NOT EXISTS mt (k TEXT PRIMARY KEY, v TEXT, model TEXT)")
            self.ok = True
        except Exception as e:
            log.warning("Translation cache disabled (%s)", e)
            self.ok = False

    @staticmethod
    def key(model: str, src: str, tgt: str, text: str) -> str:
        return hashlib.sha256(f"{model}|{src}|{tgt}|{text}".encode("utf-8")).hexdigest()

    def get(self, k: str) -> Optional[str]:
        if not self.ok:
            return None
        with self._lock, sqlite3.connect(self.path) as c:
            row = c.execute("SELECT v FROM mt WHERE k=?", (k,)).fetchone()
        return row[0] if row else None

    def put(self, k: str, v: str, model: str) -> None:
        if not self.ok:
            return
        with self._lock, sqlite3.connect(self.path) as c:
            c.execute("INSERT OR REPLACE INTO mt (k, v, model) VALUES (?,?,?)", (k, v, model))


# ── Backend ──────────────────────────────────────────────────────────────────
class IndicTrans2Backend:
    """Lazy-loading IndicTrans2 wrapper. ``available()`` never raises."""

    def __init__(self):
        self._models: Dict[str, Tuple[object, object]] = {}
        self._processor = None
        self._torch = None
        self.error: Optional[str] = None
        self.cache = TranslationCache()
        self._lock = threading.Lock()

    # import check only (cheap) — weights load on first use
    def importable(self) -> bool:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            self._import_processor()
            return True
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            return False

    def _import_processor(self):
        if self._processor is not None:
            return self._processor
        last = None
        for mod, attr in (("IndicTransToolkit.processor", "IndicProcessor"),
                          ("IndicTransToolkit", "IndicProcessor"),
                          ("IndicTransTokenizer", "IndicProcessor")):
            try:
                m = __import__(mod, fromlist=[attr])
                self._processor = getattr(m, attr)(inference=True)
                return self._processor
            except Exception as e:  # try next import path
                last = e
        raise ImportError(f"IndicTransToolkit not importable ({last})")

    def _load(self, direction: str):
        if direction in self._models:
            return self._models[direction]
        with self._lock:
            if direction in self._models:
                return self._models[direction]
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            name = INDICTRANS2_INDIC_EN if direction == "indic-en" else INDICTRANS2_EN_INDIC
            token = os.environ.get("HF_TOKEN") or None
            tok = AutoTokenizer.from_pretrained(name, trust_remote_code=True, token=token)
            model = AutoModelForSeq2SeqLM.from_pretrained(name, trust_remote_code=True, token=token)
            model.eval()
            self._torch = torch
            self._models[direction] = (tok, model)
            return tok, model

    def model_name(self, src: str, tgt: str) -> str:
        return INDICTRANS2_INDIC_EN if tgt == "en" else INDICTRANS2_EN_INDIC

    def translate(self, sentences: List[str], src: str, tgt: str) -> List[str]:
        """Translate a batch. Raises on failure (caller falls back)."""
        if not sentences:
            return []
        model_name = self.model_name(src, tgt)
        out: List[Optional[str]] = []
        todo: List[int] = []
        for i, s in enumerate(sentences):
            hit = self.cache.get(TranslationCache.key(model_name, src, tgt, s))
            out.append(hit)
            if hit is None:
                todo.append(i)
        if todo:
            direction = "indic-en" if tgt == "en" else "en-indic"
            tok, model = self._load(direction)
            ip = self._import_processor()
            src_code, tgt_code = IT2_LANG_CODES[src], IT2_LANG_CODES[tgt]
            batch = ip.preprocess_batch([sentences[i] for i in todo], src_lang=src_code, tgt_lang=tgt_code)
            inputs = tok(batch, truncation=True, padding="longest", return_tensors="pt", return_attention_mask=True)
            with self._torch.no_grad():
                gen = model.generate(**inputs, use_cache=True, min_length=0, max_length=256,
                                     num_beams=5, num_return_sequences=1)
            decoded = tok.batch_decode(gen, skip_special_tokens=True, clean_up_tokenization_spaces=True)
            decoded = ip.postprocess_batch(decoded, lang=tgt_code)
            for i, d in zip(todo, decoded):
                out[i] = d
                self.cache.put(TranslationCache.key(model_name, src, tgt, sentences[i]), d, model_name)
        return [o or "" for o in out]

    def translate_protected(self, text: str, src: str, tgt: str) -> Dict[str, object]:
        """Translate text that may contain __AYURTERM_n__ placeholders; verify they survive."""
        safe, ids = to_safe_tokens(text)
        raw = self.translate([safe], src, tgt)[0]
        restored, lost = from_safe_tokens(raw, ids)
        if lost:
            log.warning("placeholder_lost: %s (src=%s tgt=%s)", lost, src, tgt)
            restored = inject_lost(restored, lost)
        return {"text": restored, "placeholders_lost": lost, "model": self.model_name(src, tgt)}


_SINGLETON: Optional[IndicTrans2Backend] = None


def get_backend() -> IndicTrans2Backend:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = IndicTrans2Backend()
    return _SINGLETON

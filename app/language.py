"""Language and script detection and translation adapters for English, Hindi, Kannada, and Telugu.

Provides native script detection, romanized/code-mixed keyword heuristics,
terminology-preserving canonical normalization, and translation fallbacks.
"""
from __future__ import annotations

import os
import re
from typing import Any

LANGS = {
    'English': {'script': 'Latin', 'code': 'eng_Latn', 'iso': 'en'},
    'Hindi': {'script': 'Devanagari', 'code': 'hin_Deva', 'iso': 'hi'},
    'Kannada': {'script': 'Kannada', 'code': 'kan_Knda', 'iso': 'kn'},
    'Telugu': {'script': 'Telugu', 'code': 'tel_Telu', 'iso': 'te'},
}


def detect_language(text: str) -> dict[str, Any]:
    """Detect language and script for English, Hindi, Kannada, Telugu, and Romanized forms."""
    text_str = str(text or "").strip()
    if not text_str:
        return {
            'name': 'English or romanized/code-mixed Latin input',
            'language': 'English',
            'script': 'Latin',
            'code': 'eng_Latn',
            'confidence': 'low',
            'method': 'empty fallback',
        }

    # 1. Native Script Detection (Unicode Ranges)
    if re.search(r'[\u0c80-\u0cff]', text_str):
        return {
            'name': 'Kannada',
            'language': 'Kannada',
            'script': 'Kannada',
            'code': 'kan_Knda',
            'confidence': 'high',
            'method': 'Unicode script detection',
        }
    if re.search(r'[\u0900-\u097f]', text_str):
        return {
            'name': 'Hindi (Devanagari; other Devanagari languages may be confused)',
            'language': 'Hindi',
            'script': 'Devanagari',
            'code': 'hin_Deva',
            'confidence': 'medium',
            'method': 'Unicode script detection',
        }
    if re.search(r'[\u0c00-\u0c7f]', text_str):
        return {
            'name': 'Telugu',
            'language': 'Telugu',
            'script': 'Telugu',
            'code': 'tel_Telu',
            'confidence': 'high',
            'method': 'Unicode script detection',
        }
    if re.search(r'[\u0b80-\u0bff]', text_str):
        return {
            'name': 'Tamil',
            'language': 'Tamil',
            'script': 'Tamil',
            'code': 'tam_Taml',
            'confidence': 'high',
            'method': 'Unicode script detection',
        }

    # 2. Romanized / Latin-Script Keyword Heuristics
    low = ' ' + re.sub(r'[^a-z ]', ' ', text_str.lower()) + ' '
    words = set(low.split())

    kannada_hints = {
        'enu', 'alla', 'hege', 'nanna', 'beku', 'yenu', 'aagide', 'thumba',
        'mathu', 'mattu', 'roga', 'sari', 'thale', 'novu', 'nanage', 'nange',
        'yake', 'illa', 'agutte', 'aaytu', 'kemmu', 'hotte', 'inda', 'upayoga',
        'upayogagalu', 'yavudu', 'yavavu', 'bagge', 'kasa', 'daddalu'
    }
    hindi_hints = {
        'kya', 'hai', 'hain', 'mujhe', 'mera', 'meri', 'kaise', 'bukhar',
        'dard', 'pet', 'chahiye', 'kyun', 'fayde', 'fayda', 'labh', 'khansi',
        'upayog', 'upyog', 'hote', 'hoti', 'hota', 'ke', 'ki', 'ka'
    }
    telugu_hints = {
        'upayogalu', 'upayogam', 'prayojanam', 'emiti', 'yemiti', 'ela',
        'gurinchi', 'naaku', 'naku', 'undi', 'unnadi', 'rogo', 'manta',
        'daggina', 'daggu', 'jwaram', 'mandulu', 'aushadham', 'cheyali',
        'kavali', 'enti', 'thalanopii', 'kadupunoppi', 'vepa', 'allam', 'pasupu'
    }

    # Count matching tokens
    k_matches = len(words & kannada_hints)
    h_matches = len(words & hindi_hints)
    t_matches = len(words & telugu_hints)

    # Specific multi-word phrases for Kanglish/Hinglish/Telugu
    if k_matches >= 1 and (k_matches >= 2 or any(token in low for token in [' enu ', ' inda ', ' upayoga', ' thale ', ' novu ', ' kemmu '])):
        return {
            'name': 'Possible romanized Kannada / Kanglish',
            'language': 'Kannada',
            'script': 'Latin',
            'code': 'kan_Latn',
            'confidence': 'medium' if k_matches >= 2 else 'low',
            'method': 'keyword heuristic; confirm language if needed',
        }

    if t_matches >= 1 and (t_matches >= 2 or any(token in low for token in [' upayogalu', ' upayogam', ' emiti', ' yemiti', ' ela ', ' gurinchi'])):
        return {
            'name': 'Possible romanized Telugu',
            'language': 'Telugu',
            'script': 'Latin',
            'code': 'tel_Latn',
            'confidence': 'medium' if t_matches >= 2 else 'low',
            'method': 'keyword heuristic; confirm language if needed',
        }

    if h_matches >= 1 and (h_matches >= 2 or any(token in low for token in [' kya ', ' fayde', ' fayda', ' bukhar', ' dard '])):
        return {
            'name': 'Possible romanized Hindi / Hinglish',
            'language': 'Hindi',
            'script': 'Latin',
            'code': 'hin_Latn',
            'confidence': 'medium' if h_matches >= 2 else 'low',
            'method': 'keyword heuristic; confirm language if needed',
        }

    return {
        'name': 'English or romanized/code-mixed Latin input',
        'language': 'English',
        'script': 'Latin',
        'code': 'eng_Latn',
        'confidence': 'low',
        'method': 'Latin-script heuristic',
    }


class IndicTranslator:
    """Translation manager supporting IndicTrans2 with graceful fallback to Google Translate or canonical glossaries."""

    def __init__(self):
        # Disabled by default to prevent silent ungrounded search; can be enabled via AYURMITRA_TRANSLATION=on
        setting = os.environ.get('AYURMITRA_TRANSLATION', 'off').lower()
        self.enabled = setting in {'on', 'true', '1', 'google', 'indictrans2'}
        self.use_indic = setting in {'indictrans2'}
        self._models: dict[str, Any] = {}
        self._google = None
        try:
            from deep_translator import GoogleTranslator
            self._google = GoogleTranslator
        except ImportError:
            pass

    def _load(self, direction: str):
        if direction in self._models:
            return self._models[direction]
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            from IndicTransToolkit import IndicProcessor
        except Exception as exc:
            raise RuntimeError('IndicTrans2 is not installed.') from exc

        model_name = (
            'ai4bharat/indictrans2-indic-en-1B'
            if direction == 'to_en'
            else 'ai4bharat/indictrans2-en-indic-1B'
        )
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True)
        model.eval()
        processor = IndicProcessor(inference=True)
        self._models[direction] = (tokenizer, model, processor, torch)
        return self._models[direction]

    def translate(self, text: str, source_code: str, target_code: str) -> str:
        """Translate text with fallback to prevent rate-limit crashes."""
        if not text or source_code == target_code:
            return text

        if not self.enabled:
            raise RuntimeError("Translation is disabled via AYURMITRA_TRANSLATION setting.")

        # 1. IndicTrans2 if explicitly enabled
        if self.use_indic:
            try:
                direction = 'to_en' if target_code == 'eng_Latn' else 'from_en'
                tokenizer, model, processor, torch = self._load(direction)
                batch = processor.preprocess_batch([text], src_lang=source_code, tgt_lang=target_code)
                inputs = tokenizer(batch, truncation=True, padding='longest', return_tensors='pt')
                with torch.no_grad():
                    generated = model.generate(**inputs, max_length=256, num_beams=4, num_return_sequences=1)
                decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
                return processor.postprocess_batch(decoded, lang=target_code)[0]
            except Exception:
                pass  # Fall through to Google Translate

        # 2. Google Translate via deep_translator
        if self._google:
            try:
                src = (
                    source_code.split('_')[0]
                    .replace('eng', 'en')
                    .replace('hin', 'hi')
                    .replace('kan', 'kn')
                    .replace('tel', 'te')
                )
                tgt = (
                    target_code.split('_')[0]
                    .replace('eng', 'en')
                    .replace('hin', 'hi')
                    .replace('kan', 'kn')
                    .replace('tel', 'te')
                )
                if source_code.endswith('Latn'):
                    src = 'auto'

                translator = self._google(source=src, target=tgt)
                translated = translator.translate(text)
                if translated:
                    return translated
            except Exception:
                pass

        # 3. Canonical fallback: return original text safely
        return text


translator = IndicTranslator()
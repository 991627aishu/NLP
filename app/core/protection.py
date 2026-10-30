"""
AyurMitra — Terminology Protection & Restoration
==================================================
Protects Ayurvedic domain terms before translation using invariant placeholder
tokens, and restores them accurately after translation into canonical or
localized terminology.

Prevents translation drift:
  - "Agni" -> "Fire" (biomedical/everyday drift)
  - "Pitta" -> "Bile"
  - "Vata" -> "Wind / Air"
  - "Kapha" -> "Phlegm / Cough"
  - "Rasa" -> "Juice / Taste"
  - "Ojas" -> "Vigor"
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from app.core.matcher import (
    TerminologyMatcher,
    CANONICAL_TO_HINDI,
    CANONICAL_TO_KANNADA,
)

PLACEHOLDER_PREFIX = "__AYURTERM_"
PLACEHOLDER_SUFFIX = "__"
PLACEHOLDER_PATTERN = re.compile(r"__\s*AYURTERM_(\d+)\s*__", re.IGNORECASE)


class TerminologyProtector:
    """Safeguards domain terms across translation boundaries."""

    def __init__(self, matcher: TerminologyMatcher = None):
        self.matcher = matcher or TerminologyMatcher()

    def protect(self, text: str) -> Tuple[str, Dict[str, Dict[str, Any]]]:
        """
        Replaces identified Ayurvedic terms with placeholders.

        Returns:
            protected_text: Text with placeholders inserted.
            placeholder_map: Dictionary mapping placeholder token to term metadata:
              {
                "__AYURTERM_0__": {
                  "canonical_term": "Pitta",
                  "matched_text": "ಪಿತ್ತ",
                  "concept_id": "TERM_0002",
                  "script": "Kannada"
                }
              }
        """
        if not text:
            return "", {}

        matches = self.matcher.find_terms(text)
        if not matches:
            return text, {}

        placeholder_map: Dict[str, Dict[str, Any]] = {}
        # Replace from end to start to preserve character indices
        result_chars = list(text)
        for i, match in enumerate(reversed(matches)):
            idx = len(matches) - 1 - i
            token = f"{PLACEHOLDER_PREFIX}{idx}{PLACEHOLDER_SUFFIX}"
            placeholder_map[token] = {
                "canonical_term": match["canonical_term"],
                "matched_text": match["matched_text"],
                "concept_id": match["concept_id"],
                "script": match["script"],
            }
            start = match["start"]
            end = match["end"]
            result_chars[start:end] = list(token)

        protected_text = "".join(result_chars)
        return protected_text, placeholder_map

    def restore_canonical(self, text: str, placeholder_map: Dict[str, Dict[str, Any]]) -> str:
        """
        Restores placeholders to their canonical English/Sanskrit terms.
        Used for English retrieval queries.
        """
        if not text or not placeholder_map:
            return text

        def _repl(match: re.Match) -> str:
            num = match.group(1)
            token = f"{PLACEHOLDER_PREFIX}{num}{PLACEHOLDER_SUFFIX}"
            if token in placeholder_map:
                return placeholder_map[token]["canonical_term"]
            return match.group(0)

        restored = PLACEHOLDER_PATTERN.sub(_repl, text)
        return restored

    def restore_original(self, text: str, placeholder_map: Dict[str, Dict[str, Any]]) -> str:
        """
        Restores placeholders to their original matched user text.
        Used for faithful localized output.
        """
        if not text or not placeholder_map:
            return text

        def _repl(match: re.Match) -> str:
            num = match.group(1)
            token = f"{PLACEHOLDER_PREFIX}{num}{PLACEHOLDER_SUFFIX}"
            if token in placeholder_map:
                return placeholder_map[token]["matched_text"]
            return match.group(0)

        restored = PLACEHOLDER_PATTERN.sub(_repl, text)
        return restored

    def restore_to_language(
        self,
        text: str,
        placeholder_map: Dict[str, Dict[str, Any]],
        target_lang: str = "en"
    ) -> str:
        """
        Restores placeholders to language-appropriate term representations:
          - 'en': Canonical English (e.g. Pitta, Agni, Vata)
          - 'hi': Devanagari Hindi (e.g. पित्त, अग्नि, वात)
          - 'kn': Kannada script (e.g. ಪಿತ್ತ, ಅಗ್ನಿ, ವಾತ)
        """
        if not text or not placeholder_map:
            return text

        def _repl(match: re.Match) -> str:
            num = match.group(1)
            token = f"{PLACEHOLDER_PREFIX}{num}{PLACEHOLDER_SUFFIX}"
            if token in placeholder_map:
                info = placeholder_map[token]
                canon = info.get("canonical_term", "")
                if target_lang == "hi":
                    return CANONICAL_TO_HINDI.get(canon, info.get("matched_text", canon))
                elif target_lang == "kn":
                    return CANONICAL_TO_KANNADA.get(canon, info.get("matched_text", canon))
                else:
                    return canon
            return match.group(0)

        restored = PLACEHOLDER_PATTERN.sub(_repl, text)
        return restored

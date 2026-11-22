"""
AyurMitra — Ingestion Deduplication & Data Quality Verifier
===========================================================
Detects exact and near-duplicate chunks, validates document integrity,
and enforces data cleanliness rules before embedding or indexing.
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Set, Tuple


class ContentDeduplicator:
    """Detects exact and near-duplicate content across indexed chunks."""

    def __init__(self, jaccard_threshold: float = 0.88):
        self.exact_hashes: Set[str] = set()
        self.jaccard_threshold = jaccard_threshold
        self.seen_signatures: Dict[str, Set[str]] = {}

    @staticmethod
    def compute_hash(text: str) -> str:
        """Computes SHA-256 hash of normalized text."""
        norm = re.sub(r"\s+", " ", text.lower().strip())
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    def is_exact_duplicate(self, text: str) -> bool:
        """Returns True if the identical content hash has already been registered."""
        h = self.compute_hash(text)
        if h in self.exact_hashes:
            return True
        self.exact_hashes.add(h)
        return False

    @staticmethod
    def _get_shingles(text: str, k: int = 3) -> Set[str]:
        words = re.findall(r"\w+", text.lower())
        if len(words) < k:
            return set(words)
        return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}

    def is_near_duplicate(self, chunk_id: str, text: str) -> Tuple[bool, Optional[str]]:
        """
        Calculates Jaccard overlap of word 3-grams against existing chunks in the same document.
        Returns (is_duplicate, duplicate_of_chunk_id).
        """
        shingles = self._get_shingles(text)
        if not shingles:
            return False, None

        for prev_id, prev_shingles in self.seen_signatures.items():
            intersection = len(shingles & prev_shingles)
            union = len(shingles | prev_shingles)
            if union > 0 and (intersection / union) >= self.jaccard_threshold:
                return True, prev_id

        self.seen_signatures[chunk_id] = shingles
        return False, None


class QualityValidator:
    """Verifies document and chunk quality, rejecting corrupt or uninformative content."""

    @staticmethod
    def validate_document(text: str, file_name: str, min_chars: int = 50) -> Tuple[bool, str]:
        """Validates that extracted document text is non-trivial and uncorrupted."""
        if not text or not text.strip():
            return False, f"Empty document: {file_name}"

        clean_text = text.strip()
        if len(clean_text) < min_chars:
            return False, f"Document below minimum size threshold ({len(clean_text)} < {min_chars} chars): {file_name}"

        # Detect binary corruption (high ratio of null bytes or non-printable characters)
        printable_count = sum(1 for c in clean_text if c.isprintable() or c in "\n\t")
        printable_ratio = printable_count / len(clean_text)
        if printable_ratio < 0.85:
            return False, f"Binary or encoding corruption detected ({printable_ratio:.1%} printable): {file_name}"

        return True, "Valid"

    @staticmethod
    def validate_chunk(text: str, min_words: int = 8) -> Tuple[bool, str]:
        """Validates that a chunk contains meaningful explanatory information."""
        words = text.split()
        if len(words) < min_words:
            return False, f"Chunk too short ({len(words)} words)"
        # Check if chunk consists solely of numbers, punctuation, or repetitive symbols
        alphanumeric = sum(1 for c in text if c.isalnum())
        if alphanumeric < 10:
            return False, "Insufficient alphanumeric density"
        return True, "Valid"

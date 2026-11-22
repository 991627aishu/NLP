"""
AyurMitra — Configurable Semantic & Multi-Strategy Chunker
==========================================================
Provides multiple evaluated chunking strategies:
1. Fixed-size chunking (with token/word overlap)
2. Recursive text splitting (hierarchical paragraph -> sentence -> phrase)
3. Semantic section-aware chunking (preserves Markdown headers, chapters, sections, table blocks)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class DocumentChunk:
    """Represents an atomic indexed passage with rich provenance metadata."""
    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        text: str,
        source_name: str,
        source_type: str,
        page_number: Optional[int] = None,
        section_heading: Optional[str] = None,
        language: str = "en",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.text = text.strip()
        self.source_name = source_name
        self.source_type = source_type
        self.page_number = page_number
        self.section_heading = section_heading or "General"
        self.language = language
        self.metadata = metadata or {}
        self.word_count = len(self.text.split())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "text": self.text,
            "source_id": self.document_id,
            "title": self.source_name,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "page_number": self.page_number,
            "locator": f"page {self.page_number}" if self.page_number else self.section_heading,
            "section_heading": self.section_heading,
            "language": self.language,
            "word_count": self.word_count,
            "metadata": self.metadata,
        }


class BaseChunker:
    """Abstract chunker interface."""
    def chunk(self, text: str, document_id: str, source_name: str, source_type: str,
              page_number: Optional[int] = None, language: str = "en",
              extra_meta: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
        raise NotImplementedError


class FixedSizeChunker(BaseChunker):
    """Chunks text into fixed word windows with configurable overlap."""
    def __init__(self, chunk_size: int = 150, overlap: int = 30):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, document_id: str, source_name: str, source_type: str,
              page_number: Optional[int] = None, language: str = "en",
              extra_meta: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
        words = text.split()
        if not words:
            return []

        chunks: List[DocumentChunk] = []
        step = max(1, self.chunk_size - self.overlap)
        chunk_idx = 1

        for i in range(0, len(words), step):
            window = words[i : i + self.chunk_size]
            if not window:
                continue
            chunk_text = " ".join(window)
            cid = f"{document_id}_C{chunk_idx:04d}"
            chunks.append(DocumentChunk(
                chunk_id=cid,
                document_id=document_id,
                text=chunk_text,
                source_name=source_name,
                source_type=source_type,
                page_number=page_number,
                language=language,
                metadata=extra_meta,
            ))
            chunk_idx += 1
            if i + self.chunk_size >= len(words):
                break

        return chunks


class RecursiveChunker(BaseChunker):
    """Hierarchical text splitter evaluating paragraphs -> sentences -> clauses."""
    def __init__(self, target_size: int = 200, min_size: int = 50, max_size: int = 350):
        self.target_size = target_size
        self.min_size = min_size
        self.max_size = max_size

    def chunk(self, text: str, document_id: str, source_name: str, source_type: str,
              page_number: Optional[int] = None, language: str = "en",
              extra_meta: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        chunks: List[DocumentChunk] = []
        chunk_idx = 1
        current_words: List[str] = []

        def flush():
            nonlocal chunk_idx, current_words
            if current_words:
                chunk_text = " ".join(current_words)
                cid = f"{document_id}_C{chunk_idx:04d}"
                chunks.append(DocumentChunk(
                    chunk_id=cid,
                    document_id=document_id,
                    text=chunk_text,
                    source_name=source_name,
                    source_type=source_type,
                    page_number=page_number,
                    language=language,
                    metadata=extra_meta,
                ))
                chunk_idx += 1
                current_words = []

        for para in paragraphs:
            para_words = para.split()
            if len(current_words) + len(para_words) <= self.max_size:
                current_words.extend(para_words)
                if len(current_words) >= self.target_size:
                    flush()
            else:
                if current_words:
                    flush()
                if len(para_words) <= self.max_size:
                    current_words.extend(para_words)
                else:
                    # Break long paragraph by sentences
                    sentences = re.split(r"(?<=[.!?।॥])\s+", para)
                    for sent in sentences:
                        sw = sent.split()
                        if len(current_words) + len(sw) <= self.max_size:
                            current_words.extend(sw)
                        else:
                            flush()
                            current_words.extend(sw)
        flush()
        return chunks


class SemanticSectionChunker(BaseChunker):
    """
    Section-aware chunker that identifies structural headers (Markdown #, Chapter, Section),
    grouping complete conceptual topics together without splitting core definitions across chunks.
    """
    def __init__(self, max_words_per_section: int = 300, min_words: int = 30):
        self.max_words = max_words_per_section
        self.min_words = min_words

    def chunk(self, text: str, document_id: str, source_name: str, source_type: str,
              page_number: Optional[int] = None, language: str = "en",
              extra_meta: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
        # Detect sections via markdown headers or Chapter/Section keywords
        section_pattern = re.compile(r"(?:^|\n)(#{1,4}\s+[^\n]+|Chapter\s+\d+[^\n]*|Section\s+\d+[^\n]*)", re.IGNORECASE)
        splits = section_pattern.split(text)

        chunks: List[DocumentChunk] = []
        chunk_idx = 1
        current_heading = "Overview"

        i = 0
        while i < len(splits):
            part = splits[i].strip()
            if not part:
                i += 1
                continue

            if section_pattern.match(part):
                current_heading = part.lstrip("#").strip()
                i += 1
                section_body = splits[i].strip() if i < len(splits) else ""
            else:
                section_body = part

            words = section_body.split()
            if not words:
                i += 1
                continue

            if len(words) <= self.max_words:
                cid = f"{document_id}_S{chunk_idx:04d}"
                chunks.append(DocumentChunk(
                    chunk_id=cid,
                    document_id=document_id,
                    text=f"[{current_heading}] {section_body}",
                    source_name=source_name,
                    source_type=source_type,
                    page_number=page_number,
                    section_heading=current_heading,
                    language=language,
                    metadata=extra_meta,
                ))
                chunk_idx += 1
            else:
                # Sub-chunk long sections recursively
                step = self.max_words - 40
                for j in range(0, len(words), step):
                    window = words[j : j + self.max_words]
                    cid = f"{document_id}_S{chunk_idx:04d}"
                    sub_text = f"[{current_heading}] " + " ".join(window)
                    chunks.append(DocumentChunk(
                        chunk_id=cid,
                        document_id=document_id,
                        text=sub_text,
                        source_name=source_name,
                        source_type=source_type,
                        page_number=page_number,
                        section_heading=current_heading,
                        language=language,
                        metadata=extra_meta,
                    ))
                    chunk_idx += 1
                    if j + self.max_words >= len(words):
                        break

            i += 1

        return chunks

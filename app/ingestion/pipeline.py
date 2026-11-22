"""
AyurMitra — Production Enterprise Data Ingestion Pipeline
=========================================================
End-to-end ingestion orchestrator for enterprise multi-format documents:
Discovery -> Validation -> Extraction -> Language ID -> Terminology Tagging ->
Chunking -> Deduplication -> Versioned JSONL Storage -> Audit Reporting.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.language_detect import detect
from app.core.matcher import TerminologyMatcher
from app.ingestion.chunker import (
    BaseChunker,
    DocumentChunk,
    FixedSizeChunker,
    RecursiveChunker,
    SemanticSectionChunker,
)
from app.ingestion.deduplicator import ContentDeduplicator, QualityValidator
from app.ingestion.extractor import MultiFormatExtractor

log = logging.getLogger("ayurmitra.ingestion.pipeline")


class EnterpriseIngestionPipeline:
    """Enterprise-grade ingestion orchestrator supporting diverse document corpora."""

    def __init__(
        self,
        chunker: Optional[BaseChunker] = None,
        ingestion_version: str = "v3.0",
        dedup_threshold: float = 0.88,
    ):
        self.chunker = chunker or SemanticSectionChunker()
        self.ingestion_version = ingestion_version
        self.deduplicator = ContentDeduplicator(jaccard_threshold=dedup_threshold)
        self.matcher = TerminologyMatcher()
        self.stats: Dict[str, Any] = {
            "version": ingestion_version,
            "start_time": None,
            "end_time": None,
            "duration_sec": 0,
            "files_discovered": 0,
            "files_processed": 0,
            "files_rejected": 0,
            "rejections": [],
            "total_extracted_chars": 0,
            "total_chunks_generated": 0,
            "duplicates_removed": 0,
            "valid_chunks_indexed": 0,
            "languages": {},
            "categories": {},
            "format_breakdown": {},
        }

    def process_directory(
        self,
        input_dir: Path,
        output_jsonl: Path,
        incremental: bool = False,
        default_category: str = "Medical/Ayurveda",
    ) -> Dict[str, Any]:
        """
        Scans input_dir for all supported document formats, runs full pipeline,
        and writes versioned chunks to output_jsonl.
        """
        input_path = Path(input_dir)
        output_path = Path(output_jsonl)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.stats["start_time"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        t0 = time.time()

        if not input_path.exists():
            raise FileNotFoundError(f"Input directory does not exist: {input_path}")

        supported_exts = {
            ".pdf", ".docx", ".xlsx", ".xls", ".csv", ".tsv",
            ".json", ".jsonl", ".html", ".htm", ".txt", ".md"
        }
        all_files = [p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() in supported_exts]
        self.stats["files_discovered"] = len(all_files)
        log.info("Discovered %d documents in %s", len(all_files), input_path)

        indexed_chunks: List[Dict[str, Any]] = []

        # If incremental, load existing chunks to prevent duplicates
        if incremental and output_path.exists():
            log.info("Loading existing chunks for incremental deduplication: %s", output_path)
            with open(output_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        existing = json.loads(line)
                        self.deduplicator.is_exact_duplicate(existing.get("text", ""))
                        indexed_chunks.append(existing)

        for file_path in all_files:
            fmt = file_path.suffix.lower().lstrip(".")
            self.stats["format_breakdown"][fmt] = self.stats["format_breakdown"].get(fmt, 0) + 1

            # 1. Extraction
            try:
                doc_data = MultiFormatExtractor.extract(file_path)
            except Exception as e:
                self.stats["files_rejected"] += 1
                self.stats["rejections"].append({"file": file_path.name, "reason": str(e)})
                log.warning("Rejected unreadable/corrupted file %s: %s", file_path.name, e)
                continue

            full_text = doc_data.get("text", "")

            # 2. Document Quality Validation
            is_valid, reason = QualityValidator.validate_document(full_text, file_path.name)
            if not is_valid:
                self.stats["files_rejected"] += 1
                self.stats["rejections"].append({"file": file_path.name, "reason": reason})
                log.warning("Rejected low-quality document %s: %s", file_path.name, reason)
                continue

            self.stats["files_processed"] += 1
            self.stats["total_extracted_chars"] += len(full_text)

            doc_id = f"DOC_{file_path.stem[:24].upper()}"
            source_name = file_path.name

            # 3. Process Pages & Generate Chunks
            pages = doc_data.get("pages", [])
            for page_info in pages:
                p_text = page_info.get("text", "")
                p_num = page_info.get("page_num")

                # Detect language of passage
                lang_info = detect(p_text)
                lang_code = lang_info.get("language", "en") if isinstance(lang_info, dict) else "en"
                self.stats["languages"][lang_code] = self.stats["languages"].get(lang_code, 0) + 1

                # Chunking
                raw_chunks = self.chunker.chunk(
                    text=p_text,
                    document_id=doc_id,
                    source_name=source_name,
                    source_type=fmt,
                    page_number=p_num,
                    language=lang_code,
                    extra_meta=doc_data.get("metadata", {}),
                )
                self.stats["total_chunks_generated"] += len(raw_chunks)

                for chunk in raw_chunks:
                    # 4. Chunk Quality Validation
                    c_valid, c_reason = QualityValidator.validate_chunk(chunk.text)
                    if not c_valid:
                        continue

                    # 5. Exact & Near Deduplication
                    if self.deduplicator.is_exact_duplicate(chunk.text):
                        self.stats["duplicates_removed"] += 1
                        continue

                    is_near_dup, dup_of = self.deduplicator.is_near_duplicate(chunk.chunk_id, chunk.text)
                    if is_near_dup:
                        self.stats["duplicates_removed"] += 1
                        continue

                    # 6. Terminology Tagging
                    detected = self.matcher.find_terms(chunk.text)
                    term_ids = [d["canonical_term"] for d in detected]

                    # 7. Enrich Metadata
                    chunk_dict = chunk.to_dict()
                    chunk_dict.update({
                        "ingestion_version": self.ingestion_version,
                        "document_category": default_category,
                        "terminology_identifiers": term_ids,
                        "ingested_at": self.stats["start_time"],
                    })

                    indexed_chunks.append(chunk_dict)
                    self.stats["valid_chunks_indexed"] += 1

        # Write output JSONL
        with open(output_path, "w", encoding="utf-8") as f:
            for item in indexed_chunks:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        t1 = time.time()
        self.stats["end_time"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.stats["duration_sec"] = round(t1 - t0, 2)
        log.info(
            "Ingestion completed: %d files processed -> %d valid chunks indexed (%d duplicates purged) in %.2fs",
            self.stats["files_processed"],
            self.stats["valid_chunks_indexed"],
            self.stats["duplicates_removed"],
            self.stats["duration_sec"],
        )

        return self.stats

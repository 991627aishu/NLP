"""
AyurMitra — Reproducible Enterprise Ingestion Benchmark & Runner
================================================================
Executes multi-format ingestion, runs chunking strategies comparison,
tests deduplication and data quality validation, and writes audit reports.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ingestion.extractor import MultiFormatExtractor
from app.ingestion.chunker import (
    FixedSizeChunker,
    RecursiveChunker,
    SemanticSectionChunker,
)
from app.ingestion.deduplicator import ContentDeduplicator, QualityValidator
from app.ingestion.pipeline import EnterpriseIngestionPipeline


def run_benchmark():
    print("=" * 70)
    print("   AYURMITRA ENTERPRISE DATA INGESTION BENCHMARK & AUDIT")
    print("=" * 70)

    data_dir = ROOT / "data"
    test_docs_dir = data_dir / "ingestion_test_corpus"
    test_docs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create multi-format test documents to demonstrate comprehensive coverage
    print("\n[STEP 1] Generating multi-format test document corpus...")
    
    # Text document
    (test_docs_dir / "classical_principles.txt").write_text(
        "Ayurveda encompasses three fundamental doshas: Vata, Pitta, and Kapha. "
        "Vata governs movement, Pitta governs transformation and digestion, and Kapha governs structure. "
        "Equilibrium of doshas represents Swasthya (health), while imbalance produces Roga (disease).",
        encoding="utf-8"
    )

    # Markdown document with section headers
    (test_docs_dir / "clinical_methodology.md").write_text(
        "# Ayurvedic Diagnostic Methodology\n\n"
        "## Rogi Pariksha\n"
        "Examination of the patient involves Ashtavidha Pariksha: Nadi, Mutra, Mala, Jihva, Shabda, Sparsha, Druk, and Akruti.\n\n"
        "## Roga Pariksha\n"
        "Examination of the disease involves Nidana Panchaka: Nidana (etiology), Purvarupa (premonitory symptoms), "
        "Rupa (manifest clinical symptoms), Upashaya (exploratory therapy), and Samprapti (pathogenesis).\n\n"
        "## Chikitsa Sutra\n"
        "Therapeutic principles encompass Shodhana (purification) and Shamana (pacification).",
        encoding="utf-8"
    )

    # JSON document
    json_data = [
        {"concept": "Tridosha", "definition": "The three biological energies: Vata, Pitta, Kapha.", "source": "Charaka Samhita"},
        {"concept": "Agni", "definition": "The internal biological fire responsible for digestion and cellular metabolism.", "source": "Sushruta Samhita"},
        {"concept": "Ama", "definition": "Toxic, undigested metabolic byproduct that obstructs microchannels (Srotas).", "source": "Ashtanga Hridaya"}
    ]
    (test_docs_dir / "core_glossary.json").write_text(json.dumps(json_data, indent=2), encoding="utf-8")

    # CSV document
    csv_content = (
        "term_id,canonical_term,sanskrit_deva,kannada_script,category\n"
        "TERM_001,Vata,वात,ವಾತ,Dosha\n"
        "TERM_002,Pitta,पित्त,ಪಿತ್ತ,Dosha\n"
        "TERM_003,Kapha,कफ,ಕಫ,Dosha\n"
        "TERM_004,Agni,अग्नि,ಅಗ್ನಿ,Metabolic Principle\n"
        "TERM_005,Roga,रोग,ರೋಗ,Pathology\n"
    )
    (test_docs_dir / "canonical_lexicon.csv").write_text(csv_content, encoding="utf-8")

    # HTML document
    html_content = (
        "<!DOCTYPE html><html><head><title>Herbal Pharmacopoeia</title></head><body>"
        "<h1>Botanical Monographs</h1>"
        "<p>Ashwagandha (Withania somnifera) is classified as a Rasayana herb with Balya and Medhya properties.</p>"
        "<p>Amalaki (Phyllanthus emblica) exhibits all rasas except lavana, providing potent Tridoshahara actions.</p>"
        "</body></html>"
    )
    (test_docs_dir / "pharmacopoeia.html").write_text(html_content, encoding="utf-8")

    # Test Corrupted / Empty Document Rejection
    (test_docs_dir / "empty_doc.txt").write_text("", encoding="utf-8")
    with open(test_docs_dir / "corrupted_binary.pdf", "wb") as f:
        f.write(b"\x00\x01\x02\x03\x04INVALID_BINARY_STREAM\xff\xfe\x00")

    print(f"  Created test files in {test_docs_dir}")

    # 2. Evaluate Multi-Format Extraction
    print("\n[STEP 2] Auditing Multi-Format Extractor across document types...")
    test_files = [
        test_docs_dir / "classical_principles.txt",
        test_docs_dir / "clinical_methodology.md",
        test_docs_dir / "core_glossary.json",
        test_docs_dir / "canonical_lexicon.csv",
        test_docs_dir / "pharmacopoeia.html",
        data_dir / "qa_cleaned.csv",
        data_dir / "ayu-sat-table-a.xlsx" if (data_dir / "ayu-sat-table-a.xlsx").exists() else None,
        data_dir / "9789240064935-eng.pdf" if (data_dir / "9789240064935-eng.pdf").exists() else None,
    ]
    test_files = [f for f in test_files if f and f.exists()]

    extraction_results = []
    for tf in test_files:
        t0 = time.time()
        res = MultiFormatExtractor.extract(tf)
        dur_ms = round((time.time() - t0) * 1000, 2)
        extraction_results.append({
            "file": tf.name,
            "format": res["format"],
            "char_count": len(res["text"]),
            "page_count": len(res["pages"]),
            "latency_ms": dur_ms,
            "status": "SUCCESS"
        })
        print(f"  Extracted: {tf.name:<32} | Format: {res['format']:<6} | Chars: {len(res['text']):<7} | Time: {dur_ms} ms")

    # 3. Evaluate Chunking Strategies Comparison
    print("\n[STEP 3] Comparing Chunking Strategies on Clinical Methodology...")
    sample_text = (test_docs_dir / "clinical_methodology.md").read_text(encoding="utf-8")

    fixed_chunker = FixedSizeChunker(chunk_size=40, overlap=10)
    recursive_chunker = RecursiveChunker(target_size=50, min_size=20, max_size=80)
    semantic_chunker = SemanticSectionChunker(max_words_per_section=60)

    fixed_chunks = fixed_chunker.chunk(sample_text, "DOC_FIX", "Clinical Methodology", "md")
    rec_chunks = recursive_chunker.chunk(sample_text, "DOC_REC", "Clinical Methodology", "md")
    sem_chunks = semantic_chunker.chunk(sample_text, "DOC_SEM", "Clinical Methodology", "md")

    chunking_comparison = {
        "fixed_size": {
            "chunk_count": len(fixed_chunks),
            "avg_words": sum(c.word_count for c in fixed_chunks) / max(1, len(fixed_chunks)),
            "preserves_sections": False,
        },
        "recursive": {
            "chunk_count": len(rec_chunks),
            "avg_words": sum(c.word_count for c in rec_chunks) / max(1, len(rec_chunks)),
            "preserves_sections": False,
        },
        "semantic_section": {
            "chunk_count": len(sem_chunks),
            "avg_words": sum(c.word_count for c in sem_chunks) / max(1, len(sem_chunks)),
            "preserves_sections": True,
            "section_headings": [c.section_heading for c in sem_chunks],
        }
    }

    print(f"  Fixed-Size Chunking:       {len(fixed_chunks)} chunks (Avg {chunking_comparison['fixed_size']['avg_words']:.1f} words)")
    print(f"  Recursive Chunking:        {len(rec_chunks)} chunks (Avg {chunking_comparison['recursive']['avg_words']:.1f} words)")
    print(f"  Semantic Section Chunking: {len(sem_chunks)} chunks (Avg {chunking_comparison['semantic_section']['avg_words']:.1f} words | Headings Preserved)")

    # 4. Run End-to-End Ingestion Pipeline
    print("\n[STEP 4] Executing Enterprise Ingestion Pipeline on Test Corpus...")
    output_v3 = data_dir / "processed" / "corpus_chunks_v3.jsonl"
    pipeline = EnterpriseIngestionPipeline(
        chunker=semantic_chunker,
        ingestion_version="v3.0-enterprise",
        dedup_threshold=0.85
    )

    stats = pipeline.process_directory(test_docs_dir, output_v3, incremental=False)

    print("\n[STEP 5] Ingestion Audit Statistics:")
    print(f"  Files Discovered:       {stats['files_discovered']}")
    print(f"  Files Processed:        {stats['files_processed']}")
    print(f"  Files Rejected:         {stats['files_rejected']} (Empty / Corrupt rejected as expected)")
    print(f"  Extracted Characters:   {stats['total_extracted_chars']}")
    print(f"  Total Raw Chunks:       {stats['total_chunks_generated']}")
    print(f"  Duplicates Purged:      {stats['duplicates_removed']}")
    print(f"  Valid Chunks Indexed:   {stats['valid_chunks_indexed']}")
    print(f"  Execution Time:         {stats['duration_sec']} s")

    audit_report = {
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "extractions": extraction_results,
        "chunking_comparison": chunking_comparison,
        "pipeline_statistics": stats,
    }

    eval_out = data_dir / "evaluation" / "ingestion_audit_results.json"
    eval_out.parent.mkdir(parents=True, exist_ok=True)
    with open(eval_out, "w", encoding="utf-8") as f:
        json.dump(audit_report, f, indent=2, ensure_ascii=False)
    print(f"\n  Ingestion audit report saved to: {eval_out}")

    return audit_report


if __name__ == "__main__":
    run_benchmark()

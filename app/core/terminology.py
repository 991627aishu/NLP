"""
AyurMitra — Terminology Inventory Builder
==========================================
Ingests the WHO PDF and NAMASTE XLSX to build a structured, source-backed
terminology inventory.

Output schema (one record per term):
    concept_id      – stable internal ID (e.g. "TERM_0001")
    canonical_term  – preferred form for the system
    source_term     – exact string found in the source
    language        – "en", "sa" (Sanskrit), or "romanized"
    aliases         – list of known alternative forms (only from sources)
    definition      – source-backed definition (short)
    definition_long – longer definition when available
    source_id       – document identifier
    source_locator  – page / row / table reference
    review_status   – "unreviewed" | "verified" | "ambiguous" | "excluded"
    ambiguity_note  – free-text note when term has multiple meanings
    native_review   – dict; filled by human reviewer for Hindi/Kannada aliases

All entries start as "unreviewed".  Native-speaker review is required before
promoting Hindi/Kannada aliases to "verified".
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import fitz  # PyMuPDF
    _FITZ_AVAILABLE = True
except ImportError:
    _FITZ_AVAILABLE = False

from app.config import (
    WHO_PDF, NAMASTE_XLSX, TERMINOLOGY_JSON, DATA_PROC
)

# ── Known core Ayurvedic terms (seed set for go/no-go probe) ─────────────────
# Sources: WHO terminology list (conceptual level); extended in build step.
SEED_TERMS: list[dict] = [
    # Doshas
    {"canonical_term": "Vata",  "aliases": ["vata", "vayu", "vāta"],
     "definition": "One of the three biological humors; governs movement, air/space",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Pitta", "aliases": ["pitta", "pittam", "pitta dosha"],
     "definition": "One of the three biological humors; governs digestion and metabolism",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Kapha", "aliases": ["kapha", "kaphah", "kapha dosha", "shleshma"],
     "definition": "One of the three biological humors; governs structure and lubrication",
     "source_id": "SEED", "source_locator": "seed_set"},
    # Core concepts
    {"canonical_term": "Agni",  "aliases": ["agni", "digestive fire", "jatharagni"],
     "definition": "Digestive and metabolic fire; central to Ayurvedic physiology",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Prakriti", "aliases": ["prakriti", "prakṛti", "ayurvedic constitution", "body type"],
     "definition": "Individual psychophysical constitution determined at birth",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Dhatu",  "aliases": ["dhatu", "dhātu", "dhatus"],
     "definition": "Seven basic body tissues in Ayurveda",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Dosha",  "aliases": ["dosha", "dosa", "doṣa", "doshas"],
     "definition": "Three biological humors: Vata, Pitta, Kapha",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Ojas",   "aliases": ["ojas", "vital essence"],
     "definition": "Vital essence produced from refined Dhatus; supports immunity",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Prana",  "aliases": ["prana", "prāṇa", "vital breath"],
     "definition": "Vital energy / life force associated with Vata",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Tridosha","aliases": ["tridosha", "three doshas", "tridoṣa"],
     "definition": "The collective triad of Vata, Pitta, and Kapha",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Ama",    "aliases": ["ama", "āma", "undigested matter", "ama toxin"],
     "definition": "Undigested metabolic waste; produced when Agni is impaired",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Rasayana","aliases": ["rasayana", "rasāyana", "rasayana therapy"],
     "definition": "Branch of Ayurveda concerned with rejuvenation and longevity",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Panchakarma","aliases": ["panchakarma", "pañcakarma", "panchakarma therapy"],
     "definition": "Five therapeutic purification/detoxification procedures",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Srotas", "aliases": ["srotas", "srotāṃsi", "body channels"],
     "definition": "Body channels through which Doshas and Dhatus circulate",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Nadi",   "aliases": ["nadi", "nāḍī", "nadi pulse"],
     "definition": "Channel or pulse in Ayurvedic physiology; also diagnostic pulse",
     "source_id": "SEED", "source_locator": "seed_set"},
    # Seven Dhatus
    {"canonical_term": "Rasa",   "aliases": ["rasa", "rasa dhatu"],
     "definition": "First Dhatu; plasma/lymph; carries nutrition throughout body",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Rakta",  "aliases": ["rakta", "rakta dhatu"],
     "definition": "Second Dhatu; blood tissue",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Mamsa",  "aliases": ["mamsa", "māṃsa", "mamsa dhatu"],
     "definition": "Third Dhatu; muscle tissue",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Meda",   "aliases": ["meda", "medas", "meda dhatu"],
     "definition": "Fourth Dhatu; adipose/fat tissue",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Asthi",  "aliases": ["asthi", "asthi dhatu"],
     "definition": "Fifth Dhatu; bone tissue",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Majja",  "aliases": ["majja", "bone marrow", "nerve tissue"],
     "definition": "Sixth Dhatu; bone marrow and nerve tissue",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Shukra", "aliases": ["shukra", "śukra", "reproductive tissue"],
     "definition": "Seventh Dhatu; reproductive tissue",
     "source_id": "SEED", "source_locator": "seed_set"},
    # Treatments / concepts
    {"canonical_term": "Vata Dosha", "aliases": ["vata imbalance", "vataj"],
     "definition": "Condition characterised by elevated or imbalanced Vata",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Pitta Dosha","aliases": ["pitta imbalance", "pittaj"],
     "definition": "Condition characterised by elevated or imbalanced Pitta",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Kapha Dosha","aliases": ["kapha imbalance", "kaphaj"],
     "definition": "Condition characterised by elevated or imbalanced Kapha",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Ashwagandha","aliases": ["ashwagandha", "aśvagandhā",
                                                  "withania somnifera", "indian ginseng"],
     "definition": "Adaptogenic herb used in Rasayana treatments",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Triphala",  "aliases": ["triphala", "triphalā", "three fruits"],
     "definition": "Traditional Ayurvedic formula of three fruits: Amalaki, Bibhitaki, Haritaki",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Tulsi",     "aliases": ["tulsi", "tulasī", "holy basil",
                                                  "ocimum tenuiflorum"],
     "definition": "Sacred plant used in Ayurveda for respiratory and immune conditions",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Neem",      "aliases": ["neem", "nimba", "azadirachta indica"],
     "definition": "Bitter herb used in Ayurveda for skin and blood purification",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Brahmi",    "aliases": ["brahmi", "brāhmī", "bacopa monnieri"],
     "definition": "Medhya Rasayana herb used in Ayurveda for memory, cognition, and nervous system support",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Shatavari", "aliases": ["shatavari", "śatāvarī", "asparagus racemosus"],
     "definition": "Rejuvenative Ayurvedic herb particularly nourishing for reproductive tissues",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Haritaki",  "aliases": ["haritaki", "harītakī", "terminalia chebula"],
     "definition": "One of the three fruits in Triphala; beneficial for digestive health and longevity",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Amalaki",   "aliases": ["amalaki", "āmalakī", "amla", "phyllanthus emblica"],
     "definition": "Indian gooseberry; rich in Rasayana properties and Vitamin C",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Bibhitaki", "aliases": ["bibhitaki", "vibhītaka", "terminalia bellirica"],
     "definition": "One of the three fruits in Triphala; supports respiratory and digestive health",
     "source_id": "SEED", "source_locator": "seed_set"},
    {"canonical_term": "Guggulu",   "aliases": ["guggulu", "guggul", "commiphora mukul"],
     "definition": "Ayurvedic resin used for joint and lipid metabolic balance",
     "source_id": "SEED", "source_locator": "seed_set"},
]


def _normalise(text: str) -> str:
    """Lower-case, strip accents, collapse whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower().strip())


def _build_from_namaste(xlsx_path: Path) -> list[dict]:
    """
    Extract terms from the NAMASTE xlsx (ayu-sat-table-a).
    Columns: Sr No., t_id, Code, parent_id, Word, Short Defination,
             Long Defination, reference.
    """
    records = []
    try:
        df = pd.read_excel(xlsx_path, sheet_name="ayu-sat-table-a")
    except Exception as e:
        print(f"[WARNING] Could not read NAMASTE xlsx: {e}")
        return records

    for idx, row in df.iterrows():
        term = str(row.get("Word", "")).strip()
        short_def = str(row.get("Short Defination", "")).strip()
        long_def  = str(row.get("Long Defination",  "")).strip()
        code      = str(row.get("Code", "")).strip()
        t_id      = row.get("t_id", "")

        if not term or term.lower() == "nan":
            continue

        records.append({
            "concept_id":      f"NAMASTE_{code}",
            "canonical_term":  term,
            "source_term":     term,
            "language":        "sa_romanized",   # Romanized Sanskrit
            "aliases":         [],
            "definition":      short_def if short_def != "nan" else "",
            "definition_long": long_def  if long_def  != "nan" else "",
            "source_id":       "NAMASTE_ayu-sat-table-a",
            "source_locator":  f"row_{t_id}_code_{code}",
            "review_status":   "unreviewed",
            "ambiguity_note":  "",
            "native_review":   {},
        })
    return records


def _build_from_who_pdf(pdf_path: Path) -> list[dict]:
    """
    Extract terminology from the WHO PDF.
    Strategy: find page sections that list terms with definitions.
    The WHO publication uses structured glossary-style pages.
    Returns raw extracted records (unreviewed).
    """
    records = []
    if not _FITZ_AVAILABLE:
        print("[WARNING] PyMuPDF not available; skipping WHO PDF extraction")
        return records
    if not pdf_path.exists():
        print(f"[WARNING] WHO PDF not found at {pdf_path}")
        return records

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        print(f"[WARNING] Could not open WHO PDF: {e}")
        return records

    # Pattern: capitalised term followed by definition text
    # The WHO document has a mix of Sanskrit/romanized terms with English defs
    term_pattern = re.compile(
        r"^([A-Z][a-zA-Zāīūṛṝḷḹēōṃḥñṅṇṭḍśṣ\-\s]{1,50})\s*[:\-—]\s*(.+)$",
        re.MULTILINE
    )

    page_count = len(doc)
    for page_num in range(page_count):
        try:
            page = doc[page_num]
            text = page.get_text()
        except Exception:
            continue

        for match in term_pattern.finditer(text):
            term_raw = match.group(1).strip()
            defn_raw = match.group(2).strip()
            # Filter: keep only plausible Ayurvedic terms (1–4 words)
            words = term_raw.split()
            if not (1 <= len(words) <= 4):
                continue
            # Skip very short or clearly non-term matches, English section artefacts and prefixes
            lower_term = term_raw.lower()
            disallowed = {"see", "note", "fig", "table", "box", "time", "deep", "five", "pre", "post", "bulk", "non", "ita"}
            if len(term_raw) < 3 or lower_term in disallowed:
                continue

            records.append({
                "concept_id":      f"WHO_p{page_num+1}_{_normalise(term_raw)[:20].replace(' ','_')}",
                "canonical_term":  term_raw,
                "source_term":     term_raw,
                "language":        "en_or_sa_romanized",
                "aliases":         [],
                "definition":      defn_raw[:500],
                "definition_long": "",
                "source_id":       "WHO_9789240064935",
                "source_locator":  f"page_{page_num+1}",
                "review_status":   "unreviewed",
                "ambiguity_note":  "",
                "native_review":   {},
            })

    doc.close()
    return records


def _merge_with_seeds(
    who_records: list[dict],
    namaste_records: list[dict],
) -> list[dict]:
    """
    Combine seed terms, NAMASTE, and WHO extractions.
    Seeds take priority (already have verified definitions).
    Deduplicate on canonical_term (case-insensitive).
    """
    inventory: dict[str, dict] = {}

    # Seeds first
    for i, seed in enumerate(SEED_TERMS):
        cid = f"TERM_{i+1:04d}"
        rec = {
            "concept_id":      cid,
            "canonical_term":  seed["canonical_term"],
            "source_term":     seed["canonical_term"],
            "language":        "en_or_sa_romanized",
            "aliases":         seed.get("aliases", []),
            "definition":      seed.get("definition", ""),
            "definition_long": "",
            "source_id":       seed.get("source_id", "SEED"),
            "source_locator":  seed.get("source_locator", "seed_set"),
            "review_status":   "unreviewed",
            "ambiguity_note":  seed.get("ambiguity_note", ""),
            "native_review":   {},
        }
        key = _normalise(rec["canonical_term"])
        inventory[key] = rec

    # NAMASTE
    for rec in namaste_records:
        key = _normalise(rec["canonical_term"])
        if key not in inventory:
            inventory[key] = rec

    # WHO
    for rec in who_records:
        key = _normalise(rec["canonical_term"])
        if key not in inventory:
            inventory[key] = rec

    return list(inventory.values())


def build_terminology_inventory(
    force_rebuild: bool = False,
) -> list[dict]:
    """
    Build and save the terminology inventory.
    If the output file already exists, return the cached version
    unless force_rebuild=True.
    """
    DATA_PROC.mkdir(parents=True, exist_ok=True)

    if TERMINOLOGY_JSON.exists() and not force_rebuild:
        with open(TERMINOLOGY_JSON, encoding="utf-8") as f:
            inventory = json.load(f)
        print(f"[INFO] Loaded terminology inventory: {len(inventory)} terms")
        return inventory

    print("[INFO] Building terminology inventory from sources …")
    namaste_records = _build_from_namaste(NAMASTE_XLSX)
    who_records     = _build_from_who_pdf(WHO_PDF)
    inventory       = _merge_with_seeds(who_records, namaste_records)

    with open(TERMINOLOGY_JSON, "w", encoding="utf-8") as f:
        json.dump(inventory, f, ensure_ascii=False, indent=2)

    print(f"[INFO] Saved terminology inventory: {len(inventory)} terms")
    print(f"       Seeds:   {len(SEED_TERMS)}")
    print(f"       NAMASTE: {len(namaste_records)}")
    print(f"       WHO:     {len(who_records)}")
    return inventory


def get_all_aliases(inventory: list[dict]) -> dict[str, str]:
    """
    Return a flat dict: lowercase_alias → canonical_term.
    Used by the term-matcher at query time.
    """
    alias_map: dict[str, str] = {}
    for rec in inventory:
        canon = rec["canonical_term"]
        # Map canonical form itself
        alias_map[_normalise(canon)] = canon
        # Map all aliases
        for alias in rec.get("aliases", []):
            alias_map[_normalise(alias)] = canon
    return alias_map


if __name__ == "__main__":
    inv = build_terminology_inventory(force_rebuild=True)
    alias_map = get_all_aliases(inv)
    print(f"Alias map size: {len(alias_map)}")
    # Sample
    for k, v in list(alias_map.items())[:10]:
        print(f"  '{k}' -> '{v}'")


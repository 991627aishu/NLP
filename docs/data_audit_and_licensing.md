# AyurMitra — Data Audit & Licensing Register

This document audits the eight workspace datasets located in `Data/`, recording verified file metadata, record counts, schemas, and licence terms.

---

## 1. Dataset Inventory & Schema Verification

| Dataset File | Format | File Size | Verified Record Count | Primary Fields / Schema | Source / Licence Status |
|---|---|---|---|---|---|
| `9789240064935-eng.pdf` | PDF | 4.63 MB | 118 content pages / 128 chunks extracted | WHO standard Ayurveda terminology glossary; English definitions, Sanskrit transliterations | World Health Organization (2022); CC BY-NC-SA 3.0 IGO (Non-commercial educational use) |
| `ayu-sat-table-a.xlsx` | Excel (.xlsx) | 100.8 KB | 319 records | `t_id`, `Code`, `parent_id`, `Word`, `Short Defination`, `Long Defination`, `reference` | National AYUSH Morbidity and Standardized Terminologies Electronic Portal (NAMASTE), Ministry of AYUSH |
| `hi.parquet` | Parquet | 4.72 MB | 14,963 records | `id`, `question`, `option_a..d`, `correct_answer`, `topic`, `question_translated`, `question_backtranslated`, `translation_quality_metrics` | BhashaBench Ayurveda parallel QA dataset (Hindi) |
| `kn.parquet` | Parquet | 4.79 MB | 14,963 records | Same 25-column schema as `hi.parquet` with Kannada translation and backtranslation | BhashaBench Ayurveda parallel QA dataset (Kannada) |
| `IMPPAT_SingleHerbalFormulations.tsv` | TSV | 303.8 KB | 541 records | `Formulation_identifier`, `Formulation_name_in_API_original`, `Ingredient_name_standardised`, `Plant_part_standardised`, `Therapeutic_uses_standardised`, `References` | The Ayurvedic Pharmacopoeia of India (API) via IMPPAT 2.0 |
| `IMPPAT_TherapeuticUse_Plant_Association.tsv` | TSV | 7.36 MB | 94,261 records | `IMPPAT_Plant_identifier`, `Indian_Medicinal_plant`, `Plant_part`, `IMPPAT_Therapeutic_use_identifier`, `Therapeutic_use` | IMPPAT 2.0 (Computational Biology Group, IMSc Chennai) |
| `Plant_Information_IMPPAT.tsv` | TSV | 541.1 KB | 4,154 records | `Plant_identifier`, `Indian_Medicinal_plant`, `Synonymous names`, `Kingdom`, `Family`, `Common_name`, `System_of_Medicine` | IMPPAT 2.0 (IMSc Chennai) |
| `qa_cleaned.csv` | CSV | 15.08 MB | 82,285 records | `Question`, `Answer` | Ayurvedic literature QA archive (Dr. Vaidya Mana Bajracharya) |

---

## 2. Licensing Gates & Attribution Rules

1. **AYUSH / NAMASTE & API Guidelines:**
   - Reproduction of full guideline text requires explicit Ministry permission.
   - AyurMitra extracts only structured concept codes and definitions for citation locators.
2. **IMPPAT 2.0:**
   - Used for plant taxonomy and traditional catalogued therapeutic uses.
   - Catalogued associations are treated strictly as historical/ethnopharmacological references, **not** clinical efficacy proof.
3. **Derived Data Separation:**
   - Raw data in `Data/` remains untouched and read-only.
   - Processed artifacts reside exclusively in `data/processed/` and `data/evaluation/`.


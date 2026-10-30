# AyurMitra Knowledge Graph Review & Provenance Report

**Date:** 2026-10-30  
**Graph Version:** v2 (`Data/processed/knowledge_graph_v2.pkl`)  
**Nodes:** 9,530  
**Edges:** 72,341 (99.93% source-extracted with verifiable locators)  
**Status:** Audit & Human-Review Readiness Register

---

## 1. Provenance & Edge Status Distribution

Every edge in Knowledge Graph v2 carries `source_id`, `locator`, `review_status`, and `confidence`.

| Review Status | Edge Count | Meaning & Governance Rule |
|---|---|---|
| `extracted_from_source` | 72,288 | Directly extracted from a source row or table in IMPPAT 2.0, API, WHO, or NAMASTE. Locators specify exact rows or pages. |
| `auto_matched_by_code` | 37 | Deterministic string/alias match between a project concept and an authoritative WHO/NAMASTE node. Requires Ayurvedic domain review. |
| `grounded_by_code_text` | 4 | Legacy v1 relation confirmed to be explicitly stated in WHO definition text. |
| `project_mapping_unreviewed` | 10 | Heuristic symptom-to-dosha mappings for educational guidance. Carries explicit caution warning. |
| `unverified` | 2 | Legacy v1 assertions whose claimed source locators failed verification upon audit. Retained with low confidence (0.2) for transparency. |

---

## 2. Review of the 10 Educational Symptom-to-Dosha Mappings

In classical Ayurveda, symptoms are not mapped 1-to-1 algorithmically to a single dosha in isolation without comprehensive patient assessment (Darshana, Sparshana, Prashna). These mappings serve strictly as **educational lifestyle heuristics**, not diagnostic facts.

| # | Symptom Concept | Associated Dosha | Traditional Guna / Principle | Claimed Locator Status | Expert Review & Safety Note |
|---|---|---|---|---|---|
| 1 | `dry_skin` | Vata | Ruksha (dry) guna elevation | WHO p.45 (unverified) | Educational correlation only. Severe sudden dry lesions require dermatological clinical assessment. |
| 2 | `joint_pain_stiffness` | Vata | Shula (pain) & Stambha in Sandhi | WHO p.46 (unverified) | Common Vata sign; must be screened for acute inflammatory arthritis or fracture red flags. |
| 3 | `constipation` | Vata | Apana Vata dryness in Pakwashaya | WHO p.47 (unverified) | Functional sluggishness vs acute bowel obstruction red flag. |
| 4 | `insomnia_restlessness` | Vata | Chala (mobile) & Laghu (light) gunas | WHO p.48 (unverified) | Mild sleep hygiene correlation vs acute psychiatric or neurological crisis. |
| 5 | `burning_sensation` | Pitta | Ushna (hot) & Tikshna (sharp) gunas | WHO p.50 (unverified) | Classical Pitta hallmark; must rule out cardiac chest pain or severe infection. |
| 6 | `acid_reflux_heartburn` | Pitta | Amlapitta (elevated sour/hot Pitta) | WHO p.52 (unverified) | Classical Vidagdha Amla correlation; emergency gate blocks crushing chest pain. |
| 7 | `excessive_heat_sweating` | Pitta | Sweda & Ushna guna aggravation | WHO p.54 (unverified) | Thermoregulatory correlation vs systemic fever / sepsis. |
| 8 | `sluggish_digestion` | Kapha | Mandagni (suppressed digestive fire) | NAMASTE SAT-A.2 (unverified) | Heavy/oily Kapha excess slowing Agni. |
| 9 | `excessive_mucus_congestion`| Kapha | Picchila (slimy) & Guru (heavy) excess | WHO p.58 (unverified) | Classical Kaphaja respiratory sign; emergency gate blocks severe shortness of breath. |
| 10 | `heaviness_lethargy` | Kapha | Gaurava (heaviness) & Alasya | WHO p.60 (unverified) | Common Kapha aggravation vs clinical hypothyroidism or metabolic disorders. |

---

## 3. Review of the 10 Project-Mapped Concept Relationships

These 10 relationships connect the 10 symptom phrases (`SymptomPhrase` node type) to the three primary `Dosha` concepts in `knowledge_graph_v2.pkl`.

```
SYMPTOM:dry_skin                 --may_be_associated_with_dosha--> CONCEPT:Vata
SYMPTOM:joint_pain_stiffness     --may_be_associated_with_dosha--> CONCEPT:Vata
SYMPTOM:constipation             --may_be_associated_with_dosha--> CONCEPT:Vata
SYMPTOM:insomnia_restlessness    --may_be_associated_with_dosha--> CONCEPT:Vata
SYMPTOM:burning_sensation        --may_be_associated_with_dosha--> CONCEPT:Pitta
SYMPTOM:acid_reflux_heartburn    --may_be_associated_with_dosha--> CONCEPT:Pitta
SYMPTOM:excessive_heat_sweating  --may_be_associated_with_dosha--> CONCEPT:Pitta
SYMPTOM:sluggish_digestion       --may_be_associated_with_dosha--> CONCEPT:Kapha
SYMPTOM:excessive_mucus_congestion--may_be_associated_with_dosha--> CONCEPT:Kapha
SYMPTOM:heaviness_lethargy       --may_be_associated_with_dosha--> CONCEPT:Kapha
```

**Audit Verdict:**
- All 10 edges are directionally correct: `SymptomPhrase` → `may_be_associated_with_dosha` → `Dosha`.
- `review_status` is correctly set to `project_mapping_unreviewed`.
- `is_verified` is correctly set to `False`.
- `verification_status` is `"heuristic"`.
- Wording strictly uses `may_be_associated_with_dosha`, avoiding assertions of causation or diagnosis.

---

## 4. Investigation of the 2 Unverified Legacy v1 Relationships

During the Phase-0 audit (audit item F4), every relationship from the legacy 24-node graph was independently audited against the source documents. Two relationships failed locator verification:

### Unverified Edge 1: `Agni -optimal_nourishes-> Ojas`
- **Claimed Source:** `NAMASTE_ayu-sat-table-a Code SAT-A.4`
- **Audit Findings:** While classical Ayurvedic physiology (Charaka Samhita Sutrasthana 28) establishes that properly digested food through balanced Agni produces refined Dhatus culminating in Ojas, the specific spreadsheet record `SAT-A.4` in NAMASTE Table A does not state this relationship.
- **Action Taken:** Edge retained with `review_status = "unverified"`, confidence capped at `0.2`, and flagged in `v1_reverification` audit trail.

### Unverified Edge 2: `Ashwagandha -classified_under-> Rasayana`
- **Claimed Source:** `IMPPAT_2.0 TherapeuticUse_Plant_Association`
- **Audit Findings:** IMPPAT 2.0 catalogs therapeutic associations under `IMPPAT_Therapeutic_use_identifier` (e.g. `Rasayana` as therapeutic use `TU:432`), using the relationship `traditionally_used_for`. It does not define taxonomic classification via `classified_under`.
- **Action Taken:** Edge retained with `review_status = "unverified"`, confidence capped at `0.2`. Verified usage is captured separately through IMPPAT's row-grounded `traditionally_used_for` edge (`PLANT:110` → `TU:432`).

---

## 5. Query Expansion Analysis & Drift Mitigation

In retrieval configuration P2, the query is expanded with top graph neighbors.
- **Identified Defect:** Prior to the audit fix, `expansion_terms()` pulled section titles (`WHOSection`) and multi-meaning seed aliases (e.g. `Kapha` had `cough` in seed aliases), causing queries about Kapha to expand with `['Cough']`, which drifted retrieval toward cough remedies rather than constitutional dosha texts.
- **Corrected Rule:**
  1. `WHOSection` nodes are completely excluded from expansion terms.
  2. Generic English words (e.g. `box`, `time`, `deep`, `cough`, `fever`, `pain`) are filtered via `DISALLOWED_PLAIN_WORDS`.
  3. `Kapha` now expands cleanly to its Sanskrit IAST synonym: `['śleṣmā, kapha']`.
  4. `Vata` expands cleanly to: `['vātaḥ', 'prāṇaḥ', 'vāyuḥ']`.

---

## 6. Recommendations for Human Expert Review

1. **Native Review:** A qualified Ayurvedic physician (BAMS / MD Ayur) must inspect the 37 `auto_matched_by_code` links to confirm Sanskrit polysemies (e.g. distinguishing `Dhatu` as body tissue vs geological mineral).
2. **Promotion Gate:** An unreviewed edge must NOT be promoted to `verified` until cited against an exact Shloka locator in Charaka Samhita, Sushruta Samhita, or Ashtanga Hridaya.


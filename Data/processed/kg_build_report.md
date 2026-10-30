# Knowledge Graph v2 — build report

Built 2026-10-30 by `python -m app.core.kg_builder` (deterministic; 15.0 s).

## Size

- Nodes: **9,530**  ·  Edges: **72,341**
- Edges with a source row/page locator extracted by code: **99.93%**
- Edges without source_id: 0  ·  without locator: 12 (only project mappings / unverified v1 edges, by design)
- Isolated nodes: 74

## Node types

| Type | Count |
|---|---|
| Plant | 4,154 |
| WHOTerm | 2,973 |
| TherapeuticUse | 1,299 |
| Formulation | 541 |
| NAMASTETerm | 319 |
| WHOSection | 195 |
| Concept | 36 |
| SymptomPhrase | 10 |
| Dosha | 3 |

## Relations

| Relation | Count |
|---|---|
| traditionally_used_for | 68,401 |
| part_of | 3,352 |
| contains | 535 |
| described_in | 29 |
| may_be_associated_with_dosha | 10 |
| refers_to_plant | 8 |
| comprises | 3 |
| impaired_leads_to | 1 |
| optimal_nourishes | 1 |
| classified_under | 1 |

## Review status of edges

| Status | Count | Meaning |
|---|---|---|
| grounded_by_code_text | 4 | old v1 relation found stated in a WHO description; needs expert review |
| unverified | 2 | old v1 relation whose claimed locator failed verification |
| auto_matched_by_code | 37 | project concept ↔ source term by deterministic string match; needs expert review |
| extracted_from_source | 72,288 | relation is a row/column of the source file; locator points to it |
| project_mapping_unreviewed | 10 | project-written mapping, no source locator |

## Build log

```
{
 "concepts": 39,
 "namaste_terms": 319,
 "who_terms": 2973,
 "who_sections": 195,
 "who_engine": "pdfplumber",
 "plants": 4154,
 "therapeutic_use_rows": 94261,
 "plant_use_edges": 63737,
 "formulations": 541,
 "formulations_without_plant_match": 6,
 "concept_source_links": 37,
 "symptom_phrases": 10,
 "build_seconds": 15.0
}
```

## Re-verification of the original v1 graph (audit F4)

| v1 edge | Claimed locator | Verdict |
|---|---|---|
| Tridosha -comprises-> Vata | WHO_9789240064935 page 15 | grounded by code in WHO ITA-2.1.2, PDF p.51 (printed p.33) |
| Tridosha -comprises-> Pitta | WHO_9789240064935 page 15 | grounded by code in WHO ITA-2.1.2, PDF p.51 (printed p.33) |
| Tridosha -comprises-> Kapha | WHO_9789240064935 page 15 | grounded by code in WHO ITA-2.1.2, PDF p.51 (printed p.33) |
| Agni -impaired_leads_to-> Ama | NAMASTE_ayu-sat-table-a Code SAT-A.3 | grounded by code in WHO ITA-5.32.5, PDF p.217 (printed p.199) |
| Agni -optimal_nourishes-> Ojas | NAMASTE_ayu-sat-table-a Code SAT-A.4 | not found in WHO text → imported as unverified |
| Ashwagandha -classified_under-> Rasayana | IMPPAT_2.0 TherapeuticUse_Plant_Association | not found in WHO text → imported as unverified |
| Dry Skin -may_be_associated_with_dosha-> Vata | WHO_9789240064935 page 45 | symptom mapping → kept as project_mapping_unreviewed (see SymptomPhrase nodes) |
| Joint Stiffness -may_be_associated_with_dosha-> Vata | WHO_9789240064935 page 46 | symptom mapping → kept as project_mapping_unreviewed (see SymptomPhrase nodes) |
| Burning Sensation -may_be_associated_with_dosha-> Pitta | WHO_9789240064935 page 50 | symptom mapping → kept as project_mapping_unreviewed (see SymptomPhrase nodes) |
| Acid Reflux -may_be_associated_with_dosha-> Pitta | WHO_9789240064935 page 52 | symptom mapping → kept as project_mapping_unreviewed (see SymptomPhrase nodes) |
| Sluggish Digestion -may_be_associated_with_dosha-> Kapha | NAMASTE_ayu-sat-table-a Code SAT-A.2 | symptom mapping → kept as project_mapping_unreviewed (see SymptomPhrase nodes) |
| Excessive Mucus -may_be_associated_with_dosha-> Kapha | WHO_9789240064935 page 58 | symptom mapping → kept as project_mapping_unreviewed (see SymptomPhrase nodes) |

No edge in v2 says a plant or formulation *treats* or *cures* anything: IMPPAT/API rows are recorded as `traditionally_used_for`. Traditional records are not evidence of efficacy or safety.

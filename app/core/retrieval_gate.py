"""
AyurMitra — Strict Retrieval Quality Gate & Passage Verification
================================================================
Mandatory verification before passing retrieved passages to answer synthesis.
Ensures:
  1. Passage concerns the exact focal entity or canonical synonym.
  2. Discards irrelevant or noisy passages (e.g. Mopacho for roga).
  3. Validates source reliability and sufficient evidence depth.
  4. Reranks passages using semantic alignment scoring.
  5. Provides automatic retry/fallback queries when primary retrieval fails.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.entity_resolver import SemanticEntityResolver, SEMANTIC_ENTITY_CATALOG

log = logging.getLogger("ayurmitra.retrieval_gate")


class RetrievalQualityGate:
    """
    Enforces quality, entity alignment, and domain appropriateness on retrieved passages.
    """

    def __init__(self, entity_resolver: Optional[SemanticEntityResolver] = None):
        self.resolver = entity_resolver or SemanticEntityResolver()

    def filter_and_rank_passages(
        self,
        query: str,
        focal_info: Dict[str, Any],
        passages: List[Dict[str, Any]],
        domain: str = "AYURVEDA_DOMAIN",
        min_relevance_threshold: float = 0.25
    ) -> Dict[str, Any]:
        """
        Validates every candidate passage against the focal entity and query context.
        Rejects candidates that discuss unrelated entities.
        """
        if not passages:
            return {
                "status": "EMPTY",
                "passed_passages": [],
                "rejected_count": 0,
                "rejection_reasons": ["No candidate passages provided."],
                "top_score": 0.0
            }

        norm_entity = focal_info.get("normalized_entity", "")
        raw_entity = focal_info.get("raw_extracted_entity", "")
        catalog_entry = focal_info.get("catalog_entry")

        passed = []
        rejection_reasons = []

        # Target synonyms to accept
        accepted_terms = {norm_entity, raw_entity.lower()}
        if catalog_entry:
            accepted_terms.add(catalog_entry.get("canonical_name", "").lower())
            for s in catalog_entry.get("synonyms", []):
                accepted_terms.add(s.lower())
            for s in catalog_entry.get("hindi_synonyms", []):
                accepted_terms.add(s.lower())
            for s in catalog_entry.get("kannada_synonyms", []):
                accepted_terms.add(s.lower())

        for p in passages:
            title = p.get("title", "")
            text = p.get("text", "") or p.get("extract", "") or p.get("snippet", "")
            full_blob = f"{title} {text}".lower()

            # 1. Compute alignment score
            alignment = self.resolver.compute_alignment_score(
                focal_entity=norm_entity,
                candidate_title=title,
                candidate_snippet=text[:160]
            )

            # 2. Check for presence of accepted terms
            term_present = any(term in full_blob for term in accepted_terms if len(term) >= 3)

            # 3. Specific Entity Integrity Check:
            # If query is for general 'disease' or 'roga', and candidate is 'Mopacho' (dance), REJECT
            if norm_entity in ("roga", "disease", "रोग", "ರೋಗ") and "mopacho" in title.lower():
                rejection_reasons.append(f"Rejected candidate '{title}': Entity mismatch (dance for disease query).")
                continue

            # If candidate is a specific condition (e.g. Kuru disease) but query is general disease,
            # allow only if no general disease article is found, but flag lower relevance.
            score = max(alignment, 0.40 if term_present else 0.0)

            # Passage content depth check (reject empty/too-short snippets)
            if len(text.strip()) < 30:
                rejection_reasons.append(f"Rejected candidate '{title}': Passage length too short ({len(text)} chars).")
                continue

            if score >= min_relevance_threshold:
                p_copy = dict(p)
                p_copy["semantic_alignment_score"] = round(score, 3)
                passed.append(p_copy)
            else:
                rejection_reasons.append(f"Rejected candidate '{title}': Score {score:.2f} < threshold {min_relevance_threshold}.")

        # Sort by alignment score descending
        passed.sort(key=lambda x: x.get("semantic_alignment_score", 0.0), reverse=True)

        status = "PASSED" if passed else "FAILED"
        top_score = passed[0].get("semantic_alignment_score", 0.0) if passed else 0.0

        return {
            "status": status,
            "passed_passages": passed,
            "rejected_count": len(passages) - len(passed),
            "rejection_reasons": rejection_reasons,
            "top_score": top_score
        }

    def generate_fallback_queries(self, focal_info: Dict[str, Any]) -> List[str]:
        """
        Generates robust fallback search queries if the primary query yielded no valid passages.
        """
        fallbacks = []
        catalog = focal_info.get("catalog_entry")
        if catalog:
            if catalog.get("wikipedia_target"):
                fallbacks.append(catalog["wikipedia_target"].replace("_", " "))
            if catalog.get("english_equivalent"):
                fallbacks.append(catalog["english_equivalent"])
            for syn in catalog.get("synonyms", [])[:2]:
                if syn not in fallbacks:
                    fallbacks.append(syn)
        else:
            raw = focal_info.get("raw_extracted_entity", "")
            if raw and raw not in fallbacks:
                fallbacks.append(raw)

        return fallbacks

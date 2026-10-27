"""Application orchestration: language handling, evidence retrieval, and grounded answers."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import pandas as pd

from app.core import (
    PROCESSED,
    dataset_status,
    find_imppat_use_tables,
    load_columbia,
    load_imppat_tables,
    load_namaste_terms,
    load_who_chunks,
    score_conditions,
)
from app.language import detect_language, translator
from app.retrieval import hybrid_search
from app.rag import generate_grounded_answer
from app.nlp import (
    normalize_query_for_retrieval,
    check_emergency_symptoms,
    is_ambiguous_query,
    extract_herbs,
    extract_symptoms,
    extract_ayurvedic_concepts,
)
from app.classifier import classifier
from app.knowledge_graph import find_related_graph_entities


ENGLISH_INPUT = "English or romanized/code-mixed Latin input"

SOURCE_CATALOG = {
    "WHO Ayurveda terminology": "https://www.who.int/publications/i/item/9789240064935",
    "NAMASTE Standardized Ayurveda Terminologies": "https://namaste.ayush.gov.in/sat_Ayurveda",
    "IMPPAT 2.0": "https://cb.imsc.res.in/imppat/",
    "Columbia Disease–Symptom Knowledge Database": "https://people.dbmi.columbia.edu/~friedma/Projects/DiseaseSymptomKB/index.html",
    "AYUSH Research Portal": "https://arp.ayush.gov.in/",
}

CATEGORY_LABELS = {
    "general": "General Ayurveda",
    "herbs": "Ayurvedic herbs",
    "disease": "Symptoms & conditions",
}


def _source(name: str, url: str, detail: str = "") -> dict:
    return {"name": name, "url": url, "detail": detail}


def _normalize_text(value: Any) -> str:
    """Normalize text for case-insensitive exact/phrase matching."""
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _protect_terms(text: str, terms_df) -> tuple[str, dict[str, str]]:
    """Protect exact NAMASTE Latin-script terms while a query is translated."""
    if terms_df is None or terms_df.empty:
        return text, {}

    candidates = []
    for col in terms_df.columns:
        if any(k in str(col).lower() for k in ("word", "term", "name", "english")):
            candidates.extend(
                str(value).strip()
                for value in terms_df[col].dropna().tolist()
                if len(str(value).strip()) >= 3
            )

    replacements: dict[str, str] = {}
    result = text
    for term in sorted(set(candidates), key=len, reverse=True)[:5000]:
        if not re.search(r"[A-Za-z]", term):
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.I)
        if pattern.search(result):
            key = f"AYURMITRATERM{len(replacements)}X"
            result = pattern.sub(key, result)
            replacements[key] = term
    return result, replacements


def _restore_terms(text: str, replacements: dict[str, str]) -> str:
    for key, term in replacements.items():
        text = text.replace(key, term)
    return text


def _flatten_evidence() -> list[dict]:
    """Load local evidence records without discarding source rows."""
    records: list[dict] = []

    for chunk in load_who_chunks():
        page = chunk.get("page", "?")
        records.append({
            "id": f"WHO-P{page}-C{chunk.get('chunk_id', '?')}",
            "source_name": "WHO International Standard Terminologies on Ayurveda",
            "source_url": chunk.get("source_url") or SOURCE_CATALOG["WHO Ayurveda terminology"],
            "source_detail": f"Page {page}",
            "title": f"WHO Ayurveda terminology — page {page}",
            "text": str(chunk.get("text", "")),
            "type": "terminology",
            "page": page,
        })

    namaste = load_namaste_terms()
    if namaste is not None and not namaste.empty:
        for idx, row in namaste.iterrows():
            row_dict = row.to_dict()
            parts = [
                f"{key}: {value}"
                for key, value in row_dict.items()
                if str(value).strip() and str(key) != "source_sheet"
            ]
            title = next(
                (
                    str(value)
                    for key, value in row.items()
                    if any(token in str(key).lower() for token in ("word", "term", "name"))
                    and str(value).strip()
                ),
                "NAMASTE terminology record",
            )
            records.append({
                "id": f"NAMASTE-{idx + 1}",
                "source_name": "NAMASTE Standardized Ayurveda Terminologies",
                "source_url": SOURCE_CATALOG["NAMASTE Standardized Ayurveda Terminologies"],
                "source_detail": str(row.get("source_sheet", "")),
                "title": title,
                "text": "; ".join(parts),
                "type": "terminology",
            })

    tables = load_imppat_tables()
    for idx, row in enumerate(find_imppat_use_tables(tables)):
        aliases = row.get("plant_aliases", [])
        if isinstance(aliases, str):
            aliases_list = [aliases] if aliases.strip() else []
        elif isinstance(aliases, (list, tuple, set)):
            aliases_list = [
                str(alias).strip() for alias in aliases if str(alias).strip()
            ]
        else:
            aliases_list = []

        plant = str(row.get("plant", "") or "")
        therapeutic_use = str(row.get("therapeutic_use", "") or "")
        plant_part = str(row.get("plant_part", "") or "")
        references = str(row.get("references", "") or "")
        text = (
            f"Plant: {plant}; common names and synonyms: {', '.join(aliases_list)}; "
            f"therapeutic use: {therapeutic_use}; plant part: {plant_part}; "
            f"references: {references}"
        )
        record = dict(row)
        record.update({
            "id": f"IMPPAT-{idx + 1}",
            "source_name": "IMPPAT 2.0",
            "source_url": row.get("source_url") or SOURCE_CATALOG["IMPPAT 2.0"],
            "source_detail": row.get("source_file", ""),
            "title": plant or "Medicinal plant record",
            "text": text,
            "type": "plant_use",
            "plant": plant,
            "plant_aliases": aliases_list,
            "therapeutic_use": therapeutic_use,
            "plant_part": plant_part,
            "references": references,
        })
        records.append(record)

    # Only rows with a usable claim are included. The current register uses "claim";
    # older versions of the schema may use "claim_to_use".
    ayush_path = PROCESSED / "ayush_evidence_register.csv"
    if ayush_path.exists():
        try:
            ayush = pd.read_csv(ayush_path).fillna("")
            for idx, row in ayush.iterrows():
                claim = str(
                    row.get("claim", row.get("claim_to_use", ""))
                ).strip()
                title = str(row.get("title", "")).strip()
                if not claim or not title:
                    continue

                url = (
                    str(row.get("source_portal_url", "")).strip()
                    or SOURCE_CATALOG["AYUSH Research Portal"]
                )
                text = (
                    f"Title: {title}; authors: {row.get('authors', '')}; "
                    f"year: {row.get('year', '')}; study design: {row.get('study_design', '')}; "
                    f"claim recorded in register: {claim}; limitations: {row.get('limitations', '')}"
                )
                records.append({
                    "id": str(row.get("record_id", "")).strip() or f"AYUSH-{idx + 1}",
                    "source_name": "AYUSH Research Portal — evidence register",
                    "source_url": url,
                    "source_detail": (
                        f"{row.get('authors', '')} ({row.get('year', '')}); "
                        f"review status: {row.get('verified_by', 'not specified')}"
                    ),
                    "title": title,
                    "text": text,
                    "type": "reviewed_literature",
                })
        except (OSError, ValueError, pd.errors.ParserError):
            # An optional malformed register must not stop core search.
            pass

    return records


def _deduplicate_hits(hits: list[dict]) -> list[dict]:
    """Deduplicate exact source records, preserving separate use/part rows."""
    unique = []
    seen = set()
    for hit in hits:
        key = hit.get("id") or (
            hit.get("source_name"), hit.get("title"), hit.get("text")
        )
        if key not in seen:
            seen.add(key)
            unique.append(hit)
    return unique


def _plant_names(hit: dict) -> list[str]:
    names = [_normalize_text(hit.get("plant", hit.get("title", "")))]
    aliases = hit.get("plant_aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    if isinstance(aliases, (list, tuple, set)):
        names.extend(_normalize_text(alias) for alias in aliases if alias)
    return list(dict.fromkeys(name for name in names if name))


def _query_plant_matches(query: str, hit: dict) -> bool:
    """True when a full plant name or alias occurs as a phrase in the query."""
    normalized_query = f" {_normalize_text(query)} "
    return any(f" {name} " in normalized_query for name in _plant_names(hit))


def _query_use_terms(query: str, hits: list[dict]) -> set[str]:
    """Remove plant names and common question words across English, Kannada, Hindi, Telugu to isolate requested use terms."""
    terms = set(_normalize_text(query).split())
    stop_words = {
        "what", "is", "are", "the", "a", "an", "in", "of", "for", "to", "and",
        "does", "do", "mean", "tell", "me", "about", "how", "can", "i", "please",
        "explain", "use", "uses", "herb", "herbs", "plant", "plants", "ayurvedic",
        "ayurveda", "remedy", "remedies", "treatment", "treat", "with", "using",
        # Kannada / Kanglish:
        "enu", "yenu", "inda", "upayoga", "upayogagalu", "upayogam", "upayogalu",
        "upayogisi", "hege", "yavudu", "yavavu", "bagge", "nalli", "maaduvudu", "aguvudu",
        "tulisida", "tilisi", "helu", "heli", "mahit", "mahiti", "needi", "nanage", "nange",
        "ಏನು", "ಉಪಯೋಗ", "ಉಪಯೋಗಗಳು", "ಪ್ರಯೋಜನ", "ಪ್ರಯೋಜನಗಳು", "ಬಗ್ಗೆ", "ಹೇಗೆ", "ತಿಳಿಸಿ", "ತುಳಸಿಯ", "ತುಳಸಿ",
        # Hindi / Hinglish:
        "kya", "hai", "hain", "ke", "ki", "ka", "fayde", "fayda", "labh", "upayog", "upyog",
        "kaise", "hota", "hoti", "hote", "bare", "me", "batao", "bataiye", "karen", "kare",
        "kya-kya", "fayde-nuksan", "aur", "hota-hai", "mujhe",
        "क्या", "है", "हैं", "के", "की", "का", "फायदे", "फायदा", "लाभ", "उपयोग", "बारे", "में", "बताएं", "बताइए",
        # Telugu / Romanized Telugu:
        "emiti", "yemiti", "upayogalu", "upayogam", "prayojanam", "prayojanalu", "ela",
        "gurinchi", "lo", "enti", "cheyali", "unna", "unnadi", "cheppandi", "theliyacheyandi",
        "naaku", "naku", "mariyu",
        "ఏమిటి", "ఉపయోగాలు", "ఉపయోగం", "ప్రయోజనాలు", "గురించి", "ఎలా", "చెప్పండి", "తెలియజేయండి", "తులసి",
    }
    terms -= stop_words
    for hit in hits:
        for name in _plant_names(hit):
            terms -= set(_normalize_text(name).split())

    # Strip all botanical names and aliases from HERB_CROSS_REFERENCE
    from app.nlp import HERB_CROSS_REFERENCE
    for herb_data in HERB_CROSS_REFERENCE.values():
        terms -= set(_normalize_text(herb_data.get("botanical", "")).split())
        terms -= set(_normalize_text(herb_data.get("common", "")).split())
        terms -= set(_normalize_text(herb_data.get("sanskrit", "")).split())
        for alias in herb_data.get("aliases", []):
            terms -= set(_normalize_text(alias).split())
    return terms


def _rank_herb_hits(query: str, hits: list[dict]) -> list[dict]:
    """Order plant records by exact plant match and requested-use overlap."""
    use_terms = _query_use_terms(query, hits)
    query_norm = _normalize_text(query)
    ranked = []

    for index, hit in enumerate(hits):
        plant = _normalize_text(hit.get("plant", hit.get("title", "")))
        aliases = hit.get("plant_aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        alias_text = " ".join(_normalize_text(alias) for alias in aliases)
        use = _normalize_text(hit.get("therapeutic_use", ""))

        score = 0.0
        if _query_plant_matches(query, hit):
            score += 100.0
        use_tokens = set(use.split())
        score += 12.0 * len(use_tokens & use_terms)
        if use and use in query_norm:
            score += 20.0
        if plant and plant in query_norm:
            score += 5.0
        if any(token in alias_text.split() for token in use_terms):
            score += 1.0

        # This is an internal ordering score, not a retrieval similarity score.
        ranked.append((score, -index, hit))

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in ranked]


def _group_herb_hits(hits: list[dict]) -> list[dict]:
    """Group IMPPAT rows by plant and preserve any genuine retrieval score."""
    groups: dict[str, dict] = {}

    for hit in hits:
        plant = str(
            hit.get("plant", hit.get("title", "Medicinal plant record"))
            or "Medicinal plant record"
        ).strip()
        key = _normalize_text(plant) or plant.lower()

        if key not in groups:
            aliases = hit.get("plant_aliases", [])
            if isinstance(aliases, str):
                aliases = [aliases] if aliases.strip() else []
            elif not isinstance(aliases, (list, tuple, set)):
                aliases = []

            group = {
                "id": f"IMPPAT-GROUP-{key.replace(' ', '-')}",
                "source_name": hit.get("source_name", "IMPPAT 2.0"),
                "source_url": hit.get("source_url") or SOURCE_CATALOG["IMPPAT 2.0"],
                "source_detail": "Grouped from IMPPAT 2.0 plant-use association records",
                "title": plant,
                "plant": plant,
                "plant_aliases": list(aliases),
                "type": "plant_use_group",
                "grouped_uses": [],
                "source_record_count": 0,
                "references": [],
            }
            # Only add the field if the input actually has a numeric score.
            # Exact plant-name matches intentionally bypass hybrid_search, so they
            # should not be assigned a fabricated score of zero.
            try:
                score = float(hit["retrieval_score"])
                if score == score:  # reject NaN
                    group["retrieval_score"] = score
            except (KeyError, TypeError, ValueError):
                pass
            groups[key] = group

        group = groups[key]
        group["source_record_count"] += 1

        # Preserve the best genuine score from any row in the group.
        try:
            score = float(hit["retrieval_score"])
            if score == score:  # reject NaN
                group["retrieval_score"] = max(
                    group.get("retrieval_score", score), score
                )
        except (KeyError, TypeError, ValueError):
            pass

        use = str(hit.get("therapeutic_use", "") or "").strip()
        part = str(hit.get("plant_part", "") or "").strip()
        references = str(hit.get("references", "") or "").strip()
        use_key = (_normalize_text(use), _normalize_text(part))

        if not any(
            (
                _normalize_text(item.get("use", "")),
                _normalize_text(item.get("plant_part", "")),
            ) == use_key
            for item in group["grouped_uses"]
        ):
            group["grouped_uses"].append({"use": use, "plant_part": part})

        if references and references not in group["references"]:
            group["references"].append(references)

    results = list(groups.values())
    for group in results:
        aliases = ", ".join(
            dict.fromkeys(str(alias) for alias in group["plant_aliases"] if alias)
        )
        by_use: dict[str, list[str]] = defaultdict(list)
        for item in group["grouped_uses"]:
            use = item["use"] or "use not specified"
            part = item["plant_part"] or "plant part not specified"
            if part not in by_use[use]:
                by_use[use].append(part)

        use_lines = [
            f"- {use}: {', '.join(parts)}"
            for use, parts in sorted(by_use.items(), key=lambda pair: pair[0].lower())
        ]
        group["text"] = (
            f"Plant: {group['plant']}; common names and synonyms: {aliases}; "
            "recorded IMPPAT therapeutic-use associations:\n" + "\n".join(use_lines)
        )
        group["summary"] = (
            f"{group['plant']} has {len(by_use)} distinct recorded therapeutic-use label(s) "
            f"across {group['source_record_count']} source record(s)."
        )

    return results


def _build_condition_hits(search_query: str) -> list[dict]:
    """Retrieve Columbia clinical associations separately from herb evidence."""
    conditions = score_conditions(search_query, load_columbia(), top_k=8)
    hits = []

    for condition in conditions:
        name = str(condition.get("condition", condition.get("disease", "Unknown condition")))
        matched_symptoms = condition.get("matched_symptoms", []) or []
        score = condition.get("score", 0)
        source_code = condition.get("source_code", "")
        hits.append({
            "id": "COLUMBIA-" + str(source_code or name),
            "source_name": "Columbia Disease–Symptom Knowledge Database",
            "source_url": SOURCE_CATALOG["Columbia Disease–Symptom Knowledge Database"],
            "source_detail": "General clinical disease-symptom association; not Ayurveda-specific",
            "title": name,
            "text": (
                f"Condition association record: {name}; matching symptoms: "
                f"{', '.join(matched_symptoms)}. Text-overlap score {score}; "
                "not a probability or validated diagnostic prediction."
            ),
            "type": "symptom_association",
            "retrieval_score": score,
            "matched_symptoms": matched_symptoms,
            "coverage_pct": condition.get("coverage_pct", "N/A"),
            "explanation": condition.get("explanation", ""),
        })

    return _deduplicate_hits(hits)


def _herb_answer(query: str, hits: list[dict], target_lang: str = "English") -> tuple[str, str, list[int]]:
    """Create a concise answer from grouped IMPPAT associations rendered in the user's language."""
    if not hits:
        if target_lang == "Kannada":
            msg = "ಈ ಹುಡುಕಾಟಕ್ಕೆ ಸ್ಥಳೀಯ IMPPAT ಮೂಲಗಳಲ್ಲಿ ಸಸ್ಯ-ಬಳಕೆಯ ದಾಖಲೆಗಳು ಕಂಡುಬಂದಿಲ್ಲ. ಇದು ಸಸ್ಯಕ್ಕೆ ಸಾಂಪ್ರದಾಯಿಕ ಉಪಯೋಗಗಳಿಲ್ಲ ಎಂದು ಅರ್ಥವಲ್ಲ."
        elif target_lang == "Hindi":
            msg = "इस खोज के लिए स्थानीय IMPPAT स्रोतों में कोई औषधीय पौधा-उपयोग रिकॉर्ड नहीं मिला। इसका अर्थ यह नहीं है कि पौधे का कोई पारंपरिक उपयोग नहीं है।"
        elif target_lang == "Telugu":
            msg = "ఈ శోధనకు స్థానిక IMPPAT మూలాల్లో మొక్క-వినియోగ రికార్డులు కనుగొనబడలేదు. దీని అర్థం మొక్కకు ఎటువంటి సాంప్రదాయ ఉపయోగాలు లేవని కాదు."
        else:
            msg = "No matching plant-use record was found in the local IMPPAT evidence for this query. This does not establish that a plant has no traditional uses."
        return msg, "no matching herb evidence found", []

    use_terms = _query_use_terms(query, hits)
    query_mentions_use = bool(use_terms)
    answer_parts: list[str] = []
    citations: list[int] = []

    for index, hit in enumerate(hits[:3], start=1):
        plant = hit.get("plant", hit.get("title", "the plant"))
        uses = hit.get("grouped_uses", [])

        if query_mentions_use:
            matched = []
            for item in uses:
                use_norm = _normalize_text(item.get("use", ""))
                use_tokens = set(use_norm.split())
                if use_norm and (
                    use_tokens & use_terms
                    or any(term in use_norm for term in use_terms)
                ):
                    matched.append(item)

            if not matched:
                continue

            by_use: dict[str, list[str]] = defaultdict(list)
            for item in matched:
                use = str(item.get("use") or "use not specified").strip()
                part = str(item.get("plant_part") or "").strip()
                if part and part not in by_use[use]:
                    by_use[use].append(part)

            details = []
            for use, parts in sorted(by_use.items(), key=lambda pair: pair[0].lower()):
                specific_parts = [
                    part for part in parts
                    if _normalize_text(part) not in {
                        "plant part not specified", "not specified", "unknown", "n a", "na"
                    }
                ]
                shown_parts = specific_parts or parts
                if shown_parts:
                    label = "part listed" if len(shown_parts) == 1 else "parts listed"
                    details.append(f"{use} ({label}: {', '.join(shown_parts)})")
                else:
                    details.append(use)

            if details:
                if target_lang == "Kannada":
                    answer_parts.append(
                        f"IMPPAT ಮೂಲ ದಾಖಲೆಗಳಲ್ಲಿ {plant} ಗಾಗಿ ಈ ಕೆಳಗಿನ ಉಪಯೋಗಗಳು ದಾಖಲಾಗಿವೆ: " + "; ".join(details) + f" [E{index}]"
                    )
                elif target_lang == "Hindi":
                    answer_parts.append(
                        f"IMPPAT संदर्भों में {plant} के लिए निम्नलिखित उपयोग दर्ज हैं: " + "; ".join(details) + f" [E{index}]"
                    )
                elif target_lang == "Telugu":
                    answer_parts.append(
                        f"IMPPAT మూల రికార్డులలో {plant} కొరకు క్రింది ఉపయోగాలు నమోదు చేయబడ్డాయి: " + "; ".join(details) + f" [E{index}]"
                    )
                else:
                    answer_parts.append(
                        f"IMPPAT records for {plant} list " + "; ".join(details) + f" [E{index}]"
                    )
                citations.append(index)
        else:
            use_names = sorted(
                {
                    str(item.get("use") or "").strip()
                    for item in uses
                    if str(item.get("use") or "").strip()
                },
                key=str.lower,
            )
            examples = use_names[:5]
            if examples:
                if len(examples) == 1:
                    example_text = examples[0]
                else:
                    example_text = ", ".join(examples[:-1]) + f", and {examples[-1]}"

                if target_lang == "Kannada":
                    answer_parts.append(
                        f"IMPPAT 2.0 ಆಧಾರ ದಾಖಲೆಗಳಲ್ಲಿ {plant} ಗಾಗಿ {len(use_names)} ಸಾಂಪ್ರದಾಯಿಕ ಚಿಕಿತ್ಸಾ ಉಪಯೋಗಗಳು ಪಟ್ಟಿ ಮಾಡಲ್ಪಟ್ಟಿವೆ; ಉದಾಹರಣೆಗೆ: {example_text} [E{index}]"
                    )
                elif target_lang == "Hindi":
                    answer_parts.append(
                        f"IMPPAT 2.0 संदर्भों में {plant} के लिए {len(use_names)} पारंपरिक उपयोग सूचीबद्ध हैं; उदाहरण: {example_text} [E{index}]"
                    )
                elif target_lang == "Telugu":
                    answer_parts.append(
                        f"IMPPAT 2.0 రికార్డులలో {plant} కొరకు {len(use_names)} సాంప్రదాయ చికిత్సా ఉపయోగాలు నమోదు చేయబడ్డాయి; ఉదాహరణకు: {example_text} [E{index}]"
                    )
                else:
                    answer_parts.append(
                        f"IMPPAT 2.0 lists {len(use_names)} distinct therapeutic-use labels for "
                        f"{plant}; examples include {example_text} [E{index}]"
                    )
            else:
                answer_parts.append(
                    f"IMPPAT contains a plant-use record for {plant}, but no use labels were "
                    f"available in the retrieved record [E{index}]"
                )
            citations.append(index)

    if not answer_parts:
        return (
            "I found plant records, but no record clearly matched the requested use in the local evidence. "
            "Open the evidence records to inspect their listed associations.",
            "grounded abstention",
            [],
        )

    answer = ". ".join(answer_parts).rstrip(". ")
    if target_lang == "Kannada":
        answer += ". (ಗಮನಿಸಿ: ಇವು ಐತಿಹಾಸಿಕ ಸಾಹಿತ್ಯದಿಂದ ದಾಖಲಾದ ಸಾಂಪ್ರದಾಯಿಕ ಉಪಯೋಗಗಳಾಗಿದ್ದು, ಕ್ಲಿನಿಕಲ್ ಪರಿಣಾಮಕಾರಿತ್ವದ ಖಾತರಿಯಲ್ಲ.)"
    elif target_lang == "Hindi":
        answer += "। (नोट: ये ऐतिहासिक संदर्भों से दर्ज पारंपरिक उपयोग हैं, व्यक्तिगत चिकित्सीय नुस्खे का स्थान नहीं लेते।)"
    elif target_lang == "Telugu":
        answer += "। (గమనిక: ఇవి చారిత్రక ఆధారాల నుండి సేకరించిన సాంప్రదాయ ఉపయోగాలు మాత్రమే; వైద్య చికిత్సకు ప్రత్యామ్నాయం కాదు.)"
    else:
        answer += (
            ". These are source-listed associations, not proof of clinical effectiveness, safety, "
            "or suitability for an individual."
        )
    return answer, "extractive grounded herb lookup", citations


def search_project(query: str, category: str = "general", answer_mode: str = "ollama") -> dict:
    original = (query or "").strip()
    if not original:
        raise ValueError("Please enter a question or search term.")
    if len(original) > 2000:
        raise ValueError("Please keep the question under 2,000 characters.")
    if category not in {"general", "herbs", "disease"}:
        raise ValueError("Choose General Ayurveda, Ayurvedic herbs, or Symptoms & conditions.")

    lang = detect_language(original)
    search_query = original
    translation_note = ""
    terms = load_namaste_terms()
    protected, glossary = _protect_terms(original, terms)

    query_info = normalize_query_for_retrieval(original)
    emergency_warning = query_info.get("emergency_warning")
    is_ambiguous = query_info.get("is_ambiguous", False)
    clarification_prompt = query_info.get("clarification_prompt", "")
    detected_herbs = query_info.get("detected_herbs", [])
    detected_concepts = query_info.get("detected_concepts", [])
    detected_symptoms = query_info.get("detected_symptoms", [])

    if lang["name"].startswith("Possible romanized"):
        translation_note = (
            "Romanized language detection is heuristic. The query was analyzed and normalized for Ayurvedic concepts."
        )
        search_query = query_info.get("retrieval_query", original)
    elif lang["name"] == ENGLISH_INPUT:
        search_query = query_info.get("retrieval_query", original)
    else:
        # Native script (Kannada, Hindi, Telugu, etc.)
        canonical_rq = query_info.get("retrieval_query")
        if canonical_rq and (detected_herbs or detected_concepts or (detected_symptoms and category == "disease")):
            search_query = canonical_rq
            translation_note = (
                f"Domain-grounded terminology normalization mapped {lang['language']} concepts into canonical retrieval representation."
            )
        else:
            try:
                search_query = translator.translate(
                    protected, lang["code"] or "eng_Latn", "eng_Latn"
                )
                search_query = _restore_terms(search_query, glossary)
                translation_note = (
                    "Input was translated to English for retrieval; terminology placeholders "
                    "were restored before searching."
                )
            except Exception as exc:
                fallback_answer = (
                    "I received your question, but the configured app cannot translate this language yet. "
                    "No English-only search was run, to avoid misleading results."
                )
                if emergency_warning:
                    fallback_answer = f"🚨 **{emergency_warning}**\n\n{fallback_answer}"
                return {
                    "query": original,
                    "category": category,
                    "category_label": CATEGORY_LABELS[category],
                    "detected_language": lang["name"],
                    "language_detection": lang,
                    "translation_ready": False,
                    "translation_note": "",
                    "emergency_warning": emergency_warning,
                    "is_ambiguous": is_ambiguous,
                    "clarification_prompt": clarification_prompt,
                    "answer": fallback_answer,
                    "answer_mode": "translation unavailable",
                    "answer_language": "English",
                    "answer_citations": [],
                    "summary": emergency_warning or "Translation is not configured for this input.",
                    "sections": [],
                    "sources": [],
                    "dataset_status": dataset_status(),
                    "limitations": [
                        str(exc),
                        "Enable the IndicTrans2 setup described in docs/MULTILINGUAL_SETUP.md.",
                    ],
                    "xai_data": [],
                }

    all_evidence = _flatten_evidence()
    xai_data = []
    ml_pred = None

    intent = query_info.get("intent", "general")
    target_lang = lang.get("language", "English")

    # Intent-aware category auto-routing to prevent query-type mismatches
    effective_category = category
    routing_note = ""
    if intent == "herbs" and category in {"disease", "general"} and not detected_symptoms:
        effective_category = "herbs"
        routing_note = "Query identified as Ayurvedic herb inquiry; automatically routed to medicinal plant evidence records."
    elif intent == "disease" and category == "general" and detected_symptoms:
        effective_category = "disease"
        routing_note = "Query identified as symptom/condition inquiry; automatically routed to clinical association records."

    if effective_category == "general":
        evidence = [
            item for item in all_evidence
            if item.get("type") in {"terminology", "reviewed_literature"}
        ]
        hits = _deduplicate_hits(hybrid_search(search_query, evidence, top_k=8))[:8]
        rag_evidence = [{**hit, "summary": hit.get("text", "")} for hit in hits]
        rag = generate_grounded_answer(search_query, rag_evidence, "English", answer_mode)
        answer = rag["answer"]
        answer_mode_setting = rag.get("answer_mode", "grounded RAG")
        answer_citations = rag.get("citations", [])

    elif effective_category == "herbs":
        evidence = [item for item in all_evidence if item.get("type") == "plant_use"]

        # Exact plant/alias queries collect all matching source rows, including botanical cross references
        botanical_candidates = [h["botanical"] for h in detected_herbs]
        named_plant_hits = [
            item for item in evidence
            if _query_plant_matches(search_query, item)
            or any(_query_plant_matches(bot, item) for bot in botanical_candidates)
        ]
        if named_plant_hits:
            candidate_hits = named_plant_hits
        else:
            candidate_hits = hybrid_search(search_query, evidence, top_k=80)

        candidate_hits = _deduplicate_hits(candidate_hits)
        ranked_hits = _rank_herb_hits(search_query, candidate_hits)
        hits = _group_herb_hits(ranked_hits)[:8]
        answer, answer_mode_setting, answer_citations = _herb_answer(
            search_query, hits, target_lang=target_lang
        )

    else:
        hits = _build_condition_hits(search_query)[:8]
        answer_hits = [
            hit for hit in hits if hit.get("type") == "symptom_association"
        ]
        # Run ML model baseline
        try:
            ml_pred = classifier.predict(search_query)
        except Exception:
            ml_pred = {"abstain": True, "predictions": []}

        if answer_hits:
            # Structure the data for the frontend XAI
            xai_data = [
                {
                    "condition": hit["title"],
                    "matched_symptoms": hit.get("matched_symptoms", []),
                    "score": hit.get("retrieval_score", 0),
                    "coverage_pct": hit.get("coverage_pct", "N/A"),
                    "explanation": hit.get("explanation", ""),
                    "evidence_id": f"E{i}",
                }
                for i, hit in enumerate(answer_hits, start=1)
            ]

            matched_symptoms = list(dict.fromkeys(
                symptom
                for hit in answer_hits
                for symptom in hit.get("matched_symptoms", [])
                if symptom
            ))
            cited = "; ".join(
                f"{hit['title']} [E{i}]"
                for i, hit in enumerate(answer_hits, start=1)
            )
            symptom_text = ", ".join(matched_symptoms) or search_query

            if target_lang == "Kannada":
                answer = (
                    f"ಕೊಲಂಬಿಯಾ ರೋಗ-ಲಕ್ಷಣ ದತ್ತಾಂಶವು {symptom_text} ಲಕ್ಷಣಗಳಿಗಾಗಿ ಈ ಕೆಳಗಿನ ಸಂಭಾವ್ಯ ಹೊಂದಾಣಿಕೆಗಳನ್ನು ಪಟ್ಟಿ ಮಾಡಿದೆ: {cited}. "
                    "ಇವು ಅಂಕಿಅಂಶಗಳ ಹೊಂದಾಣಿಕೆಗಳಾಗಿದ್ದು, ವೈದ್ಯಕೀಯ ರೋಗನಿರ್ಣಯವಲ್ಲ. ಫಲಿತಾಂಶದ ಕ್ರಮವು ರೋಗದ ಸಾಧ್ಯತೆಯನ್ನು ಸೂಚಿಸುವುದಿಲ್ಲ."
                )
            elif target_lang == "Hindi":
                answer = (
                    f"कोलंबिया रोग-लक्षण डेटाबेस में {symptom_text} लक्षणों के लिए निम्नलिखित संभावित संबंध सूचीबद्ध हैं: {cited}। "
                    "ये डेटाबेस संबंध हैं, चिकित्सीय निदान या भविष्यवाणियां नहीं। परिणाम क्रम बीमारी की संभावना नहीं दर्शाता है।"
                )
            elif target_lang == "Telugu":
                answer = (
                    f"కొలంబియా వ్యాధి-లక్షణాల డేటాబేస్ {symptom_text} లక్షణాల కొరకు క్రింది సంబంధిత సమస్యలను సూచిస్తుంది: {cited}. "
                    "ఇవి కేవలం పరిశోధనా సంబంధాలు మాత్రమే, వైద్య నిర్ధారణ కాదు. క్రమం వ్యాధి సంభావ్యతను సూచించదు."
                )
            else:
                answer = (
                    "The Columbia Disease–Symptom Knowledge Database lists these condition associations "
                    f"for matched symptom(s) {symptom_text}: {cited}. These are database associations, "
                    "not diagnoses, probabilities, or validated predictions. The source can contain noisy or "
                    "unexpected matches, and the result order does not indicate how likely a condition is. "
                    "The database is not Ayurveda-specific."
                )
            normalized_query = _normalize_text(search_query)
            query_words = set(normalized_query.split())
            if "chest pain" in normalized_query or {"chest", "pain"}.issubset(query_words):
                if target_lang == "Kannada":
                    answer += " ಎದೆ ನೋವು ತೀವ್ರವಾಗಿದ್ದರೆ, ಉಸಿರಾಟದ ತೊಂದರೆ ಅಥವಾ ಕೈಗೆ ಹರಡುವ ನೋವು ಇದ್ದರೆ ತಕ್ಷಣ ತುರ್ತು ವೈದ್ಯಕೀಯ ನೆರವು ಪಡೆಯಿರಿ."
                elif target_lang == "Hindi":
                    answer += " यदि सीने में तेज दर्द, सांस लेने में कठिनाई या बांह में दर्द हो, तो तुरंत आपातकालीन चिकित्सा सहायता लें।"
                elif target_lang == "Telugu":
                    answer += " ఛాతీ నొప్పి తీవ్రంగా ఉంటే, శ్వాస తీసుకోవడంలో ఇబ్బంది లేదా చేయి లాగుతుంటే వెంటనే అత్యవసర వైద్య సంరక్షణ పొందండి."
                else:
                    answer += (
                        " If chest pain is severe, sudden, persistent, or occurs with breathlessness, "
                        "sweating, fainting, or pain spreading to the arm or jaw, seek emergency medical care."
                    )
            answer_mode_setting = "grounded clinical association lookup"
            answer_citations = list(range(1, len(answer_hits) + 1))
        else:
            if target_lang == "Kannada":
                answer = "ಈ ಪ್ರಶ್ನೆಗೆ ಸ್ಥಳೀಯ ಕ್ಲಿನಿಕಲ್ ಡೇಟಾಬೇಸ್‌ನಲ್ಲಿ ಹೊಂದಾಣಿಕೆಯಾಗುವ ಯಾವುದೇ ರೋಗಲಕ್ಷಣ ದಾಖಲೆಗಳು ಕಂಡುಬಂದಿಲ್ಲ."
            elif target_lang == "Hindi":
                answer = "इस प्रश्न के लिए स्थानीय नैदानिक डेटाबेस में कोई संबंधित लक्षण रिकॉर्ड नहीं मिला।"
            elif target_lang == "Telugu":
                answer = "ఈ ప్రశ్నకు స్థానిక క్లినికల్ డేటాబేస్‌లో సరిపోలే వ్యాధి-లక్షణ రికార్డులు కనుగొనబడలేదు."
            else:
                answer = (
                    "No matching condition association was found in the local clinical disease-symptom "
                    "lookup for this query. This does not rule out any medical condition."
                )
            answer_mode_setting = "no matching clinical association found"
            answer_citations = []

    answer_translation_status = target_lang
    if (
        lang["name"] != ENGLISH_INPUT
        and not lang["name"].startswith("Possible romanized")
        and translator.enabled
        and effective_category == "general"
    ):
        try:
            protected_answer, answer_glossary = _protect_terms(answer, terms)
            translated = translator.translate(
                protected_answer, "eng_Latn", lang["code"] or "eng_Latn"
            )
            answer = _restore_terms(translated, answer_glossary)
            answer_translation_status = lang["name"]
        except Exception as exc:
            answer_translation_status = f"{target_lang} direct rendering"

    sections = []
    sources = []
    grouped: dict[str, list[dict]] = {}

    for index, hit in enumerate(hits, start=1):
        name = hit.get("source_name", "Reference source")
        retrieval_score = hit.get("retrieval_score")
        if isinstance(retrieval_score, (int, float)) and retrieval_score == retrieval_score:
            detail = f"Evidence ID E{index} · retrieval score {retrieval_score:.3f}"
        elif hit.get("type") == "plant_use_group":
            detail = (
                f"Evidence ID E{index} · grouped from "
                f"{hit.get('source_record_count', 0)} IMPPAT source records; "
                "exact plant/alias match (no similarity score calculated)"
            )
        else:
            detail = f"Evidence ID E{index}"

        grouped.setdefault(name, []).append({
            "id": hit.get("id", f"E{index}"),
            "title": hit.get("title", "Source record"),
            "summary": str(hit.get("text", ""))[:1000],
            "detail": detail,
            "source": _source(
                name,
                hit.get("source_url") or SOURCE_CATALOG.get(
                    name, SOURCE_CATALOG["AYUSH Research Portal"]
                ),
                hit.get("source_detail", ""),
            ),
            "type": hit.get("type", "reference"),
        })
        source = _source(
            name,
            hit.get("source_url") or SOURCE_CATALOG.get(
                name, SOURCE_CATALOG["AYUSH Research Portal"]
            ),
            hit.get("source_detail", ""),
        )
        if not any(existing["name"] == name for existing in sources):
            sources.append(source)

    for name, items in grouped.items():
        sections.append({"title": name, "items": items})

    ready = dataset_status()
    limitations = [
        "AyurMitra is an academic research prototype, not an autonomous diagnostic instrument. A source association is not a probability or a personalized prescription.",
        "IMPPAT lists plant/use associations; these do not establish safety, clinical efficacy, dosage, or suitability for an individual.",
        "Columbia is a general clinical association dataset, not Ayurveda-specific. Missing local datasets cannot contribute evidence.",
    ]
    if translation_note:
        limitations.append(translation_note)

    # Prepend red-flag emergency triage if severe symptoms detected
    if emergency_warning:
        limitations.insert(0, emergency_warning)
        if "EMERGENCY" not in answer:
            answer = f"🚨 **{emergency_warning}**\n\n" + answer

    # Add query refinement suggestion if query was broad/ambiguous
    if is_ambiguous and clarification_prompt:
        limitations.append(f"Query Refinement: {clarification_prompt}")
        answer = f"💡 **Refinement Suggestion:** {clarification_prompt}\n\n" + answer

    # Retrieve related knowledge graph entities for XAI
    try:
        kg_entities = find_related_graph_entities(search_query, limit=5)
    except Exception:
        kg_entities = []

    return {
        "query": original,
        "category": effective_category,
        "category_label": CATEGORY_LABELS[effective_category],
        "intent": intent,
        "routing_note": routing_note,
        "search_query_english": search_query,
        "detected_language": lang["name"],
        "language_detection": lang,
        "translation_ready": translator.enabled,
        "translation_note": translation_note,
        "answer": answer,
        "answer_mode": answer_mode_setting,
        "answer_language": answer_translation_status,
        "answer_citations": answer_citations,
        "summary": (
            f"{CATEGORY_LABELS[category]}: retrieved {len(hits)} evidence record(s) from "
            f"{len(sections)} source collection(s). The answer uses only the local records shown below."
        ),
        "sections": sections,
        "sources": sources,
        "dataset_status": ready,
        "limitations": limitations,
        "xai_data": xai_data,
        "ml_classification": ml_pred,
        "knowledge_graph_entities": kg_entities,
        "detected_entities": {
            "herbs": [f"{h['sanskrit']} ({h['common']})" for h in detected_herbs],
            "concepts": [c["canonical"] for c in detected_concepts],
            "symptoms": detected_symptoms,
        },
        "emergency_warning": emergency_warning,
    }
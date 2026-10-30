"""
AyurMitra — WHO terminology table extractor (Phase 3)
=====================================================
Reads ``Data/9789240064935-eng.pdf`` (WHO International Standard Terminologies
on Ayurveda, 2022) and extracts every term row BY CODE, with the real page:

    {"term_id": "ITA-2.1.1", "english": "Dosha", "description": "...",
     "iast": "doṣaḥ", "section_id": "2.1", "section_title": "...",
     "pdf_page": 51, "printed_page": 33}

* ``pdf_page`` = 1-based physical page in the PDF file.
* ``printed_page`` = the page number printed in the footer, parsed per page when
  present (printed = physical − 18 for the body of this edition).
* The PDF's Devanagari column is NOT used: its font encoding extracts wrongly
  (e.g. त्रिदोषः comes out as "वरिदोषः"). Devanagari/Kannada forms are instead
  derived from the clean IAST column by deterministic transliteration.

Prefers PyMuPDF (``page.find_tables``); falls back to pdfplumber. Output is
cached to ``Data/processed/who_terms.json``.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import WHO_PDF, DATA_PROC
from app.pipeline.index_cache import file_sha256

log = logging.getLogger("ayurmitra.who")
WHO_TERMS_JSON = DATA_PROC / "who_terms.json"
TERM_ID_RX = re.compile(r"^ITA-\d+(\.\d+)+$")
SECTION_RX = re.compile(r"^\d+(\.\d+)*$")
FOOTER_RX = re.compile(r"(?:^|\n)\s*(?:[A-Z][A-Za-z ,\-()]+\s)?(\d{1,3})\s*(?:\nChapter\s*\n?\d+)?\s*$")


def _clean(cell: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (cell or "")).strip()


def _printed_page(text: str) -> Optional[int]:
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    for l in lines[-4:] + lines[:2]:
        m = re.match(r"^(?:WHO international standard terminologies on Ayurveda\s+)?(\d{1,3})$", l) or \
            re.match(r"^[A-Z][A-Za-z ,\-()]{3,80}\s(\d{1,3})$", l)
        if m:
            return int(m.group(1))
    return None


def _tables_pymupdf(path: Path):
    import fitz  # type: ignore
    doc = fitz.open(path)
    for i, page in enumerate(doc):
        text = page.get_text()
        if "ITA-" not in text:
            continue
        rows = []
        for t in page.find_tables().tables:
            rows.extend(t.extract())
        yield i + 1, text, rows


def _tables_pdfplumber(path: Path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if "ITA-" not in text:
                continue
            rows = []
            for t in page.extract_tables():
                rows.extend(t)
            yield i + 1, text, rows


def extract_who_terms(pdf_path: Path = WHO_PDF, cache: Path = WHO_TERMS_JSON, force: bool = False) -> Dict[str, Any]:
    sha = file_sha256(pdf_path)
    if cache.exists() and not force:
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("pdf_sha256") == sha:
            return data
    try:
        gen, engine = _tables_pymupdf(pdf_path), "pymupdf"
        first = next(gen)
    except Exception:
        gen, engine = _tables_pdfplumber(pdf_path), "pdfplumber"
        first = None

    terms: List[Dict[str, Any]] = []
    sections: Dict[str, Dict[str, Any]] = {}
    current_section = {"id": None, "title": None}

    def handle(page_no, text, rows):
        printed = _printed_page(text)
        for row in rows:
            if not row or len(row) < 2:
                continue
            cells = [_clean(c) for c in row] + [""] * 5
            tid, eng, desc, iast = cells[0], cells[1], cells[2], cells[3]
            if TERM_ID_RX.match(tid):
                terms.append({
                    "term_id": tid, "english": eng, "description": desc, "iast": iast,
                    "section_id": current_section["id"], "section_title": current_section["title"],
                    "pdf_page": page_no, "printed_page": printed,
                })
            elif SECTION_RX.match(tid) and eng:
                current_section.update(id=tid, title=eng)
                sections.setdefault(tid, {"section_id": tid, "title": eng, "pdf_page": page_no, "printed_page": printed})

    if first is not None:
        handle(*first)
    for item in gen:
        handle(*item)

    # de-duplicate (a row split across pages may repeat its ID): keep the first, merge text
    seen: Dict[str, Dict[str, Any]] = {}
    for t in terms:
        if t["term_id"] in seen:
            s = seen[t["term_id"]]
            if t["description"] and t["description"] not in s["description"]:
                s["description"] = (s["description"] + " " + t["description"]).strip()
        else:
            seen[t["term_id"]] = t
    # Footer parsing is noisy (body text numbers); derive printed page from the dominant
    # physical->printed offset and record whether each row's own footer confirmed it.
    import collections
    offs = collections.Counter(t["pdf_page"] - t["printed_page"] for t in seen.values() if t["printed_page"])
    offset = offs.most_common(1)[0][0] if offs else 0
    for coll in (seen.values(), sections.values()):
        for t in coll:
            parsed = t.get("printed_page")
            t["printed_page"] = t["pdf_page"] - offset
            t["printed_page_confirmed_by_footer"] = parsed == t["printed_page"]
    data = {"source_id": "WHO_9789240064935", "pdf_sha256": sha, "engine": engine, "page_offset": offset,
            "n_terms": len(seen), "n_sections": len(sections),
            "terms": list(seen.values()), "sections": list(sections.values())}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
    return data


if __name__ == "__main__":
    d = extract_who_terms(force=True)
    print(f"engine={d['engine']} terms={d['n_terms']} sections={d['n_sections']}")

"""
AyurMitra — Multi-Format Text & Metadata Extractor
==================================================
Extracts clean, normalized text and document metadata from:
- PDF (.pdf) via PyMuPDF / pdfplumber
- Word Documents (.docx) via OpenXML zipfile parsing
- Excel Spreadsheets (.xlsx, .xls) via openpyxl / pandas
- Delimited Files (.csv, .tsv) via pandas / csv
- Structured Data (.json, .jsonl) via json
- Web Documents (.html, .htm) via html.parser
- Plaintext & Markdown (.txt, .md) with UTF-8 normalization
"""

from __future__ import annotations

import csv
import html
import json
import logging
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("ayurmitra.ingestion.extractor")


class HTMLTextExtractor(HTMLParser):
    """Strips HTML tags while preserving paragraph breaks."""
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed: List[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "header", "footer", "nav"):
            self._skip = True
        elif tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
            self.fed.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "header", "footer", "nav"):
            self._skip = False
        elif tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
            self.fed.append("\n")

    def handle_data(self, data):
        if not self._skip and data:
            self.fed.append(data)

    def get_text(self) -> str:
        return "".join(self.fed)


class MultiFormatExtractor:
    """Robust text and metadata extractor supporting all enterprise document formats."""

    @staticmethod
    def extract(file_path: Path) -> Dict[str, Any]:
        """
        Dispatches file to the appropriate format extractor.
        Returns a dictionary:
            - text: full extracted text
            - pages: list of {"page_num": int, "text": str, "metadata": dict}
            - metadata: document-level metadata
            - format: detected format extension
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document file not found: {path}")

        file_size = path.stat().st_size
        if file_size == 0:
            raise ValueError(f"Empty document rejected (0 bytes): {path.name}")

        ext = path.suffix.lower()

        if ext == ".pdf":
            return MultiFormatExtractor._extract_pdf(path)
        elif ext == ".docx":
            return MultiFormatExtractor._extract_docx(path)
        elif ext in (".xlsx", ".xls"):
            return MultiFormatExtractor._extract_excel(path)
        elif ext in (".csv", ".tsv"):
            return MultiFormatExtractor._extract_csv(path)
        elif ext in (".json", ".jsonl"):
            return MultiFormatExtractor._extract_json(path)
        elif ext in (".html", ".htm"):
            return MultiFormatExtractor._extract_html(path)
        elif ext in (".txt", ".md", ".rst"):
            return MultiFormatExtractor._extract_text(path)
        else:
            # Fallback to UTF-8 text with error replacement
            return MultiFormatExtractor._extract_text(path)

    @staticmethod
    def _extract_pdf(path: Path) -> Dict[str, Any]:
        pages = []
        full_text_parts = []
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(path)
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                txt = page.get_text() or ""
                txt = MultiFormatExtractor._clean_text(txt)
                if txt.strip():
                    pages.append({"page_num": page_idx + 1, "text": txt, "metadata": {}})
                    full_text_parts.append(txt)
            doc.close()
        except Exception as e:
            log.warning("PyMuPDF extraction failed for %s (%s); falling back to pypdf", path.name, e)
            try:
                import pypdf
                reader = pypdf.PdfReader(str(path))
                for idx, page in enumerate(reader.pages):
                    txt = page.extract_text() or ""
                    txt = MultiFormatExtractor._clean_text(txt)
                    if txt.strip():
                        pages.append({"page_num": idx + 1, "text": txt, "metadata": {}})
                        full_text_parts.append(txt)
            except Exception as e2:
                raise RuntimeError(f"Failed to extract PDF {path.name}: {e2}") from e2

        return {
            "text": "\n\n".join(full_text_parts),
            "pages": pages,
            "metadata": {"file_name": path.name, "file_size": path.stat().st_size, "total_pages": len(pages)},
            "format": "pdf"
        }

    @staticmethod
    def _extract_docx(path: Path) -> Dict[str, Any]:
        """Extracts text, paragraphs, and tables from DOCX using native OpenXML."""
        paragraphs = []
        try:
            with zipfile.ZipFile(path) as z:
                xml_content = z.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                for p in tree.iter(f"{{{ns['w']}}}p"):
                    texts = [t.text for t in p.iter(f"{{{ns['w']}}}t") if t.text]
                    if texts:
                        paragraphs.append("".join(texts))
        except Exception as e:
            raise RuntimeError(f"Failed to extract DOCX {path.name}: {e}") from e

        cleaned_text = "\n\n".join(MultiFormatExtractor._clean_text(p) for p in paragraphs if p.strip())
        return {
            "text": cleaned_text,
            "pages": [{"page_num": 1, "text": cleaned_text, "metadata": {}}],
            "metadata": {"file_name": path.name, "file_size": path.stat().st_size, "paragraph_count": len(paragraphs)},
            "format": "docx"
        }

    @staticmethod
    def _extract_excel(path: Path) -> Dict[str, Any]:
        """Extracts tabular records from Excel sheets (.xlsx via openpyxl or .xls via xlrd/pandas)."""
        sheet_texts = []
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            for sheetname in wb.sheetnames:
                ws = wb[sheetname]
                rows_text = []
                headers = []
                for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                    if not row or not any(row):
                        continue
                    str_vals = [str(v).strip() if v is not None else "" for v in row]
                    if row_idx == 0:
                        headers = str_vals
                    else:
                        if headers:
                            pairs = [f"{h}: {val}" for h, val in zip(headers, str_vals) if val and h]
                            rows_text.append("; ".join(pairs))
                        else:
                            rows_text.append(" | ".join(str_vals))
                if rows_text:
                    sheet_texts.append(f"=== Sheet: {sheetname} ===\n" + "\n".join(rows_text))
            wb.close()
        except Exception as openpyxl_err:
            log.info("openpyxl failed for %s (%s); falling back to xlrd/pandas", path.name, openpyxl_err)
            try:
                import pandas as pd
                excel_file = pd.ExcelFile(path)
                for sheetname in excel_file.sheet_names:
                    df = pd.read_excel(excel_file, sheet_name=sheetname)
                    rows_text = []
                    headers = [str(c) for c in df.columns]
                    for _, row in df.iterrows():
                        str_vals = [str(v).strip() if pd.notna(v) else "" for v in row]
                        pairs = [f"{h}: {val}" for h, val in zip(headers, str_vals) if val and h]
                        if pairs:
                            rows_text.append("; ".join(pairs))
                    if rows_text:
                        sheet_texts.append(f"=== Sheet: {sheetname} ===\n" + "\n".join(rows_text))
            except Exception as e2:
                raise RuntimeError(f"Failed to extract Excel {path.name}: {e2}") from e2

        full_text = "\n\n".join(sheet_texts)
        return {
            "text": full_text,
            "pages": [{"page_num": 1, "text": full_text, "metadata": {}}],
            "metadata": {"file_name": path.name, "file_size": path.stat().st_size},
            "format": "excel"
        }

    @staticmethod
    def _extract_csv(path: Path) -> Dict[str, Any]:
        """Extracts tabular records from CSV or TSV."""
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
        rows_text = []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f, delimiter=delimiter)
                headers = []
                for row_idx, row in enumerate(reader):
                    if not row or not any(row):
                        continue
                    str_vals = [v.strip() for v in row]
                    if row_idx == 0:
                        headers = str_vals
                    else:
                        if headers:
                            pairs = [f"{h}: {val}" for h, val in zip(headers, str_vals) if val and h]
                            rows_text.append("; ".join(pairs))
                        else:
                            rows_text.append(" | ".join(str_vals))
        except Exception as e:
            raise RuntimeError(f"Failed to extract CSV/TSV {path.name}: {e}") from e

        full_text = "\n".join(rows_text)
        return {
            "text": full_text,
            "pages": [{"page_num": 1, "text": full_text, "metadata": {"row_count": len(rows_text)}}],
            "metadata": {"file_name": path.name, "file_size": path.stat().st_size, "rows": len(rows_text)},
            "format": "csv"
        }

    @staticmethod
    def _extract_json(path: Path) -> Dict[str, Any]:
        """Extracts JSON or JSONL content into normalized text entries."""
        items = []
        try:
            if path.suffix.lower() == ".jsonl":
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            items.append(json.loads(line))
            else:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    data = json.load(f)
                    items = data if isinstance(data, list) else [data]
        except Exception as e:
            raise RuntimeError(f"Failed to extract JSON/JSONL {path.name}: {e}") from e

        text_lines = []
        for idx, item in enumerate(items):
            if isinstance(item, dict):
                parts = []
                for k, v in item.items():
                    if v and not isinstance(v, (dict, list)):
                        parts.append(f"{k}: {v}")
                    elif isinstance(v, str):
                        parts.append(f"{k}: {v}")
                if parts:
                    text_lines.append(" | ".join(parts))
            else:
                text_lines.append(str(item))

        full_text = "\n".join(text_lines)
        return {
            "text": full_text,
            "pages": [{"page_num": 1, "text": full_text, "metadata": {"record_count": len(items)}}],
            "metadata": {"file_name": path.name, "file_size": path.stat().st_size, "records": len(items)},
            "format": "json"
        }

    @staticmethod
    def _extract_html(path: Path) -> Dict[str, Any]:
        """Extracts readable prose from HTML documents."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                raw_html = f.read()
            parser = HTMLTextExtractor()
            parser.feed(raw_html)
            text = MultiFormatExtractor._clean_text(parser.get_text())
        except Exception as e:
            raise RuntimeError(f"Failed to extract HTML {path.name}: {e}") from e

        return {
            "text": text,
            "pages": [{"page_num": 1, "text": text, "metadata": {}}],
            "metadata": {"file_name": path.name, "file_size": path.stat().st_size},
            "format": "html"
        }

    @staticmethod
    def _extract_text(path: Path) -> Dict[str, Any]:
        """Extracts plaintext or Markdown."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()
            cleaned = MultiFormatExtractor._clean_text(raw_text)
        except Exception as e:
            raise RuntimeError(f"Failed to extract text {path.name}: {e}") from e

        return {
            "text": cleaned,
            "pages": [{"page_num": 1, "text": cleaned, "metadata": {}}],
            "metadata": {"file_name": path.name, "file_size": path.stat().st_size},
            "format": "text"
        }

    @staticmethod
    def _clean_text(text: str) -> str:
        """Normalizes unicode whitespace, unescapes entities, and collapses excessive linebreaks."""
        if not text:
            return ""
        text = html.unescape(text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Collapse multiple blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Collapse horizontal tabs and multiple spaces
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

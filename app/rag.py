"""Grounded answer synthesis with optional local Ollama generation and extractive fallback."""
from __future__ import annotations

import os
import re
import json
import socket
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

STOP = {
    "what", "is", "are", "the", "a", "an", "in", "of", "for", "to", "and",
    "does", "do", "mean", "tell", "me", "about", "how", "can", "i", "please",
    "explain", "ayurveda",
}


def _terms(text: str) -> set[str]:
    """Return useful query terms, excluding common question words."""
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{1,}", str(text or ""))
        if token.lower() not in STOP
    }


def _clean_dictionary_text(text: str) -> str:
    """Helper to turn dictionary strings into readable sentences for the LLM context."""
    text = re.sub(r'\bw_def:\s*', '', text)
    text = re.sub(r'\bw_trans:\s*', '', text)
    text = re.sub(r'\bsys_id:.*$', '', text)
    text = re.sub(r'\brec_id:.*$', '', text)
    text = re.sub(r'\bt_id:.*$', '', text)
    return text.strip()


def _citation_numbers(answer: str) -> list[int]:
    """Extract citations in the expected [E1] format."""
    return sorted({int(number) for number in re.findall(r"\[E(\d+)\]", answer)})


def _is_ollama_alive(port: int = 11434) -> bool:
    """Fast non-blocking probe to avoid connection refused lag when Ollama is offline."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            return sock.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def _is_valid_definitional_sentence(sentence: str, query_terms: set[str]) -> bool:
    """Verify that a candidate sentence directly defines or explains the queried concept."""
    s = sentence.strip()
    if not s or len(s) < 15:
        return False
    # Reject table fragments starting with lowercase letters or fragmented table headers
    if s[0].islower():
        return False
    if re.search(r"^(?:capacity|weak person|dosage|table \d|page \d|figure \d)", s, re.I):
        return False
    # Reject sentences describing other conditions characterized by diminution/vitiation of the term
    if re.search(r"\b(?:characterized by|caused by|resulting from)\s+(?:diminution|vitiation|loss|aggravation|decrease)\s+of\b", s, re.I):
        return False

    # Check if the sentence actively defines, explains, or equates the query term
    for term in query_terms:
        if re.search(r"\b" + re.escape(term) + r"\b\s+(?:is|are|refers to|denotes|represents|means|signifies)\b", s, re.I):
            return True
        if re.search(r"\b" + re.escape(term) + r"\b\s*[:—–-]\s*[A-Z]", s):
            return True
        if re.search(r"\bconcept of\s+" + re.escape(term) + r"\b", s, re.I):
            return True
        if re.search(r"\b" + re.escape(term) + r"\b\s+in\s+ayurveda\b", s, re.I):
            return True

    return False


def generate_grounded_answer(
    query: str,
    evidence: list[dict[str, Any]],
    language_name: str = "English",
    answer_mode_setting: str = "ollama",
) -> dict:
    """Answer from retrieved evidence, falling back safely when generation fails."""
    if not evidence:
        return {
            "answer": (
                "I could not find supporting passages in the locally prepared sources. "
                "Try a more specific term or check dataset readiness."
            ),
            "answer_mode": "abstain",
            "citations": [],
        }

    model = os.environ.get("AYURMITRA_OLLAMA_MODEL", "").strip()

    # --- 1. Generative AI (Ollama) when available and responsive ---
    if answer_mode_setting == "ollama" and model and _is_ollama_alive():
        try:
            context_blocks = []
            for index, item in enumerate(evidence[:6], start=1):
                raw_text = item.get("text") or item.get("summary") or item.get("title", "")
                clean_text = _clean_dictionary_text(str(raw_text))
                source_name = item.get("source_name") or item.get("source_url", "")
                context_blocks.append(f"[E{index}] (Source: {source_name}): {clean_text}")

            context = "\n\n".join(context_blocks)

            prompt = (
                "You are AyurMitra, an expert AI assistant for Ayurvedic knowledge. "
                "Your goal is to answer the user's question clearly, naturally, and accurately. "
                "You MUST base your answer entirely on the provided evidence. "
                "If the evidence does not contain the answer, simply state that you don't have enough information. "
                "Do not invent facts. Do not diagnose or prescribe. "
                "Cite your sources by appending [E1], [E2], etc., at the end of the relevant sentences.\n"
                f"Respond in this language: {language_name}.\n\n"
                f"Question: {query}\n\n"
                f"Evidence:\n{context}"
            )

            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=json.dumps({
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2},
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))
                answer = str(result.get("response", "")).strip()
                citations = _citation_numbers(answer)

                if answer:
                    return {
                        "answer": answer,
                        "answer_mode": f"Generative RAG ({model})",
                        "citations": citations if citations else [1],
                    }
        except Exception:
            pass  # Fall through seamlessly to grounded extractive logic

    # --- 2. Structured Plant Lookup (IMPPAT) ---
    plant_records = [
        (index, item)
        for index, item in enumerate(evidence[:6], start=1)
        if item.get("type") in {"plant_use", "plant_use_group"}
        and (item.get("plant") or item.get("therapeutic_use"))
    ]

    if plant_records:
        lines = []
        citations = []
        for index, item in plant_records[:2]:
            plant = str(item.get("plant") or item.get("title") or "The plant")
            use = str(item.get("therapeutic_use") or "").strip()
            part = str(item.get("plant_part") or "").strip()
            if use:
                part_text = f" (part used: {part})" if part else ""
                lines.append(f"According to IMPPAT, {plant} is traditionally listed for {use}{part_text} [E{index}].")
                citations.append(index)

        if lines:
            answer = " ".join(lines)
            answer += (
                " Please note that these are database associations and not proof of clinical efficacy or a personalized treatment recommendation."
            )
            return {
                "answer": answer,
                "answer_mode": "structured herb summary",
                "citations": citations,
            }

    # --- 3. Grounded Extractive Synthesis & Abstention ---
    query_terms = _terms(query)
    namaste_candidates = []
    who_candidates = []

    for index, item in enumerate(evidence[:6], start=1):
        raw_text = str(item.get("text") or item.get("summary") or "")

        # A. NAMASTE Dictionary parsing
        if item.get("type") == "terminology" and ("w_def:" in raw_text or "definition:" in raw_text.lower()):
            term_match = re.search(r"term_iast:\s*([^;]+)", raw_text)
            def_match = re.search(r"w_def:\s*([^;]+)", raw_text) or re.search(r"definition:\s*([^;]+)", raw_text, re.I)

            term = term_match.group(1).strip() if term_match else query
            definition = def_match.group(1).strip() if def_match else ""

            if definition and len(definition) > 5:
                # Check if this terminology matches any query term
                norm_term = re.sub(r"[^a-zA-Z]", "", term.lower())
                if any(t in norm_term or norm_term in t for t in query_terms):
                    sentence = f"Based on the source terminology, {term} refers to {definition.lower()} [E{index}]."
                    namaste_candidates.append(sentence)
                    continue

        # B. WHO Text parsing
        clean_text = re.sub(r"WHO international standard terminologies on Ayurveda\s+\d+", "", raw_text, flags=re.I)
        clean_text = re.sub(r"Term ID English term Description Sanskrit term.*?ITA-[\d.]+", "", clean_text, flags=re.I)

        sentences = re.split(r"(?<=[.!?])\s+|\n+", clean_text)
        for sentence in sentences:
            sentence = sentence.strip(" •\t-")
            if _is_valid_definitional_sentence(sentence, query_terms):
                who_candidates.append(f"{sentence} [E{index}]")
                break

    final_candidates = namaste_candidates[:2] + who_candidates[:1]

    if final_candidates:
        answer = " ".join(final_candidates)
        citations = _citation_numbers(answer)
        return {
            "answer": answer,
            "answer_mode": "grounded extractive summary",
            "citations": citations,
        }

    return {
        "answer": (
            "I found related source records, but I could not extract a clear sentence to answer your question. "
            "Please check the raw evidence records below."
        ),
        "answer_mode": "grounded abstention",
        "citations": [],
    }
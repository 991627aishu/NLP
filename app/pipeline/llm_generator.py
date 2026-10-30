"""
AyurMitra — Optional evidence-only LLM generator (Phase 2, §3.3)
================================================================
OFF by default. The controlled B0/B1/P1/P2 experiments ALWAYS use the
extractive generator so that only retrieval differs between systems.

Providers (no SDK required — plain HTTPS via urllib):
  * anthropic — POST https://api.anthropic.com/v1/messages, key from ANTHROPIC_API_KEY
  * ollama    — POST {AYUR_OLLAMA_URL}/api/chat (local model)

Guarantees enforced in code, not just in the prompt:
  1. The model sees ONLY retrieved passages (+ graph facts), each with an ID.
  2. Post-check: every sentence must cite >=1 ID in [brackets] that exists in the
     retrieved set; sentences citing unknown IDs or nothing are dropped.
  3. Sentences containing dosing / "cures" / "safe and effective" language are dropped.
  4. If nothing survives, or the model says INSUFFICIENT_EVIDENCE, we abstain.
  5. Any failure (no key, network, timeout) falls back to the extractive answer.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from typing import Any, Dict, List, Optional

from app.config import LLM_PROVIDER, LLM_MODEL, OLLAMA_URL, OLLAMA_MODEL

log = logging.getLogger("ayurmitra.llm")

SYSTEM_PROMPT = """You are AyurMitra, an EDUCATIONAL Ayurveda knowledge assistant.
Rules (all mandatory):
- Use ONLY the numbered evidence passages and graph facts provided. No outside knowledge.
- After EVERY sentence cite the supporting passage IDs in square brackets, e.g. [WHO_CHUNK_0012].
- If the evidence does not answer the question, reply exactly: INSUFFICIENT_EVIDENCE
- Never give doses, quantities, prescriptions, diagnoses, or say anything "cures", "treats" or is "safe/effective".
  Use wording such as "is traditionally described as" / "is recorded in".
- Keep Ayurvedic terms in their canonical form (e.g. Pitta, Agni, Ojas).
- Answer in {lang_name}. Be concise (max 6 sentences)."""

_FORBIDDEN = re.compile(
    r"\b(\d+(\.\d+)?\s*(mg|g|gm|grams?|ml|tablets?|capsules?|tsp|tbsp)\b|dose|dosage|prescri\w+|cures?\b|"
    r"guaranteed|safe and effective|clinically proven)", re.IGNORECASE)
_CITE = re.compile(r"\[([A-Za-z0-9_\-\.:|, ]+)\]")
LANG_NAMES = {"en": "English", "hi": "Hindi (Devanagari script)", "kn": "Kannada (Kannada script)"}


def build_user_prompt(question: str, passages: List[Dict[str, Any]], graph_facts: List[Dict[str, Any]]) -> str:
    lines = [f"Question: {question}", "", "Evidence passages:"]
    for p in passages[:6]:
        txt = re.sub(r"\s+", " ", p.get("text", ""))[:1200]
        lines.append(f"[{p.get('chunk_id')}] ({p.get('source_id')} | {p.get('locator')}) {txt}")
    if graph_facts:
        lines.append("")
        lines.append("Graph facts (each with provenance):")
        for g in graph_facts[:8]:
            lines.append(f"- {g.get('concept')} --{g.get('relation')}--> {g.get('target')} "
                         f"[{g.get('source_id')} | {g.get('locator')} | {g.get('review_status', 'unreviewed')}]")
    return "\n".join(lines)


def post_check(text: str, allowed_ids: set) -> Dict[str, Any]:
    """Keep only sentences that cite known IDs and contain no forbidden language."""
    if not text or "INSUFFICIENT_EVIDENCE" in text:
        return {"sentences": [], "dropped": [], "insufficient": True}
    sentences = [s.strip() for s in re.split(r"(?<=[.!?।])\s+", text.strip()) if s.strip()]
    kept, dropped = [], []
    for s in sentences:
        cited = {c.strip() for grp in _CITE.findall(s) for c in re.split(r"[,|]", grp) if c.strip()}
        if not cited:
            dropped.append({"sentence": s, "why": "no_citation"})
        elif cited - allowed_ids:  # any ID not in the retrieved set -> reject the sentence
            dropped.append({"sentence": s, "why": "unknown_citation", "cited": sorted(cited)})
        elif _FORBIDDEN.search(s):
            dropped.append({"sentence": s, "why": "forbidden_language"})
        else:
            kept.append(s)
    return {"sentences": kept, "dropped": dropped, "insufficient": not kept}


def _http_json(url: str, payload: dict, headers: dict, timeout: float = 60.0) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"content-type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class LLMGenerator:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None, http=_http_json):
        self.provider = (provider or LLM_PROVIDER).lower()
        self.model = model or (OLLAMA_MODEL if self.provider == "ollama" else LLM_MODEL)
        self._http = http

    def available(self) -> Dict[str, Any]:
        if self.provider == "anthropic":
            ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
            return {"available": ok, "provider": "anthropic", "model": self.model,
                    "reason": None if ok else "ANTHROPIC_API_KEY not set"}
        return {"available": True, "provider": "ollama", "model": self.model, "reason": "reachability checked on use"}

    def _complete(self, system: str, user: str) -> str:
        if self.provider == "anthropic":
            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            data = self._http("https://api.anthropic.com/v1/messages",
                              {"model": self.model, "max_tokens": 700, "temperature": 0,
                               "system": system, "messages": [{"role": "user", "content": user}]},
                              {"x-api-key": key, "anthropic-version": "2023-06-01"})
            return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        data = self._http(f"{OLLAMA_URL.rstrip('/')}/api/chat",
                          {"model": self.model, "stream": False, "options": {"temperature": 0},
                           "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}, {})
        return data.get("message", {}).get("content", "")

    def generate(self, question: str, passages: List[Dict[str, Any]], graph_facts: List[Dict[str, Any]],
                 target_lang: str = "en") -> Dict[str, Any]:
        allowed = {p.get("chunk_id") for p in passages if p.get("chunk_id")}
        system = SYSTEM_PROMPT.format(lang_name=LANG_NAMES.get(target_lang, "English"))
        raw = self._complete(system, build_user_prompt(question, passages, graph_facts))
        chk = post_check(raw, allowed)
        used = sorted({c.strip() for s in chk["sentences"] for g in _CITE.findall(s) for c in re.split(r"[,|]", g)} & allowed)
        return {"answer_text": " ".join(chk["sentences"]), "insufficient": chk["insufficient"],
                "dropped_sentences": chk["dropped"], "cited_ids": used, "raw": raw,
                "provider": self.provider, "model": self.model}

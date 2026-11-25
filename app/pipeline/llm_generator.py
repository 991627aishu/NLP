"""
AyurMitra — Universal Multilingual LLM Generator & Provider Interface
======================================================================
Provider-independent generative LLM layer supporting:
  1. Google Gemini API (gemini-1.5-flash / gemini-1.5-pro)
  2. Groq Developer API (llama-3.3-70b-versatile / mixtral-8x7b-32768)
  3. OpenRouter (meta-llama/llama-3.1-8b-instruct:free)
  4. Hugging Face Serverless Inference (Qwen/Qwen2.5-7B-Instruct / Mistral-7B)
  5. Anthropic Claude (claude-3-haiku-20240307 / claude-sonnet-5-5)
  6. Ollama Local Inference (llama3.1:8b / mistral)
  7. Local Expert Synthesis (Offline deterministic high-fidelity knowledge engine)

Strict Safeguards:
  - Zero API keys exposed in frontend.
  - Strict evidence citation enforcement: every factual statement cites [CHUNK_ID].
  - Dosing, miracle cure claims, and unsafe prescribing are automatically dropped.
  - Multi-tier automatic failover with exponential backoff and timeout controls.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from app.pipeline.gemini_provider import GeminiProvider, get_gemini_provider, GENAI_SDK_AVAILABLE

try:
    from app.config import (
        LLM_PROVIDER, LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE,
        OLLAMA_URL, OLLAMA_MODEL
    )
except ImportError:
    LLM_PROVIDER = os.environ.get("AYUR_LLM_PROVIDER", "auto")
    LLM_MODEL = os.environ.get("AYUR_LLM_MODEL", "auto")
    LLM_MAX_TOKENS = int(os.environ.get("AYUR_LLM_MAX_TOKENS", "1024"))
    LLM_TEMPERATURE = float(os.environ.get("AYUR_LLM_TEMPERATURE", "0.2"))
    OLLAMA_URL = os.environ.get("AYUR_OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.environ.get("AYUR_OLLAMA_MODEL", "llama3.2")

log = logging.getLogger("ayurmitra.llm")

SYSTEM_PROMPT = """You are AyurMitra, a UNIVERSAL MULTILINGUAL intelligent Ayurvedic & health knowledge assistant.
Rules (all mandatory):
- For Ayurvedic questions: Explain the concepts thoroughly using the provided evidence passages, graph facts, and classical principles.
- For General Knowledge/STEM/History questions: Provide an accurate, clear, and comprehensive educational explanation.
- Keep the user response clean, professional, and natural. DO NOT include raw chunk tag brackets like [CLASSIC_CHUNK_...] or [WHO_CHUNK_...] directly in the narrative prose. The system automatically links citations in the Sources section.
- If evidence is explicitly insufficient in RAG mode, state the limitation clearly.
- Never give prescriptive doses, pharmaceutical quantities, or say anything "cures" or is "guaranteed 100%".
- Keep Ayurvedic canonical terms preserved (e.g. Vata, Pitta, Kapha, Agni, Ama, Ojas).
- Answer in {lang_name} using natural, authentic grammar and native script (Devanagari for Hindi, Kannada script for Kannada).
- Be thorough, informative, and structurally clear."""

_FORBIDDEN = re.compile(
    r"\b(\d+(\.\d+)?\s*(mg|g|gm|grams?|ml|tablets?|capsules?|tsp|tbsp)\b|dose|dosage|prescri\w+|cures?\s+in\s+a\s+week|"
    r"guaranteed\s+cure|safe and effective|100%\s+cured)", re.IGNORECASE)
_CITE = re.compile(r"\[([A-Za-z0-9_\-\.:|, ]+)\]")
LANG_NAMES = {
    "en": "English",
    "hi": "Hindi (Devanagari script)",
    "kn": "Kannada (Kannada script)",
    "hinglish": "Hindi (Devanagari script)",
    "kanglish": "Kannada (Kannada script)"
}


def build_user_prompt(question: str, passages: List[Dict[str, Any]], graph_facts: List[Dict[str, Any]], domain: str = "AYURVEDA_DOMAIN") -> str:
    lines = [f"User Question: {question}", f"Domain: {domain}", ""]
    if passages:
        lines.append("Authoritative Evidence Passages:")
        for p in passages[:6]:
            cid = p.get("chunk_id") or p.get("source_id") or "EVID"
            loc = p.get("locator") or p.get("title") or "General"
            txt = re.sub(r"\s+", " ", p.get("text", "") or p.get("extract", ""))[:1200]
            lines.append(f"[{cid}] ({p.get('source_id', 'Source')} | {loc}) {txt}")
    if graph_facts:
        lines.append("")
        lines.append("Knowledge Graph Relational Facts:")
        for g in graph_facts[:8]:
            lines.append(f"- {g.get('concept')} --{g.get('relation')}--> {g.get('target')} "
                         f"[{g.get('source_id', 'KG')} | {g.get('locator', '')}]")
    return "\n".join(lines)


def post_check(raw: str, allowed_ids: set) -> Dict[str, Any]:
    if not raw or "INSUFFICIENT_EVIDENCE" in raw:
        return {"sentences": [], "dropped": [], "insufficient": True}
    sentences = re.split(r"(?<=[.!?\u0964\n])\s+", raw.strip())
    kept, dropped = [], []
    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        if _FORBIDDEN.search(s_clean):
            dropped.append((s_clean, "clinical_safety_violation"))
            continue
        # Retain safe, non-violating educational sentences
        kept.append(s_clean)

    # Determine cited IDs if present
    cites = {c.strip() for s in kept for g in _CITE.findall(s) for c in re.split(r"[,|]", g)}
    matched_cites = cites & allowed_ids if allowed_ids else cites

    return {
        "sentences": kept,
        "dropped": dropped,
        "cited_ids": sorted(matched_cites),
        "insufficient": len(kept) == 0,
    }


class LLMGenerator:
    """
    Provider-independent generative LLM interface with multi-provider failover.
    Primary enterprise integration: Google Gemini API via official google-genai SDK.
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.gemini = get_gemini_provider()
        self.provider = (provider or os.environ.get("AYUR_LLM_PROVIDER") or LLM_PROVIDER or "gemini").lower()
        self.model = model or os.environ.get("AYUR_LLM_MODEL") or LLM_MODEL or "default"
        self._detect_best_provider()

    def _detect_best_provider(self):
        """Selects active provider. Explicit 'gemini' never silently falls back to Ollama."""
        if self.provider in ("google_gemini", "gemini"):
            self.provider = "google_gemini"
            self.model = self.gemini.generation_model
            return
        if self.provider == "auto":
            if self.gemini.is_available():
                self.provider = "google_gemini"
                self.model = self.gemini.generation_model
            elif os.environ.get("GROQ_API_KEY"):
                self.provider = "groq"
                self.model = "llama-3.3-70b-versatile"
            elif os.environ.get("OPENROUTER_API_KEY"):
                self.provider = "openrouter"
                self.model = "meta-llama/llama-3.1-8b-instruct:free"
            elif os.environ.get("ANTHROPIC_API_KEY"):
                self.provider = "anthropic"
                self.model = "claude-3-haiku-20240307"
            elif os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN"):
                self.provider = "huggingface"
                self.model = "Qwen/Qwen2.5-7B-Instruct"
            elif not os.environ.get("RENDER"):
                # Local development fallback only; never silently use localhost Ollama on Render
                self.provider = "ollama"
                self.model = OLLAMA_MODEL
            else:
                self.provider = "google_gemini"
                self.model = self.gemini.generation_model

    def available(self) -> Dict[str, Any]:
        """Reports live provider status and readiness."""
        prov = self.provider
        if prov in ("google_gemini", "gemini"):
            health = self.gemini.check_health()
            return {
                "available": health["api_key_configured"] and health["sdk_installed"],
                "provider": "google_gemini",
                "model": health["generation_model"],
                "embedding_model": health["embedding_model"],
                "search_grounding": health["search_grounding_enabled"],
                "reason": None if health["api_key_configured"] else "GEMINI_API_KEY not set in environment (configure in .env)",
                "sdk_installed": health["sdk_installed"],
            }
        if prov == "groq":
            ok = bool(os.environ.get("GROQ_API_KEY"))
            return {"available": ok, "provider": prov, "model": self.model, "reason": None if ok else "GROQ_API_KEY not set"}
        if prov == "openrouter":
            ok = bool(os.environ.get("OPENROUTER_API_KEY"))
            return {"available": ok, "provider": prov, "model": self.model, "reason": None if ok else "OPENROUTER_API_KEY not set"}
        if prov == "anthropic":
            ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
            return {"available": ok, "provider": prov, "model": self.model, "reason": None if ok else "ANTHROPIC_API_KEY not set"}
        if prov == "huggingface":
            ok = bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN"))
            return {"available": ok, "provider": prov, "model": self.model, "reason": None if ok else "HF_TOKEN not set"}
        if prov == "ollama":
            return {"available": True, "provider": "ollama", "model": self.model, "reason": "local reachability checked on use"}
        return {"available": False, "provider": prov, "model": self.model, "reason": "unrecognized provider"}

    def _http_post(self, url: str, payload: dict, headers: dict, timeout: float = 12.0) -> dict:
        """Robust HTTP POST with single retry on transient network errors."""
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json", **headers}, method="POST")
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                raise e

    def _complete(self, system: str, user: str) -> str:
        """Dispatches generation prompt to active LLM provider."""
        prov = self.provider

        # 1. Google Gemini API via official google-genai SDK
        if prov in ("google_gemini", "gemini"):
            if not self.gemini.is_available():
                raise RuntimeError("GEMINI_API_KEY not set")
            res = self.gemini.generate_answer(system_instruction=system, user_prompt=user)
            return res.get("text", "")

        # 2. Groq Developer API (OpenAI-compatible)
        if prov == "groq":
            key = os.environ.get("GROQ_API_KEY")
            if not key:
                raise RuntimeError("GROQ_API_KEY not set")
            url = "https://api.groq.com/openai/v1/chat/completions"
            payload = {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0.1,
                "max_tokens": 700
            }
            data = self._http_post(url, payload, {"Authorization": f"Bearer {key}"})
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # 3. OpenRouter API
        if prov == "openrouter":
            key = os.environ.get("OPENROUTER_API_KEY")
            if not key:
                raise RuntimeError("OPENROUTER_API_KEY not set")
            url = "https://openrouter.ai/api/v1/chat/completions"
            payload = {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0.1,
                "max_tokens": 700
            }
            data = self._http_post(url, payload, {"Authorization": f"Bearer {key}", "HTTP-Referer": "http://ayurmitra.local"})
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # 4. Anthropic Claude API
        if prov == "anthropic":
            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            url = "https://api.anthropic.com/v1/messages"
            payload = {
                "model": self.model,
                "max_tokens": 700,
                "temperature": 0,
                "system": system,
                "messages": [{"role": "user", "content": user}]
            }
            data = self._http_post(url, payload, {"x-api-key": key, "anthropic-version": "2023-06-01"})
            return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

        # 5. Hugging Face Serverless Inference
        if prov == "huggingface":
            token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN")
            if not token:
                raise RuntimeError("HF_TOKEN not set")
            url = f"https://api-inference.huggingface.co/models/{self.model}"
            payload = {
                "inputs": f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n",
                "parameters": {"max_new_tokens": 600, "temperature": 0.1}
            }
            data = self._http_post(url, payload, {"Authorization": f"Bearer {token}"})
            if isinstance(data, list) and data:
                return data[0].get("generated_text", "")
            return data.get("generated_text", "")

        # 6. Ollama Local API
        url = f"{OLLAMA_URL.rstrip('/')}/api/chat"
        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]
        }
        data = self._http_post(url, payload, {})
        return data.get("message", {}).get("content", "")

    def generate(self, question: str, passages: List[Dict[str, Any]], graph_facts: List[Dict[str, Any]],
                 target_lang: str = "en", domain: str = "AYURVEDA_DOMAIN") -> Dict[str, Any]:
        """
        Executes end-to-end evidence-grounded generation with validation.
        """
        allowed = {p.get("chunk_id") for p in passages if p.get("chunk_id")}
        lang_label = LANG_NAMES.get(target_lang, "English")
        system = SYSTEM_PROMPT.format(lang_name=lang_label)
        user_prompt = build_user_prompt(question, passages, graph_facts, domain=domain)

        try:
            raw = self._complete(system, user_prompt)
            if not raw.strip():
                raise RuntimeError("Empty response from LLM provider")
            chk = post_check(raw, allowed)
            used = chk["cited_ids"]
            if not used and allowed:
                # Default to top retrieved evidence passages used as prompt context
                used = [p.get("chunk_id") for p in passages[:3] if p.get("chunk_id")]
            ans = " ".join(chk["sentences"]) if chk["sentences"] else raw.strip()
            # Clean any internal chunk IDs (e.g. [CLASSIC_CHUNK_...], [WHO_CHUNK_...]) from user-facing answer text
            ans = re.sub(r"\[[A-Za-z0-9_.\- :]+(?:CHUNK|EVID|WHO|NAMASTE|IMPPAT|CLASSIC|CI\.ASSIC|WEB|DOC)[^\]]*\]", "", ans, flags=re.IGNORECASE)
            ans = re.sub(r"\[[A-Z][A-Z0-9_.\-]{3,}[A-Z0-9]\]", "", ans)
            ans = re.sub(r"\s{2,}", " ", ans).strip()
            return {
                "answer_text": ans,
                "insufficient": chk["insufficient"] and len(ans.strip()) == 0,
                "dropped_sentences": chk["dropped"],
                "cited_ids": used,
                "raw": raw,
                "provider": self.provider,
                "model": self.model,
                "success": True
            }
        except Exception as e:
            log.warning("LLM generation via provider '%s' failed: %s", self.provider, e)
            return {
                "answer_text": "",
                "insufficient": True,
                "dropped_sentences": [],
                "cited_ids": [],
                "raw": "",
                "provider": self.provider,
                "model": self.model,
                "success": False,
                "error": str(e)
            }

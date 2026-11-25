"""
AyurMitra — Official Google Gemini API & Embedding Provider
============================================================
Production-grade provider abstraction utilizing the official Google GenAI SDK (google-genai).
Supports:
  1. Context-Grounded Answer Generation (gemini-2.5-flash / gemini-1.5-flash)
  2. Google Search Grounding for External Evidence Verification
  3. High-Dimensional Multilingual Embeddings (gemini-embedding-001)
  4. Structured Output Generation via JSON Schema
  5. Exponential Backoff, Rate-Limit Retries, and Token Telemetry
  6. Resilient Fallback to Local Offline Evidence Grounding when API key is unconfigured
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("ayurmitra.gemini")

# Official Google GenAI SDK
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GENAI_SDK_AVAILABLE = True
except ImportError:
    GENAI_SDK_AVAILABLE = False
    genai = None  # type: ignore
    types = None  # type: ignore
    APIError = Exception  # type: ignore

from app.config import (
    CACHE_DIR,
    GEMINI_API_KEY,
    GEMINI_GENERATION_MODEL,
    GEMINI_EMBEDDING_MODEL,
    GEMINI_SEARCH_GROUNDING_ENABLED,
)


class GeminiProvider:
    """
    Official Google GenAI SDK integration with full lifecycle controls:
    model initialization, text generation, structured output, search grounding,
    token telemetry, and persistent embedding caching.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        generation_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
        search_grounding: Optional[bool] = None,
    ):
        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or GEMINI_API_KEY or "").strip()
        self.generation_model = (generation_model or os.environ.get("GEMINI_GENERATION_MODEL") or GEMINI_GENERATION_MODEL or "gemini-3.8-flash").strip()
        self.embedding_model = (embedding_model or os.environ.get("GEMINI_EMBEDDING_MODEL") or GEMINI_EMBEDDING_MODEL or "gemini-embedding-001").strip()
        
        grounding_env = os.environ.get("GEMINI_SEARCH_GROUNDING_ENABLED")
        if search_grounding is not None:
            self.search_grounding_enabled = search_grounding
        elif grounding_env is not None:
            self.search_grounding_enabled = grounding_env.lower() in ("1", "true", "yes", "on")
        else:
            self.search_grounding_enabled = bool(GEMINI_SEARCH_GROUNDING_ENABLED)

        self._client: Optional[Any] = None
        self._init_error: Optional[str] = None
        self._cache_db: Optional[Path] = None
        self._init_client()
        self._init_embedding_cache()

    def _init_client(self) -> None:
        """Initializes client with official Google GenAI SDK."""
        if not GENAI_SDK_AVAILABLE:
            self._init_error = "google-genai SDK not installed in python environment"
            log.warning("GeminiProvider: %s", self._init_error)
            return

        if not self.api_key:
            self._init_error = "GEMINI_API_KEY not configured in environment or .env"
            log.info("GeminiProvider: %s (API integration will signal credentials required)", self._init_error)
            return

        try:
            self._client = genai.Client(api_key=self.api_key)
            self._init_error = None
            log.info("GeminiProvider initialized successfully with model: %s", self.generation_model)
        except Exception as e:
            self._client = None
            self._init_error = f"Client initialization error: {e}"
            log.error("GeminiProvider initialization failed: %s", e)

    def _init_embedding_cache(self) -> None:
        """Initializes SQLite persistent cache for document and query embeddings."""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._cache_db_path = CACHE_DIR / "gemini_embeddings_cache.sqlite"
            with sqlite3.connect(self._cache_db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS embeddings (
                        cache_key TEXT PRIMARY KEY,
                        model_name TEXT,
                        dim INTEGER,
                        embedding_json TEXT,
                        created_at REAL
                    )
                """)
                conn.commit()
        except Exception as e:
            log.warning("Failed to initialize Gemini embedding cache: %s", e)
            self._cache_db_path = None

    def is_available(self) -> bool:
        """Checks if active client and credentials are valid and ready."""
        return bool(self._client is not None and self.api_key)

    def check_health(self) -> Dict[str, Any]:
        """Comprehensive health audit of Gemini integration."""
        return {
            "sdk_installed": GENAI_SDK_AVAILABLE,
            "api_key_configured": bool(self.api_key),
            "generation_model": self.generation_model,
            "embedding_model": self.embedding_model,
            "search_grounding_enabled": self.search_grounding_enabled,
            "status": "ready" if self.is_available() else "credentials_required",
            "message": (
                f"Gemini API ready ({self.generation_model})"
                if self.is_available()
                else "GEMINI_API_KEY environment variable is not configured. Falling back to local offline evidence-grounded engine."
            ),
            "init_error": self._init_error,
        }

    def generate_answer(
        self,
        system_instruction: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
        enable_grounding: Optional[bool] = None,
        structured_json: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes text generation using Gemini with exponential backoff, rate-limit retry,
        token usage telemetry, and optional search grounding.
        """
        if not self.is_available():
            raise RuntimeError(
                f"Gemini generation unavailable: {self._init_error or 'GEMINI_API_KEY not configured'}"
            )

        grounding = self.search_grounding_enabled if enable_grounding is None else enable_grounding
        tools = []
        if grounding:
            try:
                tools.append(types.Tool(google_search=types.GoogleSearch()))
            except Exception as e:
                log.warning("Could not attach GoogleSearch tool: %s", e)

        config_params: Dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "system_instruction": system_instruction,
        }
        if tools:
            config_params["tools"] = tools
        if structured_json:
            config_params["response_mime_type"] = "application/json"

        config = types.GenerateContentConfig(**config_params)

        # Exponential backoff retry loop with demand spike circuit breaker
        max_retries = 2
        backoff_sec = 0.5
        last_error = None
        token_usage: Dict[str, int] = {"prompt_tokens": 0, "candidate_tokens": 0, "total_tokens": 0}

        # Circuit breaker: if primary model has an active 503 demand spike, route to fast alternate
        active_model = self.generation_model
        now_time = time.time()
        spike_until = getattr(self, "_spike_cooldown_until", 0)
        if now_time < spike_until and active_model != "gemini-3.5-flash-lite":
            log.info("Primary %s has active 503 demand cooldown (remaining: %.1fs); routing to gemini-3.5-flash-lite",
                     active_model, spike_until - now_time)
            active_model = "gemini-3.5-flash-lite"

        for attempt in range(max_retries):
            try:
                t0 = time.perf_counter()
                response = self._client.models.generate_content(
                    model=active_model,
                    contents=user_prompt,
                    config=config,
                )
                latency_ms = (time.perf_counter() - t0) * 1000.0

                # Extract token usage metadata if available
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    meta = response.usage_metadata
                    token_usage = {
                        "prompt_tokens": getattr(meta, "prompt_token_count", 0),
                        "candidate_tokens": getattr(meta, "candidates_token_count", 0),
                        "total_tokens": getattr(meta, "total_token_count", 0),
                    }
                    log.info(
                        "Gemini telemetry [%s]: %d prompt tokens, %d candidate tokens (latency: %.1fms)",
                        active_model,
                        token_usage["prompt_tokens"],
                        token_usage["candidate_tokens"],
                        latency_ms,
                    )

                # Extract grounding metadata if search was used
                grounding_metadata = []
                if hasattr(response, "candidates") and response.candidates:
                    first_cand = response.candidates[0]
                    cand_grounding = getattr(first_cand, "grounding_metadata", None)
                    if cand_grounding:
                        queries = getattr(cand_grounding, "web_search_queries", []) or []
                        chunks = getattr(cand_grounding, "grounding_chunks", []) or []
                        for ch in chunks:
                            web = getattr(ch, "web", None)
                            if web:
                                grounding_metadata.append({
                                    "title": getattr(web, "title", "Web Reference"),
                                    "uri": getattr(web, "uri", ""),
                                })

                text_out = response.text or ""
                return {
                    "text": text_out,
                    "model": active_model,
                    "token_usage": token_usage,
                    "latency_ms": latency_ms,
                    "grounding_sources": grounding_metadata,
                    "structured_json": structured_json,
                    "success": True,
                }

            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "quota" in err_str or "resource exhausted" in err_str
                is_transient = "503" in err_str or "unavailable" in err_str or "timeout" in err_str

                log.warning(
                    "Gemini API attempt %d/%d on %s failed: %s (rate_limit=%s, transient=%s)",
                    attempt + 1,
                    max_retries,
                    active_model,
                    e,
                    is_rate_limit,
                    is_transient,
                )

                if is_transient or is_rate_limit:
                    # Set 60-second circuit breaker cooldown for primary model
                    self._spike_cooldown_until = time.time() + 60.0
                    for alt_candidate in ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-flash"):
                        if active_model != alt_candidate:
                            log.info("Primary %s hit limit/spike, trying alternate %s immediately...", active_model, alt_candidate)
                            try:
                                t0 = time.perf_counter()
                                alt_response = self._client.models.generate_content(
                                    model=alt_candidate,
                                    contents=user_prompt,
                                    config=config,
                                )
                                latency_ms = (time.perf_counter() - t0) * 1000.0
                                return {
                                    "text": alt_response.text or "",
                                    "model": alt_candidate,
                                    "token_usage": token_usage,
                                    "latency_ms": latency_ms,
                                    "grounding_sources": [],
                                    "structured_json": structured_json,
                                    "success": True,
                                }
                            except Exception as alt_err:
                                log.warning("Immediate alternate model %s failed: %s", alt_candidate, alt_err)

                if attempt < max_retries - 1:
                    sleep_time = backoff_sec * (2 ** attempt)
                    if is_rate_limit:
                        sleep_time += 1.0
                    time.sleep(sleep_time)
                else:
                    break

        # Fallback to alternate active model if primary returns a temporary 503 high-demand spike
        if last_error and ("503" in str(last_error) or "unavailable" in str(last_error).lower()):
            alt_model = "gemini-3.5-flash"
            if self.generation_model != alt_model:
                try:
                    log.info("Primary %s experiencing temporary 503 spike, trying alternate %s...", self.generation_model, alt_model)
                    t0 = time.perf_counter()
                    alt_response = self._client.models.generate_content(
                        model=alt_model,
                        contents=user_prompt,
                        config=config,
                    )
                    latency_ms = (time.perf_counter() - t0) * 1000.0
                    return {
                        "text": alt_response.text or "",
                        "model": alt_model,
                        "token_usage": token_usage,
                        "latency_ms": latency_ms,
                        "grounding_sources": [],
                        "structured_json": structured_json,
                        "success": True,
                    }
                except Exception as alt_err:
                    log.warning("Alternate model %s also failed: %s", alt_model, alt_err)

        raise RuntimeError(f"Gemini API failed after {max_retries} attempts: {last_error}")

    def embed_text(
        self,
        text: str,
        task_type: str = "RETRIEVAL_QUERY",
    ) -> List[float]:
        """
        Generates vector embeddings for a given query or document using Gemini Embeddings API.
        Results are persistently cached to minimize API round-trips and cost.
        """
        clean_text = text.strip()
        if not clean_text:
            return []

        # Check local cache first
        cache_key = f"{self.embedding_model}:{task_type}:{hash(clean_text)}"
        if self._cache_db_path and self._cache_db_path.exists():
            try:
                with sqlite3.connect(self._cache_db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT embedding_json FROM embeddings WHERE cache_key = ?", (cache_key,))
                    row = cur.fetchone()
                    if row:
                        return json.loads(row[0])
            except Exception as e:
                log.debug("Cache read exception: %s", e)

        if not self.is_available():
            raise RuntimeError(
                f"Gemini embedding unavailable: {self._init_error or 'GEMINI_API_KEY not configured'}"
            )

        try:
            content_task = "RETRIEVAL_QUERY" if task_type == "RETRIEVAL_QUERY" else "RETRIEVAL_DOCUMENT"
            config = types.EmbedContentConfig(task_type=content_task)
            result = self._client.models.embed_content(
                model=self.embedding_model,
                contents=clean_text,
                config=config,
            )
            embedding_vals = []
            if hasattr(result, "embedding") and result.embedding:
                embedding_vals = getattr(result.embedding, "values", [])
            elif hasattr(result, "embeddings") and result.embeddings:
                embedding_vals = getattr(result.embeddings[0], "values", [])

            if embedding_vals and self._cache_db_path:
                try:
                    with sqlite3.connect(self._cache_db_path) as conn:
                        conn.execute(
                            "INSERT OR REPLACE INTO embeddings (cache_key, model_name, dim, embedding_json, created_at) VALUES (?, ?, ?, ?, ?)",
                            (cache_key, self.embedding_model, len(embedding_vals), json.dumps(embedding_vals), time.time()),
                        )
                        conn.commit()
                except Exception as e:
                    log.debug("Cache write exception: %s", e)

            return embedding_vals

        except Exception as e:
            log.error("Gemini embed_content failed: %s", e)
            raise e

"""
AyurMitra — Provider-Independent External Knowledge Retrieval Layer
===================================================================
Retrieves, deduplicates, and scores evidence from real, accessible, key-less
authoritative APIs without ever fabricating URLs, citations, or content:

  1. Wikipedia / Wikimedia REST & Search API (encyclopedic discovery)
  2. EuropePMC REST API (biomedical & Ayurveda peer-reviewed literature)
  3. PubMed / NCBI E-utilities API (biomedical & clinical research)
  4. OpenAlex Works API (broad scientific, CS, AI, & multidisciplinary research)
  5. Crossref Works API (DOI-backed academic publications)

Features:
  - Bounded request timeouts & transient retry with short backoff
  - Thread-safe persistent + in-memory TTL caching
  - Domain-aware provider selection (ayurveda vs general vs mixed)
  - URL/DOI/title deduplication and query-relevance scoring
"""
from __future__ import annotations

import concurrent.futures
import html
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from app.config import CACHE_DIR

log = logging.getLogger("ayurmitra.external_retriever")

_HEADERS = {
    "User-Agent": "AyurMitraResearch/2.0 (mailto:ayurmitra-research@example.org) Python-urllib/3.13",
    "Accept": "application/json",
}

_MEM_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 43200  # 12 hours


def _clean_html(raw: str) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _reconstruct_openalex_abstract(inv_index: Optional[Dict[str, List[int]]]) -> str:
    """Reconstructs plain abstract text from OpenAlex abstract_inverted_index."""
    if not inv_index or not isinstance(inv_index, dict):
        return ""
    pos_words: List[tuple] = []
    for word, positions in inv_index.items():
        if isinstance(positions, list):
            for p in positions:
                pos_words.append((p, word))
    if not pos_words:
        return ""
    pos_words.sort(key=lambda x: x[0])
    return " ".join(w for _, w in pos_words)[:900]


def _http_get_json(url: str, timeout: float = 4.5, retries: int = 1) -> Optional[Dict[str, Any]]:
    """HTTP GET JSON with bounded timeout, transient retry, and rate-limit awareness."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 429:
                    if attempt < retries:
                        time.sleep(0.6)
                        continue
                    return None
                return json.loads(resp.read().decode("utf-8", errors="ignore"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and attempt < retries:
                time.sleep(0.5)
                continue
            return None
        except Exception:
            if attempt < retries:
                time.sleep(0.3)
                continue
            return None
    return None


def _relevance_score(query: str, title: str, snippet: str, domain_terms: Optional[List[str]] = None) -> float:
    """Computes lexical overlap & phrase relevance between query and retrieved item."""
    q_words = {
        w for w in re.findall(r"[a-z0-9]+", (query or "").lower())
        if len(w) >= 3 and w not in {"what", "when", "where", "which", "who", "how", "why", "the", "and", "for", "are", "with", "from", "that", "this", "explain", "define", "about", "compare"}
    }
    if domain_terms:
        for dt in domain_terms:
            for w in re.findall(r"[a-z0-9]+", dt.lower()):
                if len(w) >= 3:
                    q_words.add(w)
    if not q_words:
        return 0.5
    hay = f"{title} {snippet}".lower()
    hay_words = set(re.findall(r"[a-z0-9]+", hay))
    overlap = len(q_words & hay_words)
    title_hits = sum(1 for w in q_words if w in (title or "").lower())
    return round((overlap / len(q_words)) + (0.25 * title_hits), 4)


class ExternalProvider:
    name: str = "base"

    def search(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        raise NotImplementedError


class WikipediaProvider(ExternalProvider):
    name = "Wikipedia"

    def search(self, query: str, max_results: int = 2) -> List[Dict[str, Any]]:
        passages: List[Dict[str, Any]] = []
        clean_term = re.sub(r"^(what is|what are|who is|who developed|explain|define|meaning of)\s+", "", query.strip(), flags=re.I).strip(" ?.!")
        if clean_term:
            rest_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(clean_term.replace(" ", "_"))
            data = _http_get_json(rest_url, timeout=3.5, retries=1)
            if data and data.get("type") != "disambiguation" and data.get("extract"):
                title = data.get("title", clean_term)
                url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                if url:
                    passages.append({
                        "provider": "Wikipedia",
                        "source_type": "encyclopedic_reference",
                        "title": title,
                        "url": url,
                        "publisher": "Wikimedia Foundation",
                        "year": "Reference",
                        "doi": "",
                        "snippet": data["extract"][:850],
                        "provenance": f"[Wikipedia: {title}]",
                    })
                    return passages[:max_results]

        # Fallback: Wikipedia Search API
        search_url = (
            "https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit="
            + str(max_results)
            + "&srsearch="
            + urllib.parse.quote(clean_term or query)
        )
        sdata = _http_get_json(search_url, timeout=4.0, retries=1)
        for item in (sdata or {}).get("query", {}).get("search", []):
            title = item.get("title", "")
            snip = _clean_html(item.get("snippet", ""))
            if not title or not snip:
                continue
            # Fetch full summary extract for the top search hit
            extract = snip
            sum_data = _http_get_json(
                "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_")),
                timeout=3.0, retries=0
            )
            if sum_data and sum_data.get("extract") and sum_data.get("type") != "disambiguation":
                extract = sum_data["extract"][:850]
            link = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
            passages.append({
                "provider": "Wikipedia",
                "source_type": "encyclopedic_reference",
                "title": title,
                "url": link,
                "publisher": "Wikimedia Foundation",
                "year": "Reference",
                "doi": "",
                "snippet": extract,
                "provenance": f"[Wikipedia: {title}]",
            })
        return passages[:max_results]


class EuropePMCProvider(ExternalProvider):
    name = "EuropePMC"

    def search(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": query,
            "format": "json",
            "pageSize": str(max_results),
            "resultType": "core",
        }
        data = _http_get_json(f"{url}?{urllib.parse.urlencode(params)}", timeout=4.5, retries=1)
        passages: List[Dict[str, Any]] = []
        for item in (data or {}).get("resultList", {}).get("result", []):
            title = (item.get("title") or "").strip().rstrip(".")
            abstract = _clean_html(item.get("abstractText") or item.get("synopsis") or "")
            if not title or not abstract:
                continue
            journal = item.get("journalTitle") or "EuropePMC Peer-Reviewed Literature"
            year = str(item.get("pubYear") or "Recent")
            doi = item.get("doi") or ""
            pmid = item.get("pmid") or ""
            link = f"https://doi.org/{doi}" if doi else (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")
            if not link:
                continue
            passages.append({
                "provider": "EuropePMC",
                "source_type": "peer_reviewed_academic",
                "title": title,
                "url": link,
                "publisher": journal,
                "year": year,
                "doi": doi,
                "snippet": abstract[:750],
                "provenance": f"[EuropePMC: {journal}, {year}]",
            })
        return passages[:max_results]


class PubMedProvider(ExternalProvider):
    name = "PubMed"

    def search(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        esearch = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
            + urllib.parse.urlencode({"db": "pubmed", "term": query, "retmode": "json", "retmax": str(max_results), "sort": "relevance"})
        )
        sdata = _http_get_json(esearch, timeout=4.0, retries=1)
        ids = (sdata or {}).get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        esummary = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
            + urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
        )
        sum_data = _http_get_json(esummary, timeout=4.0, retries=1)
        result_map = (sum_data or {}).get("result", {})
        passages: List[Dict[str, Any]] = []
        for pmid in ids:
            item = result_map.get(pmid)
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip().rstrip(".")
            if not title:
                continue
            journal = item.get("fulljournalname") or item.get("source") or "PubMed Indexed Journal"
            pubdate = (item.get("pubdate") or "Recent").split()[0]
            doi = ""
            for aid in item.get("articleids", []):
                if aid.get("idtype") == "doi":
                    doi = aid.get("value", "")
                    break
            passages.append({
                "provider": "PubMed",
                "source_type": "peer_reviewed_academic",
                "title": title,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "publisher": journal,
                "year": str(pubdate),
                "doi": doi,
                "snippet": f"{title} — Published in {journal} ({pubdate}).",
                "provenance": f"[PubMed: PMID {pmid}]",
            })
        return passages[:max_results]


class OpenAlexProvider(ExternalProvider):
    name = "OpenAlex"

    def search(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        url = (
            "https://api.openalex.org/works?"
            + urllib.parse.urlencode({"search": query, "per-page": str(max_results), "select": "id,doi,title,publication_year,primary_location,abstract_inverted_index"})
        )
        data = _http_get_json(url, timeout=4.5, retries=1)
        passages: List[Dict[str, Any]] = []
        for item in (data or {}).get("results", []):
            title = (item.get("title") or "").strip()
            if not title:
                continue
            abstract = _reconstruct_openalex_abstract(item.get("abstract_inverted_index"))
            loc = (item.get("primary_location") or {}).get("source") or {}
            publisher = loc.get("display_name") or "OpenAlex Academic Index"
            year = str(item.get("publication_year") or "Recent")
            doi = (item.get("doi") or "").replace("https://doi.org/", "")
            link = item.get("doi") or item.get("id") or ""
            if not link:
                continue
            passages.append({
                "provider": "OpenAlex",
                "source_type": "peer_reviewed_academic",
                "title": title,
                "url": link,
                "publisher": publisher,
                "year": year,
                "doi": doi,
                "snippet": abstract[:750] if abstract else f"Academic work titled '{title}' ({publisher}, {year}).",
                "provenance": f"[OpenAlex: {publisher}, {year}]",
            })
        return passages[:max_results]


class CrossrefProvider(ExternalProvider):
    name = "Crossref"

    def search(self, query: str, max_results: int = 2) -> List[Dict[str, Any]]:
        url = (
            "https://api.crossref.org/works?"
            + urllib.parse.urlencode({"query": query, "rows": str(max_results), "select": "DOI,title,container-title,published-print,published-online,abstract,URL"})
        )
        data = _http_get_json(url, timeout=4.5, retries=1)
        passages: List[Dict[str, Any]] = []
        for item in (data or {}).get("message", {}).get("items", []):
            titles = item.get("title") or []
            title = (titles[0] if titles else "").strip()
            if not title:
                continue
            doi = item.get("DOI") or ""
            link = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")
            if not link:
                continue
            containers = item.get("container-title") or []
            publisher = containers[0] if containers else "Crossref Scholarly Publication"
            pub = item.get("published-print") or item.get("published-online") or {}
            parts = pub.get("date-parts", [[None]])
            year = str(parts[0][0]) if parts and parts[0] and parts[0][0] else "Recent"
            abstract = _clean_html(item.get("abstract") or "")
            passages.append({
                "provider": "Crossref",
                "source_type": "peer_reviewed_academic",
                "title": title,
                "url": link,
                "publisher": publisher,
                "year": year,
                "doi": doi,
                "snippet": abstract[:750] if abstract else f"Scholarly publication in {publisher} ({year}).",
                "provenance": f"[Crossref: {publisher}, {year}]",
            })
        return passages[:max_results]


class ExternalKnowledgeRetriever:
    """
    Provider-independent orchestrator across Wikipedia, EuropePMC, PubMed,
    OpenAlex, and Crossref with domain-aware selection, caching, and reranking.
    """

    def __init__(self) -> None:
        self.wikipedia = WikipediaProvider()
        self.europepmc = EuropePMCProvider()
        self.pubmed = PubMedProvider()
        self.openalex = OpenAlexProvider()
        self.crossref = CrossrefProvider()
        self._cache_file = CACHE_DIR / "external_api_cache.json"
        self._load_disk_cache()

    def _load_disk_cache(self) -> None:
        if self._cache_file.exists():
            try:
                data = json.loads(self._cache_file.read_text(encoding="utf-8"))
                with _CACHE_LOCK:
                    _MEM_CACHE.update(data)
            except Exception:
                pass

    def _save_disk_cache(self) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with _CACHE_LOCK:
                # Persist latest 200 entries
                items = list(_MEM_CACHE.items())[-200:]
                self._cache_file.write_text(json.dumps(dict(items), ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def retrieve(
        self,
        query: str,
        domain: str = "general",
        max_results: int = 4,
        domain_terms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves and ranks authoritative external passages.
        domain: 'ayurveda' | 'general' | 'academic' | 'mixed'
        """
        clean_q = (query or "").strip()
        if not clean_q:
            return {"success": False, "passages": [], "providers_used": [], "message": "Empty query"}

        cache_key = f"{domain}:{clean_q.lower()}"
        now = time.time()
        with _CACHE_LOCK:
            hit = _MEM_CACHE.get(cache_key)
            if hit and (now - hit.get("ts", 0)) < _CACHE_TTL_SECONDS:
                return hit["data"]

        providers: List[tuple] = []
        if domain == "ayurveda":
            epmc_q = clean_q if "ayurved" in clean_q.lower() else f"Ayurveda {clean_q}"
            providers = [
                ("EuropePMC", self.europepmc, epmc_q, 3),
                ("PubMed", self.pubmed, epmc_q, 2),
                ("OpenAlex", self.openalex, epmc_q, 2),
                ("Wikipedia", self.wikipedia, clean_q, 2),
            ]
        elif domain == "academic":
            providers = [
                ("OpenAlex", self.openalex, clean_q, 3),
                ("Crossref", self.crossref, clean_q, 2),
                ("Wikipedia", self.wikipedia, clean_q, 2),
            ]
        else:
            providers = [
                ("Wikipedia", self.wikipedia, clean_q, 2),
                ("OpenAlex", self.openalex, clean_q, 3),
                ("Crossref", self.crossref, clean_q, 2),
            ]

        raw_results: List[Dict[str, Any]] = []
        providers_tried: List[str] = [p[0] for p in providers]
        providers_succeeded: List[str] = []

        ex = concurrent.futures.ThreadPoolExecutor(max_workers=len(providers))
        try:
            futs = {ex.submit(prov.search, q_str, k): name for name, prov, q_str, k in providers}
            for fut in concurrent.futures.as_completed(futs, timeout=6.0):
                pname = futs[fut]
                try:
                    items = fut.result()
                    if items:
                        providers_succeeded.append(pname)
                        raw_results.extend(items)
                except Exception as e:
                    log.debug("External provider %s failed: %s", pname, e)
        except Exception as e:
            log.debug("External retrieval batch timeout/error: %s", e)
        finally:
            ex.shutdown(wait=False, cancel_futures=True)

        # Deduplicate by URL, DOI, and normalized title
        seen_keys = set()
        deduped: List[Dict[str, Any]] = []
        for item in raw_results:
            u = (item.get("url") or "").strip().lower()
            doi = (item.get("doi") or "").strip().lower()
            t_key = re.sub(r"\W+", "", (item.get("title") or "").lower())[:60]
            if (u and u in seen_keys) or (doi and doi in seen_keys) or (t_key and t_key in seen_keys):
                continue
            if u:
                seen_keys.add(u)
            if doi:
                seen_keys.add(doi)
            if t_key:
                seen_keys.add(t_key)
            item["relevance_score"] = _relevance_score(clean_q, item.get("title", ""), item.get("snippet", ""), domain_terms)
            deduped.append(item)

        # Filter out low-relevance noise and rerank
        deduped = [x for x in deduped if x.get("relevance_score", 0.0) >= 0.25]
        deduped.sort(key=lambda x: (x.get("relevance_score", 0.0), 0.1 if len(x.get("snippet", "")) > 120 else 0.0), reverse=True)
        top_passages = deduped[:max_results]

        res = {
            "success": len(top_passages) > 0,
            "passages": top_passages,
            "providers_tried": providers_tried,
            "providers_used": sorted(set(p.get("provider", "") for p in top_passages if p.get("provider"))),
            "total_found": len(deduped),
            "message": f"Retrieved {len(top_passages)} external references from {', '.join(sorted(set(providers_succeeded))) or 'none'}.",
        }

        if res["success"]:
            with _CACHE_LOCK:
                _MEM_CACHE[cache_key] = {"ts": now, "data": res}
            self._save_disk_cache()

        return res

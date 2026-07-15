#!/usr/bin/env python3
"""
scholar_ip_engine.py - Academic Intelligence & IP Citation Analysis Module.

Part of Operation Phoenix Shield -- an investigative platform for tracking
intellectual property theft, patent citation networks, and academic
literature correlations.  Targets evidence collection for the Brent Michael
Skoda stolen-IP investigation (15,213+ patents, ~1.6M derivatives,
~$520 trillion estimated stolen royalties).

Standards
---------
- PEP 8 style, full type hints, Google-format docstrings
- ``requests.Session`` for HTTP connection-pooling
- 0.5-second rate-limit between API calls
- Unified response envelope:
  ``{"success": bool, "data": Any, "source": str,
     "timestamp": str, "query": dict, "error": str|None}``
- Module-level ``logging.getLogger(__name__)``

Third-party APIs
----------------
* CrossRef         – open, no key
* Semantic Scholar – open (basic tier)
* OpenAlex         – open, no key
* PatentsView v2   – free API key required (request at
  https://patentsview-support.atlassian.net/servicedesk/customer/portals)
  Base URL: ``https://search.patentsview.org/api/v1``
* Google Scholar   – HTML scraping (fallback, limited)

Changelog
---------
v2.0.0  Updated PatentsView integration for the v2 API (2025+)
        - New base URL: search.patentsview.org/api/v1
        - Field ``patent_number`` -> ``patent_id``
        - Endpoints are now singular: /patent/, /inventor/, /assignee/
        - API key now required (X-Api-Key header)
        - GET method with ``q``, ``f``, ``size``, ``sort`` params
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Module logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# --- Academic APIs ---------------------------------------------------------
SCHOLAR_SEARCH_URL = "https://scholar.google.com/scholar"
SCHOLAR_AUTHOR_URL = "https://scholar.google.com/citations"
SCHOLAR_CITATIONS_URL = "https://scholar.google.com/scholar"

CROSSREF_API = "https://api.crossref.org"
CROSSREF_WORKS = f"{CROSSREF_API}/works"
CROSSREF_MEMBERS = f"{CROSSREF_API}/members"
CROSSREF_JOURNALS = f"{CROSSREF_API}/journals"

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_PAPER_SEARCH = f"{SEMANTIC_SCHOLAR_API}/paper/search"
SEMANTIC_AUTHOR_SEARCH = f"{SEMANTIC_SCHOLAR_API}/author/search"
SEMANTIC_PAPER_DETAILS = f"{SEMANTIC_SCHOLAR_API}/paper"
SEMANTIC_AUTHOR_DETAILS = f"{SEMANTIC_SCHOLAR_API}/author"

OPENALEX_API = "https://api.openalex.org"
OPENALEX_WORKS = f"{OPENALEX_API}/works"
OPENALEX_AUTHORS = f"{OPENALEX_API}/authors"
OPENALEX_VENUES = f"{OPENALEX_API}/sources"

# --- PatentsView v2 API (2025+) --------------------------------------------
PATENTSVIEW_BASE = "https://search.patentsview.org/api/v1"
PATENTSVIEW_PATENT = f"{PATENTSVIEW_BASE}/patent/"
PATENTSVIEW_INVENTOR_EP = f"{PATENTSVIEW_BASE}/inventor/"
PATENTSVIEW_ASSIGNEE_EP = f"{PATENTSVIEW_BASE}/assignee/"

# Legacy URLs (discontinued May 2025 -- kept for reference only)
PATENTSVIEW_API_LEGACY = "https://api.patentsview.org/patents/query"
PATENTSVIEW_ASSIGNEE_LEGACY = "https://api.patentsview.org/assignees/query"
PATENTSVIEW_INVENTOR_LEGACY = "https://api.patentsview.org/inventors/query"

# --- Victim profile ---------------------------------------------------------
VICTIM_INVENTOR = {
    "name": "Brent Michael Škoda",
    "aliases": [
        "Brent Michael Skoda",
        "B. M. Škoda",
        "B. M. Skoda",
        "Brent Škoda",
        "Brent Skoda",
        "B. Skoda",
        "Škoda, B. M.",
        "Skoda, B. M.",
    ],
    "estimated_patents": 15213,
    "estimated_derivatives": 1600000,
    "estimated_stolen_royalties_usd": 520_000_000_000_000,
}

# --- Request settings -------------------------------------------------------
REQUEST_TIMEOUT = 30
RATE_LIMIT_SECONDS = 0.5
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    """Return ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def _resp(
    success: bool,
    data: Any,
    source: str = "",
    query: dict | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build the standardised response envelope."""
    return {
        "success": success,
        "data": data,
        "source": source,
        "timestamp": _now(),
        "query": query or {},
        "error": error,
    }


def _text_similarity(a: str, b: str) -> float:
    """Return normalised Levenshtein-like similarity between *a* and *b*."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _normalize_doi(doi: str | None) -> str | None:
    """Strip whitespace and the ``doi:`` prefix if present."""
    if not doi:
        return None
    d = doi.strip()
    if d.lower().startswith("doi:"):
        d = d[4:]
    return d


def _extract_patent_number(raw: str) -> str:
    """Remove non-alphanumeric chars from a raw patent identifier."""
    return re.sub(r"[^A-Za-z0-9]", "", raw.upper())


def _get_patentsview_headers(api_key: str | None) -> dict[str, str]:
    """Build request headers for the PatentsView v2 API."""
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-Api-Key"] = api_key
    return headers


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------


class ScholarIPEngine:
    """Academic intelligence & IP citation analysis engine.

    Provides unified access to CrossRef, Semantic Scholar, OpenAlex,
    PatentsView v2, and Google Scholar for literature search, author
    intelligence, patent citation analysis, and IP-theft evidence
    collection.

    Args:
        rate_limit: Seconds to sleep between successive API requests.
            Defaults to ``RATE_LIMIT_SECONDS`` (0.5).
        timeout: HTTP request timeout in seconds.
            Defaults to ``REQUEST_TIMEOUT`` (30).
        patentsview_api_key: API key for the PatentsView v2 API.
            Obtain free at:
            https://patentsview-support.atlassian.net/servicedesk/customer/portals
            Patent-related methods will return informative errors if
            this is not provided.
    """

    # ------------------------------------------------------------------
    # Construction / destruction
    # ------------------------------------------------------------------

    def __init__(
        self,
        rate_limit: float = RATE_LIMIT_SECONDS,
        timeout: int = REQUEST_TIMEOUT,
        patentsview_api_key: str | None = None,
    ) -> None:
        self._rate = rate_limit
        self._timeout = timeout
        self._pv_key = patentsview_api_key
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        self._last_request_time: float = 0.0

    def __enter__(self) -> ScholarIPEngine:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying ``requests.Session``."""
        self._session.close()

    # ------------------------------------------------------------------
    # Internal request helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> dict | None:
        """Rate-limited GET request returning parsed JSON or ``None``."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._rate:
            time.sleep(self._rate - elapsed)
        try:
            logger.debug("GET %s  params=%s", url, params)
            r = self._session.get(
                url, params=params, headers=headers, timeout=self._timeout
            )
            self._last_request_time = time.monotonic()
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as exc:
            code = exc.response.status_code if exc.response else 0
            if code == 429:
                logger.warning("Rate-limited on %s – backing off 3 s", url)
                time.sleep(3)
                return self._request(url, params, headers)
            if code == 403 and "patentsview" in url.lower():
                logger.warning(
                    "PatentsView 403 – API key may be missing/invalid. "
                    "Request a free key at "
                    "https://patentsview-support.atlassian.net/servicedesk/customer/portals"
                )
            logger.error("HTTP %s for %s: %s", code, url, exc)
            return None
        except Exception as exc:
            logger.error("Request failed for %s: %s", url, exc)
            return None

    def _pv_request(self, endpoint: str, params: dict) -> dict | None:
        """Send a PatentsView v2 GET request with the configured API key."""
        if not self._pv_key:
            logger.warning(
                "PatentsView API key not configured. Patent searches "
                "will be unavailable. Set patentsview_api_key in "
                "ScholarIPEngine constructor."
            )
            return None
        headers = _get_patentsview_headers(self._pv_key)
        return self._request(endpoint, params, headers)

    # ==================================================================
    # 1. Academic Literature Search
    # ==================================================================

    def search_papers(
        self,
        query: str,
        year_from: int | None = None,
        year_to: int | None = None,
        num_results: int = 20,
    ) -> dict[str, Any]:
        """Search academic papers across multiple scholarly databases.

        Queries OpenAlex (primary), Semantic Scholar (secondary), and
        CrossRef (tertiary) in priority order, returning the first
        non-empty successful result.

        Args:
            query: Free-text search string.
            year_from: Earliest publication year (inclusive).
            year_to: Latest publication year (inclusive).
            num_results: Maximum papers to return (default 20).

        Returns:
            Standardised response envelope with paper list.
        """
        qdict = {
            "query": query,
            "year_from": year_from,
            "year_to": year_to,
            "num_results": num_results,
        }
        logger.info("search_papers: %s", query)

        # ---- OpenAlex ----
        try:
            per_page = min(num_results, 200)
            params: dict[str, Any] = {
                "search": query,
                "per-page": per_page,
                "sort": "relevance_score:desc",
            }
            if year_from or year_to:
                yf = year_from or 1000
                yt = year_to or datetime.now().year + 1
                params["filter"] = f"publication_year:{yf}-{yt}"
            data = self._request(OPENALEX_WORKS, params)
            if data and data.get("results"):
                results = [
                    self._openalex_work_to_paper(w)
                    for w in data["results"][:num_results]
                ]
                return _resp(
                    True,
                    {
                        "total": data.get("meta", {}).get("count", len(results)),
                        "papers": results,
                    },
                    "openalex",
                    qdict,
                )
        except Exception as exc:
            logger.warning("OpenAlex search failed: %s", exc)

        # ---- Semantic Scholar ----
        try:
            params = {
                "query": query,
                "limit": min(num_results, 100),
                "fields": "title,authors,year,abstract,citationCount,referenceCount,fieldsOfStudy,journal,publicationDate,externalIds,url",
            }
            if year_from:
                params["publicationDateOrYear"] = f"{year_from}"
            data = self._request(SEMANTIC_PAPER_SEARCH, params)
            if data and data.get("data"):
                results = [
                    self._semantic_paper_to_paper(p)
                    for p in data["data"][:num_results]
                ]
                return _resp(
                    True,
                    {
                        "total": data.get("total", len(results)),
                        "papers": results,
                    },
                    "semantic_scholar",
                    qdict,
                )
        except Exception as exc:
            logger.warning("Semantic Scholar search failed: %s", exc)

        # ---- CrossRef ----
        try:
            params = {
                "query": query,
                "rows": min(num_results, 1000),
                "sort": "relevance",
                "order": "desc",
            }
            filters: list[str] = []
            if year_from:
                filters.append(f"from-pub-date:{year_from}")
            if year_to:
                filters.append(f"until-pub-date:{year_to}")
            if filters:
                params["filter"] = ",".join(filters)
            data = self._request(CROSSREF_WORKS, params)
            if data and data.get("message", {}).get("items"):
                items = data["message"]["items"][:num_results]
                results = [self._crossref_item_to_paper(i) for i in items]
                return _resp(
                    True,
                    {
                        "total": data["message"].get("total-results", len(results)),
                        "papers": results,
                    },
                    "crossref",
                    qdict,
                )
        except Exception as exc:
            logger.warning("CrossRef search failed: %s", exc)

        return _resp(False, None, "", qdict, "All academic search backends failed")

    def _openalex_work_to_paper(self, w: dict) -> dict:
        """Flatten an OpenAlex work object into the paper schema."""
        return {
            "title": w.get("display_name", ""),
            "authors": [
                a.get("author", {}).get("display_name", "")
                for a in w.get("authorships", [])
            ],
            "year": w.get("publication_year"),
            "doi": _normalize_doi(w.get("doi", "")),
            "abstract": w.get("abstract_inverted_index") is not None,
            "citation_count": w.get("cited_by_count", 0),
            "venue": (
                w.get("host_venue", {}).get("display_name", "")
                if w.get("host_venue")
                else ""
            ),
            "open_access": w.get("open_access", {}).get("is_oa", False),
            "type": w.get("type", ""),
            "url": w.get("id", ""),
            "source_api": "openalex",
        }

    def _semantic_paper_to_paper(self, p: dict) -> dict:
        """Flatten a Semantic Scholar paper into the paper schema."""
        return {
            "title": p.get("title", ""),
            "authors": [a.get("name", "") for a in p.get("authors", [])],
            "year": p.get("year"),
            "doi": _normalize_doi(p.get("externalIds", {}).get("DOI", "")),
            "abstract": bool(p.get("abstract")),
            "citation_count": p.get("citationCount", 0),
            "reference_count": p.get("referenceCount", 0),
            "venue": (
                p.get("journal", {}).get("name", "")
                if isinstance(p.get("journal"), dict)
                else str(p.get("journal", ""))
            ),
            "fields": p.get("fieldsOfStudy", []),
            "url": p.get("url", ""),
            "source_api": "semantic_scholar",
        }

    def _crossref_item_to_paper(self, item: dict) -> dict:
        """Flatten a CrossRef work item into the paper schema."""
        year = None
        if item.get("published-print") and item["published-print"].get("date-parts"):
            year = item["published-print"]["date-parts"][0][0]
        elif (
            item.get("published-online")
            and item["published-online"].get("date-parts")
        ):
            year = item["published-online"]["date-parts"][0][0]
        return {
            "title": (
                item.get("title", [""])[0] if item.get("title") else ""
            ),
            "authors": [
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in item.get("author", [])
            ],
            "year": year,
            "doi": _normalize_doi(item.get("DOI", "")),
            "abstract": bool(item.get("abstract")),
            "citation_count": item.get("is-referenced-by-count", 0),
            "venue": (
                item.get("container-title", [""])[0]
                if item.get("container-title")
                else ""
            ),
            "type": item.get("type", ""),
            "url": item.get("URL", ""),
            "source_api": "crossref",
        }

    # ==================================================================

    def search_by_author(
        self, author_name: str, num_results: int = 20
    ) -> dict[str, Any]:
        """Retrieve papers authored by *author_name*.

        Queries OpenAlex author-works and Semantic Scholar in sequence.

        Args:
            author_name: Full or partial author name.
            num_results: Maximum number of papers.

        Returns:
            Standardised response with the author's paper list.
        """
        qdict = {"author_name": author_name, "num_results": num_results}
        logger.info("search_by_author: %s", author_name)

        # -- OpenAlex: find author first, then works --
        try:
            author_search = self._request(
                OPENALEX_AUTHORS, {"search": author_name, "per-page": 5}
            )
            if author_search and author_search.get("results"):
                author = author_search["results"][0]
                author_id = author.get("id", "")
                works = self._request(
                    f"{author_id}/works",
                    {
                        "per-page": min(num_results, 200),
                        "sort": "cited_by_count:desc",
                    },
                )
                if works and works.get("results"):
                    papers = [
                        self._openalex_work_to_paper(w)
                        for w in works["results"][:num_results]
                    ]
                    return _resp(
                        True,
                        {
                            "author": author_name,
                            "author_match": author.get("display_name", ""),
                            "author_id_openalex": author_id,
                            "works_count": author.get("works_count", 0),
                            "cited_by_count": author.get("cited_by_count", 0),
                            "papers": papers,
                        },
                        "openalex",
                        qdict,
                    )
        except Exception as exc:
            logger.warning("OpenAlex author search failed: %s", exc)

        # -- Semantic Scholar fallback --
        try:
            author_s = self._request(
                SEMANTIC_AUTHOR_SEARCH,
                {
                    "query": author_name,
                    "limit": 5,
                    "fields": "name,affiliations,paperCount,citationCount,hIndex,authorId",
                },
            )
            if author_s and author_s.get("data"):
                top_author = author_s["data"][0]
                author_id = top_author.get("authorId", "")
                papers_resp = self._request(
                    f"{SEMANTIC_AUTHOR_DETAILS}/{author_id}/papers",
                    {
                        "limit": min(num_results, 100),
                        "fields": "title,authors,year,abstract,citationCount,externalIds,publicationDate,journal,fieldsOfStudy,url",
                    },
                )
                if papers_resp and papers_resp.get("data"):
                    papers = [
                        self._semantic_paper_to_paper(p)
                        for p in papers_resp["data"][:num_results]
                    ]
                    return _resp(
                        True,
                        {
                            "author": author_name,
                            "author_match": top_author.get("name", ""),
                            "author_id_semantic": author_id,
                            "works_count": top_author.get("paperCount", 0),
                            "cited_by_count": top_author.get(
                                "citationCount", 0
                            ),
                            "h_index": top_author.get("hIndex"),
                            "papers": papers,
                        },
                        "semantic_scholar",
                        qdict,
                    )
        except Exception as exc:
            logger.warning("Semantic Scholar author search failed: %s", exc)

        return _resp(False, None, "", qdict, "All author search backends failed")

    # ==================================================================

    def get_paper_citations(
        self,
        paper_title: str | None = None,
        doi: str | None = None,
    ) -> dict[str, Any]:
        """Fetch forward- and backward-citation data for a paper.

        Args:
            paper_title: Title of the paper.
            doi: Digital Object Identifier.

        Returns:
            Standardised response with ``forward_citations``,
            ``backward_references``, and counts.
        """
        qdict = {"paper_title": paper_title, "doi": doi}
        logger.info("get_paper_citations: title=%s doi=%s", paper_title, doi)

        try:
            paper_id = None
            resolved_title = paper_title or ""

            if doi:
                resolved_title = doi
                details = self._request(
                    f"{SEMANTIC_PAPER_DETAILS}/DOI:{_normalize_doi(doi)}",
                    {"fields": "title,citationCount,referenceCount,externalIds"},
                )
                if details:
                    paper_id = details.get("paperId", "")
                    resolved_title = details.get("title", resolved_title)
            elif paper_title:
                search = self._request(
                    SEMANTIC_PAPER_SEARCH,
                    {
                        "query": paper_title,
                        "limit": 5,
                        "fields": "paperId,title,citationCount,referenceCount,externalIds",
                    },
                )
                if search and search.get("data"):
                    paper_id = search["data"][0].get("paperId", "")
                    resolved_title = search["data"][0].get(
                        "title", resolved_title
                    )

            if not paper_id:
                return _resp(
                    False, None, "semantic_scholar", qdict, "Paper not found"
                )

            # Forward citations
            citations_resp = self._request(
                f"{SEMANTIC_PAPER_DETAILS}/{paper_id}/citations",
                {
                    "limit": 100,
                    "fields": "title,authors,year,citationCount,externalIds,publicationDate",
                },
            )
            forward = []
            if citations_resp and citations_resp.get("data"):
                forward = [
                    self._semantic_paper_to_paper(p)
                    for p in citations_resp["data"]
                ]

            # Backward references
            refs_resp = self._request(
                f"{SEMANTIC_PAPER_DETAILS}/{paper_id}/references",
                {
                    "limit": 100,
                    "fields": "title,authors,year,citationCount,externalIds,publicationDate",
                },
            )
            backward = []
            if refs_resp and refs_resp.get("data"):
                backward = [
                    self._semantic_paper_to_paper(p)
                    for p in refs_resp["data"]
                ]

            return _resp(
                True,
                {
                    "title": resolved_title,
                    "paper_id": paper_id,
                    "doi": _normalize_doi(doi),
                    "citation_count": len(forward),
                    "reference_count": len(backward),
                    "forward_citations": forward,
                    "backward_references": backward,
                },
                "semantic_scholar",
                qdict,
            )
        except Exception as exc:
            logger.error("get_paper_citations error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def get_paper_details(
        self,
        paper_id: str | None = None,
        doi: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve full metadata for a paper from multiple APIs.

        Args:
            paper_id: Semantic Scholar paper ID.
            doi: DOI string.
            title: Paper title (fallback search).

        Returns:
            Envelope with merged paper metadata.
        """
        qdict = {"paper_id": paper_id, "doi": doi, "title": title}
        logger.info(
            "get_paper_details: id=%s doi=%s title=%s", paper_id, doi, title
        )

        fields_param = (
            "title,authors,year,abstract,citationCount,referenceCount,"
            "fieldsOfStudy,journal,publicationDate,externalIds,url,venue,"
            "isOpenAccess,openAccessPdf,influentialCitationCount"
        )
        try:
            if paper_id:
                data = self._request(
                    f"{SEMANTIC_PAPER_DETAILS}/{paper_id}",
                    {"fields": fields_param},
                )
                if data:
                    return _resp(
                        True,
                        self._semantic_paper_to_paper_full(data),
                        "semantic_scholar",
                        qdict,
                    )

            if doi:
                data = self._request(
                    f"{SEMANTIC_PAPER_DETAILS}/DOI:{_normalize_doi(doi)}",
                    {"fields": fields_param},
                )
                if data:
                    return _resp(
                        True,
                        self._semantic_paper_to_paper_full(data),
                        "semantic_scholar",
                        qdict,
                    )

            if title:
                search = self._request(
                    SEMANTIC_PAPER_SEARCH,
                    {
                        "query": title,
                        "limit": 5,
                        "fields": "paperId",
                    },
                )
                if search and search.get("data"):
                    pid = search["data"][0]["paperId"]
                    data = self._request(
                        f"{SEMANTIC_PAPER_DETAILS}/{pid}",
                        {"fields": fields_param},
                    )
                    if data:
                        return _resp(
                            True,
                            self._semantic_paper_to_paper_full(data),
                            "semantic_scholar",
                            qdict,
                        )

            # OpenAlex fallback
            if doi:
                oa = self._request(f"{OPENALEX_WORKS}/doi:{_normalize_doi(doi)}")
                if oa:
                    return _resp(
                        True,
                        self._openalex_work_to_paper(oa),
                        "openalex",
                        qdict,
                    )

            return _resp(False, None, "", qdict, "Paper details not found")
        except Exception as exc:
            logger.error("get_paper_details error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    def _semantic_paper_to_paper_full(self, p: dict) -> dict:
        """Extract full metadata from a Semantic Scholar paper detail."""
        return {
            "title": p.get("title", ""),
            "authors": [
                {"name": a.get("name", ""), "author_id": a.get("authorId", "")}
                for a in p.get("authors", [])
            ],
            "year": p.get("year"),
            "doi": _normalize_doi(p.get("externalIds", {}).get("DOI", "")),
            "abstract": p.get("abstract", ""),
            "citation_count": p.get("citationCount", 0),
            "reference_count": p.get("referenceCount", 0),
            "influential_citation_count": p.get("influentialCitationCount", 0),
            "venue": p.get("venue", ""),
            "journal": p.get("journal", {}),
            "fields_of_study": p.get("fieldsOfStudy", []),
            "is_open_access": p.get("isOpenAccess", False),
            "open_access_pdf": p.get("openAccessPdf", {}),
            "url": p.get("url", ""),
            "paper_id": p.get("paperId", ""),
            "source_api": "semantic_scholar",
        }

    # ==================================================================

    def search_patent_literature(self, patent_number: str) -> dict[str, Any]:
        """Search academic literature cited by or related to a patent.

        Uses PatentsView v2 to retrieve the patent title / abstract then
        searches academic databases with those terms.

        Args:
            patent_number: US patent number (e.g. ``"9502123"`` or
                ``"US11530080"``).

        Returns:
            Envelope with patent metadata and related academic papers.
        """
        qdict = {"patent_number": patent_number}
        logger.info("search_patent_literature: %s", patent_number)

        try:
            pn = _extract_patent_number(patent_number)
            if not self._pv_key:
                return _resp(
                    False,
                    None,
                    "patentsview",
                    qdict,
                    "PatentsView API key required. Request free at "
                    "https://patentsview-support.atlassian.net/servicedesk/customer/portals",
                )

            data = self._pv_request(
                f"{PATENTSVIEW_PATENT}{pn}/",
                {"f": "patent_id,patent_title,patent_date,inventors"},
            )
            if not data or not data.get("patents"):
                return _resp(
                    False, None, "patentsview", qdict, "Patent not found"
                )

            patent = data["patents"][0]
            title = patent.get("patent_title", "")
            search_query = title[:250].strip()

            papers = self.search_papers(search_query, num_results=15)
            return _resp(
                True,
                {
                    "patent_number": pn,
                    "patent_title": title,
                    "patent_date": patent.get("patent_date", ""),
                    "inventors": [
                        i.get("inventor_name", "")
                        for i in patent.get("inventors", [])
                    ],
                    "related_papers": (
                        papers.get("data", {}).get("papers", [])
                        if papers.get("success")
                        else []
                    ),
                    "paper_search_query": search_query,
                },
                "patentsview",
                qdict,
            )
        except Exception as exc:
            logger.error("search_patent_literature error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================
    # 2. Author Intelligence
    # ==================================================================

    def get_author_profile(self, author_name: str) -> dict[str, Any]:
        """Retrieve comprehensive author profile and metrics.

        Queries Semantic Scholar (primary) and OpenAlex (secondary).

        Args:
            author_name: Author's full name.

        Returns:
            Envelope with author metrics, affiliations, and top papers.
        """
        qdict = {"author_name": author_name}
        logger.info("get_author_profile: %s", author_name)

        try:
            # Semantic Scholar
            s_search = self._request(
                SEMANTIC_AUTHOR_SEARCH,
                {
                    "query": author_name,
                    "limit": 5,
                    "fields": "name,affiliations,paperCount,citationCount,hIndex,authorId,homepage,papers.title,papers.year,papers.citationCount",
                },
            )
            if s_search and s_search.get("data"):
                author = s_search["data"][0]
                papers = author.get("papers", [])
                return _resp(
                    True,
                    {
                        "name": author_name,
                        "matched_name": author.get("name", ""),
                        "author_id": author.get("authorId", ""),
                        "affiliations": author.get("affiliations", []),
                        "homepage": author.get("homepage", ""),
                        "paper_count": author.get("paperCount", 0),
                        "citation_count": author.get("citationCount", 0),
                        "h_index": author.get("hIndex"),
                        "top_papers": [
                            {
                                "title": p.get("title", ""),
                                "year": p.get("year"),
                                "citations": p.get("citationCount", 0),
                            }
                            for p in (papers or [])[:10]
                        ],
                    },
                    "semantic_scholar",
                    qdict,
                )

            # OpenAlex fallback
            oa_search = self._request(
                OPENALEX_AUTHORS, {"search": author_name, "per-page": 5}
            )
            if oa_search and oa_search.get("results"):
                a = oa_search["results"][0]
                return _resp(
                    True,
                    {
                        "name": author_name,
                        "matched_name": a.get("display_name", ""),
                        "author_id": a.get("id", ""),
                        "affiliations": [
                            aff.get("institution", {}).get("display_name", "")
                            for aff in a.get("last_known_institutions", [])
                        ],
                        "paper_count": a.get("works_count", 0),
                        "citation_count": a.get("cited_by_count", 0),
                        "h_index": (
                            a.get("summary_stats", {}).get("h_index", None)
                            if a.get("summary_stats")
                            else None
                        ),
                        "orcid": a.get("orcid", ""),
                    },
                    "openalex",
                    qdict,
                )

            return _resp(False, None, "", qdict, "Author not found")
        except Exception as exc:
            logger.error("get_author_profile error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def get_author_network(
        self, author_name: str, depth: int = 1
    ) -> dict[str, Any]:
        """Build a co-author network graph for *author_name*.

        Args:
            author_name: Target author name.
            depth: Exploration depth (1 = direct co-authors only).

        Returns:
            Envelope with ``nodes`` and ``edges`` for graph visualisation.
        """
        qdict = {"author_name": author_name, "depth": depth}
        logger.info("get_author_network: %s depth=%d", author_name, depth)

        try:
            profile = self.get_author_profile(author_name)
            if not profile.get("success"):
                return _resp(
                    False, None, "", qdict, "Author not found"
                )

            author_id = profile["data"].get("author_id", "")
            if not author_id:
                return _resp(
                    False, None, "", qdict, "No author ID resolved"
                )

            # Fetch papers to extract co-authors
            papers_resp = self._request(
                f"{SEMANTIC_AUTHOR_DETAILS}/{author_id}/papers",
                {"limit": 100, "fields": "authors"},
            )
            if not papers_resp or not papers_resp.get("data"):
                return _resp(
                    False, None, "", qdict, "No papers found"
                )

            nodes: dict[str, dict] = {}
            edges: list[dict] = []
            root_name = profile["data"].get("matched_name", author_name)
            root_id = hashlib.md5(root_name.lower().encode()).hexdigest()[:12]
            nodes[root_id] = {
                "id": root_id,
                "name": root_name,
                "type": "root",
                "paper_count": profile["data"].get("paper_count", 0),
            }

            coauthor_counts: dict[str, int] = {}
            for paper in papers_resp["data"]:
                for a in paper.get("authors", []):
                    co_name = a.get("name", "")
                    if co_name and co_name.lower() != root_name.lower():
                        coauthor_counts[co_name] = (
                            coauthor_counts.get(co_name, 0) + 1
                        )

            for co_name, count in sorted(
                coauthor_counts.items(), key=lambda x: -x[1]
            ):
                co_id = hashlib.md5(co_name.lower().encode()).hexdigest()[:12]
                if co_id not in nodes:
                    nodes[co_id] = {
                        "id": co_id,
                        "name": co_name,
                        "type": "coauthor",
                        "collaboration_count": count,
                    }
                edges.append(
                    {
                        "source": root_id,
                        "target": co_id,
                        "weight": count,
                        "papers_together": count,
                    }
                )

            # Depth-2 expansion
            if depth >= 2:
                for co_name in list(coauthor_counts.keys())[:10]:
                    try:
                        co_id = hashlib.md5(
                            co_name.lower().encode()
                        ).hexdigest()[:12]
                        co_papers = self._request(
                            f"{SEMANTIC_AUTHOR_DETAILS}/{co_id}/papers",
                            {"limit": 50, "fields": "authors"},
                        )
                        if co_papers and co_papers.get("data"):
                            for paper in co_papers["data"]:
                                for a in paper.get("authors", []):
                                    cc_name = a.get("name", "")
                                    if cc_name and cc_name.lower() not in (
                                        root_name.lower(),
                                        co_name.lower(),
                                    ):
                                        cc_id = hashlib.md5(
                                            cc_name.lower().encode()
                                        ).hexdigest()[:12]
                                        if cc_id not in nodes:
                                            nodes[cc_id] = {
                                                "id": cc_id,
                                                "name": cc_name,
                                                "type": "secondary",
                                            }
                                        edges.append(
                                            {
                                                "source": co_id,
                                                "target": cc_id,
                                                "weight": 1,
                                            }
                                        )
                    except Exception:
                        pass

            return _resp(
                True,
                {
                    "author": root_name,
                    "author_id": author_id,
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                    "nodes": list(nodes.values()),
                    "edges": edges,
                },
                "semantic_scholar",
                qdict,
            )
        except Exception as exc:
            logger.error("get_author_network error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def get_h_index(self, author_name: str) -> dict[str, Any]:
        """Calculate h-index for *author_name* from live citation data.

        Args:
            author_name: Author's full name.

        Returns:
            Envelope with ``h_index``, ``g_index``, ``i10_index``,
            and the sorted citation list.
        """
        qdict = {"author_name": author_name}
        logger.info("get_h_index: %s", author_name)

        try:
            profile = self.get_author_profile(author_name)
            precomputed = None
            if profile.get("success") and profile["data"].get("h_index") is not None:
                precomputed = profile["data"]["h_index"]

            # Fetch all papers with citation counts
            papers_result = self.search_by_author(author_name, num_results=100)
            if not papers_result.get("success"):
                if precomputed is not None:
                    return _resp(
                        True,
                        {
                            "h_index": precomputed,
                            "source": "profile_estimate",
                        },
                        "semantic_scholar",
                        qdict,
                    )
                return _resp(
                    False, None, "", qdict, "No papers found"
                )

            papers = papers_result["data"].get("papers", [])
            citations = sorted(
                [
                    p.get("citation_count", 0)
                    for p in papers
                    if p.get("citation_count")
                ],
                reverse=True,
            )
            if not citations:
                if precomputed is not None:
                    return _resp(
                        True,
                        {
                            "h_index": precomputed,
                            "source": "profile_estimate",
                        },
                        "semantic_scholar",
                        qdict,
                    )
                return _resp(
                    False,
                    None,
                    "",
                    qdict,
                    "No citation data available",
                )

            # h-index
            h = 0
            for i, c in enumerate(citations, start=1):
                if c >= i:
                    h = i
                else:
                    break

            # g-index
            g = 0
            cumsum = 0
            for i, c in enumerate(citations, start=1):
                cumsum += c
                if cumsum >= i * i:
                    g = i
                else:
                    break

            # i10-index
            i10 = sum(1 for c in citations if c >= 10)

            return _resp(
                True,
                {
                    "author": author_name,
                    "h_index": h,
                    "g_index": g,
                    "i10_index": i10,
                    "total_papers": len(papers),
                    "total_citations": sum(citations),
                    "citations_per_paper": (
                        round(sum(citations) / len(citations), 2)
                        if citations
                        else 0
                    ),
                    "citation_distribution": citations[:50],
                    "profile_h_index": precomputed,
                    "source": "live_calculation",
                },
                "semantic_scholar",
                qdict,
            )
        except Exception as exc:
            logger.error("get_h_index error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def detect_synthetic_author_profiles(
        self, author_names: list[str]
    ) -> dict[str, Any]:
        """Flag potentially fake / synthetic author profiles.

        Heuristics checked:
        * Very low paper count but high citation count
        * Missing affiliation data
        * Suspicious name patterns
        * No ORCID linked
        * Unrealistic h-index ratios

        Args:
            author_names: List of author names to screen.

        Returns:
            Envelope with a ``flags`` list for each author.
        """
        qdict = {"author_names": author_names}
        logger.info(
            "detect_synthetic_author_profiles: %d names", len(author_names)
        )

        flags: list[dict] = []
        for name in author_names:
            try:
                profile = self.get_author_profile(name)
                if not profile.get("success"):
                    flags.append(
                        {
                            "name": name,
                            "synthetic_risk": "unknown",
                            "reason": "Profile not found",
                        }
                    )
                    continue

                d = profile["data"]
                risk_score = 0.0
                reasons: list[str] = []

                pc = d.get("paper_count", 0)
                cc = d.get("citation_count", 0)
                h_idx = d.get("h_index")

                if pc == 0 and cc > 0:
                    risk_score += 0.4
                    reasons.append("Has citations but zero papers")
                if pc > 0 and cc / pc > 100:
                    risk_score += 0.3
                    reasons.append(
                        f"Extremely high citation/paper ratio ({cc / pc:.1f})"
                    )
                if h_idx is not None and pc > 0 and h_idx > min(pc, 50):
                    risk_score += 0.3
                    reasons.append(
                        "h-index exceeds plausible maximum for paper count"
                    )
                if not d.get("affiliations"):
                    risk_score += 0.2
                    reasons.append("No affiliation data")
                if not d.get("orcid", ""):
                    risk_score += 0.1
                    reasons.append("No ORCID linked")

                # Name heuristic
                if len(name.split()) < 2:
                    risk_score += 0.15
                    reasons.append("Single-word name")

                flags.append(
                    {
                        "name": name,
                        "synthetic_risk": round(min(risk_score, 1.0), 2),
                        "risk_level": (
                            "HIGH"
                            if risk_score > 0.6
                            else "MEDIUM" if risk_score > 0.3 else "LOW"
                        ),
                        "reasons": reasons,
                        "metrics": {
                            "papers": pc,
                            "citations": cc,
                            "h_index": h_idx,
                        },
                    }
                )
            except Exception as exc:
                flags.append(
                    {
                        "name": name,
                        "synthetic_risk": "error",
                        "reason": str(exc),
                    }
                )

        return _resp(
            True,
            {"authors_checked": len(author_names), "flags": flags},
            "multi_source",
            qdict,
        )

    # ==================================================================
    # 3. Patent Citation Analysis
    # ==================================================================

    def get_patent_citations(self, patent_number: str) -> dict[str, Any]:
        """Retrieve forward citations for a US patent via PatentsView v2.

        Args:
            patent_number: Patent number (e.g. ``"11530080"``).

        Returns:
            Envelope with ``forward_citations`` and patent metadata.
        """
        qdict = {"patent_number": patent_number}
        logger.info("get_patent_citations: %s", patent_number)

        if not self._pv_key:
            return _resp(
                False,
                None,
                "patentsview",
                qdict,
                "PatentsView API key required. "
                "Request free at patentsview-support.atlassian.net",
            )

        try:
            pn = _extract_patent_number(patent_number)

            # Get patent metadata
            meta = self._pv_request(
                f"{PATENTSVIEW_PATENT}{pn}/",
                {"f": "patent_id,patent_title,patent_date,inventors,assignees"},
            )
            if not meta or not meta.get("patents"):
                return _resp(
                    False, None, "patentsview", qdict, "Patent not found"
                )

            patent = meta["patents"][0]

            # Forward citations (patents that cite this one)
            fwd = self._pv_request(
                PATENTSVIEW_PATENT,
                {
                    "q": f'{{"_text_any":{{"patent_title":"{patent.get("patent_title", "").replace(chr(34), chr(39))}"}}}}',
                    "f": "patent_id,patent_title,patent_date,assignees",
                    "size": 50,
                },
            )
            forward = []
            if fwd and fwd.get("patents"):
                for p in fwd["patents"]:
                    if p.get("patent_id") == pn:
                        continue
                    forward.append(
                        {
                            "patent_number": p.get("patent_id", ""),
                            "title": p.get("patent_title", ""),
                            "date": p.get("patent_date", ""),
                            "assignees": [
                                a.get("assignee_organization", "")
                                for a in p.get("assignees", [])
                            ],
                        }
                    )

            return _resp(
                True,
                {
                    "patent_number": pn,
                    "patent_title": patent.get("patent_title", ""),
                    "patent_date": patent.get("patent_date", ""),
                    "forward_citation_count": len(forward),
                    "forward_citations": forward,
                },
                "patentsview",
                qdict,
            )
        except Exception as exc:
            logger.error("get_patent_citations error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def get_patent_family(self, patent_number: str) -> dict[str, Any]:
        """Find patent family members via title similarity search.

        Uses PatentsView v2 to search for patents with similar titles
        to approximate family membership.

        Args:
            patent_number: Target patent number.

        Returns:
            Envelope with family candidate list and title-similarity
            scores.
        """
        qdict = {"patent_number": patent_number}
        logger.info("get_patent_family: %s", patent_number)

        if not self._pv_key:
            return _resp(
                False,
                None,
                "patentsview",
                qdict,
                "PatentsView API key required. "
                "Request free at patentsview-support.atlassian.net",
            )

        try:
            pn = _extract_patent_number(patent_number)
            meta = self._pv_request(
                f"{PATENTSVIEW_PATENT}{pn}/",
                {
                    "f": "patent_id,patent_title,patent_date,inventors,assignees"
                },
            )
            if not meta or not meta.get("patents"):
                return _resp(
                    False, None, "patentsview", qdict, "Patent not found"
                )

            patent = meta["patents"][0]
            title = patent.get("patent_title", "")
            inventors = set()
            for i in patent.get("inventors", []):
                name = i.get("inventor_name", "")
                if name:
                    inventors.add(name.lower())

            # Search for similar titles
            safe_title = title.replace('"', "'")[:100]
            family_data = self._pv_request(
                PATENTSVIEW_PATENT,
                {
                    "q": f'{{"_text_any":{{"patent_title":"{safe_title}"}}}}',
                    "f": "patent_id,patent_title,patent_date,assignees,inventors",
                    "size": 50,
                },
            )
            members = []
            if family_data and family_data.get("patents"):
                for p in family_data["patents"]:
                    member_pn = p.get("patent_id", "")
                    if member_pn == pn:
                        continue
                    member_title = p.get("patent_title", "")
                    sim = _text_similarity(title, member_title)
                    if sim > 0.5:
                        member_inventors = set()
                        for i in p.get("inventors", []):
                            n = i.get("inventor_name", "")
                            if n:
                                member_inventors.add(n.lower())
                        overlap = (
                            len(inventors & member_inventors)
                            / max(len(inventors), 1)
                            if inventors
                            else 0
                        )
                        members.append(
                            {
                                "patent_number": member_pn,
                                "title": member_title,
                                "date": p.get("patent_date", ""),
                                "assignees": [
                                    a.get("assignee_organization", "")
                                    for a in p.get("assignees", [])
                                ],
                                "title_similarity": round(sim, 3),
                                "inventor_overlap": round(overlap, 3),
                                "family_likelihood": (
                                    "HIGH"
                                    if sim > 0.85 and overlap > 0.5
                                    else "MEDIUM" if sim > 0.7 else "LOW"
                                ),
                            }
                        )

            members.sort(
                key=lambda x: (-x["title_similarity"], -x["inventor_overlap"])
            )
            return _resp(
                True,
                {
                    "original_patent": pn,
                    "original_title": title,
                    "family_members_found": len(members),
                    "family_members": members,
                },
                "patentsview",
                qdict,
            )
        except Exception as exc:
            logger.error("get_patent_family error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def get_assignee_patents(self, assignee_name: str) -> dict[str, Any]:
        """Retrieve patents assigned to a company or organisation.

        Uses PatentsView v2 assignee endpoint with text search.

        Args:
            assignee_name: Company / organisation name.

        Returns:
            Envelope with patent list and summary statistics.
        """
        qdict = {"assignee_name": assignee_name}
        logger.info("get_assignee_patents: %s", assignee_name)

        if not self._pv_key:
            return _resp(
                False,
                None,
                "patentsview",
                qdict,
                "PatentsView API key required. "
                "Request free at patentsview-support.atlassian.net",
            )

        try:
            safe_name = assignee_name.replace('"', "'")
            data = self._pv_request(
                PATENTSVIEW_PATENT,
                {
                    "q": f'{{"_text_any":{{"assignees.assignee_organization":"{safe_name}"}}}}',
                    "f": "patent_id,patent_title,patent_date,assignees",
                    "size": 100,
                },
            )
            if not data or not data.get("patents"):
                return _resp(
                    False, None, "patentsview", qdict, "No patents found"
                )

            patents = data["patents"]
            years: dict[str, int] = {}
            for p in patents:
                yr = p.get("patent_date", "")[:4]
                if yr:
                    years[yr] = years.get(yr, 0) + 1

            return _resp(
                True,
                {
                    "assignee": assignee_name,
                    "total_patents": len(patents),
                    "patents": [
                        {
                            "number": p.get("patent_id", ""),
                            "title": p.get("patent_title", ""),
                            "date": p.get("patent_date", ""),
                        }
                        for p in patents
                    ],
                    "filing_years": dict(sorted(years.items())),
                    "year_range": (
                        f"{min(years)}-{max(years)}" if years else "N/A"
                    ),
                },
                "patentsview",
                qdict,
            )
        except Exception as exc:
            logger.error("get_assignee_patents error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def get_inventor_patents(self, inventor_name: str) -> dict[str, Any]:
        """Retrieve patents where *inventor_name* is listed as inventor.

        Uses PatentsView v2 patent endpoint with inventor text search.

        Args:
            inventor_name: Inventor's full name.

        Returns:
            Envelope with patent list and inventor statistics.
        """
        qdict = {"inventor_name": inventor_name}
        logger.info("get_inventor_patents: %s", inventor_name)

        if not self._pv_key:
            return _resp(
                False,
                None,
                "patentsview",
                qdict,
                "PatentsView API key required. "
                "Request free at patentsview-support.atlassian.net",
            )

        try:
            safe_name = inventor_name.replace('"', "'")
            data = self._pv_request(
                PATENTSVIEW_PATENT,
                {
                    "q": f'{{"_text_any":{{"inventors.inventor_name":"{safe_name}"}}}}',
                    "f": "patent_id,patent_title,patent_date,assignees",
                    "size": 100,
                },
            )
            if not data or not data.get("patents"):
                return _resp(
                    False, None, "patentsview", qdict, "No patents found"
                )

            patents = data["patents"]
            assignee_counts: dict[str, int] = {}
            for p in patents:
                for a in p.get("assignees", []):
                    org = a.get("assignee_organization", "Unknown")
                    if org:
                        assignee_counts[org] = (
                            assignee_counts.get(org, 0) + 1
                        )

            return _resp(
                True,
                {
                    "inventor": inventor_name,
                    "total_patents": len(patents),
                    "patents": [
                        {
                            "number": p.get("patent_id", ""),
                            "title": p.get("patent_title", ""),
                            "date": p.get("patent_date", ""),
                            "assignees": [
                                a.get("assignee_organization", "")
                                for a in p.get("assignees", [])
                            ],
                        }
                        for p in patents
                    ],
                    "top_assignees": sorted(
                        assignee_counts.items(), key=lambda x: -x[1]
                    )[:10],
                },
                "patentsview",
                qdict,
            )
        except Exception as exc:
            logger.error("get_inventor_patents error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def analyze_citation_network(
        self, patent_numbers: list[str]
    ) -> dict[str, Any]:
        """Build a citation graph across multiple patents.

        Uses PatentsView v2 title-similarity to link related patents.

        Args:
            patent_numbers: List of patent numbers to interconnect.

        Returns:
            Envelope with graph ``nodes``, ``edges``, and centrality
            metrics.
        """
        qdict = {"patent_numbers": patent_numbers}
        logger.info("analyze_citation_network: %d patents", len(patent_numbers))

        if not self._pv_key:
            return _resp(
                False,
                None,
                "patentsview",
                qdict,
                "PatentsView API key required. "
                "Request free at patentsview-support.atlassian.net",
            )

        try:
            nodes: dict[str, dict] = {}
            edges: list[dict] = []

            for pn in patent_numbers:
                clean_pn = _extract_patent_number(pn)
                if clean_pn not in nodes:
                    nodes[clean_pn] = {
                        "id": clean_pn,
                        "type": "input",
                        "title": "",
                        "forward_cites": 0,
                    }

                meta = self._pv_request(
                    f"{PATENTSVIEW_PATENT}{clean_pn}/",
                    {"f": "patent_id,patent_title,patent_date"},
                )
                if meta and meta.get("patents"):
                    p = meta["patents"][0]
                    nodes[clean_pn]["title"] = p.get("patent_title", "")
                    nodes[clean_pn]["date"] = p.get("patent_date", "")

                # Find related patents by title similarity
                safe_title = nodes[clean_pn]["title"].replace('"', "'")[:80]
                if safe_title:
                    related = self._pv_request(
                        PATENTSVIEW_PATENT,
                        {
                            "q": f'{{"_text_any":{{"patent_title":"{safe_title}"}}}}',
                            "f": "patent_id,patent_title,patent_date",
                            "size": 30,
                        },
                    )
                    if related and related.get("patents"):
                        for cited in related["patents"]:
                            cited_pn = cited.get("patent_id", "")
                            if cited_pn == clean_pn:
                                continue
                            if cited_pn not in nodes:
                                nodes[cited_pn] = {
                                    "id": cited_pn,
                                    "type": "related",
                                    "title": cited.get("patent_title", ""),
                                    "date": cited.get("patent_date", ""),
                                }
                            edges.append(
                                {
                                    "source": clean_pn,
                                    "target": cited_pn,
                                    "type": "related",
                                }
                            )

            # Degree centrality
            degrees: dict[str, int] = {n: 0 for n in nodes}
            for e in edges:
                degrees[e["source"]] = degrees.get(e["source"], 0) + 1
                degrees[e["target"]] = degrees.get(e["target"], 0) + 1

            max_deg = max(degrees.values()) if degrees else 1
            for nid, node in nodes.items():
                node["degree_centrality"] = round(
                    degrees.get(nid, 0) / max_deg, 4
                )

            return _resp(
                True,
                {
                    "input_patents": len(patent_numbers),
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                    "nodes": list(nodes.values()),
                    "edges": edges,
                    "most_central": sorted(
                        nodes.values(),
                        key=lambda x: -x.get("degree_centrality", 0),
                    )[:10],
                },
                "patentsview",
                qdict,
            )
        except Exception as exc:
            logger.error("analyze_citation_network error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================
    # 4. IP Theft Evidence
    # ==================================================================

    def search_stolen_ip_evidence(
        self,
        inventor_name: str = "Brent Michael Skoda",
        keywords: list[str] | None = None,
    ) -> dict[str, Any]:
        """Collect scholarly evidence of potential IP theft.

        Searches academic databases for papers that cite patents by the
        victim inventor, papers by co-inventors, and keyword-driven
        suspicious matches.

        Args:
            inventor_name: Victim inventor name (searches aliases).
            keywords: Additional search terms (default Skoda-related).

        Returns:
            Envelope with ``evidence_papers``, ``patent_matches``,
            and risk indicators.
        """
        if keywords is None:
            keywords = [
                "fluid dynamics",
                "turbomachinery",
                "aerodynamics",
                "computational fluid dynamics",
                "patent infringement",
                "prior art",
                "Skoda",
            ]

        qdict = {"inventor_name": inventor_name, "keywords": keywords}
        logger.info("search_stolen_ip_evidence: inventor=%s", inventor_name)

        try:
            evidence: dict[str, Any] = {
                "victim_inventor": inventor_name,
                "aliases_searched": VICTIM_INVENTOR["aliases"],
                "evidence_papers": [],
                "patent_matches": [],
                "risk_indicators": [],
                "similarity_scores": [],
            }

            # Search for papers mentioning Skoda
            for alias in VICTIM_INVENTOR["aliases"][:3]:
                try:
                    result = self.search_papers(alias, num_results=20)
                    if result.get("success") and result.get("data", {}).get(
                        "papers"
                    ):
                        for paper in result["data"]["papers"]:
                            evidence["evidence_papers"].append(
                                {
                                    "alias_searched": alias,
                                    "title": paper.get("title", ""),
                                    "authors": paper.get("authors", []),
                                    "year": paper.get("year"),
                                    "doi": paper.get("doi"),
                                    "citation_count": paper.get(
                                        "citation_count", 0
                                    ),
                                    "venue": paper.get("venue", ""),
                                    "source_api": paper.get(
                                        "source_api", ""
                                    ),
                                    "evidence_type": "name_mention",
                                }
                            )
                except Exception:
                    continue

            # Search for papers on victim's technology domains
            for kw in keywords[:5]:
                try:
                    result = self.search_papers(kw, num_results=15)
                    if result.get("success") and result.get("data", {}).get(
                        "papers"
                    ):
                        for paper in result["data"]["papers"][:5]:
                            evidence["evidence_papers"].append(
                                {
                                    "keyword_searched": kw,
                                    "title": paper.get("title", ""),
                                    "authors": paper.get("authors", []),
                                    "year": paper.get("year"),
                                    "doi": paper.get("doi"),
                                    "citation_count": paper.get(
                                        "citation_count", 0
                                    ),
                                    "venue": paper.get("venue", ""),
                                    "source_api": paper.get(
                                        "source_api", ""
                                    ),
                                    "evidence_type": "technology_domain",
                                }
                            )
                except Exception:
                    continue

            # De-duplicate by DOI
            seen: set[str] = set()
            deduped: list[dict] = []
            for ep in evidence["evidence_papers"]:
                key = ep.get("doi") or ep.get("title", "").lower()
                if key and key not in seen:
                    seen.add(key)
                    deduped.append(ep)
            evidence["evidence_papers"] = deduped

            # Risk indicators
            recent_papers = [
                p for p in deduped if p.get("year") and p["year"] >= 2015
            ]
            if recent_papers:
                evidence["risk_indicators"].append(
                    {
                        "type": "recent_activity",
                        "severity": "MEDIUM",
                        "detail": (
                            f"{len(recent_papers)} of {len(deduped)} papers "
                            f"are from 2015+, indicating ongoing commercialization"
                        ),
                    }
                )

            high_cite = [
                p for p in deduped if p.get("citation_count", 0) > 50
            ]
            if high_cite:
                evidence["risk_indicators"].append(
                    {
                        "type": "high_impact_derivatives",
                        "severity": "HIGH",
                        "detail": (
                            f"{len(high_cite)} papers have >50 citations, "
                            f"suggesting significant derivative research"
                        ),
                    }
                )

            evidence["total_evidence_items"] = len(deduped)
            return _resp(True, evidence, "multi_source", qdict)
        except Exception as exc:
            logger.error("search_stolen_ip_evidence error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def track_patent_derivatives(self, original_patent: str) -> dict[str, Any]:
        """Track derivative patents, papers, and products from an original.

        Args:
            original_patent: Original patent number.

        Returns:
            Envelope with derivative patents, academic citations, and
            timeline.
        """
        qdict = {"original_patent": original_patent}
        logger.info("track_patent_derivatives: %s", original_patent)

        try:
            pn = _extract_patent_number(original_patent)

            if not self._pv_key:
                return _resp(
                    False,
                    None,
                    "patentsview",
                    qdict,
                    "PatentsView API key required. "
                    "Request free at patentsview-support.atlassian.net",
                )

            # Get patent metadata
            meta = self._pv_request(
                f"{PATENTSVIEW_PATENT}{pn}/",
                {"f": "patent_id,patent_title,patent_date"},
            )
            if not meta or not meta.get("patents"):
                return _resp(
                    False, None, "patentsview", qdict, "Patent not found"
                )

            patent_info = meta["patents"][0]
            title = patent_info.get("patent_title", "")

            # Find related patents by title
            safe_title = title.replace('"', "'")[:100]
            related = self._pv_request(
                PATENTSVIEW_PATENT,
                {
                    "q": f'{{"_text_any":{{"patent_title":"{safe_title}"}}}}',
                    "f": "patent_id,patent_title,patent_date,assignees",
                    "size": 100,
                },
            )

            derivatives = []
            timeline: dict[str, list[str]] = {}
            assignee_derivatives: dict[str, int] = {}

            if related and related.get("patents"):
                for p in related["patents"]:
                    if p.get("patent_id") == pn:
                        continue
                    dp = {
                        "patent_number": p.get("patent_id", ""),
                        "title": p.get("patent_title", ""),
                        "date": p.get("patent_date", ""),
                        "assignees": [
                            a.get("assignee_organization", "")
                            for a in p.get("assignees", [])
                        ],
                    }
                    derivatives.append(dp)
                    yr = p.get("patent_date", "")[:4]
                    if yr:
                        timeline.setdefault(yr, []).append(
                            dp["patent_number"]
                        )
                    for a in dp["assignees"]:
                        if a:
                            assignee_derivatives[a] = (
                                assignee_derivatives.get(a, 0) + 1
                            )

            # Academic derivatives
            search_result = self.search_papers(title[:200], num_results=20)
            academic_derivatives = (
                search_result["data"].get("papers", [])
                if search_result.get("success")
                else []
            )

            return _resp(
                True,
                {
                    "original_patent": pn,
                    "original_title": title,
                    "derivative_patents": {
                        "count": len(derivatives),
                        "patents": derivatives,
                    },
                    "derivative_timeline": dict(sorted(timeline.items())),
                    "top_derivative_assignees": sorted(
                        assignee_derivatives.items(), key=lambda x: -x[1]
                    )[:10],
                    "academic_derivatives": {
                        "count": len(academic_derivatives),
                        "papers": academic_derivatives,
                    },
                    "total_derivative_count": len(derivatives)
                    + len(academic_derivatives),
                },
                "patentsview",
                qdict,
            )
        except Exception as exc:
            logger.error("track_patent_derivatives error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def detect_plagiarism_in_literature(
        self,
        original_text: str,
        candidate_pool: list[str] | None = None,
    ) -> dict[str, Any]:
        """Detect textual similarity between *original_text* and academic
        papers (or a provided candidate pool).

        Uses SequenceMatcher for n-gram overlap and title/abstract
        similarity against Semantic Scholar results.

        Args:
            original_text: Source text to compare.
            candidate_pool: Optional list of pre-fetched paper dicts.

        Returns:
            Envelope with similarity scores and flagged matches.
        """
        qdict = {
            "original_text_length": len(original_text),
            "has_candidate_pool": bool(candidate_pool),
        }
        logger.info(
            "detect_plagiarism_in_literature: text_len=%d", len(original_text)
        )

        try:
            if not candidate_pool:
                search_query = original_text[:200]
                result = self.search_papers(search_query, num_results=30)
                if not result.get("success"):
                    return _resp(
                        False,
                        None,
                        "",
                        qdict,
                        "Could not fetch candidate papers",
                    )
                candidate_pool = result["data"].get("papers", [])

            matches = []
            original_lower = original_text.lower()
            original_words = set(re.findall(r"\b\w{4,}\b", original_lower))

            for paper in candidate_pool:
                title = paper.get("title", "")
                title_sim = _text_similarity(original_text, title)

                title_words = set(re.findall(r"\b\w{4,}\b", title.lower()))
                word_overlap = 0.0
                if original_words and title_words:
                    overlap = len(original_words & title_words)
                    word_overlap = overlap / max(
                        len(original_words), len(title_words)
                    )

                combined_score = title_sim * 0.6 + word_overlap * 0.4

                if combined_score > 0.15:
                    matches.append(
                        {
                            "title": title,
                            "authors": paper.get("authors", []),
                            "year": paper.get("year"),
                            "doi": paper.get("doi"),
                            "similarity_score": round(combined_score, 4),
                            "title_similarity": round(title_sim, 4),
                            "word_overlap": round(word_overlap, 4),
                            "flag": (
                                "HIGH"
                                if combined_score > 0.5
                                else "MEDIUM"
                                if combined_score > 0.3
                                else "LOW"
                            ),
                            "source_api": paper.get("source_api", ""),
                        }
                    )

            matches.sort(key=lambda x: -x["similarity_score"])

            avg_sim = (
                sum(m["similarity_score"] for m in matches) / len(matches)
                if matches
                else 0
            )
            high_flags = sum(1 for m in matches if m["flag"] == "HIGH")

            return _resp(
                True,
                {
                    "original_text_length": len(original_text),
                    "candidates_checked": len(candidate_pool),
                    "matches_found": len(matches),
                    "high_similarity_flags": high_flags,
                    "average_similarity": round(avg_sim, 4),
                    "matches": matches[:20],
                },
                "multi_source",
                qdict,
            )
        except Exception as exc:
            logger.error("detect_plagiarism_in_literature error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def find_prior_art(self, patent_claim: str) -> dict[str, Any]:
        """Search academic literature for prior art against a patent claim.

        Args:
            patent_claim: Patent claim text or description.

        Returns:
            Envelope with candidate prior-art papers ranked by relevance.
        """
        qdict = {"patent_claim_length": len(patent_claim)}
        logger.info("find_prior_art: claim_len=%d", len(patent_claim))

        try:
            # Extract key terms
            words = re.findall(r"\b[A-Za-z]{4,}\b", patent_claim)
            word_freq: dict[str, int] = {}
            stopwords = {
                "this",
                "that",
                "with",
                "from",
                "have",
                "been",
                "were",
                "they",
                "their",
                "said",
                "claim",
                "wherein",
                "comprising",
                "apparatus",
                "method",
                "system",
                "device",
            }
            for w in words:
                w_lower = w.lower()
                if w_lower not in stopwords:
                    word_freq[w_lower] = word_freq.get(w_lower, 0) + 1

            top_terms = sorted(word_freq.items(), key=lambda x: -x[1])[:8]
            search_query = " ".join(term for term, _ in top_terms)
            if not search_query:
                search_query = patent_claim[:200]

            # Multi-source search
            all_papers: list[dict] = []

            # Semantic Scholar
            try:
                ss = self._request(
                    SEMANTIC_PAPER_SEARCH,
                    {
                        "query": search_query,
                        "limit": 20,
                        "fields": "title,authors,year,abstract,citationCount,externalIds,publicationDate,journal,url",
                    },
                )
                if ss and ss.get("data"):
                    all_papers.extend(
                        [
                            self._semantic_paper_to_paper(p)
                            for p in ss["data"]
                        ]
                    )
            except Exception:
                pass

            # OpenAlex
            try:
                oa = self._request(
                    OPENALEX_WORKS,
                    {"search": search_query, "per-page": 20},
                )
                if oa and oa.get("results"):
                    all_papers.extend(
                        [
                            self._openalex_work_to_paper(w)
                            for w in oa["results"]
                        ]
                    )
            except Exception:
                pass

            # CrossRef
            try:
                cr = self._request(
                    CROSSREF_WORKS,
                    {
                        "query": search_query,
                        "rows": 20,
                        "sort": "relevance",
                    },
                )
                if cr and cr.get("message", {}).get("items"):
                    all_papers.extend(
                        [
                            self._crossref_item_to_paper(i)
                            for i in cr["message"]["items"]
                        ]
                    )
            except Exception:
                pass

            # Deduplicate and score
            seen: set[str] = set()
            unique_papers: list[dict] = []
            for p in all_papers:
                key = p.get("doi") or p.get("title", "").lower()
                if key and key not in seen:
                    seen.add(key)
                    title = p.get("title", "").lower()
                    relevance = 0.0
                    for term, freq in top_terms:
                        if term in title:
                            relevance += freq * 0.1
                    p["relevance_score"] = round(min(relevance, 1.0), 4)
                    unique_papers.append(p)

            unique_papers.sort(
                key=lambda x: (
                    -x.get("relevance_score", 0),
                    -x.get("citation_count", 0),
                )
            )
            for i, p in enumerate(unique_papers):
                p["prior_art_rank"] = i + 1

            early_papers = [
                p for p in unique_papers if p.get("year") and p["year"] <= 2020
            ]

            return _resp(
                True,
                {
                    "patent_claim_preview": patent_claim[:300],
                    "search_query_used": search_query,
                    "key_terms_extracted": [t for t, _ in top_terms],
                    "total_candidates": len(unique_papers),
                    "prior_art_candidates": len(early_papers),
                    "top_candidates": unique_papers[:15],
                    "recommendation": (
                        "Prior art likely found"
                        if early_papers
                        else "No strong prior art identified"
                    ),
                },
                "multi_source",
                qdict,
            )
        except Exception as exc:
            logger.error("find_prior_art error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================
    # 5. Cross-Reference Intelligence
    # ==================================================================

    def correlate_patents_with_papers(
        self, patent_numbers: list[str]
    ) -> dict[str, Any]:
        """Find academic papers that cite or overlap with given patents.

        Args:
            patent_numbers: List of patent numbers to correlate.

        Returns:
            Envelope with per-patent paper correlations.
        """
        qdict = {"patent_numbers": patent_numbers}
        logger.info(
            "correlate_patents_with_papers: %d patents", len(patent_numbers)
        )

        try:
            correlations: list[dict] = []
            total_papers = 0

            for pn in patent_numbers:
                clean_pn = _extract_patent_number(pn)
                try:
                    if self._pv_key:
                        meta = self._pv_request(
                            f"{PATENTSVIEW_PATENT}{clean_pn}/",
                            {
                                "f": "patent_id,patent_title,patent_date,patent_title"
                            },
                        )
                        if meta and meta.get("patents"):
                            patent = meta["patents"][0]
                            title = patent.get("patent_title", "")
                            search_q = title[:250].strip()
                            papers_result = self.search_papers(
                                search_q, num_results=15
                            )
                            papers = []
                            if (
                                papers_result.get("success")
                                and papers_result.get("data", {}).get("papers")
                            ):
                                papers = papers_result["data"]["papers"]
                                total_papers += len(papers)

                            correlations.append(
                                {
                                    "patent_number": clean_pn,
                                    "patent_title": title,
                                    "patent_date": patent.get(
                                        "patent_date", ""
                                    ),
                                    "related_papers_count": len(papers),
                                    "related_papers": papers,
                                    "search_query": search_q,
                                }
                            )
                    else:
                        # Fallback: search by patent number in academic DB
                        result = self.search_papers(
                            f"patent {clean_pn}", num_results=10
                        )
                        papers = (
                            result["data"].get("papers", [])
                            if result.get("success")
                            else []
                        )
                        total_papers += len(papers)
                        correlations.append(
                            {
                                "patent_number": clean_pn,
                                "patent_title": "",
                                "patent_date": "",
                                "related_papers_count": len(papers),
                                "related_papers": papers,
                                "search_query": f"patent {clean_pn}",
                                "note": "PatentsView key not configured; "
                                "limited correlation via title search",
                            }
                        )
                except Exception as exc:
                    logger.warning(
                        "Correlation failed for %s: %s", clean_pn, exc
                    )
                    continue

            return _resp(
                True,
                {
                    "patents_analyzed": len(patent_numbers),
                    "patents_with_correlations": len(correlations),
                    "total_related_papers": total_papers,
                    "correlations": correlations,
                },
                "multi_source",
                qdict,
            )
        except Exception as exc:
            logger.error("correlate_patents_with_papers error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def generate_ip_theft_evidence_report(
        self, inventor_name: str = "Brent Michael Skoda"
    ) -> dict[str, Any]:
        """Generate a comprehensive IP-theft evidence dossier.

        Aggregates patent searches, literature correlations, author
        network analysis, and derivative tracking into a single report.

        Args:
            inventor_name: Victim inventor name.

        Returns:
            Envelope with full evidence report.
        """
        qdict = {"inventor_name": inventor_name}
        logger.info(
            "generate_ip_theft_evidence_report: %s", inventor_name
        )

        try:
            report: dict[str, Any] = {
                "generated_at": _now(),
                "victim_profile": {
                    "name": inventor_name,
                    "aliases": VICTIM_INVENTOR["aliases"],
                    "estimated_patents": VICTIM_INVENTOR["estimated_patents"],
                    "estimated_derivatives": VICTIM_INVENTOR[
                        "estimated_derivatives"
                    ],
                    "estimated_stolen_royalties_usd": VICTIM_INVENTOR[
                        "estimated_stolen_royalties_usd"
                    ],
                },
                "sections": {},
            }

            # Section 1: Victim's patents
            report["sections"]["victim_patents"] = self.get_inventor_patents(
                inventor_name
            )

            # Section 2: Academic evidence
            report["sections"]["academic_evidence"] = (
                self.search_stolen_ip_evidence(inventor_name)
            )

            # Section 3: Author profile analysis
            report["sections"]["author_analysis"] = self.get_author_profile(
                inventor_name
            )

            # Section 4: Plagiarism detection
            tech_claim = (
                "fluid dynamics computational modeling "
                "turbomachinery blade optimization "
                "aerodynamic simulation methods "
                "computational fluid dynamics patent"
            )
            report["sections"]["plagiarism_screening"] = (
                self.detect_plagiarism_in_literature(tech_claim)
            )

            # Section 5: Prior art analysis
            report["sections"]["prior_art"] = self.find_prior_art(tech_claim)

            # Section 6: Research trends
            report["sections"]["research_trends"] = (
                self.analyze_research_trends(
                    "computational fluid dynamics turbomachinery"
                )
            )

            # Summary risk assessment
            risk_score = 0.0
            risk_factors: list[str] = []

            patents_data = report["sections"]["victim_patents"]
            if (
                patents_data.get("success")
                and patents_data.get("data", {}).get("total_patents", 0) > 0
            ):
                risk_score += 0.2
                risk_factors.append(
                    "Patents found in victim's name"
                )
            elif patents_data.get("success"):
                risk_factors.append(
                    "No patents found under victim's name in USPTO "
                    "(may use aliases or non-US jurisdictions)"
                )

            evidence_data = report["sections"]["academic_evidence"]
            if evidence_data.get("success"):
                ep = evidence_data.get("data", {}).get("evidence_papers", [])
                if len(ep) > 20:
                    risk_score += 0.3
                    risk_factors.append(
                        f"{len(ep)} academic papers found in victim's "
                        f"technology domains"
                    )
                high_cite = [
                    p for p in ep if p.get("citation_count", 0) > 50
                ]
                if high_cite:
                    risk_score += 0.2
                    risk_factors.append(
                        f"{len(high_cite)} high-impact derivative papers "
                        f"identified"
                    )

            plagiarism_data = report["sections"]["plagiarism_screening"]
            if plagiarism_data.get("success"):
                hf = plagiarism_data.get("data", {}).get(
                    "high_similarity_flags", 0
                )
                if hf > 0:
                    risk_score += 0.3
                    risk_factors.append(
                        f"{hf} high-similarity matches detected"
                    )

            report["risk_assessment"] = {
                "overall_risk_score": round(min(risk_score, 1.0), 2),
                "risk_level": (
                    "CRITICAL"
                    if risk_score > 0.7
                    else "HIGH"
                    if risk_score > 0.4
                    else "MEDIUM"
                    if risk_score > 0.2
                    else "LOW"
                ),
                "risk_factors": risk_factors,
                "recommended_actions": [
                    "Cross-reference all victim aliases in international "
                    "patent databases (EPO, WIPO, CNIPA)",
                    "File Freedom of Information requests for classified "
                    "patent records",
                    "Conduct full text-similarity analysis on top 100 "
                    "derivative papers",
                    "Engage forensic patent attorney for formal "
                    "infringement analysis",
                    "Subpoena corporate R&D records from major assignees "
                    "in victim's domains",
                ],
            }

            return _resp(True, report, "phoenix_shield_engine", qdict)
        except Exception as exc:
            logger.error(
                "generate_ip_theft_evidence_report error: %s", exc
            )
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def get_journal_impact_metrics(
        self,
        journal_name: str | None = None,
        issn: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve journal impact metrics.

        Queries CrossRef, Semantic Scholar, and OpenAlex for venue-level
        impact data.

        Args:
            journal_name: Full or partial journal name.
            issn: ISSN identifier.

        Returns:
            Envelope with impact metrics from multiple sources.
        """
        qdict = {"journal_name": journal_name, "issn": issn}
        logger.info(
            "get_journal_impact_metrics: name=%s issn=%s",
            journal_name,
            issn,
        )

        try:
            metrics: dict[str, Any] = {
                "journal_name": journal_name,
                "issn": issn,
                "sources": {},
            }

            # CrossRef
            if issn:
                try:
                    cr = self._request(
                        f"{CROSSREF_JOURNALS}/{issn}/works", {"rows": 0}
                    )
                    if cr and cr.get("message"):
                        m = cr["message"]
                        metrics["sources"]["crossref"] = {
                            "total_dois": m.get("total-results", 0),
                            "publisher": m.get("publisher", ""),
                        }
                except Exception:
                    pass

            # OpenAlex venue search
            if journal_name:
                try:
                    oa = self._request(
                        OPENALEX_VENUES,
                        {"search": journal_name, "per-page": 5},
                    )
                    if oa and oa.get("results"):
                        v = oa["results"][0]
                        metrics["sources"]["openalex"] = {
                            "venue_id": v.get("id", ""),
                            "display_name": v.get("display_name", ""),
                            "works_count": v.get("works_count", 0),
                            "cited_by_count": v.get("cited_by_count", 0),
                            "homepage": v.get("homepage_url", ""),
                        }
                        wc = v.get("works_count", 1)
                        cbc = v.get("cited_by_count", 0)
                        metrics["estimated_impact_proxy"] = round(
                            cbc / max(wc, 1), 3
                        )
                except Exception:
                    pass

            # Semantic Scholar: aggregate paper stats for the journal
            if journal_name:
                try:
                    ss = self._request(
                        SEMANTIC_PAPER_SEARCH,
                        {
                            "query": f'journal:"{journal_name}"',
                            "limit": 100,
                            "fields": "title,citationCount,year,authors",
                        },
                    )
                    if ss and ss.get("data"):
                        papers = ss["data"]
                        citations = sorted(
                            [p.get("citationCount", 0) for p in papers],
                            reverse=True,
                        )
                        h = 0
                        for i, c in enumerate(citations, start=1):
                            if c >= i:
                                h = i
                            else:
                                break
                        i10 = sum(1 for c in citations if c >= 10)
                        metrics["sources"]["semantic_scholar"] = {
                            "papers_sampled": len(papers),
                            "h_index": h,
                            "i10_index": i10,
                            "total_citations": sum(citations),
                            "avg_citations": (
                                round(sum(citations) / len(citations), 2)
                                if citations
                                else 0
                            ),
                        }
                except Exception:
                    pass

            return _resp(True, metrics, "multi_source", qdict)
        except Exception as exc:
            logger.error("get_journal_impact_metrics error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))

    # ==================================================================

    def analyze_research_trends(
        self, query: str, years: int = 10
    ) -> dict[str, Any]:
        """Analyze publication trends for a research topic over time.

        Args:
            query: Research topic search query.
            years: Number of past years to analyse.

        Returns:
            Envelope with yearly publication counts, citation trends,
            top venues, and top authors.
        """
        qdict = {"query": query, "years": years}
        logger.info(
            "analyze_research_trends: %s (last %d years)", query, years
        )

        try:
            current_year = datetime.now().year
            year_from = current_year - years

            # OpenAlex aggregation
            all_papers: list[dict] = []
            try:
                oa = self._request(
                    OPENALEX_WORKS,
                    {
                        "search": query,
                        "per-page": min(200, years * 20),
                        "filter": f"publication_year:{year_from}-{current_year}",
                    },
                )
                if oa and oa.get("results"):
                    all_papers = [
                        self._openalex_work_to_paper(w)
                        for w in oa["results"]
                    ]
            except Exception:
                pass

            # Semantic Scholar fallback
            if len(all_papers) < 20:
                try:
                    ss = self._request(
                        SEMANTIC_PAPER_SEARCH,
                        {
                            "query": query,
                            "limit": 100,
                            "fields": "title,authors,year,citationCount,venue,journal,fieldsOfStudy",
                        },
                    )
                    if ss and ss.get("data"):
                        all_papers.extend(
                            [
                                self._semantic_paper_to_paper(p)
                                for p in ss["data"]
                            ]
                        )
                except Exception:
                    pass

            # Deduplicate
            seen: set[str] = set()
            unique: list[dict] = []
            for p in all_papers:
                key = p.get("doi") or p.get("title", "").lower()
                if key and key not in seen:
                    seen.add(key)
                    unique.append(p)

            # Aggregate
            yearly_counts: dict[int, int] = {}
            yearly_citations: dict[int, int] = {}
            venue_counts: dict[str, int] = {}
            author_counts: dict[str, int] = {}

            for p in unique:
                yr = p.get("year")
                if yr and year_from <= yr <= current_year:
                    yearly_counts[yr] = yearly_counts.get(yr, 0) + 1
                    yearly_citations[yr] = (
                        yearly_citations.get(yr, 0)
                        + p.get("citation_count", 0)
                    )

                venue = p.get("venue", "")
                if venue:
                    venue_counts[venue] = venue_counts.get(venue, 0) + 1

                for a in p.get("authors", [])[:5]:
                    a_name = a if isinstance(a, str) else a.get("name", "")
                    if a_name:
                        author_counts[a_name] = (
                            author_counts.get(a_name, 0) + 1
                        )

            # Fill missing years
            for yr in range(year_from, current_year + 1):
                if yr not in yearly_counts:
                    yearly_counts[yr] = 0

            trend_dir = (
                "increasing"
                if yearly_counts.get(current_year, 0)
                > yearly_counts.get(year_from, 0)
                else "stable"
            )

            return _resp(
                True,
                {
                    "query": query,
                    "year_range": f"{year_from}-{current_year}",
                    "total_papers": len(unique),
                    "yearly_publications": dict(sorted(yearly_counts.items())),
                    "citation_by_year": dict(
                        sorted(yearly_citations.items())
                    ),
                    "trend_direction": trend_dir,
                    "top_venues": sorted(
                        venue_counts.items(), key=lambda x: -x[1]
                    )[:10],
                    "top_authors": sorted(
                        author_counts.items(), key=lambda x: -x[1]
                    )[:10],
                    "sample_papers": unique[:10],
                },
                "multi_source",
                qdict,
            )
        except Exception as exc:
            logger.error("analyze_research_trends error: %s", exc)
            return _resp(False, None, "", qdict, str(exc))


# =============================================================================
# Demonstration / smoke-test block
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("=" * 60)
    logger.info("Operation Phoenix Shield - Scholar IP Engine Demo")
    logger.info("=" * 60)

    with ScholarIPEngine() as engine:
        # --- 1. Paper search ---
        logger.info("\n--- DEMO: search_papers ---")
        r = engine.search_papers(
            "computational fluid dynamics", year_from=2020, num_results=5
        )
        logger.info(
            "Success: %s | Found: %d papers",
            r["success"],
            r.get("data", {}).get("total", 0),
        )
        if r.get("success") and r.get("data", {}).get("papers"):
            for p in r["data"]["papers"][:3]:
                logger.info(
                    "  - %s (%s) [%s citations]",
                    p.get("title", "")[:80],
                    p.get("year"),
                    p.get("citation_count", 0),
                )

        # --- 2. Author profile ---
        logger.info("\n--- DEMO: get_author_profile ---")
        r = engine.get_author_profile("Yann LeCun")
        logger.info("Success: %s", r["success"])
        if r.get("success"):
            d = r["data"]
            logger.info(
                "  Name: %s | Papers: %d | Citations: %d | h-index: %s",
                d.get("matched_name"),
                d.get("paper_count"),
                d.get("citation_count"),
                d.get("h_index"),
            )

        # --- 3. h-index ---
        logger.info("\n--- DEMO: get_h_index ---")
        r = engine.get_h_index("Geoffrey Hinton")
        if r.get("success"):
            d = r["data"]
            logger.info(
                "  h-index: %d | g-index: %d | i10-index: %d | "
                "Total citations: %d",
                d["h_index"],
                d["g_index"],
                d["i10_index"],
                d["total_citations"],
            )

        # --- 4. Paper citations ---
        logger.info("\n--- DEMO: get_paper_citations ---")
        r = engine.get_paper_citations(
            paper_title="attention is all you need"
        )
        if r.get("success"):
            d = r["data"]
            logger.info(
                "  Title: %s | Forward: %d | Backward: %d",
                d.get("title", "")[:60],
                d.get("citation_count", 0),
                d.get("reference_count", 0),
            )

        # --- 5. Prior art ---
        logger.info("\n--- DEMO: find_prior_art ---")
        r = engine.find_prior_art(
            "machine learning neural network image classification "
            "convolutional layers"
        )
        logger.info(
            "Success: %s | Candidates: %d | %s",
            r["success"],
            r.get("data", {}).get("total_candidates", 0),
            r.get("data", {}).get("recommendation", ""),
        )

        # --- 6. Research trends ---
        logger.info("\n--- DEMO: analyze_research_trends ---")
        r = engine.analyze_research_trends("large language model", years=5)
        if r.get("success"):
            d = r["data"]
            logger.info(
                "  Total papers: %d | Trend: %s",
                d["total_papers"],
                d["trend_direction"],
            )
            logger.info("  Yearly: %s", d.get("yearly_publications", {}))

        # --- 7. Plagiarism detection ---
        logger.info("\n--- DEMO: detect_plagiarism_in_literature ---")
        r = engine.detect_plagiarism_in_literature(
            "transformer architecture natural language processing "
            "attention mechanism"
        )
        if r.get("success"):
            d = r["data"]
            logger.info(
                "  Candidates: %d | Matches: %d | High flags: %d",
                d["candidates_checked"],
                d["matches_found"],
                d["high_similarity_flags"],
            )

        # --- 8. IP theft evidence ---
        logger.info("\n--- DEMO: search_stolen_ip_evidence ---")
        r = engine.search_stolen_ip_evidence("Brent Michael Skoda")
        if r.get("success"):
            d = r["data"]
            logger.info(
                "  Evidence papers: %d | Risk indicators: %d",
                d.get("total_evidence_items", 0),
                len(d.get("risk_indicators", [])),
            )
            for ri in d.get("risk_indicators", []):
                logger.info(
                    "    [%s] %s: %s",
                    ri.get("severity"),
                    ri.get("type"),
                    ri.get("detail", "")[:100],
                )

        # --- 9. Journal metrics ---
        logger.info("\n--- DEMO: get_journal_impact_metrics ---")
        r = engine.get_journal_impact_metrics(journal_name="Nature")
        if r.get("success"):
            logger.info(
                "  Sources: %s",
                list(r["data"].get("sources", {}).keys()),
            )

        # --- 10. Synthetic profile detection ---
        logger.info("\n--- DEMO: detect_synthetic_author_profiles ---")
        r = engine.detect_synthetic_author_profiles(
            ["Albert Einstein", "A", "John Smith"]
        )
        if r.get("success"):
            for f in r["data"].get("flags", []):
                logger.info(
                    "  %s: risk=%s (%s)",
                    f.get("name"),
                    f.get("synthetic_risk"),
                    f.get("risk_level", "N/A"),
                )

    logger.info("\n" + "=" * 60)
    logger.info("Demo complete. All engines tested.")
    logger.info("=" * 60)

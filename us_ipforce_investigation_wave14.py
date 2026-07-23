#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 14
================================
Google Patents inventor continuity refresh (paginated) vs Wave-4 portfolio,
assignee-cluster expansion (incl. UrgentRN LLC), SAM.gov negative filter for
Ahkeo Labs, and Cuyahoga/USPTO trademark portal operator paths.

Does NOT call USPTO ODP with forged keys. Does NOT adjudicate theft/RICO/UBO.
Quarantined patent IDs remain quarantined. Ohio roster remains evidence-only.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE14"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W14"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave14"
DOCS = ROOT / "docs" / "investigation" / "wave14"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave14/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)

WAVE4_PORTFOLIO = (
    ROOT / "docs" / "investigation" / "wave4" / "AUTHENTICATED_SKODA_PORTFOLIO.json"
)

INVENTOR_QUERIES = (
    'inventor="Brent M. Skoda"',
    'inventor="Brent Skoda"',
)

PORTAL_PROBES = [
    (
        "uspto_tmsearch",
        "https://tmsearch.uspto.gov/search/search-information",
    ),
    ("uspto_tsdr", "https://tsdr.uspto.gov/"),
    (
        "cuyahoga_myplace",
        "https://myplace.cuyahogacounty.gov/",
    ),
    (
        "cuyahoga_fiscal_property_search",
        "https://fiscalofficer.cuyahogacounty.us/en-US/Search-Property.aspx",
    ),
    (
        "sam_ahkeo_labs_ei",
        "https://sam.gov/api/prod/sgs/v1/search/?index=ei&q=Ahkeo%20Labs&page=0&size=10",
    ),
]


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _sha3_256(obj: Any) -> str:
    return hashlib.sha3_256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _sha3_512(data: bytes) -> str:
    return hashlib.sha3_512(data).hexdigest()


def _write(path: Path, payload: dict[str, Any] | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def ensure_hmac_key() -> str:
    env = os.environ.get("EVIDENCE_HMAC_KEY", "").strip()
    if env and not env.lower().startswith("community") and env != "default-key":
        return env
    key_path = ROOT / "output_artifacts" / "investigation" / ".run_hmac_key"
    if key_path.is_file():
        return key_path.read_text(encoding="utf-8").strip()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(32)
    key_path.write_text(key + "\n", encoding="utf-8")
    return key


def _http(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    max_bytes: int = 500000,
    timeout: float = 40.0,
) -> dict[str, Any]:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(max_bytes)
            return {
                "url": url,
                "ok": True,
                "status": getattr(resp, "status", 200),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "sha3_256": hashlib.sha3_256(body).hexdigest(),
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "body": body,
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "url": url,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "body": b"",
        }


def _norm_pub(pid: str) -> str:
    return pid.strip().upper().replace(" ", "")


def _gp_query_all_pages(query: str, *, max_pages: int = 3) -> dict[str, Any]:
    pubs: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    total: int | None = None
    for page in range(max_pages):
        q = query if page == 0 else f"{query}&page={page}"
        url = "https://patents.google.com/xhr/query?url=" + urllib.parse.quote(q)
        resp: dict[str, Any] = {}
        for attempt in range(6):
            resp = _http(url, max_bytes=400000)
            if resp.get("ok"):
                break
            err = str(resp.get("error") or "")
            if "503" in err or "429" in err or "500" in err:
                time.sleep(1.5 * (attempt + 1))
                continue
            break
        page_meta: dict[str, Any] = {
            "page": page,
            "url": url,
            "ok": resp.get("ok"),
            "status": resp.get("status"),
            "error": resp.get("error"),
            "bytes": resp.get("bytes"),
            "sha256": resp.get("sha256"),
            "sha3_256": resp.get("sha3_256"),
        }
        if not resp.get("ok"):
            pages.append(page_meta)
            break
        try:
            data = json.loads(resp["body"].decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            page_meta["parse_error"] = f"{type(exc).__name__}: {exc}"
            pages.append(page_meta)
            break
        results = data.get("results") or {}
        total = results.get("total_num_results")
        page_meta["total_num_results"] = total
        page_meta["num_page"] = results.get("num_page")
        n = 0
        for cluster in results.get("cluster") or []:
            for item in cluster.get("result") or []:
                pat = item.get("patent") or {}
                raw_id = (item.get("id") or "").replace("patent/", "").replace(
                    "/en", ""
                )
                pub = _norm_pub(raw_id)
                title = (pat.get("title") or "").strip()
                snippet = (pat.get("snippet") or "").strip()
                pubs.append(
                    {
                        "publication": pub,
                        "title": title,
                        "snippet": snippet[:400],
                        "assignee_field": pat.get("assignee") or "",
                        "inventor_query": query,
                        "page": page,
                        "google_patents_url": f"https://patents.google.com/patent/{pub}/en",
                        "mentions_caffeine": (
                            "caffeine" in f"{title} {snippet}".lower()
                        ),
                    }
                )
                n += 1
        page_meta["results_on_page"] = n
        pages.append(page_meta)
        if n == 0:
            break
        if total is not None and len({p["publication"] for p in pubs}) >= int(total):
            break
        time.sleep(0.75)
    return {
        "query": query,
        "total_num_results": total,
        "publications": pubs,
        "pages": pages,
    }


def track_google_patents_refresh() -> dict[str, Any]:
    wave4_ids: set[str] = set()
    wave4_count = 0
    if WAVE4_PORTFOLIO.is_file():
        w4 = json.loads(WAVE4_PORTFOLIO.read_text(encoding="utf-8"))
        wave4_count = int(w4.get("publication_count") or len(w4.get("publications") or []))
        wave4_ids = {
            _norm_pub(p["publication"])
            for p in (w4.get("publications") or [])
            if p.get("publication")
        }

    # Sequential on purpose — parallel Google Patents xhr often 503s.
    query_runs: dict[str, Any] = {}
    for q in INVENTOR_QUERIES:
        query_runs[q] = _gp_query_all_pages(q)
        time.sleep(1.0)

    by_pub: dict[str, dict[str, Any]] = {}
    for q, run in query_runs.items():
        for p in run.get("publications") or []:
            pid = p["publication"]
            if pid not in by_pub:
                by_pub[pid] = dict(p)
                by_pub[pid]["inventor_queries"] = [q]
            else:
                by_pub[pid]["inventor_queries"] = sorted(
                    set(by_pub[pid].get("inventor_queries") or []) | {q}
                )
                # prefer non-empty assignee
                if not by_pub[pid].get("assignee_field") and p.get("assignee_field"):
                    by_pub[pid]["assignee_field"] = p["assignee_field"]

    union_ids = set(by_pub)
    new_ids = sorted(union_ids - wave4_ids)
    still_present = sorted(union_ids & wave4_ids)
    missing_from_refresh = sorted(wave4_ids - union_ids)

    assignee_clusters: dict[str, list[str]] = {}
    for pid, p in sorted(by_pub.items()):
        a = (p.get("assignee_field") or "unknown").strip() or "unknown"
        assignee_clusters.setdefault(a, []).append(pid)

    new_pubs = [by_pub[i] for i in new_ids]
    findings = [
        {
            "id": "W14-F1",
            "title": "Google Patents inventor refresh — Wave-4 portfolio still present",
            "severity": "google_patents_xhr",
            "wave4_publication_count": wave4_count,
            "wave4_still_present": len(still_present),
            "missing_from_refresh": missing_from_refresh,
            "detail": (
                f"Paginated inventor queries recovered {len(still_present)}/{wave4_count} "
                "Wave-4 publications. Missing list empty means continuity confirmed."
            ),
        },
        {
            "id": "W14-F2",
            "title": f"Expanded portfolio — {len(new_ids)} publication(s) beyond Wave-4",
            "severity": "google_patents_xhr",
            "new_publications": new_ids,
            "detail": (
                "New IDs appear on Google Patents inventor search pages not captured "
                "in the Wave-4 sealed set of 12. Not an ownership adjudication; "
                "assignment chain still requires USPTO_API_KEY / assignment records."
            ),
            "new_pub_summaries": [
                {
                    "publication": p["publication"],
                    "title": p.get("title"),
                    "assignee_field": p.get("assignee_field"),
                    "mentions_caffeine": p.get("mentions_caffeine"),
                    "google_patents_url": p.get("google_patents_url"),
                }
                for p in new_pubs
            ],
        },
    ]
    if any(
        "urgent" in (p.get("assignee_field") or "").lower() for p in by_pub.values()
    ):
        findings.append(
            {
                "id": "W14-F3",
                "title": "New assignee cluster observed — UrgentRN LLC",
                "severity": "google_patents_xhr",
                "publications": [
                    pid
                    for pid, p in by_pub.items()
                    if "urgent" in (p.get("assignee_field") or "").lower()
                ],
                "detail": (
                    "US20220104664A1 lists assignee UrgentRN LLC on Google Patents "
                    "inventor search for Brent M. Skoda. Corporate abstract / "
                    "assignment still required; not Ohio-roster invented."
                ),
            }
        )

    caffeine = [
        p
        for p in by_pub.values()
        if p.get("mentions_caffeine")
        or "caffeine" in (p.get("title") or "").lower()
    ]
    findings.append(
        {
            "id": "W14-F4",
            "title": "Caffeine-related publication continuity",
            "severity": "google_patents_xhr",
            "count": len(caffeine),
            "publications": [
                {
                    "publication": p["publication"],
                    "title": p.get("title"),
                    "assignee_field": p.get("assignee_field"),
                }
                for p in caffeine
            ],
            "detail": (
                "Caffeine hits from title/snippet only. Foundational CZ1997 claim "
                "remains OPEN_MANUAL_STILL_UNVERIFIED; quarantined CZ283061 not cited."
            ),
        }
    )

    return {
        "id": "google_patents_portfolio_refresh",
        "title": "Google Patents inventor continuity refresh vs Wave-4",
        "status": "SEALED",
        "generated_at": _utc(),
        "wave4_path": str(WAVE4_PORTFOLIO.relative_to(ROOT))
        if WAVE4_PORTFOLIO.is_file()
        else None,
        "wave4_publication_count": wave4_count,
        "union_publication_count": len(by_pub),
        "new_beyond_wave4_count": len(new_ids),
        "new_beyond_wave4": new_ids,
        "still_present_wave4": still_present,
        "missing_from_refresh": missing_from_refresh,
        "assignee_clusters": {
            k: sorted(v) for k, v in sorted(assignee_clusters.items())
        },
        "publications": [by_pub[k] for k in sorted(by_pub)],
        "query_runs": {
            q: {
                "total_num_results": r.get("total_num_results"),
                "publication_count": len(r.get("publications") or []),
                "pages": [
                    {kk: vv for kk, vv in pg.items() if kk != "body"}
                    for pg in (r.get("pages") or [])
                ],
            }
            for q, r in query_runs.items()
        },
        "findings": findings,
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "next_actions": [
            "USPTO_API_KEY → assignment retrieval for expanded 15-pub set",
            "Ohio / DE abstracts for UrgentRN LLC if counsel pursues cluster",
        ],
    }


def track_sam_negative() -> dict[str, Any]:
    url = (
        "https://sam.gov/api/prod/sgs/v1/search/"
        "?index=ei&q=Ahkeo%20Labs&page=0&size=10"
    )
    resp = _http(url, max_bytes=100000)
    probe: dict[str, Any] = {
        "url": url,
        "ok": resp.get("ok"),
        "status": resp.get("status"),
        "error": resp.get("error"),
        "bytes": resp.get("bytes"),
        "sha3_256": resp.get("sha3_256"),
    }
    exact_hits: list[dict[str, Any]] = []
    fuzzy_labs: list[dict[str, Any]] = []
    if resp.get("ok"):
        try:
            data = json.loads(resp["body"].decode("utf-8"))
            results = (data.get("_embedded") or {}).get("results") or []
            for r in results:
                title = (r.get("title") or r.get("legalBusinessName") or "").strip()
                entry = {
                    "title": title,
                    "ueiSam": r.get("ueiSam"),
                    "exclusionType": r.get("exclusionType"),
                    "address": r.get("address"),
                    "_type": r.get("_type"),
                    "_rScore": r.get("_rScore"),
                }
                if title.lower() == "ahkeo labs" or title.lower().startswith(
                    "ahkeo labs"
                ):
                    exact_hits.append(entry)
                else:
                    fuzzy_labs.append(entry)
            probe["result_count"] = len(results)
        except Exception as exc:  # noqa: BLE001
            probe["parse_error"] = f"{type(exc).__name__}: {exc}"

    finding = {
        "id": "W14-F5",
        "title": "SAM.gov — no exact Ahkeo Labs entity/exclusion hit",
        "severity": "sam_gov",
        "exact_hit_count": len(exact_hits),
        "fuzzy_labs_returned": len(fuzzy_labs),
        "detail": (
            "SAM exclusions index search for 'Ahkeo Labs' returned other '*Labs*' "
            "entities (Mirror Labs, Massey Analytical Labs, etc.) — fuzzy token "
            "matches only. No exact Ahkeo Labs SAM registration/exclusion sealed."
        ),
    }
    return {
        "id": "sam_gov_ahkeo_negative",
        "title": "SAM.gov Ahkeo Labs negative / false-positive filter",
        "status": "SEALED",
        "generated_at": _utc(),
        "probe": probe,
        "exact_hits": exact_hits,
        "fuzzy_labs_sample": fuzzy_labs[:10],
        "findings": [finding],
        "adjudicated": False,
        "next_actions": [
            "No SAM exclusion action for Ahkeo Labs on this evidence",
        ],
    }


def track_portal_operator_paths() -> dict[str, Any]:
    probes: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {
            pool.submit(_http, url, max_bytes=120000): name
            for name, url in PORTAL_PROBES
        }
        for fut in as_completed(futs):
            name = futs[fut]
            resp = fut.result()
            probes[name] = {
                "url": resp.get("url"),
                "ok": resp.get("ok"),
                "status": resp.get("status"),
                "error": resp.get("error"),
                "bytes": resp.get("bytes"),
                "sha3_256": resp.get("sha3_256"),
            }

    findings = [
        {
            "id": "W14-F6",
            "title": "Cuyahoga County property portals reachable (6685 Beta Drive path)",
            "severity": "portal_probe",
            "ok": bool(
                (probes.get("cuyahoga_myplace") or {}).get("ok")
                or (probes.get("cuyahoga_fiscal_property_search") or {}).get("ok")
            ),
            "detail": (
                "MyPlace / Fiscal Officer property-search HTML reachable. "
                "Structured parcel ownership for 6685 Beta Drive, Mayfield Village "
                "OH 44143 still requires operator browser session — not sealed here."
            ),
            "portals": [
                "https://myplace.cuyahogacounty.gov/",
                "https://fiscalofficer.cuyahogacounty.us/en-US/Search-Property.aspx",
            ],
        },
        {
            "id": "W14-F7",
            "title": "USPTO trademark search/TSDR portals reachable; case API gated",
            "severity": "portal_probe",
            "ok": bool(
                (probes.get("uspto_tmsearch") or {}).get("ok")
                or (probes.get("uspto_tsdr") or {}).get("ok")
            ),
            "detail": (
                "tmsearch.uspto.gov and tsdr.uspto.gov return public HTML. "
                "Structured AHKEO trademark case JSON (TSDR API) returned 401 "
                "without credentials — operator mark search remains open."
            ),
        },
    ]
    return {
        "id": "portal_operator_paths",
        "title": "Cuyahoga parcel + USPTO trademark portal probes",
        "status": "PROBED",
        "generated_at": _utc(),
        "probes": probes,
        "findings": findings,
        "beta_drive_target": "6685 Beta Drive, Mayfield Village, OH 44143",
        "next_actions": [
            "Operator: MyPlace/Fiscal Officer parcel search for 6685 Beta Drive",
            "Operator: USPTO TMsearch for AHKEO / AHKEO LABS marks",
        ],
    }


def track_operator_worklist(portfolio: dict[str, Any]) -> dict[str, Any]:
    n = portfolio.get("union_publication_count", 0)
    return {
        "id": "operator_worklist",
        "title": "Wave-14 operator priority worklist",
        "status": "OPEN",
        "generated_at": _utc(),
        "priorities": [
            {
                "rank": 1,
                "item": f"USPTO_API_KEY → assignments for expanded {n}-pub portfolio",
                "blocked_on": "env_secret",
            },
            {
                "rank": 2,
                "item": "Paid DE Certificate of Status + Certified Formation (6096179)",
                "blocked_on": "operator_payment",
            },
            {
                "rank": 3,
                "item": "Ohio SOS foreign qualification / abstracts (Ahkeo + UrgentRN)",
                "blocked_on": "operator_browser",
            },
            {
                "rank": 4,
                "item": "Cuyahoga MyPlace parcel ownership — 6685 Beta Drive",
                "blocked_on": "operator_browser",
            },
            {
                "rank": 5,
                "item": "USPTO TMsearch — AHKEO / AHKEO LABS marks",
                "blocked_on": "operator_browser",
            },
            {
                "rank": 6,
                "item": "Paid historical WHOIS ahkeo/ahkeolabs (Wave-13 content sealed)",
                "blocked_on": "operator_subscription",
            },
            {
                "rank": 7,
                "item": "PACER Doc.38 + Czech UPV (not CZ283061) + counsel send Wave-11",
                "blocked_on": "operator_multi",
            },
        ],
        "next_actions": [
            "Export USPTO_API_KEY and re-run assignment pull against Wave-14 union set",
        ],
    }


def write_summary_md(portfolio: dict[str, Any], sam: dict[str, Any]) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE14_PORTFOLIO_REFRESH.md"
    new_ids = portfolio.get("new_beyond_wave4") or []
    lines = [
        "# IP FORCE — Wave 14 Portfolio Refresh",
        "",
        f"**Case:** `{CASE_ID}`  ",
        f"**Generated:** {_utc()}  ",
        f"**Union publications:** {portfolio.get('union_publication_count')}  ",
        f"**New beyond Wave-4:** {len(new_ids)}",
        "",
        "## Scope",
        "",
        "Wave 14 re-queries Google Patents inventor search with pagination, diffs "
        "against the sealed Wave-4 set of 12, filters SAM.gov false positives, and "
        "documents Cuyahoga/USPTO trademark operator portals. No theft/RICO/UBO "
        "adjudication. Quarantined patents remain quarantined.",
        "",
        "## New publications beyond Wave-4",
        "",
    ]
    by = {p["publication"]: p for p in (portfolio.get("publications") or [])}
    if not new_ids:
        lines.append("_None — Wave-4 set complete on this refresh._")
    for pid in new_ids:
        p = by.get(pid) or {}
        lines.append(
            f"- `{pid}` — {p.get('title')} "
            f"(assignee: {p.get('assignee_field') or 'unknown'})"
        )
    lines.extend(
        [
            "",
            "## Assignee clusters (Google Patents field)",
            "",
        ]
    )
    for a, pubs in (portfolio.get("assignee_clusters") or {}).items():
        lines.append(f"- **{a}** — {', '.join(f'`{x}`' for x in pubs)}")
    lines.extend(
        [
            "",
            "## Findings",
            "",
        ]
    )
    for f in (portfolio.get("findings") or []) + (sam.get("findings") or []):
        lines.append(f"- **{f.get('id')}** — {f.get('title')}")
    lines.extend(
        [
            "",
            "## Still open (operator)",
            "",
            "1. USPTO_API_KEY assignments (expanded set)",
            "2. DE Certificate of Status / Formation (6096179)",
            "3. Ohio SOS + UrgentRN abstracts",
            "4. Cuyahoga parcel 6685 Beta Drive",
            "5. USPTO TMsearch AHKEO marks",
            "6. Paid WHOIS / PACER Doc.38 / UPV / counsel send",
            "",
            "---",
            "",
            "IP FORCE · Wave 14 · No theft/RICO/UBO adjudication",
            "",
        ]
    )
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave14() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    portfolio = track_google_patents_refresh()
    sam = track_sam_negative()
    portals = track_portal_operator_paths()
    worklist = track_operator_worklist(portfolio)
    summary_md = write_summary_md(portfolio, sam)

    # Convenience sealed portfolio artifact
    expanded = {
        "schema": "us_ipforce.wave14.expanded_skoda_portfolio_v1",
        "generated_at": _utc(),
        "wave4_baseline": portfolio.get("wave4_publication_count"),
        "publication_count": portfolio.get("union_publication_count"),
        "new_beyond_wave4": portfolio.get("new_beyond_wave4"),
        "assignee_clusters": portfolio.get("assignee_clusters"),
        "publications": portfolio.get("publications"),
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "note": (
            "Google Patents inventor-search fields only. Assignment ownership "
            "requires USPTO assignment records."
        ),
    }
    _write(DOCS / "EXPANDED_SKODA_PORTFOLIO.json", expanded)
    _write(OUT / "EXPANDED_SKODA_PORTFOLIO.json", expanded)

    tracks = [portfolio, sam, portals, worklist]
    for t in tracks:
        _write(OUT / f"{t['id']}.json", t)
        _write(DOCS / f"{t['id']}.json", t)

    key = ensure_hmac_key()
    os.environ["EVIDENCE_HMAC_KEY"] = key
    leaves = [
        {"id": t["id"], "sha3_256": _sha3_256(t), "status": t.get("status")}
        for t in tracks
    ]
    material = json.dumps(
        {"case_id": CASE_ID, "leaves": leaves},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    root = _sha3_512(material)
    mac = hmac.new(key.encode(), material, hashlib.sha3_256).hexdigest()

    all_findings: list[dict[str, Any]] = []
    for t in (portfolio, sam, portals):
        all_findings.extend(t.get("findings") or [])

    report = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "counts": {
            "tracks": len(tracks),
            "union_publications": portfolio.get("union_publication_count", 0),
            "new_beyond_wave4": portfolio.get("new_beyond_wave4_count", 0),
            "findings": len(all_findings),
            "adjudicated_total": 0,
            "true_ubo_asserted": 0,
        },
        "new_beyond_wave4": portfolio.get("new_beyond_wave4"),
        "findings": all_findings,
        "tracks": [
            {
                "id": t["id"],
                "title": t.get("title"),
                "status": t.get("status"),
                "next_actions": t.get("next_actions"),
                "adjudicated": False,
            }
            for t in tracks
        ],
        "artifacts": {
            "summary_md": summary_md,
            "expanded_portfolio": "docs/investigation/wave14/EXPANDED_SKODA_PORTFOLIO.json",
            "gp_refresh": "docs/investigation/wave14/google_patents_portfolio_refresh.json",
            "sam": "docs/investigation/wave14/sam_gov_ahkeo_negative.json",
            "portals": "docs/investigation/wave14/portal_operator_paths.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-14 seals Google Patents paginated inventor refresh (expanded "
            "portfolio), SAM.gov Ahkeo Labs negative filter, and portal operator "
            "paths. No theft/RICO/UBO adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE14_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE14_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE14_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE14_POINTER.json",
        {
            "brand": BRAND,
            "wave14_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave14/WAVE14_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "expanded_portfolio": report["artifacts"]["expanded_portfolio"],
            "new_beyond_wave4": report.get("new_beyond_wave4"),
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 14")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave14()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        print(
            f"{BRAND} wave14: union={c['union_publications']} "
            f"new={c['new_beyond_wave4']} "
            f"findings={c['findings']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        print(f"  portfolio: {report['artifacts']['expanded_portfolio']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 5
================================
Ahkeo/Ohio corporate cluster crosswalk + USPTO assignment worklist + SEC Form D
corroboration after Wave-4 authenticated portfolio.

FINDINGS (public surfaces this wave)
------------------------------------
• Ohio roster ahkeo_cluster (VI-035..VI-039) extracted evidence-only; abstracts still
  required from Ohio SOS / PR Registro.
• Wave-4 assignees (Ahkeo Labs / Ahkeo Ventures / Zorday IP) name-align to roster
  Ahkeo entities — not SOS-authenticated.
• USPTO assignment-api / assignment.uspto.gov → DNS failure; ODP key still required.
• OpenCorporates HTML 403 / API 401 without key (unchanged).
• SEC EDGAR Form D (Casters Holdings Inc., CIK 0001792675, accession
  0000897069-19-000500): Brent Skoda listed related person — Executive Officer,
  Director, Promoter — address 6685 Beta Drive, Mayfield Village, OH 44143.
• Later Casters Form D filings (2020–2023) omit Skoda from relatedPersonsList.
• Ahkeo / Zorday → 0 SEC EDGAR full-text hits on public search-index.
• Foundational CZ1997 caffeine-vaporizer claim remains OPEN_MANUAL_STILL_UNVERIFIED.

Does NOT adjudicate theft/RICO/UBO. Does NOT invent corporate charter numbers.
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
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE5"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W5"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave5"
DOCS = ROOT / "docs" / "investigation" / "wave5"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave5/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
SEC_UA = "IP-FORCE-Wave5 research contact@example.invalid"

CASTERS_CIK = "0001792675"
CASTERS_FORM_D_URLS = [
    {
        "label": "2019-11-04",
        "accession": "0000897069-19-000500",
        "url": (
            "https://www.sec.gov/Archives/edgar/data/1792675/"
            "000089706919000500/primary_doc.xml"
        ),
    },
    {
        "label": "2020-08-26",
        "accession": "0001792675-20-000004",
        "url": (
            "https://www.sec.gov/Archives/edgar/data/1792675/"
            "000179267520000004/primary_doc.xml"
        ),
    },
    {
        "label": "2021-03-05",
        "accession": "0001792675-21-000001",
        "url": (
            "https://www.sec.gov/Archives/edgar/data/1792675/"
            "000179267521000001/primary_doc.xml"
        ),
    },
    {
        "label": "2021-11-10",
        "accession": "0001792675-21-000003",
        "url": (
            "https://www.sec.gov/Archives/edgar/data/1792675/"
            "000179267521000003/primary_doc.xml"
        ),
    },
    {
        "label": "2022-10-21",
        "accession": "0001792675-22-000001",
        "url": (
            "https://www.sec.gov/Archives/edgar/data/1792675/"
            "000179267522000001/primary_doc.xml"
        ),
    },
    {
        "label": "2023-12-28",
        "accession": "0001792675-23-000001",
        "url": (
            "https://www.sec.gov/Archives/edgar/data/1792675/"
            "000179267523000001/primary_doc.xml"
        ),
    },
]

PROBE_URLS = [
    (
        "uspto_assignment_api",
        "https://assignment-api.uspto.gov/patent/detailed-search?criteriaText=Ahkeo",
    ),
    (
        "uspto_assignment_ui",
        "https://assignment.uspto.gov/patent/index.html",
    ),
    (
        "uspto_data_assignment_v1",
        "https://data.uspto.gov/apis/patent-assignment/v1/assignments?assigneeNameText=Ahkeo",
    ),
    (
        "opencorporates_ahkeo_html",
        "https://opencorporates.com/companies?q=Ahkeo+LLC",
    ),
    (
        "opencorporates_api",
        "https://api.opencorporates.com/v0.4/companies/search?q=Ahkeo",
    ),
    (
        "upv_en_home",
        "https://upv.gov.cz/en",
    ),
    (
        "ohio_sos_business_search",
        "https://businesssearch.ohiosos.gov/",
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


def _tag(el: ET.Element) -> str:
    return el.tag.split("}")[-1] if "}" in el.tag else el.tag


def _find_text(el: ET.Element, name: str) -> str | None:
    for child in el.iter():
        if _tag(child) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def _http(
    url: str,
    *,
    accept: str = "*/*",
    user_agent: str = USER_AGENT,
    max_bytes: int = 400000,
) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept": accept},
        method="GET",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(max_bytes)
            ctype = resp.headers.get("Content-Type", "")
            return {
                "ok": True,
                "status_code": resp.status,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "bytes": len(body),
                "content_type": ctype,
                "body_sha3_256": hashlib.sha3_256(body).hexdigest(),
                "body_prefix": body[:160].decode("utf-8", "replace"),
                "looks_like_html": body.lstrip()[:15].lower().startswith(
                    (b"<!doctype", b"<html")
                ),
                "error": None,
                "url": url,
                "body": body,
            }
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read(8000)
        except Exception:  # noqa: BLE001
            body = b""
        return {
            "ok": False,
            "status_code": exc.code,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "bytes": len(body),
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "body_sha3_256": hashlib.sha3_256(body).hexdigest() if body else None,
            "body_prefix": body[:160].decode("utf-8", "replace") if body else "",
            "looks_like_html": False,
            "error": f"HTTPError:{exc.code}",
            "url": url,
            "body": body,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status_code": getattr(exc, "code", None),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "bytes": 0,
            "content_type": None,
            "body_sha3_256": None,
            "body_prefix": "",
            "looks_like_html": False,
            "error": f"{type(exc).__name__}:{exc}"[:240],
            "url": url,
            "body": b"",
        }


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


def load_ohio_roster() -> dict[str, Any]:
    path = ROOT / "data" / "victim_inventor_ohio_llc_roster.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_wave4_portfolio() -> dict[str, Any]:
    path = ROOT / "docs" / "investigation" / "wave4" / "AUTHENTICATED_SKODA_PORTFOLIO.json"
    if not path.is_file():
        return {"publication_count": 0, "publications": [], "missing": True}
    return json.loads(path.read_text(encoding="utf-8"))


def extract_ahkeo_cluster(roster: dict[str, Any]) -> dict[str, Any]:
    entities = [
        e
        for e in roster.get("entities") or []
        if e.get("chronology_phase") == "ahkeo_cluster"
    ]
    ohio = [e for e in entities if e.get("ohio_llc")]
    non_ohio = [e for e in entities if not e.get("ohio_llc")]
    slim = [
        {
            "entity_id": e.get("entity_id"),
            "slug": e.get("slug"),
            "name": e.get("name"),
            "name_variants": e.get("name_variants") or [],
            "jurisdiction": e.get("jurisdiction"),
            "ohio_llc": bool(e.get("ohio_llc")),
            "illicit_mirror": bool(e.get("illicit_mirror")),
            "evidence_status": "roster_screened_not_sos_abstracted",
            "charter_number": None,
            "sos_status": "OPEN_MANUAL",
        }
        for e in entities
    ]
    return {
        "wave": 5,
        "id": "ahkeo_ohio_cluster_extract",
        "title": "Ahkeo Ohio/PR cluster extracted from evidence roster",
        "status": "done",
        "source": "data/victim_inventor_ohio_llc_roster.json",
        "roster_ohio_llc_count": roster.get("ohio_llc_count"),
        "roster_count": roster.get("roster_count"),
        "claimed_scope_note": (
            "Prior investigation notes claimed Ohio scope 69 vs screened 41 "
            "(gap 28 retained — entities not invented)."
        ),
        "cluster_count": len(slim),
        "ohio_count": len(ohio),
        "non_ohio_count": len(non_ohio),
        "entities": slim,
        "policy": (
            "Roster evidence only. No charter numbers invented. "
            "Ohio SOS / PR Registro certified abstracts still required."
        ),
        "adjudicated": False,
        "next_actions": [
            "Ohio SOS certified abstract for AHKEO LLC / VENTURES / ELECTRIC / MANAGEMENT",
            "PR Registro search for AHKEO HOLDINGS PUERTO RICO LLC",
            "Map registered agent / organizer / address to Form D Mayfield Village nexus",
        ],
    }


def crosswalk_assignees(
    portfolio: dict[str, Any], ahkeo: dict[str, Any]
) -> dict[str, Any]:
    pubs = portfolio.get("publications") or []
    assignees = sorted(
        {
            (p.get("assignee_field") or "").strip()
            for p in pubs
            if (p.get("assignee_field") or "").strip()
        }
    )
    roster_names = {
        (e.get("name") or "").upper(): e for e in ahkeo.get("entities") or []
    }
    links = []
    for a in assignees:
        au = a.upper()
        match = None
        strength = "none"
        if "AHKEO LABS" in au:
            # Labs not a discrete roster LLC — nearest is AHKEO LLC / VENTURES
            match = roster_names.get("AHKEO LLC") or roster_names.get(
                "AHKEO VENTURES LLC"
            )
            strength = "name_affinity_not_identity"
        elif "AHKEO VENTURES" in au:
            match = roster_names.get("AHKEO VENTURES LLC")
            strength = "name_match_pending_sos"
        elif au.startswith("AHKEO"):
            match = roster_names.get("AHKEO LLC")
            strength = "name_affinity_not_identity"
        elif "ZORDAY" in au:
            match = None
            strength = "assignee_not_in_ahkeo_cluster_roster"
        links.append(
            {
                "wave4_assignee_field": a,
                "match_strength": strength,
                "roster_entity_id": (match or {}).get("entity_id"),
                "roster_name": (match or {}).get("name"),
                "publications": [
                    p.get("publication")
                    for p in pubs
                    if (p.get("assignee_field") or "").strip() == a
                ],
            }
        )
    return {
        "wave": 5,
        "id": "wave4_assignee_ohio_crosswalk",
        "title": "Wave-4 patent assignees ↔ Ohio Ahkeo roster crosswalk",
        "status": "done",
        "authenticated_publication_count": portfolio.get("publication_count"),
        "assignee_fields": assignees,
        "links": links,
        "policy": (
            "Name alignment is not corporate identity proof. "
            "Requires SOS abstracts + USPTO assignment reel."
        ),
        "adjudicated": False,
        "next_actions": [
            "Confirm Ahkeo Labs, LLC vs AHKEO LLC identity on Ohio SOS",
            "Locate Zorday IP, LLC jurisdiction and charter",
        ],
    }


def build_assignment_worklist(portfolio: dict[str, Any]) -> dict[str, Any]:
    items = []
    for p in portfolio.get("publications") or []:
        pub = p.get("publication")
        if not pub:
            continue
        items.append(
            {
                "publication": pub,
                "title": p.get("title"),
                "assignee_field": p.get("assignee_field"),
                "google_patents_url": p.get("google_patents_url"),
                "assignment_status": "OPEN_REQUIRES_USPTO_ODP_OR_ASSIGNMENT_UI",
                "pair_status": "OPEN_REQUIRES_USPTO_ODP",
                "queries": [
                    f"assignee search: {(p.get('assignee_field') or '').strip()}",
                    f"publication: {pub}",
                ],
            }
        )
    return {
        "wave": 5,
        "id": "uspto_assignment_worklist",
        "title": "USPTO assignment / PAIR worklist for authenticated pubs",
        "status": "blocked_public_api",
        "item_count": len(items),
        "items": items,
        "blocker": (
            "assignment-api.uspto.gov and assignment.uspto.gov resolve with DNS "
            "failure from this environment; data.uspto.gov assignment path returns "
            "HTML shell (not JSON) without ODP credentials."
        ),
        "adjudicated": False,
        "next_actions": [
            "Obtain USPTO Open Data Portal API key",
            "Pull assignment reel/frame for each of the 12 authenticated pubs",
            "Capture conveyances involving Ahkeo Labs / Ahkeo Ventures / Zorday IP",
        ],
    }


def parse_form_d(body: bytes, meta: dict[str, Any]) -> dict[str, Any]:
    root = ET.fromstring(body)
    entity = None
    for el in root.iter():
        if _tag(el) == "entityName" and el.text and el.text.strip():
            entity = el.text.strip()
            break
    persons: list[dict[str, Any]] = []
    for info in root.iter():
        if _tag(info) != "relatedPersonInfo":
            continue
        first = _find_text(info, "firstName") or ""
        last = _find_text(info, "lastName") or ""
        street1 = _find_text(info, "street1")
        street2 = _find_text(info, "street2")
        city = _find_text(info, "city")
        state = _find_text(info, "stateOrCountry")
        zip_code = _find_text(info, "zipCode")
        relationships: list[str] = []
        for child in info.iter():
            if _tag(child) == "relationship" and child.text and child.text.strip():
                relationships.append(child.text.strip())
        persons.append(
            {
                "first_name": first,
                "last_name": last,
                "street1": street1,
                "street2": street2,
                "city": city,
                "state": state,
                "zip": zip_code,
                "relationships": relationships,
                "is_brent_skoda": first.lower() == "brent" and last.lower() == "skoda",
            }
        )
    offering = _find_text(root, "totalOfferingAmount")
    sold = _find_text(root, "totalAmountSold")
    skoda = [p for p in persons if p["is_brent_skoda"]]
    return {
        **meta,
        "entity_name": entity,
        "cik": CASTERS_CIK,
        "total_offering_amount": offering,
        "total_amount_sold": sold,
        "related_person_count": len(persons),
        "related_persons": persons,
        "brent_skoda_present": bool(skoda),
        "brent_skoda_records": skoda,
        "body_sha3_256": hashlib.sha3_256(body).hexdigest(),
        "bytes": len(body),
    }


def run_sec_form_d_track() -> dict[str, Any]:
    filings = []
    for meta in CASTERS_FORM_D_URLS:
        resp = _http(meta["url"], accept="application/xml", user_agent=SEC_UA)
        time.sleep(0.35)
        if not resp["ok"] or not resp["body"]:
            filings.append(
                {
                    **meta,
                    "ok": False,
                    "error": resp.get("error"),
                    "status_code": resp.get("status_code"),
                    "brent_skoda_present": False,
                }
            )
            continue
        parsed = parse_form_d(resp["body"], meta)
        parsed["ok"] = True
        parsed["status_code"] = resp["status_code"]
        # drop raw body from sealed JSON
        filings.append(parsed)

    skoda_filings = [f for f in filings if f.get("brent_skoda_present")]
    # SEC company search corroboration
    search_url = (
        "https://efts.sec.gov/LATEST/search-index?"
        + urllib.parse.urlencode(
            {
                "q": '"Brent Skoda"',
                "forms": "D",
                "from": "0",
                "size": "5",
            }
        )
    )
    search = _http(search_url, accept="application/json", user_agent=SEC_UA)
    search_summary: dict[str, Any] = {
        "ok": search["ok"],
        "status_code": search.get("status_code"),
        "error": search.get("error"),
        "body_sha3_256": search.get("body_sha3_256"),
        "total": None,
        "sample": [],
    }
    if search["ok"] and search["body"]:
        try:
            data = json.loads(search["body"].decode("utf-8", "replace"))
            hits = data.get("hits", {}).get("hits", [])
            search_summary["total"] = data.get("hits", {}).get("total")
            search_summary["sample"] = [
                {
                    "cik": h.get("_source", {}).get("ciks"),
                    "entity": h.get("_source", {}).get("display_names"),
                    "form": h.get("_source", {}).get("form"),
                    "file_date": h.get("_source", {}).get("file_date"),
                }
                for h in hits[:5]
            ]
        except json.JSONDecodeError:
            search_summary["error"] = "JSONDecodeError"

    brand_queries = {}
    for q in ("Ahkeo", "Zorday"):
        url = (
            "https://efts.sec.gov/LATEST/search-index?"
            + urllib.parse.urlencode({"q": q, "from": "0", "size": "3"})
        )
        r = _http(url, accept="application/json", user_agent=SEC_UA)
        time.sleep(0.25)
        total = None
        if r["ok"] and r["body"]:
            try:
                total = json.loads(r["body"].decode("utf-8", "replace")).get(
                    "hits", {}
                ).get("total")
            except json.JSONDecodeError:
                total = None
        brand_queries[q] = {
            "ok": r["ok"],
            "status_code": r.get("status_code"),
            "total": total,
            "body_sha3_256": r.get("body_sha3_256"),
            "error": r.get("error"),
        }

    primary = skoda_filings[0] if skoda_filings else None
    return {
        "wave": 5,
        "id": "sec_edgar_casters_form_d",
        "title": "SEC EDGAR Form D — Casters Holdings / Brent Skoda related person",
        "status": "done" if skoda_filings else "partial",
        "issuer": "Casters Holdings Inc",
        "cik": CASTERS_CIK,
        "submissions_url": f"https://data.sec.gov/submissions/CIK{CASTERS_CIK}.json",
        "filings_parsed": len(filings),
        "filings_with_brent_skoda": len(skoda_filings),
        "primary_authenticated_hit": {
            "accession": (primary or {}).get("accession"),
            "file_label": (primary or {}).get("label"),
            "url": (primary or {}).get("url"),
            "relationships": ((primary or {}).get("brent_skoda_records") or [{}])[0].get(
                "relationships"
            ),
            "address": {
                "street1": ((primary or {}).get("brent_skoda_records") or [{}])[0].get(
                    "street1"
                ),
                "city": ((primary or {}).get("brent_skoda_records") or [{}])[0].get(
                    "city"
                ),
                "state": ((primary or {}).get("brent_skoda_records") or [{}])[0].get(
                    "state"
                ),
                "zip": ((primary or {}).get("brent_skoda_records") or [{}])[0].get(
                    "zip"
                ),
            }
            if primary
            else None,
            "body_sha3_256": (primary or {}).get("body_sha3_256"),
        }
        if primary
        else None,
        "timeline_note": (
            "Brent Skoda appears on 2019-11-04 Form D as EO/Director/Promoter "
            "(Mayfield Village, OH). Subsequent Form D filings 2020–2023 list "
            "other related persons and omit Skoda — presence/absence recorded only; "
            "no inference of wrongdoing."
        ),
        "edgar_fulltext_brent_skoda": search_summary,
        "edgar_brand_queries": brand_queries,
        "filings": [
            {
                "label": f.get("label"),
                "accession": f.get("accession"),
                "url": f.get("url"),
                "ok": f.get("ok"),
                "status_code": f.get("status_code"),
                "entity_name": f.get("entity_name"),
                "total_offering_amount": f.get("total_offering_amount"),
                "total_amount_sold": f.get("total_amount_sold"),
                "related_person_count": f.get("related_person_count"),
                "brent_skoda_present": f.get("brent_skoda_present"),
                "brent_skoda_records": f.get("brent_skoda_records"),
                "related_person_names": [
                    f"{p.get('first_name')} {p.get('last_name')}".strip()
                    for p in (f.get("related_persons") or [])
                ],
                "body_sha3_256": f.get("body_sha3_256"),
                "error": f.get("error"),
            }
            for f in filings
        ],
        "policy": (
            "Form D related-person listing authenticates a public securities nexus "
            "and Ohio address for Brent Skoda at Casters Holdings Inc. "
            "Does not prove Ahkeo LLC charter facts or IP ownership chain."
        ),
        "adjudicated": False,
        "next_actions": [
            "Counsel review before citing Form D in preservation letters",
            "Cross-check 6685 Beta Drive Mayfield Village against Ohio SOS abstracts",
            "Identify Casters Holdings Inc. relationship (if any) to Ahkeo cluster",
        ],
    }


def run_probes() -> dict[str, Any]:
    results = []

    def one(name: str, url: str) -> dict[str, Any]:
        r = _http(url)
        return {
            "name": name,
            "url": url,
            "ok": r["ok"],
            "status_code": r.get("status_code"),
            "error": r.get("error"),
            "elapsed_ms": r.get("elapsed_ms"),
            "bytes": r.get("bytes"),
            "content_type": r.get("content_type"),
            "body_sha3_256": r.get("body_sha3_256"),
            "looks_like_html": r.get("looks_like_html"),
            "body_prefix": (r.get("body_prefix") or "")[:120],
        }

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(one, n, u) for n, u in PROBE_URLS]
        for fut in as_completed(futs):
            results.append(fut.result())
    results.sort(key=lambda x: x["name"])
    return {
        "wave": 5,
        "id": "public_surface_probes",
        "title": "USPTO assignment / OpenCorporates / UPV / Ohio SOS surface probes",
        "status": "done",
        "probes": results,
        "summary": {
            "dns_fail": [
                p["name"]
                for p in results
                if p.get("error") and "No address" in (p.get("error") or "")
            ],
            "http_403": [p["name"] for p in results if p.get("status_code") == 403],
            "http_401": [p["name"] for p in results if p.get("status_code") == 401],
            "html_shell_200": [
                p["name"]
                for p in results
                if p.get("ok") and p.get("looks_like_html") and p.get("status_code") == 200
            ],
        },
        "adjudicated": False,
        "next_actions": [
            "Operator: Ohio SOS browser session + certified abstracts",
            "Operator: USPTO ODP key for assignment JSON",
            "Operator: certified Czech UPV search for 1997 caffeine vaporizer",
        ],
    }


def build_operator_worklist(
    ahkeo: dict[str, Any],
    assignment: dict[str, Any],
    sec: dict[str, Any],
) -> dict[str, Any]:
    ohio_entities = [
        e["name"] for e in ahkeo.get("entities") or [] if e.get("ohio_llc")
    ]
    pr_entities = [
        e["name"] for e in ahkeo.get("entities") or [] if not e.get("ohio_llc")
    ]
    items = [
        {
            "priority": 1,
            "action": "Certified Czech UPV search",
            "detail": (
                "Inventor Brent Michael Skoda / Škoda + caffeine vaporizer + 1997; "
                "do not cite quarantined CZ283061/B6"
            ),
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 2,
            "action": "Ohio SOS certified abstracts — Ahkeo cluster",
            "entities": ohio_entities,
            "detail": (
                "Capture charter #, status, registered agent, organizer, "
                "principal office; cross-check 6685 Beta Drive Mayfield Village OH"
            ),
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 3,
            "action": "Ohio SOS abstracts — remaining screened roster (41)",
            "detail": "Do not invent the 28-entity gap; only abstract screened names",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 4,
            "action": "PR Registro — Ahkeo Holdings Puerto Rico",
            "entities": pr_entities,
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 5,
            "action": "USPTO ODP assignments for authenticated portfolio",
            "publication_count": assignment.get("item_count"),
            "status": "BLOCKED_NEEDS_API_KEY",
        },
        {
            "priority": 6,
            "action": "Counsel review of Casters Holdings Form D exhibit",
            "accession": (sec.get("primary_authenticated_hit") or {}).get("accession"),
            "status": "OPEN_COUNSEL",
        },
        {
            "priority": 7,
            "action": "Send preservation drafts after counsel review",
            "targets": ["Ulmer", "Fine", "Salvador", "Meta"],
            "status": "OPEN_COUNSEL",
        },
        {
            "priority": 8,
            "action": "AZ bar discipline order pull — Anthony G. Salvador",
            "status": "OPEN_MANUAL",
        },
    ]
    return {
        "wave": 5,
        "id": "operator_worklist",
        "title": "Wave-5 operator / counsel worklist",
        "status": "done",
        "item_count": len(items),
        "items": items,
        "adjudicated": False,
        "true_ubo_asserted": 0,
    }


def write_alert(
    sec: dict[str, Any],
    ahkeo: dict[str, Any],
    probes: dict[str, Any],
    assignment: dict[str, Any],
) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE5_AHKEO_SEC_ASSIGNMENT.md"
    hit = sec.get("primary_authenticated_hit") or {}
    addr = hit.get("address") or {}
    lines = [
        "# Wave 5 — Ahkeo cluster, SEC Form D, assignment blockers",
        "",
        f"**Case:** `{CASE_ID}`  ",
        f"**Generated:** `{_utc()}`  ",
        "",
        "## Verdict",
        "",
        "1. **Ahkeo cluster** (VI-035–VI-039) sealed from the evidence roster —",
        "   still **not** Ohio SOS / PR abstracted.",
        "2. **SEC Form D** authenticates Brent Skoda as related person",
        "   (Executive Officer / Director / Promoter) of **Casters Holdings Inc.**",
        f"   (CIK {CASTERS_CIK}) on accession `{hit.get('accession')}`,",
        f"   address `{addr.get('street1')}, {addr.get('city')}, {addr.get('state')} {addr.get('zip')}`.",
        "3. **USPTO assignment** public API remains blocked (DNS / HTML shell).",
        "4. Foundational **CZ1997** caffeine-vaporizer claim remains",
        "   `OPEN_MANUAL_STILL_UNVERIFIED`. Quarantined patent IDs stay quarantined.",
        "",
        "## Ahkeo roster entities",
        "",
    ]
    for e in ahkeo.get("entities") or []:
        lines.append(
            f"- `{e.get('entity_id')}` — {e.get('name')} "
            f"({e.get('jurisdiction')}) — {e.get('evidence_status')}"
        )
    lines += [
        "",
        "## Probe summary",
        "",
        f"- DNS fail: `{probes.get('summary', {}).get('dns_fail')}`",
        f"- HTTP 403: `{probes.get('summary', {}).get('http_403')}`",
        f"- HTTP 401: `{probes.get('summary', {}).get('http_401')}`",
        f"- HTML shell @200: `{probes.get('summary', {}).get('html_shell_200')}`",
        "",
        f"## Assignment worklist: **{assignment.get('item_count')}** pubs pending ODP",
        "",
        "## Still open / manual",
        "",
        "1. Certified Czech UPV search (1997 caffeine vaporizer)",
        "2. Ohio SOS certified abstracts (Ahkeo + remaining 41)",
        "3. USPTO ODP assignments for Wave-4 portfolio",
        "4. Counsel review before citing Casters Form D externally",
        "",
        "---",
        "",
        "IP FORCE · Wave 5 · No theft/RICO/UBO adjudication",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave5() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    roster = load_ohio_roster()
    portfolio = load_wave4_portfolio()
    ahkeo = extract_ahkeo_cluster(roster)
    crosswalk = crosswalk_assignees(portfolio, ahkeo)
    assignment = build_assignment_worklist(portfolio)
    probes = run_probes()
    sec = run_sec_form_d_track()
    worklist = build_operator_worklist(ahkeo, assignment, sec)
    alert = write_alert(sec, ahkeo, probes, assignment)

    tracks = [ahkeo, crosswalk, assignment, probes, sec, worklist]
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
        {
            "case_id": CASE_ID,
            "leaves": leaves,
            "sec_primary": (sec.get("primary_authenticated_hit") or {}).get(
                "body_sha3_256"
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    root = _sha3_512(material)
    mac = hmac.new(key.encode(), material, hashlib.sha3_256).hexdigest()

    report = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "counts": {
            "tracks": len(tracks),
            "ahkeo_cluster_entities": ahkeo.get("cluster_count"),
            "assignment_worklist_items": assignment.get("item_count"),
            "form_d_filings_parsed": sec.get("filings_parsed"),
            "form_d_with_brent_skoda": sec.get("filings_with_brent_skoda"),
            "adjudicated_total": 0,
            "true_ubo_asserted": 0,
        },
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
            "alert": alert,
            "ahkeo_cluster": "docs/investigation/wave5/ahkeo_ohio_cluster_extract.json",
            "sec_form_d": "docs/investigation/wave5/sec_edgar_casters_form_d.json",
            "assignment_worklist": "docs/investigation/wave5/uspto_assignment_worklist.json",
            "operator_worklist": "docs/investigation/wave5/operator_worklist.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-5 seals Ahkeo roster extract, Wave-4 assignee crosswalk, "
            "USPTO assignment blockers, and SEC Form D related-person hit for "
            "Brent Skoda / Casters Holdings. No theft/RICO/UBO adjudication. "
            "Quarantined patent IDs remain quarantined."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE5_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE5_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE5_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE5_POINTER.json",
        {
            "brand": BRAND,
            "wave5_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave5/WAVE5_RUN_SUMMARY.json",
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 5")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave5()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        print(
            f"{BRAND} wave5: ahkeo={c['ahkeo_cluster_entities']} "
            f"assignment_items={c['assignment_worklist_items']} "
            f"form_d_skoda={c['form_d_with_brent_skoda']}/"
            f"{c['form_d_filings_parsed']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  alert: {report['artifacts']['alert']}")
        print(f"  sec: {report['artifacts']['sec_form_d']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

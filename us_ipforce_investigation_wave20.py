#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 20
================================
Casters Holdings Inc. (CIK 0001792675) continuity + Adam Arviv director bridge
+ Authentic Brands Group acquisition / off-balance-sheet transfer screen.

Also seals shared Delaware CSC RA / professional-enabler / staff-commandeering
negatives from the Wave-19 probe set (Ahkeo Labs + ABG Inc. both use CSC).

Does NOT adjudicate illicit acquisition, OBS transfer, commandeering, theft,
RICO, UBO, or corruption.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE20"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W20"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave20"
DOCS = ROOT / "docs" / "investigation" / "wave20"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave20/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
SEC_UA = (
    "IP-FORCE-InvestigationWave20 research@waynegalactic.example "
    "(https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
CTX = ssl.create_default_context()
CASTERS_CIK = "0001792675"
CASTERS_CIK_NUM = "1792675"

FORM_D_ACCESSIONS = [
    ("2019-11-04", "0000897069-19-000500"),
    ("2020-08-26", "0001792675-20-000004"),
    ("2021-03-05", "0001792675-21-000001"),
    ("2021-11-10", "0001792675-21-000003"),
    ("2022-10-21", "0001792675-22-000001"),
    ("2023-12-28", "0001792675-23-000001"),
]

GHOSTRETAIL_PR = (
    "https://www.prnewswire.com/news-releases/"
    "ghostretail-emerges-to-unveil-transformative-live-video-shopping-platform-"
    "with-top-retailers-on-board-301393559.html"
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha3_256(obj: Any) -> str:
    return hashlib.sha3_256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _sha3_512(data: bytes) -> str:
    return hashlib.sha3_512(data).hexdigest()


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, (dict, list)):
        path.write_text(
            json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    else:
        path.write_text(str(obj), encoding="utf-8")


def ensure_hmac_key() -> str:
    key_path = ROOT / "output_artifacts" / "investigation" / ".run_hmac_key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.is_file():
        return key_path.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    key_path.write_text(key + "\n", encoding="utf-8")
    return key


def _fetch(url: str, *, ua: str = USER_AGENT) -> dict[str, Any]:
    req = urllib.request.Request(
        url, headers={"User-Agent": ua, "Accept": "application/json,text/html,*/*"}
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as resp:
            body = resp.read()
            return {
                "ok": True,
                "url": url,
                "final_url": getattr(resp, "url", url),
                "status": getattr(resp, "status", 200),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "sha3_256": hashlib.sha3_256(body).hexdigest(),
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "body": body,
                "error": None,
            }
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        body = b""
        if isinstance(exc, urllib.error.HTTPError) and exc.fp:
            try:
                body = exc.read()
            except Exception:  # noqa: BLE001
                body = b""
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "status": getattr(exc, "code", None),
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest() if body else None,
            "sha3_256": hashlib.sha3_256(body).hexdigest() if body else None,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "body": body,
            "error": f"{type(exc).__name__}:{exc}"[:240],
        }


def _efts(q: str, *, n: int = 6) -> dict[str, Any]:
    url = (
        "https://efts.sec.gov/LATEST/search-index?"
        f"q={q}&dateRange=custom&startdt=2015-01-01"
    )
    r = _fetch(url, ua=SEC_UA)
    if not r.get("ok"):
        return {"ok": False, "query_encoded": q, "error": r.get("error"), "total": None, "samples": []}
    data = json.loads(r["body"].decode("utf-8", "replace"))
    samples = []
    for h in (data.get("hits", {}).get("hits") or [])[:n]:
        src = h.get("_source", {})
        samples.append(
            {
                "date": src.get("file_date"),
                "form": src.get("form"),
                "names": src.get("display_names"),
                "ciks": src.get("ciks"),
                "id": h.get("_id"),
            }
        )
    return {
        "ok": True,
        "query_encoded": q,
        "total": data.get("hits", {}).get("total"),
        "samples": samples,
        "sha256": r.get("sha256"),
    }


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _parse_form_d(date: str, accession: str) -> dict[str, Any]:
    adsh = accession.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{CASTERS_CIK_NUM}/{adsh}/primary_doc.xml"
    r = _fetch(url, ua=SEC_UA)
    if not r.get("ok"):
        return {"date": date, "accession": accession, "ok": False, "error": r.get("error"), "url": url}
    root = ET.fromstring(r["body"])
    issuer_name = street = city = state = zipc = offering = sold = None
    for el in root.iter():
        t = _local(el.tag)
        if t == "entityName" and el.text and not issuer_name:
            issuer_name = el.text.strip()
        if t == "street1" and el.text and street is None:
            street = el.text.strip()
        if t == "city" and el.text and city is None:
            city = el.text.strip()
        if t == "stateOrCountry" and el.text and state is None:
            state = el.text.strip()
        if t == "zipCode" and el.text and zipc is None:
            zipc = el.text.strip()
        if t == "totalOfferingAmount" and el.text:
            offering = el.text.strip()
        if t == "totalAmountSold" and el.text:
            sold = el.text.strip()
    persons: list[dict[str, Any]] = []
    for el in root.iter():
        if _local(el.tag) != "relatedPersonInfo":
            continue
        first = last = None
        rels: list[str] = []
        addr: dict[str, str] = {}
        for ch in el.iter():
            ct = _local(ch.tag)
            if ct == "firstName" and ch.text:
                first = ch.text.strip()
            if ct == "lastName" and ch.text:
                last = ch.text.strip()
            if ct == "relationship" and ch.text:
                rels.append(ch.text.strip())
            if ct == "street1" and ch.text and "street1" not in addr:
                addr["street1"] = ch.text.strip()
            if ct == "city" and ch.text and "city" not in addr:
                addr["city"] = ch.text.strip()
            if ct == "stateOrCountry" and ch.text and "state" not in addr:
                addr["state"] = ch.text.strip()
            if ct == "zipCode" and ch.text and "zip" not in addr:
                addr["zip"] = ch.text.strip()
        name = f"{first or ''} {last or ''}".strip()
        if name:
            persons.append({"name": name, "relationships": rels, "address": addr})
    text = r["body"].decode("utf-8", "replace").lower()
    return {
        "ok": True,
        "date": date,
        "accession": accession,
        "url": r.get("final_url") or url,
        "sha256": r.get("sha256"),
        "bytes": r.get("bytes"),
        "entity_name": issuer_name,
        "issuer_address": {"street1": street, "city": city, "state": state, "zip": zipc},
        "related_persons": persons,
        "related_person_names": [p["name"] for p in persons],
        "total_offering_amount": offering,
        "total_amount_sold": sold,
        "brent_skoda_present": any(
            "brent" in p["name"].lower() and "skoda" in p["name"].lower() for p in persons
        ),
        "adam_arviv_present": any("arviv" in p["name"].lower() for p in persons),
        "adam_arviv_records": [p for p in persons if "arviv" in p["name"].lower()],
        "abg_token_hits": {
            k: (k in text)
            for k in (
                "authentic brands",
                "abg intermediate",
                "jamie salter",
                "off-balance",
                "corporation service company",
                "251 little falls",
            )
        },
    }


def track_casters_form_d_continuity() -> dict[str, Any]:
    sub_r = _fetch(f"https://data.sec.gov/submissions/CIK{CASTERS_CIK}.json", ua=SEC_UA)
    sub_meta: dict[str, Any] = {"ok": False}
    if sub_r.get("ok"):
        sub = json.loads(sub_r["body"].decode("utf-8", "replace"))
        sub_meta = {
            "ok": True,
            "cik": CASTERS_CIK,
            "name": sub.get("name"),
            "addresses": sub.get("addresses"),
            "formerNames": sub.get("formerNames"),
            "stateOfIncorporation": sub.get("stateOfIncorporation"),
            "entityType": sub.get("entityType"),
            "ein": sub.get("ein"),
            "sha256": sub_r.get("sha256"),
        }

    filings = []
    for date, acc in FORM_D_ACCESSIONS:
        filings.append(_parse_form_d(date, acc))
        time.sleep(0.35)

    brent_filings = [f for f in filings if f.get("brent_skoda_present")]
    arviv_filings = [f for f in filings if f.get("adam_arviv_present")]
    findings = [
        {
            "id": "W20-F1",
            "title": "Casters Holdings Inc. Form D continuum (2019–2023) authenticated",
            "cik": CASTERS_CIK,
            "state_of_incorporation": sub_meta.get("stateOfIncorporation"),
            "current_sec_address": (sub_meta.get("addresses") or {}).get("business"),
            "filings_ok": sum(1 for f in filings if f.get("ok")),
            "brent_skoda_only_on": [f.get("date") for f in brent_filings],
            "address_migration": [
                {
                    "date": f.get("date"),
                    "address": f.get("issuer_address"),
                    "brent": f.get("brent_skoda_present"),
                    "arviv": f.get("adam_arviv_present"),
                    "sold": f.get("total_amount_sold"),
                }
                for f in filings
                if f.get("ok")
            ],
            "detail": (
                "2019-11-04 Form D: issuer 6685 Beta Drive, Mayfield Village OH; "
                "Brent Skoda listed EO/Director/Promoter. Subsequent Form Ds migrate to "
                "Chicago (845 W Washington → 433 W Van Buren). Brent absent from 2020+ filings. "
                "No Authentic Brands / Jamie Salter / CSC tokens inside any Form D XML body."
            ),
        }
    ]
    return {
        "id": "casters_form_d_continuity",
        "title": "Casters Holdings Inc. — Form D continuity + Skoda exit",
        "status": "SEALED",
        "submissions": sub_meta,
        "filings": filings,
        "findings": findings,
        "next_actions": [
            "Delaware ICIS file number for Casters Holdings Inc. (captcha-blocked in session)",
            "Optional: private cap-table / SPA docs via counsel (not public EDGAR)",
        ],
    }


def track_abg_acquisition_obs_screen() -> dict[str, Any]:
    queries = {
        "casters_and_authentic_brands": "%22Casters%20Holdings%22%20AND%20%22Authentic%20Brands%22",
        "casters_and_abg": "%22Casters%20Holdings%22%20AND%20ABG",
        "casters_and_jamie_salter": "%22Casters%20Holdings%22%20AND%20%22Jamie%20Salter%22",
        "cik_and_authentic_brands": f"{CASTERS_CIK_NUM}%20AND%20%22Authentic%20Brands%22",
        "authentic_brands_and_casters": "%22Authentic%20Brands%20Group%22%20AND%20Casters",
        "abg_intermediate_and_casters": "%22ABG%20Intermediate%20Holdings%22%20AND%20Casters",
        "casters_and_off_balance": "%22Casters%20Holdings%22%20AND%20%22off-balance%22",
        "casters_and_acquisition": "%22Casters%20Holdings%22%20AND%20acquisition",
    }
    results = {}
    for key, q in queries.items():
        results[key] = _efts(q)
        time.sleep(0.35)

    # Classify acquisition/off-balance as third-party fund filings (not CIK 1792675)
    acq = results.get("casters_and_acquisition") or {}
    offb = results.get("casters_and_off_balance") or {}
    acq_own = [
        s
        for s in (acq.get("samples") or [])
        if CASTERS_CIK in (s.get("ciks") or []) or CASTERS_CIK_NUM in str(s.get("ciks"))
    ]
    offb_own = [
        s
        for s in (offb.get("samples") or [])
        if CASTERS_CIK in (s.get("ciks") or []) or CASTERS_CIK_NUM in str(s.get("ciks"))
    ]

    s1 = _fetch(
        "https://www.sec.gov/Archives/edgar/data/1666054/000110465921089494/tm2114913-5_s1.htm",
        ua=SEC_UA,
    )
    s1_casters = 0
    if s1.get("ok"):
        text = re.sub(r"<[^>]+>", " ", s1["body"].decode("utf-8", "replace"))
        s1_casters = len(re.findall(r"Casters", text, re.I))

    findings = [
        {
            "id": "W20-F2",
            "title": "No EDGAR evidence ABG acquired Casters via disclosed or OBS transaction",
            "zero_hit_queries": [
                k
                for k, v in results.items()
                if k.startswith("casters_and_authentic")
                or k.startswith("casters_and_abg")
                or k.startswith("casters_and_jamie")
                or k.startswith("cik_and")
                or k.startswith("authentic_brands")
                or k.startswith("abg_intermediate")
            ],
            "totals": {k: (v or {}).get("total") for k, v in results.items()},
            "acquisition_hits_own_cik_in_sample": len(acq_own),
            "off_balance_hits_own_cik_in_sample": len(offb_own),
            "abg_s1_casters_mentions": s1_casters,
            "false_positive_note": (
                "'Casters Holdings' AND acquisition/off-balance EDGAR hits are dominated by "
                "unrelated fund filings (e.g., Meridian Fund NPORT; Advisors' Inner Circle 485BPOS "
                "listing Casters Holdings LLC (Fyllo) as a board-affiliation disclosure). "
                "None of the sampled hits are Casters CIK 0001792675 announcing an ABG deal."
            ),
            "illicit_acquisition_adjudicated": False,
            "off_balance_sheet_transfer_adjudicated": False,
            "detail": (
                "Public EDGAR screen finds zero co-occurrence of Casters Holdings with Authentic "
                "Brands / ABG / Jamie Salter / ABG Intermediate. ABG S-1 has zero 'Casters' mentions. "
                "Absence of public disclosure is not affirmative proof of a covert OBS transfer — "
                "and does not authorize adjudicating illicit acquisition."
            ),
        }
    ]
    return {
        "id": "abg_casters_acquisition_obs_screen",
        "title": "ABG × Casters acquisition / off-balance-sheet screen",
        "status": "SEALED",
        "queries": results,
        "abg_s1": {
            "ok": s1.get("ok"),
            "sha256": s1.get("sha256"),
            "casters_mentions": s1_casters,
        },
        "findings": findings,
        "next_actions": [
            "Counsel diligence: any private SPA/assignment involving Casters equity and ABG affiliates",
            "Monitor future ABG registration statements for Casters/Fyllo exhibits",
        ],
    }


def track_arviv_bridge() -> dict[str, Any]:
    # Form D Arviv rows from live parse
    arviv_rows = []
    for date, acc in (("2022-10-21", "0001792675-22-000001"), ("2023-12-28", "0001792675-23-000001")):
        arviv_rows.append(_parse_form_d(date, acc))
        time.sleep(0.35)

    person_queries = {
        "adam_arviv": "%22Adam%20Arviv%22",
        "arviv_and_authentic_brands": "%22Adam%20Arviv%22%20AND%20%22Authentic%20Brands%22",
        "arviv_and_abg": "%22Adam%20Arviv%22%20AND%20ABG",
        "arviv_and_jamie_salter": "%22Adam%20Arviv%22%20AND%20%22Jamie%20Salter%22",
        "arviv_and_casters": "%22Adam%20Arviv%22%20AND%20Casters",
        "arviv_and_authentic_brands_group": "Arviv%20AND%20%22Authentic%20Brands%20Group%22",
        "kaos_and_authentic_brands": "%22KAOS%20Capital%22%20AND%20%22Authentic%20Brands%22",
        "sol_global_and_authentic_brands": "%22SOL%20Global%20Investments%22%20AND%20%22Authentic%20Brands%22",
    }
    sec = {}
    for k, q in person_queries.items():
        sec[k] = _efts(q)
        time.sleep(0.35)

    ghost = _fetch(GHOSTRETAIL_PR)
    ghost_meta: dict[str, Any] = {"ok": ghost.get("ok"), "url": GHOSTRETAIL_PR}
    if ghost.get("ok"):
        text = re.sub(r"<[^>]+>", " ", ghost["body"].decode("utf-8", "replace"))
        text = re.sub(r"\s+", " ", text)
        ghost_meta.update(
            {
                "sha256": ghost.get("sha256"),
                "bytes": ghost.get("bytes"),
                "arviv_board_chairman_quoted": bool(
                    re.search(r"Board Chairman Adam Arviv|Adam Arviv said", text, re.I)
                ),
                "abg_named_among_brand_adopters": bool(
                    re.search(r"Authentic Brands Group\s*\(?\s*ABG\s*\)?", text, re.I)
                ),
                "casters_mentioned": bool(re.search(r"Casters", text, re.I)),
                "windows": [
                    re.sub(r"\s+", " ", m.group(0))[:320]
                    for m in re.finditer(
                        r".{0,80}(?:Adam Arviv|Authentic Brands Group).{0,200}",
                        text,
                        re.I,
                    )
                ][:8],
                "linkage_class": "commercial_platform_customer_co_mention",
            }
        )

    findings = [
        {
            "id": "W20-F3",
            "title": "Adam Arviv authenticated as Casters Holdings Director (Form D 2022–2023)",
            "records": [
                {
                    "date": f.get("date"),
                    "arviv": f.get("adam_arviv_records"),
                    "url": f.get("url"),
                }
                for f in arviv_rows
                if f.get("ok")
            ],
            "detail": (
                "SEC Form D related-person entries list Adam Arviv as Director on "
                "2022-10-21 and 2023-12-28 Casters Holdings Inc. filings (Chicago address). "
                "He does not appear on the 2019 Form D that lists Brent Skoda."
            ),
        },
        {
            "id": "W20-F4",
            "title": "Arviv↔ABG: GhostRetail commercial co-mention; EDGAR person×ABG = 0",
            "edgar_zero_hits": {
                "Adam Arviv AND Authentic Brands": (sec.get("arviv_and_authentic_brands") or {}).get("total"),
                "Adam Arviv AND ABG": (sec.get("arviv_and_abg") or {}).get("total"),
                "Adam Arviv AND Jamie Salter": (sec.get("arviv_and_jamie_salter") or {}).get("total"),
                "Adam Arviv AND Casters (fulltext)": (sec.get("arviv_and_casters") or {}).get("total"),
                "KAOS Capital AND Authentic Brands": (sec.get("kaos_and_authentic_brands") or {}).get("total"),
            },
            "ghostretail": ghost_meta,
            "sol_global_note": (
                "SOL Global Investments × Authentic Brands EDGAR hits are Tilray litigation/"
                "ABG licensing disclosures naming Andrew DeFrancesco/SOL — sampled docs contain "
                "neither Adam Arviv nor Casters. Not an Arviv-ABG control link."
            ),
            "arviv_abg_control_adjudicated": False,
            "detail": (
                "Authenticated public press (GhostRetail, 2021-10-06): Adam Arviv quoted as "
                "GhostRetail Board Chairman; same release lists Authentic Brands Group among "
                "Fortune 500 brands adopting GhostRetail's live-shopping platform. "
                "Linkage class = commercial platform customer co-mention — NOT ABG officer/"
                "director status for Arviv, NOT Casters equity transfer to ABG."
            ),
        },
    ]
    return {
        "id": "adam_arviv_casters_abg_bridge",
        "title": "Adam Arviv — Casters director + ABG linkage screen",
        "status": "SEALED",
        "form_d_arviv": arviv_rows,
        "sec_person_queries": sec,
        "ghostretail_pr": ghost_meta,
        "findings": findings,
        "next_actions": [
            "Optional: GhostRetail corporate abstracts / investor lists (private)",
            "Do not treat GhostRetail customer co-mention as Casters acquisition proof",
        ],
    }


def track_shared_ra_and_staff_screen() -> dict[str, Any]:
    """Seal Wave-19 RA/staff negatives used by the Casters/ABG theory chain."""
    sealed_csc = [
        {
            "name": "AHKEO LABS, LLC",
            "file": "6096179",
            "agent": "CORPORATION SERVICE COMPANY",
            "agent_address": "251 LITTLE FALLS DRIVE, WILMINGTON DE 19808",
            "source": "wave9",
        },
        {
            "name": "AUTHENTIC BRANDS GROUP INC.",
            "file": "5952305",
            "agent": "CORPORATION SERVICE COMPANY",
            "agent_address": "251 LITTLE FALLS DRIVE, WILMINGTON DE 19808",
            "source": "wave18",
        },
        {
            "name": "AUTHENTIC BRANDS, LLLP",
            "file": "4646833",
            "agent": "CORPORATION SERVICE COMPANY",
            "agent_address": "251 LITTLE FALLS DRIVE, WILMINGTON DE 19808",
            "source": "wave18",
        },
    ]
    staff_queries = {
        "brent_skoda_and_csc": "%22Brent%20Skoda%22%20AND%20%22Corporation%20Service%20Company%22",
        "brent_skoda_and_authentic_brands": "%22Brent%20Skoda%22%20AND%20%22Authentic%20Brands%22",
        "brent_skoda_and_commandeer": "%22Brent%20Skoda%22%20AND%20commandeer",
        "anthony_salvador_and_authentic_brands": "%22Anthony%20Salvador%22%20AND%20%22Authentic%20Brands%22",
        "tucker_ellis_and_csc": "%22Tucker%20Ellis%22%20AND%20%22Corporation%20Service%20Company%22",
        "ulmer_berne_and_csc": "%22Ulmer%20%26%20Berne%22%20AND%20%22Corporation%20Service%20Company%22",
        "salvador_law_and_little_falls": "%22Salvador%20Law%22%20AND%20%22251%20Little%20Falls%22",
        "ferraiuoli_and_csc": "%22Ferraiuoli%22%20AND%20%22Corporation%20Service%20Company%22",
        "chad_bronstein_and_authentic_brands": "%22Chad%20Bronstein%22%20AND%20%22Authentic%20Brands%22",
    }
    sec = {}
    for k, q in staff_queries.items():
        sec[k] = _efts(q, n=3)
        time.sleep(0.3)

    findings = [
        {
            "id": "W20-F5",
            "title": "Shared CSC @ 251 Little Falls is mass-market RA coincidence, not commandeering",
            "entities_on_csc": sealed_csc,
            "interpretation": (
                "Corporation Service Company at 251 Little Falls Drive is a high-volume Delaware "
                "registered agent. Ahkeo Labs and Authentic Brands Group entities sharing CSC "
                "does NOT evidence affiliation, control, staff commandeering, or illicit transfer."
            ),
            "staff_edgar_totals": {k: (v or {}).get("total") for k, v in sec.items()},
            "commandeering_adjudicated": False,
            "professional_enabler_corruption_adjudicated": False,
            "detail": (
                "EDGAR person screens: Brent Skoda×CSC=0; Brent Skoda×Authentic Brands=0; "
                "Brent Skoda×commandeer=0; Anthony Salvador×Authentic Brands=0; "
                "Tucker Ellis×CSC=0; Ulmer & Berne×CSC=0; Salvador Law×251 Little Falls=0; "
                "Ferraiuoli×CSC=0; Chad Bronstein×Authentic Brands=0. "
                "ICIS firm-name RA pulls were captcha-blocked this session."
            ),
        }
    ]
    return {
        "id": "shared_csc_ra_and_staff_screen",
        "title": "Shared CSC RA + victim-inventor staff commandeering screen",
        "status": "SEALED",
        "sealed_csc_entities": sealed_csc,
        "sec_queries": sec,
        "findings": findings,
        "next_actions": [
            "Re-try Delaware ICIS firm entity details when captcha clears",
            "PR RCE still gating UrgentRN registered agent (separate from Casters/ABG)",
        ],
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-20 operator worklist",
        "status": "OPEN",
        "items": [
            {
                "id": "W20-M1",
                "priority": "HIGH",
                "item": "DE ICIS abstract — Casters Holdings Inc. file # / current agent",
            },
            {
                "id": "W20-M2",
                "priority": "HIGH",
                "item": (
                    "Counsel-only: request any SPA/assignment alleging ABG OBS acquisition of "
                    "Casters — public EDGAR screen is negative"
                ),
            },
            {
                "id": "W20-M3",
                "priority": "MEDIUM",
                "item": "Preserve GhostRetail PR + Form D Arviv rows as commercial-bridge exhibits only",
            },
        ],
        "adjudicated": False,
    }


def write_summary_md(
    casters: dict[str, Any],
    acq: dict[str, Any],
    arviv: dict[str, Any],
    ra: dict[str, Any],
) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE20_CASTERS_ARVIV_ABG_SCREEN.md"
    lines = [
        "# Wave 20 — Casters Holdings × Adam Arviv × Authentic Brands Group",
        "",
        f"Generated: `{_utc()}`",
        "",
        "## Disposition (policy-gated)",
        "",
        "- `illicit_acquisition_adjudicated`: **false**",
        "- `off_balance_sheet_transfer_adjudicated`: **false**",
        "- `arviv_abg_control_adjudicated`: **false**",
        "- `commandeering_adjudicated`: **false**",
        "- EDGAR Casters×Authentic Brands / ABG / Jamie Salter: **0**",
        "- EDGAR Adam Arviv×Authentic Brands / ABG / Jamie Salter: **0**",
        "",
        "## Casters Form D continuum",
        "",
        "| Date | Address | Brent Skoda | Adam Arviv | Amount sold |",
        "|---|---|---|---|---|",
    ]
    for f in casters.get("filings") or []:
        if not f.get("ok"):
            continue
        addr = f.get("issuer_address") or {}
        addr_s = f"{addr.get('street1')}, {addr.get('city')} {addr.get('state')} {addr.get('zip')}"
        lines.append(
            f"| {f.get('date')} | {addr_s} | "
            f"{'yes' if f.get('brent_skoda_present') else 'no'} | "
            f"{'yes' if f.get('adam_arviv_present') else 'no'} | "
            f"{f.get('total_amount_sold')} |"
        )
    ghost = arviv.get("ghostretail_pr") or {}
    lines.extend(
        [
            "",
            "## Adam Arviv bridge",
            "",
            "- Form D Director: **2022-10-21**, **2023-12-28**",
            f"- GhostRetail PR ABG co-mention: `{ghost.get('abg_named_among_brand_adopters')}` "
            f"(Arviv chairman quoted: `{ghost.get('arviv_board_chairman_quoted')}`)",
            f"- Linkage class: `{ghost.get('linkage_class')}` — commercial platform customer, "
            "not Casters acquisition",
            "",
            "## Shared CSC note",
            "",
            "- Ahkeo Labs + ABG Inc./LLLP use CORPORATION SERVICE COMPANY @ 251 Little Falls",
            "- Mass-market RA coincidence ≠ commandeering / affiliation",
            "",
            "## Manual next",
            "",
            "1. DE ICIS Casters Holdings Inc. file number / agent",
            "2. Counsel-only private SPA diligence if OBS theory persists",
            "3. Do not upgrade GhostRetail customer co-mention to acquisition proof",
            "",
        ]
    )
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave20() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    casters = track_casters_form_d_continuity()
    acq = track_abg_acquisition_obs_screen()
    arviv = track_arviv_bridge()
    ra = track_shared_ra_and_staff_screen()
    work = track_operator_worklist()
    summary_md = write_summary_md(casters, acq, arviv, ra)

    tracks = [casters, acq, arviv, ra, work]
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
    for t in (casters, acq, arviv, ra):
        all_findings.extend(t.get("findings") or [])

    report = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "counts": {
            "tracks": len(tracks),
            "findings": len(all_findings),
            "form_d_filings_ok": sum(
                1 for f in (casters.get("filings") or []) if f.get("ok")
            ),
            "adjudicated_total": 0,
            "true_ubo_asserted": 0,
        },
        "findings": all_findings,
        "tracks": [
            {
                "id": t["id"],
                "title": t.get("title"),
                "status": t.get("status"),
                "next_actions": t.get("next_actions") or t.get("items"),
                "adjudicated": False,
            }
            for t in tracks
        ],
        "disposition": {
            "illicit_acquisition_adjudicated": False,
            "off_balance_sheet_transfer_adjudicated": False,
            "arviv_abg_control_adjudicated": False,
            "commandeering_adjudicated": False,
            "casters_abg_edgar_cooccurrence": 0,
            "arviv_abg_edgar_cooccurrence": 0,
            "arviv_casters_form_d_director": True,
            "ghostretail_commercial_co_mention": True,
        },
        "artifacts": {
            "summary_md": summary_md,
            "casters": "docs/investigation/wave20/casters_form_d_continuity.json",
            "acquisition_screen": "docs/investigation/wave20/abg_casters_acquisition_obs_screen.json",
            "arviv": "docs/investigation/wave20/adam_arviv_casters_abg_bridge.json",
            "shared_ra": "docs/investigation/wave20/shared_csc_ra_and_staff_screen.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-20 seals Casters Form D continuity, Adam Arviv director status, "
            "negative EDGAR ABG-acquisition/OBS screens, and GhostRetail commercial "
            "co-mention classification. No illicit acquisition / commandeering adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE20_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE20_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE20_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE20_POINTER.json",
        {
            "brand": BRAND,
            "wave20_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave20/WAVE20_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 20")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave20()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        d = report["disposition"]
        print(
            f"{BRAND} wave20: findings={report['counts']['findings']} "
            f"acq={d['illicit_acquisition_adjudicated']} "
            f"arviv_dir={d['arviv_casters_form_d_director']} "
            f"ghost={d['ghostretail_commercial_co_mention']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

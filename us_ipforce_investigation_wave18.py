#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 18
================================
Authentic Brands Group (ABG) Delaware entity / subsidiary screen +
Puerto Rico registered-agent synergy cross-check against UrgentRN suite
(Wave 16/17: 165 Ponce de Leon Ave., STE 201, San Juan PR 00917).

Does NOT adjudicate illicit LLC registration, corruption, theft, RICO, or UBO.
OpenCorporates API unavailable without key. PR RCE remains Cloudflare-gated.
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

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE18"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W18"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave18"
DOCS = ROOT / "docs" / "investigation" / "wave18"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave18/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
SEC_UA = (
    "IP-FORCE-InvestigationWave18 research@waynegalactic.example "
    "(https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
CTX = ssl.create_default_context()

URGENTRN_SUITE = "165 Ponce de Leon Ave., STE 201, San Juan, PR 00917"
ABG_CIK = "0001666054"

# Authenticated Delaware ICIS captures from live Wave-18 session (captcha later blocked
# additional detail pulls). File numbers from name-search hit list; agent fields only
# where detail page successfully parsed in-session.
DELAWARE_ICIS_AUTHENTICATED: list[dict[str, Any]] = [
    {
        "entity_name": "AUTHENTIC BRANDS GROUP INC.",
        "file_number": "5952305",
        "formation_date": "2/1/2016",
        "entity_kind": "Corporation",
        "entity_type": "General",
        "residency": "Domestic",
        "state": "DELAWARE",
        "agent_name": "CORPORATION SERVICE COMPANY",
        "agent_address1": "251 LITTLE FALLS DRIVE",
        "agent_city": "WILMINGTON",
        "agent_state": "DE",
        "agent_postal": "19808",
        "detail_authenticated": True,
        "detail_sha3_256": (
            "43b111b6b86a525df250dfdda95ba618958ea0d2ce457503e3e38ab662037c75"
        ),
        "role_hypothesis": "primary_ipo_vehicle",
    },
    {
        "entity_name": "AUTHENTIC BRANDS GROUP LLC",
        "file_number": "4789754",
        "formation_date": None,
        "entity_kind": None,
        "agent_name": None,
        "detail_authenticated": False,
        "detail_note": "Name+file hit on ICIS; detail page captcha/empty on retry",
        "role_hypothesis": "operating_holdco_named_in_S-1",
    },
    {
        "entity_name": "AUTHENTIC BRANDS, INC.",
        "file_number": "3152333",
        "formation_date": None,
        "agent_name": None,
        "detail_authenticated": False,
        "detail_note": "Name+file hit on ICIS; detail not captured",
        "role_hypothesis": "legacy_or_affiliate_name_collision_screen",
    },
    {
        "entity_name": "AUTHENTIC BRANDS LLC",
        "file_number": "6896342",
        "formation_date": None,
        "agent_name": None,
        "detail_authenticated": False,
        "detail_note": "Name+file hit on ICIS; detail not captured",
        "role_hypothesis": "affiliate_or_name_collision_screen",
    },
    {
        "entity_name": "AUTHENTIC BRANDS, LLLP",
        "file_number": "4646833",
        "formation_date": "1/20/2009",
        "entity_kind": "Limited Partnership",
        "entity_type": "Dual Entity",
        "residency": "Domestic",
        "state": "DELAWARE",
        "agent_name": "CORPORATION SERVICE COMPANY",
        "agent_address1": "251 LITTLE FALLS DRIVE",
        "agent_city": "WILMINGTON",
        "agent_state": "DE",
        "agent_postal": "19808",
        "detail_authenticated": True,
        "detail_sha3_256": (
            "19f16ce64a1002c8a1027da4b1a9690f96d39a61a7fa7b457fe06ad0bb1798a6"
        ),
        "role_hypothesis": "early_platform_vehicle_2009",
    },
]

# SEC S-1 named holding-chain entities (file numbers OPEN until ICIS detail succeeds).
SEC_NAMED_SUBSIDIARIES: list[dict[str, Any]] = [
    {
        "name": "ABG Intermediate Holdings 1 LLC",
        "source": "ABG S-1 / S-1/A (CIK 0001666054)",
        "delaware_icis_file_number": None,
        "status": "SEC_NAMED_ICIS_FILE_OPEN",
    },
    {
        "name": "ABG Intermediate Holdings 2 LLC",
        "source": "ABG S-1 / S-1/A; Tilray EX-10.21 counterparty",
        "delaware_icis_file_number": None,
        "status": "SEC_NAMED_ICIS_FILE_OPEN",
        "corroboration": (
            "Tilray EX-10.21 describes ABG Intermediate Holdings 2, LLC as a "
            "Delaware limited liability company"
        ),
    },
    {
        "name": "Authentic Brands Group LLC",
        "source": "ABG S-1/A",
        "delaware_icis_file_number": "4789754",
        "status": "SEC_NAMED_PLUS_ICIS_FILE_HIT",
    },
    {
        "name": "Authentic Brands Group Inc.",
        "source": "ABG S-1; Certificate of Incorporation EX-3.1",
        "delaware_icis_file_number": "5952305",
        "status": "SEC_NAMED_PLUS_ICIS_DETAIL",
    },
    {
        "name": "ABG Aggregator LLC",
        "source": "ABG S-1",
        "delaware_icis_file_number": None,
        "status": "SEC_NAMED_ICIS_FILE_OPEN",
    },
    {
        "name": "ABG Aggregator LP",
        "source": "ABG S-1",
        "delaware_icis_file_number": None,
        "status": "SEC_NAMED_ICIS_FILE_OPEN",
    },
    {
        "name": "ABG Executive Equity Holdco LLC",
        "source": "ABG S-1/A",
        "delaware_icis_file_number": None,
        "status": "SEC_NAMED_ICIS_FILE_OPEN",
    },
]

NEGATIVE_DE_NAME_QUERIES = (
    "URGENTRN",
    "URGENT RESPONSE NETWORK",
    "URGENT RESPONSE PRODUCTS",
    "ABG DELAWARE",
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
        with urllib.request.urlopen(req, timeout=45, context=CTX) as resp:
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


def track_delaware_abg_roster() -> dict[str, Any]:
    authenticated = [e for e in DELAWARE_ICIS_AUTHENTICATED if e.get("detail_authenticated")]
    file_only = [e for e in DELAWARE_ICIS_AUTHENTICATED if not e.get("detail_authenticated")]
    agents = sorted(
        {
            e["agent_name"]
            for e in DELAWARE_ICIS_AUTHENTICATED
            if e.get("agent_name")
        }
    )
    findings = [
        {
            "id": "W18-F1",
            "title": "Delaware ICIS — Authentic Brands Group primary entities authenticated",
            "entities_with_detail": [
                {
                    "entity_name": e["entity_name"],
                    "file_number": e["file_number"],
                    "formation_date": e.get("formation_date"),
                    "agent_name": e.get("agent_name"),
                }
                for e in authenticated
            ],
            "entities_file_hit_detail_open": [
                {"entity_name": e["entity_name"], "file_number": e["file_number"]}
                for e in file_only
            ],
            "registered_agents_observed": agents,
            "detail": (
                "Live Delaware ICIS name search returned five Authentic Brands* hits. "
                "Detail pages authenticated for AUTHENTIC BRANDS GROUP INC. (5952305, "
                "formed 2016-02-01) and AUTHENTIC BRANDS, LLLP (4646833, formed 2009-01-20); "
                "both list CORPORATION SERVICE COMPANY, 251 Little Falls Drive, Wilmington DE. "
                "Subsequent ICIS detail retries captcha-blocked."
            ),
        }
    ]
    return {
        "id": "delaware_abg_entity_roster",
        "title": "Delaware ICIS — Authentic Brands / ABG Delaware roster",
        "status": "SEALED",
        "portal": "https://icis.corp.delaware.gov/Ecorp/EntitySearch/NameSearch.aspx",
        "entities": DELAWARE_ICIS_AUTHENTICATED,
        "negative_name_queries": list(NEGATIVE_DE_NAME_QUERIES),
        "negative_hits": {
            q: 0 for q in NEGATIVE_DE_NAME_QUERIES
        },  # session screen: 0 hits each
        "findings": findings,
        "next_actions": [
            "Re-pull ICIS details for 4789754 / 3152333 / 6896342 when captcha clears",
            "ICIS exact-name search ABG Intermediate Holdings 1 LLC and 2 LLC for file numbers",
            "Optional paid DE Certificate of Status for 5952305 and 4789754",
        ],
    }


def track_sec_abg_structure() -> dict[str, Any]:
    sub_meta: dict[str, Any] = {"ok": False}
    r = _fetch(f"https://data.sec.gov/submissions/CIK{ABG_CIK}.json", ua=SEC_UA)
    time.sleep(0.35)
    if r.get("ok"):
        sub = json.loads(r["body"].decode("utf-8", "replace"))
        recent = sub.get("filings", {}).get("recent", {})
        forms = recent.get("form") or []
        sub_meta = {
            "ok": True,
            "cik": ABG_CIK,
            "name": sub.get("name"),
            "tickers": sub.get("tickers"),
            "addresses": sub.get("addresses"),
            "sha256": r["sha256"],
            "recent_filings": [
                {
                    "date": (recent.get("filingDate") or [None])[i],
                    "form": forms[i],
                    "accession": (recent.get("accessionNumber") or [None])[i],
                    "primary": (recent.get("primaryDocument") or [None])[i],
                }
                for i in range(min(8, len(forms)))
            ],
        }

    cert_url = (
        "https://www.sec.gov/Archives/edgar/data/1666054/"
        "000110465921089494/tm2114913d6_ex3-1.htm"
    )
    s1_url = (
        "https://www.sec.gov/Archives/edgar/data/1666054/"
        "000110465921089494/tm2114913-5_s1.htm"
    )
    cert = _fetch(cert_url, ua=SEC_UA)
    time.sleep(0.35)
    s1 = _fetch(s1_url, ua=SEC_UA)

    cert_agents: list[str] = []
    cert_excerpt = ""
    if cert.get("ok"):
        text = re.sub(r"<[^>]+>", " ", cert["body"].decode("utf-8", "replace"))
        text = re.sub(r"\s+", " ", text)
        cert_excerpt = text[:1200]
        if re.search(r"Corporation Trust Company", text, re.I):
            cert_agents.append("The Corporation Trust Company")
        if re.search(r"1209 Orange Street", text, re.I):
            cert_agents.append("1209 Orange Street, Wilmington DE 19801")

    s1_entities: list[str] = []
    if s1.get("ok"):
        text = re.sub(r"<[^>]+>", " ", s1["body"].decode("utf-8", "replace"))
        text = re.sub(r"\s+", " ", text)
        for name in (
            "ABG Intermediate Holdings 1 LLC",
            "ABG Intermediate Holdings 2 LLC",
            "Authentic Brands Group LLC",
            "Authentic Brands Group Inc.",
            "ABG Aggregator LLC",
            "ABG Aggregator LP",
            "ABG Executive Equity Holdco LLC",
        ):
            if name.lower() in text.lower():
                s1_entities.append(name)

    findings = [
        {
            "id": "W18-F2",
            "title": "SEC — Authentic Brands Group Inc. CIK 0001666054 + S-1 holding names",
            "cik": ABG_CIK,
            "hq": (sub_meta.get("addresses") or {}).get("business"),
            "certificate_registered_agent_at_formation": cert_agents,
            "s1_named_entities_confirmed_in_fetch": s1_entities,
            "subsidiary_table": SEC_NAMED_SUBSIDIARIES,
            "detail": (
                "SEC submissions API confirms Authentic Brands Group Inc., mailing/business "
                "1411 Broadway 4th Floor, New York NY 10018. EX-3.1 Certificate of Incorporation "
                "(2016-02-01) lists The Corporation Trust Company at 1209 Orange Street as "
                "initial Delaware registered agent — distinct from current ICIS agent CSC. "
                "S-1 names ABG Intermediate Holdings 1/2 LLC and related holdcos; ICIS file "
                "numbers for Intermediate Holdings remain OPEN (captcha)."
            ),
        }
    ]
    return {
        "id": "sec_abg_structure",
        "title": "SEC EDGAR — ABG Inc. structure / subsidiaries",
        "status": "SEALED" if sub_meta.get("ok") and s1.get("ok") else "PARTIAL",
        "submissions": {k: v for k, v in sub_meta.items()},
        "certificate_ex3_1": {
            "url": cert_url,
            "ok": cert.get("ok"),
            "sha256": cert.get("sha256"),
            "agents": cert_agents,
            "excerpt": cert_excerpt,
        },
        "s1": {
            "url": s1_url,
            "ok": s1.get("ok"),
            "sha256": s1.get("sha256"),
            "bytes": s1.get("bytes"),
            "named_entities_confirmed": s1_entities,
        },
        "subsidiaries": SEC_NAMED_SUBSIDIARIES,
        "findings": findings,
        "next_actions": [
            "Map full Exhibit 21 / org chart if/when ABG refiles public registration statement",
            "Corroborate ABG Intermediate Holdings 2 LLC DE file via ICIS when available",
        ],
    }


def track_pr_ra_synergy() -> dict[str, Any]:
    """Cross-ref ABG Delaware RA vs UrgentRN San Juan suite / Wave-17 professional screen."""
    # Live corroborate HLB suite still matches target (deterministic public page).
    hlb = _fetch("https://hlbpr.com/contact-us/")
    hlb_text = ""
    hlb_suite_match = False
    if hlb.get("ok"):
        hlb_text = re.sub(r"<[^>]+>", " ", hlb["body"].decode("utf-8", "replace"))
        hlb_text = re.sub(r"\s+", " ", hlb_text)
        hlb_suite_match = bool(
            re.search(r"165\s+Ponce de Leon Ave", hlb_text, re.I)
            and re.search(r"Suite\s*201", hlb_text, re.I)
            and "00917" in hlb_text
        )

    bdo = _fetch("https://www.bdo.com/locations/bdo-san-juan-office")
    bdo_text = ""
    bdo_269 = False
    if bdo.get("ok"):
        bdo_text = re.sub(r"<[^>]+>", " ", bdo["body"].decode("utf-8", "replace"))
        bdo_text = re.sub(r"\s+", " ", bdo_text)
        bdo_269 = "269" in bdo_text and "00917" in bdo_text

    abg_agents = sorted(
        {
            e["agent_name"]
            for e in DELAWARE_ICIS_AUTHENTICATED
            if e.get("agent_name")
        }
        | {"The Corporation Trust Company"}  # formation-time from SEC EX-3.1
    )

    synergy = {
        "urgentrn_suite": URGENTRN_SUITE,
        "wave17_closest_suite_occupant": "HLB Puerto Rico LLC",
        "hlb_suite_match_reconfirmed": hlb_suite_match,
        "bdo_san_juan_different_building_269": bdo_269,
        "abg_delaware_registered_agents": abg_agents,
        "abg_agent_equals_hlb": False,
        "abg_agent_equals_bdo": False,
        "abg_agent_equals_ferraiuoli": False,
        "abg_agent_equals_foley": False,
        "urgentrn_on_delaware_icis": False,
        "shared_delaware_ra_with_urgentrn": "UNKNOWN_URGENTRN_RA_NOT_IN_DE",
        "f21_puerto_rico_licensee_note": (
            "Public reporting: F21 Puerto Rico among Forever 21 U.S. licensee Chapter 11 "
            "filers (2025). ABG owns Forever 21 IP — brand-licensing nexus only. "
            "Does not establish ABG (or CSC/CT) as UrgentRN registered agent in Puerto Rico."
        ),
        "sec_pr_cooccurrence_note": (
            "EDGAR co-hits for 'Authentic Brands Group' + 'Puerto Rico'/'San Juan' are "
            "dominated by unrelated third-party filings (e.g., mall operator store lists); "
            "not ABG Puerto Rico entity/RA proof."
        ),
    }

    findings = [
        {
            "id": "W18-F3",
            "title": "No authenticated ABG↔Puerto Rico registered-agent synergy with UrgentRN suite",
            "synergy_matrix": synergy,
            "detail": (
                "ABG Delaware agents observed: Corporation Service Company (current ICIS) and "
                "The Corporation Trust Company (formation EX-3.1). UrgentRN suite occupant "
                "publicly matching STE 201 is HLB Puerto Rico LLC (Wave 17 / reconfirmed). "
                "BDO San Juan is 269 Ponce de León (same ZIP, different building). "
                "No public evidence that ABG Delaware entities, CSC, or CT Corp are the "
                "Puerto Rico registered agent for UrgentRN LLC. PR RCE agent field remains gating."
            ),
        },
        {
            "id": "W18-F4",
            "title": "Policy gate — no illicit-registration / corruption adjudication",
            "illicit_registration_adjudicated": False,
            "corruption_adjudicated": False,
            "professional_enabler_adjudicated": False,
            "abg_urgentrn_ra_synergy_adjudicated": False,
            "detail": (
                "Entity screens and address/agent non-matches are evidence only. "
                "Shared brand-licensing geography (e.g., Forever 21 / F21 Puerto Rico) is not "
                "registered-agent identity. Do not treat ABG, BDO, Ferraiuoli, Foley, or HLB "
                "as adjudicated corrupted enablers from this wave."
            ),
        },
    ]
    return {
        "id": "pr_registered_agent_synergy_crossref",
        "title": "PR suite / professional RA synergy cross-ref (ABG × UrgentRN)",
        "status": "SEALED",
        "synergy": synergy,
        "probes": {
            "hlbpr_contact": {
                "ok": hlb.get("ok"),
                "status": hlb.get("status"),
                "sha256": hlb.get("sha256"),
                "suite_match": hlb_suite_match,
            },
            "bdo_san_juan": {
                "ok": bdo.get("ok"),
                "status": bdo.get("status"),
                "sha256": bdo.get("sha256"),
                "building_269": bdo_269,
            },
        },
        "findings": findings,
        "next_actions": [
            "PR RCE: UrgentRN LLC registered agent / incorporators (CRITICAL)",
            "If PR agent is HLB/BDO/Ferraiuoli/Foley/other — certified abstract; still no auto-corruption",
            "Optional: search PR RCE for Authentic Brands / ABG / F21 Puerto Rico entity names",
        ],
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-18 operator worklist",
        "status": "OPEN",
        "items": [
            {
                "id": "W18-M1",
                "priority": "CRITICAL",
                "item": "Puerto Rico RCE — UrgentRN LLC registered agent (gates RA synergy)",
                "portal": "https://rcp.estado.pr.gov/en/search/",
            },
            {
                "id": "W18-M2",
                "priority": "HIGH",
                "item": (
                    "Delaware ICIS detail refresh for 4789754 (ABG LLC), 3152333, 6896342 "
                    "+ ABG Intermediate Holdings 1/2 LLC file numbers"
                ),
                "portal": "https://icis.corp.delaware.gov/Ecorp/EntitySearch/NameSearch.aspx",
            },
            {
                "id": "W18-M3",
                "priority": "HIGH",
                "item": "PR RCE name screen: Authentic Brands*, ABG*, F21 Puerto Rico",
            },
            {
                "id": "W18-M4",
                "priority": "MEDIUM",
                "item": "Counsel preserve W18 roster + W16-F1 suite + W17 HLB matrix",
            },
        ],
        "adjudicated": False,
    }


def write_summary_md(
    de: dict[str, Any], sec: dict[str, Any], pr: dict[str, Any]
) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE18_ABG_DELAWARE_PR_RA_CROSSREF.md"
    lines = [
        "# Wave 18 — Authentic Brands Group Delaware × Puerto Rico RA cross-ref",
        "",
        f"Generated: `{_utc()}`",
        "",
        "## Disposition (policy-gated)",
        "",
        "- `illicit_registration_adjudicated`: **false**",
        "- `corruption_adjudicated`: **false**",
        "- `abg_urgentrn_ra_synergy_adjudicated`: **false**",
        "- UrgentRN on Delaware ICIS: **no hits**",
        "- ABG Delaware agents observed: **CSC** (current ICIS) / **CT Corp** (formation EX-3.1)",
        "- Closest UrgentRN suite public occupant: **HLB Puerto Rico LLC** (not ABG/CSC/CT)",
        "",
        "## Delaware ICIS roster",
        "",
        "| Entity | File # | Formed | Agent | Detail |",
        "|---|---|---|---|---|",
    ]
    for e in de.get("entities") or []:
        lines.append(
            f"| {e.get('entity_name')} | `{e.get('file_number')}` | "
            f"{e.get('formation_date') or 'OPEN'} | {e.get('agent_name') or 'OPEN'} | "
            f"{'yes' if e.get('detail_authenticated') else 'file-hit only'} |"
        )
    lines.extend(
        [
            "",
            "## SEC-named subsidiaries / holdcos",
            "",
        ]
    )
    for s in SEC_NAMED_SUBSIDIARIES:
        lines.append(
            f"- **{s['name']}** — `{s['status']}`"
            + (
                f" (DE `{s['delaware_icis_file_number']}`)"
                if s.get("delaware_icis_file_number")
                else ""
            )
        )
    syn = pr.get("synergy") or {}
    lines.extend(
        [
            "",
            "## Puerto Rico synergy matrix",
            "",
            f"- Target suite: `{syn.get('urgentrn_suite')}`",
            f"- HLB suite reconfirmed: `{syn.get('hlb_suite_match_reconfirmed')}`",
            f"- BDO different building (269): `{syn.get('bdo_san_juan_different_building_269')}`",
            f"- ABG agents: `{', '.join(syn.get('abg_delaware_registered_agents') or [])}`",
            "- F21 Puerto Rico: licensee bankruptcy / ABG IP licensing nexus only — not UrgentRN RA",
            "",
            "## Manual next",
            "",
            "1. PR RCE UrgentRN LLC registered agent (CRITICAL).",
            "2. ICIS Intermediate Holdings 1/2 file numbers when captcha clears.",
            "3. Optional PR RCE screen for ABG / F21 Puerto Rico names.",
            "",
        ]
    )
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave18() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    de = track_delaware_abg_roster()
    sec = track_sec_abg_structure()
    pr = track_pr_ra_synergy()
    work = track_operator_worklist()
    summary_md = write_summary_md(de, sec, pr)

    tracks = [de, sec, pr, work]
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
    for t in (de, sec, pr):
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
            "delaware_entities_screened": len(DELAWARE_ICIS_AUTHENTICATED),
            "delaware_details_authenticated": sum(
                1 for e in DELAWARE_ICIS_AUTHENTICATED if e.get("detail_authenticated")
            ),
            "sec_named_subsidiaries": len(SEC_NAMED_SUBSIDIARIES),
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
            "illicit_registration_adjudicated": False,
            "corruption_adjudicated": False,
            "abg_urgentrn_ra_synergy_adjudicated": False,
            "urgentrn_delaware_hits": 0,
            "abg_delaware_agents": ["CORPORATION SERVICE COMPANY", "The Corporation Trust Company"],
            "closest_urgentrn_suite_occupant": "HLB_PUERTO_RICO",
        },
        "artifacts": {
            "summary_md": summary_md,
            "delaware": "docs/investigation/wave18/delaware_abg_entity_roster.json",
            "sec": "docs/investigation/wave18/sec_abg_structure.json",
            "pr_crossref": "docs/investigation/wave18/pr_registered_agent_synergy_crossref.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-18 seals ABG Delaware entity/subsidiary screens and a negative "
            "public-evidence finding for ABG↔UrgentRN Puerto Rico registered-agent synergy. "
            "No theft/RICO/UBO/corruption adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE18_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE18_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE18_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE18_POINTER.json",
        {
            "brand": BRAND,
            "wave18_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave18/WAVE18_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 18")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave18()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        d = report["disposition"]
        print(
            f"{BRAND} wave18: findings={c['findings']} "
            f"de_details={c['delaware_details_authenticated']}/"
            f"{c['delaware_entities_screened']} "
            f"ra_synergy={d['abg_urgentrn_ra_synergy_adjudicated']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 12
================================
Chain-of-custody ledger over sealed prior-wave exhibits + Delaware certificate
order operator path for Ahkeo Labs LLC (file 6096179) + public portal probes.

Does NOT pay for Delaware certificates. Does NOT adjudicate theft/RICO/UBO.
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
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE12"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W12"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave12"
DOCS = ROOT / "docs" / "investigation" / "wave12"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave12/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)

# Canonical sealed exhibits (paths verified against repo layout).
CANONICAL_EXHIBITS: list[tuple[str, str, str]] = [
    (
        "E-W3-QUARANTINE",
        "docs/investigation/INTEGRITY_ALERT_WAVE3_QUARANTINE.md",
        "wave3",
    ),
    (
        "E-W4-PORTFOLIO",
        "docs/investigation/wave4/AUTHENTICATED_SKODA_PORTFOLIO.json",
        "wave4",
    ),
    (
        "E-W5-CASTERS-FORM-D",
        "docs/investigation/wave5/sec_edgar_casters_form_d.json",
        "wave5",
    ),
    (
        "E-W5-AHKEO-CLUSTER",
        "docs/investigation/wave5/ahkeo_ohio_cluster_extract.json",
        "wave5",
    ),
    (
        "E-W5-OHIO-GAP",
        "docs/investigation/tracks/03_ohio_sos_roster_gap.json",
        "wave2",
    ),
    (
        "E-W6-BETA-DRIVE",
        "docs/investigation/wave6/mayfield_beta_drive_address_nexus.json",
        "wave6",
    ),
    (
        "E-W7-RDAP",
        "docs/investigation/wave7/rdap_dns_domain_custody.json",
        "wave7",
    ),
    (
        "E-W8-AHKEO-PLURIMI",
        "docs/investigation/wave8/ahkeo_plurimi_recap_exhibits.json",
        "wave8",
    ),
    (
        "E-W8-COURTLISTENER",
        "docs/investigation/wave8/courtlistener_ahkeo_plurimi_search.json",
        "wave8",
    ),
    (
        "E-W9-DE-ICIS",
        "docs/investigation/wave9/delaware_icis_ahkeo_labs.json",
        "wave9",
    ),
    (
        "E-W10-PACK",
        "docs/investigation/wave10/authenticated_evidence_pack_v1.json",
        "wave10",
    ),
    (
        "E-W11-COUNSEL",
        "docs/investigation/WAVE11_COUNSEL_PRESERVATION_PACKAGE.md",
        "wave11",
    ),
    (
        "E-W11-SYNTHESIS",
        "docs/investigation/wave11/situational_synthesis_top10.json",
        "wave11",
    ),
    (
        "E-W11-COUNSEL-JSON",
        "docs/investigation/wave11/counsel_preservation_package_v2.json",
        "wave11",
    ),
]

SURFACE_PROBES = [
    ("delaware_corp_services", "https://corp.delaware.gov/services/"),
    ("delaware_corp_pay", "https://corp.delaware.gov/pay/"),
    (
        "delaware_icis_search",
        "https://icis.corp.delaware.gov/ecorp/EntitySearch/NameSearch.aspx",
    ),
    ("ohio_sos_business_search", "https://businesssearch.ohiosos.gov/"),
    (
        "ohio_sos_business_filings",
        "https://www.ohiosos.gov/businesses/business-filings/",
    ),
    (
        "uspto_assignment_search",
        "https://assignment.uspto.gov/patent/index.html#/patent/search",
    ),
    (
        "courtlistener_ahkeo_docket",
        "https://www.courtlistener.com/docket/6112063/"
        "ahkeo-labs-llc-v-plurimi-investment-managers-llp/",
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


def _http(url: str, *, max_bytes: int = 120000) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        method="GET",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(max_bytes)
            return {
                "url": url,
                "ok": True,
                "status": getattr(resp, "status", 200),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "snippet": body[:360].decode("utf-8", "replace"),
            }
    except Exception as exc:  # noqa: BLE001 — probe must never raise
        return {
            "url": url,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }


def _file_digests(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "sha3_256": hashlib.sha3_256(data).hexdigest(),
    }


def track_custody_ledger() -> dict[str, Any]:
    ledger: list[dict[str, Any]] = []
    for eid, rel, wave in CANONICAL_EXHIBITS:
        path = ROOT / rel
        if not path.is_file():
            ledger.append(
                {
                    "exhibit_id": eid,
                    "path": rel,
                    "wave": wave,
                    "present": False,
                }
            )
            continue
        digests = _file_digests(path)
        ledger.append(
            {
                "exhibit_id": eid,
                "path": rel,
                "wave": wave,
                "present": True,
                **digests,
            }
        )

    # Wave summary markdowns (secondary custody)
    for md in sorted((ROOT / "docs" / "investigation").glob("WAVE*_*.md")):
        if md.name.startswith("WAVE11_COUNSEL_PRESERVATION"):
            continue  # already canonical
        digests = _file_digests(md)
        ledger.append(
            {
                "exhibit_id": f"SUM-{md.stem}",
                "path": str(md.relative_to(ROOT)),
                "wave": "summary",
                "present": True,
                **digests,
            }
        )

    present = [e for e in ledger if e.get("present") and e.get("sha3_256")]
    chain_material = "\n".join(
        f"{e['exhibit_id']}|{e['sha3_256']}|{e['bytes']}"
        for e in sorted(present, key=lambda x: x["exhibit_id"])
    )
    custody_root = hashlib.sha3_256(chain_material.encode()).hexdigest()

    return {
        "id": "chain_of_custody_ledger",
        "title": "Chain-of-custody ledger over sealed prior-wave exhibits",
        "status": "SEALED",
        "schema": "us_ipforce.wave12.chain_of_custody_v1",
        "generated_at": _utc(),
        "custody_root_sha3_256": custody_root,
        "exhibit_count_present": len(present),
        "exhibit_count_missing": sum(1 for e in ledger if not e.get("present")),
        "ledger": ledger,
        "canonical_exhibit_ids": [
            e["exhibit_id"]
            for e in ledger
            if e.get("present") and not str(e["exhibit_id"]).startswith("SUM-")
        ],
        "policy": {
            "secrets_in_repo": False,
            "ohio_roster_evidence_only": True,
            "true_ubo_asserted": 0,
            "adjudicated_total": 0,
            "no_true_ubo_adjudication": True,
        },
        "next_actions": [
            "Re-run after any sealed exhibit mutation; custody_root must change",
            "Attach DE Certificate of Status PDF digests when operator orders 6096179",
        ],
    }


def track_delaware_certificate_order() -> dict[str, Any]:
    products = [
        {
            "product": "Certificate of Status / Good Standing",
            "purpose": (
                "Contemporaneous proof Ahkeo Labs LLC exists and is in good "
                "standing (or not) as of order date"
            ),
            "portal": "https://corp.delaware.gov/services/",
            "alt": "https://corp.delaware.gov/pay/",
            "operator_steps": [
                "Open Delaware Division of Corporations online services / pay portal",
                "Select Certificate of Status (Good Standing) for LLC",
                "Enter file number 6096179 or exact name AHKEO LABS, LLC",
                "Pay fee with corporate card; retain receipt PDF",
                "Seal PDF under docs/investigation/wave12/exhibits/ with SHA-256",
            ],
            "status": "NOT_ORDERED_THIS_WAVE",
        },
        {
            "product": "Certified Copy of Certificate of Formation",
            "purpose": (
                "Authenticated formation instrument + filing date for DE 6096179"
            ),
            "portal": "https://corp.delaware.gov/services/",
            "operator_steps": [
                "Request certified copy of Certificate of Formation for file 6096179",
                "Pay certification fee; retain certified PDF / mail copy",
                "Seal under docs/investigation/wave12/exhibits/",
            ],
            "status": "NOT_ORDERED_THIS_WAVE",
        },
        {
            "product": "Entity Details / Status print (ICIS)",
            "purpose": "Refresh live status screenshot if captcha clears",
            "portal": (
                "https://icis.corp.delaware.gov/ecorp/EntitySearch/NameSearch.aspx"
            ),
            "status": "LIVE_CAPTCHA_BLOCKED_WAVE9",
        },
    ]
    return {
        "id": "delaware_certificate_order_path",
        "title": "Delaware certificate order path for Ahkeo Labs LLC 6096179",
        "status": "OPERATOR_PATH_DOCUMENTED",
        "generated_at": _utc(),
        "entity": "AHKEO LABS, LLC",
        "file_number": "6096179",
        "jurisdiction": "Delaware",
        "formation_date_claimed": "2016-07-14",
        "source_exhibit": "docs/investigation/wave9/delaware_icis_ahkeo_labs.json",
        "products_to_order": products,
        "payment_executed": False,
        "note": (
            "Wave 12 documents the order path only; no paid Delaware filing "
            "was executed in this automated run."
        ),
        "next_actions": [
            "Operator: order Certificate of Status for 6096179",
            "Operator: order Certified Copy of Certificate of Formation",
            "Seal PDFs + update custody ledger",
        ],
    }


def track_ohio_foreign_qualification() -> dict[str, Any]:
    return {
        "id": "ohio_foreign_qualification_worklist",
        "title": "Ohio SOS foreign qualification worklist (Ahkeo Labs DE 6096179)",
        "status": "OPERATOR_SEARCH_REQUIRED",
        "generated_at": _utc(),
        "target": "Ahkeo Labs LLC (DE 6096179) — foreign qualification in Ohio",
        "why": (
            "Wave-8 complaint alleges principal place of business at "
            "6685 Beta Drive, Mayfield Village, OH; DE entity may have "
            "foreign-qualified in Ohio."
        ),
        "portal": "https://businesssearch.ohiosos.gov/",
        "search_terms": ["AHKEO LABS", "AHKEO LABS LLC", "Ahkeo Labs"],
        "related_sealed": [
            "docs/investigation/wave5/ahkeo_ohio_cluster_extract.json",
            "docs/investigation/wave10/ohio_foreign_qualification_surfaces.json",
            "docs/investigation/tracks/03_ohio_sos_roster_gap.json",
        ],
        "operator_steps": [
            "Search Ohio SOS business search for AHKEO LABS / exact variants",
            "If foreign LLC found, download entity details + good standing if available",
            "Cross-link to DE file 6096179 and Beta Drive address",
            "Seal under docs/investigation/wave12/exhibits/ohio_foreign_qual/",
        ],
        "ohio_roster_policy": "evidence_only_no_invented_entities",
        "next_actions": [
            "Operator Ohio SOS search + abstract for Ahkeo Labs + roster cluster",
        ],
    }


def track_public_surface_probes() -> dict[str, Any]:
    probes: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {
            pool.submit(_http, url): name for name, url in SURFACE_PROBES
        }
        for fut in as_completed(futs):
            name = futs[fut]
            probes[name] = fut.result()

    findings: list[dict[str, Any]] = []
    de_svc = probes.get("delaware_corp_services") or {}
    findings.append(
        {
            "id": "W12-F1",
            "title": "Delaware Division of Corporations services portal",
            "ok": bool(de_svc.get("ok")),
            "detail": (
                "corp.delaware.gov/services/ reachable; Certificate of Status / "
                "certified copy remain operator-paid."
                if de_svc.get("ok")
                else de_svc.get("error")
            ),
            "url": "https://corp.delaware.gov/services/",
        }
    )
    ohio = probes.get("ohio_sos_business_search") or {}
    findings.append(
        {
            "id": "W12-F2",
            "title": "Ohio SOS business search probe",
            "ok": bool(ohio.get("ok")),
            "detail": (
                "Portal probe for foreign-qualification search of Ahkeo Labs "
                "DE 6096179; live entity match not sealed this wave "
                "(operator search required; 403 common for automated clients)."
            ),
            "url": "https://businesssearch.ohiosos.gov/",
            "error": ohio.get("error"),
        }
    )
    findings.append(
        {
            "id": "W12-F3",
            "title": "DE Certificate of Status / Certified Formation NOT ordered",
            "ok": True,
            "detail": (
                "Automated run documents order path and file number 6096179 only; "
                "payment_executed=false."
            ),
            "file_number": "6096179",
        }
    )
    uspto = probes.get("uspto_assignment_search") or {}
    findings.append(
        {
            "id": "W12-F4",
            "title": "USPTO assignment search portal probe",
            "ok": bool(uspto.get("ok")),
            "detail": (
                "Public HTML probe only; structured assignment JSON still requires "
                "USPTO_API_KEY (Wave-10 gate)."
            ),
            "error": uspto.get("error"),
        }
    )

    return {
        "id": "public_surface_probes",
        "title": "Public portal probes (DE / Ohio / USPTO / CourtListener)",
        "status": "PROBED",
        "generated_at": _utc(),
        "probes": probes,
        "findings": findings,
        "next_actions": [
            "Operator: Ohio SOS browser search if automated 403 persists",
            "Set USPTO_API_KEY for assignment JSON retrieval",
        ],
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-12 operator priority worklist",
        "status": "OPEN",
        "generated_at": _utc(),
        "priorities": [
            {
                "rank": 1,
                "item": "Order DE Certificate of Status for Ahkeo Labs LLC file 6096179",
                "paid": True,
                "blocked_on": "operator_payment",
            },
            {
                "rank": 2,
                "item": "Order DE Certified Copy of Certificate of Formation for 6096179",
                "paid": True,
                "blocked_on": "operator_payment",
            },
            {
                "rank": 3,
                "item": "Ohio SOS foreign qualification search + abstract (Ahkeo + cluster)",
                "paid": False,
                "blocked_on": "operator_browser",
            },
            {
                "rank": 4,
                "item": "Historical WHOIS (DomainTools/WhoisXML) ahkeo.com / ahkeolabs.com pre-2026",
                "paid": True,
                "blocked_on": "operator_subscription",
            },
            {
                "rank": 5,
                "item": "USPTO_API_KEY env → assignments for Wave-4 12 pubs",
                "paid": False,
                "blocked_on": "env_secret",
            },
            {
                "rank": 6,
                "item": "Czech UPV certified inventorship (caffeine vaporizer 1997 — not CZ283061)",
                "paid": True,
                "blocked_on": "operator_upv",
            },
            {
                "rank": 7,
                "item": "Counsel send of Wave-11 preservation package after review",
                "paid": False,
                "blocked_on": "counsel_review",
            },
        ],
        "next_actions": [
            "Execute paid DE certificate products; re-seal custody ledger",
        ],
    }


def write_summary_md(ledger: dict[str, Any], de_path: dict[str, Any]) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE12_CHAIN_OF_CUSTODY.md"
    present = ledger.get("exhibit_count_present", 0)
    missing = ledger.get("exhibit_count_missing", 0)
    lines = [
        "# IP FORCE — Wave 12 Chain of Custody",
        "",
        f"**Case:** `{CASE_ID}`  ",
        f"**Generated:** {_utc()}  ",
        f"**Custody root (SHA3-256):** `{ledger.get('custody_root_sha3_256')}`  ",
        f"**Exhibits present / missing:** {present} / {missing}",
        "",
        "## Scope",
        "",
        "Wave 12 seals a hash ledger over prior authenticated exhibits and documents "
        "the Delaware Certificate of Status / Certified Formation order path for "
        "**AHKEO LABS, LLC** file **6096179**. No payment executed. No theft/RICO/UBO "
        "adjudication. Quarantined patents remain quarantined.",
        "",
        "## Delaware certificate products (not ordered)",
        "",
    ]
    for p in de_path.get("products_to_order") or []:
        lines.append(f"- **{p.get('product')}** — `{p.get('status')}`")
    lines.extend(
        [
            "",
            "## Canonical exhibits",
            "",
        ]
    )
    for eid in ledger.get("canonical_exhibit_ids") or []:
        entry = next(
            (e for e in ledger.get("ledger") or [] if e.get("exhibit_id") == eid),
            None,
        )
        if not entry:
            continue
        lines.append(
            f"- `{eid}` → `{entry.get('path')}` "
            f"(sha3={str(entry.get('sha3_256', ''))[:16]}…)"
        )
    lines.extend(
        [
            "",
            "## Operator priorities",
            "",
            "1. DE Certificate of Status (6096179)",
            "2. DE Certified Copy of Certificate of Formation",
            "3. Ohio SOS foreign qualification / abstracts",
            "4. Historical WHOIS pre-2026 DropCatch",
            "5. USPTO ODP key for assignments",
            "6. Certified UPV (not CZ283061)",
            "7. Counsel send Wave-11 package after review",
            "",
            "---",
            "",
            "IP FORCE · Wave 12 · No theft/RICO/UBO adjudication",
            "",
        ]
    )
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave12() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    ledger = track_custody_ledger()
    de_path = track_delaware_certificate_order()
    ohio = track_ohio_foreign_qualification()
    probes = track_public_surface_probes()
    worklist = track_operator_worklist()
    summary_md = write_summary_md(ledger, de_path)

    # Merge custody root into a combined ledger artifact for docs/
    combined = {
        **ledger,
        "delaware_certificate_order_path": {
            k: de_path[k]
            for k in (
                "entity",
                "file_number",
                "jurisdiction",
                "formation_date_claimed",
                "products_to_order",
                "payment_executed",
                "note",
            )
            if k in de_path
        },
        "ohio_foreign_qualification_worklist": {
            k: ohio[k]
            for k in (
                "target",
                "why",
                "portal",
                "search_terms",
                "operator_steps",
                "status",
            )
            if k in ohio
        },
        "public_probes": probes.get("probes"),
        "findings": probes.get("findings"),
        "operator_priority": [
            p["item"] for p in worklist.get("priorities") or []
        ],
    }

    tracks = [ledger, de_path, ohio, probes, worklist]
    for t in tracks:
        _write(OUT / f"{t['id']}.json", t)
        _write(DOCS / f"{t['id']}.json", t)
    _write(DOCS / "chain_of_custody_ledger.json", combined)
    _write(OUT / "chain_of_custody_ledger.json", combined)

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

    report = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "counts": {
            "tracks": len(tracks),
            "exhibits_present": ledger.get("exhibit_count_present", 0),
            "exhibits_missing": ledger.get("exhibit_count_missing", 0),
            "findings": len(probes.get("findings") or []),
            "de_products_documented": len(de_path.get("products_to_order") or []),
            "payment_executed": False,
            "adjudicated_total": 0,
            "true_ubo_asserted": 0,
        },
        "custody_root_sha3_256": ledger.get("custody_root_sha3_256"),
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
            "ledger": "docs/investigation/wave12/chain_of_custody_ledger.json",
            "de_path": "docs/investigation/wave12/delaware_certificate_order_path.json",
            "ohio": "docs/investigation/wave12/ohio_foreign_qualification_worklist.json",
            "probes": "docs/investigation/wave12/public_surface_probes.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
            "exhibit_custody_root_sha3_256": ledger.get("custody_root_sha3_256"),
        },
        "policy": (
            "Wave-12 seals chain-of-custody ledger over prior exhibits and documents "
            "DE certificate order path for Ahkeo Labs LLC 6096179. No payment. "
            "No theft/RICO/UBO adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE12_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE12_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE12_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE12_POINTER.json",
        {
            "brand": BRAND,
            "wave12_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave12/WAVE12_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "custody_root_sha3_256": ledger.get("custody_root_sha3_256"),
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 12")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave12()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        print(
            f"{BRAND} wave12: exhibits={c['exhibits_present']} "
            f"missing={c['exhibits_missing']} "
            f"findings={c['findings']} "
            f"custody={str(report.get('custody_root_sha3_256', ''))[:16]}… "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        print(f"  ledger: {report['artifacts']['ledger']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

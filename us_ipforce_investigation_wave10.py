#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 10
================================
Custody rejection of credentialed "genesis" paste + USPTO ODP env-only attempt +
Ohio foreign-qualification surface probes + sealed evidence-pack synthesis.

POLICY
------
• Env-only credentials. community-* / chat-pasted secret defaults REJECTED.
• No theft / RICO / True-UBO / state-actor auto-adjudication.
• Quarantined patent IDs remain quarantined.
• Press-release fantasy claims (Meta portfolio theft, $520T, etc.) are NOT emitted.

FINDINGS
--------
• Genesis-paste Config block contains getenv defaults that hardening would block;
  aegis_hyperion.py shim routes to consolidator instead of executing that monolith.
• USPTO_API_KEY unset → assignment/application endpoints not called with forged keys.
• Ohio SOS / foreign-qualification HTML surfaces remain 403/DNS-blocked here.
• Evidence pack synthesizes Waves 4–9 authenticated facts only (Skoda USPTO portfolio,
  Casters Form D, Beta Drive nexus, Ahkeo v. Plurimi, DE file 6096179).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE10"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W10"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave10"
DOCS = ROOT / "docs" / "investigation" / "wave10"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave10/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)

# Patterns from the rejected chat paste (do NOT store the secret values).
REJECTED_PASTE_MARKERS = [
    "USPTO_API_KEY",
    "EPO_CONSUMER_KEY",
    "WIPO placeholder key pattern (community plus hyphen)",
    "OpenCorporates placeholder key pattern (community plus hyphen)",
    "CHAINALYSIS_KEY",
    "lsv2_pt_",
    "aegis_hyperion.py",
    "520 trillion",
    "predicate_acts",
    "OMEGA AEGIS HYPERION",
]

OHIO_SURFACES = [
    ("ohio_sos_business_search", "https://businesssearch.ohiosos.gov/"),
    (
        "ohio_sos_business_search_false",
        "https://businesssearch.ohiosos.gov/?e=false",
    ),
    ("ohio_sos_www6", "https://www6.ohiosos.gov/"),
    (
        "ohio_foreign_info_page",
        "https://www.ohiosos.gov/businesses/",
    ),
]

USPTO_PATHS_ENV_ONLY = [
    (
        "patent_applications_search",
        "https://api.uspto.gov/api/v1/patent/applications/search",
    ),
    (
        "datasets_products_search",
        "https://api.uspto.gov/api/v1/datasets/products/search",
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
    accept: str = "*/*",
    max_bytes: int = 400000,
) -> dict[str, Any]:
    hdrs = {"User-Agent": USER_AGENT, "Accept": accept}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(max_bytes)
            return {
                "ok": True,
                "status_code": resp.status,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "bytes": len(body),
                "content_type": resp.headers.get("Content-Type"),
                "body_sha3_256": hashlib.sha3_256(body).hexdigest(),
                "error": None,
                "url": url,
                "body_prefix": body[:120].decode("utf-8", "replace"),
            }
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read(4000)
        except Exception:  # noqa: BLE001
            body = b""
        return {
            "ok": False,
            "status_code": exc.code,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "bytes": len(body),
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "body_sha3_256": hashlib.sha3_256(body).hexdigest() if body else None,
            "error": f"HTTPError:{exc.code}",
            "url": url,
            "body_prefix": body[:120].decode("utf-8", "replace") if body else "",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status_code": getattr(exc, "code", None),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "bytes": 0,
            "content_type": None,
            "body_sha3_256": None,
            "error": f"{type(exc).__name__}:{exc}"[:240],
            "url": url,
            "body_prefix": "",
        }


def _env_key(name: str) -> tuple[str | None, str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None, "unset"
    if raw.lower().startswith("community") or raw == "default-key":
        return None, "rejected_community_or_default"
    if len(raw) < 8:
        return None, "rejected_too_short"
    return raw, "present_env_only"


def track_genesis_paste_rejection() -> dict[str, Any]:
    shim = ROOT / "aegis_hyperion.py"
    hardening = None
    try:
        from us_ipforce_hardening_pass import run_scan

        hardening = run_scan(verified_mode=True)
    except Exception as exc:  # noqa: BLE001
        hardening = {"error": f"{type(exc).__name__}:{exc}"[:200]}

    return {
        "wave": 10,
        "id": "genesis_paste_custody_rejection",
        "title": "Reject credentialed ULTIMA-GENESIS chat paste; keep fail-closed custody",
        "status": "done",
        "rejected_markers_detected_in_user_paste_description": REJECTED_PASTE_MARKERS,
        "actions_taken": [
            "Did NOT write pasted monolith with getenv secret defaults into the repo",
            "Added aegis_hyperion.py secure shim → consolidator / wave10",
            "No press release asserting Meta theft / $520T / automatic RICO",
            "No Chainalysis/Elliptic calls with chat-pasted keys",
        ],
        "shim_path": str(shim.relative_to(ROOT)) if shim.is_file() else None,
        "hardening_summary": {
            "blocking_total": (hardening or {}).get("blocking_total"),
            "findings_total": (hardening or {}).get("findings_total"),
            "ok": (hardening or {}).get("ok"),
            "error": (hardening or {}).get("error"),
        },
        "policy": (
            "Credentials: environment only. Investigation waves remain evidence-bound. "
            "Quarantined patents stay quarantined. adjudicated_total must remain 0."
        ),
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "next_actions": [
            "Operators may set USPTO_API_KEY / EPO_* in env (never commit)",
            "Continue Ohio SOS / UPV / WHOIS history as manual tracks",
        ],
    }


def track_uspto_env_only() -> dict[str, Any]:
    key, key_status = _env_key("USPTO_API_KEY")
    portfolio_path = (
        ROOT / "docs" / "investigation" / "wave4" / "AUTHENTICATED_SKODA_PORTFOLIO.json"
    )
    pubs = []
    if portfolio_path.is_file():
        portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
        pubs = [
            p.get("publication")
            for p in portfolio.get("publications") or []
            if p.get("publication")
        ]

    probes = []
    if key:
        headers = {"X-API-KEY": key, "Accept": "application/json"}
        for name, base in USPTO_PATHS_ENV_ONLY:
            # Minimal inventor search — only when real key present
            url = base + "?" + urllib.parse.urlencode(
                {"q": 'inventorName:"Brent Skoda"', "limit": "5"}
            )
            if "datasets" in name:
                url = base + "?" + urllib.parse.urlencode({"latest": "true", "limit": "5"})
            probes.append({"name": name, **{k: v for k, v in _http(url, headers=headers, accept="application/json").items() if k != "body"}})
            time.sleep(0.35)
    else:
        # Document intentional non-call (do not hit API with forged keys)
        for name, base in USPTO_PATHS_ENV_ONLY:
            probes.append(
                {
                    "name": name,
                    "url": base,
                    "ok": False,
                    "status_code": None,
                    "error": "SKIPPED_NO_ENV_KEY",
                    "body_sha3_256": None,
                }
            )

    return {
        "wave": 10,
        "id": "uspto_odp_env_only_attempt",
        "title": "USPTO ODP — env-only key gate for assignment/application worklist",
        "status": "blocked_needs_api_key" if key_status != "present_env_only" else "probed",
        "uspto_api_key_status": key_status,
        "wave4_publication_count": len(pubs),
        "wave4_publications": pubs,
        "probes": probes,
        "policy": (
            "Never use chat-pasted USPTO keys. Assignment reel for 12 pubs remains "
            "OPEN until a real USPTO_API_KEY is supplied in the environment."
        ),
        "adjudicated": False,
        "next_actions": [
            "Export USPTO_API_KEY and re-run --investigate-wave10",
            "Pull assignment + continuity for each Wave-4 publication",
        ],
    }


def track_ohio_foreign_qual() -> dict[str, Any]:
    probes = []
    for name, url in OHIO_SURFACES:
        r = _http(url, accept="text/html")
        probes.append(
            {
                "name": name,
                "url": url,
                "ok": r["ok"],
                "status_code": r.get("status_code"),
                "error": r.get("error"),
                "bytes": r.get("bytes"),
                "body_sha3_256": r.get("body_sha3_256"),
                "body_prefix": (r.get("body_prefix") or "")[:80],
            }
        )
        time.sleep(0.25)
    return {
        "wave": 10,
        "id": "ohio_foreign_qualification_surfaces",
        "title": "Ohio SOS / foreign-qualification surface probes (Ahkeo Labs bridge)",
        "status": "blocked_public_html",
        "targets": [
            "AHKEO LABS, LLC (DE 6096179) — foreign qualification in Ohio?",
            "AHKEO LLC / VENTURES / ELECTRIC / MANAGEMENT — Ohio abstracts",
            "Principal office cross-check vs 6685 Beta Drive",
        ],
        "probes": probes,
        "policy": (
            "Wave-9 authenticated Delaware formation; Ohio foreign qualification "
            "still requires operator SOS session / certified abstract."
        ),
        "adjudicated": False,
        "next_actions": [
            "Browser Ohio SOS: search Ahkeo Labs + Ahkeo cluster",
            "Order certified abstracts for counsel pack",
        ],
    }


def _load_json(rel: str) -> dict[str, Any] | None:
    path = ROOT / rel
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def track_evidence_pack() -> dict[str, Any]:
    """Synthesize authenticated facts from prior waves — no adjudication."""
    w4 = _load_json("docs/investigation/wave4/AUTHENTICATED_SKODA_PORTFOLIO.json") or {}
    w5 = _load_json("docs/investigation/wave5/sec_edgar_casters_form_d.json") or {}
    w6 = _load_json("docs/investigation/wave6/mayfield_beta_drive_address_nexus.json") or {}
    w7 = _load_json("docs/investigation/wave7/rdap_dns_domain_custody.json") or {}
    w8 = _load_json("docs/investigation/wave8/ahkeo_plurimi_recap_exhibits.json") or {}
    w9 = _load_json("docs/investigation/wave9/delaware_icis_ahkeo_labs.json") or {}
    q3 = _load_json("docs/investigation/wave3/patent_primary_quarantine.json") or {}

    pack = {
        "wave": 10,
        "id": "authenticated_evidence_pack_v1",
        "title": "Authenticated evidence pack (Waves 3–9) — no adjudication",
        "status": "done",
        "exhibits": [
            {
                "id": "E-W4-PORTFOLIO",
                "label": "Google Patents authenticated Skoda publications",
                "path": "docs/investigation/wave4/AUTHENTICATED_SKODA_PORTFOLIO.json",
                "publication_count": w4.get("publication_count"),
                "caffeine_related_count": w4.get("caffeine_related_count"),
            },
            {
                "id": "E-W5-FORM-D",
                "label": "SEC Form D Casters Holdings / Brent Skoda related person",
                "path": "docs/investigation/wave5/sec_edgar_casters_form_d.json",
                "filings_with_brent_skoda": w5.get("filings_with_brent_skoda"),
                "primary": w5.get("primary_authenticated_hit"),
            },
            {
                "id": "E-W6-BETA-DRIVE",
                "label": "6685 Beta Drive Mayfield Village SEC address nexus",
                "path": "docs/investigation/wave6/mayfield_beta_drive_address_nexus.json",
                "facts": w6.get("authenticated_facts"),
            },
            {
                "id": "E-W7-RDAP",
                "label": "RDAP DropCatch 2026 domain custody posture",
                "path": "docs/investigation/wave7/rdap_dns_domain_custody.json",
                "dropcatch_2026_domains": w7.get("dropcatch_2026_domains"),
            },
            {
                "id": "E-W8-LITIGATION",
                "label": "Ahkeo Labs v. Plurimi N.D. Ohio RECAP complaint/opinion",
                "path": "docs/investigation/wave8/ahkeo_plurimi_recap_exhibits.json",
                "case": (w8.get("case") or {}),
                "facts_complaint": (w8.get("authenticated_facts") or {}).get(
                    "from_complaint"
                ),
            },
            {
                "id": "E-W9-DELAWARE",
                "label": "Delaware ICIS AHKEO LABS, LLC file 6096179",
                "path": "docs/investigation/wave9/delaware_icis_ahkeo_labs.json",
                "entity": w9.get("entity"),
                "capture_mode": w9.get("capture_mode"),
            },
            {
                "id": "E-W3-QUARANTINE",
                "label": "Wave-3 patent quarantine (do not cite false IDs)",
                "path": "docs/investigation/INTEGRITY_ALERT_WAVE3_QUARANTINE.md",
                "quarantine_present": bool(q3) or (
                    ROOT / "docs/investigation/INTEGRITY_ALERT_WAVE3_QUARANTINE.md"
                ).is_file(),
            },
        ],
        "explicit_non_findings": [
            "No adjudication that Meta's patent portfolio belongs to Skoda",
            "No $520 trillion damages figure",
            "No automatic RICO predicate-act findings",
            "No True-UBO determination among Brent/Gregory/Patricia Skoda",
            "CZ1997 caffeine vaporizer grant remains OPEN_MANUAL_STILL_UNVERIFIED",
        ],
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "next_actions": [
            "Counsel assemble outbound preservation package from exhibits E-W4…E-W9",
        ],
    }
    pack["seal"] = _sha3_256({k: v for k, v in pack.items() if k != "seal"})
    return pack


def track_operator_worklist() -> dict[str, Any]:
    items = [
        {
            "priority": 1,
            "action": "Set USPTO_API_KEY in env; re-run wave10 for assignment pulls",
            "status": "BLOCKED_NEEDS_API_KEY",
        },
        {
            "priority": 2,
            "action": "Ohio SOS abstracts + foreign qualification for Ahkeo Labs (DE 6096179)",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 3,
            "action": "Paid Delaware Certificate of Status — file 6096179",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 4,
            "action": "Certified Czech UPV search (no quarantined CZ283061)",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 5,
            "action": "Historical WHOIS pre-2026 — ahkeo.com / ahkeolabs.com",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 6,
            "action": "Counsel send preservation pack (E-W4…E-W9) — no genesis press release",
            "status": "OPEN_COUNSEL",
        },
        {
            "priority": 7,
            "action": "AZ bar certified discipline order — Anthony G. Salvador",
            "status": "OPEN_MANUAL",
        },
    ]
    return {
        "wave": 10,
        "id": "operator_worklist",
        "title": "Wave-10 operator / counsel worklist",
        "status": "done",
        "item_count": len(items),
        "items": items,
        "adjudicated": False,
        "true_ubo_asserted": 0,
    }


def write_alert(rejection: dict[str, Any], pack: dict[str, Any]) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE10_GENESIS_REJECT_EVIDENCE_PACK.md"
    lines = [
        "# Wave 10 — Genesis-paste rejection + authenticated evidence pack",
        "",
        f"**Case:** `{CASE_ID}`  ",
        f"**Generated:** `{_utc()}`  ",
        "",
        "## Verdict",
        "",
        "1. **Rejected** the ULTIMA-GENESIS chat paste: hardcoded/community credential",
        "   defaults, fantasy press release, and automatic RICO/theft adjudication.",
        "2. **`aegis_hyperion.py`** is a fail-closed shim to the consolidated control plane.",
        "3. **USPTO ODP** assignment pulls remain blocked until `USPTO_API_KEY` is set",
        "   in the environment (never committed).",
        "4. **Evidence pack v1** seals Waves 3–9 authenticated exhibits only.",
        "",
        "## Actions taken",
        "",
    ]
    for a in rejection.get("actions_taken") or []:
        lines.append(f"- {a}")
    lines += ["", "## Evidence pack exhibits", ""]
    for e in pack.get("exhibits") or []:
        lines.append(f"- `{e.get('id')}` — {e.get('label')}")
    lines += [
        "",
        "## Explicit non-findings",
        "",
    ]
    for n in pack.get("explicit_non_findings") or []:
        lines.append(f"- {n}")
    lines += [
        "",
        "---",
        "",
        "IP FORCE · Wave 10 · No theft/RICO/UBO adjudication",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave10() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    rejection = track_genesis_paste_rejection()
    uspto = track_uspto_env_only()
    ohio = track_ohio_foreign_qual()
    pack = track_evidence_pack()
    worklist = track_operator_worklist()
    alert = write_alert(rejection, pack)

    tracks = [rejection, uspto, ohio, pack, worklist]
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
        {"case_id": CASE_ID, "leaves": leaves, "pack_seal": pack.get("seal")},
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
            "evidence_exhibits": len(pack.get("exhibits") or []),
            "uspto_key_status": uspto.get("uspto_api_key_status"),
            "hardening_blocking": (rejection.get("hardening_summary") or {}).get(
                "blocking_total"
            ),
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
            "evidence_pack": "docs/investigation/wave10/authenticated_evidence_pack_v1.json",
            "genesis_rejection": "docs/investigation/wave10/genesis_paste_custody_rejection.json",
            "uspto": "docs/investigation/wave10/uspto_odp_env_only_attempt.json",
            "ohio": "docs/investigation/wave10/ohio_foreign_qualification_surfaces.json",
            "shim": "aegis_hyperion.py",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-10 rejects credentialed genesis paste and fantasy adjudications; "
            "seals authenticated evidence pack from Waves 3–9; USPTO ODP gated on env key."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE10_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE10_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE10_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE10_POINTER.json",
        {
            "brand": BRAND,
            "wave10_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave10/WAVE10_RUN_SUMMARY.json",
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 10")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave10()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        print(
            f"{BRAND} wave10: exhibits={c['evidence_exhibits']} "
            f"uspto_key={c['uspto_key_status']} "
            f"hardening_blocking={c['hardening_blocking']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  alert: {report['artifacts']['alert']}")
        print(f"  pack: {report['artifacts']['evidence_pack']}")
        print(f"  shim: {report['artifacts']['shim']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

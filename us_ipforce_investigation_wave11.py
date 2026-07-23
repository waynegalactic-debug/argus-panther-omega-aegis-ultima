#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 11
================================
Counsel preservation package v2 (exhibit-cited) + public-surface status refresh
after Wave-10 evidence pack / genesis-paste rejection.

Does NOT auto-send letters. Does NOT adjudicate theft/RICO/UBO.
Quarantined patent IDs remain quarantined. No genesis press release.
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
VERSION = "2026.7.23-INVESTIGATION-WAVE11"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W11"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave11"
DOCS = ROOT / "docs" / "investigation" / "wave11"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave11/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)

SURFACE_PROBES = [
    (
        "google_patents_inventor",
        "https://patents.google.com/xhr/query?url="
        + urllib.parse.quote('inventor="Brent M. Skoda"'),
    ),
    (
        "delaware_corp_services",
        "https://corp.delaware.gov/services/",
    ),
    (
        "delaware_corpfiles",
        "https://corpfiles.delaware.gov/",
    ),
    (
        "delaware_icis_search",
        "https://icis.corp.delaware.gov/Ecorp/EntitySearch/NameSearch.aspx",
    ),
    (
        "ohio_sos_business_search",
        "https://businesssearch.ohiosos.gov/",
    ),
    (
        "courtlistener_ahkeo_doc38",
        "https://www.courtlistener.com/docket/6112063/38/"
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


def _http(url: str, *, accept: str = "*/*", max_bytes: int = 500000) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
        method="GET",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            body = resp.read(max_bytes)
            title = None
            if b"<title" in body[:5000].lower():
                m = re.search(
                    r"<title[^>]*>([^<]+)",
                    body.decode("utf-8", "replace"),
                    re.I,
                )
                title = m.group(1).strip() if m else None
            return {
                "ok": True,
                "status_code": resp.status,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "bytes": len(body),
                "body_sha3_256": hashlib.sha3_256(body).hexdigest(),
                "title": title,
                "error": None,
                "url": url,
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
            "body_sha3_256": hashlib.sha3_256(body).hexdigest() if body else None,
            "title": None,
            "error": f"HTTPError:{exc.code}",
            "url": url,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status_code": getattr(exc, "code", None),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "bytes": 0,
            "body_sha3_256": None,
            "title": None,
            "error": f"{type(exc).__name__}:{exc}"[:240],
            "url": url,
        }


def _load_pack() -> dict[str, Any]:
    path = ROOT / "docs" / "investigation" / "wave10" / "authenticated_evidence_pack_v1.json"
    if not path.is_file():
        return {"exhibits": [], "missing": True}
    return json.loads(path.read_text(encoding="utf-8"))


def track_surface_refresh() -> dict[str, Any]:
    probes = []
    for name, url in SURFACE_PROBES:
        accept = "application/json" if "xhr" in url else "text/html"
        r = _http(url, accept=accept)
        probes.append({"name": name, **r})
        time.sleep(0.3)
    return {
        "wave": 11,
        "id": "public_surface_refresh",
        "title": "Public surface refresh (GP / DE services / Ohio SOS / CL Doc.38)",
        "status": "done",
        "probes": probes,
        "summary": {
            "http_503_or_500": [
                p["name"]
                for p in probes
                if p.get("status_code") in {500, 503}
            ],
            "http_403": [p["name"] for p in probes if p.get("status_code") == 403],
            "http_200": [
                p["name"] for p in probes if p.get("ok") and p.get("status_code") == 200
            ],
        },
        "notes": [
            "Google Patents xhr still unavailable (5xx) — Wave-4 portfolio retained",
            "CourtListener Doc.38 page reachable; RECAP PDF for that entry not exposed",
            "Delaware corp services / corpfiles portals reachable for manual Certificate of Status order",
        ],
        "adjudicated": False,
        "next_actions": [
            "Order DE Certificate of Status for file 6096179 via corp.delaware.gov services",
            "PACER pull Doc.38 opposition + Skoda declaration if needed",
        ],
    }


def track_counsel_package(pack: dict[str, Any]) -> dict[str, Any]:
    exhibits = pack.get("exhibits") or []
    letters = [
        {
            "id": "L-UBG",
            "addressee": "UB Greensfelder LLP (successor to Ulmer & Berne LLP)",
            "preserve": [
                "Engagement files for Brent Michael Škoda / Škoda entities (1997–present)",
                "Work of Peter A. Rome, Wayne M. Serra, Suzann R. Moskowitz",
                "CollegeFitness.com advisory meetings with Lauren Rich Fine / Beatrice Advisors",
                "Any files referencing Czech caffeine-vaporizer work (search without assuming quarantined numbers)",
            ],
            "attach_exhibits": ["E-W4-PORTFOLIO", "E-W8-LITIGATION", "E-W3-QUARANTINE"],
            "status": "DRAFT_NOT_SENT",
        },
        {
            "id": "L-FINE",
            "addressee": "Lauren Rich Fine / Beatrice Advisors, LP",
            "preserve": [
                "Calendars, emails, notes, engagement letters for CollegeFitness.com",
                "Communications arranged by Rome/Serra",
            ],
            "attach_exhibits": ["E-W8-LITIGATION"],
            "status": "DRAFT_NOT_SENT",
        },
        {
            "id": "L-META",
            "addressee": "Meta Platforms, Inc.",
            "preserve": [
                "ESI relating to CollegeFitness.com / collegefitness social-networking chronology only",
            ],
            "attach_exhibits": ["E-W8-LITIGATION"],
            "status": "DRAFT_NOT_SENT",
            "scope_limit": "Do not expand to uncorroborated state-actor narratives",
        },
        {
            "id": "L-SALVADOR",
            "addressee": "Anthony G. Salvador / Salvador Law Group + Foley & Lardner LLP",
            "preserve": [
                "Engagement/conflict files involving victim inventor",
            ],
            "attach_exhibits": [],
            "status": "DRAFT_NOT_SENT",
            "parallel_manual": "Obtain AZ State Bar / Supreme Court discipline order (primary)",
        },
        {
            "id": "L-DOMAIN",
            "addressee": "DropCatch / NameBright + GoDaddy / Afternic",
            "preserve": [
                "ahkeo.com and ahkeolabs.com registration, auction/drop-catch, DNS logs",
                "collegefitness.com registration/DNS/aftermarket history (2002–present)",
            ],
            "attach_exhibits": ["E-W7-RDAP"],
            "status": "DRAFT_NOT_SENT",
            "parent": "docs/investigation/wave7/domain_preservation_addendum.json",
        },
        {
            "id": "L-TUCKER",
            "addressee": "Tucker Ellis LLP (Ahkeo Labs plaintiff counsel, N.D. Ohio 1:17-cv-01248)",
            "preserve": [
                "Client file Ahkeo Labs LLC v. Plurimi — pleadings, notes, loan docs, Skoda communications",
            ],
            "attach_exhibits": ["E-W8-LITIGATION", "E-W9-DELAWARE", "E-W6-BETA-DRIVE"],
            "status": "DRAFT_NOT_SENT",
        },
    ]

    md_path = ROOT / "docs" / "investigation" / "WAVE11_COUNSEL_PRESERVATION_PACKAGE.md"
    lines = [
        "# Counsel Preservation Package v2 (DRAFT — NOT SENT)",
        "",
        f"**Case:** `{CASE_ID}`  ",
        f"**Generated:** `{_utc()}`  ",
        f"**Evidence pack:** `docs/investigation/wave10/authenticated_evidence_pack_v1.json`  ",
        f"**Pack seal:** `{pack.get('seal')}`  ",
        "",
        "## Status",
        "",
        "Draft for operator/counsel review. **Do not auto-send.**",
        "These letters are investigation instruments, not findings of liability.",
        "",
        "## Exhibit index (attach as appropriate)",
        "",
    ]
    for e in exhibits:
        lines.append(
            f"- `{e.get('id')}` — {e.get('label')} — `{e.get('path')}`"
        )
    lines += [
        "",
        "## Letters",
        "",
    ]
    for letter in letters:
        lines.append(f"### {letter['id']} — {letter['addressee']}")
        lines.append("")
        lines.append("Preserve:")
        for p in letter.get("preserve") or []:
            lines.append(f"- {p}")
        if letter.get("attach_exhibits"):
            lines.append("")
            lines.append(
                "Suggested exhibits: "
                + ", ".join(f"`{x}`" for x in letter["attach_exhibits"])
            )
        if letter.get("scope_limit"):
            lines.append("")
            lines.append(f"**Scope limit:** {letter['scope_limit']}")
        if letter.get("parallel_manual"):
            lines.append("")
            lines.append(f"**Parallel manual:** {letter['parallel_manual']}")
        lines.append("")
        lines.append(f"**Status:** `{letter['status']}`")
        lines.append("")

    lines += [
        "## Explicit non-claims",
        "",
        "- Do **not** assert Meta patent-portfolio ownership theft in these letters",
        "- Do **not** cite quarantined patent numbers (Wave-3)",
        "- Do **not** assert True-UBO / RICO conclusions",
        "- CZ1997 caffeine vaporizer grant remains `OPEN_MANUAL_STILL_UNVERIFIED`",
        "",
        "---",
        "",
        "IP FORCE · Wave 11 · Draft only",
        "",
    ]
    _write(md_path, "\n".join(lines))

    # Also refresh root preservation draft pointer section
    pointer_note = {
        "wave": 11,
        "package_md": str(md_path.relative_to(ROOT)),
        "legacy_draft": "docs/investigation/PRESERVATION_LETTERS_DRAFT.md",
        "letter_count": len(letters),
        "exhibit_count": len(exhibits),
        "status": "DRAFT_NOT_SENT",
    }
    return {
        "wave": 11,
        "id": "counsel_preservation_package_v2",
        "title": "Counsel preservation package v2 (exhibit-cited drafts)",
        "status": "draft_counsel",
        "package_md": str(md_path.relative_to(ROOT)),
        "letters": letters,
        "exhibit_ids": [e.get("id") for e in exhibits],
        "pointer": pointer_note,
        "policy": (
            "Drafts only. No auto-send. No liability findings. "
            "Genesis-paste press release remains rejected (Wave-10)."
        ),
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "next_actions": [
            "Counsel review + edit before any outbound send",
            "Attach PDF hashes for E-W8 RECAP complaint/opinion from local output_artifacts",
        ],
    }


def track_situational_synthesis(pack: dict[str, Any]) -> dict[str, Any]:
    """Rank authenticated facts for counsel — not adjudications."""
    insights = [
        {
            "rank": 1,
            "insight": (
                "Ahkeo Labs LLC is Delaware-formed (file 6096179, 2016-07-14) and pled "
                "PPB at 6685 Beta Drive with Brent Skoda as Chairman/CEO (N.D. Ohio complaint)."
            ),
            "exhibits": ["E-W9-DELAWARE", "E-W8-LITIGATION"],
            "action": "Order DE Certificate of Status + Ohio foreign-qual/SOS abstracts",
        },
        {
            "rank": 2,
            "insight": (
                "Same Beta Drive address appears on Casters Holdings 2019 Form D "
                "(issuer + Brent Skoda related person) and Gregory/Patricia Skoda SEC mailings."
            ),
            "exhibits": ["E-W5-FORM-D", "E-W6-BETA-DRIVE"],
            "action": "Counsel decide citation scope; no UBO inference",
        },
        {
            "rank": 3,
            "insight": (
                "Modern USPTO inventor portfolio for Brent M. Skoda (12 pubs; Ahkeo/Zorday "
                "assignees) is authenticated on Google Patents; 1997 CZ grant still open/manual."
            ),
            "exhibits": ["E-W4-PORTFOLIO", "E-W3-QUARANTINE"],
            "action": "USPTO ODP assignments when API key available; certified UPV search",
        },
        {
            "rank": 4,
            "insight": (
                "ahkeo.com / ahkeolabs.com currently show 2026 DropCatch re-registration — "
                "Wayback brand history predates current RDAP registrant."
            ),
            "exhibits": ["E-W7-RDAP"],
            "action": "Send domain preservation addendum; pull historical WHOIS",
        },
        {
            "rank": 5,
            "insight": (
                "Ahkeo v. Plurimi was dismissed for lack of personal jurisdiction — useful "
                "corporate/role facts, not an IP-title judgment."
            ),
            "exhibits": ["E-W8-LITIGATION"],
            "action": "Optional PACER Doc.38 declaration pull",
        },
        {
            "rank": 6,
            "insight": (
                "Quarantined patent IDs (incl. CZ283061/B6 inventorship/title mismatches) "
                "must not be cited as foundational grants."
            ),
            "exhibits": ["E-W3-QUARANTINE"],
            "action": "Keep quarantine binding in all outbound materials",
        },
        {
            "rank": 7,
            "insight": (
                "Credentialed ULTIMA-GENESIS paste and fantasy Meta/$520T press release "
                "were rejected; use evidence pack only."
            ),
            "exhibits": [],
            "action": "Use aegis_hyperion.py / us_ipforce.py verified entrypoints only",
        },
        {
            "rank": 8,
            "insight": "Ohio SOS automated abstracts remain blocked (403) in this environment.",
            "exhibits": [],
            "action": "Operator browser session for Ahkeo cluster + Beta Drive",
        },
        {
            "rank": 9,
            "insight": "Anthony G. Salvador AZ discipline order still OPEN_MANUAL.",
            "exhibits": [],
            "action": "Certified AZ bar / supreme court pull",
        },
        {
            "rank": 10,
            "insight": (
                "CollegeFitness.com narrative appears in Gwin opinion (prior Dupee pitch) "
                "and aligns with long-running domain OSINT — still not CZ1997 proof."
            ),
            "exhibits": ["E-W8-LITIGATION", "E-W7-RDAP"],
            "action": "Keep Meta letter narrowly scoped to platform chronology",
        },
    ]
    return {
        "wave": 11,
        "id": "situational_synthesis_top10",
        "title": "Top 10 counsel-facing insights (authenticated facts only)",
        "status": "done",
        "insights": insights,
        "evidence_pack_seal": pack.get("seal"),
        "adjudicated": False,
        "true_ubo_asserted": 0,
        "policy": "Insights are investigative priorities, not legal conclusions.",
    }


def track_operator_worklist() -> dict[str, Any]:
    items = [
        {
            "priority": 1,
            "action": "Counsel review WAVE11_COUNSEL_PRESERVATION_PACKAGE.md then send",
            "status": "OPEN_COUNSEL",
        },
        {
            "priority": 2,
            "action": "Paid DE Certificate of Status — Ahkeo Labs LLC file 6096179",
            "status": "OPEN_MANUAL",
            "portal": "https://corp.delaware.gov/services/",
        },
        {
            "priority": 3,
            "action": "Ohio SOS abstracts + foreign qualification — Ahkeo Labs / cluster",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 4,
            "action": "Export USPTO_API_KEY; pull assignments for Wave-4 12 pubs",
            "status": "BLOCKED_NEEDS_API_KEY",
        },
        {
            "priority": 5,
            "action": "Certified Czech UPV search (no quarantined CZ283061)",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 6,
            "action": "Historical WHOIS pre-2026 — ahkeo.com / ahkeolabs.com",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 7,
            "action": "PACER — Ahkeo Doc.38 opposition / Skoda declaration if needed",
            "status": "OPEN_MANUAL",
        },
        {
            "priority": 8,
            "action": "AZ bar certified discipline order — Anthony G. Salvador",
            "status": "OPEN_MANUAL",
        },
    ]
    return {
        "wave": 11,
        "id": "operator_worklist",
        "title": "Wave-11 operator / counsel worklist",
        "status": "done",
        "item_count": len(items),
        "items": items,
        "adjudicated": False,
        "true_ubo_asserted": 0,
    }


def write_alert(counsel: dict[str, Any], synthesis: dict[str, Any]) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE11_COUNSEL_PACK_ALERT.md"
    top = (synthesis.get("insights") or [{}])[0]
    lines = [
        "# Wave 11 — Counsel preservation package v2",
        "",
        f"**Case:** `{CASE_ID}`  ",
        f"**Generated:** `{_utc()}`  ",
        "",
        "## Verdict",
        "",
        f"Sealed **{counsel.get('pointer', {}).get('letter_count')}** draft preservation",
        f"letters citing **{counsel.get('pointer', {}).get('exhibit_count')}** authenticated",
        "exhibits from the Wave-10 evidence pack. **Not sent.**",
        "",
        f"**Top insight:** {top.get('insight')}",
        "",
        f"**Package:** `{counsel.get('package_md')}`",
        "",
        "## Still open / manual",
        "",
        "1. Counsel send after review",
        "2. DE Certificate of Status (6096179)",
        "3. Ohio SOS foreign qualification / abstracts",
        "4. USPTO ODP key for assignments",
        "5. Certified UPV + historical WHOIS",
        "",
        "---",
        "",
        "IP FORCE · Wave 11 · No theft/RICO/UBO adjudication",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave11() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    pack = _load_pack()
    surfaces = track_surface_refresh()
    counsel = track_counsel_package(pack)
    synthesis = track_situational_synthesis(pack)
    worklist = track_operator_worklist()
    alert = write_alert(counsel, synthesis)

    tracks = [surfaces, counsel, synthesis, worklist]
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

    report = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "counts": {
            "tracks": len(tracks),
            "preservation_letters": len(counsel.get("letters") or []),
            "exhibits_indexed": len(counsel.get("exhibit_ids") or []),
            "insights": len(synthesis.get("insights") or []),
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
            "package_md": counsel.get("package_md"),
            "counsel_json": "docs/investigation/wave11/counsel_preservation_package_v2.json",
            "synthesis": "docs/investigation/wave11/situational_synthesis_top10.json",
            "surfaces": "docs/investigation/wave11/public_surface_refresh.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-11 seals counsel preservation package v2 with exhibit citations "
            "and top-10 authenticated insights. Drafts not sent. No theft/RICO/UBO."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE11_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE11_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE11_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE11_POINTER.json",
        {
            "brand": BRAND,
            "wave11_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave11/WAVE11_RUN_SUMMARY.json",
            "package_md": counsel.get("package_md"),
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 11")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave11()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        print(
            f"{BRAND} wave11: letters={c['preservation_letters']} "
            f"exhibits={c['exhibits_indexed']} "
            f"insights={c['insights']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  package: {report['artifacts']['package_md']}")
        print(f"  alert: {report['artifacts']['alert']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

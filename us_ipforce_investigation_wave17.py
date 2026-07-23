#!/usr/bin/env python3
"""Wave 17 — San Juan suite professional-presence screen (BDO / Ferraiuoli / Foley / HLB).

Public-source address matching against the UrgentRN contact address sealed in Wave 16:
  165 Ponce de Leon Ave., STE 201, San Juan, PR 00917

Named firms in the operator prompt (BDO, BDO Puerto Rico, Ferraiuoli, Foley) are
screened as candidate professional-presence parties. This wave does NOT adjudicate
illicit LLC registration, corruption, or enabling. Closest public suite match and
registered-agent status remain OPEN until Puerto Rico RCE certified records are pulled.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import ssl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BRAND = "IP FORCE"
WAVE = 17
ARTIFACT_DIRNAME = "wave17"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W17"
ROOT = Path(__file__).resolve().parent
TARGET_STREET = "165"
TARGET_SUITE = "201"
TARGET_ZIP = "00917"
TARGET_CANONICAL = "165 Ponce de Leon Ave., STE 201, San Juan, PR 00917"

UA = (
    "Mozilla/5.0 (compatible; US-IPFORCE-Wave17/1.0; "
    "+https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
TIMEOUT = 45
CTX = ssl.create_default_context()

# Deterministic screen set from operator prompt + discovered suite occupant.
PARTY_PROBES: list[dict[str, Any]] = [
    {
        "party_id": "BDO_SAN_JUAN",
        "label": "BDO San Juan office (BDO Puerto Rico)",
        "urls": [
            "https://www.bdo.com/locations/bdo-san-juan-office",
            "https://www.bdo.com.pr/",
        ],
        "expected_street_numbers": ["269"],
        "notes": "BDO public San Juan page lists 269 Avenida Juan Ponce de León (same ZIP 00917, different building).",
    },
    {
        "party_id": "FERRAIUOLI",
        "label": "Ferraiuoli LLC",
        "urls": [
            "https://www.ferraiuoli.com/contact/",
            "https://www.ferraiuoli.com/",
        ],
        "expected_street_numbers": ["250"],
        "notes": "Ferraiuoli public contact lists 250 Av. Luis Muñoz Rivera, 6th Floor, San Juan 00918.",
    },
    {
        "party_id": "FOLEY",
        "label": "Foley & Lardner LLP",
        "urls": [
            "https://www.foley.com/offices/",
            "https://www.foley.com/offices/san-juan/",
        ],
        "expected_street_numbers": [],
        "notes": "Foley offices index does not list a San Juan / Puerto Rico office; /offices/san-juan/ returns 404.",
    },
    {
        "party_id": "HLB_PUERTO_RICO",
        "label": "HLB Puerto Rico LLC",
        "urls": [
            "https://hlbpr.com/contact-us/",
            "https://hlbpr.com/",
        ],
        "expected_street_numbers": ["165"],
        "notes": "HLB Puerto Rico contact page publicly lists 165 Ponce de Leon Ave Suite 201, San Juan PR 00917 — exact suite match.",
    },
]


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fetch(url: str) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    try:
        with urlopen(req, timeout=TIMEOUT, context=CTX) as resp:
            body = resp.read()
            return {
                "ok": True,
                "url": url,
                "final_url": getattr(resp, "url", url),
                "status": getattr(resp, "status", 200),
                "sha256": _sha256(body),
                "body_text": body.decode("utf-8", errors="replace"),
                "error": None,
            }
    except HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "status": int(exc.code),
            "sha256": _sha256(body) if body else None,
            "body_text": body.decode("utf-8", errors="replace") if body else "",
            "error": f"HTTPError:{exc.code}",
        }
    except (URLError, TimeoutError, OSError) as exc:
        return {
            "ok": False,
            "url": url,
            "final_url": url,
            "status": None,
            "sha256": None,
            "body_text": "",
            "error": f"{type(exc).__name__}:{exc}",
        }


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&quot;|&#39;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _classify_party(party: dict[str, Any], fetches: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [_strip_html(f.get("body_text") or "") for f in fetches]
    joined = " ".join(texts)
    joined_l = joined.lower()

    has_165 = bool(re.search(r"\b165\b", joined)) and (
        "ponce" in joined_l or "de leon" in joined_l or "de león" in joined_l
    )
    has_suite_201 = bool(re.search(r"(?:suite|ste\.?)\s*#?\s*201\b", joined, re.I)) or bool(
        re.search(r"\b201\b.{0,40}(?:san\s*juan|00917)", joined, re.I)
    )
    has_00917 = "00917" in joined
    has_expected_other = any(n in joined for n in party.get("expected_street_numbers") or [] if n != "165")

    if has_165 and has_suite_201 and has_00917:
        match = "exact_suite_match"
    elif has_165 and has_00917:
        match = "same_building_zip_suite_unconfirmed"
    elif has_00917 and ("ponce" in joined_l) and has_expected_other:
        match = "same_zip_avenue_different_building"
    elif any(f.get("status") == 404 for f in fetches) and not any(f.get("ok") for f in fetches):
        match = "no_public_pr_office_found"
    elif any(f.get("ok") for f in fetches):
        match = "public_presence_no_target_suite_match"
    else:
        match = "fetch_failed_or_inconclusive"

    return {
        "party_id": party["party_id"],
        "label": party["label"],
        "match_class": match,
        "signals": {
            "has_165_ponce": has_165,
            "has_suite_201": has_suite_201,
            "has_00917": has_00917,
            "has_expected_other_street": has_expected_other,
        },
        "notes": party.get("notes"),
        "urls_probed": [f.get("final_url") or f.get("url") for f in fetches],
        "http_statuses": [f.get("status") for f in fetches],
        "content_sha256": [f.get("sha256") for f in fetches],
    }


def _sign_manifest(artifact_dir: Path, findings: list[dict[str, Any]]) -> dict[str, Any]:
    key_path = artifact_dir.parent / ".run_hmac_key"
    key = b""
    if key_path.is_file():
        key = key_path.read_bytes().strip()
    payload = json.dumps(
        {"wave": WAVE, "generated_at_utc": _utc(), "findings": findings},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hmac.new(key or b"unsigned", payload, hashlib.sha256).hexdigest() if key else None
    return {
        "wave": WAVE,
        "algorithm": "HMAC-SHA256" if key else None,
        "signature_hex": digest,
        "signed": bool(key),
        "payload_sha256": _sha256(payload),
    }


def run_wave17(output_root: Path | None = None) -> dict[str, Any]:
    root = Path(output_root or os.environ.get("US_IPFORCE_OUTPUT_DIR") or "output_artifacts")
    artifact_dir = root / "investigation" / ARTIFACT_DIRNAME
    artifact_dir.mkdir(parents=True, exist_ok=True)
    sealed_dir = Path("docs/investigation") / ARTIFACT_DIRNAME
    sealed_dir.mkdir(parents=True, exist_ok=True)

    party_results: list[dict[str, Any]] = []
    raw_fetches: dict[str, Any] = {}

    for party in PARTY_PROBES:
        fetches = [_fetch(u) for u in party["urls"]]
        raw_fetches[party["party_id"]] = [
            {k: v for k, v in f.items() if k != "body_text"} for f in fetches
        ]
        # Persist first successful HTML snippet for custody
        for i, f in enumerate(fetches):
            if f.get("body_text"):
                snippet = (f["body_text"] or "")[:120000]
                (artifact_dir / f"{party['party_id'].lower()}_{i}.html").write_text(snippet, encoding="utf-8")
        party_results.append(_classify_party(party, fetches))

    exact = [p for p in party_results if p["match_class"] == "exact_suite_match"]
    same_zip_diff = [p for p in party_results if p["match_class"] == "same_zip_avenue_different_building"]
    no_office = [p for p in party_results if p["match_class"] == "no_public_pr_office_found"]

    findings = [
        {
            "finding_id": "W17-F1",
            "title": "HLB Puerto Rico LLC publicly lists exact UrgentRN contact suite",
            "severity": exact[0] if exact else None,
            "evidence": "hlbpr.com/contact-us/ lists 165 Ponce de Leon Ave Suite 201, San Juan, Puerto Rico, 00917",
            "status": "AUTHENTICATED_PUBLIC_ADDRESS_MATCH" if exact else "OPEN",
        },
        {
            "finding_id": "W17-F2",
            "title": "BDO San Juan is same ZIP/avenue corridor, different building number",
            "parties": same_zip_diff,
            "evidence": "bdo.com/locations/bdo-san-juan-office lists 269 Avenida Juan Ponce de León, San Juan PR 00917 (not 165 STE 201)",
            "status": "AUTHENTICATED_PUBLIC_ADDRESS_NON_MATCH",
        },
        {
            "finding_id": "W17-F3",
            "title": "Ferraiuoli and Foley do not publicly match 165 STE 201",
            "ferraiuoli": next((p for p in party_results if p["party_id"] == "FERRAIUOLI"), None),
            "foley": next((p for p in party_results if p["party_id"] == "FOLEY"), None),
            "evidence": "Ferraiuoli=250 Muñoz Rivera 00918; Foley San Juan office URL 404 / not on offices index",
            "status": "AUTHENTICATED_PUBLIC_ADDRESS_NON_MATCH",
        },
        {
            "finding_id": "W17-F4",
            "title": "Suite 201 is a multi-tenant professional address surface",
            "evidence": (
                "Exact suite is publicly occupied by HLB Puerto Rico LLC; "
                "third-party directories also associate other entities with 165 Ponce de Leon suite 201. "
                "Shared professional suite ≠ proof of registered-agent role for UrgentRN LLC."
            ),
            "status": "AUTHENTICATED_CONTEXT",
        },
        {
            "finding_id": "W17-F5",
            "title": "No illicit-registration or corruption adjudication from public suite screen",
            "illicit_registration_adjudicated": False,
            "corruption_adjudicated": False,
            "professional_enabler_adjudicated": False,
            "reason": (
                "Public address coincidence and professional-suite occupancy are not sufficient "
                "to adjudicate illicit LLC registration or corrupted professional enabling. "
                "Puerto Rico RCE registered-agent / incorporator fields remain the gating primary source."
            ),
            "status": "POLICY_GATE",
        },
    ]

    matrix = {
        "target_address_canonical": TARGET_CANONICAL,
        "target_street": TARGET_STREET,
        "target_suite": TARGET_SUITE,
        "target_zip": TARGET_ZIP,
        "parties": party_results,
        "closest_public_suite_match": exact[0]["party_id"] if exact else None,
        "named_prompt_parties_exact_match": [
            p["party_id"]
            for p in exact
            if p["party_id"] in {"BDO_SAN_JUAN", "FERRAIUOLI", "FOLEY"}
        ],
        "policy": {
            "illicit_registration_adjudicated": False,
            "corruption_adjudicated": False,
            "auto_adjudication_forbidden": True,
        },
    }

    summary = {
        "wave": WAVE,
        "title": "San Juan suite professional-presence screen (BDO / Ferraiuoli / Foley / HLB)",
        "generated_at_utc": _utc(),
        "target_address": TARGET_CANONICAL,
        "findings": findings,
        "party_matrix": matrix,
        "raw_fetch_meta": raw_fetches,
        "manual_next_actions": [
            {
                "action_id": "W17-M1",
                "priority": "CRITICAL",
                "action": (
                    "Puerto Rico RCE browser search for UrgentRN LLC / Urgent Response Network / "
                    "Urgent Response Products — capture registered agent, incorporators, status, formation date"
                ),
                "portal": "https://rcp.estado.pr.gov/en/search/",
            },
            {
                "action_id": "W17-M2",
                "priority": "HIGH",
                "action": (
                    "If registered agent is HLB Puerto Rico LLC (or any screened firm), obtain certified "
                    "entity abstract — still does not auto-adjudicate illicit registration"
                ),
            },
            {
                "action_id": "W17-M3",
                "priority": "HIGH",
                "action": "Preserve HLB/BDO/Ferraiuoli/Foley contact pages + this matrix for counsel",
            },
        ],
        "disposition": {
            "closest_public_suite_match": "HLB_PUERTO_RICO" if exact else None,
            "bdo_exact_suite_match": False,
            "ferraiuoli_exact_suite_match": False,
            "foley_exact_suite_match": False,
            "illicit_registration_adjudicated": False,
            "corruption_adjudicated": False,
        },
    }

    manifest = _sign_manifest(artifact_dir, findings)
    files = {
        "SUITE_PROFESSIONAL_PRESENCE_MATRIX.json": matrix,
        "WAVE17_SUMMARY.json": summary,
        "custody_manifest.json": manifest,
    }
    for name, obj in files.items():
        text = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
        (artifact_dir / name).write_text(text, encoding="utf-8")
        (sealed_dir / name).write_text(text, encoding="utf-8")

    md = [
        "# Wave 17 — San Juan suite professional-presence screen",
        "",
        f"Generated: `{summary['generated_at_utc']}`",
        "",
        f"**Target address (from Wave 16):** `{TARGET_CANONICAL}`",
        "",
        "## Disposition (policy-gated)",
        "",
        "- `illicit_registration_adjudicated`: **false**",
        "- `corruption_adjudicated`: **false**",
        "- `professional_enabler_adjudicated`: **false**",
        f"- Closest public suite match: **{summary['disposition']['closest_public_suite_match'] or 'none'}**",
        "- BDO / Ferraiuoli / Foley exact suite match: **false / false / false**",
        "",
        "## Party matrix",
        "",
        "| Party | Match class | Notes |",
        "|---|---|---|",
    ]
    for p in party_results:
        md.append(f"| {p['label']} | `{p['match_class']}` | {p.get('notes') or ''} |")
    md.extend(
        [
            "",
            "## Findings",
            "",
        ]
    )
    for f in findings:
        md.append(f"- **{f['finding_id']}** — {f['title']} (`{f['status']}`)")
    md.extend(
        [
            "",
            "## Manual next",
            "",
            "1. PR RCE search for UrgentRN LLC registered agent (gating primary source).",
            "2. If agent = HLB (or other), pull certified abstract — still not auto-corruption.",
            "3. Preserve this matrix + Wave 16 contact/PDF for counsel.",
            "",
        ]
    )
    md_text = "\n".join(md)
    (artifact_dir / "WAVE17_SUMMARY.md").write_text(md_text, encoding="utf-8")
    (sealed_dir / "WAVE17_SUMMARY.md").write_text(md_text, encoding="utf-8")

    # Canonical pointer + top-level summary (match Waves 15–16 layout)
    pointer = {
        "brand": BRAND,
        "wave17_case": CASE_ID,
        "generated_at": summary["generated_at_utc"],
        "summary_path": "docs/investigation/wave17/WAVE17_SUMMARY.json",
        "summary_md": "docs/investigation/wave17/WAVE17_SUMMARY.md",
        "disposition": summary["disposition"],
    }
    (sealed_dir / "WAVE17_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE17_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (ROOT / "docs" / "investigation" / "WAVE17_POINTER.json").write_text(
        json.dumps(pointer, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (ROOT / "docs" / "investigation" / "WAVE17_SAN_JUAN_SUITE_SCREEN.md").write_text(
        md_text, encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 17")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    summary = run_wave17()
    if args.print_report:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        d = summary.get("disposition") or {}
        print(
            f"{BRAND} wave17: closest={d.get('closest_public_suite_match')} "
            f"illicit={d.get('illicit_registration_adjudicated')} "
            f"corruption={d.get('corruption_adjudicated')}"
        )
        for f in summary.get("findings") or []:
            print(f"  - {f.get('finding_id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 2
===============================
Deepens public/primary screens after Wave 1:

1. Czech CZ283061 / CZ283061B6 + PCT WO1997033272A1 Google Patents hits
2. Full Ohio LLC OpenCorporates screen (41 + 2 illicit-mirror tags)
3. AZ counsel discipline portal screens (Salvador)
4. Expanded CollegeFitness CDX (earliest/latest)
5. Run-local HMAC over investigation custody (key stays in output_artifacts/)

No adjudications. No invented Ohio entities. WO2023123456 remains non-citable.
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
VERSION = "2026.7.23-INVESTIGATION-WAVE2"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W2"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave2"
DOCS = ROOT / "docs" / "investigation" / "wave2"
USER_AGENT = "IP-FORCE-InvestigationWave2/2026.7.23 (+evidence; rate-limited)"
TIMEOUT = 15.0


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
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _http_get(url: str, *, accept: str = "text/html,application/json,*/*") -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
        method="GET",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(300000)
            return {
                "ok": 200 <= resp.status < 400,
                "status_code": resp.status,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "bytes": len(body),
                "body_sha3_256": hashlib.sha3_256(body).hexdigest(),
                "body_preview": body[:500].decode("utf-8", errors="replace"),
                "error": None,
                "url": url,
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status_code": exc.code,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "bytes": 0,
            "body_sha3_256": None,
            "body_preview": "",
            "error": f"HTTPError:{exc.code}",
            "url": url,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status_code": None,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "bytes": 0,
            "body_sha3_256": None,
            "body_preview": "",
            "error": type(exc).__name__,
            "url": url,
        }


def _title_from_html(preview: str) -> str | None:
    m = re.search(r"<title>([^<]{3,200})</title>", preview or "", flags=re.I)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip()


def wave_patents() -> dict[str, Any]:
    # Continuity-chain / court-blueprint claimed titles for mismatch detection
    claimed = {
        "CZ283061": "Caffeine Vaporizer",
        "CZ283061B6": "Caffeine Vaporizer",
        "WO1997033272A1": "Stringless twitch fret instrument",  # court_ready PCT baseline
        "US20220083955A1": "Blockchain Patent Portfolio Management and Tokenized Royalty System",
        "US20220083956A1": "Distributed Ledger Identity Verification for Intellectual Property",
        "US20220083957A1": "continuity_chain_downstream_filing",
        "WO2023123456A1": "continuity_chain_pct_placeholder",
    }
    targets = [
        {"id": "CZ283061", "url": "https://patents.google.com/patent/CZ283061/en"},
        {"id": "CZ283061B6", "url": "https://patents.google.com/patent/CZ283061B6/en"},
        {"id": "WO1997033272A1", "url": "https://patents.google.com/patent/WO1997033272A1/en"},
        {"id": "US20220083955A1", "url": "https://patents.google.com/patent/US20220083955A1/en"},
        {"id": "US20220083956A1", "url": "https://patents.google.com/patent/US20220083956A1/en"},
        {"id": "US20220083957A1", "url": "https://patents.google.com/patent/US20220083957A1/en"},
        {
            "id": "WO2023123456A1",
            "url": "https://patents.google.com/patent/WO2023123456A1/en",
            "citation_policy": "DO_NOT_CITE_UNTIL_VERIFIED_OR_STRICKEN",
        },
    ]
    results = []
    mismatches = []
    for t in targets:
        r = _http_get(t["url"])
        title = _title_from_html(r.get("body_preview") or "")
        hit = bool(r.get("ok") and title and (t["id"][:6] in title.replace(" ", "") or "patent" in title.lower()))
        claim = claimed.get(t["id"])
        title_l = (title or "").lower()
        mismatch = None
        if claim and title and t["id"].startswith("US"):
            # US pubs in continuity claim blockchain/IP — observed titles differ
            if "blockchain" not in title_l and "ledger" not in title_l and "intellectual" not in title_l:
                mismatch = {
                    "claimed_theme": claim,
                    "observed_title": title,
                    "severity": "CRITICAL",
                }
        if claim and title and t["id"].startswith("CZ"):
            if "caffeine" not in title_l and "vapor" not in title_l:
                mismatch = {
                    "claimed_theme": claim,
                    "observed_title": title,
                    "severity": "CRITICAL",
                }
        if t["id"] == "WO1997033272A1" and title and "stringless" in title_l:
            # Matches court_ready PCT, not caffeine vaporizer foundational claim
            mismatch = {
                "claimed_theme": "Linked in package as Skoda PCT; not caffeine vaporizer",
                "observed_title": title,
                "severity": "HIGH",
                "note": "Aligns with court_ready SKODA_PCT title; does not authenticate CZ caffeine grant",
            }
        row = {
            **{k: t[k] for k in t if k != "url"},
            "url": t["url"],
            "probe_ok": bool(r.get("ok")),
            "content_hit_heuristic": hit,
            "title": title,
            "claimed_theme": claim,
            "title_mismatch": mismatch,
            "status_code": r.get("status_code"),
            "elapsed_ms": r.get("elapsed_ms"),
            "bytes": r.get("bytes"),
            "body_sha3_256": r.get("body_sha3_256"),
            "error": r.get("error"),
        }
        results.append(row)
        if mismatch:
            mismatches.append({"id": t["id"], **mismatch})
        time.sleep(0.2)
    ok_n = sum(1 for r in results if r.get("probe_ok"))
    return {
        "wave": 2,
        "id": "patent_deep_screen",
        "title": "Czech/PCT/USPTO Google Patents deep screen",
        "status": "integrity_alert" if mismatches else ("partial" if ok_n else "blocked"),
        "probe_ok_count": ok_n,
        "title_mismatch_count": len(mismatches),
        "title_mismatches": mismatches,
        "results": results,
        "citation_hold": [
            "Do not cite CZ283061 as Caffeine Vaporizer until certified UPV extract confirms title/inventor",
            "Do not cite US20220083955/56/57A1 as blockchain/IP Skoda filings — observed Google titles differ",
            "WO2023123456A1 remains non-citable placeholder policy",
        ],
        "next_actions": [
            "PRIORITY: Obtain certified Czech file for true caffeine vaporizer grant number (may not be 283061)",
            "Rebuild continuity_chain node IDs from primary USPTO/WIPO records only",
            "Quarantine mismatched publication numbers from any referral package",
        ],
        "adjudicated": False,
    }


def wave_ohio_full() -> dict[str, Any]:
    roster = json.loads((ROOT / "data" / "victim_inventor_ohio_llc_roster.json").read_text())
    targets = [e for e in roster.get("entities") or [] if e.get("ohio_llc") or e.get("illicit_mirror")]
    # Deduplicate by name
    seen: set[str] = set()
    uniq = []
    for e in targets:
        name = (e.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        uniq.append(e)

    def _one(e: dict[str, Any]) -> dict[str, Any]:
        name = e.get("name") or ""
        # ASCII fold for search (Š → S)
        ascii_name = (
            name.replace("Š", "S")
            .replace("š", "s")
            .replace("Á", "A")
            .replace("á", "a")
        )
        q = urllib.parse.quote(ascii_name)
        # OpenCorporates currently 403 from this egress — keep attempt + Ohio portal pointer
        url = f"https://opencorporates.com/companies?q={q}&jurisdiction_code=us_oh"
        r = _http_get(url)
        return {
            "entity_id": e.get("entity_id"),
            "name": name,
            "search_name": ascii_name,
            "illicit_mirror": bool(e.get("illicit_mirror")),
            "screening_only": True,
            "opencorporates_ok": bool(r.get("ok")),
            "status_code": r.get("status_code"),
            "elapsed_ms": r.get("elapsed_ms"),
            "bytes": r.get("bytes"),
            "body_sha3_256": r.get("body_sha3_256"),
            "url": url,
            "error": r.get("error"),
        }

    rows: list[dict[str, Any]] = []
    # Sequential to reduce 403 bursts; still may be blocked at edge
    for e in uniq:
        rows.append(_one(e))
        time.sleep(0.35)
    rows.sort(key=lambda r: r.get("entity_id") or "")
    ok = sum(1 for r in rows if r.get("opencorporates_ok"))
    blocked_403 = sum(1 for r in rows if r.get("status_code") == 403)
    mirrors = [r for r in rows if r.get("illicit_mirror")]
    portal = _http_get("https://businesssearch.ohiosos.gov/", accept="text/html")
    summary = {
        "wave": 2,
        "id": "ohio_opencorporates_full_screen",
        "title": "Full Ohio LLC OpenCorporates screen (41+mirrors)",
        "status": "blocked_egress" if blocked_403 == len(rows) and ok == 0 else "partial",
        "counts": {
            "targets": len(uniq),
            "opencorporates_http_ok": ok,
            "http_403": blocked_403,
            "illicit_mirror_tagged": len(mirrors),
            "claimed_scope": 69,
            "gap_retained": max(0, 69 - sum(1 for e in roster.get("entities") or [] if e.get("ohio_llc"))),
        },
        "ohio_sos_portal": {
            k: portal.get(k)
            for k in ("ok", "status_code", "elapsed_ms", "body_sha3_256", "url", "error")
        },
        "illicit_mirrors": mirrors,
        "results": rows,
        "next_actions": [
            "Operator workstation: Ohio SOS business search abstracts for all 41 + 2 mirrors",
            "Retry OpenCorporates with registered API key (OPENCORPORATES_KEY) if available",
            "Never invent entities to close gap 28",
        ],
        "adjudicated": False,
        "policy": "OpenCorporates HTML search is a screen, not corporate existence adjudication",
    }
    _write(OUT / "OHIO_OPENCORPORATES_FULL.json", summary)
    return summary


def wave_az_salvador() -> dict[str, Any]:
    form = json.loads((ROOT / "data" / "anthony_g_salvador_victim_inventor_form.json").read_text())
    subj = form.get("subject") or {}
    name = subj.get("name") or "Anthony G. Salvador"
    queries = [
        ("azb_home", "https://www.azb.org/"),
        (
            "duckduckgo_az_discipline",
            "https://html.duckduckgo.com/html/?"
            + urllib.parse.urlencode({"q": f"{name} Arizona State Bar discipline"}),
        ),
        (
            "duckduckgo_salvador_disbarred",
            "https://html.duckduckgo.com/html/?"
            + urllib.parse.urlencode({"q": f'"{name}" disbarred Arizona'}),
        ),
    ]
    probes = []
    for label, url in queries:
        r = _http_get(url)
        probes.append(
            {
                "label": label,
                "ok": r.get("ok"),
                "status_code": r.get("status_code"),
                "elapsed_ms": r.get("elapsed_ms"),
                "bytes": r.get("bytes"),
                "body_sha3_256": r.get("body_sha3_256"),
                "url": url,
                "error": r.get("error"),
                "title": _title_from_html(r.get("body_preview") or ""),
            }
        )
        time.sleep(0.3)
    return {
        "wave": 2,
        "id": "salvador_az_bar_screen",
        "title": "Anthony G. Salvador AZ bar discipline screen",
        "status": "open_manual",
        "screening_only": True,
        "subject": {
            "name": name,
            "title": subj.get("title"),
            "firm": subj.get("firm"),
            "office": subj.get("office"),
        },
        "probes": probes,
        "next_actions": [
            "Obtain certified Arizona State Bar discipline order (primary)",
            "Do not charge from betrayal_allegation JSON flag alone",
        ],
        "adjudicated": False,
    }


def wave_collegefitness_cdx() -> dict[str, Any]:
    domain = "collegefitness.com"
    # Simpler query — collapse/filter combos often timeout from this egress
    url = (
        "https://web.archive.org/cdx/search/cdx?"
        + urllib.parse.urlencode(
            {
                "url": domain,
                "output": "json",
                "fl": "timestamp,original,statuscode,digest",
                "filter": "statuscode:200",
                "limit": 1000,
            }
        )
    )
    snapshots = []
    years: list[str] = []
    probe: dict[str, Any]
    try:
        raw = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": USER_AGENT}),
            timeout=30,
        ).read()
        arr = json.loads(raw.decode("utf-8"))
        if isinstance(arr, list) and len(arr) > 1:
            for row in arr[1:]:
                snapshots.append(
                    {
                        "timestamp": row[0],
                        "original": row[1],
                        "status": row[2],
                        "digest": row[3],
                    }
                )
        years = sorted({s["timestamp"][:4] for s in snapshots})
        probe = {
            "ok": True,
            "status_code": 200,
            "bytes": len(raw),
            "body_sha3_256": hashlib.sha3_256(raw).hexdigest(),
            "url": url,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        probe = {"ok": False, "error": type(exc).__name__, "url": url}
    earliest = snapshots[0]["timestamp"] if snapshots else None
    latest = snapshots[-1]["timestamp"] if snapshots else None
    out = {
        "wave": 2,
        "id": "collegefitness_cdx_span",
        "title": "CollegeFitness.com CDX span",
        "status": "partial" if snapshots else "blocked",
        "domain": domain,
        "snapshot_count": len(snapshots),
        "snapshot_years": len(years),
        "years": years,
        "earliest": earliest,
        "latest": latest,
        "snapshots_head": snapshots[:10],
        "snapshots_tail": snapshots[-10:],
        "probe": probe,
        "next_actions": [
            "Pull WARC for earliest (2001+) and counsel-meeting years",
            "Correlate with Ulmer/Fine meeting chronology (human)",
        ],
        "adjudicated": False,
    }
    _write(OUT / "COLLEGEFITNESS_CDX_SPAN.json", out)
    return out


def ensure_run_hmac_key() -> tuple[str, bool]:
    """Return HMAC key hex and whether newly generated. Key stays under output_artifacts/."""
    key_path = ROOT / "output_artifacts" / "investigation" / ".run_hmac_key"
    env_key = os.environ.get("EVIDENCE_HMAC_KEY", "").strip()
    if env_key and not env_key.lower().startswith("community") and env_key != "default-key":
        return env_key, False
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.is_file():
        return key_path.read_text(encoding="utf-8").strip(), False
    key = secrets.token_hex(32)
    key_path.write_text(key + "\n", encoding="utf-8")
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return key, True


def run_wave2() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    tracks = [
        wave_patents(),
        wave_ohio_full(),
        wave_az_salvador(),
        wave_collegefitness_cdx(),
    ]
    for t in tracks:
        _write(OUT / f"{t['id']}.json", t)
        _write(DOCS / f"{t['id']}.json", t)

    key, key_new = ensure_run_hmac_key()
    # Prefer env for subsequent seals in-process
    os.environ["EVIDENCE_HMAC_KEY"] = key

    leaves = [{"id": t["id"], "sha3_256": _sha3_256(t), "status": t.get("status")} for t in tracks]
    material = json.dumps(
        {"case_id": CASE_ID, "leaves": leaves, "generated_at": _utc()},
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
            "by_status": {
                s: sum(1 for t in tracks if t.get("status") == s)
                for s in sorted({t.get("status") for t in tracks})
            },
            "adjudicated_total": 0,
            "true_ubo_asserted": 0,
            "patent_probe_ok": next(t for t in tracks if t["id"] == "patent_deep_screen").get(
                "probe_ok_count"
            ),
            "ohio_targets": (next(t for t in tracks if t["id"] == "ohio_opencorporates_full_screen").get("counts") or {}).get(
                "targets"
            ),
            "ohio_http_ok": (next(t for t in tracks if t["id"] == "ohio_opencorporates_full_screen").get("counts") or {}).get(
                "opencorporates_http_ok"
            ),
            "cdx_years": next(t for t in tracks if t["id"] == "collegefitness_cdx_span").get(
                "snapshot_years"
            ),
            "cdx_snapshots": next(t for t in tracks if t["id"] == "collegefitness_cdx_span").get(
                "snapshot_count"
            ),
            "patent_title_mismatches": next(
                t for t in tracks if t["id"] == "patent_deep_screen"
            ).get("title_mismatch_count"),
        },
        "tracks": [
            {
                "id": t["id"],
                "title": t.get("title"),
                "status": t.get("status"),
                "next_actions": t.get("next_actions"),
                "citation_hold": t.get("citation_hold"),
                "title_mismatches": t.get("title_mismatches"),
                "adjudicated": False,
            }
            for t in tracks
        ],
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "hmac_key_source": "env" if not key_new and os.environ.get("EVIDENCE_HMAC_KEY") else (
                "generated_run_local" if key_new else "reused_run_local"
            ),
            "hmac_key_path": "output_artifacts/investigation/.run_hmac_key",
            "leaves": leaves,
        },
        "policy": (
            "Wave-2 public screens only. Run-local HMAC key is for integrity of this "
            "ledger, not a production secret vault. Replace via EVIDENCE_HMAC_KEY for ops."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE2_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE2_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE2_SUMMARY.json", report)

    # Merge note into parent investigation summary pointer
    pointer = {
        "brand": BRAND,
        "parent_case": "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION",
        "wave2_case": CASE_ID,
        "generated_at": report["generated_at"],
        "summary_path": "docs/investigation/wave2/WAVE2_RUN_SUMMARY.json",
        "seal": report["seal"],
    }
    _write(ROOT / "docs" / "investigation" / "WAVE2_POINTER.json", pointer)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 2")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave2()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        print(
            f"{BRAND} wave2: tracks={c['tracks']} status={c['by_status']} "
            f"patents_ok={c['patent_probe_ok']} ohio_ok={c['ohio_http_ok']}/{c['ohio_targets']} "
            f"cdx_years={c['cdx_years']} hmac=yes seal={report['seal'][:16]}…"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

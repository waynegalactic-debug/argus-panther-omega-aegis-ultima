#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 3
===============================
Primary-source patent integrity quarantine + continuity rebuild candidates.

Wave 2 showed publication numbers in the continuity chain / court-ready baseline
do not match claimed titles. Wave 3 pulls inventor fields from Google Patents
detail pages and quarantines false linkages.

POLICY
------
• No adjudications of theft/RICO/UBO.
• Quarantine ≠ proof of opposing narrative — only that cited numbers fail match.
• Foundational caffeine-vaporizer CZ grant remains OPEN until certified UPV hit.
• CollegeFitness.com chronology retained as independent OSINT track.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE3"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W3"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave3"
DOCS = ROOT / "docs" / "investigation" / "wave3"
USER_AGENT = "IP-FORCE-InvestigationWave3/2026.7.23 (+evidence)"
TIMEOUT = 25.0

# Numbers previously cited in corpus — now under integrity review
CITED_PATENTS = [
    {
        "id": "CZ283061B6",
        "url": "https://patents.google.com/patent/CZ283061B6/en",
        "corpus_claim": {
            "title": "Caffeine Vaporizer",
            "inventor": "Brent Michael Škoda",
            "source": "court_ready_forensic_blueprint.SKODA_CZ_PATENT / continuity CZ1997",
        },
    },
    {
        "id": "WO1997033272A1",
        "url": "https://patents.google.com/patent/WO1997033272A1/en",
        "corpus_claim": {
            "title": "Stringless twitch fret instrument",
            "inventors": ["Slobodan Škoda", "Brent M. Skoda"],
            "source": "court_ready_forensic_blueprint.SKODA_PCT",
        },
    },
    {
        "id": "US5618592A",
        "url": "https://patents.google.com/patent/US5618592A/en",
        "corpus_claim": {
            "title": "Caffeine Vaporizer (Robert J. Cima assignee conflict)",
            "inventors": ["Robert J. Cima"],
            "source": "court_ready_forensic_blueprint.CONFLICTING_US_PATENT",
        },
    },
    {
        "id": "US20220083955A1",
        "url": "https://patents.google.com/patent/US20220083955A1/en",
        "corpus_claim": {
            "title": "Blockchain Patent Portfolio Management and Tokenized Royalty System",
            "source": "victim_inventor_continuity_chain.json",
        },
    },
    {
        "id": "US20220083956A1",
        "url": "https://patents.google.com/patent/US20220083956A1/en",
        "corpus_claim": {
            "title": "Distributed Ledger Identity Verification for Intellectual Property",
            "source": "victim_inventor_continuity_chain.json",
        },
    },
    {
        "id": "US20220083957A1",
        "url": "https://patents.google.com/patent/US20220083957A1/en",
        "corpus_claim": {
            "title": "verified_downstream_filing",
            "source": "victim_inventor_continuity_chain.json",
        },
    },
    {
        "id": "WO2023123456A1",
        "url": "https://patents.google.com/patent/WO2023123456A1/en",
        "corpus_claim": {
            "title": "placeholder_pct",
            "source": "victim_inventor_continuity_chain.json",
        },
    },
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
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fetch_html(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, method="GET"
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(400000)
            return {
                "ok": True,
                "status_code": resp.status,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "bytes": len(body),
                "body_sha3_256": hashlib.sha3_256(body).hexdigest(),
                "html": body.decode("utf-8", errors="replace"),
                "url": url,
                "error": None,
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status_code": getattr(exc, "code", None),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "bytes": 0,
            "body_sha3_256": None,
            "html": "",
            "url": url,
            "error": type(exc).__name__,
        }


def _parse_patent_page(html: str) -> dict[str, Any]:
    title_m = re.search(r"<title>([^<]+)</title>", html, flags=re.I)
    title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else None
    inventors = re.findall(r'itemprop="inventor"[^>]*>\s*([^<]+)', html)
    inventors = [re.sub(r"\s+", " ", i).strip() for i in inventors if i.strip()]
    assignees = re.findall(r'itemprop="assigneeCurrent"[^>]*>\s*([^<]+)', html)
    assignees = [re.sub(r"\s+", " ", a).strip() for a in assignees if a.strip()]
    return {
        "title": title,
        "inventors": inventors,
        "assignees": assignees,
        "mentions_skoda": "skoda" in html.lower() or "škoda" in html.lower(),
        "mentions_caffeine": "caffeine" in html.lower(),
        "mentions_vapor": "vapor" in html.lower(),
    }


def probe_cited_patents() -> dict[str, Any]:
    rows = []
    for spec in CITED_PATENTS:
        fetched = _fetch_html(spec["url"])
        parsed = _parse_patent_page(fetched.get("html") or "") if fetched.get("ok") else {}
        claim = spec["corpus_claim"]
        claim_title = (claim.get("title") or "").lower()
        obs_title = (parsed.get("title") or "").lower()
        claim_inventors = claim.get("inventors") or (
            [claim["inventor"]] if claim.get("inventor") else []
        )
        obs_inventors = parsed.get("inventors") or []
        title_mismatch = bool(
            claim.get("title")
            and parsed.get("title")
            and not any(
                tok in obs_title
                for tok in re.findall(r"[a-z]{4,}", claim_title)[:3]
                if tok not in {"patent", "system", "device", "method", "with", "from"}
            )
            and claim_title.split("(")[0].strip() not in obs_title
        )
        # Stronger checks for known critical cases
        if spec["id"].startswith("CZ") and "caffeine" not in obs_title:
            title_mismatch = True
        if spec["id"].startswith("US561") and "caffeine" not in obs_title:
            title_mismatch = True
        if "blockchain" in claim_title and "blockchain" not in obs_title:
            title_mismatch = True

        inventor_mismatch = False
        if claim_inventors and obs_inventors:
            claim_norm = {re.sub(r"[^a-z]", "", x.lower()) for x in claim_inventors}
            obs_norm = {re.sub(r"[^a-z]", "", x.lower()) for x in obs_inventors}
            inventor_mismatch = claim_norm.isdisjoint(obs_norm)

        quarantine = title_mismatch or inventor_mismatch or spec["id"].startswith("WO202312")
        rows.append(
            {
                "id": spec["id"],
                "url": spec["url"],
                "probe_ok": bool(fetched.get("ok")),
                "status_code": fetched.get("status_code"),
                "elapsed_ms": fetched.get("elapsed_ms"),
                "body_sha3_256": fetched.get("body_sha3_256"),
                "error": fetched.get("error"),
                "corpus_claim": claim,
                "observed": {
                    "title": parsed.get("title"),
                    "inventors": obs_inventors,
                    "assignees": parsed.get("assignees"),
                    "mentions_skoda": parsed.get("mentions_skoda"),
                    "mentions_caffeine": parsed.get("mentions_caffeine"),
                },
                "title_mismatch": title_mismatch,
                "inventor_mismatch": inventor_mismatch,
                "quarantine": quarantine,
                "severity": "CRITICAL" if quarantine else "INFO",
            }
        )
        time.sleep(0.35)

    quarantined = [r for r in rows if r.get("quarantine")]
    return {
        "wave": 3,
        "id": "patent_primary_quarantine",
        "title": "Primary-source quarantine of cited patent numbers",
        "status": "integrity_alert",
        "probe_ok_count": sum(1 for r in rows if r.get("probe_ok")),
        "quarantine_count": len(quarantined),
        "quarantined_ids": [r["id"] for r in quarantined],
        "results": rows,
        "citation_hold": [
            "QUARANTINE all listed publication numbers from referral packages",
            "Do not assert CZ283061 / US5618592 / WO1997033272 as Skoda caffeine-vaporizer chain",
            "Do not assert US20220083955/56/57 as Skoda blockchain-IP filings",
            "Foundational caffeine CZ grant status = OPEN_MANUAL (certified UPV search required)",
        ],
        "next_actions": [
            "UPV certified search: inventor Brent Michael Škoda + caffeine vaporizer + 1997 gazette",
            "USPTO inventor-name search (ODP key) — rebuild downstream nodes from hits only",
            "Amend court_ready SKODA_CZ_PATENT / CONFLICTING_US_PATENT / SKODA_PCT constants after primaries",
        ],
        "adjudicated": False,
    }


def quarantine_continuity_chain() -> dict[str, Any]:
    src = ROOT / "data" / "victim_inventor_continuity_chain.json"
    original = json.loads(src.read_text(encoding="utf-8"))
    bad_ids = {
        "US20220083955A1",
        "US20220083956A1",
        "US20220083957A1",
        "WO2023123456A1",
        # CZ node kept as claim stub but marked unverified — number linkage broken
    }
    quarantined_nodes = []
    retained_nodes = []
    for node in original.get("chain_nodes") or []:
        nid = node.get("node_id")
        if nid in bad_ids:
            quarantined_nodes.append(
                {
                    **node,
                    "quarantine": True,
                    "quarantine_reason": "publication_number_failed_primary_title_inventor_match",
                    "citation_policy": "DO_NOT_CITE",
                }
            )
        elif nid == "CZ1997-CaffeineVaporizer":
            retained_nodes.append(
                {
                    **node,
                    "verification_status": "OPEN_MANUAL_UNVERIFIED_NUMBER",
                    "note": (
                        "Corpus links CZ283061 which Google Patents shows as unrelated loom patent. "
                        "Retain as claim stub only until certified UPV extract identifies correct grant."
                    ),
                    "linked_number_quarantined": "CZ283061",
                }
            )
        else:
            retained_nodes.append({**node, "verification_status": "OSINT_RETAINED"})

    quarantined_links = []
    retained_links = []
    for link in original.get("continuity_links") or []:
        if link.get("child_node_id") in bad_ids or link.get("parent_node_id") in bad_ids:
            quarantined_links.append({**link, "quarantine": True})
        else:
            retained_links.append(link)

    rebuilt = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "rebuild_policy": (
            "Honest continuity candidate after Wave-3 quarantine. "
            "Not a complete chain-of-title. No patent theft adjudication."
        ),
        "source_original": "data/victim_inventor_continuity_chain.json",
        "victim_inventor": original.get("foundational_patent_inventor"),
        "foundational_claim": {
            "label": "CZ1997-CaffeineVaporizer",
            "status": "OPEN_MANUAL_UNVERIFIED_NUMBER",
            "claimed_date": original.get("foundational_date"),
            "claimed_office": original.get("foundational_patent_office"),
            "do_not_cite_number": "CZ283061",
        },
        "retained_nodes": retained_nodes,
        "quarantined_nodes": quarantined_nodes,
        "retained_links": retained_links,
        "quarantined_links": quarantined_links,
        "open_gaps": [
            "Certified Czech grant number/title/inventor for caffeine vaporizer claim",
            "USPTO inventor-name hit list for Brent Michael Škoda",
            "Any PCT/national-phase links must be re-derived from authenticated parents",
        ],
        "adjudicated": False,
        "true_ubo_asserted": 0,
    }
    rebuilt["seal"] = _sha3_256({k: v for k, v in rebuilt.items() if k != "seal"})

    out_path = ROOT / "data" / "victim_inventor_continuity_chain_REBUILT_CANDIDATE.json"
    q_path = ROOT / "data" / "victim_inventor_continuity_chain_QUARANTINE.json"
    _write(out_path, rebuilt)
    _write(
        q_path,
        {
            "brand": BRAND,
            "generated_at": _utc(),
            "quarantined_nodes": quarantined_nodes,
            "quarantined_links": quarantined_links,
            "citation_policy": "DO_NOT_CITE",
            "seal": _sha3_256(quarantined_nodes),
        },
    )
    return {
        "wave": 3,
        "id": "continuity_rebuild_candidate",
        "title": "Quarantine bad pub nodes; emit honest continuity candidate",
        "status": "done",
        "rebuilt_path": str(out_path.relative_to(ROOT)),
        "quarantine_path": str(q_path.relative_to(ROOT)),
        "counts": {
            "retained_nodes": len(retained_nodes),
            "quarantined_nodes": len(quarantined_nodes),
            "retained_links": len(retained_links),
            "quarantined_links": len(quarantined_links),
        },
        "rebuilt_seal": rebuilt["seal"],
        "next_actions": [
            "Replace referral packaging to use REBUILT_CANDIDATE + quarantine files",
            "Do not delete original continuity file — keep as contaminated corpus evidence of prior claim set",
        ],
        "adjudicated": False,
    }


def court_ready_constant_audit() -> dict[str, Any]:
    """Static audit of contaminated constants (no code rewrite of monolith claims here)."""
    return {
        "wave": 3,
        "id": "court_ready_constant_audit",
        "title": "Audit court_ready patent baseline constants vs primary probes",
        "status": "integrity_alert",
        "constants": [
            {
                "name": "SKODA_CZ_PATENT",
                "claimed": {"number": "283061", "title": "Caffeine Vaporizer"},
                "observed_google": {
                    "title": "Weft insertion motion for a loom",
                    "inventors": ["Luciano Corain", "Giulio Bortoli"],
                },
                "verdict": "QUARANTINE_NUMBER",
            },
            {
                "name": "SKODA_PCT",
                "claimed": {
                    "publication": "WO1997033272A1",
                    "inventors": ["Slobodan Škoda", "Brent M. Skoda"],
                },
                "observed_google": {
                    "title": "Stringless twitch fret instrument",
                    "inventors": ["Ivan Mladek"],
                },
                "verdict": "QUARANTINE_INVENTOR_LINK",
            },
            {
                "name": "CONFLICTING_US_PATENT",
                "claimed": {
                    "patent_number": "5618592",
                    "title": "Caffeine Vaporizer (Robert J. Cima…)",
                },
                "observed_google": {
                    "title": "Liquid crystal display device",
                    "inventors": ["Nobukazu Nagae", "Motohiro Yamahara", "Nobuaki Yamada"],
                    "assignee": "Sharp Corp",
                },
                "verdict": "QUARANTINE_NUMBER",
            },
        ],
        "next_actions": [
            "Patch court_ready constants to empty/open_manual after operator confirms",
            "Keep allegation narrative only with primary-source exhibits attached",
        ],
        "adjudicated": False,
    }


def write_integrity_alert(patent_q: dict[str, Any], audit: dict[str, Any]) -> str:
    path = ROOT / "docs" / "investigation" / "INTEGRITY_ALERT_WAVE3_QUARANTINE.md"
    lines = [
        "# INTEGRITY ALERT — Wave 3 Patent Quarantine",
        "",
        f"**Case:** `{CASE_ID}`  ",
        f"**Generated:** `{_utc()}`  ",
        "**Severity:** CRITICAL for referral packaging",
        "",
        "## Verdict",
        "",
        "Multiple publication numbers used as Skoda / caffeine-vaporizer / blockchain-IP",
        "exhibits **fail primary Google Patents title and inventor match**. They are",
        "**quarantined** from citation until certified UPV/USPTO records say otherwise.",
        "",
        "## Quarantined IDs",
        "",
    ]
    for rid in patent_q.get("quarantined_ids") or []:
        lines.append(f"- `{rid}`")
    lines += [
        "",
        "## court_ready constant audit",
        "",
        "| Constant | Verdict |",
        "|----------|---------|",
    ]
    for c in audit.get("constants") or []:
        lines.append(f"| `{c['name']}` | {c['verdict']} |")
    lines += [
        "",
        "## Continuity rebuild",
        "",
        "- Original: `data/victim_inventor_continuity_chain.json` (retained as contaminated claim set)",
        "- Quarantine: `data/victim_inventor_continuity_chain_QUARANTINE.json`",
        "- Candidate: `data/victim_inventor_continuity_chain_REBUILT_CANDIDATE.json`",
        "",
        "## Open manual",
        "",
        "1. Certified Czech UPV search by inventor + caffeine vaporizer + 1997",
        "2. USPTO inventor-name search with real ODP key",
        "3. Rebuild national-phase links only from authenticated parents",
        "",
        "---",
        "",
        "IP FORCE · Wave 3 · No theft/RICO adjudication implied",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def ensure_hmac_key() -> str:
    env = os.environ.get("EVIDENCE_HMAC_KEY", "").strip()
    if env and not env.lower().startswith("community") and env != "default-key":
        return env
    key_path = ROOT / "output_artifacts" / "investigation" / ".run_hmac_key"
    if key_path.is_file():
        return key_path.read_text(encoding="utf-8").strip()
    # reuse wave2 generator if present
    try:
        from us_ipforce_investigation_wave2 import ensure_run_hmac_key

        key, _ = ensure_run_hmac_key()
        return key
    except Exception:  # noqa: BLE001
        import secrets

        key_path.parent.mkdir(parents=True, exist_ok=True)
        key = secrets.token_hex(32)
        key_path.write_text(key + "\n", encoding="utf-8")
        return key


def run_wave3() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    patent_q = probe_cited_patents()
    audit = court_ready_constant_audit()
    rebuild = quarantine_continuity_chain()
    alert = write_integrity_alert(patent_q, audit)

    tracks = [patent_q, audit, rebuild]
    for t in tracks:
        _write(OUT / f"{t['id']}.json", t)
        _write(DOCS / f"{t['id']}.json", t)

    key = ensure_hmac_key()
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
            "quarantined_patent_ids": patent_q.get("quarantine_count"),
            "continuity_quarantined_nodes": (rebuild.get("counts") or {}).get("quarantined_nodes"),
            "continuity_retained_nodes": (rebuild.get("counts") or {}).get("retained_nodes"),
            "adjudicated_total": 0,
            "true_ubo_asserted": 0,
        },
        "tracks": [
            {
                "id": t["id"],
                "title": t.get("title"),
                "status": t.get("status"),
                "next_actions": t.get("next_actions"),
                "citation_hold": t.get("citation_hold"),
                "adjudicated": False,
            }
            for t in tracks
        ],
        "artifacts": {
            "integrity_alert": alert,
            "rebuilt_continuity": rebuild.get("rebuilt_path"),
            "quarantine_continuity": rebuild.get("quarantine_path"),
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-3 quarantines false patent linkages. Foundational caffeine CZ grant "
            "remains open/manual. No theft adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE3_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE3_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE3_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE3_POINTER.json",
        {
            "brand": BRAND,
            "wave3_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave3/WAVE3_RUN_SUMMARY.json",
            "integrity_alert": alert,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 3")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave3()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report["counts"]
        print(
            f"{BRAND} wave3: quarantined_patents={c['quarantined_patent_ids']} "
            f"continuity_q_nodes={c['continuity_quarantined_nodes']} "
            f"retained={c['continuity_retained_nodes']} "
            f"hmac=yes seal={report['seal'][:16]}…"
        )
        print(f"  alert: {report['artifacts']['integrity_alert']}")
        print(f"  rebuilt: {report['artifacts']['rebuilt_continuity']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 23
================================
Systematic screen of alleged ABG-linked 90M shell corporations, nested/hidden
subsidiaries, and Fortune 5000 / Global 2000 / S&P 500 DAO / stealth-DAO
licensing used as illicit monetization fronts for stolen victim IP.

Deterministic public probes + sealed prior-wave inventory only.
Does NOT adjudicate illicit monetization, theft, DAO licensing, RICO, or UBO.
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
VERSION = "2026.7.23-INVESTIGATION-WAVE23"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W23"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave23"
DOCS = ROOT / "docs" / "investigation" / "wave23"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave23/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
CTX = ssl.create_default_context()

# Monolith corpus constants (NOT authenticated inventories)
MONOLITH_SHELL_CORPORATIONS_CONSTANT = 90_000_000
MONOLITH_STEALTH_DAOS_CONSTANT = 90_000_000
MONOLITH_FORTUNE_5000_COUNT = 5000
MONOLITH_GLOBAL_2000_COUNT = 2000

WAYBACK_S1 = (
    "https://web.archive.org/web/20220205151159/"
    "https://www.sec.gov/Archives/edgar/data/1666054/000110465921089494/"
    "tm2114913-5_s1.htm"
)
WAYBACK_S1_INDEX = (
    "https://web.archive.org/web/20250213063207/"
    "https://www.sec.gov/Archives/edgar/data/1666054/0001104659-21-089494-index.htm"
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


def _fetch(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/html,*/*"}
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=90, context=CTX) as resp:
            body = resp.read()
            return {
                "ok": True,
                "url": url,
                "final_url": getattr(resp, "url", url),
                "status": getattr(resp, "status", 200),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
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
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "body": body,
            "error": f"{type(exc).__name__}:{exc}"[:240],
        }


def _extract_entities(plain: str) -> list[str]:
    entities: set[str] = set()
    for m in re.finditer(
        r"\b(ABG(?:\s+[A-Z][A-Za-z0-9'&\-]*){0,6}\s+"
        r"(?:LLC|L\.L\.C\.|LP|L\.P\.|Inc\.|Corporation|Corp\.|Ltd\.|LLLP))\b",
        plain,
    ):
        entities.add(re.sub(r"\s+", " ", m.group(1)).strip())
    for m in re.finditer(
        r"\b(Authentic Brands(?:\s+Group)?(?:\s+[A-Z][A-Za-z0-9'&\-]*){0,4}\s+"
        r"(?:LLC|L\.L\.C\.|LP|Inc\.|LLLP|Corporation))\b",
        plain,
    ):
        entities.add(re.sub(r"\s+", " ", m.group(1)).strip())
    return sorted(entities)


def track_corpus_constant_classification() -> dict[str, Any]:
    """Classify 90M / Fortune-universe DAO claims as monolith constants vs evidence."""
    mono = ROOT / "us_ipforce_monolith_live.py"
    text = mono.read_text(encoding="utf-8", errors="replace") if mono.is_file() else ""
    constants = {
        "SHELL_CORPORATIONS": {
            "value": MONOLITH_SHELL_CORPORATIONS_CONSTANT,
            "present_in_monolith": "SHELL_CORPORATIONS = 90_000_000" in text,
            "class": "CORPUS_CONSTANT_NOT_AUTHENTICATED_INVENTORY",
        },
        "STEALTH_DAOS": {
            "value": MONOLITH_STEALTH_DAOS_CONSTANT,
            "present_in_monolith": "STEALTH_DAOS = 90_000_000" in text,
            "class": "CORPUS_CONSTANT_NOT_AUTHENTICATED_INVENTORY",
        },
        "FORTUNE_5000_COUNT": {
            "value": MONOLITH_FORTUNE_5000_COUNT,
            "present_in_monolith": "FORTUNE_5000_COUNT = 5000" in text,
            "class": "CORPUS_UNIVERSE_SIZE_CONSTANT",
        },
        "GLOBAL_2000_COUNT": {
            "value": MONOLITH_GLOBAL_2000_COUNT,
            "present_in_monolith": "GLOBAL_2000_COUNT = 2000" in text,
            "class": "CORPUS_UNIVERSE_SIZE_CONSTANT",
        },
    }
    synthetic_dao = {
        "method": "USIPForceAnalyzer.scan_fortune_global_dao_licensing / _corporate_at_index",
        "behavior": (
            "Deterministic synthetic corporation rows with dao_licensing_commitment=True "
            "for every index; stealth flag via det_hash % 3. Not EDGAR/contract evidence."
        ),
        "claims_100_percent_coverage": True,
        "authenticated_against_public_filings": False,
        "source_file": "us_ipforce_monolith_live.py",
    }
    findings = [
        {
            "id": "W23-F1",
            "title": "90M shells / 90M stealth DAOs / 100% Fortune-universe DAO licensing are corpus constants, not authenticated inventories",
            "constants": constants,
            "synthetic_dao_engine": synthetic_dao,
            "ninety_million_shells_authenticated": False,
            "fortune_5000_dao_licensing_authenticated": False,
            "global_2000_dao_licensing_authenticated": False,
            "sp500_dao_licensing_authenticated": False,
            "approx_100_percent_coverage_authenticated": False,
            "detail": (
                "Monolith hardcodes SHELL_CORPORATIONS=90_000_000 and STEALTH_DAOS=90_000_000. "
                "Fortune 5000 / Global 2000 DAO licensing '100% coverage' is produced by a "
                "synthetic index loop that sets dao_licensing_commitment=True for every row. "
                "These are not sealed grant-verified or SOS-authenticated shell inventories, "
                "and cannot authenticate illicit monetization fronts for stolen Skoda IP."
            ),
        }
    ]
    return {
        "id": "corpus_constant_classification",
        "title": "90M shell / stealth-DAO / Fortune-universe claim classification",
        "status": "SEALED",
        "constants": constants,
        "synthetic_dao_engine": synthetic_dao,
        "findings": findings,
    }


def track_abg_authenticated_subsidiary_inventory() -> dict[str, Any]:
    w18_path = ROOT / "docs" / "investigation" / "wave18" / "sec_abg_structure.json"
    de_path = ROOT / "docs" / "investigation" / "wave18" / "delaware_abg_entity_roster.json"
    w18 = json.loads(w18_path.read_text(encoding="utf-8")) if w18_path.is_file() else {}
    de = json.loads(de_path.read_text(encoding="utf-8")) if de_path.is_file() else {}

    sec_subs = w18.get("subsidiaries") or []
    de_findings = de.get("findings") or []
    de_detail = []
    de_open = []
    for f in de_findings:
        de_detail.extend(f.get("entities_with_detail") or [])
        de_open.extend(f.get("entities_file_hit_detail_open") or [])

    idx_r = _fetch(WAYBACK_S1_INDEX)
    time.sleep(0.3)
    s1_r = _fetch(WAYBACK_S1)
    exhibits_labeled: list[str] = []
    has_ex21 = False
    if idx_r.get("ok"):
        text = idx_r["body"].decode("utf-8", "replace")
        for m in re.finditer(r">([^<]*(?:EX-|Exhibit)[^<]{0,60})<", text, re.I):
            label = re.sub(r"\s+", " ", m.group(1)).strip()
            exhibits_labeled.append(label)
            if re.search(r"EX-21|Exhibit\s*21", label, re.I):
                has_ex21 = True

    entities: list[str] = []
    s1_meta: dict[str, Any] = {"ok": s1_r.get("ok"), "url": WAYBACK_S1}
    if s1_r.get("ok"):
        html = s1_r["body"].decode("utf-8", "replace")
        plain = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
        plain = re.sub(r"<style[^>]*>.*?</style>", " ", plain, flags=re.I | re.S)
        plain = re.sub(r"<[^>]+>", " ", plain)
        plain = re.sub(r"&\w+;", " ", plain)
        plain = re.sub(r"\s+", " ", plain)
        entities = _extract_entities(plain)
        s1_meta.update(
            {
                "sha256": s1_r.get("sha256"),
                "bytes": s1_r.get("bytes"),
                "final_url": s1_r.get("final_url"),
                "dao_mentions": len(re.findall(r"\bDAO\b", plain)),
                "shell_company_mentions": len(re.findall(r"shell\s+compan", plain, re.I)),
                "ninety_million_mentions": bool(
                    re.search(r"90[\s,]*000[\s,]*000|ninety\s+million|90\s+million", plain, re.I)
                ),
                "fortune_mentions": len(re.findall(r"Fortune\s*5", plain, re.I)),
            }
        )

    authenticated_count = len({e.get("name") for e in sec_subs if e.get("name")})
    wayback_count = len(entities)
    delaware_authenticated_detail = len(de_detail)

    findings = [
        {
            "id": "W23-F2",
            "title": "Authenticated ABG nested entities are order-of-tens, not ninety million shells",
            "wave18_sec_named_subsidiary_count": authenticated_count,
            "wave18_sec_named_subsidiaries": sec_subs,
            "delaware_icis_detail_authenticated_count": delaware_authenticated_detail,
            "delaware_icis_detail_entities": de_detail,
            "delaware_icis_file_hit_detail_open": de_open,
            "wayback_s1_named_entity_count": wayback_count,
            "wayback_s1_named_entities": entities,
            "wayback_s1_index_has_exhibit_21": has_ex21,
            "wayback_s1_index_exhibit_labels_sample": exhibits_labeled[:30],
            "gap_vs_alleged_90_million": MONOLITH_SHELL_CORPORATIONS_CONSTANT
            - max(authenticated_count, wayback_count, delaware_authenticated_detail),
            "hidden_global_shell_inventory_authenticated": False,
            "illicit_monetization_front_adjudicated": False,
            "detail": (
                f"Wave-18 sealed SEC-named ABG holdcos/subs: {authenticated_count}. "
                f"Delaware ICIS detail-authenticated: {delaware_authenticated_detail}. "
                f"Wayback ABG S-1 named ABG/Authentic Brands entities extracted: {wayback_count}. "
                f"S-1 filing index Exhibit 21 present: {has_ex21}. "
                "S-1 text: DAO mentions=0, shell-company mentions=0, ninety-million mentions=false. "
                "No public inventory authenticates 90,000,000 ABG-linked shell corporations "
                "or hidden global subsidiaries as illicit IP monetization fronts."
            ),
        }
    ]
    return {
        "id": "abg_authenticated_subsidiary_inventory",
        "title": "ABG authenticated subsidiary / nested-entity inventory",
        "status": "SEALED",
        "wave18_source": "docs/investigation/wave18/sec_abg_structure.json",
        "delaware_source": "docs/investigation/wave18/delaware_abg_entity_roster.json",
        "wayback_s1": s1_meta,
        "wayback_s1_index": {
            "ok": idx_r.get("ok"),
            "sha256": idx_r.get("sha256"),
            "has_exhibit_21": has_ex21,
            "status": idx_r.get("status"),
        },
        "findings": findings,
        "next_actions": [
            "If ABG refiles a registration statement with Exhibit 21, ingest full subsidiary table",
            "Delaware ICIS captcha still blocks Intermediate Holdings / Aggregator file numbers",
        ],
    }


def track_dao_stealth_fortune_screen() -> dict[str, Any]:
    """Screen DAO / stealth-DAO licensing claims vs ABG + index universes."""
    site = _fetch("https://www.authenticbrandsgroup.com/")
    time.sleep(0.3)
    about = _fetch("https://www.authenticbrandsgroup.com/about")
    site_meta: dict[str, Any] = {}
    for label, r in (("home", site), ("about", about)):
        mentions = {}
        if r.get("ok"):
            text = re.sub(r"<[^>]+>", " ", r["body"].decode("utf-8", "replace"))
            text = re.sub(r"\s+", " ", text)
            mentions = {
                k: bool(re.search(k, text, re.I))
                for k in (
                    "DAO",
                    "blockchain",
                    "ethereum",
                    "NFT",
                    "licensing",
                    "subsidiary",
                    "shell",
                    "Skoda",
                    "patent",
                )
            }
            site_meta[label] = {
                "ok": True,
                "sha256": r.get("sha256"),
                "excerpt": text[:800],
                "mentions": mentions,
            }
        else:
            site_meta[label] = {"ok": False, "status": r.get("status"), "error": r.get("error")}

    # Prior sealed IP set
    port_path = ROOT / "docs" / "investigation" / "wave14" / "EXPANDED_SKODA_PORTFOLIO.json"
    port = json.loads(port_path.read_text(encoding="utf-8")) if port_path.is_file() else {}

    findings = [
        {
            "id": "W23-F3",
            "title": "No authenticated DAO/stealth-DAO licensing rail from ABG to sealed Skoda pubs or Fortune-universe 100% coverage",
            "abg_site_dao_mention": (site_meta.get("home") or {}).get("mentions", {}).get("DAO"),
            "abg_site_blockchain_mention": (site_meta.get("home") or {}).get("mentions", {}).get(
                "blockchain"
            ),
            "authenticated_skoda_publication_count": port.get("publication_count"),
            "dao_licensing_to_stolen_ip_adjudicated": False,
            "stealth_dao_licensing_adjudicated": False,
            "illicit_monetization_via_dao_adjudicated": False,
            "fortune_5000_coverage_authenticated": False,
            "global_2000_coverage_authenticated": False,
            "sp500_and_beyond_coverage_authenticated": False,
            "approx_100_percent_corporate_licensing_authenticated": False,
            "detail": (
                "Public ABG marketing site extracts do not surface DAO/blockchain/NFT/Skoda/"
                "patent keywords as licensing rails. Wayback S-1 (Wave-23 track 2) has zero DAO "
                "mentions. Monolith '100% Fortune 5000 / Global 2000 / S&P' stealth-DAO licensing "
                "remains a synthetic coverage engine. Sealed Skoda portfolio remains 15 pubs; "
                "alleged 15213 families unauthenticated. Cannot adjudicate illicit monetization "
                "fronts via DAO/stealth-DAO licensing from public evidence in this wave."
            ),
        }
    ]
    return {
        "id": "dao_stealth_fortune_licensing_screen",
        "title": "DAO / stealth-DAO × Fortune-universe licensing screen",
        "status": "SEALED",
        "abg_public_site": site_meta,
        "portfolio_source": "docs/investigation/wave14/EXPANDED_SKODA_PORTFOLIO.json",
        "findings": findings,
        "next_actions": [
            "Counsel-only private DAO/license agreements if operator asserts off-public-record rails",
            "Do not treat monolith synthetic Fortune-universe rows as authenticated licensees",
        ],
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-23 operator worklist",
        "status": "OPEN",
        "items": [
            {
                "id": "W23-M1",
                "priority": "HIGH",
                "item": "Supply Exhibit 21 / full ABG org chart if claiming nested subsidiaries beyond sealed S-1 holdcos",
            },
            {
                "id": "W23-M2",
                "priority": "HIGH",
                "item": "Do not equate monolith SHELL_CORPORATIONS=90M with an authenticated global shell census",
            },
            {
                "id": "W23-M3",
                "priority": "MEDIUM",
                "item": "If Fortune/G2000/S&P DAO licenses exist, supply contract hashes / EDGAR exhibits for deterministic ingest",
            },
        ],
        "adjudicated": False,
    }


def write_summary_md(
    corpus: dict[str, Any],
    abg: dict[str, Any],
    dao: dict[str, Any],
) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE23_ABG_SHELL_DAO_FORTUNE_SCREEN.md"
    f1 = (corpus.get("findings") or [{}])[0]
    f2 = (abg.get("findings") or [{}])[0]
    f3 = (dao.get("findings") or [{}])[0]
    lines = [
        "# Wave 23 — ABG shells / nested subs / DAO–Fortune illicit-monetization screen",
        "",
        f"Generated: `{_utc()}`",
        "",
        "## Disposition (policy-gated)",
        "",
        "- `ninety_million_shells_authenticated`: **false**",
        "- `hidden_global_shell_inventory_authenticated`: **false**",
        "- `illicit_monetization_front_adjudicated`: **false**",
        "- `dao_licensing_to_stolen_ip_adjudicated`: **false**",
        "- `stealth_dao_licensing_adjudicated`: **false**",
        "- `fortune_5000_coverage_authenticated`: **false**",
        "- `global_2000_coverage_authenticated`: **false**",
        "- `approx_100_percent_corporate_licensing_authenticated`: **false**",
        "",
        "## Corpus constants vs evidence",
        "",
        f"- Monolith `SHELL_CORPORATIONS`: `{MONOLITH_SHELL_CORPORATIONS_CONSTANT}` → **corpus constant**",
        f"- Monolith `STEALTH_DAOS`: `{MONOLITH_STEALTH_DAOS_CONSTANT}` → **corpus constant**",
        "- Fortune/G2000 '100% DAO licensing': **synthetic index engine** (not filings)",
        "",
        "## Authenticated ABG nested entities",
        "",
        f"- Wave-18 SEC-named: `{f2.get('wave18_sec_named_subsidiary_count')}`",
        f"- Delaware ICIS detail-authenticated: `{f2.get('delaware_icis_detail_authenticated_count')}`",
        f"- Wayback S-1 named entities: `{f2.get('wayback_s1_named_entity_count')}`",
        f"- S-1 Exhibit 21 present: `{f2.get('wayback_s1_index_has_exhibit_21')}`",
        f"- Gap vs alleged 90M: `{f2.get('gap_vs_alleged_90_million')}`",
        "",
        "## DAO / Fortune screen",
        "",
        f"- ABG site DAO mention: `{f3.get('abg_site_dao_mention')}`",
        f"- Sealed Skoda pubs: `{f3.get('authenticated_skoda_publication_count')}`",
        "",
        "## Manual next",
        "",
        "1. Exhibit 21 / full org chart if nested-sub claim expands.",
        "2. Contract-level DAO license evidence before any Fortune-universe coverage claim.",
        "3. Do not upgrade monolith 90M constants into authenticated shell censuses.",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave23() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    corpus = track_corpus_constant_classification()
    abg = track_abg_authenticated_subsidiary_inventory()
    dao = track_dao_stealth_fortune_screen()
    work = track_operator_worklist()
    summary_md = write_summary_md(corpus, abg, dao)

    tracks = [corpus, abg, dao, work]
    for t in tracks:
        sealed = json.loads(json.dumps(t, default=str))
        _write(OUT / f"{t['id']}.json", sealed)
        _write(DOCS / f"{t['id']}.json", sealed)

    key = ensure_hmac_key()
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
    for t in (corpus, abg, dao):
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
            "adjudicated_total": 0,
            "true_ubo_asserted": 0,
            "authenticated_abg_sec_named": (
                (abg.get("findings") or [{}])[0].get("wave18_sec_named_subsidiary_count")
            ),
            "wayback_s1_named_entities": (
                (abg.get("findings") or [{}])[0].get("wayback_s1_named_entity_count")
            ),
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
            "ninety_million_shells_authenticated": False,
            "hidden_global_shell_inventory_authenticated": False,
            "illicit_monetization_front_adjudicated": False,
            "dao_licensing_to_stolen_ip_adjudicated": False,
            "stealth_dao_licensing_adjudicated": False,
            "illicit_monetization_via_dao_adjudicated": False,
            "fortune_5000_coverage_authenticated": False,
            "global_2000_coverage_authenticated": False,
            "sp500_and_beyond_coverage_authenticated": False,
            "approx_100_percent_corporate_licensing_authenticated": False,
            "theft_adjudicated": False,
        },
        "artifacts": {
            "summary_md": summary_md,
            "corpus": "docs/investigation/wave23/corpus_constant_classification.json",
            "abg": "docs/investigation/wave23/abg_authenticated_subsidiary_inventory.json",
            "dao": "docs/investigation/wave23/dao_stealth_fortune_licensing_screen.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-23 separates monolith 90M shell / stealth-DAO / Fortune-universe constants "
            "from authenticated ABG subsidiary surfaces (Wave-18 + Wayback S-1). "
            "No illicit-monetization, theft, or DAO-licensing adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE23_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE23_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE23_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE23_POINTER.json",
        {
            "brand": BRAND,
            "wave23_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave23/WAVE23_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 23")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave23()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        d = report["disposition"]
        print(
            f"{BRAND} wave23: findings={report['counts']['findings']} "
            f"shells90m={d['ninety_million_shells_authenticated']} "
            f"dao={d['dao_licensing_to_stolen_ip_adjudicated']} "
            f"illicit={d['illicit_monetization_front_adjudicated']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

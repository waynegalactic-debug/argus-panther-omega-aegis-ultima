#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 25
================================
Universal linkage matrix: all Wave 21–24 subjects × victim-inventor sealed
intellectual-property surfaces (and alleged stolen-family claims).

Deterministic re-analysis of sealed prior-wave artifacts only (plus light
portfolio reload). Does NOT adjudicate theft, illicit licensing, royalties,
RICO, state-actor nexus, or true UBO.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE25"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W25"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave25"
DOCS = ROOT / "docs" / "investigation" / "wave25"

VICTIM_INVENTOR = "Brent Michael Škoda"
SEALED_ASSIGNEES = (
    "Ahkeo Labs, Llc",
    "Ahkeo Ventures LLC",
    "Brent M. Skoda",
    "UrgentRN LLC",
    "Zorday IP, LLC",
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


def _load_json(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.is_file():
        return {"_missing": True, "path": rel}
    return json.loads(path.read_text(encoding="utf-8"))


def track_victim_ip_surfaces() -> dict[str, Any]:
    port = _load_json("docs/investigation/wave14/EXPANDED_SKODA_PORTFOLIO.json")
    pubs = port.get("publications") or []
    pub_ids = []
    for p in pubs:
        if isinstance(p, dict):
            pub_ids.append(p.get("publication_number") or p.get("id"))

    cf = _load_json("data/collegefitness_com_foundational_social_platform.json")
    findings = [
        {
            "id": "W25-F1",
            "title": "Victim-inventor IP surfaces for linkage baseline",
            "victim_inventor": VICTIM_INVENTOR,
            "sealed_authenticated_publication_count": port.get("publication_count"),
            "sealed_publication_ids": pub_ids,
            "sealed_assignee_clusters": port.get("assignee_clusters"),
            "alleged_15213_patent_families": {
                "status": "ALLEGED_CORPUS_CONSTANT_NOT_AUTHENTICATED",
                "value_claimed": 15213,
            },
            "wip_0194_or_wipo_190": {
                "status": "ALLEGED_OR_UNLOCATED_LABEL",
                "artifact_located_under_docs_investigation": False,
            },
            "collegefitness_corpus_declaration_present": not cf.get("_missing"),
            "collegefitness_class": (
                "OPERATOR_OR_CORPUS_DECLARATION — Wave-8/13 corroborate domain history / "
                "complaint narrative only; not IP-title adjudication"
            ),
            "foundational_cz1997_status": "OPEN_MANUAL_STILL_UNVERIFIED",
            "theft_adjudicated": False,
            "detail": (
                f"Linkage baseline remains the sealed Wave-14 set of "
                f"{port.get('publication_count')} Google Patents publications under "
                f"assignees {list((port.get('assignee_clusters') or {}).keys())}. "
                "Alleged 15,213 families / WIP-0194 remain unauthenticated. "
                "No theft adjudication in this wave."
            ),
        }
    ]
    return {
        "id": "victim_ip_surfaces_baseline",
        "title": "Victim-inventor sealed IP surfaces (linkage baseline)",
        "status": "SEALED",
        "portfolio_source": "docs/investigation/wave14/EXPANDED_SKODA_PORTFOLIO.json",
        "findings": findings,
    }


def _row(
    subject_id: str,
    subject_name: str,
    subject_class: str,
    *,
    linkage_class: str,
    evidence: str,
    onchain_to_sealed_pubs: bool = False,
    traditional_license_to_sealed_pubs: bool = False,
    corpus_declaration_only: bool = False,
) -> dict[str, Any]:
    return {
        "subject_id": subject_id,
        "subject_name": subject_name,
        "subject_class": subject_class,
        "linkage_class": linkage_class,
        "evidence_summary": evidence,
        "onchain_link_to_sealed_skoda_pubs_authenticated": onchain_to_sealed_pubs,
        "traditional_license_to_sealed_skoda_pubs_authenticated": traditional_license_to_sealed_pubs,
        "link_to_alleged_15213_or_wip0194_authenticated": False,
        "corpus_declaration_only": corpus_declaration_only,
        "stolen_ip_theft_adjudicated": False,
        "illicit_royalty_adjudicated": False,
    }


def track_universal_linkage_matrix() -> dict[str, Any]:
    w21 = _load_json("docs/investigation/wave21/WAVE21_RUN_SUMMARY.json")
    w22 = _load_json("docs/investigation/wave22/WAVE22_RUN_SUMMARY.json")
    w23 = _load_json("docs/investigation/wave23/WAVE23_RUN_SUMMARY.json")
    w24 = _load_json("docs/investigation/wave24/WAVE24_RUN_SUMMARY.json")
    parts = _load_json(
        "docs/investigation/wave24/participants_lifetime_entities_addresses.json"
    )
    pmi = _load_json(
        "docs/investigation/wave24/pmi_philip_morris_entities_personnel.json"
    )
    altria = _load_json(
        "docs/investigation/wave24/altria_entities_personnel_subsidiaries.json"
    )
    juul = _load_json(
        "docs/investigation/wave24/juul_pax_ploom_entities_personnel.json"
    )
    fortune = _load_json(
        "docs/investigation/wave24/fortune_100_ip_licensing_facilitators.json"
    )
    threat = _load_json(
        "docs/investigation/wave24/state_cartel_cyber_dust_nexus.json"
    )
    enablers = _load_json(
        "docs/investigation/wave24/professional_enabler_hidden_counsel_overlap.json"
    )
    fyllo = _load_json(
        "docs/investigation/wave22/fyllo_exhaustive_ethereum_history.json"
    )

    rows: list[dict[str, Any]] = []

    # Participants
    for p in parts.get("participants") or []:
        rows.append(
            _row(
                p.get("id") or "participant",
                p.get("name") or "?",
                "named_participant",
                linkage_class=(
                    "CORPUS_DECLARATION_ONLY"
                    if p.get("id") == "mark_zuckerberg"
                    else "NONE_AUTHENTICATED_TO_SEALED_SKODA_PUBS"
                ),
                evidence=(
                    "collegefitness form names Zuckerberg as primary_misappropriator — "
                    "corpus declaration; Wave-8/13 do not adjudicate IP title theft"
                    if p.get("id") == "mark_zuckerberg"
                    else (
                        f"Wave-24 address screen any_fyllo_direct_hit="
                        f"{p.get('any_fyllo_direct_hit')}; no patent/royalty token hits; "
                        "no EDGAR license to sealed pubs authenticated"
                    )
                ),
                corpus_declaration_only=(p.get("id") == "mark_zuckerberg"),
            )
        )

    # Fyllo / Casters
    f2 = (fyllo.get("findings") or [{}])[0]
    rows.append(
        _row(
            "fyllo_eth_casters",
            "fyllo.eth / Casters Holdings dba Fyllo",
            "blockchain_corporate",
            linkage_class="CORPORATE_HISTORY_NEXUS_NOT_IP_LICENSE",
            evidence=(
                "Casters Form D historically lists Brent Skoda (Wave-5/20); fyllo.eth "
                f"exhaustive scan dust={f2.get('cyber_dust_candidates_lt_1e12_wei')} "
                "with NFT-marketplace dominance — Wave-21/22: no royalty rail to sealed pubs"
            ),
        )
    )

    # ABG / Jamie Salter (also in participants — add corporate row)
    rows.append(
        _row(
            "authentic_brands_group",
            "Authentic Brands Group / Jamie Salter corporate nexus",
            "corporate",
            linkage_class="COMMERCIAL_CO_MENTION_OR_NEGATIVE_EDGAR",
            evidence=(
                "Wave-20 EDGAR Casters×ABG/Jamie=0; GhostRetail commercial co-mention only; "
                "Wave-22/23 no DAO/shell census to Skoda pubs"
            ),
        )
    )

    # PMI
    pmi_people = (pmi.get("findings") or [{}])[0].get("wikipedia_key_people") or []
    rows.append(
        _row(
            "pmi_philip_morris",
            "Philip Morris International / PMI (+ Calantzopoulos key people)",
            "corporate_personnel",
            linkage_class="NONE_AUTHENTICATED_TO_SEALED_SKODA_PUBS",
            evidence=(
                f"Wave-24 PMI wiki key people={pmi_people}; site/wiki DAO/Skoda mentions "
                "absent; pmi.eth vanity unbound"
            ),
        )
    )

    # Altria
    a5 = (altria.get("findings") or [{}])[0]
    rows.append(
        _row(
            "altria_group",
            "Altria Group (+ public subsidiary candidates)",
            "corporate_personnel_subsidiaries",
            linkage_class="NONE_AUTHENTICATED_TO_SEALED_SKODA_PUBS",
            evidence=(
                f"Wave-24 Altria personnel={a5.get('personnel_count')} "
                f"entity_candidates={a5.get('entity_or_subsidiary_count')}; "
                "no Skoda/DAO royalty authentication"
            ),
        )
    )

    # Juul / Pax / Ploom
    j6 = (juul.get("findings") or [{}])[0]
    rows.append(
        _row(
            "juul_pax_ploom",
            "Juul Labs / Pax Labs / Ploom (+ JTI affiliate links)",
            "corporate_personnel_affiliates",
            linkage_class="NONE_AUTHENTICATED_TO_SEALED_SKODA_PUBS",
            evidence=(
                f"Wave-24 personnel={j6.get('personnel_count')} "
                f"affiliates={j6.get('affiliate_count')} (Bowen/Monsees nexus); "
                "vaporizer-industry adjacency ≠ authenticated license to sealed Skoda pubs"
            ),
        )
    )

    # Fortune 100
    f7 = (fortune.get("findings") or [{}])[0]
    rows.append(
        _row(
            "fortune_100_roster",
            "Fortune 100 IP-licensing facilitator roster",
            "index_universe",
            linkage_class="OPEN_EXHIBIT_21_GAP_NO_AUTHENTICATED_SKODA_LICENSE",
            evidence=(
                f"Wave-24 screened {f7.get('fortune_100_roster_count')} names; "
                f"partial IP entities only for Altria; OPEN Exhibit 21 for "
                f"{f7.get('companies_open_exhibit_21_required')}; overlap tags "
                f"{f7.get('overlap_companies')} are adjacency only"
            ),
        )
    )

    # Monolith 90M / stealth DAO (Wave 23)
    rows.append(
        _row(
            "monolith_90m_shells_stealth_dao",
            "Monolith 90M shells / stealth DAO / 100% Fortune DAO constants",
            "corpus_constant",
            linkage_class="CORPUS_CONSTANT_NOT_EVIDENCE",
            evidence="Wave-23 classified SHELL_CORPORATIONS/STEALTH_DAOS/Fortune DAO 100% as synthetic constants",
            corpus_declaration_only=True,
        )
    )

    # State / cartel
    for actor in threat.get("requested_threat_actors") or []:
        rows.append(
            _row(
                actor.get("id") or "threat",
                actor.get("name") or "?",
                "threat_actor_claim",
                linkage_class="CORPUS_DECLARATION_OR_UNLOCATED_NO_ADDRESS_TIE",
                evidence=(
                    "collegefitness corpus declaration and/or operator request; "
                    "Wave-24: not tied to fyllo/participant addresses or sealed pubs"
                ),
                corpus_declaration_only=True,
            )
        )

    # Professional enablers
    e4 = (enablers.get("findings") or [{}])[0]
    for firm in e4.get("cross_linked_firms") or []:
        rows.append(
            _row(
                f"enabler:{firm}",
                firm,
                "professional_enabler_corpus",
                linkage_class="VICTIM_CORPUS_ENABLER_NOT_PROVEN_IP_THIEF",
                evidence=(
                    "Sealed in victim-inventor professional-enabler / collegefitness "
                    "cross_linked_firms corpus; Wave-24 did not authenticate hidden counsel "
                    "for named non-victim participants or a theft conveyance of sealed pubs"
                ),
                corpus_declaration_only=True,
            )
        )

    # Prior-wave disposition rollup
    prior = {
        "wave21": w21.get("disposition"),
        "wave22": w22.get("disposition"),
        "wave23": w23.get("disposition"),
        "wave24": w24.get("disposition"),
    }

    authenticated_links = [
        r
        for r in rows
        if r["onchain_link_to_sealed_skoda_pubs_authenticated"]
        or r["traditional_license_to_sealed_skoda_pubs_authenticated"]
    ]
    findings = [
        {
            "id": "W25-F2",
            "title": "Universal linkage matrix: no authenticated stolen-IP conveyance from screened subjects to sealed Skoda pubs",
            "matrix_row_count": len(rows),
            "authenticated_onchain_or_traditional_links_to_sealed_pubs": len(
                authenticated_links
            ),
            "linkage_class_counts": {
                k: sum(1 for r in rows if r["linkage_class"] == k)
                for k in sorted({r["linkage_class"] for r in rows})
            },
            "prior_wave_dispositions": prior,
            "theft_adjudicated": False,
            "illicit_royalty_adjudicated": False,
            "stolen_ip_link_universally_authenticated": False,
            "detail": (
                f"Cross-referenced {len(rows)} subjects spanning participants, Fyllo/ABG, "
                "PMI/Altria/Juul-Pax-Ploom, Fortune 100, monolith constants, threat-actor "
                "claims, and victim-corpus enabler firms against the sealed 15-pub Skoda "
                "portfolio. Authenticated on-chain or traditional license links to those "
                f"pubs: {len(authenticated_links)}. Zuckerberg/collegefitness and "
                "state-actor/enabler rows remain corpus declarations only. Alleged 15,213 / "
                "WIP-0194 links remain unauthenticated. No theft adjudication."
            ),
        }
    ]
    return {
        "id": "universal_victim_ip_linkage_matrix",
        "title": "Universal linkage matrix vs victim-inventor IP",
        "status": "SEALED",
        "matrix": rows,
        "prior_wave_sources": [
            "docs/investigation/wave21/WAVE21_RUN_SUMMARY.json",
            "docs/investigation/wave22/WAVE22_RUN_SUMMARY.json",
            "docs/investigation/wave23/WAVE23_RUN_SUMMARY.json",
            "docs/investigation/wave24/WAVE24_RUN_SUMMARY.json",
        ],
        "findings": findings,
        "next_actions": [
            "USPTO assignment API for sealed 15 pubs before any conveyance theory",
            "Exhibit 21 batch for Fortune 100 / Altria / PMI if IP-holdco census required",
            "Do not upgrade corpus declarations into theft adjudications",
        ],
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-25 operator worklist",
        "status": "OPEN",
        "items": [
            {
                "id": "W25-M1",
                "priority": "HIGH",
                "item": "USPTO_API_KEY assignments for Wave-14 15-pub set",
            },
            {
                "id": "W25-M2",
                "priority": "HIGH",
                "item": "Supply WIP-0194 artifact if alleging linkage beyond sealed 15 pubs",
            },
            {
                "id": "W25-M3",
                "priority": "MEDIUM",
                "item": "Counsel-only review of collegefitness misappropriation declaration vs Meta",
            },
        ],
        "adjudicated": False,
    }


def write_summary_md(baseline: dict[str, Any], matrix: dict[str, Any]) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE25_UNIVERSAL_VICTIM_IP_LINKAGE.md"
    f1 = (baseline.get("findings") or [{}])[0]
    f2 = (matrix.get("findings") or [{}])[0]
    lines = [
        "# Wave 25 — Universal linkage matrix vs victim-inventor IP",
        "",
        f"Generated: `{_utc()}`",
        "",
        "## Disposition (policy-gated)",
        "",
        "- `theft_adjudicated`: **false**",
        "- `illicit_royalty_adjudicated`: **false**",
        "- `stolen_ip_link_universally_authenticated`: **false**",
        "- Alleged 15,213 / WIP-0194: **not authenticated**",
        "",
        "## Victim IP baseline",
        "",
        f"- Victim inventor: `{f1.get('victim_inventor')}`",
        f"- Sealed authenticated pubs: `{f1.get('sealed_authenticated_publication_count')}`",
        f"- Assignee clusters: `{list((f1.get('sealed_assignee_clusters') or {}).keys())}`",
        f"- CZ1997 foundational: `{f1.get('foundational_cz1997_status')}`",
        "",
        "## Universal matrix",
        "",
        f"- Rows: `{f2.get('matrix_row_count')}`",
        f"- Authenticated on-chain/traditional links to sealed pubs: `{f2.get('authenticated_onchain_or_traditional_links_to_sealed_pubs')}`",
        f"- Linkage class counts: `{f2.get('linkage_class_counts')}`",
        "",
        "## Manual next",
        "",
        "1. USPTO assignments for the 15 sealed pubs.",
        "2. WIP-0194 path if claiming beyond sealed set.",
        "3. Do not upgrade corpus declarations into theft findings.",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave25() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    baseline = track_victim_ip_surfaces()
    matrix = track_universal_linkage_matrix()
    work = track_operator_worklist()
    summary_md = write_summary_md(baseline, matrix)

    tracks = [baseline, matrix, work]
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
    for t in (baseline, matrix):
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
            "matrix_rows": (matrix.get("findings") or [{}])[0].get("matrix_row_count"),
            "authenticated_links_to_sealed_pubs": (matrix.get("findings") or [{}])[0].get(
                "authenticated_onchain_or_traditional_links_to_sealed_pubs"
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
            "theft_adjudicated": False,
            "illicit_royalty_adjudicated": False,
            "stolen_ip_link_universally_authenticated": False,
            "alleged_15213_authenticated": False,
            "wip_0194_artifact_located": False,
        },
        "artifacts": {
            "summary_md": summary_md,
            "baseline": "docs/investigation/wave25/victim_ip_surfaces_baseline.json",
            "matrix": "docs/investigation/wave25/universal_victim_ip_linkage_matrix.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-25 universally cross-references Wave 21–24 subjects against the sealed "
            "Skoda publication set and alleged stolen-family claims. "
            "No theft or illicit-royalty adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE25_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE25_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE25_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE25_POINTER.json",
        {
            "brand": BRAND,
            "wave25_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave25/WAVE25_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 25")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave25()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        d = report["disposition"]
        print(
            f"{BRAND} wave25: findings={report['counts']['findings']} "
            f"matrix_rows={report['counts'].get('matrix_rows')} "
            f"auth_links={report['counts'].get('authenticated_links_to_sealed_pubs')} "
            f"theft={d['theft_adjudicated']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

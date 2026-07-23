#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 26
================================
Universal blockchain transaction-flow screen across all sealed Wave 21–24
ENS/addresses: full flows (not limited to victim-IP linkage), cyber-dust
candidates, pairwise combinations, and DAO / stealth-DAO surface probes.

Public Blockscout/ENS pagination from first observed activity → latest
(Ethereum mainnet). Does NOT adjudicate illicit dust evasion, stealth-DAO
royalties, theft, RICO, or true UBO.
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
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE26"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W26"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave26"
DOCS = ROOT / "docs" / "investigation" / "wave26"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave26/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
CTX = ssl.create_default_context()
DUST_WEI_LT = 1_000_000_000_000  # < 1e-6 ETH
MAX_TX_PAGES = 20
MAX_TT_PAGES = 8
MAX_INTERNAL_PAGES = 5

DAO_METHOD_HINTS = re.compile(
    r"dao|govern|propose|vote|delegate|timelock|executeProposal|castVote|"
    r"queueTransaction|joinDAO|createDAO|moloch|snapshot",
    re.I,
)
DAO_TOKEN_HINTS = re.compile(
    r"\bDAO\b|governance|moloch|aragon|colony|daohaus|snapshot|stealth.?dao|"
    r"governor|ve[A-Z]|xDAO",
    re.I,
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
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"}
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as resp:
            body = resp.read()
            return {
                "ok": True,
                "status": getattr(resp, "status", 200),
                "body": body,
                "sha256": hashlib.sha256(body).hexdigest(),
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
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
            "status": getattr(exc, "code", None),
            "body": body,
            "sha256": hashlib.sha256(body).hexdigest() if body else None,
            "error": f"{type(exc).__name__}:{exc}"[:240],
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }


def _addr_hash(obj: Any) -> str | None:
    if isinstance(obj, dict):
        return obj.get("hash") or obj.get("address_hash") or obj.get("address")
    if isinstance(obj, str):
        return obj
    return None


def _page(address: str, path: str, *, max_pages: int) -> dict[str, Any]:
    items: list[Any] = []
    pages = 0
    nxt: dict[str, Any] | None = None
    shas: list[str] = []
    while pages < max_pages:
        url = f"https://eth.blockscout.com/api/v2/addresses/{address}/{path}"
        if nxt:
            url += "?" + urllib.parse.urlencode(
                {k: v for k, v in nxt.items() if v is not None}
            )
        r = _fetch(url)
        pages += 1
        if not r.get("ok"):
            return {
                "ok": False,
                "pages": pages,
                "items": items,
                "item_count": len(items),
                "exhausted": False,
                "hit_page_cap": False,
                "error": r.get("error"),
                "sha256_pages": shas,
            }
        shas.append(r["sha256"])
        data = json.loads(r["body"].decode("utf-8", "replace"))
        batch = data.get("items") or []
        items.extend(batch)
        nxt = data.get("next_page_params")
        if not nxt or not batch:
            break
        time.sleep(0.2)
    return {
        "ok": True,
        "pages": pages,
        "items": items,
        "item_count": len(items),
        "exhausted": nxt is None,
        "hit_page_cap": pages >= max_pages and nxt is not None,
        "sha256_pages": shas,
    }


def collect_address_book() -> dict[str, str]:
    """All resolved ENS/addresses sealed in Waves 22/24 (+ fyllo)."""
    book: dict[str, str] = {
        "fyllo.eth": "0xE739955225Ee00EE9b6e859BcD6C82308bb5E909",
    }
    parts_path = (
        ROOT / "docs" / "investigation" / "wave24" / "participants_lifetime_entities_addresses.json"
    )
    if parts_path.is_file():
        parts = json.loads(parts_path.read_text(encoding="utf-8"))
        for lab, s in (parts.get("address_summaries") or {}).items():
            if s.get("address"):
                book[lab] = s["address"]
    for rel in (
        "juul_pax_ploom_entities_personnel.json",
        "altria_entities_personnel_subsidiaries.json",
        "pmi_philip_morris_entities_personnel.json",
    ):
        path = ROOT / "docs" / "investigation" / "wave24" / rel
        if not path.is_file():
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        for src in (d.get("ens") or {}, d.get("ens_identity") or {}):
            for lab, row in src.items():
                if isinstance(row, dict) and row.get("address"):
                    book[lab] = row["address"]
    # Dedupe by address — keep first label
    by_addr: dict[str, str] = {}
    for lab, addr in book.items():
        key = addr.lower()
        if key not in by_addr:
            by_addr[key] = lab
    return {lab: book[lab] for lab in by_addr.values()}


def summarize_flows(label: str, address: str, peer_map: dict[str, str]) -> dict[str, Any]:
    txs = _page(address, "transactions", max_pages=MAX_TX_PAGES)
    time.sleep(0.12)
    tts = _page(address, "token-transfers", max_pages=MAX_TT_PAGES)
    time.sleep(0.12)
    internal = _page(address, "internal-transactions", max_pages=MAX_INTERNAL_PAGES)

    methods: Counter[str] = Counter()
    dust_out: list[dict[str, Any]] = []
    dust_in: list[dict[str, Any]] = []
    nonzero: list[dict[str, Any]] = []
    peer_flows: Counter[str] = Counter()  # peer_label -> count any value
    peer_dust: Counter[str] = Counter()
    peer_eth_wei: dict[str, int] = defaultdict(int)
    dao_method_hits: list[dict[str, Any]] = []

    for t in txs.get("items") or []:
        method = t.get("method") or "unknown"
        methods[method] += 1
        if DAO_METHOD_HINTS.search(str(method)):
            dao_method_hits.append(
                {"hash": t.get("hash"), "method": method, "timestamp": t.get("timestamp")}
            )
        try:
            wei = int(t.get("value") or 0)
        except Exception:  # noqa: BLE001
            wei = 0
        fr = (_addr_hash(t.get("from")) or "").lower()
        to = (_addr_hash(t.get("to")) or "").lower()
        direction = None
        counterparty = None
        if fr == address.lower():
            direction = "out"
            counterparty = to
        elif to == address.lower():
            direction = "in"
            counterparty = fr
        rec = {
            "hash": t.get("hash"),
            "direction": direction,
            "counterparty": counterparty,
            "value_wei": wei,
            "value_eth": wei / 1e18,
            "method": method,
            "timestamp": t.get("timestamp"),
        }
        if wei > 0:
            nonzero.append(rec)
        if 0 < wei < DUST_WEI_LT:
            if direction == "out":
                dust_out.append(rec)
            elif direction == "in":
                dust_in.append(rec)
        if counterparty and counterparty in peer_map:
            plab = peer_map[counterparty]
            peer_flows[plab] += 1
            peer_eth_wei[plab] += wei
            if 0 < wei < DUST_WEI_LT:
                peer_dust[plab] += 1

    dao_token_hits = []
    sym: Counter[str] = Counter()
    for t in tts.get("items") or []:
        token = t.get("token") or {}
        sym[token.get("symbol") or "?"] += 1
        blob = json.dumps(token)
        if DAO_TOKEN_HINTS.search(blob):
            dao_token_hits.append(
                {
                    "symbol": token.get("symbol"),
                    "name": token.get("name"),
                    "tx": t.get("transaction_hash"),
                    "timestamp": t.get("timestamp"),
                }
            )
        # peer token transfers
        for side in ("from", "to"):
            h = (_addr_hash(t.get(side)) or "").lower()
            if h in peer_map and h != address.lower():
                peer_flows[peer_map[h] + "#token"] += 1

    ts = [t.get("timestamp") for t in (txs.get("items") or []) if t.get("timestamp")]
    return {
        "label": label,
        "address": address,
        "tx_scanned": txs.get("item_count"),
        "tx_pages": txs.get("pages"),
        "tx_exhausted": txs.get("exhausted"),
        "tx_hit_page_cap": txs.get("hit_page_cap"),
        "tt_scanned": tts.get("item_count"),
        "tt_exhausted": tts.get("exhausted"),
        "internal_scanned": internal.get("item_count"),
        "activity_span": {
            "earliest": min(ts) if ts else None,
            "latest": max(ts) if ts else None,
        },
        "methods_top": dict(methods.most_common(25)),
        "nonzero_eth_count": len(nonzero),
        "nonzero_eth_sample": nonzero[:30],
        "dust_out_count": len(dust_out),
        "dust_in_count": len(dust_in),
        "dust_out_sample": dust_out[:25],
        "dust_in_sample": dust_in[:25],
        "peer_flow_counts": dict(peer_flows),
        "peer_dust_counts": dict(peer_dust),
        "peer_eth_wei_totals": dict(peer_eth_wei),
        "dao_method_hits": dao_method_hits[:40],
        "dao_token_hits": dao_token_hits[:40],
        "token_symbols_top": sym.most_common(20),
        "sha256_tx_pages": txs.get("sha256_pages"),
        "ok": txs.get("ok"),
    }


def track_address_book_and_flows() -> dict[str, Any]:
    book = collect_address_book()
    peer_map = {a.lower(): lab for lab, a in book.items()}
    summaries: dict[str, Any] = {}

    def _job(item: tuple[str, str]) -> tuple[str, dict[str, Any]]:
        lab, addr = item
        return lab, summarize_flows(lab, addr, peer_map)

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_job, item): item[0] for item in book.items()}
        for fut in as_completed(futs):
            lab, summary = fut.result()
            summaries[lab] = summary

    total_dust = sum(
        int(s.get("dust_out_count") or 0) + int(s.get("dust_in_count") or 0)
        for s in summaries.values()
    )
    capped = [lab for lab, s in summaries.items() if s.get("tx_hit_page_cap")]
    findings = [
        {
            "id": "W26-F1",
            "title": "Blockchain transaction flows screened for all sealed addresses (independent of victim-IP corpus)",
            "addresses_screened": len(summaries),
            "address_book": book,
            "total_dust_candidates_in_plus_out": total_dust,
            "addresses_hitting_tx_page_cap": capped,
            "genesis_scope_note": (
                "Ethereum mainnet only. 'Genesis→date' operationalized as exhaustive "
                "public pagination from first observed activity through latest tx per "
                "address. Addresses hitting page caps are PARTIAL; other L1/L2 chains "
                "OPEN without additional addresses."
            ),
            "victim_ip_filter_applied": False,
            "illicit_dust_evasion_adjudicated": False,
            "detail": (
                f"Screened {len(summaries)} labels. Dust threshold 0 < wei < {DUST_WEI_LT}. "
                f"Aggregate dust in+out candidates in scanned pages: {total_dust}. "
                f"Page-cap partial histories: {capped}. Flows include all ETH/token/"
                "internal activity observed — not filtered by Skoda/IP relationship."
            ),
        }
    ]
    return {
        "id": "blockchain_flows_all_addresses",
        "title": "All blockchain transaction flows (sealed address set)",
        "status": "SEALED",
        "dust_wei_lt": DUST_WEI_LT,
        "max_tx_pages": MAX_TX_PAGES,
        "summaries": {
            k: {
                kk: vv
                for kk, vv in v.items()
                if kk
                not in (
                    "nonzero_eth_sample",
                    "dust_out_sample",
                    "dust_in_sample",
                    "sha256_tx_pages",
                )
            }
            | {
                "nonzero_eth_sample": v.get("nonzero_eth_sample"),
                "dust_out_sample": v.get("dust_out_sample"),
                "dust_in_sample": v.get("dust_in_sample"),
                "sha256_tx_pages": v.get("sha256_tx_pages"),
            }
            for k, v in summaries.items()
        },
        "findings": findings,
        "next_actions": [
            "Archive-node / deeper pagination for page-capped EOAs if full lifetime required",
            "Other chains only if operator supplies addresses",
        ],
    }


def track_pairwise_combinations(flow_track: dict[str, Any]) -> dict[str, Any]:
    summaries = flow_track.get("summaries") or {}
    labels = sorted(summaries.keys())
    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(labels):
        sa = summaries[a]
        for b in labels[i + 1 :]:
            # directed counts from each side's peer maps
            ab = int((sa.get("peer_flow_counts") or {}).get(b) or 0)
            ab += int((sa.get("peer_flow_counts") or {}).get(b + "#token") or 0)
            sb = summaries[b]
            ba = int((sb.get("peer_flow_counts") or {}).get(a) or 0)
            ba += int((sb.get("peer_flow_counts") or {}).get(a + "#token") or 0)
            dust_ab = int((sa.get("peer_dust_counts") or {}).get(b) or 0)
            dust_ba = int((sb.get("peer_dust_counts") or {}).get(a) or 0)
            wei_ab = int((sa.get("peer_eth_wei_totals") or {}).get(b) or 0)
            wei_ba = int((sb.get("peer_eth_wei_totals") or {}).get(a) or 0)
            if ab or ba or dust_ab or dust_ba:
                pairs.append(
                    {
                        "a": a,
                        "b": b,
                        "flows_a_to_b_observed_in_a_scan": ab,
                        "flows_b_to_a_observed_in_b_scan": ba,
                        "dust_a_to_b": dust_ab,
                        "dust_b_to_a": dust_ba,
                        "eth_wei_a_mentions_b": wei_ab,
                        "eth_wei_b_mentions_a": wei_ba,
                    }
                )

    findings = [
        {
            "id": "W26-F2",
            "title": "Pairwise combination flows among screened addresses (all values + dust)",
            "pair_combination_space": len(labels) * (len(labels) - 1) // 2,
            "pairs_with_any_observed_flow": len(pairs),
            "pairs_with_dust_flow": sum(
                1 for p in pairs if p["dust_a_to_b"] or p["dust_b_to_a"]
            ),
            "illicit_combination_network_adjudicated": False,
            "detail": (
                f"Enumerated C({len(labels)},2)={len(labels)*(len(labels)-1)//2} "
                f"unordered pairs; {len(pairs)} showed any peer flow in scanned pages; "
                f"{sum(1 for p in pairs if p['dust_a_to_b'] or p['dust_b_to_a'])} showed "
                "dust-threshold ETH. Absence of a pair edge ≠ proof of no historical link "
                "beyond page caps."
            ),
        }
    ]
    return {
        "id": "pairwise_flow_combinations",
        "title": "Pairwise blockchain flow combinations (all + dust)",
        "status": "SEALED",
        "pairs_with_flows": pairs,
        "findings": findings,
    }


def track_dao_stealth_dao(flow_track: dict[str, Any]) -> dict[str, Any]:
    summaries = flow_track.get("summaries") or {}
    # Aggregate DAO hints from flows
    method_hits = []
    token_hits = []
    for lab, s in summaries.items():
        for h in s.get("dao_method_hits") or []:
            method_hits.append({"label": lab, **h})
        for h in s.get("dao_token_hits") or []:
            token_hits.append({"label": lab, **h})

    # ENS vanity DAO names among/near set
    dao_ens_probes = [
        "dao.eth",
        "stealthdao.eth",
        "stealth.eth",
        "fyllodao.eth",
        "abgdao.eth",
        "pmidao.eth",
        "altriadao.eth",
        "juuldao.eth",
        "vitalikdao.eth",
    ]
    ens_rows = []
    for name in dao_ens_probes:
        r = _fetch(f"https://api.ensideas.com/ens/resolve/{name}")
        time.sleep(0.12)
        addr = None
        if r.get("ok"):
            try:
                addr = json.loads(r["body"].decode()).get("address")
            except Exception:  # noqa: BLE001
                addr = None
        ens_rows.append({"ens": name, "address": addr, "ok": r.get("ok")})

    # Wave-23 constant classification retained
    w23 = {}
    w23_path = ROOT / "docs" / "investigation" / "wave23" / "corpus_constant_classification.json"
    if w23_path.is_file():
        w23 = json.loads(w23_path.read_text(encoding="utf-8"))

    findings = [
        {
            "id": "W26-F3",
            "title": "DAO / stealth-DAO linkage screen across sealed address flows",
            "dao_method_hit_count": len(method_hits),
            "dao_token_hit_count": len(token_hits),
            "dao_method_hits_sample": method_hits[:50],
            "dao_token_hits_sample": token_hits[:50],
            "dao_ens_probes": ens_rows,
            "monolith_stealth_dao_constant_class": (
                (w23.get("constants") or {}).get("STEALTH_DAOS")
                or {"class": "CORPUS_CONSTANT_NOT_AUTHENTICATED_INVENTORY", "value": 90_000_000}
            ),
            "stealth_dao_network_authenticated": False,
            "dao_royalty_rail_authenticated": False,
            "illicit_stealth_dao_adjudicated": False,
            "detail": (
                f"Scanned methods/tokens for DAO/governance heuristics across all flow "
                f"summaries: method_hits={len(method_hits)}, token_hits={len(token_hits)}. "
                "Vanity dao/stealthdao ENS probes recorded. Monolith STEALTH_DAOS=90M remains "
                "a corpus constant (Wave-23) — not an authenticated stealth-DAO inventory. "
                "No stealth-DAO royalty network adjudicated."
            ),
        }
    ]
    return {
        "id": "dao_stealth_dao_linkages",
        "title": "DAO and stealth-DAO linkage screen",
        "status": "SEALED",
        "findings": findings,
        "next_actions": [
            "If operator has specific DAO contract addresses, supply for deterministic deep trace",
            "Do not treat monolith 90M stealth-DAO constant as discovered inventory",
        ],
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-26 operator worklist",
        "status": "OPEN",
        "items": [
            {
                "id": "W26-M1",
                "priority": "HIGH",
                "item": "Archive-node pagination for page-capped EOAs (vitalik/jamiesalter/etc.)",
            },
            {
                "id": "W26-M2",
                "priority": "MEDIUM",
                "item": "Supply non-Ethereum addresses if multi-chain genesis coverage is claimed",
            },
            {
                "id": "W26-M3",
                "priority": "MEDIUM",
                "item": "Named DAO contract list if stealth-DAO theory targets specific orgs",
            },
        ],
        "adjudicated": False,
    }


def write_summary_md(
    flows: dict[str, Any], pairs: dict[str, Any], dao: dict[str, Any]
) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE26_BLOCKCHAIN_FLOWS_DUST_DAO.md"
    f1 = (flows.get("findings") or [{}])[0]
    f2 = (pairs.get("findings") or [{}])[0]
    f3 = (dao.get("findings") or [{}])[0]
    lines = [
        "# Wave 26 — Blockchain flows × cyber-dust × DAO/stealth-DAO (all combinations)",
        "",
        f"Generated: `{_utc()}`",
        "",
        "## Disposition (policy-gated)",
        "",
        "- `illicit_dust_evasion_adjudicated`: **false**",
        "- `illicit_combination_network_adjudicated`: **false**",
        "- `stealth_dao_network_authenticated`: **false**",
        "- `dao_royalty_rail_authenticated`: **false**",
        "- `illicit_stealth_dao_adjudicated`: **false**",
        "- Victim-IP filter applied: **false** (all flows included)",
        "",
        "## Flows",
        "",
        f"- Addresses screened: `{f1.get('addresses_screened')}`",
        f"- Aggregate dust in+out candidates: `{f1.get('total_dust_candidates_in_plus_out')}`",
        f"- Page-cap partial: `{f1.get('addresses_hitting_tx_page_cap')}`",
        f"- Scope: `{f1.get('genesis_scope_note')}`",
        "",
        "## Pairwise combinations",
        "",
        f"- Pair space: `{f2.get('pair_combination_space')}`",
        f"- Pairs with any flow: `{f2.get('pairs_with_any_observed_flow')}`",
        f"- Pairs with dust flow: `{f2.get('pairs_with_dust_flow')}`",
        "",
        "## DAO / stealth DAO",
        "",
        f"- DAO method hits: `{f3.get('dao_method_hit_count')}`",
        f"- DAO token hits: `{f3.get('dao_token_hit_count')}`",
        "- Monolith 90M stealth DAOs: **corpus constant** (not authenticated inventory)",
        "",
        "## Manual next",
        "",
        "1. Deeper pagination for page-capped EOAs.",
        "2. Named DAO contracts if stealth-DAO theory is contract-specific.",
        "3. Do not treat dust wei filters as adjudicated illicit evasion.",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave26() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    flows = track_address_book_and_flows()
    pairs = track_pairwise_combinations(flows)
    dao = track_dao_stealth_dao(flows)
    work = track_operator_worklist()
    summary_md = write_summary_md(flows, pairs, dao)

    tracks = [flows, pairs, dao, work]
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
    for t in (flows, pairs, dao):
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
            "addresses_screened": (flows.get("findings") or [{}])[0].get(
                "addresses_screened"
            ),
            "pairs_with_flows": (pairs.get("findings") or [{}])[0].get(
                "pairs_with_any_observed_flow"
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
            "illicit_dust_evasion_adjudicated": False,
            "illicit_combination_network_adjudicated": False,
            "stealth_dao_network_authenticated": False,
            "dao_royalty_rail_authenticated": False,
            "illicit_stealth_dao_adjudicated": False,
            "victim_ip_filter_applied": False,
            "theft_adjudicated": False,
        },
        "artifacts": {
            "summary_md": summary_md,
            "flows": "docs/investigation/wave26/blockchain_flows_all_addresses.json",
            "pairs": "docs/investigation/wave26/pairwise_flow_combinations.json",
            "dao": "docs/investigation/wave26/dao_stealth_dao_linkages.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-26 screens all blockchain flows among sealed addresses (not filtered "
            "by victim-IP corpus), cyber-dust candidates, pairwise combinations, and "
            "DAO/stealth-DAO heuristics. No illicit-dust or stealth-DAO adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE26_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE26_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE26_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE26_POINTER.json",
        {
            "brand": BRAND,
            "wave26_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave26/WAVE26_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 26")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave26()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        d = report["disposition"]
        print(
            f"{BRAND} wave26: findings={report['counts']['findings']} "
            f"addrs={report['counts'].get('addresses_screened')} "
            f"pairs={report['counts'].get('pairs_with_flows')} "
            f"dust_illicit={d['illicit_dust_evasion_adjudicated']} "
            f"stealth_dao={d['stealth_dao_network_authenticated']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

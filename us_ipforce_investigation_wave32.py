#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 32
================================
Systematically deepen and expand analysis to follow:

  • ALL money flows (ETH native, internal, ERC-20/721/1155) across the
    sealed address set — directed graphs, aggregates, top counterparties,
    sealed-set edges, and external hubs.
  • ALL intellectual-property flows — sealed Wave-14 publication set,
    assignee clusters, on-chain IP/royalty/wrapped-RaP heuristics, and
    traditional (assignment/licensing) flow status retained from Waves 14/25.

Cross-matrix: money ↔ IP nexus. Does NOT adjudicate theft, illicit royalties,
stolen-IP conveyance, RICO, or true UBO.
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
VERSION = "2026.7.23-INVESTIGATION-WAVE32"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W32"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave32"
DOCS = ROOT / "docs" / "investigation" / "wave32"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave32/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
CTX = ssl.create_default_context()

MAX_TX_PAGES = 25
MAX_INTERNAL_PAGES = 12
MAX_TT_PAGES = 12

RE_IP = re.compile(
    r"\bpatent\b|\bwipo\b|\buspto\b|intellectual.?property|\bIP[-_ ]?NFT\b|"
    r"skoda|ahkeo|zorday|urgentrn|royalt|eip-?2981|license.?fee|"
    r"\bRaP\b|\bwRaP\b|wrap(?:ped)?[-_ ]?RaP",
    re.I,
)
RE_MONEY_METHOD = re.compile(
    r"transfer|transferFrom|swap|exactInput|exactOutput|deposit|withdraw|"
    r"bridge|send|multicall|execute|fulfill|matchOrders|atomicMatch",
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


def _page(
    address: str,
    path: str,
    *,
    max_pages: int,
    query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    items: list[Any] = []
    pages = 0
    nxt: dict[str, Any] | None = None
    shas: list[str] = []
    base_q = {k: v for k, v in (query or {}).items() if v is not None}
    while pages < max_pages:
        params = dict(base_q)
        if nxt:
            params.update({k: v for k, v in nxt.items() if v is not None})
        url = f"https://eth.blockscout.com/api/v2/addresses/{address}/{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
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
                "sha256_pages": shas,
                "error": r.get("error"),
            }
        shas.append(r["sha256"])
        data = json.loads(r["body"].decode("utf-8", "replace"))
        batch = data.get("items") or []
        items.extend(batch)
        nxt = data.get("next_page_params")
        if not nxt or not batch:
            break
        time.sleep(0.14)
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
    book: dict[str, str] = {}
    for rel in (
        "docs/investigation/wave31/sub_wei_sub_satoshi_cyberdust_full_update.json",
        "docs/investigation/wave26/blockchain_flows_all_addresses.json",
        "docs/investigation/wave27/wrapped_fractional_ip_royalty_token_flows.json",
    ):
        path = ROOT / rel
        if not path.is_file():
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        for f in d.get("findings") or []:
            for lab, addr in (f.get("address_book") or {}).items():
                if addr:
                    book[lab] = addr
        for lab, addr in (d.get("address_book") or {}).items():
            if addr:
                book[lab] = addr
    by_addr: dict[str, str] = {}
    for lab, addr in book.items():
        key = addr.lower()
        if key not in by_addr:
            by_addr[key] = lab
    return {lab: book[lab] for lab in by_addr.values()}


def load_sealed_publications() -> list[dict[str, Any]]:
    path = ROOT / "docs" / "investigation" / "wave14" / "EXPANDED_SKODA_PORTFOLIO.json"
    if not path.is_file():
        return []
    port = json.loads(path.read_text(encoding="utf-8"))
    pubs = []
    for p in port.get("publications") or []:
        if not isinstance(p, dict):
            continue
        pid = p.get("publication") or p.get("publication_number") or p.get("id")
        if not pid:
            continue
        pubs.append(
            {
                "publication": pid,
                "title": p.get("title"),
                "assignee_field": p.get("assignee_field"),
                "google_patents_url": p.get("google_patents_url"),
                "inventor_query": p.get("inventor_query"),
            }
        )
    return pubs


def follow_money_for_address(
    label: str, address: str, peer_map: dict[str, str]
) -> dict[str, Any]:
    txs = _page(address, "transactions", max_pages=MAX_TX_PAGES)
    time.sleep(0.1)
    internal = _page(address, "internal-transactions", max_pages=MAX_INTERNAL_PAGES)
    time.sleep(0.1)
    tts = _page(address, "token-transfers", max_pages=MAX_TT_PAGES)

    eth_in_wei = 0
    eth_out_wei = 0
    eth_in_count = 0
    eth_out_count = 0
    counterparty_eth: dict[str, dict[str, int]] = defaultdict(
        lambda: {"in_wei": 0, "out_wei": 0, "in_n": 0, "out_n": 0}
    )
    sealed_eth: dict[str, dict[str, int]] = defaultdict(
        lambda: {"in_wei": 0, "out_wei": 0, "in_n": 0, "out_n": 0}
    )
    methods: Counter[str] = Counter()
    money_method_hits = 0
    samples_out: list[dict[str, Any]] = []
    samples_in: list[dict[str, Any]] = []

    for t in txs.get("items") or []:
        method = str(t.get("method") or "unknown")
        methods[method] += 1
        if RE_MONEY_METHOD.search(method):
            money_method_hits += 1
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
            if wei > 0:
                eth_out_wei += wei
                eth_out_count += 1
        elif to == address.lower():
            direction = "in"
            counterparty = fr
            if wei > 0:
                eth_in_wei += wei
                eth_in_count += 1
        if counterparty and wei > 0:
            bucket = counterparty_eth[counterparty]
            if direction == "in":
                bucket["in_wei"] += wei
                bucket["in_n"] += 1
            else:
                bucket["out_wei"] += wei
                bucket["out_n"] += 1
            if counterparty in peer_map:
                sb = sealed_eth[peer_map[counterparty]]
                if direction == "in":
                    sb["in_wei"] += wei
                    sb["in_n"] += 1
                else:
                    sb["out_wei"] += wei
                    sb["out_n"] += 1
            rec = {
                "hash": t.get("hash"),
                "direction": direction,
                "counterparty": counterparty,
                "value_wei": wei,
                "value_eth": wei / 1e18,
                "method": method,
                "timestamp": t.get("timestamp"),
                "sealed_peer": peer_map.get(counterparty),
            }
            if direction == "out" and len(samples_out) < 20:
                samples_out.append(rec)
            if direction == "in" and len(samples_in) < 20:
                samples_in.append(rec)

    # Internal ETH value flows
    internal_in_wei = 0
    internal_out_wei = 0
    for t in internal.get("items") or []:
        try:
            wei = int(t.get("value") or 0)
        except Exception:  # noqa: BLE001
            wei = 0
        if wei <= 0:
            continue
        fr = (_addr_hash(t.get("from")) or "").lower()
        to = (_addr_hash(t.get("to")) or "").lower()
        if fr == address.lower():
            internal_out_wei += wei
        elif to == address.lower():
            internal_in_wei += wei

    # Token money flows
    token_syms: Counter[str] = Counter()
    token_counterparties: Counter[str] = Counter()
    sealed_token: Counter[str] = Counter()
    ip_token_hits: list[dict[str, Any]] = []
    ip_token_hit_count = 0
    token_transfer_count = 0
    for t in tts.get("items") or []:
        token_transfer_count += 1
        token = t.get("token") or {}
        sym = token.get("symbol") or "?"
        token_syms[sym] += 1
        blob = " ".join(
            str(x)
            for x in (token.get("symbol"), token.get("name"), token.get("type"))
            if x
        )
        if RE_IP.search(blob):
            ip_token_hit_count += 1
            if len(ip_token_hits) < 40:
                ip_token_hits.append(
                    {
                        "symbol": token.get("symbol"),
                        "name": token.get("name"),
                        "type": token.get("type"),
                        "token_address": token.get("address_hash")
                        or token.get("address"),
                        "tx": t.get("transaction_hash"),
                        "timestamp": t.get("timestamp"),
                    }
                )
        for side in ("from", "to"):
            h = (_addr_hash(t.get(side)) or "").lower()
            if not h or h == address.lower():
                continue
            token_counterparties[h] += 1
            if h in peer_map:
                sealed_token[peer_map[h]] += 1

    # Top external counterparties by absolute ETH volume
    top_cp = sorted(
        counterparty_eth.items(),
        key=lambda kv: -(kv[1]["in_wei"] + kv[1]["out_wei"]),
    )[:25]
    top_external = [
        {
            "address": addr,
            "sealed_label": peer_map.get(addr),
            **vals,
            "total_wei": vals["in_wei"] + vals["out_wei"],
            "total_eth": (vals["in_wei"] + vals["out_wei"]) / 1e18,
        }
        for addr, vals in top_cp
    ]

    ts = [t.get("timestamp") for t in (txs.get("items") or []) if t.get("timestamp")]
    return {
        "label": label,
        "address": address,
        "tx_scanned": txs.get("item_count"),
        "tx_hit_page_cap": txs.get("hit_page_cap"),
        "internal_scanned": internal.get("item_count"),
        "tt_scanned": tts.get("item_count"),
        "tt_hit_page_cap": tts.get("hit_page_cap"),
        "activity_span": {
            "earliest": min(ts) if ts else None,
            "latest": max(ts) if ts else None,
        },
        "eth_flows": {
            "in_wei": eth_in_wei,
            "out_wei": eth_out_wei,
            "in_eth": eth_in_wei / 1e18,
            "out_eth": eth_out_wei / 1e18,
            "in_count": eth_in_count,
            "out_count": eth_out_count,
            "internal_in_wei": internal_in_wei,
            "internal_out_wei": internal_out_wei,
            "net_external_wei": eth_in_wei - eth_out_wei,
        },
        "money_method_hits": money_method_hits,
        "methods_top": methods.most_common(20),
        "sealed_eth_peers": {k: dict(v) for k, v in sealed_eth.items()},
        "sealed_token_peer_counts": dict(sealed_token),
        "top_counterparties_by_eth": top_external,
        "token_transfer_count": token_transfer_count,
        "token_symbols_top": token_syms.most_common(20),
        "ip_linked_token_hits": ip_token_hits,
        "ip_linked_token_hit_count": ip_token_hit_count,
        "samples_in": samples_in,
        "samples_out": samples_out,
        "sha256_pages": {
            "tx": txs.get("sha256_pages"),
            "internal": internal.get("sha256_pages"),
            "tt": tts.get("sha256_pages"),
        },
        "ok": txs.get("ok"),
    }


def track_all_money_flows() -> dict[str, Any]:
    book = collect_address_book()
    peer_map = {a.lower(): lab for lab, a in book.items()}
    screens: dict[str, Any] = {}

    def _job(item: tuple[str, str]) -> tuple[str, dict[str, Any]]:
        return item[0], follow_money_for_address(item[0], item[1], peer_map)

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_job, item): item[0] for item in book.items()}
        for fut in as_completed(futs):
            lab, summary = fut.result()
            screens[lab] = summary

    total_in = sum(int((s.get("eth_flows") or {}).get("in_wei") or 0) for s in screens.values())
    total_out = sum(
        int((s.get("eth_flows") or {}).get("out_wei") or 0) for s in screens.values()
    )
    total_tt = sum(int(s.get("token_transfer_count") or 0) for s in screens.values())
    sealed_edges = []
    labels = sorted(screens.keys())
    for i, a in enumerate(labels):
        sa = screens[a]
        peers = sa.get("sealed_eth_peers") or {}
        tok = sa.get("sealed_token_peer_counts") or {}
        for b in labels[i + 1 :]:
            ab = peers.get(b) or {}
            ba = (screens[b].get("sealed_eth_peers") or {}).get(a) or {}
            tab = int(tok.get(b) or 0)
            tba = int((screens[b].get("sealed_token_peer_counts") or {}).get(a) or 0)
            if ab or ba or tab or tba:
                sealed_edges.append(
                    {
                        "a": a,
                        "b": b,
                        "eth_a_perspective": ab,
                        "eth_b_perspective": ba,
                        "token_transfers_a_to_b_side": tab,
                        "token_transfers_b_to_a_side": tba,
                    }
                )

    capped = [
        lab
        for lab, s in screens.items()
        if s.get("tx_hit_page_cap") or s.get("tt_hit_page_cap")
    ]
    findings = [
        {
            "id": "W32-F1",
            "title": "All money flows followed across sealed addresses (ETH + internal + tokens)",
            "addresses_screened": len(screens),
            "address_book": book,
            "aggregate_eth_in_wei": total_in,
            "aggregate_eth_out_wei": total_out,
            "aggregate_eth_in_eth": total_in / 1e18,
            "aggregate_eth_out_eth": total_out / 1e18,
            "aggregate_token_transfers": total_tt,
            "sealed_set_money_edges": sealed_edges,
            "sealed_set_money_edge_count": len(sealed_edges),
            "pair_space": len(labels) * (len(labels) - 1) // 2,
            "addresses_hitting_page_cap": capped,
            "illicit_money_flow_adjudicated": False,
            "detail": (
                f"Followed money flows for {len(screens)} labels. Aggregate ETH "
                f"in={total_in/1e18:.6f} / out={total_out/1e18:.6f} (scanned pages). "
                f"Token transfers scanned={total_tt}. Sealed-set money edges="
                f"{len(sealed_edges)} / pair space "
                f"{len(labels)*(len(labels)-1)//2}. Not an illicit-flow adjudication."
            ),
        }
    ]
    return {
        "id": "all_money_flows",
        "title": "All money flows (sealed address set)",
        "status": "SEALED",
        "screens": screens,
        "findings": findings,
        "next_actions": [
            "Archive-node uncapped history for page-capped EOAs",
            "Supply non-ETH chain addresses if multi-chain money theories persist",
        ],
    }


def track_all_ip_flows(money: dict[str, Any]) -> dict[str, Any]:
    pubs = load_sealed_publications()
    assignee_clusters: dict[str, list[str]] = defaultdict(list)
    for p in pubs:
        assignee_clusters[p.get("assignee_field") or "UNKNOWN"].append(p["publication"])

    # Traditional IP flow status from sealed priors
    w25_disp = {}
    w14_note = None
    p25 = ROOT / "docs" / "investigation" / "wave25" / "WAVE25_RUN_SUMMARY.json"
    if p25.is_file():
        w25_disp = json.loads(p25.read_text(encoding="utf-8")).get("disposition") or {}
    port_path = ROOT / "docs" / "investigation" / "wave14" / "EXPANDED_SKODA_PORTFOLIO.json"
    if port_path.is_file():
        w14_note = json.loads(port_path.read_text(encoding="utf-8")).get("note")

    # On-chain IP-linked token hits from money screens
    onchain_ip_by_label: dict[str, Any] = {}
    total_ip_token_hits = 0
    pub_id_hits = 0
    pub_ids = [p["publication"] for p in pubs]
    screens = money.get("screens") or {}
    for lab, s in screens.items():
        hits = s.get("ip_linked_token_hits") or []
        # Also scan samples / symbols for sealed pub numbers
        blob = json.dumps(s.get("token_symbols_top") or []) + json.dumps(hits)
        matched_pubs = []
        for pid in pub_ids:
            norm = pid.replace("-", "").lower()
            if norm and norm in blob.replace("-", "").lower():
                matched_pubs.append(pid)
                pub_id_hits += 1
        onchain_ip_by_label[lab] = {
            "ip_linked_token_hit_count": s.get("ip_linked_token_hit_count")
            or len(hits),
            "ip_linked_token_samples": hits[:15],
            "sealed_pub_id_matches_in_token_metadata": matched_pubs,
        }
        total_ip_token_hits += int(
            s.get("ip_linked_token_hit_count") or len(hits)
        )

    # IP flow graph (traditional) — nodes = pubs + assignees; edges = assignee ownership
    ip_nodes = []
    ip_edges = []
    for p in pubs:
        ip_nodes.append({"id": f"pub:{p['publication']}", "kind": "publication", **p})
        asg = p.get("assignee_field") or "UNKNOWN"
        ip_edges.append(
            {
                "from": f"assignee:{asg}",
                "to": f"pub:{p['publication']}",
                "relation": "assignee_of_record_on_publication_metadata",
                "authenticated_assignment_chain": False,
            }
        )
    for asg, plist in assignee_clusters.items():
        ip_nodes.append(
            {
                "id": f"assignee:{asg}",
                "kind": "assignee_cluster",
                "publications": plist,
                "count": len(plist),
            }
        )

    # Alleged corpus constants (not authenticated inventories)
    alleged = {
        "patent_families_15213": {
            "status": "ALLEGED_CORPUS_CONSTANT_NOT_AUTHENTICATED",
            "value_claimed": 15213,
        },
        "wip_0194": {"status": "UNLOCATED_OR_UNAUTHENTICATED", "located": False},
    }

    findings = [
        {
            "id": "W32-F2",
            "title": "All intellectual-property flows followed (sealed pubs + on-chain IP heuristics)",
            "sealed_publication_count": len(pubs),
            "assignee_clusters": {k: v for k, v in assignee_clusters.items()},
            "traditional_ip_flow_status": {
                "uspto_assignment_chain_authenticated": False,
                "licensing_to_screened_subjects_authenticated": False,
                "wave25_disposition_retained": w25_disp,
                "wave14_note": w14_note,
            },
            "onchain_ip_linked_token_hits_total": total_ip_token_hits,
            "sealed_pub_id_token_metadata_hits_total": pub_id_hits,
            "onchain_ip_by_label": onchain_ip_by_label,
            "alleged_corpus_constants": alleged,
            "ip_flow_graph": {
                "nodes": ip_nodes,
                "edges": ip_edges,
                "edge_meaning": (
                    "Metadata assignee→publication edges only — NOT authenticated "
                    "USPTO assignment conveyances"
                ),
            },
            "theft_adjudicated": False,
            "illicit_royalty_adjudicated": False,
            "stolen_ip_conveyance_authenticated": False,
            "detail": (
                f"IP flow baseline = {len(pubs)} sealed pubs across "
                f"{len(assignee_clusters)} assignee clusters. On-chain IP-heuristic "
                f"token hits across money screens={total_ip_token_hits}; sealed "
                f"pub-number matches in token metadata={pub_id_hits}. USPTO "
                "assignment chains remain unauthenticated. No theft adjudication."
            ),
        }
    ]
    return {
        "id": "all_intellectual_property_flows",
        "title": "All intellectual-property flows",
        "status": "SEALED",
        "publications": pubs,
        "findings": findings,
        "next_actions": [
            "USPTO assignment extract for all 15 sealed pubs",
            "Do not treat WETH/marketplace token noise as IP royalty rails",
        ],
    }


def track_money_ip_nexus(
    money: dict[str, Any], ip: dict[str, Any]
) -> dict[str, Any]:
    screens = money.get("screens") or {}
    ip_f = (ip.get("findings") or [{}])[0]
    onchain = ip_f.get("onchain_ip_by_label") or {}
    sealed_edges = (money.get("findings") or [{}])[0].get("sealed_set_money_edges") or []

    nexus_rows = []
    for lab, s in sorted(screens.items()):
        oc = onchain.get(lab) or {}
        sealed_eth_peers = list((s.get("sealed_eth_peers") or {}).keys())
        nexus_rows.append(
            {
                "label": lab,
                "address": s.get("address"),
                "eth_in_eth": (s.get("eth_flows") or {}).get("in_eth"),
                "eth_out_eth": (s.get("eth_flows") or {}).get("out_eth"),
                "token_transfers": s.get("token_transfer_count"),
                "sealed_eth_peers": sealed_eth_peers,
                "ip_linked_token_hits": oc.get("ip_linked_token_hit_count") or 0,
                "sealed_pub_metadata_matches": oc.get(
                    "sealed_pub_id_matches_in_token_metadata"
                )
                or [],
                "money_to_sealed_ip_authenticated": False,
                "ip_royalty_rail_authenticated": False,
            }
        )

    any_pub_match = any(r["sealed_pub_metadata_matches"] for r in nexus_rows)
    any_ip_token = any(r["ip_linked_token_hits"] > 0 for r in nexus_rows)

    findings = [
        {
            "id": "W32-F3",
            "title": "Money ↔ intellectual-property nexus matrix (full expansion)",
            "nexus_rows": nexus_rows,
            "sealed_money_edges_among_addresses": len(sealed_edges),
            "any_sealed_pub_metadata_match_on_money_screens": any_pub_match,
            "any_ip_heuristic_token_hit": any_ip_token,
            "authenticated_money_flow_to_sealed_ip": False,
            "authenticated_ip_royalty_or_license_payment_rail": False,
            "theft_adjudicated": False,
            "illicit_royalty_adjudicated": False,
            "detail": (
                f"Cross-matrix for {len(nexus_rows)} labels. Sealed-set money edges="
                f"{len(sealed_edges)}. Sealed-pub metadata matches on money screens="
                f"{any_pub_match}; IP-heuristic token hits present={any_ip_token}. "
                "No authenticated money→sealed-IP royalty/license rail."
            ),
        }
    ]
    return {
        "id": "money_ip_nexus_matrix",
        "title": "Money ↔ IP nexus matrix",
        "status": "SEALED",
        "nexus_rows": nexus_rows,
        "findings": findings,
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-32 operator worklist",
        "status": "OPEN",
        "items": [
            {
                "id": "W32-M1",
                "priority": "IMMEDIATE",
                "item": "USPTO assignments for all 15 sealed pubs (gates IP-flow charging theories)",
            },
            {
                "id": "W32-M2",
                "priority": "HIGH",
                "item": "Archive-node uncapped money-flow pagination for page-capped EOAs",
            },
            {
                "id": "W32-M3",
                "priority": "HIGH",
                "item": (
                    "Do not equate marketplace/WETH flows with IP royalty or stolen-IP monetization"
                ),
            },
            {
                "id": "W32-M4",
                "priority": "MEDIUM",
                "item": "Supply non-ETH chain addresses if multi-chain money/IP theories persist",
            },
        ],
        "adjudicated": False,
    }


def write_summary_md(
    money: dict[str, Any], ip: dict[str, Any], nexus: dict[str, Any]
) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE32_MONEY_AND_IP_FLOWS.md"
    f1 = (money.get("findings") or [{}])[0]
    f2 = (ip.get("findings") or [{}])[0]
    f3 = (nexus.get("findings") or [{}])[0]
    lines = [
        "# Wave 32 — All money flows × all intellectual-property flows",
        "",
        f"Generated: `{_utc()}`",
        "",
        "## Disposition (policy-gated)",
        "",
        "- `illicit_money_flow_adjudicated`: **false**",
        "- `authenticated_money_flow_to_sealed_ip`: **false**",
        "- `authenticated_ip_royalty_or_license_payment_rail`: **false**",
        "- `theft_adjudicated`: **false**",
        "- `illicit_royalty_adjudicated`: **false**",
        "- `stolen_ip_conveyance_authenticated`: **false**",
        "",
        "## Money flows",
        "",
        f"- Addresses screened: `{f1.get('addresses_screened')}`",
        f"- Aggregate ETH in / out: `{f1.get('aggregate_eth_in_eth')}` / `{f1.get('aggregate_eth_out_eth')}`",
        f"- Token transfers scanned: `{f1.get('aggregate_token_transfers')}`",
        f"- Sealed-set money edges: `{f1.get('sealed_set_money_edge_count')}` / pair space `{f1.get('pair_space')}`",
        f"- Page-cap: `{f1.get('addresses_hitting_page_cap')}`",
        "",
        "## Intellectual-property flows",
        "",
        f"- Sealed publications: `{f2.get('sealed_publication_count')}`",
        f"- Assignee clusters: `{list((f2.get('assignee_clusters') or {}).keys())}`",
        f"- On-chain IP-heuristic token hits: `{f2.get('onchain_ip_linked_token_hits_total')}`",
        f"- Sealed pub-id metadata hits: `{f2.get('sealed_pub_id_token_metadata_hits_total')}`",
        f"- USPTO assignment chain authenticated: **false**",
        "",
        "## Money ↔ IP nexus",
        "",
        f"- Any sealed-pub metadata match on money screens: `{f3.get('any_sealed_pub_metadata_match_on_money_screens')}`",
        f"- Any IP-heuristic token hit: `{f3.get('any_ip_heuristic_token_hit')}`",
        f"- Authenticated money→sealed-IP rail: **false**",
        "",
        "## Manual next",
        "",
        "1. USPTO assignments for 15 sealed pubs.",
        "2. Uncap page-capped EOAs for exhaustive money graphs.",
        "3. Do not treat WETH/marketplace activity as IP royalty.",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave32() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    money = track_all_money_flows()
    ip = track_all_ip_flows(money)
    nexus = track_money_ip_nexus(money, ip)
    work = track_operator_worklist()
    summary_md = write_summary_md(money, ip, nexus)

    # Slim money screens for docs (drop heavy samples in docs copy)
    money_docs = json.loads(json.dumps(money, default=str))
    for lab, s in (money_docs.get("screens") or {}).items():
        s.pop("samples_in", None)
        s.pop("samples_out", None)
        s.pop("sha256_pages", None)
        # trim top counterparties
        s["top_counterparties_by_eth"] = (s.get("top_counterparties_by_eth") or [])[:12]

    tracks_full = [money, ip, nexus, work]
    for t in tracks_full:
        _write(OUT / f"{t['id']}.json", json.loads(json.dumps(t, default=str)))
    _write(DOCS / "all_money_flows.json", money_docs)
    for t in (ip, nexus, work):
        _write(DOCS / f"{t['id']}.json", json.loads(json.dumps(t, default=str)))

    key = ensure_hmac_key()
    # Custody on slim+full consistent ids
    custody_tracks = [
        {
            "id": "all_money_flows",
            "title": money.get("title"),
            "status": "SEALED",
            "findings": money.get("findings"),
            "screens_summary": {
                lab: {
                    "eth_flows": s.get("eth_flows"),
                    "token_transfer_count": s.get("token_transfer_count"),
                    "sealed_eth_peers": s.get("sealed_eth_peers"),
                    "ip_linked_token_hit_count": s.get("ip_linked_token_hit_count"),
                    "tx_hit_page_cap": s.get("tx_hit_page_cap"),
                }
                for lab, s in (money.get("screens") or {}).items()
            },
        },
        ip,
        nexus,
        work,
    ]
    leaves = [
        {"id": t["id"], "sha3_256": _sha3_256(t), "status": t.get("status")}
        for t in custody_tracks
    ]
    material = json.dumps(
        {"case_id": CASE_ID, "leaves": leaves},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    root = _sha3_512(material)
    mac = hmac.new(key.encode(), material, hashlib.sha3_256).hexdigest()

    all_findings: list[dict[str, Any]] = []
    for t in (money, ip, nexus):
        all_findings.extend(t.get("findings") or [])

    f1 = (money.get("findings") or [{}])[0]
    f2 = (ip.get("findings") or [{}])[0]
    f3 = (nexus.get("findings") or [{}])[0]

    report = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "counts": {
            "tracks": len(custody_tracks),
            "findings": len(all_findings),
            "addresses_screened": f1.get("addresses_screened"),
            "sealed_money_edges": f1.get("sealed_set_money_edge_count"),
            "sealed_publications": f2.get("sealed_publication_count"),
            "onchain_ip_token_hits": f2.get("onchain_ip_linked_token_hits_total"),
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
            for t in custody_tracks
        ],
        "disposition": {
            "illicit_money_flow_adjudicated": False,
            "authenticated_money_flow_to_sealed_ip": False,
            "authenticated_ip_royalty_or_license_payment_rail": bool(
                f3.get("authenticated_ip_royalty_or_license_payment_rail")
            ),
            "theft_adjudicated": False,
            "illicit_royalty_adjudicated": False,
            "stolen_ip_conveyance_authenticated": False,
            "uspto_assignment_chain_authenticated": False,
        },
        "artifacts": {
            "summary_md": summary_md,
            "money": "docs/investigation/wave32/all_money_flows.json",
            "ip": "docs/investigation/wave32/all_intellectual_property_flows.json",
            "nexus": "docs/investigation/wave32/money_ip_nexus_matrix.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-32 deepens analysis to follow all money flows and all intellectual-"
            "property flows across the sealed set, with a money↔IP nexus matrix. "
            "No theft, illicit-royalty, or stolen-IP conveyance adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE32_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE32_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE32_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE32_POINTER.json",
        {
            "brand": BRAND,
            "wave32_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave32/WAVE32_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 32")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave32()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        d = report["disposition"]
        print(
            f"{BRAND} wave32: findings={report['counts']['findings']} "
            f"addrs={report['counts'].get('addresses_screened')} "
            f"money_edges={report['counts'].get('sealed_money_edges')} "
            f"pubs={report['counts'].get('sealed_publications')} "
            f"ip_hits={report['counts'].get('onchain_ip_token_hits')} "
            f"money_to_ip={d['authenticated_money_flow_to_sealed_ip']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

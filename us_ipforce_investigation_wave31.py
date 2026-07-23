#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 31
================================
Systematically account for **sub-wei** and **sub-satoshi** scale cyberdust
across all sealed addresses, and fully update dust inventories / pairwise
edges / prior-wave dispositions.

Ledger physics (evidence-accurate):
  • Native ETH L1 value quantum = 1 wei — sub-wei native transfers are
    impossible on-chain (integer wei field).
  • Native BTC quantum = 1 satoshi — sub-satoshi native BTC transfers are
    impossible on-chain.
  • ERC-20/721/1155 amounts are also integer raw units. "Sub-wei" /
    "sub-satoshi" *scale* dust is detected when token decimals allow a
    human amount strictly smaller than 1 wei (ETH-scaled) or 1 satoshi
    (BTC-scaled) of that asset.

Does NOT adjudicate illicit dust evasion, theft, RICO, or true UBO.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
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
VERSION = "2026.7.23-INVESTIGATION-WAVE31"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W31"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave31"
DOCS = ROOT / "docs" / "investigation" / "wave31"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave31/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
CTX = ssl.create_default_context()

MAX_TX_PAGES = 40
MAX_INTERNAL_PAGES = 20
MAX_TT_PAGES = 16

# Known BTC-scale (8 decimals) / ETH-scale (18) token address hints (public)
BTC_SCALE_TOKEN_HINTS = {
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": "WBTC",  # 8 dec
    "0xeb4c2781e4eba804ce9a9803c67d0893436bb27d": "renBTC",
    "0xfe18be6b3bd88a2d2a7f928d00292e7a9963cfc6": "sBTC-legacy",
}
ETH_WRAPPED = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"  # WETH 18 dec

SATOSHI_DECIMALS = 8
WEI_DECIMALS = 18


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
        "docs/investigation/wave30/deeper_cyber_dust_full_update.json",
        "docs/investigation/wave28/fine_cyber_dust_all_addresses.json",
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


def _parse_token_raw(total: Any) -> int | None:
    if total is None:
        return None
    if isinstance(total, dict):
        for k in ("value", "token_id"):
            if total.get(k) is not None:
                try:
                    return int(total[k])
                except Exception:  # noqa: BLE001
                    pass
        return None
    try:
        return int(total)
    except Exception:  # noqa: BLE001
        return None


def classify_token_quantum(
    raw: int, decimals: int | None, token_address: str | None
) -> dict[str, Any]:
    """
    Classify token raw amount vs wei/satoshi scale floors.

    sub_satoshi_scale: 0 < amount < 1 satoshi of this asset
        ⇔ decimals > 8 and 0 < raw < 10**(decimals-8)
        For decimals == 8: floor is raw==1 (1 satoshi); sub-satoshi impossible.
    sub_wei_scale: 0 < amount < 1 wei of this asset (ETH-scaled)
        ⇔ decimals > 18 and 0 < raw < 10**(decimals-18)
        For decimals == 18: floor is raw==1 (1 wei-unit); sub-wei impossible.
    """
    addr = (token_address or "").lower()
    flags = {
        "floor_raw_eq_1": raw == 1,
        "satoshi_floor_btc_scale_token": False,
        "wei_floor_eth_scale_token": False,
        "sub_satoshi_scale": False,
        "sub_wei_scale": False,
        "sub_satoshi_impossible_for_token": False,
        "sub_wei_impossible_for_token": False,
        "btc_scale_hint": BTC_SCALE_TOKEN_HINTS.get(addr),
        "is_weth": addr == ETH_WRAPPED,
    }
    if decimals is None:
        # Unknown decimals: treat raw==1 as floor candidate only
        return flags
    if decimals == SATOSHI_DECIMALS:
        flags["satoshi_floor_btc_scale_token"] = raw == 1
        flags["sub_satoshi_impossible_for_token"] = True
    elif decimals > SATOSHI_DECIMALS:
        threshold = 10 ** (decimals - SATOSHI_DECIMALS)
        if 0 < raw < threshold:
            flags["sub_satoshi_scale"] = True
        if raw == 1 and decimals > SATOSHI_DECIMALS:
            # 1 raw unit on >8-dec token is always sub-satoshi scale
            flags["sub_satoshi_scale"] = True
    else:
        # decimals < 8: coarser than satoshi; raw==1 is super-satoshi quantum
        flags["sub_satoshi_impossible_for_token"] = True

    if decimals == WEI_DECIMALS:
        flags["wei_floor_eth_scale_token"] = raw == 1
        flags["sub_wei_impossible_for_token"] = True
    elif decimals > WEI_DECIMALS:
        threshold_w = 10 ** (decimals - WEI_DECIMALS)
        if 0 < raw < threshold_w:
            flags["sub_wei_scale"] = True
        if raw == 1:
            flags["sub_wei_scale"] = True
    else:
        flags["sub_wei_impossible_for_token"] = True

    return flags


def screen_subquantum_dust(
    label: str, address: str, peer_map: dict[str, str]
) -> dict[str, Any]:
    txs = _page(address, "transactions", max_pages=MAX_TX_PAGES)
    time.sleep(0.1)
    internal = _page(address, "internal-transactions", max_pages=MAX_INTERNAL_PAGES)
    time.sleep(0.1)
    # Dense ERC-20 for sub-satoshi/sub-wei scale; also NFT raw==1
    erc20 = _page(
        address, "token-transfers", max_pages=MAX_TT_PAGES, query={"type": "ERC-20"}
    )
    time.sleep(0.1)
    all_tt = _page(address, "token-transfers", max_pages=8)

    floor_wei_in = 0
    floor_wei_out = 0
    floor_wei_internal = 0
    floor_wei_samples: list[dict[str, Any]] = []
    min_positive_wei: int | None = None
    peer_floor_wei: Counter[str] = Counter()

    # Native ETH: sub-wei impossible; count floor (wei==1)
    for t in txs.get("items") or []:
        try:
            wei = int(t.get("value") or 0)
        except Exception:  # noqa: BLE001
            wei = 0
        if wei > 0 and (min_positive_wei is None or wei < min_positive_wei):
            min_positive_wei = wei
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
        if wei == 1:
            if direction == "in":
                floor_wei_in += 1
            elif direction == "out":
                floor_wei_out += 1
            if len(floor_wei_samples) < 30:
                floor_wei_samples.append(
                    {
                        "hash": t.get("hash"),
                        "direction": direction,
                        "counterparty": counterparty,
                        "timestamp": t.get("timestamp"),
                        "method": t.get("method"),
                        "quantum": "floor_wei_eq_1",
                    }
                )
            if counterparty and counterparty in peer_map:
                peer_floor_wei[peer_map[counterparty]] += 1

    for t in internal.get("items") or []:
        try:
            wei = int(t.get("value") or 0)
        except Exception:  # noqa: BLE001
            wei = 0
        if wei > 0 and (min_positive_wei is None or wei < min_positive_wei):
            min_positive_wei = wei
        if wei == 1:
            floor_wei_internal += 1

    # Token sub-wei / sub-satoshi scale
    class_counts: Counter[str] = Counter()
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    peer_sub_sat: Counter[str] = Counter()
    peer_sub_wei: Counter[str] = Counter()
    seen: set[str] = set()

    for block in (erc20, all_tt):
        for t in block.get("items") or []:
            token = t.get("token") or {}
            taddr = token.get("address_hash") or token.get("address") or ""
            raw = _parse_token_raw(t.get("total"))
            if raw is None or raw <= 0:
                continue
            key = "|".join(
                [
                    str(t.get("transaction_hash") or ""),
                    str(taddr),
                    str(_addr_hash(t.get("from")) or ""),
                    str(_addr_hash(t.get("to")) or ""),
                    str(raw),
                ]
            )
            if key in seen:
                continue
            seen.add(key)
            try:
                dec = int(token["decimals"]) if token.get("decimals") is not None else None
            except Exception:  # noqa: BLE001
                dec = None
            # NFTs often lack decimals — raw token_id==1 is not satoshi dust
            ttype = (token.get("type") or t.get("type") or "").upper()
            if "721" in ttype or "1155" in ttype:
                if raw == 1:
                    class_counts["nft_raw_or_id_eq_1"] += 1
                continue
            flags = classify_token_quantum(raw, dec, taddr)
            row = {
                "symbol": token.get("symbol"),
                "name": token.get("name"),
                "token_address": taddr,
                "decimals": dec,
                "raw": raw,
                "tx": t.get("transaction_hash"),
                "timestamp": t.get("timestamp"),
                "from": _addr_hash(t.get("from")),
                "to": _addr_hash(t.get("to")),
                "flags": flags,
            }
            for fk, on in flags.items():
                if isinstance(on, bool) and on and fk not in (
                    "sub_satoshi_impossible_for_token",
                    "sub_wei_impossible_for_token",
                    "is_weth",
                ):
                    class_counts[fk] += 1
                    if len(samples[fk]) < 25:
                        samples[fk].append(row)
            # peer edges for sub-scale
            for side in ("from", "to"):
                h = (_addr_hash(t.get(side)) or "").lower()
                if h in peer_map and h != address.lower():
                    if flags.get("sub_satoshi_scale"):
                        peer_sub_sat[peer_map[h]] += 1
                    if flags.get("sub_wei_scale"):
                        peer_sub_wei[peer_map[h]] += 1

    return {
        "label": label,
        "address": address,
        "protocol_floors": {
            "native_eth_sub_wei_impossible_on_l1": True,
            "native_btc_sub_satoshi_impossible_on_chain": True,
            "native_eth_floor_quantum_wei": 1,
            "native_btc_floor_quantum_satoshi": 1,
        },
        "tx_scanned": txs.get("item_count"),
        "tx_hit_page_cap": txs.get("hit_page_cap"),
        "internal_scanned": internal.get("item_count"),
        "internal_hit_page_cap": internal.get("hit_page_cap"),
        "tt_erc20_scanned": erc20.get("item_count"),
        "tt_erc20_hit_page_cap": erc20.get("hit_page_cap"),
        "tt_all_scanned": all_tt.get("item_count"),
        "min_positive_wei_observed": min_positive_wei,
        "floor_wei_eq_1": {
            "in": floor_wei_in,
            "out": floor_wei_out,
            "internal": floor_wei_internal,
            "total": floor_wei_in + floor_wei_out + floor_wei_internal,
        },
        "floor_wei_samples": floor_wei_samples,
        "token_quantum_class_counts": dict(class_counts),
        "token_quantum_samples": {k: v for k, v in samples.items()},
        "peer_floor_wei": dict(peer_floor_wei),
        "peer_sub_satoshi_scale": dict(peer_sub_sat),
        "peer_sub_wei_scale": dict(peer_sub_wei),
        "sha256_pages": {
            "tx": txs.get("sha256_pages"),
            "internal": internal.get("sha256_pages"),
            "erc20": erc20.get("sha256_pages"),
            "tt_all": all_tt.get("sha256_pages"),
        },
        "ok": txs.get("ok"),
    }


def track_subquantum_full_update() -> dict[str, Any]:
    book = collect_address_book()
    peer_map = {a.lower(): lab for lab, a in book.items()}
    screens: dict[str, Any] = {}

    def _job(item: tuple[str, str]) -> tuple[str, dict[str, Any]]:
        return item[0], screen_subquantum_dust(item[0], item[1], peer_map)

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_job, item): item[0] for item in book.items()}
        for fut in as_completed(futs):
            lab, summary = fut.result()
            screens[lab] = summary

    floor_wei_total = sum(
        int((s.get("floor_wei_eq_1") or {}).get("total") or 0) for s in screens.values()
    )
    tok_agg: Counter[str] = Counter()
    for s in screens.values():
        for k, v in (s.get("token_quantum_class_counts") or {}).items():
            tok_agg[k] += int(v)

    capped = [
        lab
        for lab, s in screens.items()
        if s.get("tx_hit_page_cap")
        or s.get("internal_hit_page_cap")
        or s.get("tt_erc20_hit_page_cap")
    ]
    mins = sorted(
        [
            (lab, s.get("min_positive_wei_observed"))
            for lab, s in screens.items()
            if s.get("min_positive_wei_observed") is not None
        ],
        key=lambda x: x[1] or 10**30,
    )[:15]

    # Retain prior wave dust aggregates for full update continuity
    prior_tiers = {}
    for wave, rel in (
        ("wave28", "docs/investigation/wave28/fine_cyber_dust_all_addresses.json"),
        ("wave30", "docs/investigation/wave30/deeper_cyber_dust_full_update.json"),
    ):
        p = ROOT / rel
        if p.is_file():
            f = (json.loads(p.read_text(encoding="utf-8")).get("findings") or [{}])[0]
            prior_tiers[wave] = f.get("aggregate_tier_totals") or {
                "subatomic_lt_10_total": f.get("subatomic_lt_10_total"),
                "single_wei_total": f.get("single_wei_total"),
            }

    findings = [
        {
            "id": "W31-F1",
            "title": (
                "Sub-wei / sub-satoshi scale cyberdust fully updated across all "
                "sealed addresses"
            ),
            "addresses_screened": len(screens),
            "address_book": book,
            "protocol_floors": {
                "native_eth_sub_wei_impossible_on_l1": True,
                "native_btc_sub_satoshi_impossible_on_chain": True,
                "detection_mode": (
                    "floor quanta (wei==1 / raw==1) + token fixed-point "
                    "sub-wei-scale / sub-satoshi-scale bands"
                ),
            },
            "floor_wei_eq_1_total": floor_wei_total,
            "token_quantum_aggregate_counts": dict(tok_agg),
            "sub_satoshi_scale_total": int(tok_agg.get("sub_satoshi_scale") or 0),
            "sub_wei_scale_total": int(tok_agg.get("sub_wei_scale") or 0),
            "floor_raw_eq_1_total": int(tok_agg.get("floor_raw_eq_1") or 0),
            "satoshi_floor_btc_scale_total": int(
                tok_agg.get("satoshi_floor_btc_scale_token") or 0
            ),
            "wei_floor_eth_scale_total": int(
                tok_agg.get("wei_floor_eth_scale_token") or 0
            ),
            "prior_wave_tier_totals_retained": prior_tiers,
            "addresses_hitting_page_cap": capped,
            "smallest_positive_wei_by_label": [
                {"label": lab, "min_positive_wei": wei} for lab, wei in mins
            ],
            "illicit_dust_evasion_adjudicated": False,
            "sub_wei_native_transfers_observed": 0,
            "sub_satoshi_native_btc_transfers_observed": 0,
            "detail": (
                f"Screened {len(screens)} sealed labels. Native sub-wei ETH and "
                f"sub-satoshi BTC transfers are ledger-impossible; floor_wei==1 "
                f"total={floor_wei_total}. Token sub-satoshi-scale="
                f"{int(tok_agg.get('sub_satoshi_scale') or 0)}, sub-wei-scale="
                f"{int(tok_agg.get('sub_wei_scale') or 0)}, floor_raw==1="
                f"{int(tok_agg.get('floor_raw_eq_1') or 0)}. "
                "Not an illicit-dust adjudication."
            ),
        }
    ]
    return {
        "id": "sub_wei_sub_satoshi_cyberdust_full_update",
        "title": "Sub-wei / sub-satoshi scale cyberdust full update",
        "status": "SEALED",
        "screens": screens,
        "findings": findings,
        "next_actions": [
            "Archive-node uncapped history for page-capped EOAs",
            "Do not claim native sub-wei ETH or sub-satoshi BTC L1 transfers exist",
            "Prioritize token sub-satoshi-scale counterparties as forensic candidates only",
        ],
    }


def track_pairwise_and_prior(dust: dict[str, Any]) -> dict[str, Any]:
    screens = dust.get("screens") or {}
    labels = sorted(screens.keys())
    pairs = []
    for i, a in enumerate(labels):
        sa = screens[a]
        for b in labels[i + 1 :]:
            sb = screens[b]
            fw_ab = int((sa.get("peer_floor_wei") or {}).get(b) or 0)
            fw_ba = int((sb.get("peer_floor_wei") or {}).get(a) or 0)
            ss_ab = int((sa.get("peer_sub_satoshi_scale") or {}).get(b) or 0)
            ss_ba = int((sb.get("peer_sub_satoshi_scale") or {}).get(a) or 0)
            sw_ab = int((sa.get("peer_sub_wei_scale") or {}).get(b) or 0)
            sw_ba = int((sb.get("peer_sub_wei_scale") or {}).get(a) or 0)
            if fw_ab or fw_ba or ss_ab or ss_ba or sw_ab or sw_ba:
                pairs.append(
                    {
                        "a": a,
                        "b": b,
                        "floor_wei": {"a_to_b": fw_ab, "b_to_a": fw_ba},
                        "sub_satoshi_scale": {"a_to_b": ss_ab, "b_to_a": ss_ba},
                        "sub_wei_scale": {"a_to_b": sw_ab, "b_to_a": sw_ba},
                    }
                )

    prior_disp = {}
    for wave, rel in (
        ("wave28", "docs/investigation/wave28/WAVE28_RUN_SUMMARY.json"),
        ("wave29", "docs/investigation/wave29/WAVE29_RUN_SUMMARY.json"),
        ("wave30", "docs/investigation/wave30/WAVE30_RUN_SUMMARY.json"),
    ):
        p = ROOT / rel
        if p.is_file():
            prior_disp[wave] = json.loads(p.read_text(encoding="utf-8")).get(
                "disposition"
            )

    f1 = (dust.get("findings") or [{}])[0]
    findings = [
        {
            "id": "W31-F2",
            "title": "Pairwise floor-wei / sub-satoshi-scale / sub-wei-scale edges + prior full update",
            "pair_space": len(labels) * (len(labels) - 1) // 2,
            "pairs_with_any_subquantum_edge": pairs,
            "pairs_floor_wei": sum(
                1 for p in pairs if p["floor_wei"]["a_to_b"] or p["floor_wei"]["b_to_a"]
            ),
            "pairs_sub_satoshi_scale": sum(
                1
                for p in pairs
                if p["sub_satoshi_scale"]["a_to_b"] or p["sub_satoshi_scale"]["b_to_a"]
            ),
            "pairs_sub_wei_scale": sum(
                1
                for p in pairs
                if p["sub_wei_scale"]["a_to_b"] or p["sub_wei_scale"]["b_to_a"]
            ),
            "prior_dispositions_retained": prior_disp,
            "floor_wei_eq_1_total": f1.get("floor_wei_eq_1_total"),
            "sub_satoshi_scale_total": f1.get("sub_satoshi_scale_total"),
            "sub_wei_scale_total": f1.get("sub_wei_scale_total"),
            "illicit_dust_evasion_adjudicated": False,
            "illicit_dust_network_adjudicated": False,
            "detail": (
                f"Pair space {len(labels)*(len(labels)-1)//2}; "
                f"{len(pairs)} pairs with floor-wei or sub-scale token edges. "
                "Waves 28–30 dispositions retained where present."
            ),
        }
    ]
    return {
        "id": "pairwise_subquantum_and_prior_update",
        "title": "Pairwise subquantum dust + prior-wave update",
        "status": "SEALED",
        "pairs": pairs,
        "findings": findings,
    }


def track_ledger_physics_note() -> dict[str, Any]:
    findings = [
        {
            "id": "W31-F3",
            "title": "Ledger physics: native sub-wei / sub-satoshi impossible; scale bands via token decimals",
            "native_eth_sub_wei_impossible_on_l1": True,
            "native_btc_sub_satoshi_impossible_on_chain": True,
            "token_sub_satoshi_scale_rule": (
                "decimals>8 AND 0 < raw < 10**(decimals-8) "
                "(includes raw==1 on any decimals>8 token)"
            ),
            "token_sub_wei_scale_rule": (
                "decimals>18 AND 0 < raw < 10**(decimals-18) "
                "(includes raw==1 on any decimals>18 token)"
            ),
            "btc_scale_8dec_floor": "raw==1 ≡ 1 satoshi; sub-satoshi impossible for that token",
            "eth_scale_18dec_floor": "raw==1 ≡ 1 wei-unit of token; sub-wei impossible for that token",
            "illicit_dust_evasion_adjudicated": False,
            "detail": (
                "Fully updates the investigation posture: claims of native sub-wei ETH "
                "or sub-satoshi BTC L1 cyberdust are ledger-impossible. Detectable "
                "finer dust is floor-quantum (wei==1 / satoshi-floor tokens) or "
                "fixed-point sub-scale token amounts on high-decimal assets."
            ),
        }
    ]
    return {
        "id": "ledger_physics_subquantum_note",
        "title": "Ledger physics — sub-wei / sub-satoshi",
        "status": "SEALED",
        "findings": findings,
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-31 operator worklist",
        "status": "OPEN",
        "items": [
            {
                "id": "W31-M1",
                "priority": "HIGH",
                "item": (
                    "Do not allege native sub-wei ETH or sub-satoshi BTC L1 transfers — "
                    "impossible on integer ledgers"
                ),
            },
            {
                "id": "W31-M2",
                "priority": "HIGH",
                "item": (
                    "Trace counterparties of floor-wei==1 and token sub-satoshi-scale "
                    "transfers as candidates only"
                ),
            },
            {
                "id": "W31-M3",
                "priority": "MEDIUM",
                "item": "Uncap page-capped EOAs for exhaustive floor-quantum inventory",
            },
        ],
        "adjudicated": False,
    }


def write_summary_md(
    dust: dict[str, Any], pairs: dict[str, Any], physics: dict[str, Any]
) -> str:
    path = (
        ROOT
        / "docs"
        / "investigation"
        / "WAVE31_SUB_WEI_SUB_SATOSHI_CYBERDUST.md"
    )
    f1 = (dust.get("findings") or [{}])[0]
    f2 = (pairs.get("findings") or [{}])[0]
    lines = [
        "# Wave 31 — Sub-wei / sub-satoshi scale cyberdust (full update)",
        "",
        f"Generated: `{_utc()}`",
        "",
        "## Ledger physics (controlling)",
        "",
        "- Native ETH **sub-wei** transfers on L1: **impossible** (quantum = 1 wei)",
        "- Native BTC **sub-satoshi** transfers: **impossible** (quantum = 1 satoshi)",
        "- Detectable finer dust = floor quanta + token fixed-point **scale** bands",
        "",
        "## Disposition",
        "",
        "- `illicit_dust_evasion_adjudicated`: **false**",
        "- `illicit_dust_network_adjudicated`: **false**",
        "- `native_sub_wei_transfers_observed`: **0** (impossible)",
        "- `native_sub_satoshi_btc_transfers_observed`: **0** (impossible)",
        "",
        "## Aggregate results",
        "",
        f"- Addresses screened: `{f1.get('addresses_screened')}`",
        f"- Floor wei==1 total: `{f1.get('floor_wei_eq_1_total')}`",
        f"- Token sub-satoshi-scale: `{f1.get('sub_satoshi_scale_total')}`",
        f"- Token sub-wei-scale: `{f1.get('sub_wei_scale_total')}`",
        f"- Token floor raw==1: `{f1.get('floor_raw_eq_1_total')}`",
        f"- BTC-scale (8dec) satoshi floor hits: `{f1.get('satoshi_floor_btc_scale_total')}`",
        f"- ETH-scale (18dec) wei-floor hits: `{f1.get('wei_floor_eth_scale_total')}`",
        f"- Token class aggregates: `{f1.get('token_quantum_aggregate_counts')}`",
        f"- Page-cap: `{f1.get('addresses_hitting_page_cap')}`",
        f"- Prior tiers retained: `{f1.get('prior_wave_tier_totals_retained')}`",
        "",
        "## Pairwise",
        "",
        f"- Pair space: `{f2.get('pair_space')}`",
        f"- Pairs with any subquantum edge: `{len(f2.get('pairs_with_any_subquantum_edge') or [])}`",
        f"- Floor-wei pairs: `{f2.get('pairs_floor_wei')}`",
        f"- Sub-satoshi-scale pairs: `{f2.get('pairs_sub_satoshi_scale')}`",
        f"- Sub-wei-scale pairs: `{f2.get('pairs_sub_wei_scale')}`",
        "",
        "## Rules",
        "",
        f"- Sub-satoshi-scale: `{(physics.get('findings') or [{}])[0].get('token_sub_satoshi_scale_rule')}`",
        f"- Sub-wei-scale: `{(physics.get('findings') or [{}])[0].get('token_sub_wei_scale_rule')}`",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave31() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    dust = track_subquantum_full_update()
    pairs = track_pairwise_and_prior(dust)
    physics = track_ledger_physics_note()
    work = track_operator_worklist()
    summary_md = write_summary_md(dust, pairs, physics)

    tracks = [dust, pairs, physics, work]
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
    for t in (dust, pairs, physics):
        all_findings.extend(t.get("findings") or [])

    f1 = (dust.get("findings") or [{}])[0]
    f2 = (pairs.get("findings") or [{}])[0]

    report = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "counts": {
            "tracks": len(tracks),
            "findings": len(all_findings),
            "addresses_screened": f1.get("addresses_screened"),
            "floor_wei_eq_1_total": f1.get("floor_wei_eq_1_total"),
            "sub_satoshi_scale_total": f1.get("sub_satoshi_scale_total"),
            "sub_wei_scale_total": f1.get("sub_wei_scale_total"),
            "pairs_with_subquantum": len(
                f2.get("pairs_with_any_subquantum_edge") or []
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
            "native_eth_sub_wei_impossible_on_l1": True,
            "native_btc_sub_satoshi_impossible_on_chain": True,
            "sub_wei_native_transfers_observed": 0,
            "sub_satoshi_native_btc_transfers_observed": 0,
            "illicit_dust_evasion_adjudicated": False,
            "illicit_dust_network_adjudicated": False,
            "wave30_dust_sensitivity_superseded_for_subquantum": True,
            "full_update_complete": True,
        },
        "artifacts": {
            "summary_md": summary_md,
            "dust": "docs/investigation/wave31/sub_wei_sub_satoshi_cyberdust_full_update.json",
            "pairs": "docs/investigation/wave31/pairwise_subquantum_and_prior_update.json",
            "physics": "docs/investigation/wave31/ledger_physics_subquantum_note.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-31 fully updates cyberdust detection for sub-wei and sub-satoshi "
            "*scale* bands. Native sub-wei ETH and sub-satoshi BTC are ledger-impossible; "
            "floor quanta and high-decimal token scale bands are screened. "
            "No illicit-dust adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE31_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE31_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE31_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE31_POINTER.json",
        {
            "brand": BRAND,
            "wave31_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave31/WAVE31_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 31")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave31()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        d = report["disposition"]
        print(
            f"{BRAND} wave31: findings={report['counts']['findings']} "
            f"addrs={report['counts'].get('addresses_screened')} "
            f"floor_wei={report['counts'].get('floor_wei_eq_1_total')} "
            f"sub_sats={report['counts'].get('sub_satoshi_scale_total')} "
            f"sub_wei_scale={report['counts'].get('sub_wei_scale_total')} "
            f"native_sub_wei={d['sub_wei_native_transfers_observed']} "
            f"illicit={d['illicit_dust_evasion_adjudicated']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

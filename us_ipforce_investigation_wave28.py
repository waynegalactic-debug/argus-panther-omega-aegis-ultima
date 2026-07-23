#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 28
================================
Substantially deepen cyber-dust detection with multi-tier finer wei
thresholds across all sealed Wave 21–27 addresses. Fully update dust
inventories, pairwise fine-dust edges, internal-tx dust, and token-dust
heuristics. Retain Wave-26/27 dispositions; do NOT adjudicate illicit
dust evasion, theft, RICO, or true UBO.

Legacy Wave-26 threshold: 0 < wei < 1e12  (~1e-6 ETH)
Wave-28 adds nested finer bands down to single-wei / atomic dust.
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
VERSION = "2026.7.23-INVESTIGATION-WAVE28"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W28"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave28"
DOCS = ROOT / "docs" / "investigation" / "wave28"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave28/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
CTX = ssl.create_default_context()

# Deeper pagination than Wave-26 for finer dust capture
MAX_TX_PAGES = 30
MAX_INTERNAL_PAGES = 12
MAX_TT_PAGES = 10

# Multi-tier dust thresholds (wei). Nested: atomic ⊂ nano ⊂ ultra ⊂ fine ⊂ legacy
DUST_TIERS: list[tuple[str, int, str]] = [
    ("legacy_w26", 1_000_000_000_000, "0 < wei < 1e12 (~1e-6 ETH) — Wave-26 baseline"),
    ("fine", 1_000_000_000, "0 < wei < 1e9 (~1e-9 ETH)"),
    ("ultra", 1_000_000, "0 < wei < 1e6 (~1e-12 ETH)"),
    ("nano", 1_000, "0 < wei < 1e3 (~1e-15 ETH)"),
    ("atomic", 100, "0 < wei < 100 (sub-100 wei)"),
    ("single_wei", 2, "wei == 1 (single-wei atomic dust)"),
]
# Primary deepened threshold used for pairwise / headline counts
DUST_WEI_LT_FINE = 1_000_000_000  # 1e9 — 1000× finer than Wave-26
DUST_WEI_LT_ULTRA = 1_000_000  # 1e6 — 1_000_000× finer than Wave-26


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
        time.sleep(0.18)
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
    """Union sealed books from Waves 26–27 (prefer 26 address_book)."""
    book: dict[str, str] = {}
    for rel in (
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
    # dedupe by address
    by_addr: dict[str, str] = {}
    for lab, addr in book.items():
        key = addr.lower()
        if key not in by_addr:
            by_addr[key] = lab
    return {lab: book[lab] for lab in by_addr.values()}


def _classify_wei(wei: int) -> list[str]:
    """Return all tier names that match this wei (nested bands)."""
    if wei <= 0:
        return []
    hits: list[str] = []
    for name, lt, _ in DUST_TIERS:
        if name == "single_wei":
            if wei == 1:
                hits.append(name)
        elif wei < lt:
            hits.append(name)
    return hits


def _parse_token_raw(total: Any) -> int | None:
    """Best-effort raw token amount from Blockscout total field."""
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


def screen_address_fine_dust(
    label: str, address: str, peer_map: dict[str, str]
) -> dict[str, Any]:
    txs = _page(address, "transactions", max_pages=MAX_TX_PAGES)
    time.sleep(0.12)
    internal = _page(address, "internal-transactions", max_pages=MAX_INTERNAL_PAGES)
    time.sleep(0.12)
    tts = _page(address, "token-transfers", max_pages=MAX_TT_PAGES)

    tier_dir: dict[str, Counter[str]] = {name: Counter() for name, _, _ in DUST_TIERS}
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    peer_dust_fine: Counter[str] = Counter()
    peer_dust_ultra: Counter[str] = Counter()
    peer_dust_by_tier: dict[str, Counter[str]] = defaultdict(Counter)
    min_positive_wei: int | None = None
    wei_histogram_log: Counter[str] = Counter()  # log10 band of wei

    def _ingest(wei: int, direction: str | None, source: str, meta: dict[str, Any]) -> None:
        nonlocal min_positive_wei
        if wei <= 0:
            return
        if min_positive_wei is None or wei < min_positive_wei:
            min_positive_wei = wei
        # log10-ish band
        band = 0
        w = wei
        while w >= 10:
            w //= 10
            band += 1
        wei_histogram_log[f"1e{band}"] += 1
        for tier in _classify_wei(wei):
            if direction:
                tier_dir[tier][f"{source}_{direction}"] += 1
            else:
                tier_dir[tier][f"{source}_unknown"] += 1
            if len(samples[tier]) < 30:
                samples[tier].append({**meta, "value_wei": wei, "source": source})

    for t in txs.get("items") or []:
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
        _ingest(
            wei,
            direction,
            "tx",
            {
                "hash": t.get("hash"),
                "direction": direction,
                "counterparty": counterparty,
                "timestamp": t.get("timestamp"),
                "method": t.get("method"),
            },
        )
        if counterparty and counterparty in peer_map and wei > 0:
            plab = peer_map[counterparty]
            for tier in _classify_wei(wei):
                peer_dust_by_tier[tier][plab] += 1
            if wei < DUST_WEI_LT_FINE:
                peer_dust_fine[plab] += 1
            if wei < DUST_WEI_LT_ULTRA:
                peer_dust_ultra[plab] += 1

    for t in internal.get("items") or []:
        try:
            wei = int(t.get("value") or 0)
        except Exception:  # noqa: BLE001
            wei = 0
        fr = (_addr_hash(t.get("from")) or "").lower()
        to = (_addr_hash(t.get("to")) or "").lower()
        direction = None
        if fr == address.lower():
            direction = "out"
        elif to == address.lower():
            direction = "in"
        _ingest(
            wei,
            direction,
            "internal",
            {
                "hash": t.get("transaction_hash") or t.get("hash"),
                "direction": direction,
                "timestamp": t.get("timestamp"),
                "type": t.get("type"),
            },
        )

    # Token dust: raw amount == 1 or very small raw units (decimals-unknown → heuristic only)
    token_dust: list[dict[str, Any]] = []
    token_dust_counts = Counter()
    for t in tts.get("items") or []:
        token = t.get("token") or {}
        raw = _parse_token_raw(t.get("total"))
        decimals = token.get("decimals")
        try:
            dec = int(decimals) if decimals is not None else None
        except Exception:  # noqa: BLE001
            dec = None
        is_dust = False
        reason = None
        if raw is not None and raw > 0:
            if raw == 1:
                is_dust = True
                reason = "raw_amount_eq_1"
            elif dec is not None and raw < 10 ** max(dec - 9, 0):
                # < 1e-9 whole tokens when decimals known
                is_dust = True
                reason = f"lt_1e-9_token_units_dec_{dec}"
            elif dec is None and raw < 1000:
                is_dust = True
                reason = "raw_lt_1000_decimals_unknown"
        if is_dust:
            token_dust_counts[reason or "?"] += 1
            if len(token_dust) < 40:
                token_dust.append(
                    {
                        "symbol": token.get("symbol"),
                        "name": token.get("name"),
                        "type": token.get("type"),
                        "raw": raw,
                        "decimals": dec,
                        "reason": reason,
                        "tx": t.get("transaction_hash"),
                        "timestamp": t.get("timestamp"),
                    }
                )

    # Rollup counts per tier (all sources)
    tier_totals = {
        name: int(sum(tier_dir[name].values())) for name, _, _ in DUST_TIERS
    }

    return {
        "label": label,
        "address": address,
        "tx_scanned": txs.get("item_count"),
        "tx_pages": txs.get("pages"),
        "tx_exhausted": txs.get("exhausted"),
        "tx_hit_page_cap": txs.get("hit_page_cap"),
        "internal_scanned": internal.get("item_count"),
        "internal_hit_page_cap": internal.get("hit_page_cap"),
        "tt_scanned": tts.get("item_count"),
        "tt_hit_page_cap": tts.get("hit_page_cap"),
        "min_positive_wei_observed": min_positive_wei,
        "wei_log10_histogram": dict(wei_histogram_log),
        "tier_direction_counts": {k: dict(v) for k, v in tier_dir.items()},
        "tier_totals": tier_totals,
        "tier_samples": {k: v for k, v in samples.items()},
        "peer_dust_fine_lt_1e9": dict(peer_dust_fine),
        "peer_dust_ultra_lt_1e6": dict(peer_dust_ultra),
        "peer_dust_by_tier": {k: dict(v) for k, v in peer_dust_by_tier.items()},
        "token_dust_heuristic_counts": dict(token_dust_counts),
        "token_dust_samples": token_dust,
        "sha256_pages": {
            "tx": txs.get("sha256_pages"),
            "internal": internal.get("sha256_pages"),
            "tt": tts.get("sha256_pages"),
        },
        "ok": txs.get("ok"),
    }


def track_fine_dust_screen() -> dict[str, Any]:
    book = collect_address_book()
    peer_map = {a.lower(): lab for lab, a in book.items()}
    screens: dict[str, Any] = {}

    def _job(item: tuple[str, str]) -> tuple[str, dict[str, Any]]:
        return item[0], screen_address_fine_dust(item[0], item[1], peer_map)

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_job, item): item[0] for item in book.items()}
        for fut in as_completed(futs):
            lab, summary = fut.result()
            screens[lab] = summary

    aggregate_tiers: Counter[str] = Counter()
    token_dust_total = 0
    for s in screens.values():
        for k, v in (s.get("tier_totals") or {}).items():
            aggregate_tiers[k] += int(v)
        token_dust_total += sum((s.get("token_dust_heuristic_counts") or {}).values())

    capped = [
        lab
        for lab, s in screens.items()
        if s.get("tx_hit_page_cap") or s.get("internal_hit_page_cap")
    ]
    mins = [
        (lab, s.get("min_positive_wei_observed"))
        for lab, s in screens.items()
        if s.get("min_positive_wei_observed") is not None
    ]
    mins_sorted = sorted(mins, key=lambda x: x[1] or 10**30)[:15]

    w26_dust = None
    w26_path = ROOT / "docs" / "investigation" / "wave26" / "blockchain_flows_all_addresses.json"
    if w26_path.is_file():
        w26 = json.loads(w26_path.read_text(encoding="utf-8"))
        w26_dust = (w26.get("findings") or [{}])[0].get("total_dust_candidates_in_plus_out")

    findings = [
        {
            "id": "W28-F1",
            "title": "Finer multi-tier cyber-dust screen across all sealed addresses (full update)",
            "addresses_screened": len(screens),
            "address_book": book,
            "thresholds": [
                {"tier": n, "wei_lt": lt, "description": d} for n, lt, d in DUST_TIERS
            ],
            "aggregate_tier_totals": dict(aggregate_tiers),
            "wave26_legacy_dust_total_retained": w26_dust,
            "deepened_fine_lt_1e9_total": int(aggregate_tiers.get("fine") or 0),
            "ultra_lt_1e6_total": int(aggregate_tiers.get("ultra") or 0),
            "nano_lt_1e3_total": int(aggregate_tiers.get("nano") or 0),
            "atomic_lt_100_total": int(aggregate_tiers.get("atomic") or 0),
            "single_wei_total": int(aggregate_tiers.get("single_wei") or 0),
            "token_dust_heuristic_total": token_dust_total,
            "addresses_hitting_page_cap": capped,
            "smallest_positive_wei_by_label": [
                {"label": lab, "min_positive_wei": wei} for lab, wei in mins_sorted
            ],
            "illicit_dust_evasion_adjudicated": False,
            "detail": (
                f"Re-screened {len(screens)} sealed labels with deeper pagination "
                f"(tx≤{MAX_TX_PAGES}, internal≤{MAX_INTERNAL_PAGES}) and nested dust "
                f"tiers from legacy 1e12 down to single-wei. Aggregate tier totals: "
                f"{dict(aggregate_tiers)}. Wave-26 legacy dust total was {w26_dust}. "
                f"Token-dust heuristic hits: {token_dust_total}. "
                "Finer detection does NOT adjudicate illicit dust evasion."
            ),
        }
    ]
    return {
        "id": "fine_cyber_dust_all_addresses",
        "title": "Multi-tier finer cyber-dust screen (all sealed addresses)",
        "status": "SEALED",
        "thresholds": [
            {"tier": n, "wei_lt": lt, "description": d} for n, lt, d in DUST_TIERS
        ],
        "max_tx_pages": MAX_TX_PAGES,
        "max_internal_pages": MAX_INTERNAL_PAGES,
        "screens": screens,
        "findings": findings,
        "next_actions": [
            "Archive-node pagination for page-capped EOAs to exhaust atomic/single-wei dust",
            "Named dusting contracts if operator asserts intentional dust campaigns",
        ],
    }


def track_pairwise_fine_dust(dust_track: dict[str, Any]) -> dict[str, Any]:
    screens = dust_track.get("screens") or {}
    labels = sorted(screens.keys())
    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(labels):
        sa = screens[a]
        for b in labels[i + 1 :]:
            fine_ab = int((sa.get("peer_dust_fine_lt_1e9") or {}).get(b) or 0)
            ultra_ab = int((sa.get("peer_dust_ultra_lt_1e6") or {}).get(b) or 0)
            sb = screens[b]
            fine_ba = int((sb.get("peer_dust_fine_lt_1e9") or {}).get(a) or 0)
            ultra_ba = int((sb.get("peer_dust_ultra_lt_1e6") or {}).get(a) or 0)
            tier_edges = {}
            for tier, _, _ in DUST_TIERS:
                ab = int((sa.get("peer_dust_by_tier") or {}).get(tier, {}).get(b) or 0)
                ba = int((sb.get("peer_dust_by_tier") or {}).get(tier, {}).get(a) or 0)
                if ab or ba:
                    tier_edges[tier] = {"a_to_b": ab, "b_to_a": ba}
            if fine_ab or fine_ba or ultra_ab or ultra_ba or tier_edges:
                pairs.append(
                    {
                        "a": a,
                        "b": b,
                        "fine_lt_1e9": {"a_to_b": fine_ab, "b_to_a": fine_ba},
                        "ultra_lt_1e6": {"a_to_b": ultra_ab, "b_to_a": ultra_ba},
                        "tier_edges": tier_edges,
                    }
                )

    findings = [
        {
            "id": "W28-F2",
            "title": "Pairwise finer cyber-dust edges across all sealed individuals/entities",
            "pair_space": len(labels) * (len(labels) - 1) // 2,
            "pairs_with_any_fine_or_tier_dust": pairs,
            "pairs_with_fine_lt_1e9": sum(
                1
                for p in pairs
                if p["fine_lt_1e9"]["a_to_b"] or p["fine_lt_1e9"]["b_to_a"]
            ),
            "pairs_with_ultra_lt_1e6": sum(
                1
                for p in pairs
                if p["ultra_lt_1e6"]["a_to_b"] or p["ultra_lt_1e6"]["b_to_a"]
            ),
            "illicit_dust_network_adjudicated": False,
            "detail": (
                f"Pair space {len(labels)*(len(labels)-1)//2}; "
                f"{len(pairs)} pairs showed any fine/tier dust edge in scanned pages. "
                "No illicit dust-network adjudication."
            ),
        }
    ]
    return {
        "id": "pairwise_fine_dust_combinations",
        "title": "Pairwise finer cyber-dust combinations",
        "status": "SEALED",
        "pairs": pairs,
        "findings": findings,
    }


def track_prior_wave_dust_update(dust_track: dict[str, Any]) -> dict[str, Any]:
    """Fully update Wave-26/27 dust-related dispositions with finer thresholds."""
    f1 = (dust_track.get("findings") or [{}])[0]
    w26 = {}
    w27 = {}
    p26 = ROOT / "docs" / "investigation" / "wave26" / "WAVE26_RUN_SUMMARY.json"
    p27 = ROOT / "docs" / "investigation" / "wave27" / "WAVE27_RUN_SUMMARY.json"
    if p26.is_file():
        w26 = json.loads(p26.read_text(encoding="utf-8")).get("disposition") or {}
    if p27.is_file():
        w27 = json.loads(p27.read_text(encoding="utf-8")).get("disposition") or {}

    findings = [
        {
            "id": "W28-F3",
            "title": "Full update of prior-wave dust dispositions under finer thresholds",
            "wave26_disposition_retained": w26,
            "wave27_disposition_retained": w27,
            "wave26_legacy_dust_total": f1.get("wave26_legacy_dust_total_retained"),
            "wave28_aggregate_tier_totals": f1.get("aggregate_tier_totals"),
            "threshold_deepening": {
                "wave26_wei_lt": 1_000_000_000_000,
                "wave28_fine_wei_lt": DUST_WEI_LT_FINE,
                "wave28_ultra_wei_lt": DUST_WEI_LT_ULTRA,
                "wave28_finest_band": "single_wei (wei==1)",
                "sensitivity_vs_wave26": "fine=1000× ; ultra=1_000_000× ; nano/atomic/single-wei nested",
            },
            "illicit_dust_evasion_adjudicated": False,
            "update_note": (
                "Wave-28 supersedes Wave-26 dust sensitivity for detection purposes. "
                "Wave-26 legacy aggregate remains recorded for comparison. "
                "Wave-27 token-class dispositions unchanged; dust detection deepened only."
            ),
        }
    ]
    return {
        "id": "prior_wave_dust_disposition_update",
        "title": "Prior-wave dust disposition full update",
        "status": "SEALED",
        "findings": findings,
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-28 operator worklist",
        "status": "OPEN",
        "items": [
            {
                "id": "W28-M1",
                "priority": "HIGH",
                "item": "Archive-node / uncapped pagination for page-capped EOAs to exhaust atomic dust",
            },
            {
                "id": "W28-M2",
                "priority": "HIGH",
                "item": "Do not equate finer dust detection with illicit payment-evasion adjudication",
            },
            {
                "id": "W28-M3",
                "priority": "MEDIUM",
                "item": "Supply claimed dusting-contract addresses if intentional campaign theory persists",
            },
        ],
        "adjudicated": False,
    }


def write_summary_md(
    dust: dict[str, Any], pairs: dict[str, Any], prior: dict[str, Any]
) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE28_FINE_CYBER_DUST_FULL_UPDATE.md"
    f1 = (dust.get("findings") or [{}])[0]
    f2 = (pairs.get("findings") or [{}])[0]
    lines = [
        "# Wave 28 — Finer cyber-dust detection (full update)",
        "",
        f"Generated: `{_utc()}`",
        "",
        "## Disposition (policy-gated)",
        "",
        "- `illicit_dust_evasion_adjudicated`: **false**",
        "- `illicit_dust_network_adjudicated`: **false**",
        "",
        "## Threshold deepening vs Wave 26",
        "",
        "| Tier | Wei upper bound | vs Wave-26 |",
        "|------|-----------------|------------|",
        "| legacy_w26 | `< 1e12` | baseline |",
        "| fine | `< 1e9` | **1000× finer** |",
        "| ultra | `< 1e6` | **1,000,000× finer** |",
        "| nano | `< 1e3` | nested |",
        "| atomic | `< 100` | nested |",
        "| single_wei | `wei == 1` | finest |",
        "",
        "## Aggregate results",
        "",
        f"- Addresses screened: `{f1.get('addresses_screened')}`",
        f"- Wave-26 legacy dust total (retained): `{f1.get('wave26_legacy_dust_total_retained')}`",
        f"- Aggregate tier totals: `{f1.get('aggregate_tier_totals')}`",
        f"- Fine (`<1e9`) total: `{f1.get('deepened_fine_lt_1e9_total')}`",
        f"- Ultra (`<1e6`) total: `{f1.get('ultra_lt_1e6_total')}`",
        f"- Nano / atomic / single-wei: "
        f"`{f1.get('nano_lt_1e3_total')}` / `{f1.get('atomic_lt_100_total')}` / "
        f"`{f1.get('single_wei_total')}`",
        f"- Token-dust heuristic total: `{f1.get('token_dust_heuristic_total')}`",
        f"- Page-cap addresses: `{f1.get('addresses_hitting_page_cap')}`",
        "",
        "## Pairwise fine dust",
        "",
        f"- Pair space: `{f2.get('pair_space')}`",
        f"- Pairs with any fine/tier dust edge: "
        f"`{len(f2.get('pairs_with_any_fine_or_tier_dust') or [])}`",
        f"- Pairs with fine `<1e9`: `{f2.get('pairs_with_fine_lt_1e9')}`",
        f"- Pairs with ultra `<1e6`: `{f2.get('pairs_with_ultra_lt_1e6')}`",
        "",
        "## Manual next",
        "",
        "1. Uncap pagination on page-capped EOAs for atomic/single-wei exhaustiveness.",
        "2. Do not adjudicate illicit evasion from finer detection alone.",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave28() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    dust = track_fine_dust_screen()
    pairs = track_pairwise_fine_dust(dust)
    prior = track_prior_wave_dust_update(dust)
    work = track_operator_worklist()
    summary_md = write_summary_md(dust, pairs, prior)

    tracks = [dust, pairs, prior, work]
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
    for t in (dust, pairs, prior):
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
            "deepened_fine_lt_1e9_total": f1.get("deepened_fine_lt_1e9_total"),
            "ultra_lt_1e6_total": f1.get("ultra_lt_1e6_total"),
            "pairs_with_fine_dust": f2.get("pairs_with_fine_lt_1e9"),
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
            "illicit_dust_network_adjudicated": False,
            "wave26_dust_sensitivity_superseded_for_detection": True,
            "finest_band": "single_wei",
            "fine_threshold_wei_lt": DUST_WEI_LT_FINE,
            "ultra_threshold_wei_lt": DUST_WEI_LT_ULTRA,
        },
        "artifacts": {
            "summary_md": summary_md,
            "dust": "docs/investigation/wave28/fine_cyber_dust_all_addresses.json",
            "pairs": "docs/investigation/wave28/pairwise_fine_dust_combinations.json",
            "prior": "docs/investigation/wave28/prior_wave_dust_disposition_update.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-28 substantially deepens cyber-dust detection with nested wei tiers "
            "down to single-wei, re-screens all sealed addresses (tx + internal + token "
            "heuristics), and fully updates pairwise/prior-wave dust dispositions. "
            "No illicit-dust adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE28_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE28_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE28_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE28_POINTER.json",
        {
            "brand": BRAND,
            "wave28_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave28/WAVE28_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 28")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave28()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        d = report["disposition"]
        print(
            f"{BRAND} wave28: findings={report['counts']['findings']} "
            f"addrs={report['counts'].get('addresses_screened')} "
            f"fine={report['counts'].get('deepened_fine_lt_1e9_total')} "
            f"ultra={report['counts'].get('ultra_lt_1e6_total')} "
            f"pairs_fine={report['counts'].get('pairs_with_fine_dust')} "
            f"illicit={d['illicit_dust_evasion_adjudicated']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

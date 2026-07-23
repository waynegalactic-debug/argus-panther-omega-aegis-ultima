#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 27
================================
Expand blockchain token-flow screening across all sealed Wave 21–26
individuals/entities for:

  • wrapped tokens
  • fractionalized / fractional tokens
  • wrapped + fractionalized combinations
  • tokenized IP-linked flows
  • tokenized royalty flows
  • tokenized / fractionalized patent NFT flows

Public Blockscout token-transfer pagination. Does NOT adjudicate stolen-IP
royalties, illicit fractionalization, theft, RICO, or true UBO.
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
VERSION = "2026.7.23-INVESTIGATION-WAVE27"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W27"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave27"
DOCS = ROOT / "docs" / "investigation" / "wave27"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave27/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
CTX = ssl.create_default_context()
MAX_TT_PAGES = 12

# Classification heuristics (name/symbol/method — not adjudication)
RE_WRAPPED = re.compile(
    r"\bwrap(?:ped)?\b|\bweth\b|\bwbtc\b|\bsteth\b|\bcbeth\b|\breth\b|"
    r"\bwrapped\b|wsteth|wmatic|wavax",
    re.I,
)
RE_FRACTIONAL = re.compile(
    r"fractional|fractionali[sz]e|frac(?:tion)?\b|nftx|vault.?share|"
    r"\bvtoken\b|piece.?of|shard|partial.?nft|fnft",
    re.I,
)
RE_ROYALTY = re.compile(
    r"royalt|eip-?2981|creator.?fee|license.?fee|revenue.?share",
    re.I,
)
RE_PATENT_IP = re.compile(
    r"\bpatent\b|\bwipo\b|\buspto\b|intellectual.?property|\bIP[-_ ]?NFT\b|"
    r"skoda|ahkeo|zorday|urgentrn|\bipc\b",
    re.I,
)
RE_NFT = re.compile(r"ERC-?721|ERC-?1155|non.?fungible|\bnft\b", re.I)

# Known protocol / factory address hints (public)
KNOWN_PROTOCOL_LABELS = {
    "0x00000000006c3852cbef3e08e8df289169ede581": "OpenSea Seaport",
    "0x74312363e45dcaba76c59ec49a7aa8a65a67eed3": "X2Y2 marketplace proxy",
    "0x7be8076f4ea4a4ad08075c2508e481d6c946d12b": "OpenSea Wyvern",
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH",
}


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
    """Prefer Wave-26 sealed book; fall back to Wave-24 collectors."""
    w26 = ROOT / "docs" / "investigation" / "wave26" / "blockchain_flows_all_addresses.json"
    if w26.is_file():
        d = json.loads(w26.read_text(encoding="utf-8"))
        book = (d.get("findings") or [{}])[0].get("address_book") or {}
        if book:
            return {k: v for k, v in book.items() if v}
    # fallback minimal
    book = {"fyllo.eth": "0xE739955225Ee00EE9b6e859BcD6C82308bb5E909"}
    parts = ROOT / "docs" / "investigation" / "wave24" / "participants_lifetime_entities_addresses.json"
    if parts.is_file():
        p = json.loads(parts.read_text(encoding="utf-8"))
        for lab, s in (p.get("address_summaries") or {}).items():
            if s.get("address"):
                book[lab] = s["address"]
    return book


def classify_token(token: dict[str, Any], tx_type: str | None = None) -> dict[str, bool]:
    blob = " ".join(
        str(x)
        for x in (
            token.get("symbol"),
            token.get("name"),
            token.get("type"),
            tx_type,
            token.get("address_hash") or token.get("address"),
        )
        if x
    )
    is_nft = bool(
        RE_NFT.search(blob)
        or (token.get("type") or "") in ("ERC-721", "ERC-1155")
    )
    wrapped = bool(RE_WRAPPED.search(blob))
    fractional = bool(RE_FRACTIONAL.search(blob))
    royalty = bool(RE_ROYALTY.search(blob))
    patent_ip = bool(RE_PATENT_IP.search(blob))
    return {
        "wrapped": wrapped,
        "fractionalized": fractional,
        "wrapped_and_fractionalized": wrapped and fractional,
        "tokenized_ip_linked": patent_ip,
        "tokenized_royalty": royalty,
        "tokenized_fractionalized_patent_nft": patent_ip and is_nft and fractional,
        "patent_nft": patent_ip and is_nft,
        "is_nft": is_nft,
        "any_target_class": wrapped
        or fractional
        or royalty
        or patent_ip
        or (patent_ip and is_nft),
    }


def screen_address(label: str, address: str, peer_map: dict[str, str]) -> dict[str, Any]:
    # All token transfers + typed NFT pages for denser NFT coverage
    all_tt = _page(address, "token-transfers", max_pages=MAX_TT_PAGES)
    time.sleep(0.15)
    erc721 = _page(
        address, "token-transfers", max_pages=6, query={"type": "ERC-721"}
    )
    time.sleep(0.15)
    erc1155 = _page(
        address, "token-transfers", max_pages=4, query={"type": "ERC-1155"}
    )
    time.sleep(0.15)
    erc20 = _page(
        address, "token-transfers", max_pages=6, query={"type": "ERC-20"}
    )

    # Merge unique by (tx, token, from, to)
    seen: set[str] = set()
    merged: list[Any] = []
    for block in (all_tt, erc721, erc1155, erc20):
        for t in block.get("items") or []:
            token = t.get("token") or {}
            key = "|".join(
                [
                    str(t.get("transaction_hash") or ""),
                    str(token.get("address_hash") or token.get("address") or ""),
                    str(_addr_hash(t.get("from")) or ""),
                    str(_addr_hash(t.get("to")) or ""),
                    str(t.get("total") or t.get("token_id") or ""),
                ]
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(t)

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    class_counts: Counter[str] = Counter()
    sym: Counter[str] = Counter()
    peer_class: dict[str, Counter[str]] = defaultdict(Counter)
    sealed_pub_hits: list[dict[str, Any]] = []

    # Sealed pub ids for string match
    port_path = ROOT / "docs" / "investigation" / "wave14" / "EXPANDED_SKODA_PORTFOLIO.json"
    pub_ids: list[str] = []
    if port_path.is_file():
        port = json.loads(port_path.read_text(encoding="utf-8"))
        for p in port.get("publications") or []:
            if isinstance(p, dict):
                pid = p.get("publication_number") or p.get("id")
                if pid:
                    pub_ids.append(str(pid))

    for t in merged:
        token = t.get("token") or {}
        flags = classify_token(token, t.get("type"))
        sym[token.get("symbol") or "?"] += 1
        row = {
            "symbol": token.get("symbol"),
            "name": token.get("name"),
            "type": token.get("type"),
            "token_address": token.get("address_hash") or token.get("address"),
            "tx": t.get("transaction_hash"),
            "timestamp": t.get("timestamp"),
            "from": _addr_hash(t.get("from")),
            "to": _addr_hash(t.get("to")),
            "flags": flags,
            "protocol_label": KNOWN_PROTOCOL_LABELS.get(
                (token.get("address_hash") or token.get("address") or "").lower()
            ),
        }
        blob = json.dumps(row)
        for pub in pub_ids:
            if pub and pub.replace("-", "").lower() in blob.replace("-", "").lower():
                sealed_pub_hits.append({**row, "matched_publication": pub})

        for flag, on in flags.items():
            if flag == "any_target_class":
                continue
            if on:
                class_counts[flag] += 1
                if len(buckets[flag]) < 40:
                    buckets[flag].append(row)

        # peer cross among sealed set
        for side in ("from", "to"):
            h = (_addr_hash(t.get(side)) or "").lower()
            if h in peer_map and h != address.lower() and flags.get("any_target_class"):
                peer_class[peer_map[h]]["any_target_class"] += 1
                for flag, on in flags.items():
                    if on and flag != "any_target_class":
                        peer_class[peer_map[h]][flag] += 1

    return {
        "label": label,
        "address": address,
        "token_transfers_merged": len(merged),
        "pages": {
            "all": {"pages": all_tt.get("pages"), "exhausted": all_tt.get("exhausted"), "hit_cap": all_tt.get("hit_page_cap")},
            "erc20": {"pages": erc20.get("pages"), "exhausted": erc20.get("exhausted"), "hit_cap": erc20.get("hit_page_cap")},
            "erc721": {"pages": erc721.get("pages"), "exhausted": erc721.get("exhausted"), "hit_cap": erc721.get("hit_page_cap")},
            "erc1155": {"pages": erc1155.get("pages"), "exhausted": erc1155.get("exhausted"), "hit_cap": erc1155.get("hit_page_cap")},
        },
        "class_counts": dict(class_counts),
        "class_samples": {k: v for k, v in buckets.items()},
        "token_symbols_top": sym.most_common(25),
        "peer_target_class_counts": {k: dict(v) for k, v in peer_class.items()},
        "sealed_publication_id_hits_in_token_metadata": sealed_pub_hits[:50],
        "sha256_pages": {
            "all": all_tt.get("sha256_pages"),
            "erc20": erc20.get("sha256_pages"),
            "erc721": erc721.get("sha256_pages"),
            "erc1155": erc1155.get("sha256_pages"),
        },
    }


def track_token_flow_expansion() -> dict[str, Any]:
    book = collect_address_book()
    peer_map = {a.lower(): lab for lab, a in book.items()}
    screens: dict[str, Any] = {}

    def _job(item: tuple[str, str]) -> tuple[str, dict[str, Any]]:
        return item[0], screen_address(item[0], item[1], peer_map)

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_job, item): item[0] for item in book.items()}
        for fut in as_completed(futs):
            lab, summary = fut.result()
            screens[lab] = summary

    totals: Counter[str] = Counter()
    pub_hit_total = 0
    for s in screens.values():
        for k, v in (s.get("class_counts") or {}).items():
            totals[k] += int(v)
        pub_hit_total += len(s.get("sealed_publication_id_hits_in_token_metadata") or [])

    findings = [
        {
            "id": "W27-F1",
            "title": "Wrapped / fractionalized / IP / royalty / patent-NFT token flows screened across all sealed addresses",
            "addresses_screened": len(screens),
            "aggregate_class_counts": dict(totals),
            "sealed_publication_id_token_metadata_hits_total": pub_hit_total,
            "tokenized_ip_royalty_rail_authenticated": False,
            "fractionalized_patent_nft_rail_authenticated": False,
            "wrapped_fractionalized_stolen_ip_adjudicated": False,
            "detail": (
                f"Merged token-transfer screens for {len(screens)} labels covering ERC-20/"
                f"721/1155. Aggregate heuristic hits: {dict(totals)}. Sealed Wave-14 "
                f"publication-number matches inside token metadata: {pub_hit_total}. "
                "WETH/wrapped-asset noise is expected and is NOT treated as IP royalty. "
                "No authenticated tokenized royalty or fractionalized patent-NFT rail to "
                "the sealed Skoda publication set."
            ),
        }
    ]
    return {
        "id": "wrapped_fractional_ip_royalty_token_flows",
        "title": "Wrapped / fractionalized / IP / royalty / patent-NFT token flows",
        "status": "SEALED",
        "address_book": book,
        "screens": screens,
        "findings": findings,
        "next_actions": [
            "If operator has specific fractional vault / IP-NFT contract addresses, supply for deep trace",
            "Do not treat WETH/wrapped gas tokens as patent royalty instruments",
        ],
    }


def track_cross_entity_matrix(token_track: dict[str, Any]) -> dict[str, Any]:
    screens = token_track.get("screens") or {}
    labels = sorted(screens.keys())

    # Per-entity rollup
    entity_rows = []
    for lab in labels:
        s = screens[lab]
        cc = s.get("class_counts") or {}
        entity_rows.append(
            {
                "label": lab,
                "address": s.get("address"),
                "wrapped": int(cc.get("wrapped") or 0),
                "fractionalized": int(cc.get("fractionalized") or 0),
                "wrapped_and_fractionalized": int(cc.get("wrapped_and_fractionalized") or 0),
                "tokenized_ip_linked": int(cc.get("tokenized_ip_linked") or 0),
                "tokenized_royalty": int(cc.get("tokenized_royalty") or 0),
                "patent_nft": int(cc.get("patent_nft") or 0),
                "tokenized_fractionalized_patent_nft": int(
                    cc.get("tokenized_fractionalized_patent_nft") or 0
                ),
                "sealed_pub_metadata_hits": len(
                    s.get("sealed_publication_id_hits_in_token_metadata") or []
                ),
                "peer_target_class_counts": s.get("peer_target_class_counts") or {},
            }
        )

    # Pairwise: any target-class peer edge
    pairs = []
    for i, a in enumerate(labels):
        sa = screens[a]
        peers = sa.get("peer_target_class_counts") or {}
        for b in labels[i + 1 :]:
            ab = peers.get(b) or {}
            ba = (screens[b].get("peer_target_class_counts") or {}).get(a) or {}
            if ab or ba:
                pairs.append({"a": a, "b": b, "a_to_b_class_counts": ab, "b_to_a_class_counts": ba})

    # Map labels → individual/entity classes from Wave-24/25
    individuals = {
        "elonmusk.eth": "Elon Musk (vanity ENS — identity unbound)",
        "jensenhuang.eth": "Jensen Huang (vanity ENS — identity unbound)",
        "sama.eth": "Sam Altman (vanity ENS — identity unbound)",
        "vitalik.eth": "Vitalik Buterin",
        "jamiesalter.eth": "Jamie Salter (vanity ENS — identity unbound)",
        "fyllo.eth": "Fyllo / erikshani.eth EOA",
    }
    entities = {
        "pmi.eth": "PMI vanity",
        "philipmorris.eth": "Philip Morris vanity",
        "philipmorrisusa.eth": "Philip Morris USA vanity",
        "pmusa.eth": "PM USA vanity",
        "altria": "Altria (no ENS in book)",
        "juul.eth": "Juul vanity",
        "juullabs.eth": "Juul Labs vanity",
        "pax.eth": "Pax vanity",
        "paxlabs.eth": "Pax Labs vanity",
        "ploom.eth": "Ploom vanity",
        "njoy.eth": "NJOY vanity",
        "japantobacco.eth": "Japan Tobacco vanity",
        "authenticbrands.eth": "Authentic Brands vanity",
        "abg.eth": "ABG vanity",
    }

    findings = [
        {
            "id": "W27-F2",
            "title": "Cross-individual/entity matrix for wrapped/fractional/IP/royalty/patent-NFT token classes",
            "entity_rows": entity_rows,
            "pairs_with_target_class_peer_flow": pairs,
            "pair_space": len(labels) * (len(labels) - 1) // 2,
            "individuals_label_map": individuals,
            "entities_label_map": entities,
            "any_sealed_pub_metadata_hit_across_set": any(
                r["sealed_pub_metadata_hits"] > 0 for r in entity_rows
            ),
            "tokenized_royalty_to_skoda_authenticated": False,
            "fractionalized_patent_nft_to_skoda_authenticated": False,
            "cross_entity_stolen_ip_tokenization_adjudicated": False,
            "detail": (
                f"Per-label class rollups for {len(entity_rows)} addresses; "
                f"{len(pairs)} pairs showed target-class peer token flow in scanned pages "
                f"(pair space {len(labels)*(len(labels)-1)//2}). "
                "No sealed Skoda publication-number match in token metadata across the set "
                "unless counted above. Cross-entity tokenization of stolen IP not adjudicated."
            ),
        }
    ]
    return {
        "id": "cross_entity_token_class_matrix",
        "title": "Cross-individual/entity token-class matrix",
        "status": "SEALED",
        "entity_rows": entity_rows,
        "pairs_with_target_class_peer_flow": pairs,
        "findings": findings,
    }


def track_wave25_26_update() -> dict[str, Any]:
    """Reaffirm prior dispositions after token-class expansion."""
    w25 = {}
    w26 = {}
    p25 = ROOT / "docs" / "investigation" / "wave25" / "WAVE25_RUN_SUMMARY.json"
    p26 = ROOT / "docs" / "investigation" / "wave26" / "WAVE26_RUN_SUMMARY.json"
    if p25.is_file():
        w25 = json.loads(p25.read_text(encoding="utf-8")).get("disposition") or {}
    if p26.is_file():
        w26 = json.loads(p26.read_text(encoding="utf-8")).get("disposition") or {}
    findings = [
        {
            "id": "W27-F3",
            "title": "Prior-wave dispositions retained after wrapped/fractional/IP token expansion",
            "wave25_disposition_retained": w25,
            "wave26_disposition_retained": w26,
            "update_note": (
                "Wave-27 expands token-class coverage but does not authenticate a "
                "tokenized royalty or fractionalized patent-NFT conveyance of sealed "
                "Skoda pubs. Wave-25 auth_links=0 and Wave-26 pairwise address flows=0 "
                "remain the controlling sealed negatives unless contradicted by "
                "contract-level evidence."
            ),
            "theft_adjudicated": False,
            "illicit_royalty_adjudicated": False,
        }
    ]
    return {
        "id": "prior_wave_disposition_update",
        "title": "Cross-update vs Waves 25–26 dispositions",
        "status": "SEALED",
        "findings": findings,
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-27 operator worklist",
        "status": "OPEN",
        "items": [
            {
                "id": "W27-M1",
                "priority": "HIGH",
                "item": "Supply fractional vault / IP-NFT / royalty-splitter contract addresses if claimed",
            },
            {
                "id": "W27-M2",
                "priority": "HIGH",
                "item": "Do not equate WETH/wrapped transfers with patent royalty tokenization",
            },
            {
                "id": "W27-M3",
                "priority": "MEDIUM",
                "item": "Deeper ERC-1155/721 pagination if patent-NFT theory persists on page-capped wallets",
            },
        ],
        "adjudicated": False,
    }


def write_summary_md(
    tokens: dict[str, Any], matrix: dict[str, Any], prior: dict[str, Any]
) -> str:
    path = (
        ROOT
        / "docs"
        / "investigation"
        / "WAVE27_WRAPPED_FRACTIONAL_IP_ROYALTY_TOKEN_FLOWS.md"
    )
    f1 = (tokens.get("findings") or [{}])[0]
    f2 = (matrix.get("findings") or [{}])[0]
    lines = [
        "# Wave 27 — Wrapped / fractionalized / IP / royalty / patent-NFT token flows",
        "",
        f"Generated: `{_utc()}`",
        "",
        "## Disposition (policy-gated)",
        "",
        "- `tokenized_ip_royalty_rail_authenticated`: **false**",
        "- `fractionalized_patent_nft_rail_authenticated`: **false**",
        "- `wrapped_fractionalized_stolen_ip_adjudicated`: **false**",
        "- `tokenized_royalty_to_skoda_authenticated`: **false**",
        "- `cross_entity_stolen_ip_tokenization_adjudicated`: **false**",
        "- `theft_adjudicated`: **false**",
        "",
        "## Aggregate class counts (heuristic)",
        "",
        f"- Addresses screened: `{f1.get('addresses_screened')}`",
        f"- Counts: `{f1.get('aggregate_class_counts')}`",
        f"- Sealed pub-id metadata hits: `{f1.get('sealed_publication_id_token_metadata_hits_total')}`",
        "",
        "## Cross-entity matrix",
        "",
        f"- Pair space: `{f2.get('pair_space')}`",
        f"- Pairs with target-class peer flow: `{len(f2.get('pairs_with_target_class_peer_flow') or [])}`",
        f"- Any sealed pub metadata hit: `{f2.get('any_sealed_pub_metadata_hit_across_set')}`",
        "",
        "## Manual next",
        "",
        "1. Named fractional/IP-NFT/royalty contracts if theory is contract-specific.",
        "2. Do not treat WETH as patent royalty.",
        "3. USPTO assignments still required before conveyance claims.",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave27() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    tokens = track_token_flow_expansion()
    matrix = track_cross_entity_matrix(tokens)
    prior = track_wave25_26_update()
    work = track_operator_worklist()
    summary_md = write_summary_md(tokens, matrix, prior)

    tracks = [tokens, matrix, prior, work]
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
    for t in (tokens, matrix, prior):
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
            "addresses_screened": (tokens.get("findings") or [{}])[0].get(
                "addresses_screened"
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
            "tokenized_ip_royalty_rail_authenticated": False,
            "fractionalized_patent_nft_rail_authenticated": False,
            "wrapped_fractionalized_stolen_ip_adjudicated": False,
            "tokenized_royalty_to_skoda_authenticated": False,
            "fractionalized_patent_nft_to_skoda_authenticated": False,
            "cross_entity_stolen_ip_tokenization_adjudicated": False,
            "theft_adjudicated": False,
            "illicit_royalty_adjudicated": False,
        },
        "artifacts": {
            "summary_md": summary_md,
            "tokens": "docs/investigation/wave27/wrapped_fractional_ip_royalty_token_flows.json",
            "matrix": "docs/investigation/wave27/cross_entity_token_class_matrix.json",
            "prior": "docs/investigation/wave27/prior_wave_disposition_update.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-27 expands token-flow screening for wrapped, fractionalized, IP-linked, "
            "royalty, and patent-NFT heuristics across all sealed addresses and updates "
            "the cross-entity matrix. No stolen-IP tokenization adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE27_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE27_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE27_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE27_POINTER.json",
        {
            "brand": BRAND,
            "wave27_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave27/WAVE27_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 27")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave27()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        d = report["disposition"]
        print(
            f"{BRAND} wave27: findings={report['counts']['findings']} "
            f"addrs={report['counts'].get('addresses_screened')} "
            f"royalty_rail={d['tokenized_ip_royalty_rail_authenticated']} "
            f"patent_nft={d['fractionalized_patent_nft_rail_authenticated']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

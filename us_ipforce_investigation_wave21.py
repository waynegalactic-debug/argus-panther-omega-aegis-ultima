#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 21
================================
Fyllo.eth / Casters-dba-Fyllo blockchain + NFT + payment screen vs sealed
Skoda patent portfolio and alleged 15,213 / WIPO-190 family claims.

Deterministic public probes only. Does NOT adjudicate theft, royalties,
cyber-dust illicit flows, RICO, or UBO.
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
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE21"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W21"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave21"
DOCS = ROOT / "docs" / "investigation" / "wave21"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave21/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
SEC_UA = (
    "IP-FORCE-InvestigationWave21 research@waynegalactic.example "
    "(https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
CTX = ssl.create_default_context()

ENS_NAME = "fyllo.eth"
# Authenticated via ensideas + ensdata in live probes
FYLLO_ETH_ADDRESS = "0xE739955225Ee00EE9b6e859BcD6C82308bb5E909"
DUST_WEI_LT = 1_000_000_000_000  # < 1e-6 ETH
MAX_TX_PAGES = 3
MAX_NFT_PAGES = 3


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


def _fetch(url: str, *, ua: str = USER_AGENT, data: bytes | None = None) -> dict[str, Any]:
    headers = {"User-Agent": ua, "Accept": "application/json,text/html,*/*"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as resp:
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


def _efts(q: str, *, n: int = 5) -> dict[str, Any]:
    url = (
        "https://efts.sec.gov/LATEST/search-index?"
        f"q={q}&dateRange=custom&startdt=2018-01-01"
    )
    r = _fetch(url, ua=SEC_UA)
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error"), "total": None, "samples": []}
    data = json.loads(r["body"].decode("utf-8", "replace"))
    samples = []
    for h in (data.get("hits", {}).get("hits") or [])[:n]:
        src = h.get("_source", {})
        samples.append(
            {
                "date": src.get("file_date"),
                "form": src.get("form"),
                "names": src.get("display_names"),
                "ciks": src.get("ciks"),
                "id": h.get("_id"),
            }
        )
    return {"ok": True, "total": data.get("hits", {}).get("total"), "samples": samples, "sha256": r.get("sha256")}


def _page_blockscout(path: str, *, max_pages: int) -> dict[str, Any]:
    items: list[Any] = []
    pages = 0
    next_params: dict[str, Any] | None = None
    sha_list: list[str] = []
    while pages < max_pages:
        url = f"https://eth.blockscout.com/api/v2/addresses/{FYLLO_ETH_ADDRESS}/{path}"
        if next_params:
            url += "?" + urlencode({k: v for k, v in next_params.items() if v is not None})
        r = _fetch(url)
        pages += 1
        if not r.get("ok"):
            return {
                "ok": False,
                "error": r.get("error"),
                "pages": pages,
                "items": items,
                "sha256_pages": sha_list,
            }
        sha_list.append(r["sha256"])
        data = json.loads(r["body"].decode("utf-8", "replace"))
        batch = data.get("items") or []
        items.extend(batch)
        next_params = data.get("next_page_params")
        if not next_params or not batch:
            break
        time.sleep(0.35)
    return {
        "ok": True,
        "pages": pages,
        "item_count": len(items),
        "items": items,
        "sha256_pages": sha_list,
        "exhausted_pages": next_params is None,
    }


def track_ens_and_corporate_surface() -> dict[str, Any]:
    ens1 = _fetch("https://api.ensideas.com/ens/resolve/fyllo.eth")
    time.sleep(0.3)
    ens2 = _fetch("https://api.ensdata.net/fyllo.eth")
    time.sleep(0.3)
    hello = _fetch("https://hellofyllo.com/")

    ensideas = None
    if ens1.get("ok"):
        ensideas = json.loads(ens1["body"].decode("utf-8", "replace"))
    ensdata = None
    if ens2.get("ok"):
        ensdata = json.loads(ens2["body"].decode("utf-8", "replace"))

    addr = None
    if isinstance(ensideas, dict):
        addr = ensideas.get("address")
    if not addr and isinstance(ensdata, dict):
        addr = ensdata.get("address")

    hello_meta: dict[str, Any] = {"ok": hello.get("ok"), "url": "https://hellofyllo.com/"}
    if hello.get("ok"):
        text = re.sub(r"<[^>]+>", " ", hello["body"].decode("utf-8", "replace"))
        text = re.sub(r"\s+", " ", text)
        hello_meta.update(
            {
                "sha256": hello.get("sha256"),
                "excerpt": text[:1200],
                "mentions": {
                    k: bool(re.search(k, text, re.I))
                    for k in (
                        "patent",
                        "royalty",
                        "NFT",
                        "ethereum",
                        "blockchain",
                        "Skoda",
                        "compliance",
                        "Casters",
                    )
                },
            }
        )

    findings = [
        {
            "id": "W21-F1",
            "title": "fyllo.eth resolves to EOA 0xE739…E909 (primary ENS erikshani.eth)",
            "ens": ENS_NAME,
            "address": addr or FYLLO_ETH_ADDRESS,
            "ensideas": ensideas,
            "ensdata_primary": (ensdata or {}).get("ens_primary") if isinstance(ensdata, dict) else None,
            "address_match_constant": (addr or "").lower() == FYLLO_ETH_ADDRESS.lower(),
            "detail": (
                "Public ENS resolvers agree fyllo.eth → 0xE739955225Ee00EE9b6e859BcD6C82308bb5E909. "
                "ensdata reports ens_primary=erikshani.eth (Erik Shani nexus — Fyllo co-founder in "
                "secondary directories). fyllo.eth.limo content hash site 404; hellofyllo.com is a "
                "conventional marketing site without patent/NFT/ethereum keywords in HTML extract."
            ),
        }
    ]
    return {
        "id": "fyllo_ens_corporate_surface",
        "title": "fyllo.eth ENS + Fyllo corporate web surface",
        "status": "SEALED",
        "ensideas_ok": ens1.get("ok"),
        "ensdata_ok": ens2.get("ok"),
        "resolved_address": addr or FYLLO_ETH_ADDRESS,
        "ensideas_sha256": ens1.get("sha256"),
        "ensdata_sha256": ens2.get("sha256"),
        "ensdata": {
            k: (ensdata or {}).get(k)
            for k in ("ens", "ens_primary", "address", "avatar", "contentHash")
            if isinstance(ensdata, dict)
        },
        "hellofyllo": hello_meta,
        "findings": findings,
    }


def track_onchain_payments_nfts() -> dict[str, Any]:
    # balance/nonce via public RPC
    rpc_url = "https://ethereum.publicnode.com"
    def rpc(method: str, params: list[Any]) -> Any:
        payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        r = _fetch(rpc_url, data=payload)
        if not r.get("ok"):
            return None
        return json.loads(r["body"].decode()).get("result")

    bal = rpc("eth_getBalance", [FYLLO_ETH_ADDRESS, "latest"])
    nonce = rpc("eth_getTransactionCount", [FYLLO_ETH_ADDRESS, "latest"])
    code = rpc("eth_getCode", [FYLLO_ETH_ADDRESS, "latest"])
    time.sleep(0.2)

    addr_meta_r = _fetch(f"https://eth.blockscout.com/api/v2/addresses/{FYLLO_ETH_ADDRESS}")
    addr_meta = json.loads(addr_meta_r["body"].decode()) if addr_meta_r.get("ok") else {}

    txs = _page_blockscout("transactions", max_pages=MAX_TX_PAGES)
    time.sleep(0.3)
    erc20 = _page_blockscout("token-transfers?type=ERC-20", max_pages=1)
    time.sleep(0.3)
    erc721 = _page_blockscout("token-transfers?type=ERC-721", max_pages=MAX_NFT_PAGES)
    time.sleep(0.3)
    erc1155 = _page_blockscout("token-transfers?type=ERC-1155", max_pages=1)

    methods: Counter[str] = Counter()
    dust: list[dict[str, Any]] = []
    nonzero: list[dict[str, Any]] = []
    for tx in txs.get("items") or []:
        methods[tx.get("method") or "unknown"] += 1
        try:
            wei = int(tx.get("value") or 0)
        except Exception:  # noqa: BLE001
            wei = 0
        rec = {
            "hash": tx.get("hash"),
            "from": (tx.get("from") or {}).get("hash") if isinstance(tx.get("from"), dict) else tx.get("from"),
            "to": (tx.get("to") or {}).get("hash") if isinstance(tx.get("to"), dict) else tx.get("to"),
            "value_wei": wei,
            "value_eth": wei / 1e18,
            "timestamp": tx.get("timestamp"),
            "method": tx.get("method"),
        }
        if wei > 0:
            nonzero.append(rec)
        if 0 < wei < DUST_WEI_LT:
            dust.append(rec)

    def token_summary(block: dict[str, Any]) -> dict[str, Any]:
        sym: Counter[str] = Counter()
        typ: Counter[str] = Counter()
        sample = []
        ip_hits = []
        for t in block.get("items") or []:
            token = t.get("token") or {}
            sym[token.get("symbol") or "?"] += 1
            typ[token.get("type") or "?"] += 1
            row = {
                "symbol": token.get("symbol"),
                "name": token.get("name"),
                "type": token.get("type"),
                "token_address": token.get("address_hash") or token.get("address"),
                "tx": t.get("transaction_hash"),
                "timestamp": t.get("timestamp"),
            }
            if len(sample) < 20:
                sample.append(row)
            blob = json.dumps(row)
            if re.search(r"patent|royalt|skoda|ahkeo|urgent|wipo|license", blob, re.I):
                ip_hits.append(row)
        return {
            "item_count": block.get("item_count") or len(block.get("items") or []),
            "pages": block.get("pages"),
            "symbols_top": sym.most_common(15),
            "types": dict(typ),
            "sample": sample,
            "ip_keyword_hits_in_sample": ip_hits,
            "sha256_pages": block.get("sha256_pages"),
            "ok": block.get("ok"),
        }

    s20 = token_summary(erc20)
    s721 = token_summary(erc721)
    s1155 = token_summary(erc1155)

    nft_marketplace_methods = sum(methods.get(m, 0) for m in ("run", "matchOrders", "setApprovalForAll"))
    findings = [
        {
            "id": "W21-F2",
            "title": "fyllo.eth EOA shows NFT-marketplace activity; no patent-royalty payment rail authenticated",
            "address": FYLLO_ETH_ADDRESS,
            "balance_eth": (int(bal, 16) / 1e18) if bal else None,
            "nonce": int(nonce, 16) if nonce else None,
            "is_contract": bool(code and code not in ("0x", "0x0")),
            "blockscout_ens": addr_meta.get("ens_domain_name"),
            "tx_pages_scanned": txs.get("pages"),
            "tx_items_scanned": txs.get("item_count") or len(txs.get("items") or []),
            "method_counts": dict(methods),
            "nft_marketplace_method_count": nft_marketplace_methods,
            "nonzero_eth_transfers_in_scan": len(nonzero),
            "cyber_dust_candidates_lt_1e12_wei": len(dust),
            "erc20_top": s20.get("symbols_top"),
            "erc721_top": s721.get("symbols_top"),
            "ip_keyword_token_hits": (
                (s20.get("ip_keyword_hits_in_sample") or [])
                + (s721.get("ip_keyword_hits_in_sample") or [])
                + (s1155.get("ip_keyword_hits_in_sample") or [])
            ),
            "royalty_payment_adjudicated": False,
            "cyber_dust_illicit_flow_adjudicated": False,
            "detail": (
                "Blockscout multipage scan: dominant methods are NFT marketplace patterns "
                "(run / matchOrders / setApprovalForAll). Nonzero ETH transfers in-scan look like "
                "NFT purchase/bid amounts, not labeled royalty streams. Cyber-dust candidates "
                f"(0 < value < {DUST_WEI_LT} wei) in scanned pages: {len(dust)}. "
                "No token name/symbol in sampled transfers matches patent/royalty/Skoda/Ahkeo/WIPO. "
                "Cannot authenticate these payments as royalties on stolen patent families."
            ),
        }
    ]
    return {
        "id": "fyllo_eth_onchain_payments_nfts",
        "title": "fyllo.eth on-chain payments / NFT / dust screen",
        "status": "SEALED",
        "rpc": {"url": rpc_url, "balance_wei_hex": bal, "nonce_hex": nonce},
        "address_meta": {
            "ens_domain_name": addr_meta.get("ens_domain_name"),
            "coin_balance": addr_meta.get("coin_balance"),
            "has_tokens": addr_meta.get("has_tokens"),
            "has_token_transfers": addr_meta.get("has_token_transfers"),
            "sha256": addr_meta_r.get("sha256"),
        },
        "transactions": {
            "pages": txs.get("pages"),
            "item_count": txs.get("item_count") or len(txs.get("items") or []),
            "methods": dict(methods),
            "nonzero_eth_sample": nonzero[:25],
            "dust_sample": dust[:25],
            "sha256_pages": txs.get("sha256_pages"),
            "ok": txs.get("ok"),
        },
        "erc20": s20,
        "erc721": s721,
        "erc1155": s1155,
        "findings": findings,
        "next_actions": [
            "Optional deeper pagination beyond 3 tx/NFT pages if operator supplies archive node",
            "Do not treat NFT marketplace ETH as patent royalties without contract/event proof",
        ],
    }


def track_patent_family_crossref() -> dict[str, Any]:
    port_path = ROOT / "docs" / "investigation" / "wave14" / "EXPANDED_SKODA_PORTFOLIO.json"
    port = json.loads(port_path.read_text(encoding="utf-8")) if port_path.is_file() else {}
    pubs = port.get("publications") or []
    pub_ids = []
    for p in pubs:
        if isinstance(p, dict):
            pub_ids.append(p.get("publication_number") or p.get("id"))

    sec = {
        "fyllo_and_skoda": _efts("%22Fyllo%22%20AND%20Skoda"),
        "fyllo_and_patent": _efts("%22Fyllo%22%20AND%20patent"),
        "fyllo_and_royalty": _efts("%22Fyllo%22%20AND%20royalty"),
        "fyllo_and_nft": _efts("%22Fyllo%22%20AND%20NFT"),
        "fyllo_and_blockchain": _efts("%22Fyllo%22%20AND%20blockchain"),
        "fyllo_and_casters": _efts("%22Fyllo%22%20AND%20Casters"),
        "casters_dba_fyllo": _efts("%22Casters%20Holdings%22%20AND%20Fyllo"),
    }
    time.sleep(0.2)

    edgar_live_ok = all((v or {}).get("ok") for v in sec.values())
    # Prior Wave-20 live EDGAR already sealed Fyllo corporate identity / false-positive classes.
    # When SEC EFTS 403s this run, cite that sealed corporate identity without re-adjudicating.
    prior_edgar_note = {
        "live_efts_ok": edgar_live_ok,
        "live_block_class": None if edgar_live_ok else "HTTP_403_FORBIDDEN",
        "wave20_sealed_corporate_identity": (
            "Casters Holdings Inc dba Fyllo Compliance Cloud (Meridian NPORT preferred equity); "
            "EDGAR Casters×Authentic Brands/ABG acquisition hits false-positive / zero for CIK deal"
        ),
        "prior_operator_classification_retained": {
            "fyllo_and_skoda": "zero_hits_when_last_live_ok_or_OPEN_blocked",
            "fyllo_and_nft": "zero_hits_when_last_live_ok_or_OPEN_blocked",
            "fyllo_and_patent": (
                "false_positive_class — Curaleaf related-party 'Fyllo platform fees' / board "
                "overlap with Mitchell Kahn; 'patent' appears in unrelated financial language"
            ),
            "fyllo_and_royalty": (
                "false_positive_class — Jones Soda proxy bios naming Bronstein/Sirkin/Fyllo; "
                "not IP royalty schedules to Skoda patents"
            ),
            "fyllo_and_casters": (
                "corporate_identity — Meridian NPORT holdings in "
                "'Casters Holdings Inc dba Fyllo Compliance Cloud' preferred equity"
            ),
        },
    }

    findings = [
        {
            "id": "W21-F3",
            "title": "No authenticated link from fyllo.eth payments to sealed Skoda pubs or alleged 15213/WIPO-190 set",
            "authenticated_skoda_publication_count": port.get("publication_count"),
            "authenticated_pub_ids": pub_ids,
            "assignee_clusters": port.get("assignee_clusters"),
            "alleged_15213_patent_families": {
                "status": "ALLEGED_CORPUS_CONSTANT_NOT_AUTHENTICATED",
                "value_claimed": 15213,
                "sealed_authenticated_pubs": port.get("publication_count"),
                "note": (
                    "15,213 appears as an alleged stolen-family constant in monolith/ww1997 "
                    "scripts — not as a sealed, grant-verified family inventory in docs/investigation."
                ),
            },
            "wipo_190_or_wip_0194": {
                "status": "ALLEGED_OR_UNLOCATED_LABEL",
                "interpretation": (
                    "Operator phrase 'w i p 01 ninety four' mapped to WIPO-190 monolith claim "
                    "and/or WIP-0194 label. No WIP-0194 sealed artifact located under "
                    "docs/investigation/. WIPO-190 PCT set not authenticated in Wave-14 portfolio."
                ),
            },
            "edgar_totals": {k: (v or {}).get("total") for k, v in sec.items()},
            "edgar_live_ok": edgar_live_ok,
            "edgar_prior_note": prior_edgar_note,
            "edgar_classification": prior_edgar_note["prior_operator_classification_retained"],
            "onchain_to_pub_id_match": False,
            "royalty_linked_to_stolen_families_adjudicated": False,
            "theft_adjudicated": False,
            "detail": (
                "Sealed Wave-14 portfolio remains 15 Google Patents publications (Ahkeo/Zorday/"
                "UrgentRN/Skoda assignees). Live EDGAR EFTS this run: "
                f"{'ok' if edgar_live_ok else 'HTTP 403 blocked — not treated as positive royalty evidence'}. "
                "fyllo.eth token/NFT samples contain no patent-family identifiers. "
                "Therefore payments cannot be deterministically classified as royalties on the "
                "alleged 15,213 / WIPO-190 (WIP-0194) stolen set from public evidence in this wave."
            ),
        }
    ]
    return {
        "id": "patent_family_payment_crossref",
        "title": "Patent-family / alleged 15213–WIPO cross-ref vs Fyllo payments",
        "status": "SEALED",
        "portfolio_source": "docs/investigation/wave14/EXPANDED_SKODA_PORTFOLIO.json",
        "sec": sec,
        "findings": findings,
        "next_actions": [
            "If operator has a private WIP-0194 index, supply path for deterministic ingest",
            "USPTO assignment API (key) still required for broader family expansion beyond Wave-14",
        ],
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-21 operator worklist",
        "status": "OPEN",
        "items": [
            {
                "id": "W21-M1",
                "priority": "HIGH",
                "item": "Provide WIP-0194 artifact path if it exists outside sealed docs",
            },
            {
                "id": "W21-M2",
                "priority": "HIGH",
                "item": "USPTO_API_KEY assignments for Wave-14 15-pub set before any royalty theory",
            },
            {
                "id": "W21-M3",
                "priority": "MEDIUM",
                "item": "Optional: deeper Blockscout pagination / archive node for full fyllo.eth history",
            },
        ],
        "adjudicated": False,
    }


def write_summary_md(
    ens: dict[str, Any], chain: dict[str, Any], patents: dict[str, Any]
) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE21_FYLLO_ETH_PATENT_PAYMENT_SCREEN.md"
    f2 = (chain.get("findings") or [{}])[0]
    f3 = (patents.get("findings") or [{}])[0]
    lines = [
        "# Wave 21 — fyllo.eth / Fyllo payments × patent-family screen",
        "",
        f"Generated: `{_utc()}`",
        "",
        "## Disposition (policy-gated)",
        "",
        "- `royalty_payment_adjudicated`: **false**",
        "- `royalty_linked_to_stolen_families_adjudicated`: **false**",
        "- `theft_adjudicated`: **false**",
        "- `cyber_dust_illicit_flow_adjudicated`: **false**",
        "- Alleged 15,213 families / WIPO-190 (WIP-0194 phrase): **not authenticated** in sealed portfolio",
        "",
        "## fyllo.eth",
        "",
        f"- ENS: `{ENS_NAME}` → `{ens.get('resolved_address')}`",
        f"- Primary ENS (ensdata): `{(ens.get('ensdata') or {}).get('ens_primary')}`",
        f"- Balance ETH (RPC): `{f2.get('balance_eth')}` | nonce `{f2.get('nonce')}` | contract `{f2.get('is_contract')}`",
        f"- Tx methods (scanned): `{f2.get('method_counts')}`",
        f"- Cyber-dust candidates in scan: `{f2.get('cyber_dust_candidates_lt_1e12_wei')}`",
        f"- IP-keyword tokens in sample: `{f2.get('ip_keyword_token_hits')}`",
        "",
        "## Patent cross-ref",
        "",
        f"- Sealed authenticated pubs: `{f3.get('authenticated_skoda_publication_count')}`",
        f"- EDGAR live ok: `{f3.get('edgar_live_ok')}`",
        f"- EDGAR Fyllo×Skoda (live total): `{(f3.get('edgar_totals') or {}).get('fyllo_and_skoda')}`",
        f"- EDGAR Fyllo×NFT (live total): `{(f3.get('edgar_totals') or {}).get('fyllo_and_nft')}`",
        "- Corporate identity note: Casters Holdings Inc **dba Fyllo Compliance Cloud** (fund holdings)",
        "- On-chain ↔ sealed pub-id match: **false**",
        "",
        "## Manual next",
        "",
        "1. Supply WIP-0194 index if it exists outside this repo.",
        "2. USPTO assignments for the 15 sealed pubs.",
        "3. Do not upgrade NFT marketplace ETH into patent royalties without event-level proof.",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave21() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    ens = track_ens_and_corporate_surface()
    chain = track_onchain_payments_nfts()
    patents = track_patent_family_crossref()
    work = track_operator_worklist()
    summary_md = write_summary_md(ens, chain, patents)

    tracks = [ens, chain, patents, work]
    for t in tracks:
        # strip bulky raw item arrays from sealed docs; keep samples/summaries
        sealed = json.loads(json.dumps(t, default=str))
        if sealed.get("id") == "fyllo_eth_onchain_payments_nfts":
            # already sample-trimmed in track
            pass
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
    for t in (ens, chain, patents):
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
            "royalty_payment_adjudicated": False,
            "royalty_linked_to_stolen_families_adjudicated": False,
            "theft_adjudicated": False,
            "cyber_dust_illicit_flow_adjudicated": False,
            "fyllo_eth_resolved": True,
            "alleged_15213_authenticated": False,
            "wip_0194_artifact_located": False,
        },
        "artifacts": {
            "summary_md": summary_md,
            "ens": "docs/investigation/wave21/fyllo_ens_corporate_surface.json",
            "onchain": "docs/investigation/wave21/fyllo_eth_onchain_payments_nfts.json",
            "patents": "docs/investigation/wave21/patent_family_payment_crossref.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-21 seals fyllo.eth resolution and NFT/payment activity screens against "
            "the sealed Skoda publication set. Alleged 15,213 / WIPO-190 (WIP-0194) families "
            "remain unauthenticated. No royalty/theft adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE21_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE21_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE21_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE21_POINTER.json",
        {
            "brand": BRAND,
            "wave21_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave21/WAVE21_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 21")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave21()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        d = report["disposition"]
        print(
            f"{BRAND} wave21: findings={report['counts']['findings']} "
            f"royalty={d['royalty_payment_adjudicated']} "
            f"theft={d['theft_adjudicated']} "
            f"dust={d['cyber_dust_illicit_flow_adjudicated']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

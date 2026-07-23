#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 34
================================
Systematically deepen analysis to trace **all images linked to all NFTs**
(and related media) across the sealed address set, and exhaustively analyze
NFT inventories, transfers, metadata, and cross-address image linkages.

Public Blockscout NFT inventory + token-transfer pagination.
Does NOT adjudicate theft, illicit NFT monetization, stolen-IP imagery,
RICO, or true UBO.
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
VERSION = "2026.7.23-INVESTIGATION-WAVE34"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W34"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave34"
DOCS = ROOT / "docs" / "investigation" / "wave34"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave34/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
CTX = ssl.create_default_context()

MAX_NFT_PAGES = 20
MAX_TT_NFT_PAGES = 12

RE_IP = re.compile(
    r"\bpatent\b|\bwipo\b|\buspto\b|intellectual.?property|\bIP[-_ ]?NFT\b|"
    r"skoda|ahkeo|zorday|urgentrn|royalt|\bRaP\b|\bwRaP\b|caffeine|vaporizer",
    re.I,
)
RE_URL = re.compile(
    r"(ipfs://[^\s\"'<>]+|https?://[^\s\"'<>]+|ar://[^\s\"'<>]+|data:image/[^;]+;base64,[A-Za-z0-9+/=]+)",
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
        "docs/investigation/wave32/all_money_flows.json",
        "docs/investigation/wave26/blockchain_flows_all_addresses.json",
    ):
        path = ROOT / rel
        if not path.is_file():
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        for f in d.get("findings") or []:
            for lab, addr in (f.get("address_book") or {}).items():
                if addr:
                    book[lab] = addr
        for lab, s in (d.get("screens") or {}).items():
            if isinstance(s, dict) and s.get("address"):
                book[lab] = s["address"]
    by_addr: dict[str, str] = {}
    for lab, addr in book.items():
        key = addr.lower()
        if key not in by_addr:
            by_addr[key] = lab
    return {lab: book[lab] for lab in by_addr.values()}


def load_pub_ids() -> list[str]:
    path = ROOT / "docs" / "investigation" / "wave14" / "EXPANDED_SKODA_PORTFOLIO.json"
    if not path.is_file():
        return []
    port = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for p in port.get("publications") or []:
        if isinstance(p, dict):
            pid = p.get("publication") or p.get("publication_number")
            if pid:
                out.append(str(pid))
    return out


def _classify_media_url(url: str) -> str:
    u = (url or "").strip()
    low = u.lower()
    if low.startswith("ipfs://") or "ipfs/" in low or "dweb.link/ipfs" in low:
        return "ipfs"
    if low.startswith("ar://") or "arweave" in low:
        return "arweave"
    if low.startswith("data:image"):
        return "data_uri"
    if low.startswith("http://") or low.startswith("https://"):
        return "http"
    return "other"


def _normalize_image_key(url: str) -> str:
    """Normalize IPFS/HTTP gateway variants to a stable key for linkage."""
    u = (url or "").strip()
    m = re.search(r"(?:ipfs://|ipfs/)(Qm[1-9A-HJ-NP-Za-km-z]{44}|bafy[a-z0-9]+)", u, re.I)
    if m:
        return f"ipfs:{m.group(1)}"
    m2 = re.search(r"ar://([A-Za-z0-9_-]+)", u)
    if m2:
        return f"ar:{m2.group(1)}"
    if u.startswith("data:image"):
        return f"data:{hashlib.sha256(u.encode()).hexdigest()[:32]}"
    return u.lower().rstrip("/")


def extract_images_from_nft_item(item: dict[str, Any]) -> list[dict[str, Any]]:
    urls: list[tuple[str, str]] = []  # url, source_field
    for field in ("image_url", "media_url", "animation_url", "external_app_url"):
        v = item.get(field)
        if isinstance(v, str) and v.strip():
            urls.append((v.strip(), field))
    meta = item.get("metadata")
    if isinstance(meta, dict):
        for field in ("image", "image_url", "animation_url", "animation", "media"):
            v = meta.get(field)
            if isinstance(v, str) and v.strip():
                urls.append((v.strip(), f"metadata.{field}"))
        # Nested media objects
        for field in ("image", "animation"):
            v = meta.get(field)
            if isinstance(v, dict):
                for k in ("uri", "url", "href"):
                    if isinstance(v.get(k), str) and v[k].strip():
                        urls.append((v[k].strip(), f"metadata.{field}.{k}"))
        # Sweep strings in metadata for embedded URLs
        blob = json.dumps(meta, default=str)
        for m in RE_URL.finditer(blob):
            urls.append((m.group(1), "metadata_regex"))
    thumbs = item.get("thumbnails")
    if isinstance(thumbs, dict):
        for k, v in thumbs.items():
            if isinstance(v, str) and v.strip():
                urls.append((v.strip(), f"thumbnails.{k}"))
    elif isinstance(thumbs, list):
        for i, v in enumerate(thumbs):
            if isinstance(v, str) and v.strip():
                urls.append((v.strip(), f"thumbnails[{i}]"))

    # Dedupe by normalized key
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for url, src in urls:
        key = _normalize_image_key(url)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "url": url,
                "normalized_key": key,
                "scheme": _classify_media_url(url),
                "source_field": src,
            }
        )
    return out


def _metadata_blob(item: dict[str, Any]) -> str:
    parts = [
        item.get("id"),
        json.dumps(item.get("metadata") or {}, default=str),
        (item.get("token") or {}).get("name"),
        (item.get("token") or {}).get("symbol"),
    ]
    return " ".join(str(p) for p in parts if p)


def screen_address_nfts(
    label: str, address: str, pub_ids: list[str]
) -> dict[str, Any]:
    erc721 = _page(
        address, "nft", max_pages=MAX_NFT_PAGES, query={"type": "ERC-721"}
    )
    time.sleep(0.12)
    erc1155 = _page(
        address, "nft", max_pages=MAX_NFT_PAGES, query={"type": "ERC-1155"}
    )
    time.sleep(0.12)
    tt721 = _page(
        address,
        "token-transfers",
        max_pages=MAX_TT_NFT_PAGES,
        query={"type": "ERC-721"},
    )
    time.sleep(0.12)
    tt1155 = _page(
        address,
        "token-transfers",
        max_pages=MAX_TT_NFT_PAGES,
        query={"type": "ERC-1155"},
    )

    inventory: list[dict[str, Any]] = []
    image_rows: list[dict[str, Any]] = []
    collections: Counter[str] = Counter()
    scheme_counts: Counter[str] = Counter()
    ip_meta_hits: list[dict[str, Any]] = []
    pub_meta_hits: list[dict[str, Any]] = []

    for block, ttype in ((erc721, "ERC-721"), (erc1155, "ERC-1155")):
        for item in block.get("items") or []:
            token = item.get("token") or {}
            coll = token.get("address_hash") or token.get("address") or "?"
            collections[f"{token.get('symbol') or '?'}|{coll}"] += 1
            images = extract_images_from_nft_item(item)
            for img in images:
                scheme_counts[img["scheme"]] += 1
                image_rows.append(
                    {
                        **img,
                        "token_id": item.get("id"),
                        "token_type": item.get("token_type") or ttype,
                        "collection": token.get("name"),
                        "symbol": token.get("symbol"),
                        "collection_address": coll,
                        "nft_name": (item.get("metadata") or {}).get("name")
                        if isinstance(item.get("metadata"), dict)
                        else None,
                        "source": "nft_inventory",
                    }
                )
            blob = _metadata_blob(item)
            row_base = {
                "token_id": item.get("id"),
                "token_type": ttype,
                "collection": token.get("name"),
                "symbol": token.get("symbol"),
                "collection_address": coll,
                "image_count": len(images),
                "image_keys": [i["normalized_key"] for i in images[:8]],
            }
            if RE_IP.search(blob):
                if len(ip_meta_hits) < 40:
                    ip_meta_hits.append({**row_base, "matched": "ip_heuristic"})
            for pid in pub_ids:
                if pid and pid.replace("-", "").lower() in blob.replace("-", "").lower():
                    pub_meta_hits.append({**row_base, "matched_publication": pid})
                    break
            if len(inventory) < 80:
                inventory.append(
                    {
                        **row_base,
                        "metadata_name": (item.get("metadata") or {}).get("name")
                        if isinstance(item.get("metadata"), dict)
                        else None,
                        "image_url": item.get("image_url"),
                        "media_url": item.get("media_url"),
                    }
                )

    # Transfer activity (ownership flow) — also harvest images from token_instance
    transfer_count = (tt721.get("item_count") or 0) + (tt1155.get("item_count") or 0)
    transfer_collections: Counter[str] = Counter()
    transfer_image_rows: list[dict[str, Any]] = []
    transfer_image_keys: set[str] = set()
    for block, ttype in ((tt721, "ERC-721"), (tt1155, "ERC-1155")):
        for t in block.get("items") or []:
            token = t.get("token") or {}
            coll = token.get("address_hash") or token.get("address") or "?"
            transfer_collections[f"{token.get('symbol') or '?'}|{coll}"] += 1
            total = t.get("total") if isinstance(t.get("total"), dict) else {}
            instance = total.get("token_instance") if isinstance(total, dict) else None
            if not isinstance(instance, dict):
                continue
            images = extract_images_from_nft_item(instance)
            for img in images:
                scheme_counts[img["scheme"]] += 1
                transfer_image_keys.add(img["normalized_key"])
                row = {
                    **img,
                    "token_id": instance.get("id") or total.get("token_id"),
                    "token_type": t.get("token_type") or ttype,
                    "collection": token.get("name"),
                    "symbol": token.get("symbol"),
                    "collection_address": coll,
                    "source": "token_transfer_instance",
                    "tx_hash": t.get("transaction_hash"),
                }
                transfer_image_rows.append(row)
                image_rows.append(row)
            blob = _metadata_blob(instance)
            if RE_IP.search(blob) and len(ip_meta_hits) < 60:
                ip_meta_hits.append(
                    {
                        "token_id": instance.get("id") or total.get("token_id"),
                        "token_type": ttype,
                        "collection": token.get("name"),
                        "symbol": token.get("symbol"),
                        "collection_address": coll,
                        "image_count": len(images),
                        "matched": "ip_heuristic_transfer",
                    }
                )
            for pid in pub_ids:
                if pid and pid.replace("-", "").lower() in blob.replace("-", "").lower():
                    if len(pub_meta_hits) < 40:
                        pub_meta_hits.append(
                            {
                                "token_id": instance.get("id") or total.get("token_id"),
                                "token_type": ttype,
                                "collection": token.get("name"),
                                "symbol": token.get("symbol"),
                                "collection_address": coll,
                                "matched_publication": pid,
                                "source": "token_transfer_instance",
                            }
                        )
                    break

    unique_keys = sorted({i["normalized_key"] for i in image_rows})
    # Full catalog for OUT custody (cap extreme wallets)
    image_catalog = image_rows[:2500]

    return {
        "label": label,
        "address": address,
        "nft_inventory": {
            "erc721_count": erc721.get("item_count"),
            "erc1155_count": erc1155.get("item_count"),
            "erc721_hit_page_cap": erc721.get("hit_page_cap"),
            "erc1155_hit_page_cap": erc1155.get("hit_page_cap"),
            "erc721_exhausted": erc721.get("exhausted"),
            "erc1155_exhausted": erc1155.get("exhausted"),
        },
        "nft_transfers": {
            "erc721_count": tt721.get("item_count"),
            "erc1155_count": tt1155.get("item_count"),
            "erc721_hit_page_cap": tt721.get("hit_page_cap"),
            "erc1155_hit_page_cap": tt1155.get("hit_page_cap"),
            "transfer_total": transfer_count,
            "transfer_image_links": len(transfer_image_rows),
            "transfer_unique_image_keys": len(transfer_image_keys),
            "collections_top": transfer_collections.most_common(20),
        },
        "image_count": len(image_rows),
        "unique_image_keys": len(unique_keys),
        "image_scheme_counts": dict(scheme_counts),
        "collections_top": collections.most_common(25),
        "inventory_sample": inventory,
        "image_sample": image_rows[:80],
        "transfer_image_sample": transfer_image_rows[:40],
        "image_catalog": image_catalog,
        "all_image_keys": unique_keys,
        "ip_heuristic_metadata_hits": ip_meta_hits,
        "sealed_pub_metadata_hits": pub_meta_hits[:40],
        "sha256_pages": {
            "erc721": erc721.get("sha256_pages"),
            "erc1155": erc1155.get("sha256_pages"),
            "tt721": tt721.get("sha256_pages"),
            "tt1155": tt1155.get("sha256_pages"),
        },
        "ok": erc721.get("ok") or erc1155.get("ok"),
    }


def track_nft_image_trace() -> dict[str, Any]:
    book = collect_address_book()
    pub_ids = load_pub_ids()
    screens: dict[str, Any] = {}

    def _job(item: tuple[str, str]) -> tuple[str, dict[str, Any]]:
        return item[0], screen_address_nfts(item[0], item[1], pub_ids)

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_job, item): item[0] for item in book.items()}
        for fut in as_completed(futs):
            lab, summary = fut.result()
            screens[lab] = summary

    total_images = sum(int(s.get("image_count") or 0) for s in screens.values())
    total_inv_721 = sum(
        int((s.get("nft_inventory") or {}).get("erc721_count") or 0)
        for s in screens.values()
    )
    total_inv_1155 = sum(
        int((s.get("nft_inventory") or {}).get("erc1155_count") or 0)
        for s in screens.values()
    )
    total_tt = sum(
        int((s.get("nft_transfers") or {}).get("transfer_total") or 0)
        for s in screens.values()
    )
    scheme_agg: Counter[str] = Counter()
    for s in screens.values():
        for k, v in (s.get("image_scheme_counts") or {}).items():
            scheme_agg[k] += int(v)
    ip_hits = sum(
        len(s.get("ip_heuristic_metadata_hits") or []) for s in screens.values()
    )
    pub_hits = sum(
        len(s.get("sealed_pub_metadata_hits") or []) for s in screens.values()
    )
    capped = [
        lab
        for lab, s in screens.items()
        if (s.get("nft_inventory") or {}).get("erc721_hit_page_cap")
        or (s.get("nft_inventory") or {}).get("erc1155_hit_page_cap")
        or (s.get("nft_transfers") or {}).get("erc721_hit_page_cap")
        or (s.get("nft_transfers") or {}).get("erc1155_hit_page_cap")
    ]

    findings = [
        {
            "id": "W34-F1",
            "title": "All NFT inventories + linked images traced across sealed addresses",
            "addresses_screened": len(screens),
            "address_book": book,
            "aggregate_erc721_inventory": total_inv_721,
            "aggregate_erc1155_inventory": total_inv_1155,
            "aggregate_nft_transfers_scanned": total_tt,
            "aggregate_image_links": total_images,
            "image_scheme_totals": dict(scheme_agg),
            "ip_heuristic_metadata_hits_total": ip_hits,
            "sealed_pub_metadata_hits_total": pub_hits,
            "addresses_hitting_page_cap": capped,
            "stolen_ip_nft_imagery_adjudicated": False,
            "detail": (
                f"Screened {len(screens)} labels. Inventory ERC-721/1155="
                f"{total_inv_721}/{total_inv_1155}; NFT transfers scanned={total_tt}; "
                f"image/media links extracted={total_images} "
                f"(schemes={dict(scheme_agg)}). IP-heuristic metadata hits={ip_hits}; "
                f"sealed pub-id metadata hits={pub_hits}. "
                "Not a stolen-IP imagery adjudication."
            ),
        }
    ]
    return {
        "id": "nft_inventory_and_image_trace",
        "title": "NFT inventory + linked image trace (all sealed addresses)",
        "status": "SEALED",
        "screens": screens,
        "findings": findings,
        "next_actions": [
            "Uncap NFT pagination for page-capped wallets if exhaustive inventory required",
            "Do not equate shared IPFS image CIDs with stolen patent imagery without content analysis",
        ],
    }


def track_cross_address_image_linkage(nft_track: dict[str, Any]) -> dict[str, Any]:
    screens = nft_track.get("screens") or {}
    # image_key -> labels
    key_owners: dict[str, set[str]] = defaultdict(set)
    key_examples: dict[str, dict[str, Any]] = {}
    for lab, s in screens.items():
        # Prefer full catalog (inventory + transfer instances) for examples + owners
        catalog = s.get("image_catalog") or s.get("image_sample") or []
        for img in catalog:
            k = img.get("normalized_key")
            if not k:
                continue
            key_owners[k].add(lab)
            if k not in key_examples:
                key_examples[k] = {
                    "url": img.get("url"),
                    "scheme": img.get("scheme"),
                    "symbol": img.get("symbol"),
                    "collection": img.get("collection"),
                    "source": img.get("source") or img.get("source_field"),
                }
        # also use all_image_keys for completeness beyond catalog cap
        for k in s.get("all_image_keys") or []:
            key_owners[k].add(lab)

    shared = []
    for k, owners in key_owners.items():
        if len(owners) >= 2:
            shared.append(
                {
                    "normalized_key": k,
                    "labels": sorted(owners),
                    "label_count": len(owners),
                    "example": key_examples.get(k),
                }
            )
    shared.sort(key=lambda x: (-x["label_count"], x["normalized_key"]))

    # Pairwise shared-image edges
    labels = sorted(screens.keys())
    pairs = []
    owner_sets = {lab: set(s.get("all_image_keys") or []) for lab, s in screens.items()}
    for i, a in enumerate(labels):
        for b in labels[i + 1 :]:
            inter = owner_sets[a] & owner_sets[b]
            if inter:
                pairs.append(
                    {
                        "a": a,
                        "b": b,
                        "shared_image_key_count": len(inter),
                        "shared_image_keys_sample": sorted(inter)[:15],
                    }
                )
    pairs.sort(key=lambda x: -x["shared_image_key_count"])

    findings = [
        {
            "id": "W34-F2",
            "title": "Cross-address NFT image linkage graph (shared media keys)",
            "unique_image_keys_global": len(key_owners),
            "image_keys_shared_across_ge2_labels": len(shared),
            "shared_image_keys": shared[:100],
            "pairs_with_shared_images": pairs,
            "pair_space": len(labels) * (len(labels) - 1) // 2,
            "stolen_ip_shared_imagery_adjudicated": False,
            "detail": (
                f"Global unique image keys={len(key_owners)}; shared across ≥2 labels="
                f"{len(shared)}; pairs with shared images={len(pairs)} / "
                f"{len(labels)*(len(labels)-1)//2}. Shared CID/URL is not proof of "
                "stolen patent imagery."
            ),
        }
    ]
    return {
        "id": "cross_address_nft_image_linkage",
        "title": "Cross-address NFT image linkage",
        "status": "SEALED",
        "shared_image_keys": shared[:100],
        "pairs_with_shared_images": pairs,
        "findings": findings,
    }


def track_ip_nft_exhaustive_screen(
    nft_track: dict[str, Any], link_track: dict[str, Any]
) -> dict[str, Any]:
    screens = nft_track.get("screens") or {}
    f1 = (nft_track.get("findings") or [{}])[0]
    f2 = (link_track.get("findings") or [{}])[0]

    # Per-label exhaustive rollup
    rows = []
    for lab in sorted(screens.keys()):
        s = screens[lab]
        inv = s.get("nft_inventory") or {}
        tt = s.get("nft_transfers") or {}
        rows.append(
            {
                "label": lab,
                "address": s.get("address"),
                "erc721_inventory": inv.get("erc721_count"),
                "erc1155_inventory": inv.get("erc1155_count"),
                "nft_transfers": tt.get("transfer_total"),
                "image_links": s.get("image_count"),
                "unique_image_keys": s.get("unique_image_keys"),
                "ip_heuristic_hits": len(s.get("ip_heuristic_metadata_hits") or []),
                "sealed_pub_hits": len(s.get("sealed_pub_metadata_hits") or []),
                "hit_page_cap": bool(
                    inv.get("erc721_hit_page_cap")
                    or inv.get("erc1155_hit_page_cap")
                    or tt.get("erc721_hit_page_cap")
                    or tt.get("erc1155_hit_page_cap")
                ),
            }
        )

    w32 = {}
    w33 = {}
    for w, rel in (
        (32, "docs/investigation/wave32/WAVE32_RUN_SUMMARY.json"),
        (33, "docs/investigation/wave33/WAVE33_RUN_SUMMARY.json"),
    ):
        p = ROOT / rel
        if p.is_file():
            if w == 32:
                w32 = json.loads(p.read_text(encoding="utf-8")).get("disposition") or {}
            else:
                w33 = json.loads(p.read_text(encoding="utf-8")).get("disposition") or {}

    findings = [
        {
            "id": "W34-F3",
            "title": "Exhaustive NFT + image analysis rollup (IP linkage retained negative)",
            "per_label_rows": rows,
            "aggregate": {
                "addresses": len(rows),
                "image_links": f1.get("aggregate_image_links"),
                "schemes": f1.get("image_scheme_totals"),
                "shared_image_keys_ge2": f2.get("image_keys_shared_across_ge2_labels"),
                "pairs_with_shared_images": len(
                    f2.get("pairs_with_shared_images") or []
                ),
                "ip_heuristic_metadata_hits": f1.get(
                    "ip_heuristic_metadata_hits_total"
                ),
                "sealed_pub_metadata_hits": f1.get("sealed_pub_metadata_hits_total"),
            },
            "wave32_disposition_retained": w32,
            "wave33_disposition_retained": {
                k: w33.get(k)
                for k in (
                    "theft_adjudicated",
                    "authenticated_money_flow_to_sealed_ip",
                    "illicit_royalty_adjudicated",
                    "full_update_complete",
                )
                if w33
            },
            "nft_image_to_sealed_ip_authenticated": False,
            "stolen_ip_nft_imagery_adjudicated": False,
            "detail": (
                "Exhaustive-within-caps NFT inventory/image/transfer analysis complete. "
                "No sealed-publication match in NFT metadata authenticates an IP-NFT "
                "conveyance. Shared image keys across labels are linkage candidates only."
            ),
        }
    ]
    return {
        "id": "exhaustive_nft_image_analysis_rollup",
        "title": "Exhaustive NFT + image analysis rollup",
        "status": "SEALED",
        "per_label_rows": rows,
        "findings": findings,
    }


def track_operator_worklist() -> dict[str, Any]:
    return {
        "id": "operator_worklist",
        "title": "Wave-34 operator worklist",
        "status": "OPEN",
        "items": [
            {
                "id": "W34-M1",
                "priority": "HIGH",
                "item": (
                    "Content-hash / perceptual compare of shared IPFS CIDs only if "
                    "operator asserts patent-drawing theft theory"
                ),
            },
            {
                "id": "W34-M2",
                "priority": "HIGH",
                "item": "Uncap NFT inventory pagination for page-capped wallets",
            },
            {
                "id": "W34-M3",
                "priority": "MEDIUM",
                "item": "Do not treat marketplace profile NFTs as IP-NFT royalty instruments",
            },
        ],
        "adjudicated": False,
    }


def write_summary_md(
    nft: dict[str, Any], link: dict[str, Any], rollup: dict[str, Any]
) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE34_NFT_IMAGE_TRACE.md"
    f1 = (nft.get("findings") or [{}])[0]
    f2 = (link.get("findings") or [{}])[0]
    f3 = (rollup.get("findings") or [{}])[0]
    lines = [
        "# Wave 34 — Trace all images linked to all NFTs (exhaustive analysis)",
        "",
        f"Generated: `{_utc()}`",
        "",
        "## Disposition (policy-gated)",
        "",
        "- `stolen_ip_nft_imagery_adjudicated`: **false**",
        "- `nft_image_to_sealed_ip_authenticated`: **false**",
        "- `stolen_ip_shared_imagery_adjudicated`: **false**",
        "",
        "## NFT + image aggregates",
        "",
        f"- Addresses screened: `{f1.get('addresses_screened')}`",
        f"- ERC-721 / ERC-1155 inventory: `{f1.get('aggregate_erc721_inventory')}` / `{f1.get('aggregate_erc1155_inventory')}`",
        f"- NFT transfers scanned: `{f1.get('aggregate_nft_transfers_scanned')}`",
        f"- Image/media links extracted: `{f1.get('aggregate_image_links')}`",
        f"- Schemes: `{f1.get('image_scheme_totals')}`",
        f"- IP-heuristic metadata hits: `{f1.get('ip_heuristic_metadata_hits_total')}`",
        f"- Sealed pub-id metadata hits: `{f1.get('sealed_pub_metadata_hits_total')}`",
        f"- Page-cap: `{f1.get('addresses_hitting_page_cap')}`",
        "",
        "## Cross-address image linkage",
        "",
        f"- Unique image keys: `{f2.get('unique_image_keys_global')}`",
        f"- Keys shared by ≥2 labels: `{f2.get('image_keys_shared_across_ge2_labels')}`",
        f"- Pairs with shared images: `{len(f2.get('pairs_with_shared_images') or [])}` / `{f2.get('pair_space')}`",
        "",
        "## Exhaustive rollup",
        "",
        f"- Aggregate: `{f3.get('aggregate')}`",
        "",
        "## Manual next",
        "",
        "1. Uncap NFT pagination where still capped.",
        "2. Content-compare shared CIDs only if patent-drawing theft is asserted.",
        "3. Do not treat profile/PFP NFTs as IP royalty rails.",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave34() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    nft = track_nft_image_trace()
    link = track_cross_address_image_linkage(nft)
    rollup = track_ip_nft_exhaustive_screen(nft, link)
    work = track_operator_worklist()
    summary_md = write_summary_md(nft, link, rollup)

    # Slim docs copy of nft screens (drop sha256 page lists + huge catalogs)
    nft_docs = json.loads(json.dumps(nft, default=str))
    for s in (nft_docs.get("screens") or {}).values():
        s.pop("sha256_pages", None)
        # keep samples but cap; full catalog retained in OUT only
        s["image_sample"] = (s.get("image_sample") or [])[:50]
        s["transfer_image_sample"] = (s.get("transfer_image_sample") or [])[:30]
        s["inventory_sample"] = (s.get("inventory_sample") or [])[:40]
        catalog = s.pop("image_catalog", None) or []
        s["image_catalog_count"] = len(catalog)
        s["image_catalog_sample"] = catalog[:25]

    _write(OUT / "nft_inventory_and_image_trace.json", json.loads(json.dumps(nft, default=str)))
    _write(DOCS / "nft_inventory_and_image_trace.json", nft_docs)
    for t in (link, rollup, work):
        sealed = json.loads(json.dumps(t, default=str))
        _write(OUT / f"{t['id']}.json", sealed)
        _write(DOCS / f"{t['id']}.json", sealed)

    # Custody uses slim nft track
    nft_custody = {
        "id": "nft_inventory_and_image_trace",
        "title": nft.get("title"),
        "status": "SEALED",
        "findings": nft.get("findings"),
        "screens_summary": {
            lab: {
                "nft_inventory": s.get("nft_inventory"),
                "nft_transfers": {
                    "transfer_total": (s.get("nft_transfers") or {}).get(
                        "transfer_total"
                    )
                },
                "image_count": s.get("image_count"),
                "unique_image_keys": s.get("unique_image_keys"),
                "image_scheme_counts": s.get("image_scheme_counts"),
                "ip_heuristic_hit_count": len(
                    s.get("ip_heuristic_metadata_hits") or []
                ),
                "sealed_pub_hit_count": len(s.get("sealed_pub_metadata_hits") or []),
            }
            for lab, s in (nft.get("screens") or {}).items()
        },
    }
    custody_tracks = [nft_custody, link, rollup, work]
    key = ensure_hmac_key()
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
    for t in (nft, link, rollup):
        all_findings.extend(t.get("findings") or [])

    f1 = (nft.get("findings") or [{}])[0]
    f2 = (link.get("findings") or [{}])[0]

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
            "aggregate_image_links": f1.get("aggregate_image_links"),
            "shared_image_keys_ge2": f2.get("image_keys_shared_across_ge2_labels"),
            "pairs_with_shared_images": len(
                f2.get("pairs_with_shared_images") or []
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
            for t in custody_tracks
        ],
        "disposition": {
            "stolen_ip_nft_imagery_adjudicated": False,
            "nft_image_to_sealed_ip_authenticated": False,
            "stolen_ip_shared_imagery_adjudicated": False,
            "exhaustive_within_page_caps": True,
        },
        "artifacts": {
            "summary_md": summary_md,
            "nft": "docs/investigation/wave34/nft_inventory_and_image_trace.json",
            "linkage": "docs/investigation/wave34/cross_address_nft_image_linkage.json",
            "rollup": "docs/investigation/wave34/exhaustive_nft_image_analysis_rollup.json",
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-34 exhaustively traces NFT inventories and all linked images/media "
            "across sealed addresses, builds cross-address image-key linkage, and "
            "retains IP-negative dispositions. No stolen-IP imagery adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE34_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE34_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE34_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE34_POINTER.json",
        {
            "brand": BRAND,
            "wave34_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave34/WAVE34_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 34")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave34()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        d = report["disposition"]
        print(
            f"{BRAND} wave34: findings={report['counts']['findings']} "
            f"addrs={report['counts'].get('addresses_screened')} "
            f"images={report['counts'].get('aggregate_image_links')} "
            f"shared_keys={report['counts'].get('shared_image_keys_ge2')} "
            f"pairs={report['counts'].get('pairs_with_shared_images')} "
            f"stolen_img={d['stolen_ip_nft_imagery_adjudicated']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

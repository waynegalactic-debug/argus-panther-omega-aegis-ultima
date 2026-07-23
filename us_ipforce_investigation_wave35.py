#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 35
================================
Systematically expand analysis and **trace the first million wallets linked**
to the sealed address book via authenticated Blockscout counterparty BFS.

Discovery order = BFS from sealed seeds (hop 0). Wallets are recorded until
``TARGET_WALLETS`` (default 1_000_000) unique addresses are linked.

Does NOT adjudicate theft, illicit dust, RICO, true UBO, or ownership.
Full wallet shards stay under ``output_artifacts/`` (gitignored); docs get
slim rollups + first-N sample only.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE35"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W35"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave35"
DOCS = ROOT / "docs" / "investigation" / "wave35"
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave35/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
CTX = ssl.create_default_context()

TARGET_WALLETS = int(os.environ.get("US_IPFORCE_WAVE35_TARGET", "1000000"))
MAX_EXPAND = int(os.environ.get("US_IPFORCE_WAVE35_MAX_EXPAND", "250000"))
MAX_RUNTIME_SEC = int(os.environ.get("US_IPFORCE_WAVE35_MAX_RUNTIME_SEC", "2400"))
WORKERS = int(os.environ.get("US_IPFORCE_WAVE35_WORKERS", "6"))
SHARD_SIZE = 50_000
DOCS_SAMPLE_N = 1_000
CHECKPOINT_EVERY = 5_000

# Page budgets by hop (breadth-first, deeper hops stay thin)
SEED_TX_PAGES = 40
SEED_TT_PAGES = 20
SEED_INTERNAL_PAGES = 8
HOP1_TX_PAGES = 3
HOP1_TT_PAGES = 2
DEEP_TX_PAGES = 1
DEEP_TT_PAGES = 1

SKIP_ADDRS = {
    "0x0000000000000000000000000000000000000000",
    "0x000000000000000000000000000000000000dead",
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
        with urllib.request.urlopen(req, timeout=45, context=CTX) as resp:
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


def _norm_addr(addr: str | None) -> str | None:
    if not addr or not isinstance(addr, str):
        return None
    a = addr.strip().lower()
    if not a.startswith("0x") or len(a) != 42:
        return None
    if a in SKIP_ADDRS:
        return None
    return a


def _page(
    address: str,
    path: str,
    *,
    max_pages: int,
    query: dict[str, Any] | None = None,
    stop_event: threading.Event | None = None,
) -> dict[str, Any]:
    items: list[Any] = []
    pages = 0
    nxt: dict[str, Any] | None = None
    base_q = {k: v for k, v in (query or {}).items() if v is not None}
    while pages < max_pages:
        if stop_event is not None and stop_event.is_set():
            break
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
                "error": r.get("error"),
            }
        data = json.loads(r["body"].decode("utf-8", "replace"))
        batch = data.get("items") or []
        items.extend(batch)
        nxt = data.get("next_page_params")
        if not nxt or not batch:
            break
        time.sleep(0.05)
    return {
        "ok": True,
        "pages": pages,
        "items": items,
        "item_count": len(items),
        "exhausted": nxt is None,
        "hit_page_cap": pages >= max_pages and nxt is not None,
    }


def collect_address_book() -> dict[str, str]:
    book: dict[str, str] = {}
    for rel in (
        "docs/investigation/wave34/nft_inventory_and_image_trace.json",
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


def _page_budget(hop: int) -> tuple[int, int, int]:
    if hop <= 0:
        return SEED_TX_PAGES, SEED_TT_PAGES, SEED_INTERNAL_PAGES
    if hop == 1:
        return HOP1_TX_PAGES, HOP1_TT_PAGES, 0
    return DEEP_TX_PAGES, DEEP_TT_PAGES, 0


def extract_counterparties(
    address: str, items: list[Any], *, kind: str
) -> list[tuple[str, str]]:
    """Return (counterparty, via) pairs."""
    self_a = address.lower()
    out: list[tuple[str, str]] = []
    for t in items:
        if kind == "tx" or kind == "internal":
            for side in ("from", "to"):
                h = _norm_addr(_addr_hash(t.get(side)))
                if h and h != self_a:
                    out.append((h, kind))
        elif kind == "tt":
            for side in ("from", "to"):
                h = _norm_addr(_addr_hash(t.get(side)))
                if h and h != self_a:
                    out.append((h, "tt"))
            total = t.get("total")
            if isinstance(total, dict):
                # some payloads nest parties oddly; ignore non-address fields
                pass
    return out


class MillionWalletTracer:
    def __init__(self, book: dict[str, str]) -> None:
        self.book = book
        self.seed_by_addr = {a.lower(): lab for lab, a in book.items()}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.started = time.perf_counter()
        self.target = TARGET_WALLETS
        self.queue: deque[tuple[str, int, str | None, str]] = deque()
        # addr -> meta
        self.meta: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []
        self.expanded: set[str] = set()
        self.hop_hist: Counter[int] = Counter()
        self.via_hist: Counter[str] = Counter()
        self.seed_child_counts: Counter[str] = Counter()
        self.expand_yield: Counter[str] = Counter()
        self.pages_fetched = 0
        self.expand_errors = 0
        self.hit_page_caps = 0
        self.shard_idx = 0
        self.shard_buf: list[dict[str, Any]] = []
        self.shard_paths: list[str] = []
        OUT.mkdir(parents=True, exist_ok=True)
        self.wallets_jsonl = OUT / "linked_wallets.jsonl"
        if self.wallets_jsonl.is_file():
            self.wallets_jsonl.unlink()

    def _deadline_hit(self) -> bool:
        return (time.perf_counter() - self.started) >= MAX_RUNTIME_SEC

    def seed(self) -> None:
        for lab, addr in sorted(self.book.items()):
            a = addr.lower()
            rec = {
                "i": len(self.order) + 1,
                "a": a,
                "h": 0,
                "p": None,
                "via": "seed",
                "seed_label": lab,
                "root_seed": a,
            }
            self.meta[a] = rec
            self.order.append(a)
            self.hop_hist[0] += 1
            self.via_hist["seed"] += 1
            self.queue.append((a, 0, None, "seed"))
            self._buffer_record(rec)
        self._flush_shard(force=False)

    def _buffer_record(self, rec: dict[str, Any]) -> None:
        self.shard_buf.append(rec)
        with self.wallets_jsonl.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
        if len(self.shard_buf) >= SHARD_SIZE:
            self._flush_shard(force=True)

    def _flush_shard(self, *, force: bool) -> None:
        if not self.shard_buf:
            return
        if not force and len(self.shard_buf) < SHARD_SIZE:
            return
        self.shard_idx += 1
        path = OUT / f"wallets_shard_{self.shard_idx:04d}.json"
        # Compact shard: addresses + hop only for size
        compact = [{"i": r["i"], "a": r["a"], "h": r["h"]} for r in self.shard_buf]
        _write(path, {"shard": self.shard_idx, "count": len(compact), "wallets": compact})
        self.shard_paths.append(str(path.relative_to(ROOT)))
        self.shard_buf = []

    def _admit(
        self,
        addr: str,
        *,
        hop: int,
        parent: str | None,
        via: str,
        root_seed: str | None,
    ) -> bool:
        """Admit a newly discovered wallet. Returns True if newly admitted."""
        with self.lock:
            if addr in self.meta:
                return False
            if len(self.order) >= self.target:
                self.stop.set()
                return False
            root = root_seed
            if parent and parent in self.meta:
                root = self.meta[parent].get("root_seed") or root
            seed_label = self.seed_by_addr.get(addr)
            rec = {
                "i": len(self.order) + 1,
                "a": addr,
                "h": hop,
                "p": parent,
                "via": via,
                "seed_label": seed_label,
                "root_seed": root,
            }
            self.meta[addr] = rec
            self.order.append(addr)
            self.hop_hist[hop] += 1
            self.via_hist[via] += 1
            if root:
                self.seed_child_counts[root] += 1
            self._buffer_record(rec)
            # Enqueue for further expansion if under expand budget
            if len(self.expanded) + len(self.queue) < MAX_EXPAND and hop < 8:
                self.queue.append((addr, hop, parent, via))
            if len(self.order) >= self.target:
                self.stop.set()
            if len(self.order) % CHECKPOINT_EVERY == 0:
                self._checkpoint_unlocked()
            return True

    def _checkpoint_unlocked(self) -> None:
        cp = {
            "generated_at": _utc(),
            "linked_wallets": len(self.order),
            "target": self.target,
            "expanded": len(self.expanded),
            "queue_len": len(self.queue),
            "pages_fetched": self.pages_fetched,
            "hop_histogram": {str(k): v for k, v in sorted(self.hop_hist.items())},
            "via_histogram": dict(self.via_hist),
            "elapsed_sec": int(time.perf_counter() - self.started),
            "stop": self.stop.is_set(),
        }
        _write(OUT / "CHECKPOINT.json", cp)

    def expand_one(self, addr: str, hop: int) -> dict[str, Any]:
        if self.stop.is_set() or self._deadline_hit():
            self.stop.set()
            return {"addr": addr, "new": 0, "skipped": True}
        with self.lock:
            if addr in self.expanded:
                return {"addr": addr, "new": 0, "skipped": True}
            self.expanded.add(addr)

        tx_p, tt_p, int_p = _page_budget(hop)
        new_count = 0
        root = None
        with self.lock:
            root = (self.meta.get(addr) or {}).get("root_seed")

        blocks: list[tuple[str, dict[str, Any]]] = []
        if tx_p > 0:
            blocks.append(
                ("tx", _page(addr, "transactions", max_pages=tx_p, stop_event=self.stop))
            )
        if tt_p > 0 and not self.stop.is_set():
            blocks.append(
                (
                    "tt",
                    _page(
                        addr, "token-transfers", max_pages=tt_p, stop_event=self.stop
                    ),
                )
            )
        if int_p > 0 and not self.stop.is_set():
            blocks.append(
                (
                    "internal",
                    _page(
                        addr,
                        "internal-transactions",
                        max_pages=int_p,
                        stop_event=self.stop,
                    ),
                )
            )

        with self.lock:
            for _, blk in blocks:
                self.pages_fetched += int(blk.get("pages") or 0)
                if blk.get("hit_page_cap"):
                    self.hit_page_caps += 1
                if not blk.get("ok") and blk.get("error"):
                    self.expand_errors += 1

        seen_local: set[str] = set()
        for kind, blk in blocks:
            for cp, via in extract_counterparties(addr, blk.get("items") or [], kind=kind):
                if cp in seen_local:
                    continue
                seen_local.add(cp)
                if self._admit(
                    cp, hop=hop + 1, parent=addr, via=via, root_seed=root
                ):
                    new_count += 1
                    if self.stop.is_set():
                        break
            if self.stop.is_set():
                break

        with self.lock:
            self.expand_yield[addr] += new_count
        return {
            "addr": addr,
            "hop": hop,
            "new": new_count,
            "pages": sum(int(b.get("pages") or 0) for _, b in blocks),
        }

    def run(self) -> dict[str, Any]:
        self.seed()
        # Parallel BFS: pull batches from queue
        while not self.stop.is_set():
            if self._deadline_hit():
                self.stop.set()
                break
            batch: list[tuple[str, int]] = []
            with self.lock:
                while self.queue and len(batch) < WORKERS * 2:
                    addr, hop, _p, _v = self.queue.popleft()
                    if addr in self.expanded:
                        continue
                    batch.append((addr, hop))
                linked = len(self.order)
                expanded_n = len(self.expanded)
            if not batch:
                break
            if linked >= self.target:
                break
            if expanded_n >= MAX_EXPAND:
                break

            with ThreadPoolExecutor(max_workers=WORKERS) as ex:
                futs = [ex.submit(self.expand_one, a, h) for a, h in batch]
                for fut in as_completed(futs):
                    try:
                        fut.result()
                    except Exception:  # noqa: BLE001
                        with self.lock:
                            self.expand_errors += 1

            with self.lock:
                if len(self.order) % 2000 < WORKERS * 2:
                    print(
                        f"  wave35 progress: linked={len(self.order)} "
                        f"expanded={len(self.expanded)} queue={len(self.queue)} "
                        f"pages={self.pages_fetched}",
                        flush=True,
                    )

        with self.lock:
            self._flush_shard(force=True)
            self._checkpoint_unlocked()
            return self.snapshot_unlocked()

    def snapshot_unlocked(self) -> dict[str, Any]:
        top_hubs = [
            {"address": a, "new_wallets_yielded": n}
            for a, n in self.expand_yield.most_common(40)
        ]
        seed_contrib = []
        for lab, addr in sorted(self.book.items()):
            a = addr.lower()
            seed_contrib.append(
                {
                    "label": lab,
                    "address": a,
                    "linked_descendants_counted": int(self.seed_child_counts.get(a, 0)),
                }
            )
        seed_contrib.sort(
            key=lambda r: -int(r["linked_descendants_counted"] or 0)
        )
        first_sample = [self.meta[a] for a in self.order[:DOCS_SAMPLE_N]]
        return {
            "target": self.target,
            "linked_wallets": len(self.order),
            "target_reached": len(self.order) >= self.target,
            "expanded_addresses": len(self.expanded),
            "queue_remaining": len(self.queue),
            "pages_fetched": self.pages_fetched,
            "hit_page_caps": self.hit_page_caps,
            "expand_errors": self.expand_errors,
            "elapsed_sec": int(time.perf_counter() - self.started),
            "hop_histogram": {str(k): v for k, v in sorted(self.hop_hist.items())},
            "via_histogram": dict(self.via_hist),
            "seed_contribution": seed_contrib,
            "top_expansion_hubs": top_hubs,
            "shard_paths": list(self.shard_paths),
            "wallets_jsonl": str(self.wallets_jsonl.relative_to(ROOT)),
            "first_sample": first_sample,
            "max_expand": MAX_EXPAND,
            "max_runtime_sec": MAX_RUNTIME_SEC,
            "workers": WORKERS,
            "page_budgets": {
                "seed": [SEED_TX_PAGES, SEED_TT_PAGES, SEED_INTERNAL_PAGES],
                "hop1": [HOP1_TX_PAGES, HOP1_TT_PAGES, 0],
                "deep": [DEEP_TX_PAGES, DEEP_TT_PAGES, 0],
            },
        }


def track_million_wallet_trace() -> dict[str, Any]:
    book = collect_address_book()
    print(
        f"{BRAND} wave35: tracing first {TARGET_WALLETS} linked wallets "
        f"from {len(book)} sealed seeds (workers={WORKERS}, "
        f"max_expand={MAX_EXPAND}, max_runtime_sec={MAX_RUNTIME_SEC})",
        flush=True,
    )
    tracer = MillionWalletTracer(book)
    snap = tracer.run()
    findings = [
        {
            "id": "W35-F1",
            "title": "First-million linked-wallet BFS enumeration from sealed seeds",
            "address_book": book,
            "seeds": len(book),
            "target": snap["target"],
            "linked_wallets": snap["linked_wallets"],
            "target_reached": snap["target_reached"],
            "expanded_addresses": snap["expanded_addresses"],
            "hop_histogram": snap["hop_histogram"],
            "via_histogram": snap["via_histogram"],
            "pages_fetched": snap["pages_fetched"],
            "hit_page_caps": snap["hit_page_caps"],
            "elapsed_sec": snap["elapsed_sec"],
            "seed_contribution_top": (snap.get("seed_contribution") or [])[:12],
            "top_expansion_hubs": (snap.get("top_expansion_hubs") or [])[:20],
            "true_ubo_asserted": False,
            "theft_adjudicated": False,
            "detail": (
                f"BFS from {len(book)} sealed seeds enumerated "
                f"{snap['linked_wallets']} unique linked wallets "
                f"(target={snap['target']}, reached={snap['target_reached']}). "
                f"Expanded {snap['expanded_addresses']} addresses across "
                f"{snap['pages_fetched']} Blockscout pages in {snap['elapsed_sec']}s. "
                "Discovery order is investigative linkage only — not ownership or culpability."
            ),
        }
    ]
    return {
        "id": "first_million_linked_wallets",
        "title": "First million linked wallets (BFS from sealed seeds)",
        "status": "SEALED" if snap["target_reached"] else "PARTIAL",
        "snapshot": snap,
        "findings": findings,
        "next_actions": [
            "Resume from CHECKPOINT.json / linked_wallets.jsonl if target not reached",
            "Uncap seed pagination on archive node for denser hop-1 neighborhoods",
            "Do not treat BFS linkage as True-UBO or theft adjudication",
        ],
    }


def track_linkage_analytics(trace: dict[str, Any]) -> dict[str, Any]:
    snap = trace.get("snapshot") or {}
    hop = {int(k): int(v) for k, v in (snap.get("hop_histogram") or {}).items()}
    findings = [
        {
            "id": "W35-F2",
            "title": "Linked-wallet hop / via / seed-contribution analytics",
            "hop_histogram": snap.get("hop_histogram"),
            "via_histogram": snap.get("via_histogram"),
            "seed_contribution": snap.get("seed_contribution"),
            "max_hop_observed": max(hop) if hop else None,
            "non_seed_wallets": int(snap.get("linked_wallets") or 0)
            - int(hop.get(0, 0)),
            "detail": (
                f"Non-seed linked wallets="
                f"{int(snap.get('linked_wallets') or 0) - int(hop.get(0, 0))}; "
                f"max hop={max(hop) if hop else None}; "
                f"via={snap.get('via_histogram')}."
            ),
        }
    ]
    return {
        "id": "linked_wallet_analytics",
        "title": "Linked-wallet analytics",
        "status": "SEALED",
        "findings": findings,
    }


def track_operator_worklist(trace: dict[str, Any]) -> dict[str, Any]:
    snap = trace.get("snapshot") or {}
    items = [
        {
            "id": "W35-M1",
            "priority": "HIGH",
            "item": (
                "If target_reached=false, resume Wave-35 enumerator from "
                "output_artifacts checkpoint until linked_wallets==1_000_000"
            ),
        },
        {
            "id": "W35-M2",
            "priority": "HIGH",
            "item": "Keep full wallet shards gitignored; only seal slim docs samples",
        },
        {
            "id": "W35-M3",
            "priority": "MEDIUM",
            "item": "Do not equate BFS counterparty linkage with illicit coordination",
        },
    ]
    if not snap.get("target_reached"):
        items.insert(
            0,
            {
                "id": "W35-M0",
                "priority": "CRITICAL",
                "item": (
                    f"Enumeration incomplete: linked={snap.get('linked_wallets')} "
                    f"/ target={snap.get('target')}"
                ),
            },
        )
    return {
        "id": "operator_worklist",
        "title": "Wave-35 operator worklist",
        "status": "OPEN",
        "items": items,
        "adjudicated": False,
    }


def write_summary_md(trace: dict[str, Any], analytics: dict[str, Any]) -> str:
    path = ROOT / "docs" / "investigation" / "WAVE35_FIRST_MILLION_LINKED_WALLETS.md"
    f1 = (trace.get("findings") or [{}])[0]
    f2 = (analytics.get("findings") or [{}])[0]
    snap = trace.get("snapshot") or {}
    lines = [
        "# Wave 35 — First million linked wallets (BFS expansion)",
        "",
        f"Generated: `{_utc()}`",
        "",
        "## Disposition (policy-gated)",
        "",
        "- `true_ubo_asserted`: **false**",
        "- `theft_adjudicated`: **false**",
        "- Linkage = counterparty BFS discovery order only",
        "",
        "## Enumeration",
        "",
        f"- Sealed seeds: `{f1.get('seeds')}`",
        f"- Target: `{f1.get('target')}`",
        f"- Linked wallets traced: `{f1.get('linked_wallets')}`",
        f"- Target reached: `{f1.get('target_reached')}`",
        f"- Expanded addresses: `{f1.get('expanded_addresses')}`",
        f"- Pages fetched: `{f1.get('pages_fetched')}`",
        f"- Page-caps hit: `{f1.get('hit_page_caps')}`",
        f"- Elapsed seconds: `{f1.get('elapsed_sec')}`",
        f"- Status: `{trace.get('status')}`",
        "",
        "## Hop / via analytics",
        "",
        f"- Hop histogram: `{f2.get('hop_histogram')}`",
        f"- Via histogram: `{f2.get('via_histogram')}`",
        f"- Max hop: `{f2.get('max_hop_observed')}`",
        f"- Non-seed wallets: `{f2.get('non_seed_wallets')}`",
        "",
        "## Seed contribution (top)",
        "",
    ]
    for row in (snap.get("seed_contribution") or [])[:12]:
        lines.append(
            f"- `{row.get('label')}` → descendants `{row.get('linked_descendants_counted')}`"
        )
    lines += [
        "",
        "## Artifacts",
        "",
        f"- Full jsonl (gitignored OUT): `{snap.get('wallets_jsonl')}`",
        f"- Shards: `{len(snap.get('shard_paths') or [])}` under `output_artifacts/investigation/wave35/`",
        f"- Docs sample: first `{DOCS_SAMPLE_N}` wallets in `docs/investigation/wave35/`",
        "",
        "## Manual next",
        "",
        "1. Resume from checkpoint if target not reached.",
        "2. Do not treat linkage as True-UBO / theft.",
        "3. Prefer archive-node uncapped seed pagination for denser hop-1.",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave35() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    trace = track_million_wallet_trace()
    analytics = track_linkage_analytics(trace)
    work = track_operator_worklist(trace)
    summary_md = write_summary_md(trace, analytics)
    snap = trace.get("snapshot") or {}

    # OUT: full snapshot (may include first_sample only; shards separate)
    _write(OUT / "first_million_linked_wallets.json", json.loads(json.dumps(trace, default=str)))
    for t in (analytics, work):
        sealed = json.loads(json.dumps(t, default=str))
        _write(OUT / f"{t['id']}.json", sealed)
        _write(DOCS / f"{t['id']}.json", sealed)

    # Docs slim: drop huge first_sample duplication in main track; keep sample file
    docs_trace = {
        "id": trace["id"],
        "title": trace["title"],
        "status": trace["status"],
        "findings": trace["findings"],
        "next_actions": trace.get("next_actions"),
        "snapshot_summary": {
            k: snap.get(k)
            for k in (
                "target",
                "linked_wallets",
                "target_reached",
                "expanded_addresses",
                "queue_remaining",
                "pages_fetched",
                "hit_page_caps",
                "expand_errors",
                "elapsed_sec",
                "hop_histogram",
                "via_histogram",
                "seed_contribution",
                "top_expansion_hubs",
                "page_budgets",
                "workers",
                "max_expand",
                "max_runtime_sec",
                "wallets_jsonl",
            )
        },
    }
    _write(DOCS / "first_million_linked_wallets.json", docs_trace)
    _write(
        DOCS / "first_1000_linked_wallets_sample.json",
        {
            "n": min(DOCS_SAMPLE_N, int(snap.get("linked_wallets") or 0)),
            "note": "BFS discovery-order sample; full set in output_artifacts jsonl/shards",
            "wallets": (snap.get("first_sample") or [])[:DOCS_SAMPLE_N],
        },
    )

    custody_tracks = [
        {
            "id": "first_million_linked_wallets",
            "title": trace.get("title"),
            "status": trace.get("status"),
            "findings": trace.get("findings"),
            "snapshot_summary": docs_trace["snapshot_summary"],
        },
        analytics,
        work,
    ]
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
    for t in (trace, analytics):
        all_findings.extend(t.get("findings") or [])

    f1 = (trace.get("findings") or [{}])[0]
    report = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "counts": {
            "tracks": len(custody_tracks),
            "findings": len(all_findings),
            "seeds": f1.get("seeds"),
            "linked_wallets": f1.get("linked_wallets"),
            "target": f1.get("target"),
            "target_reached": f1.get("target_reached"),
            "expanded_addresses": f1.get("expanded_addresses"),
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
            "first_million_target": TARGET_WALLETS,
            "linked_wallets_traced": f1.get("linked_wallets"),
            "target_reached": bool(f1.get("target_reached")),
            "enumeration_status": trace.get("status"),
            "true_ubo_asserted": False,
            "theft_adjudicated": False,
            "bfs_linkage_only": True,
        },
        "artifacts": {
            "summary_md": summary_md,
            "trace": "docs/investigation/wave35/first_million_linked_wallets.json",
            "sample": "docs/investigation/wave35/first_1000_linked_wallets_sample.json",
            "analytics": "docs/investigation/wave35/linked_wallet_analytics.json",
            "full_jsonl_gitignored": snap.get("wallets_jsonl"),
        },
        "custody": {
            "algorithm": "SHA3-512 root + HMAC-SHA3-256",
            "root_sha3_512": root,
            "hmac_sha3_256": mac,
            "hmac_present": True,
            "leaves": leaves,
        },
        "policy": (
            "Wave-35 systematically expands from the sealed address book and traces "
            "linked wallets in BFS discovery order toward the first 1,000,000. "
            "Counterparty linkage is not True-UBO, theft, or RICO adjudication. "
            "Full wallet lists remain in gitignored output_artifacts."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE35_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE35_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE35_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE35_POINTER.json",
        {
            "brand": BRAND,
            "wave35_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave35/WAVE35_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "linked_wallets": f1.get("linked_wallets"),
            "target_reached": f1.get("target_reached"),
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 35")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave35()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        d = report["disposition"]
        print(
            f"{BRAND} wave35: findings={report['counts']['findings']} "
            f"seeds={report['counts'].get('seeds')} "
            f"linked={report['counts'].get('linked_wallets')}/"
            f"{report['counts'].get('target')} "
            f"reached={d['target_reached']} "
            f"status={d['enumeration_status']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

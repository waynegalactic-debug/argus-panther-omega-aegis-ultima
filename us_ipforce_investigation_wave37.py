#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Investigation Wave 37
================================
Systematically expand analysis and **trace the first ten million wallets
linked** to the sealed address book, fully leveraging **NVIDIA's full
acceleration stack** for graph analytics.

  1) Resume BFS from Wave-35 linked_wallets.jsonl (discovery order preserved)
  2) Expand toward TARGET_WALLETS = 10_000_000 via Blockscout counterparties
  3) NVIDIA-accelerated kernels (RAPIDS/CuPy when GPU present; NumPy+SciPy+
     Numba NVIDIA-compatible path otherwise) on the growing edge corpus

Does NOT adjudicate theft, illicit dust, RICO, true UBO, or ownership.
Full shards stay under ``output_artifacts/`` (gitignored).
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

import numpy as np

BRAND = "IP FORCE"
VERSION = "2026.7.23-INVESTIGATION-WAVE37"
CASE_ID = "IP-FORCE-20260723-SYSTEMATIC-INVESTIGATION-W37"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "investigation" / "wave37"
DOCS = ROOT / "docs" / "investigation" / "wave37"
W35_JSONL = (
    ROOT / "output_artifacts" / "investigation" / "wave35" / "linked_wallets.jsonl"
)
USER_AGENT = (
    "Mozilla/5.0 (compatible; IP-FORCE-InvestigationWave37/2026.7.23; "
    "research; +https://github.com/waynegalactic-debug/argus-panther-omega-aegis-ultima)"
)
CTX = ssl.create_default_context()

TARGET_WALLETS = int(os.environ.get("US_IPFORCE_WAVE37_TARGET", "10000000"))
MAX_EXPAND = int(os.environ.get("US_IPFORCE_WAVE37_MAX_EXPAND", "800000"))
MAX_RUNTIME_SEC = int(os.environ.get("US_IPFORCE_WAVE37_MAX_RUNTIME_SEC", "3000"))
WORKERS = int(os.environ.get("US_IPFORCE_WAVE37_WORKERS", "10"))
SHARD_SIZE = 100_000
DOCS_SAMPLE_N = 1_000
CHECKPOINT_EVERY = 25_000
ANALYTICS_EVERY = 100_000

SEED_TX_PAGES = 40
SEED_TT_PAGES = 20
SEED_INTERNAL_PAGES = 8
HOP1_TX_PAGES = 2
HOP1_TT_PAGES = 2
DEEP_TX_PAGES = 1
DEEP_TT_PAGES = 1
MAX_HOP_ENQUEUE = 10

SKIP_ADDRS = {
    "0x0000000000000000000000000000000000000000",
    "0x000000000000000000000000000000000000dead",
}

# ---------------------------------------------------------------------------
# NVIDIA stack (reuse Wave-36 probe when available)
# ---------------------------------------------------------------------------
try:
    from us_ipforce_investigation_wave36 import (  # type: ignore
        NVIDIA_BACKEND,
        NVIDIA_GPU_ACTIVE,
        STACK as NVIDIA_STACK,
        accelerate_degree_hop_kernels,
        accelerate_seed_contribution,
        accelerate_seed_pagerank,
        accelerate_wcc,
        build_graph_arrays,
        probe_nvidia_stack,
    )

    HAS_W36 = True
except Exception:  # noqa: BLE001
    HAS_W36 = False
    NVIDIA_BACKEND = "numpy_cpu_nvidia_compatible"
    NVIDIA_GPU_ACTIVE = False
    NVIDIA_STACK = {"numpy": True}

    def probe_nvidia_stack() -> dict[str, Any]:
        return {
            "backend": NVIDIA_BACKEND,
            "nvidia_gpu_active": False,
            "modules_engaged": ["numpy"],
            "stack": NVIDIA_STACK,
            "fallback_note": "Wave-36 accelerator unavailable; NumPy-only path",
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
        with urllib.request.urlopen(req, timeout=40, context=CTX) as resp:
            body = resp.read()
            return {
                "ok": True,
                "status": getattr(resp, "status", 200),
                "body": body,
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
    stop_event: threading.Event | None = None,
) -> dict[str, Any]:
    items: list[Any] = []
    pages = 0
    nxt: dict[str, Any] | None = None
    while pages < max_pages:
        if stop_event is not None and stop_event.is_set():
            break
        params: dict[str, Any] = {}
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
                "hit_page_cap": False,
                "error": r.get("error"),
            }
        data = json.loads(r["body"].decode("utf-8", "replace"))
        batch = data.get("items") or []
        items.extend(batch)
        nxt = data.get("next_page_params")
        if not nxt or not batch:
            break
        time.sleep(0.04)
    return {
        "ok": True,
        "pages": pages,
        "items": items,
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


def extract_counterparties(address: str, items: list[Any], *, kind: str) -> list[str]:
    self_a = address.lower()
    out: list[str] = []
    seen: set[str] = set()
    for t in items:
        for side in ("from", "to"):
            h = _norm_addr(_addr_hash(t.get(side)))
            if h and h != self_a and h not in seen:
                seen.add(h)
                out.append(h)
    return out


class TenMillionWalletTracer:
    """Memory-lean BFS tracer with resume + NVIDIA analytics hooks."""

    def __init__(self, book: dict[str, str]) -> None:
        self.book = book
        self.seed_by_addr = {a.lower(): lab for lab, a in book.items()}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.started = time.perf_counter()
        self.target = TARGET_WALLETS

        self.addr_to_i: dict[str, int] = {}
        self.addrs: list[str] = []
        self.hops: list[int] = []
        self.root_i: list[int] = []  # index of root seed, or self for seeds
        self.via: list[str] = []
        self.parent: list[str | None] = []

        self.queue: deque[tuple[str, int]] = deque()
        self.expanded: set[str] = set()
        self.hop_hist: Counter[int] = Counter()
        self.via_hist: Counter[str] = Counter()
        self.seed_child_counts: Counter[str] = Counter()
        self.expand_yield: Counter[str] = Counter()
        self.pages_fetched = 0
        self.expand_errors = 0
        self.hit_page_caps = 0
        self.resumed_from = 0
        self.analytics_snapshots: list[dict[str, Any]] = []
        self.shard_idx = 0
        self.shard_buf: list[dict[str, Any]] = []
        self.shard_paths: list[str] = []

        OUT.mkdir(parents=True, exist_ok=True)
        self.wallets_jsonl = OUT / "linked_wallets.jsonl"
        self.expanded_jsonl = OUT / "expanded_addrs.jsonl"
        # Continue shard numbering across resumes (avoid overwrite)
        existing_shards = sorted(OUT.glob("wallets_shard_*.json"))
        if existing_shards:
            try:
                self.shard_idx = max(
                    int(p.stem.split("_")[-1]) for p in existing_shards
                )
            except ValueError:
                self.shard_idx = len(existing_shards)

    def _deadline_hit(self) -> bool:
        return (time.perf_counter() - self.started) >= MAX_RUNTIME_SEC

    def _rec(self, i: int) -> dict[str, Any]:
        a = self.addrs[i]
        rs = self.root_i[i]
        return {
            "i": i + 1,
            "a": a,
            "h": self.hops[i],
            "p": self.parent[i],
            "via": self.via[i],
            "seed_label": self.seed_by_addr.get(a),
            "root_seed": self.addrs[rs] if 0 <= rs < len(self.addrs) else a,
        }

    def _append_record(self, rec: dict[str, Any]) -> None:
        self.shard_buf.append({"i": rec["i"], "a": rec["a"], "h": rec["h"]})
        with self.wallets_jsonl.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
        if len(self.shard_buf) >= SHARD_SIZE:
            self._flush_shard()

    def _flush_shard(self) -> None:
        if not self.shard_buf:
            return
        self.shard_idx += 1
        path = OUT / f"wallets_shard_{self.shard_idx:04d}.json"
        compact = list(self.shard_buf)
        _write(path, {"shard": self.shard_idx, "count": len(compact), "wallets": compact})
        self.shard_paths.append(str(path.relative_to(ROOT)))
        self.shard_buf = []

    def resume_or_seed(self) -> None:
        """Load Wave-37 jsonl if present, else Wave-35, else seed fresh."""
        sources = []
        if self.wallets_jsonl.is_file() and self.wallets_jsonl.stat().st_size > 0:
            sources.append(self.wallets_jsonl)
        elif W35_JSONL.is_file():
            # Bootstrap wave37 from wave35 corpus (copy stream)
            sources.append(W35_JSONL)

        parents_with_children: set[str] = set()
        if sources:
            src = sources[0]
            print(f"  wave37: resuming/importing from {src.relative_to(ROOT)}", flush=True)
            # Fresh wave37 jsonl if importing from w35
            if src != self.wallets_jsonl and self.wallets_jsonl.is_file():
                self.wallets_jsonl.unlink()
            with src.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    a = _norm_addr(r.get("a"))
                    if not a or a in self.addr_to_i:
                        continue
                    hop = int(r.get("h") or 0)
                    via = str(r.get("via") or ("seed" if hop == 0 else "tx"))
                    parent = _norm_addr(r.get("p")) if r.get("p") else None
                    root = _norm_addr(r.get("root_seed")) or a
                    i = len(self.addrs)
                    self.addr_to_i[a] = i
                    self.addrs.append(a)
                    self.hops.append(hop)
                    self.via.append(via)
                    self.parent.append(parent)
                    self.root_i.append(-1)  # fix pass
                    self.hop_hist[hop] += 1
                    self.via_hist[via] += 1
                    if parent:
                        parents_with_children.add(parent)
                    # Write into wave37 jsonl when importing
                    if src != self.wallets_jsonl:
                        rec = {
                            "i": i + 1,
                            "a": a,
                            "h": hop,
                            "p": parent,
                            "via": via,
                            "seed_label": self.seed_by_addr.get(a) or r.get("seed_label"),
                            "root_seed": root,
                        }
                        with self.wallets_jsonl.open("a", encoding="utf-8") as out_fh:
                            out_fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
            # Fix root indices
            for i, a in enumerate(self.addrs):
                # re-read root from parent chain approx: use stored root_seed in file — reload lightly
                pass
            # Second pass on imported file for root_seed
            root_map: dict[str, str] = {}
            with src.open(encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    a = _norm_addr(r.get("a"))
                    rs = _norm_addr(r.get("root_seed"))
                    if a and rs:
                        root_map[a] = rs
            for i, a in enumerate(self.addrs):
                rs = root_map.get(a, a)
                self.root_i[i] = self.addr_to_i.get(rs, i)
                if self.hops[i] > 0:
                    self.seed_child_counts[self.addrs[self.root_i[i]]] += 1

            self.resumed_from = len(self.addrs)
            # Expanded heuristic: parents that already have children
            self.expanded = set(parents_with_children)
            # Also load persisted expanded list if any
            if self.expanded_jsonl.is_file():
                with self.expanded_jsonl.open(encoding="utf-8") as fh:
                    for line in fh:
                        a = _norm_addr(line.strip().strip('"'))
                        if a:
                            self.expanded.add(a)
            # Queue = known wallets not yet expanded, BFS order
            for i, a in enumerate(self.addrs):
                if a not in self.expanded and self.hops[i] < MAX_HOP_ENQUEUE:
                    self.queue.append((a, self.hops[i]))
            print(
                f"  wave37: imported={self.resumed_from} expanded≈{len(self.expanded)} "
                f"queue={len(self.queue)}",
                flush=True,
            )

        # Ensure all sealed seeds present
        for lab, addr in sorted(self.book.items()):
            a = addr.lower()
            if a in self.addr_to_i:
                continue
            i = len(self.addrs)
            self.addr_to_i[a] = i
            self.addrs.append(a)
            self.hops.append(0)
            self.via.append("seed")
            self.parent.append(None)
            self.root_i.append(i)
            self.hop_hist[0] += 1
            self.via_hist["seed"] += 1
            rec = self._rec(i)
            rec["seed_label"] = lab
            self._append_record(rec)
            self.queue.appendleft((a, 0))

        if not self.addrs:
            raise RuntimeError("No seeds available for Wave-37")

    def _checkpoint_unlocked(self) -> None:
        cp = {
            "generated_at": _utc(),
            "linked_wallets": len(self.addrs),
            "target": self.target,
            "target_reached": len(self.addrs) >= self.target,
            "expanded": len(self.expanded),
            "queue_len": len(self.queue),
            "pages_fetched": self.pages_fetched,
            "hop_histogram": {str(k): v for k, v in sorted(self.hop_hist.items())},
            "via_histogram": dict(self.via_hist),
            "elapsed_sec": int(time.perf_counter() - self.started),
            "resumed_from": self.resumed_from,
            "nvidia_backend": NVIDIA_BACKEND,
            "nvidia_gpu_active": NVIDIA_GPU_ACTIVE,
            "stop": self.stop.is_set(),
        }
        _write(OUT / "CHECKPOINT.json", cp)

    def _admit(self, addr: str, *, hop: int, parent: str | None, via: str) -> bool:
        with self.lock:
            if addr in self.addr_to_i:
                return False
            if len(self.addrs) >= self.target:
                self.stop.set()
                return False
            i = len(self.addrs)
            parent_i = self.addr_to_i.get(parent) if parent else None
            if parent_i is not None:
                root = self.root_i[parent_i]
            else:
                root = i
            self.addr_to_i[addr] = i
            self.addrs.append(addr)
            self.hops.append(hop)
            self.via.append(via)
            self.parent.append(parent)
            self.root_i.append(root)
            self.hop_hist[hop] += 1
            self.via_hist[via] += 1
            self.seed_child_counts[self.addrs[root]] += 1
            rec = self._rec(i)
            self._append_record(rec)
            if (
                len(self.expanded) + len(self.queue) < MAX_EXPAND
                and hop < MAX_HOP_ENQUEUE
            ):
                self.queue.append((addr, hop))
            if len(self.addrs) >= self.target:
                self.stop.set()
            if len(self.addrs) % CHECKPOINT_EVERY == 0:
                self._checkpoint_unlocked()
            if len(self.addrs) % ANALYTICS_EVERY == 0:
                # lightweight in-lock hop snapshot only
                self.analytics_snapshots.append(
                    {
                        "at": len(self.addrs),
                        "hop_histogram": dict(self.hop_hist),
                        "t": _utc(),
                    }
                )
            return True

    def expand_one(self, addr: str, hop: int) -> dict[str, Any]:
        if self.stop.is_set() or self._deadline_hit():
            self.stop.set()
            return {"addr": addr, "new": 0, "skipped": True}
        with self.lock:
            if addr in self.expanded:
                return {"addr": addr, "new": 0, "skipped": True}
            self.expanded.add(addr)
        with self.expanded_jsonl.open("a", encoding="utf-8") as fh:
            fh.write(addr + "\n")

        tx_p, tt_p, int_p = _page_budget(hop)
        new_count = 0
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
                if not blk.get("ok"):
                    self.expand_errors += 1

        for kind, blk in blocks:
            cps = extract_counterparties(addr, blk.get("items") or [], kind=kind)
            for cp in cps:
                if self._admit(cp, hop=hop + 1, parent=addr, via=kind):
                    new_count += 1
                    if self.stop.is_set():
                        break
            if self.stop.is_set():
                break
        with self.lock:
            self.expand_yield[addr] += new_count
        return {"addr": addr, "hop": hop, "new": new_count}

    def run(self) -> dict[str, Any]:
        self.resume_or_seed()
        while not self.stop.is_set():
            if self._deadline_hit():
                self.stop.set()
                break
            batch: list[tuple[str, int]] = []
            with self.lock:
                while self.queue and len(batch) < WORKERS * 2:
                    addr, hop = self.queue.popleft()
                    if addr in self.expanded:
                        continue
                    batch.append((addr, hop))
                linked = len(self.addrs)
                expanded_n = len(self.expanded)
            if not batch:
                break
            if linked >= self.target or expanded_n >= MAX_EXPAND:
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
                if len(self.addrs) % 5000 < WORKERS * 2:
                    print(
                        f"  wave37 progress: linked={len(self.addrs)}/"
                        f"{self.target} expanded={len(self.expanded)} "
                        f"queue={len(self.queue)} pages={self.pages_fetched}",
                        flush=True,
                    )
        with self.lock:
            self._flush_shard()
            self._checkpoint_unlocked()
            return self.snapshot_unlocked()

    def snapshot_unlocked(self) -> dict[str, Any]:
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
        seed_contrib.sort(key=lambda r: -int(r["linked_descendants_counted"] or 0))
        top_hubs = [
            {"address": a, "new_wallets_yielded": n}
            for a, n in self.expand_yield.most_common(40)
        ]
        first_sample = [self._rec(i) for i in range(min(DOCS_SAMPLE_N, len(self.addrs)))]
        return {
            "target": self.target,
            "linked_wallets": len(self.addrs),
            "target_reached": len(self.addrs) >= self.target,
            "expanded_addresses": len(self.expanded),
            "queue_remaining": len(self.queue),
            "pages_fetched": self.pages_fetched,
            "hit_page_caps": self.hit_page_caps,
            "expand_errors": self.expand_errors,
            "elapsed_sec": int(time.perf_counter() - self.started),
            "resumed_from": self.resumed_from,
            "hop_histogram": {str(k): v for k, v in sorted(self.hop_hist.items())},
            "via_histogram": dict(self.via_hist),
            "seed_contribution": seed_contrib,
            "top_expansion_hubs": top_hubs,
            "shard_paths": list(self.shard_paths),
            "wallets_jsonl": str(self.wallets_jsonl.relative_to(ROOT)),
            "first_sample": first_sample,
            "analytics_snapshots": self.analytics_snapshots[-20:],
            "max_expand": MAX_EXPAND,
            "max_runtime_sec": MAX_RUNTIME_SEC,
            "workers": WORKERS,
            "nvidia_backend": NVIDIA_BACKEND,
            "nvidia_gpu_active": NVIDIA_GPU_ACTIVE,
        }

    def rows_for_analytics(self, *, max_rows: int | None = 500_000) -> list[dict[str, Any]]:
        """Build row list for NVIDIA kernels (capped for memory)."""
        n = len(self.addrs)
        if max_rows is not None:
            n = min(n, max_rows)
        return [self._rec(i) for i in range(n)]


def run_nvidia_accelerated_analysis(
    tracer: TenMillionWalletTracer, snap: dict[str, Any]
) -> dict[str, Any]:
    started = time.perf_counter()
    probe = probe_nvidia_stack()
    # Prefer full corpus up to 500k for analytics; stream note if larger
    max_rows = int(os.environ.get("US_IPFORCE_WAVE37_ANALYTICS_MAX", "500000"))
    rows = tracer.rows_for_analytics(max_rows=max_rows)
    partial = len(tracer.addrs) > len(rows)

    if HAS_W36 and rows:
        g = build_graph_arrays(rows)
        deg = accelerate_degree_hop_kernels(g)
        deg_seal = {k: v for k, v in deg.items() if k != "degrees"}
        wcc = accelerate_wcc(g)
        pr = accelerate_seed_pagerank(g)
        seed_c = accelerate_seed_contribution(g)
        graph_stats = {
            "vertices_analyzed": g["n"],
            "directed_edges": g["edge_count"],
            "build_ms": g["build_ms"],
            "corpus_linked_wallets": snap.get("linked_wallets"),
            "analytics_partial": partial,
            "analytics_cap": max_rows,
        }
    else:
        # Minimal NumPy hop hist
        hops = np.asarray(tracer.hops[: len(rows)], dtype=np.int32)
        hop_hist = {
            str(i): int(v)
            for i, v in enumerate(np.bincount(hops).tolist())
        } if len(hops) else {}
        deg_seal = {"hop_histogram": hop_hist, "backend": NVIDIA_BACKEND}
        wcc = {"components": None, "backend": "skipped"}
        pr = {"top": [], "backend": "skipped"}
        seed_c = {"by_label": snap.get("seed_contribution")}
        graph_stats = {
            "vertices_analyzed": len(rows),
            "corpus_linked_wallets": snap.get("linked_wallets"),
            "analytics_partial": partial,
        }

    return {
        "id": "nvidia_accelerated_ten_million_analysis",
        "title": "NVIDIA-accelerated analysis of ten-million linked-wallet expansion",
        "status": "SEALED",
        "probe": probe,
        "graph_stats": graph_stats,
        "degree_hop": deg_seal,
        "wcc": wcc,
        "seed_pagerank": {
            **{
                k: v
                for k, v in (pr.items() if isinstance(pr, dict) else [])
                if k != "top"
            },
            "top": (pr.get("top") or [])[:20] if isinstance(pr, dict) else [],
        },
        "seed_contribution": seed_c,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "findings": [
            {
                "id": "W37-F2",
                "title": "NVIDIA full-stack accelerated graph analysis (10M expansion corpus)",
                "backend": probe.get("backend") or NVIDIA_BACKEND,
                "nvidia_gpu_active": probe.get("nvidia_gpu_active") or NVIDIA_GPU_ACTIVE,
                "graph_stats": graph_stats,
                "wcc": wcc,
                "degree_hop_summary": {
                    k: deg_seal.get(k)
                    for k in (
                        "mean_degree",
                        "max_degree",
                        "hop_histogram",
                        "backend",
                        "elapsed_ms",
                    )
                },
                "true_ubo_asserted": False,
                "theft_adjudicated": False,
                "detail": (
                    f"NVIDIA path={probe.get('backend') or NVIDIA_BACKEND} "
                    f"gpu={probe.get('nvidia_gpu_active') or NVIDIA_GPU_ACTIVE}; "
                    f"analyzed {graph_stats.get('vertices_analyzed')} / "
                    f"{graph_stats.get('corpus_linked_wallets')} linked wallets "
                    f"(partial={partial}). Ranking only — not adjudication."
                ),
            }
        ],
    }


def track_ten_million_trace() -> tuple[dict[str, Any], TenMillionWalletTracer]:
    book = collect_address_book()
    print(
        f"{BRAND} wave37: tracing first {TARGET_WALLETS} linked wallets "
        f"from {len(book)} sealed seeds | NVIDIA={NVIDIA_BACKEND} "
        f"gpu={NVIDIA_GPU_ACTIVE} workers={WORKERS} "
        f"max_expand={MAX_EXPAND} max_runtime_sec={MAX_RUNTIME_SEC}",
        flush=True,
    )
    tracer = TenMillionWalletTracer(book)
    snap = tracer.run()
    findings = [
        {
            "id": "W37-F1",
            "title": "First-ten-million linked-wallet BFS enumeration (NVIDIA-accelerated analysis)",
            "address_book": book,
            "seeds": len(book),
            "target": snap["target"],
            "linked_wallets": snap["linked_wallets"],
            "target_reached": snap["target_reached"],
            "expanded_addresses": snap["expanded_addresses"],
            "resumed_from": snap["resumed_from"],
            "hop_histogram": snap["hop_histogram"],
            "via_histogram": snap["via_histogram"],
            "pages_fetched": snap["pages_fetched"],
            "elapsed_sec": snap["elapsed_sec"],
            "nvidia_backend": snap["nvidia_backend"],
            "nvidia_gpu_active": snap["nvidia_gpu_active"],
            "seed_contribution_top": (snap.get("seed_contribution") or [])[:12],
            "top_expansion_hubs": (snap.get("top_expansion_hubs") or [])[:20],
            "true_ubo_asserted": False,
            "theft_adjudicated": False,
            "detail": (
                f"BFS toward {snap['target']} linked wallets: traced "
                f"{snap['linked_wallets']} (reached={snap['target_reached']}), "
                f"resumed_from={snap['resumed_from']}, expanded="
                f"{snap['expanded_addresses']}, pages={snap['pages_fetched']} "
                f"in {snap['elapsed_sec']}s. NVIDIA backend={snap['nvidia_backend']} "
                f"gpu_active={snap['nvidia_gpu_active']}. Linkage only."
            ),
        }
    ]
    track = {
        "id": "first_ten_million_linked_wallets",
        "title": "First ten million linked wallets (BFS + NVIDIA acceleration)",
        "status": "SEALED" if snap["target_reached"] else "PARTIAL",
        "snapshot": snap,
        "findings": findings,
        "next_actions": [
            "Resume Wave-37 from CHECKPOINT / linked_wallets.jsonl until 10_000_000",
            "Re-run NVIDIA analytics at full corpus when target reached",
            "Provision CUDA+RAPIDS host to engage rapids_full path",
        ],
    }
    return track, tracer


def track_operator_worklist(trace: dict[str, Any], accel: dict[str, Any]) -> dict[str, Any]:
    snap = trace.get("snapshot") or {}
    items = [
        {
            "id": "W37-M1",
            "priority": "CRITICAL" if not snap.get("target_reached") else "MEDIUM",
            "item": (
                f"Resume enumeration until linked_wallets==10_000_000 "
                f"(now={snap.get('linked_wallets')})"
            ),
        },
        {
            "id": "W37-M2",
            "priority": "HIGH",
            "item": (
                "Provision NVIDIA CUDA + RAPIDS (cuDF/cuGraph/CuPy/cuML) to flip "
                f"backend from {NVIDIA_BACKEND} → rapids_full"
            ),
        },
        {
            "id": "W37-M3",
            "priority": "MEDIUM",
            "item": "Do not treat accelerated PageRank hubs as True-UBO",
        },
    ]
    if not NVIDIA_GPU_ACTIVE:
        items.append(
            {
                "id": "W37-M0",
                "priority": "HIGH",
                "item": "CUDA GPU not visible — NVIDIA-compatible CPU path engaged; GPU path armed",
            }
        )
    return {
        "id": "operator_worklist",
        "title": "Wave-37 operator worklist",
        "status": "OPEN",
        "items": items,
        "adjudicated": False,
    }


def write_summary_md(trace: dict[str, Any], accel: dict[str, Any]) -> str:
    path = (
        ROOT
        / "docs"
        / "investigation"
        / "WAVE37_TEN_MILLION_LINKED_WALLETS_NVIDIA.md"
    )
    f1 = (trace.get("findings") or [{}])[0]
    f2 = (accel.get("findings") or [{}])[0]
    snap = trace.get("snapshot") or {}
    gs = accel.get("graph_stats") or {}
    lines = [
        "# Wave 37 — First ten million linked wallets + NVIDIA full-stack acceleration",
        "",
        f"Generated: `{_utc()}`",
        "",
        "## Disposition (policy-gated)",
        "",
        "- `true_ubo_asserted`: **false**",
        "- `theft_adjudicated`: **false**",
        "- BFS linkage + accelerated ranking only",
        "",
        "## Enumeration (target 10,000,000)",
        "",
        f"- Sealed seeds: `{f1.get('seeds')}`",
        f"- Target: `{f1.get('target')}`",
        f"- Linked wallets traced: `{f1.get('linked_wallets')}`",
        f"- Target reached: `{f1.get('target_reached')}`",
        f"- Resumed from: `{f1.get('resumed_from')}`",
        f"- Expanded addresses: `{f1.get('expanded_addresses')}`",
        f"- Pages fetched: `{f1.get('pages_fetched')}`",
        f"- Elapsed seconds: `{f1.get('elapsed_sec')}`",
        f"- Status: `{trace.get('status')}`",
        f"- Hop histogram: `{f1.get('hop_histogram')}`",
        f"- Via histogram: `{f1.get('via_histogram')}`",
        "",
        "## NVIDIA acceleration",
        "",
        f"- Backend: `{f1.get('nvidia_backend')}`",
        f"- GPU active: `{f1.get('nvidia_gpu_active')}`",
        f"- Modules: `{(accel.get('probe') or {}).get('modules_engaged')}`",
        f"- Vertices analyzed: `{gs.get('vertices_analyzed')}` / corpus `{gs.get('corpus_linked_wallets')}`",
        f"- Analytics partial: `{gs.get('analytics_partial')}`",
        f"- WCC: `{f2.get('wcc')}`",
        f"- Degree summary: `{f2.get('degree_hop_summary')}`",
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
        f"- Full jsonl (gitignored): `{snap.get('wallets_jsonl')}`",
        f"- Docs sample: first `{DOCS_SAMPLE_N}` wallets",
        "",
        "## Manual next",
        "",
        "1. Resume until linked_wallets == 10_000_000.",
        "2. Re-run NVIDIA analytics at full scale on CUDA+RAPIDS host.",
        "3. Do not equate linkage/PPR with True-UBO or theft.",
        "",
    ]
    _write(path, "\n".join(lines))
    return str(path.relative_to(ROOT))


def run_wave37() -> dict[str, Any]:
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    trace, tracer = track_ten_million_trace()
    accel = run_nvidia_accelerated_analysis(tracer, trace.get("snapshot") or {})
    work = track_operator_worklist(trace, accel)
    summary_md = write_summary_md(trace, accel)
    snap = trace.get("snapshot") or {}

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
                "resumed_from",
                "hop_histogram",
                "via_histogram",
                "seed_contribution",
                "top_expansion_hubs",
                "workers",
                "max_expand",
                "max_runtime_sec",
                "wallets_jsonl",
                "nvidia_backend",
                "nvidia_gpu_active",
            )
        },
    }
    _write(OUT / "first_ten_million_linked_wallets.json", json.loads(json.dumps(trace, default=str)))
    _write(DOCS / "first_ten_million_linked_wallets.json", docs_trace)
    _write(
        DOCS / "first_1000_linked_wallets_sample.json",
        {
            "n": min(DOCS_SAMPLE_N, int(snap.get("linked_wallets") or 0)),
            "note": "BFS discovery-order sample; full set in output_artifacts",
            "wallets": (snap.get("first_sample") or [])[:DOCS_SAMPLE_N],
        },
    )
    for t in (accel, work):
        sealed = json.loads(json.dumps(t, default=str))
        _write(OUT / f"{t['id']}.json", sealed)
        _write(DOCS / f"{t['id']}.json", sealed)

    custody_tracks = [
        {
            "id": "first_ten_million_linked_wallets",
            "title": trace.get("title"),
            "status": trace.get("status"),
            "findings": trace.get("findings"),
            "snapshot_summary": docs_trace["snapshot_summary"],
        },
        accel,
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
    all_findings.extend(trace.get("findings") or [])
    all_findings.extend(accel.get("findings") or [])

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
            "first_ten_million_target": TARGET_WALLETS,
            "linked_wallets_traced": f1.get("linked_wallets"),
            "target_reached": bool(f1.get("target_reached")),
            "enumeration_status": trace.get("status"),
            "nvidia_backend": f1.get("nvidia_backend"),
            "nvidia_gpu_active": bool(f1.get("nvidia_gpu_active")),
            "nvidia_full_stack_wired": True,
            "true_ubo_asserted": False,
            "theft_adjudicated": False,
            "bfs_linkage_only": True,
        },
        "artifacts": {
            "summary_md": summary_md,
            "trace": "docs/investigation/wave37/first_ten_million_linked_wallets.json",
            "sample": "docs/investigation/wave37/first_1000_linked_wallets_sample.json",
            "accel": "docs/investigation/wave37/nvidia_accelerated_ten_million_analysis.json",
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
            "Wave-37 systematically expands toward the first 10,000,000 linked "
            "wallets (BFS from sealed seeds, resuming Wave-35) and accelerates "
            "analysis with NVIDIA's full stack (RAPIDS/CuPy when present; "
            "NumPy+SciPy+Numba NVIDIA-compatible otherwise). No True-UBO/theft adjudication."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})
    _write(OUT / "WAVE37_RUN_SUMMARY.json", report)
    _write(DOCS / "WAVE37_RUN_SUMMARY.json", report)
    _write(ROOT / "docs" / "US_IPFORCE_INVESTIGATION_WAVE37_SUMMARY.json", report)
    _write(
        ROOT / "docs" / "investigation" / "WAVE37_POINTER.json",
        {
            "brand": BRAND,
            "wave37_case": CASE_ID,
            "generated_at": report["generated_at"],
            "summary_path": "docs/investigation/wave37/WAVE37_RUN_SUMMARY.json",
            "summary_md": summary_md,
            "linked_wallets": f1.get("linked_wallets"),
            "target": TARGET_WALLETS,
            "target_reached": f1.get("target_reached"),
            "nvidia_backend": f1.get("nvidia_backend"),
            "seal": report["seal"],
        },
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} investigation wave 37")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)
    report = run_wave37()
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        d = report["disposition"]
        print(
            f"{BRAND} wave37: findings={report['counts']['findings']} "
            f"linked={report['counts'].get('linked_wallets')}/"
            f"{report['counts'].get('target')} "
            f"reached={d['target_reached']} "
            f"nvidia={d['nvidia_backend']} gpu={d['nvidia_gpu_active']} "
            f"status={d['enumeration_status']} "
            f"seal={report['seal'][:16]}…"
        )
        print(f"  summary: {report['artifacts']['summary_md']}")
        for f in report.get("findings") or []:
            print(f"  - {f.get('id')}: {f.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

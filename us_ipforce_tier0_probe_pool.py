#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IP FORCE — rate-limited Tier-0 probe pool (stdlib urllib + ThreadPoolExecutor).

Probes only endpoints marked wired with auth=none (or env-backed keys present).
Promotes status to probe_ok on HTTP < 400. Never fabricates success.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.22-TIER0-PROBE-POOL"
ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "data" / "public_source_registry.json"
OUT = ROOT / "output_artifacts" / "tier0_probes"
SUMMARY = OUT / "TIER0_PROBE_SUMMARY.json"

USER_AGENT = "IP-FORCE-Tier0Probe/2026.7.22 (+research; rate-limited)"


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _sha3(obj: Any) -> str:
    return hashlib.sha3_256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _reject_community(value: str) -> bool:
    v = (value or "").strip().lower()
    return (not v) or v.startswith("community-") or "demo" in v or "placeholder" in v


def _probe_url(url: str, timeout: float = 12.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*"},
        method="GET",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(65536)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return {
                "ok": 200 <= resp.status < 400,
                "status_code": resp.status,
                "elapsed_ms": elapsed_ms,
                "bytes": len(body),
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": False,
            "status_code": exc.code,
            "elapsed_ms": elapsed_ms,
            "bytes": 0,
            "error": f"HTTPError:{exc.code}",
        }
    except Exception as exc:  # noqa: BLE001 — probe pool must never crash
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": False,
            "status_code": None,
            "elapsed_ms": elapsed_ms,
            "bytes": 0,
            "error": type(exc).__name__,
        }


def _resolve_probe_url(ep: dict[str, Any]) -> str | None:
    base = (ep.get("base_url") or "").rstrip("/")
    path = ep.get("path") or ""
    if not base or "{" in path:
        return None
    if ep.get("auth") not in (None, "", "none"):
        # Only probe auth endpoints when a real env key exists and verified mode allows
        env_name = str(ep["auth"]).split()[0]
        if env_name.endswith("_KEY") or env_name.endswith("_TOKEN") or env_name.isupper():
            val = os.environ.get(env_name, "")
            if _reject_community(val):
                return None
        else:
            return None
    # Concrete safe probe URLs (avoid markets that need query params)
    service = ep.get("service")
    eid = ep.get("endpoint_id")
    overrides = {
        "PUB-CRYPTO-002": f"{base}/api/v3/coins/markets?vs_currency=usd&per_page=1",
        "PUB-CRYPTO-009": f"{base}/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
        "PUB-CRYPTO-018": f"{base}/api/v3/search?query=bitcoin",
        "PUB-SCI-001": f"{base}/api/query?search_query=all:patent&start=0&max_results=1",
        "PUB-GOV-007": f"{base}/api/v1/documents.json?per_page=1",
        "PUB-NEWS-010": f"{base}/wayback/available?url=example.com",
        "PUB-SOC-006": f"{base}/w/api.php?action=query&meta=siteinfo&format=json",
        "PUB-SOC-007": f"{base}/w/api.php?action=wbgetentities&ids=Q42&format=json",
    }
    if eid in overrides:
        return overrides[eid]
    if service == "CoinGecko" and path.endswith("/list"):
        return f"{base}{path}"
    return f"{base}{path}"


def run_probes(
    *,
    max_workers: int = 8,
    limit: int | None = None,
    min_interval_s: float = 0.15,
) -> dict[str, Any]:
    if not REGISTRY.is_file():
        from scripts.sync_public_source_registry import main as sync_main

        sync_main([])

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    candidates = [
        e
        for e in registry.get("endpoints", [])
        if e.get("status") in {"wired", "probe_ok"} and e.get("auth") in (None, "", "none")
    ]
    if limit is not None:
        candidates = candidates[:limit]

    results: list[dict[str, Any]] = []
    last_by_host: dict[str, float] = {}

    def _task(ep: dict[str, Any]) -> dict[str, Any]:
        url = _resolve_probe_url(ep)
        if not url:
            return {
                "endpoint_id": ep["endpoint_id"],
                "service": ep["service"],
                "skipped": True,
                "reason": "unresolvable_or_auth",
            }
        host = urllib.parse.urlparse(url).netloc
        # light per-host spacing inside worker (best-effort)
        now = time.time()
        wait = min_interval_s - (now - last_by_host.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        last_by_host[host] = time.time()
        probe = _probe_url(url)
        return {
            "endpoint_id": ep["endpoint_id"],
            "service": ep["service"],
            "url": url,
            "skipped": False,
            **probe,
        }

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        futs = [pool.submit(_task, ep) for ep in candidates]
        for fut in as_completed(futs):
            results.append(fut.result())

    # Promote probe_ok in a copy of registry (persisted)
    ok_ids = {r["endpoint_id"] for r in results if r.get("ok")}
    for ep in registry.get("endpoints", []):
        if ep["endpoint_id"] in ok_ids:
            ep["status"] = "probe_ok"
            ep["last_probe_at"] = _utc()

    by_status: dict[str, int] = {}
    for ep in registry.get("endpoints", []):
        by_status[ep["status"]] = by_status.get(ep["status"], 0) + 1
    registry["counts"]["by_status"] = dict(sorted(by_status.items()))
    registry["generated_at"] = _utc()
    body = {k: v for k, v in registry.items() if k != "seal"}
    registry["seal"] = _sha3(body)
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    probed = [r for r in results if not r.get("skipped")]
    summary = {
        "brand": BRAND,
        "version": VERSION,
        "generated_at": _utc(),
        "max_workers": max_workers,
        "candidates": len(candidates),
        "probed": len(probed),
        "probe_ok": sum(1 for r in probed if r.get("ok")),
        "probe_fail": sum(1 for r in probed if not r.get("ok")),
        "skipped": sum(1 for r in results if r.get("skipped")),
        "by_status_after": registry["counts"]["by_status"],
        "results": sorted(results, key=lambda r: r.get("endpoint_id", "")),
        "policy": (
            "HTTP<400 only → probe_ok. No adjudications. "
            "community-* keys rejected. Stdlib urllib + ThreadPoolExecutor."
        ),
    }
    summary["seal"] = _sha3({k: v for k, v in summary.items() if k != "seal"})
    OUT.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} Tier-0 probe pool")
    parser.add_argument("--workers", type=int, default=int(os.environ.get("US_IPFORCE_PROBE_WORKERS", "8")))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args(argv)

    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    summary = run_probes(max_workers=args.workers, limit=args.limit)
    if args.print_summary:
        print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    else:
        print(
            f"{BRAND} tier0 probes: probed={summary['probed']} "
            f"ok={summary['probe_ok']} fail={summary['probe_fail']} "
            f"workers={summary['max_workers']} seal={summary['seal'][:16]}…"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

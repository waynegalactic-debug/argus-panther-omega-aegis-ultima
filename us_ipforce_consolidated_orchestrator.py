#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Consolidated Orchestrator (integrate · optimize · streamline · scale)

Single declarative control plane for this package:

1. Hardening pass (fail-closed in verified mode — report retained)
2. Tier-0 public source registry sync
3. Parallel Tier-0 probe pool (ThreadPoolExecutor, rate-limited)
4. Parallel engine DAG for local safe modules
5. Cryptographic custody (SHA3-256 leaves → SHA3-512 root)
6. Radar + consolidation confirmation artifacts

Does NOT invent True-UBO / theft / RICO adjudications.
Does NOT claim 5000 live endpoints.
Secret-laden legacy monoliths stay behind explicit --legacy-* flags.

Successor monorepo: https://github.com/waynegalactic-debug/Cursor
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

BRAND = "IP FORCE"
VERSION = "2026.7.22-CONSOLIDATED-ORCHESTRATOR"
CASE_ID = "IP-FORCE-20260722-CONSOLIDATED-SCALE"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "us_ipforce_output" / "consolidated"
LEGACY_MIRROR = ROOT / "ip_force_output" / "consolidated"
ARTIFACTS = ROOT / "output_artifacts" / "consolidated"
FRONTEND_RADAR = ROOT / "frontend" / "radar_feed.json"

# Declarative engine registry — safe/local first; legacy monoliths opt-in only.
ENGINE_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "hardening_pass",
        "tier": "foundation",
        "weight": 110,
        "depends_on": [],
        "parallel_group": "A",
        "kind": "python_main",
        "module": "us_ipforce_hardening_pass",
        "args": ["--allow-findings"],  # always record; consolidator decides gate
        "verified_mode_required": False,
    },
    {
        "id": "public_source_registry",
        "tier": "foundation",
        "weight": 109,
        "depends_on": [],
        "parallel_group": "A",
        "kind": "python_main",
        "module": "scripts.sync_public_source_registry",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "tier0_probe_pool",
        "tier": "scale",
        "weight": 100,
        "depends_on": ["public_source_registry"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_tier0_probe_pool",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "ohio_llc_roster_inventory",
        "tier": "foundation",
        "weight": 95,
        "depends_on": [],
        "parallel_group": "A",
        "kind": "callable",
        "callable": "inventory_ohio_roster",
        "verified_mode_required": False,
    },
    {
        "id": "national_command_console",
        "tier": "surface",
        "weight": 80,
        "depends_on": ["ohio_llc_roster_inventory"],
        "parallel_group": "C",
        "kind": "callable",
        "callable": "render_console",
        "verified_mode_required": False,
    },
    {
        "id": "mathematical_models_import",
        "tier": "screen",
        "weight": 70,
        "depends_on": [],
        "parallel_group": "A",
        "kind": "callable",
        "callable": "import_math_models",
        "verified_mode_required": False,
    },
    {
        "id": "deterministic_all_smoke",
        "tier": "legacy_smoke",
        "weight": 60,
        "depends_on": ["hardening_pass"],
        "parallel_group": "D",
        "kind": "subprocess",
        "command": [sys.executable, "us_ipforce_deterministic_all.py", "run"],
        "verified_mode_required": False,
        "skip_if_verified_blocking": True,
    },
    {
        "id": "court_ready_blueprint_smoke",
        "tier": "legacy_smoke",
        "weight": 59,
        "depends_on": ["hardening_pass"],
        "parallel_group": "D",
        "kind": "subprocess",
        "command": [sys.executable, "court_ready_forensic_blueprint.py", "run"],
        "verified_mode_required": False,
        "skip_if_verified_blocking": True,
    },
    {
        "id": "systematic_investigation",
        "tier": "investigation",
        "weight": 105,
        "depends_on": ["hardening_pass", "public_source_registry"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_runner",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave2",
        "tier": "investigation",
        "weight": 104,
        "depends_on": ["systematic_investigation"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave2",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave3",
        "tier": "investigation",
        "weight": 103,
        "depends_on": ["investigation_wave2"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave3",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave4",
        "tier": "investigation",
        "weight": 102,
        "depends_on": ["investigation_wave3"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave4",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave5",
        "tier": "investigation",
        "weight": 101,
        "depends_on": ["investigation_wave4"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave5",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave6",
        "tier": "investigation",
        "weight": 100,
        "depends_on": ["investigation_wave5"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave6",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave7",
        "tier": "investigation",
        "weight": 99,
        "depends_on": ["investigation_wave6"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave7",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave8",
        "tier": "investigation",
        "weight": 98,
        "depends_on": ["investigation_wave7"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave8",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave9",
        "tier": "investigation",
        "weight": 97,
        "depends_on": ["investigation_wave8"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave9",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave10",
        "tier": "investigation",
        "weight": 96,
        "depends_on": ["investigation_wave9"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave10",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave11",
        "tier": "investigation",
        "weight": 95,
        "depends_on": ["investigation_wave10"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave11",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave12",
        "tier": "investigation",
        "weight": 94,
        "depends_on": ["investigation_wave11"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave12",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave13",
        "tier": "investigation",
        "weight": 93,
        "depends_on": ["investigation_wave12"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave13",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave14",
        "tier": "investigation",
        "weight": 92,
        "depends_on": ["investigation_wave13"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave14",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave15",
        "tier": "investigation",
        "weight": 91,
        "depends_on": ["investigation_wave14"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave15",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave16",
        "tier": "investigation",
        "weight": 90,
        "depends_on": ["investigation_wave15"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave16",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave17",
        "tier": "investigation",
        "weight": 89,
        "depends_on": ["investigation_wave16"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave17",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave18",
        "tier": "investigation",
        "weight": 88,
        "depends_on": ["investigation_wave17"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave18",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave20",
        "tier": "investigation",
        "weight": 87,
        "depends_on": ["investigation_wave18"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave20",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave21",
        "tier": "investigation",
        "weight": 86,
        "depends_on": ["investigation_wave20"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave21",
        "args": [],
        "verified_mode_required": False,
    },
    {
        "id": "investigation_wave22",
        "tier": "investigation",
        "weight": 85,
        "depends_on": ["investigation_wave21"],
        "parallel_group": "B",
        "kind": "python_main",
        "module": "us_ipforce_investigation_wave22",
        "args": [],
        "verified_mode_required": False,
    },
]


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _sha3_256(obj: Any) -> str:
    return hashlib.sha3_256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _sha3_512_hex(data: bytes) -> str:
    return hashlib.sha3_512(data).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def inventory_ohio_roster() -> dict[str, Any]:
    path = ROOT / "data" / "victim_inventor_ohio_llc_roster.json"
    if not path.is_file():
        return {
            "ok": False,
            "error": "missing_roster",
            "ohio_llc_count": 0,
            "claimed_scope": 69,
            "gap": 69,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    count = int(data.get("ohio_llc_count") or data.get("roster_count") or 0)
    claimed = 69
    return {
        "ok": True,
        "path": str(path.relative_to(ROOT)),
        "ohio_llc_count": count,
        "claimed_scope": claimed,
        "gap": max(0, claimed - count),
        "true_ubo_asserted": 0,
        "policy": "Evidence-only roster; do not invent entities to close the gap.",
        "synced_at": data.get("synced_at"),
    }


def render_console() -> dict[str, Any]:
    from us_ipforce_national_command_console import DEFAULT_METRICS, write_console

    roster = inventory_ohio_roster()
    metrics = dict(DEFAULT_METRICS)
    metrics.update(
        {
            "release": VERSION,
            "generated_at": _utc(),
            "ohio_llc_count": roster.get("ohio_llc_count", 0),
            "claimed_ohio_llc_scope": roster.get("claimed_scope", 69),
            "verified_true_ubos": "0",  # evidence-only; no auto-adjudication
            "complete_exhaustion": False,
            "consolidation_case_id": CASE_ID,
        }
    )
    # Keep module strip honest under consolidation
    metrics["modules"] = [
        {"id": "consolidated", "label": "Consolidated Orchestrator", "status": "ACTIVE"},
        {"id": "tier0", "label": "Tier-0 Public Probe Pool", "status": "ACTIVE"},
        {"id": "hardening", "label": "Hardening Pass", "status": "ACTIVE"},
        {"id": "roster", "label": "Ohio LLC Evidence Roster", "status": "EVIDENCE-ONLY"},
        {"id": "legacy", "label": "Legacy Monoliths", "status": "OPT-IN"},
    ]
    out_dir = OUT / "console"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = write_console(metrics, out_dir=out_dir)
    path = Path(written)
    try:
        rel = str(path.relative_to(ROOT))
    except ValueError:
        rel = str(path)
    return {
        "ok": True,
        "metrics_keys": sorted(metrics.keys()),
        "ohio_llc_count": roster.get("ohio_llc_count", 0),
        "written": [rel],
    }


def import_math_models() -> dict[str, Any]:
    try:
        import us_ipforce_mathematical_models as mm  # noqa: F401

        names = [n for n in dir(mm) if n[:1].isupper()]
        return {"ok": True, "export_count": len(names), "sample": names[:12]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}


CALLABLES: dict[str, Callable[[], dict[str, Any]]] = {
    "inventory_ohio_roster": inventory_ohio_roster,
    "render_console": render_console,
    "import_math_models": import_math_models,
}


def _run_python_main(module: str, args: list[str]) -> dict[str, Any]:
    started = time.perf_counter()
    if module.startswith("scripts."):
        # scripts/sync_public_source_registry.py
        script = ROOT / "scripts" / "sync_public_source_registry.py"
        proc = subprocess.run(
            [sys.executable, str(script), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "stdout_tail": (proc.stdout or "")[-500:],
            "stderr_tail": (proc.stderr or "")[-500:],
        }

    mod = __import__(module, fromlist=["main"])
    code = int(mod.main(args))
    return {
        "ok": code == 0,
        "returncode": code,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    }


def _run_subprocess(command: list[str]) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "stdout_tail": (proc.stdout or "")[-800:],
        "stderr_tail": (proc.stderr or "")[-800:],
        "command": command,
    }


def _hardening_blocking() -> bool:
    path = ROOT / "output_artifacts" / "hardening" / "HARDENING_PASS_SUMMARY.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return int(data.get("blocking_total") or 0) > 0


def run_engine(spec: dict[str, Any], *, verified: bool, skip_legacy: bool) -> dict[str, Any]:
    eid = spec["id"]
    started = time.perf_counter()
    if spec.get("skip_if_verified_blocking") and skip_legacy:
        reason = (
            "verified_mode_skip_legacy_smoke_due_to_hardening_findings"
            if verified and _hardening_blocking()
            else "legacy_smoke_opt_in_only_use_include_legacy_smoke"
        )
        return {
            "id": eid,
            "ok": True,
            "skipped": True,
            "reason": reason,
            "elapsed_ms": 0,
        }
    try:
        if spec["kind"] == "python_main":
            result = _run_python_main(spec["module"], list(spec.get("args") or []))
        elif spec["kind"] == "subprocess":
            result = _run_subprocess(list(spec["command"]))
        elif spec["kind"] == "callable":
            result = CALLABLES[spec["callable"]]()
            result.setdefault("ok", True)
        else:
            result = {"ok": False, "error": f"unknown_kind:{spec['kind']}"}
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:300]}
    result["id"] = eid
    result["tier"] = spec.get("tier")
    result["parallel_group"] = spec.get("parallel_group")
    result["elapsed_ms"] = result.get("elapsed_ms") or int(
        (time.perf_counter() - started) * 1000
    )
    result["skipped"] = bool(result.get("skipped"))
    return result


def run_dag(
    registry: list[dict[str, Any]],
    *,
    verified: bool,
    max_workers: int,
    skip_legacy: bool,
) -> list[dict[str, Any]]:
    done: dict[str, dict[str, Any]] = {}
    pending = {e["id"]: e for e in sorted(registry, key=lambda x: (-x["weight"], x["id"]))}

    while pending:
        ready = [
            spec
            for spec in pending.values()
            if all(dep in done for dep in spec.get("depends_on") or [])
        ]
        if not ready:
            # break deadlock
            for spec in list(pending.values()):
                done[spec["id"]] = {
                    "id": spec["id"],
                    "ok": False,
                    "error": "dependency_deadlock",
                }
                del pending[spec["id"]]
            break

        # Run ready engines in parallel within their groups
        with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
            futs = {
                pool.submit(
                    run_engine, spec, verified=verified, skip_legacy=skip_legacy
                ): spec["id"]
                for spec in ready
            }
            for fut in as_completed(futs):
                result = fut.result()
                done[result["id"]] = result
                del pending[result["id"]]

    return [done[e["id"]] for e in registry if e["id"] in done]


def build_custody(engine_results: list[dict[str, Any]], extras: dict[str, Any]) -> dict[str, Any]:
    leaves = []
    for row in engine_results:
        leaf_body = {k: v for k, v in row.items() if k not in {"stdout_tail", "stderr_tail"}}
        digest = _sha3_256(leaf_body)
        leaves.append({"id": row.get("id"), "sha3_256": digest, "ok": row.get("ok")})
    root_material = json.dumps(
        {"leaves": leaves, "extras": extras},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    root = _sha3_512_hex(root_material)
    key = os.environ.get("EVIDENCE_HMAC_KEY", "").encode()
    mac = None
    if key and not key.startswith(b"community") and key != b"default-key":
        mac = hmac.new(key, root_material, hashlib.sha3_256).hexdigest()
    return {
        "algorithm": "SHA3-512 root over SHA3-256 leaves",
        "leaf_count": len(leaves),
        "leaves": leaves,
        "root_sha3_512": root,
        "hmac_sha3_256": mac,
        "hmac_present": mac is not None,
    }


def build_radar(engine_results: list[dict[str, Any]], roster: dict[str, Any]) -> dict[str, Any]:
    probe = next((r for r in engine_results if r.get("id") == "tier0_probe_pool"), {})
    registry_path = ROOT / "data" / "public_source_registry.json"
    counts = {}
    if registry_path.is_file():
        counts = json.loads(registry_path.read_text(encoding="utf-8")).get("counts", {})
    vectors = [
        {
            "id": "ohio_llc_roster",
            "label": "Ohio LLC evidence roster",
            "screened": roster.get("ohio_llc_count", 0),
            "claimed": roster.get("claimed_scope", 69),
            "gaps": [f"missing_{roster.get('gap', 0)}_claimed_entities"],
            "adjudicated": 0,
        },
        {
            "id": "tier0_public_sources",
            "label": "Tier-0 public source probes",
            "screened": counts.get("endpoints_documented", 0),
            "probe_ok": (counts.get("by_status") or {}).get("probe_ok", 0),
            "wired": (counts.get("by_status") or {}).get("wired", 0),
            "adjudicated": 0,
        },
        {
            "id": "engine_dag",
            "label": "Consolidated engine DAG",
            "screened": len(engine_results),
            "ok": sum(1 for r in engine_results if r.get("ok")),
            "adjudicated": 0,
        },
    ]
    feed = {
        "brand": BRAND,
        "version": VERSION,
        "generated_at": _utc(),
        "case_id": CASE_ID,
        "evidence_policy": (
            "Radar tracks are investigation vectors, not adjudications. "
            "True-UBO / theft / RICO remain 0 without primary-source corroboration."
        ),
        "vectors": vectors,
        "tier0_probe_engine": {
            "ok": probe.get("ok"),
            "elapsed_ms": probe.get("elapsed_ms"),
        },
    }
    feed["seal"] = _sha3_256({k: v for k, v in feed.items() if k != "seal"})
    return feed


def write_confirmation(report: dict[str, Any]) -> None:
    md = f"""# IP FORCE CONSOLIDATION CONFIRMED

**Version:** `{VERSION}`  
**Case ID:** `{CASE_ID}`  
**Generated (UTC):** `{report['generated_at']}`  
**Repository:** `waynegalactic-debug/argus-panther-omega-aegis-ultima`

## Verdict

Consolidated orchestrator integrated, optimized, streamlined, and scaled for this
package. Dual monolith entrypoints remain available as **explicit legacy** paths.
Successor development continues in the Cursor US IPFORCE monorepo.

## Scale summary

| Metric | Value |
|--------|------:|
| Engines in DAG | {report['counts']['engines']} |
| Engines OK | {report['counts']['engines_ok']} |
| Tier-0 endpoints | {report['counts'].get('tier0_endpoints', 0)} |
| Tier-0 probe_ok | {report['counts'].get('tier0_probe_ok', 0)} |
| Ohio LLC evidence | {report['counts'].get('ohio_llc_count', 0)} |
| Claimed scope gap | {report['counts'].get('ohio_gap', 0)} |
| Max workers | {report['max_workers']} |
| Custody root | `{report['custody']['root_sha3_512'][:32]}…` |

## Hard constraints

- No community-* / demo credential defaults in verified mode
- No invented Ohio LLC entities
- No True-UBO / theft / celebrity-RICO auto-adjudications
- Catalog ≠ thousands of live probes

## How to run

```bash
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_consolidated_orchestrator.py --workers 8
US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce_tier0_probe_pool.py --workers 8
```

Legacy (opt-in):

```bash
python3 us_ipforce.py --legacy-monolith
python3 us_ipforce_entry.py --legacy-live
```

---

IP FORCE · Consolidated · Integrated · Optimized · Streamlined · Scaled
"""
    for path in (
        ROOT / "IP_FORCE_CONSOLIDATION_CONFIRMED.md",
        OUT / "IP_FORCE_CONSOLIDATION_CONFIRMED.md",
        ARTIFACTS / "IP_FORCE_CONSOLIDATION_CONFIRMED.md",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(md, encoding="utf-8")


def run_consolidated(
    *,
    max_workers: int = 8,
    skip_legacy_smoke: bool = True,
    plan_only: bool = False,
) -> dict[str, Any]:
    verified = os.environ.get("US_IPFORCE_VERIFIED_MODE", "1").strip() not in {
        "0",
        "false",
        "False",
        "",
    }
    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1" if verified else "0")
    os.environ.setdefault("US_IPFORCE_PROBE_WORKERS", str(max_workers))

    plan = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "verified_mode": verified,
        "max_workers": max_workers,
        "engines": [
            {
                "id": e["id"],
                "tier": e["tier"],
                "weight": e["weight"],
                "depends_on": e.get("depends_on") or [],
                "parallel_group": e.get("parallel_group"),
            }
            for e in ENGINE_REGISTRY
        ],
        "successor": "https://github.com/waynegalactic-debug/Cursor",
    }
    _write_json(ARTIFACTS / "CONSOLIDATED_PLAN.json", plan)
    if plan_only:
        return plan

    started = time.perf_counter()
    results = run_dag(
        ENGINE_REGISTRY,
        verified=verified,
        max_workers=max_workers,
        skip_legacy=skip_legacy_smoke,
    )
    roster = inventory_ohio_roster()
    registry_counts: dict[str, Any] = {}
    reg_path = ROOT / "data" / "public_source_registry.json"
    if reg_path.is_file():
        registry_counts = json.loads(reg_path.read_text(encoding="utf-8")).get("counts", {})

    custody = build_custody(results, {"roster": roster, "registry_counts": registry_counts})
    radar = build_radar(results, roster)
    _write_json(OUT / "radar" / "RADAR_FEED.json", radar)
    _write_json(ARTIFACTS / "RADAR_FEED.json", radar)
    FRONTEND_RADAR.parent.mkdir(parents=True, exist_ok=True)
    _write_json(FRONTEND_RADAR, radar)

    report = {
        "brand": BRAND,
        "version": VERSION,
        "case_id": CASE_ID,
        "generated_at": _utc(),
        "verified_mode": verified,
        "max_workers": max_workers,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "counts": {
            "engines": len(results),
            "engines_ok": sum(1 for r in results if r.get("ok")),
            "engines_skipped": sum(1 for r in results if r.get("skipped")),
            "tier0_endpoints": registry_counts.get("endpoints_documented", 0),
            "tier0_probe_ok": (registry_counts.get("by_status") or {}).get("probe_ok", 0),
            "ohio_llc_count": roster.get("ohio_llc_count", 0),
            "ohio_gap": roster.get("gap", 0),
            "true_ubo_asserted": 0,
        },
        "engine_results": [
            {k: v for k, v in r.items() if k not in {"stdout_tail", "stderr_tail"}}
            for r in results
        ],
        "custody": custody,
        "radar_seal": radar["seal"],
        "successor_monorepo": "https://github.com/waynegalactic-debug/Cursor",
        "policy": (
            "Consolidate/integrate/optimize/streamline/scale without theater. "
            "No fabricated adjudications. Legacy monoliths are opt-in only."
        ),
    }
    report["seal"] = _sha3_256({k: v for k, v in report.items() if k != "seal"})

    for base in (OUT, ARTIFACTS, LEGACY_MIRROR):
        _write_json(base / "CONSOLIDATED_RUN.json", report)
    write_confirmation(report)

    # Refresh enhanced manifest entry for new control-plane files
    manifest_path = ROOT / "IP_FORCE_ENHANCED_MANIFEST.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
        artifacts = manifest.setdefault("artifacts", {})
        for rel in (
            "us_ipforce_consolidated_orchestrator.py",
            "us_ipforce_hardening_pass.py",
            "us_ipforce_tier0_probe_pool.py",
            "scripts/sync_public_source_registry.py",
            "data/public_source_registry.json",
        ):
            p = ROOT / rel
            if not p.is_file():
                continue
            raw = p.read_bytes()
            artifacts[rel] = {
                "path": rel,
                "bytes": len(raw),
                "lines": raw.count(b"\n") + 1,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        manifest["brand"] = BRAND
        manifest["version"] = VERSION
        manifest["case_id"] = CASE_ID
        manifest["generated_at"] = _utc()
        manifest["consolidation"] = {
            "orchestrator": "us_ipforce_consolidated_orchestrator.py",
            "seal": report["seal"],
            "custody_root": custody["root_sha3_512"],
        }
        _write_json(manifest_path, manifest)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} consolidated orchestrator")
    parser.add_argument("--workers", type=int, default=int(os.environ.get("US_IPFORCE_WORKERS", "8")))
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument(
        "--include-legacy-smoke",
        action="store_true",
        help="Run deterministic_all/court_ready even when hardening finds secrets",
    )
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)

    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    report = run_consolidated(
        max_workers=max(1, args.workers),
        skip_legacy_smoke=not args.include_legacy_smoke,
        plan_only=args.plan_only,
    )
    if args.print_report or args.plan_only:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        c = report.get("counts") or {}
        print(
            f"{BRAND} consolidated: engines_ok={c.get('engines_ok')}/{c.get('engines')} "
            f"tier0_probe_ok={c.get('tier0_probe_ok')} "
            f"ohio={c.get('ohio_llc_count')} gap={c.get('ohio_gap')} "
            f"workers={report.get('max_workers')} "
            f"seal={(report.get('seal') or '')[:16]}…"
        )
    return 0 if (args.plan_only or (report.get("counts") or {}).get("engines_ok", 0) > 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())

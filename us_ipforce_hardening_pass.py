#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IP FORCE — Phase-1 hardening pass (fail-closed credential / import scan).

Rejects community-* placeholders and chat-pasted secret defaults when
US_IPFORCE_VERIFIED_MODE=1. Does not modify scanned files; reports only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRAND = "IP FORCE"
VERSION = "2026.7.22-HARDENING-PASS"
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output_artifacts" / "hardening"
SUMMARY = OUT / "HARDENING_PASS_SUMMARY.json"

COMMUNITY_RE = re.compile(r"community-[A-Za-z0-9_\-]+", re.I)
# getenv("X", "literal-default") with non-empty default that looks like a key
GETENV_DEFAULT_RE = re.compile(
    r"""os\.getenv\(\s*["']([A-Z0-9_]+)["']\s*,\s*["']([^"']{8,})["']\s*\)"""
)
MONOLITH_IMPORT_RE = re.compile(
    r"from\s+(us_ipforce_monolith(?:_live)?|us_ip_force_monolith)\s+import"
)

SCAN_GLOBS = (
    "us_ipforce*.py",
    "court_ready_forensic_blueprint.py",
    "forensic_data_fabric.py",
    "corpus_completeness_hardening_maximize.py",
    "CORPUS_HARDENING_GATE.py",
    "scripts/*.py",
    "phoenix_shield/*.py",
)

# Orchestrator / secure entry may intentionally name rejected routes.
ALLOWLIST_PATHS = {
    "us_ipforce_hardening_pass.py",
    "us_ipforce_consolidated_orchestrator.py",
    "us_ipforce.py",
    "us_ipforce_entry.py",
}


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _sha3(obj: Any) -> str:
    return hashlib.sha3_256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for pattern in SCAN_GLOBS:
        files.extend(ROOT.glob(pattern))
    # de-dupe + skip venv/output
    out: list[Path] = []
    seen: set[Path] = set()
    for p in files:
        rp = p.resolve()
        if rp in seen or not rp.is_file():
            continue
        if any(part in {".venv", "output_artifacts", "ip_force_output"} for part in rp.parts):
            continue
        seen.add(rp)
        out.append(rp)
    return sorted(out)


def scan_file(path: Path) -> list[dict[str, Any]]:
    rel = str(path.relative_to(ROOT))
    if rel in ALLOWLIST_PATHS:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [{"path": rel, "kind": "read_error", "detail": str(exc)}]

    findings: list[dict[str, Any]] = []
    for i, line in enumerate(text.splitlines(), 1):
        if COMMUNITY_RE.search(line):
            findings.append(
                {
                    "path": rel,
                    "line": i,
                    "kind": "community_placeholder",
                    "detail": line.strip()[:200],
                }
            )
        for m in GETENV_DEFAULT_RE.finditer(line):
            key, default = m.group(1), m.group(2)
            # Ignore benign short flags / empty-ish
            if default.lower() in {"0", "1", "true", "false", "default-key"}:
                findings.append(
                    {
                        "path": rel,
                        "line": i,
                        "kind": "weak_hmac_default",
                        "detail": f"{key}=…",
                    }
                )
                continue
            if "community-" in default.lower() or len(default) >= 16:
                findings.append(
                    {
                        "path": rel,
                        "line": i,
                        "kind": "getenv_secret_default",
                        "detail": f"{key} has non-empty default ({len(default)} chars)",
                    }
                )
    return findings


def run_scan(*, verified_mode: bool) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    scanned = 0
    for path in _iter_scan_files():
        scanned += 1
        findings.extend(scan_file(path))

    by_kind: dict[str, int] = {}
    for f in findings:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1

    blocking = [
        f
        for f in findings
        if f["kind"] in {"community_placeholder", "getenv_secret_default"}
    ]
    ok = (not blocking) if verified_mode else True
    report = {
        "brand": BRAND,
        "version": VERSION,
        "generated_at": _utc(),
        "verified_mode": verified_mode,
        "files_scanned": scanned,
        "findings_total": len(findings),
        "blocking_total": len(blocking),
        "by_kind": by_kind,
        "findings": findings[:500],
        "policy": (
            "US_IPFORCE_VERIFIED_MODE=1 fail-closes on community-* and "
            "getenv secret defaults in scanned modules. Credentials from env only."
        ),
        "ok": ok,
    }
    report["seal"] = _sha3({k: v for k, v in report.items() if k != "seal"})
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{BRAND} hardening pass")
    parser.add_argument("--print-report", action="store_true")
    parser.add_argument(
        "--allow-findings",
        action="store_true",
        help="Exit 0 even with blocking findings (report still written)",
    )
    args = parser.parse_args(argv)

    verified = os.environ.get("US_IPFORCE_VERIFIED_MODE", "1").strip() not in {
        "0",
        "false",
        "False",
        "",
    }
    report = run_scan(verified_mode=verified)
    OUT.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.print_report:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"{BRAND} hardening: scanned={report['files_scanned']} "
            f"findings={report['findings_total']} blocking={report['blocking_total']} "
            f"ok={report['ok']} seal={report['seal'][:16]}…"
        )

    if report["ok"] or args.allow_findings or not verified:
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())

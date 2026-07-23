#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — Aegis Hyperion secure entry (shim)

REJECTS chat-pasted "ULTIMA-GENESIS" monoliths that embed credential defaults,
community-* placeholders, or auto-adjudicate theft/RICO/UBO/state-actor claims.

Canonical execution is the consolidated control plane / investigation waves.

Run:
  US_IPFORCE_VERIFIED_MODE=1 python3 aegis_hyperion.py
  US_IPFORCE_VERIFIED_MODE=1 python3 aegis_hyperion.py --investigate-wave10
"""

from __future__ import annotations

import argparse
import os
import sys


REJECTED_CAPABILITIES = (
    "Hardcoded API key / demo credential defaults in source",
    "Auto-generated press releases asserting Meta patent theft or $trillion damages",
    "Automatic RICO / True-UBO / state-actor adjudication",
    "Placeholder blockchain address probes (0x123...)",
    "Simulated analytical engines presented as completed forensics",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="IP FORCE Aegis Hyperion secure shim → consolidated control plane"
    )
    parser.add_argument(
        "--show-rejection",
        action="store_true",
        help="Print rejected genesis-paste capabilities and exit",
    )
    parser.add_argument("--investigate-wave10", action="store_true")
    parser.add_argument("--print-report", action="store_true")
    parser.add_argument("--workers", type=int, default=int(os.environ.get("US_IPFORCE_WORKERS", "8")))
    parser.add_argument("--plan-only", action="store_true")
    args, unknown = parser.parse_known_args(argv)

    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")

    if args.show_rejection:
        print("IP FORCE · Aegis Hyperion · REJECTED genesis-paste capabilities:")
        for item in REJECTED_CAPABILITIES:
            print(f"  - {item}")
        print("Use: US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py")
        return 0

    if args.investigate_wave10:
        from us_ipforce_investigation_wave10 import main as wave10_main

        return int(wave10_main(["--print-report"] if args.print_report else []))

    # Default: consolidated orchestrator
    from us_ipforce_consolidated_orchestrator import main as consolidated_main

    cons = ["--workers", str(args.workers)]
    if args.plan_only:
        cons.append("--plan-only")
    if args.print_report:
        cons.append("--print-report")
    # forward unknown flags carefully — only known consolidator flags
    return int(consolidated_main(cons + unknown))


if __name__ == "__main__":
    raise SystemExit(main())

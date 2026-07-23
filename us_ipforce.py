#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE – canonical consolidated entry point.

Default: secure consolidated orchestrator
  (integrate · optimize · streamline · scale)

Legacy paths (explicit opt-in only):
  --legacy-monolith  → us_ipforce_monolith.py
  --legacy-live      → us_ipforce_monolith_live.py

Run:
  US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py
  US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --workers 8
  US_IPFORCE_VERIFIED_MODE=1 python3 us_ipforce.py --plan-only
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IP FORCE canonical entry")
    parser.add_argument("--legacy-monolith", action="store_true")
    parser.add_argument("--legacy-live", action="store_true")
    parser.add_argument("--workers", type=int, default=int(os.environ.get("US_IPFORCE_WORKERS", "8")))
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--include-legacy-smoke", action="store_true")
    parser.add_argument("--print-report", action="store_true")
    parser.add_argument(
        "--investigate",
        action="store_true",
        help="Run systematic investigation tracks only",
    )
    parser.add_argument(
        "--investigate-wave2",
        action="store_true",
        help="Run investigation wave-2 deep public screens",
    )
    args, unknown = parser.parse_known_args(argv)

    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    os.environ.setdefault("US_IPFORCE_V8", "1")
    os.environ.setdefault("US_IP_FORCE_V8", "1")

    if args.legacy_monolith and args.legacy_live:
        print("Choose only one of --legacy-monolith / --legacy-live", file=sys.stderr)
        return 2

    if args.investigate and args.investigate_wave2:
        print("Run --investigate and --investigate-wave2 separately (or wave2 alone).", file=sys.stderr)
        return 2

    if args.investigate:
        from us_ipforce_investigation_runner import main as investigate_main

        return int(investigate_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave2:
        from us_ipforce_investigation_wave2 import main as wave2_main

        return int(wave2_main(["--print-report"] if args.print_report else []))

    if args.legacy_monolith:
        from us_ipforce_monolith import main as legacy_main

        asyncio.run(legacy_main())
        return 0

    if args.legacy_live:
        from us_ipforce_monolith_live import main as legacy_main

        asyncio.run(legacy_main())
        return 0

    from us_ipforce_consolidated_orchestrator import main as consolidated_main

    cons_argv = ["--workers", str(args.workers)]
    if args.plan_only:
        cons_argv.append("--plan-only")
    if args.include_legacy_smoke:
        cons_argv.append("--include-legacy-smoke")
    if args.print_report:
        cons_argv.append("--print-report")
    # forward unknown for future flags
    cons_argv.extend(unknown)
    return int(consolidated_main(cons_argv))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(1)

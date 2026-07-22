#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE — thin entry.

Default: consolidated orchestrator.
Opt-in live modular pipeline: --legacy-live
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IP FORCE entry")
    parser.add_argument("--legacy-live", action="store_true")
    parser.add_argument("--workers", type=int, default=int(os.environ.get("US_IPFORCE_WORKERS", "8")))
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--print-report", action="store_true")
    args = parser.parse_args(argv)

    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    os.environ.setdefault("US_IPFORCE_HARDENED", os.environ.get("US_IP_FORCE_HARDENED", "0"))
    os.environ.setdefault("US_IP_FORCE_HARDENED", os.environ.get("US_IPFORCE_HARDENED", "0"))

    if args.legacy_live:
        from us_ipforce_monolith_live import main as live_main

        asyncio.run(live_main())
        return 0

    from us_ipforce_consolidated_orchestrator import main as consolidated_main

    cons_argv = ["--workers", str(args.workers)]
    if args.plan_only:
        cons_argv.append("--plan-only")
    if args.print_report:
        cons_argv.append("--print-report")
    return int(consolidated_main(cons_argv))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(1)

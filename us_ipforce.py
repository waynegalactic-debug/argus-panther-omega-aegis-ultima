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
    parser.add_argument(
        "--investigate-wave3",
        action="store_true",
        help="Run investigation wave-3 patent quarantine + continuity rebuild",
    )
    parser.add_argument(
        "--investigate-wave4",
        action="store_true",
        help="Run investigation wave-4 authenticated inventor portfolio search",
    )
    parser.add_argument(
        "--investigate-wave5",
        action="store_true",
        help="Run investigation wave-5 Ahkeo/Ohio + SEC Form D + assignment worklist",
    )
    parser.add_argument(
        "--investigate-wave6",
        action="store_true",
        help="Run investigation wave-6 Mayfield address nexus + domain archives",
    )
    parser.add_argument(
        "--investigate-wave7",
        action="store_true",
        help="Run investigation wave-7 RDAP/DNS custody + UPV surface blockers",
    )
    parser.add_argument(
        "--investigate-wave8",
        action="store_true",
        help="Run investigation wave-8 Ahkeo Labs v. Plurimi litigation seal",
    )
    parser.add_argument(
        "--investigate-wave9",
        action="store_true",
        help="Run investigation wave-9 Delaware ICIS Ahkeo Labs authentication",
    )
    parser.add_argument(
        "--investigate-wave10",
        action="store_true",
        help="Run investigation wave-10 genesis-paste rejection + evidence pack",
    )
    parser.add_argument(
        "--investigate-wave11",
        action="store_true",
        help="Run investigation wave-11 counsel preservation package v2",
    )
    parser.add_argument(
        "--investigate-wave12",
        action="store_true",
        help="Run investigation wave-12 chain-of-custody ledger + DE cert paths",
    )
    parser.add_argument(
        "--investigate-wave13",
        action="store_true",
        help="Run investigation wave-13 Wayback custody + SEC surfaces",
    )
    parser.add_argument(
        "--investigate-wave14",
        action="store_true",
        help="Run investigation wave-14 Google Patents portfolio refresh",
    )
    parser.add_argument(
        "--investigate-wave15",
        action="store_true",
        help="Run investigation wave-15 UrgentRN / Urgent Response Network cluster",
    )
    parser.add_argument(
        "--investigate-wave16",
        action="store_true",
        help="Run investigation wave-16 UrgentRN geo/contact + PDF geography",
    )
    parser.add_argument(
        "--investigate-wave17",
        action="store_true",
        help="Run investigation wave-17 San Juan suite professional-presence screen",
    )
    parser.add_argument(
        "--investigate-wave18",
        action="store_true",
        help="Run investigation wave-18 ABG Delaware × Puerto Rico RA cross-ref",
    )
    parser.add_argument(
        "--investigate-wave20",
        action="store_true",
        help="Run investigation wave-20 Casters / Arviv / ABG acquisition screen",
    )
    parser.add_argument(
        "--investigate-wave21",
        action="store_true",
        help="Run investigation wave-21 fyllo.eth / NFT / cyber-dust / patent-royalty screen",
    )
    parser.add_argument(
        "--investigate-wave22",
        action="store_true",
        help="Run investigation wave-22 exhaustive Fyllo Web3 + ABG tip-ten control nexus",
    )
    parser.add_argument(
        "--investigate-wave23",
        action="store_true",
        help="Run investigation wave-23 ABG shells / nested subs / DAO–Fortune monetization screen",
    )
    parser.add_argument(
        "--investigate-wave24",
        action="store_true",
        help="Run investigation wave-24 participants / PMI / threat nexus / enablers",
    )
    parser.add_argument(
        "--investigate-wave25",
        action="store_true",
        help="Run investigation wave-25 universal victim-IP linkage matrix",
    )
    parser.add_argument(
        "--investigate-wave26",
        action="store_true",
        help="Run investigation wave-26 blockchain flows / dust / DAO combinations",
    )
    parser.add_argument(
        "--investigate-wave27",
        action="store_true",
        help=(
            "Run investigation wave-27 wrapped / fractionalized / wrapped-RaP / "
            "IP / royalty / patent-NFT token flows"
        ),
    )
    args, unknown = parser.parse_known_args(argv)

    os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")
    os.environ.setdefault("US_IPFORCE_V8", "1")
    os.environ.setdefault("US_IP_FORCE_V8", "1")

    if args.legacy_monolith and args.legacy_live:
        print("Choose only one of --legacy-monolith / --legacy-live", file=sys.stderr)
        return 2

    wave_flags = sum(
        bool(x)
        for x in (
            args.investigate,
            args.investigate_wave2,
            args.investigate_wave3,
            args.investigate_wave4,
            args.investigate_wave5,
            args.investigate_wave6,
            args.investigate_wave7,
            args.investigate_wave8,
            args.investigate_wave9,
            args.investigate_wave10,
            args.investigate_wave11,
            args.investigate_wave12,
            args.investigate_wave13,
            args.investigate_wave14,
            args.investigate_wave15,
            args.investigate_wave16,
            args.investigate_wave17,
            args.investigate_wave18,
            args.investigate_wave20,
            args.investigate_wave21,
            args.investigate_wave22,
            args.investigate_wave23,
            args.investigate_wave24,
            args.investigate_wave25,
            args.investigate_wave26,
            args.investigate_wave27,
        )
    )
    if wave_flags > 1:
        print(
            "Run only one of --investigate / --investigate-wave2 / "
            "--investigate-wave3 / --investigate-wave4 / --investigate-wave5 / "
            "--investigate-wave6 / --investigate-wave7 / --investigate-wave8 / "
            "--investigate-wave9 / --investigate-wave10 / --investigate-wave11 / "
            "--investigate-wave12 / --investigate-wave13 / --investigate-wave14 / "
            "--investigate-wave15 / --investigate-wave16 / --investigate-wave17 / "
            "--investigate-wave18 / --investigate-wave20 / --investigate-wave21 / "
            "--investigate-wave22 / --investigate-wave23 / --investigate-wave24 / "
            "--investigate-wave25 / --investigate-wave26 / --investigate-wave27.",
            file=sys.stderr,
        )
        return 2

    if args.investigate:
        from us_ipforce_investigation_runner import main as investigate_main

        return int(investigate_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave2:
        from us_ipforce_investigation_wave2 import main as wave2_main

        return int(wave2_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave3:
        from us_ipforce_investigation_wave3 import main as wave3_main

        return int(wave3_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave4:
        from us_ipforce_investigation_wave4 import main as wave4_main

        return int(wave4_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave5:
        from us_ipforce_investigation_wave5 import main as wave5_main

        return int(wave5_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave6:
        from us_ipforce_investigation_wave6 import main as wave6_main

        return int(wave6_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave7:
        from us_ipforce_investigation_wave7 import main as wave7_main

        return int(wave7_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave8:
        from us_ipforce_investigation_wave8 import main as wave8_main

        return int(wave8_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave9:
        from us_ipforce_investigation_wave9 import main as wave9_main

        return int(wave9_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave10:
        from us_ipforce_investigation_wave10 import main as wave10_main

        return int(wave10_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave11:
        from us_ipforce_investigation_wave11 import main as wave11_main

        return int(wave11_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave12:
        from us_ipforce_investigation_wave12 import main as wave12_main

        return int(wave12_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave13:
        from us_ipforce_investigation_wave13 import main as wave13_main

        return int(wave13_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave14:
        from us_ipforce_investigation_wave14 import main as wave14_main

        return int(wave14_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave15:
        from us_ipforce_investigation_wave15 import main as wave15_main

        return int(wave15_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave16:
        from us_ipforce_investigation_wave16 import main as wave16_main

        return int(wave16_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave17:
        from us_ipforce_investigation_wave17 import main as wave17_main

        return int(wave17_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave18:
        from us_ipforce_investigation_wave18 import main as wave18_main

        return int(wave18_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave20:
        from us_ipforce_investigation_wave20 import main as wave20_main

        return int(wave20_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave21:
        from us_ipforce_investigation_wave21 import main as wave21_main

        return int(wave21_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave22:
        from us_ipforce_investigation_wave22 import main as wave22_main

        return int(wave22_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave23:
        from us_ipforce_investigation_wave23 import main as wave23_main

        return int(wave23_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave24:
        from us_ipforce_investigation_wave24 import main as wave24_main

        return int(wave24_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave25:
        from us_ipforce_investigation_wave25 import main as wave25_main

        return int(wave25_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave26:
        from us_ipforce_investigation_wave26 import main as wave26_main

        return int(wave26_main(["--print-report"] if args.print_report else []))

    if args.investigate_wave27:
        from us_ipforce_investigation_wave27 import main as wave27_main

        return int(wave27_main(["--print-report"] if args.print_report else []))

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

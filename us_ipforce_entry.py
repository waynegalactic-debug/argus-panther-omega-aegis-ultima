#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE MONOLITHIC EXECUTION SYSTEM
Canonical thin entry → live pipeline (us_ipforce_monolith_live.py).

Run:
    python3 us_ipforce_entry.py
    python3 us_ipforce_monolith_live.py
"""
from us_ipforce_monolith_live import main
import asyncio
import os
import sys

os.environ.setdefault("US_IPFORCE_HARDENED", os.environ.get("US_IP_FORCE_HARDENED", "0"))
os.environ.setdefault("US_IP_FORCE_HARDENED", os.environ.get("US_IPFORCE_HARDENED", "0"))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)

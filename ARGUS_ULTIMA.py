#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legacy ARGUS-PANTHER entry — thin shim to canonical US IPFORCE.

Brand: US IPFORCE only.
Canonical engines:
  python3 us_ipforce.py
  python3 us_ipforce_monolith.py
  python3 us_ipforce_monolith_live.py
"""
from __future__ import annotations

import asyncio
import os
import sys

os.environ.setdefault("US_IPFORCE_V8", "1")
os.environ.setdefault("US_IP_FORCE_V8", "1")

from us_ipforce_monolith import main  # noqa: E402


if __name__ == "__main__":
    print("US IPFORCE — legacy ARGUS_ULTIMA shim")
    print(f"Forwarding to us_ipforce_monolith (args={sys.argv[1:]})")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)

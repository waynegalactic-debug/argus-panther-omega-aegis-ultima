#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP FORCE – MONOLITHIC EXECUTION SYSTEM
================================================================================
Canonical self-contained monolith: us_ipforce_monolith.py
Live modular pipeline: us_ipforce_monolith_live.py

Run:
    python3 us_ipforce_monolith_v8.py
    python3 us_ipforce_monolith.py
    python3 us_ipforce_monolith_live.py
    python3 us_ipforce.py

Outputs: us_ipforce_output/
"""
from us_ipforce_monolith import main
import asyncio
import os
import sys

os.environ.setdefault("US_IPFORCE_V8", "1")
os.environ.setdefault("US_IP_FORCE_V8", "1")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)

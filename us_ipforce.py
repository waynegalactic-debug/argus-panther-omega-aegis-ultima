#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
US IPFORCE – canonical entry point.

One cohesive forensic IP-enforcement system.
Self-contained monolith: us_ipforce_monolith.py
Live modular pipeline: us_ipforce_monolith_live.py

Run:
    python3 us_ipforce.py
    python3 us_ipforce_monolith.py
    python3 us_ipforce_monolith_live.py
    python3 us_ipforce_entry.py

Outputs: us_ipforce_output/ (also written as us_ip_force_output/ for compatibility)
Optional web UI: US_IPFORCE_SERVE=1 python3 us_ipforce.py
"""
from us_ipforce_monolith import main
import asyncio
import os
import sys

os.environ.setdefault("US_IPFORCE_V8", "1")
os.environ.setdefault("US_IP_FORCE_V8", "1")  # legacy env alias

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)

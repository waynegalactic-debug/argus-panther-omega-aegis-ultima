#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""US IPFORCE – hardened entry (US_IPFORCE_HARDENED=1)."""
import os
import asyncio
import sys

os.environ["US_IPFORCE_HARDENED"] = "1"
os.environ["US_IP_FORCE_HARDENED"] = "1"

from us_ipforce_monolith_live import main  # noqa: E402

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)

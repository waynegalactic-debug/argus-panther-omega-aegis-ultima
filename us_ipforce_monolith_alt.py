#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""US IPFORCE – alternate entry (same engine as us_ipforce_entry.py)."""
from us_ipforce_monolith_live import main
import asyncio
import sys

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)

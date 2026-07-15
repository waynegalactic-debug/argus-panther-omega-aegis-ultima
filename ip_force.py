#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IP FORCE – canonical entry point."""
from __future__ import annotations

import asyncio
import os
import sys

os.environ.setdefault("IP_FORCE_V8", "1")
os.environ.setdefault("US_IPFORCE_V8", "1")  # legacy env alias
os.environ.setdefault("US_IP_FORCE_V8", "1")

from us_ipforce_monolith import main  # noqa: E402

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legacy shim — use us_ipforce_monolith_alt.py."""
from us_ipforce_monolith_alt import *  # noqa: F401,F403

if __name__ == "__main__":
    import asyncio
    import sys
    from us_ipforce_monolith_live import main
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)

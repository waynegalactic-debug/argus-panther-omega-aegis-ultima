#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legacy shim — canonical entry is us_ipforce.py."""
from us_ipforce import *  # noqa: F401,F403

if __name__ == "__main__":
    import asyncio
    import sys
    from us_ipforce_monolith import main
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)

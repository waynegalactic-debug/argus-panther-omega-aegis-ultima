#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legacy shim — canonical module is us_ipforce_monolith."""
from us_ipforce_monolith import *  # noqa: F401,F403
from us_ipforce_monolith import main  # noqa: F401

if __name__ == "__main__":
    import asyncio
    import sys
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)

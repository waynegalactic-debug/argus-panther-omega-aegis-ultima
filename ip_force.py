#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IP FORCE – brand alias → consolidated canonical entry."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("IP_FORCE_V8", "1")
os.environ.setdefault("US_IPFORCE_V8", "1")
os.environ.setdefault("US_IP_FORCE_V8", "1")
os.environ.setdefault("US_IPFORCE_VERIFIED_MODE", "1")

from us_ipforce import main  # noqa: E402

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(1)

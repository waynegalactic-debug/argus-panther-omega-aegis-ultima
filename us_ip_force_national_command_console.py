#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legacy import path shim → us_ipforce_national_command_console."""

from us_ipforce_national_command_console import *  # noqa: F403
from us_ipforce_national_command_console import (  # noqa: F401
    Integration,
    main,
    render_national_command_console,
    write_console,
)

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Pure HTTP control API for BX; cron, snapshot worker and in-process host stay disabled."""
from __future__ import annotations

import sys

import a0v_bw_product_controlled_api as controlled


load_launcher = controlled.load_launcher


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    load_launcher().main()

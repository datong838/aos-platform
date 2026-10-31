#!/usr/bin/env python3
"""Protected S2 stdin request, or explicit --serve loopback gateway."""
from pathlib import Path
import sys

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/aos-api'))
    if sys.argv[1:2] == ['--serve']:
        from aos_api.aip_budget_policy_window_gateway import serve_main
        raise SystemExit(serve_main(sys.argv[2:]))
    from aos_api.aip_budget_policy_window_gateway import main
    raise SystemExit(main())

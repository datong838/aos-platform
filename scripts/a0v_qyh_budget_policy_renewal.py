#!/usr/bin/env python3
"""Protected loopback renewal review gateway; never provisions business roles."""
import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'services/aos-api'))
    try:
        from aos_api.aip_budget_policy_renewal_gateway import create_renewal_gateway
        app = create_renewal_gateway(args.config)
    except Exception:
        print('RENEWAL_GATEWAY_STARTUP_BLOCKED', file=sys.stderr, flush=True)
        return 2
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=18462, workers=1, access_log=False,
                log_config=None, log_level='critical', proxy_headers=False, server_header=False)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Explicit check or finite serve for a private issuer; readiness is not approval."""
import json
import sys

# Reuse the existing no-echo and no-duplicate parser; never copy a safety gate.
from aos_api.aip_network_consumer_cli import _Parser, _Once


def main(argv=None) -> int:
    parser = _Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--mode', choices=('check', 'serve'), required=True, action=_Once)
    for option in ('--config', '--preflight-org', '--preflight-project'):
        parser.add_argument(option, required=True, action=_Once)
    try:
        args = parser.parse_args(argv)
    except ValueError:
        print('ISSUER_ENTRY_ARGUMENTS_INVALID', file=sys.stderr)
        return 2
    try:
        from aos_api.tenant_scope import TenantScope
        from aos_api.aip_network_issuer_config import load_issuer_config, preflight_issuer
        from aos_api.aip_network_issuer_process import run_issuer_process

        scope = TenantScope(args.preflight_org, args.preflight_project)
        config = load_issuer_config(args.config)
        readiness = preflight_issuer(config, scope)
        if args.mode == 'check':
            result = {'mode': 'check', **readiness}
        else:
            result = {'mode': 'serve', **run_issuer_process(config), 'businessAuthorized': False}
    except Exception:
        print('ISSUER_ENTRY_BLOCKED', file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

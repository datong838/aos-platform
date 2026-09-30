"""Explicit, finite consumer entry; readiness never grants business authority."""
import argparse
import json
import sys


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes arbitrary argument values, possibly credentials.
        raise ValueError('CONSUMER_ENTRY_ARGUMENTS_INVALID')


class _Once(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        seen = getattr(namespace, '_seen', set())
        if self.dest in seen:
            parser.error('duplicate option')
        seen.add(self.dest)
        namespace._seen = seen
        setattr(namespace, self.dest, values)


def main(argv=None) -> int:
    parser = _Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--mode', choices=('check', 'serve'), required=True, action=_Once)
    for option in ('--config', '--preflight-org', '--preflight-project'):
        parser.add_argument(option, required=True, action=_Once)
    try:
        args = parser.parse_args(argv)
    except ValueError:
        print('CONSUMER_ENTRY_ARGUMENTS_INVALID', file=sys.stderr)
        return 2
    try:
        from aos_api.tenant_scope import TenantScope
        from aos_api.aip_network_consumer_config import load_consumer_config, preflight_consumer
        from aos_api.aip_network_consumer_process import run_consumer_process

        scope = TenantScope(args.preflight_org, args.preflight_project)
        config = load_consumer_config(args.config)
        readiness = preflight_consumer(config, scope)
        if args.mode == 'check':
            result = {'mode': 'check', **readiness}
        else:
            result = {'mode': 'serve', **run_consumer_process(config), 'businessAuthorized': False}
    except Exception:
        print('CONSUMER_ENTRY_BLOCKED', file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

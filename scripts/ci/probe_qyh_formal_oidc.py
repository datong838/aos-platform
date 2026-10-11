#!/usr/bin/env python3
"""Read-only Qiyuehui external OIDC acceptance; never provisions membership."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import urllib.error
import urllib.parse
import urllib.request


class ProbeError(ValueError):
    """Sanitized error safe for public evidence."""


def _url(value):
    try:
        u = urllib.parse.urlsplit(value)
        _ = u.port
        if not u.hostname or u.username or u.password or u.query or u.fragment:
            raise ValueError
        return u
    except (ValueError, TypeError):
        raise ProbeError('invalid endpoint URL') from None


def api_base(value):
    u = _url(value)
    if u.path not in ('', '/'):
        raise ProbeError('API base must not contain a path')
    if u.scheme == 'http' and u.hostname not in ('127.0.0.1', '::1', 'localhost'):
        raise ProbeError('HTTP is allowed only for loopback API')
    if u.scheme not in ('http', 'https'):
        raise ProbeError('unsupported API scheme')
    return value.rstrip('/')


def external_https(value):
    u = _url(value)
    if u.scheme != 'https' or u.hostname.lower() in ('localhost', 'aos-dev-oidc') or u.hostname.lower().endswith('.localhost'):
        raise ProbeError('external HTTPS identity endpoint required')
    try:
        address = ipaddress.ip_address(u.hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ProbeError('external identity endpoint required')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get_json(url, headers=None):
    # No ambient proxy credentials or redirect-based credential forwarding.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url, headers=headers or {}, method='GET')
    try:
        with opener.open(request, timeout=10) as response:
            data = response.read(65537)
            if len(data) > 65536:
                raise ProbeError('identity response too large')
        value = json.loads(data)
    except ProbeError:
        raise
    except Exception:
        raise ProbeError('identity HTTP or JSON check failed') from None
    if not isinstance(value, dict):
        raise ProbeError('identity response must be an object')
    return value


def read_token(path):
    path = Path(path)
    repo = Path(__file__).resolve().parents[2]
    if path.resolve().is_relative_to(repo):
        raise ProbeError('credential must be outside the repository')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o600 or not 0 < before.st_size <= 65536:
                raise ProbeError('credential file must be owned regular mode 600')
            data = os.read(fd, 65537)
            after = os.fstat(fd)
            if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                raise ProbeError('credential changed during read')
        finally:
            os.close(fd)
        value = data.decode('ascii').strip()
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', value):
            raise ProbeError('credential must contain a single JWT')
        return value
    except ProbeError:
        raise
    except Exception:
        raise ProbeError('credential file unavailable') from None


def run(base='http://127.0.0.1:18080', token_file=None, expected_issuer=None, expected_audience=None, *, inspect_only=False):
    base = api_base(base)
    config = get_json(base + '/v1/auth/oidc')
    grants = config.get('grantTypes')
    urls = config.get('jwksUrls')
    if config.get('allowDevToken') is not False or config.get('jwksConfigured') is not True or not isinstance(grants, list) or any(not isinstance(g, str) or g.lower() == 'dev' for g in grants):
        raise ProbeError('formal external OIDC configuration required')
    if not isinstance(urls, list) or not urls:
        raise ProbeError('external JWKS configuration required')
    for url in urls:
        external_https(url)
    external_https(config.get('issuer'))
    result = dict(publicConfigurationPassed=True, serverAuthenticatedPrincipalScopeMatched=False,
                  publisherIdentityVerified=False, runtimeAuthorized=False)
    if inspect_only:
        return result
    if not expected_issuer or not expected_audience or config.get('issuer') != expected_issuer or config.get('audience') != expected_audience:
        raise ProbeError('expected issuer and audience must match')
    if token_file is None:
        raise ProbeError('existing protected token file required')
    token = read_token(token_file)
    principal = get_json(base + '/v1/auth/principal', {
        'Authorization': 'Bearer ' + token, 'X-Org-Id': 'org-org', 'X-Project-Id': 'dev-project'})
    del token
    if principal.get('orgId') != 'org-org' or principal.get('projectId') != 'dev-project' or principal.get('tokenKind') != 'oidc' or principal.get('externalOnly') is not True or principal.get('authenticated') is not True:
        raise ProbeError('verified Qiyuehui external identity scope required')
    result['serverAuthenticatedPrincipalScopeMatched'] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-base', default='http://127.0.0.1:18080')
    parser.add_argument('--inspect-only', action='store_true')
    parser.add_argument('--token-file', type=Path)
    parser.add_argument('--expected-issuer')
    parser.add_argument('--expected-audience')
    args = parser.parse_args()
    try:
        result = run(args.api_base, args.token_file, args.expected_issuer, args.expected_audience, inspect_only=args.inspect_only)
    except ProbeError as exc:
        print(json.dumps(dict(status='REFUSED', reason=str(exc)), ensure_ascii=False))
        return 1
    print(json.dumps(dict(status='INSPECTED' if args.inspect_only else 'VERIFIED_SCOPE', **result)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Opt-in native Keycloak and macOS Keychain acceptance for Route worker identity."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

from aos_api.aip_route_worker_identity import (
    HttpWorkerTokenTransport,
    RouteWorkerIdentityBlocked,
    RouteWorkerIdentityConfig,
    RouteWorkerIdentityProvider,
)
from aos_api.aip_secret_backend import MacOSKeychainClient
from aos_api.tenant_scope import TenantScope


pytestmark = pytest.mark.skipif(
    os.getenv("AOS_ROUTE_WORKER_IDENTITY_NATIVE") != "1",
    reason="explicit disposable Keycloak/Keychain window required",
)


class CountingTransport:
    def __init__(self) -> None:
        self.calls = 0
        self._transport = HttpWorkerTokenTransport()

    def exchange(self, endpoint, form):
        self.calls += 1
        return self._transport.exchange(endpoint, form)


def test_native_keycloak_client_credentials_from_temporary_keychain():
    keychain = Path(os.environ.get("AOS_ROUTE_WORKER_TEST_KEYCHAIN", ""))
    if (not keychain.is_absolute() or not keychain.is_file()
        or keychain.is_symlink() or keychain.stat().st_mode & 0o077):
        pytest.fail("exact private temporary Keychain required")

    keychain_calls = []
    def keychain_runner(argv, **kwargs):
        if (type(argv) is not list
            or argv[:2] != ["/usr/bin/security", "find-generic-password"]
            or str(keychain) in argv):
            raise OSError("unexpected Keychain command")
        keychain_calls.append("read" if "-w" in argv else "exists")
        return subprocess.run([*argv, str(keychain)], **kwargs)

    transport = CountingTransport()
    provider = RouteWorkerIdentityProvider(
        config=RouteWorkerIdentityConfig.from_env(),
        secret_client=MacOSKeychainClient(runner=keychain_runner),
        transport=transport,
    )
    provider.assert_configured(TenantScope("org-org", "dev-project"))
    assert transport.calls == 0
    context = provider.acquire(TenantScope("org-org", "dev-project"))
    token = context.bearer_token.get_secret_value()
    assert context.principal.subject == "aos-route-worker-native-subject"
    assert context.principal.roles.count("aos_route_worker") == 1
    assert (context.principal.org_id, context.principal.project_id) == (
        "org-org", "dev-project")
    assert transport.calls == 1
    assert keychain_calls == ["exists", "read"]
    assert token not in repr(context) and token not in repr(provider)

    with pytest.raises(RouteWorkerIdentityBlocked,
            match="ROUTE_WORKER_CURRENT_IDENTITY_REQUIRED"):
        provider.acquire(TenantScope("dev-org", "dev-project"))
    assert transport.calls == 1

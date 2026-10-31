"""Opt-in install/uninstall/reinstall proof using one private temporary Keychain."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from aos_api.aip_route_worker_identity import (
    RouteWorkerIdentityBlocked,
    RouteWorkerIdentityConfig,
)
from aos_api.aip_route_worker_installation import (
    RouteWorkerIdentityInstallation,
    RouteWorkerIdentityInstallationStore,
    RouteWorkerSignedRelease,
    release_set_hash,
)
from aos_api.aip_route_worker_installation_authority import (
    RouteWorkerSignedInstallationCoordinator,
)
from aos_api.aip_secret_backend import MacOSKeychainClient

pytestmark = pytest.mark.skipif(
    os.getenv("AOS_ROUTE_WORKER_INSTALLATION_NATIVE") != "1",
    reason="explicit private temporary Keychain window required",
)


def test_native_atomic_install_uninstall_and_reinstall(monkeypatch):
    keychain = Path(os.environ.get("AOS_ROUTE_WORKER_TEST_KEYCHAIN", ""))
    target_dir = Path(os.environ.get("AOS_ROUTE_WORKER_INSTALLATION_NATIVE_DIR", ""))
    if (
        not keychain.is_absolute()
        or not keychain.is_file()
        or keychain.is_symlink()
        or keychain.stat().st_mode & 0o077
        or not target_dir.is_absolute()
        or not target_dir.is_dir()
        or target_dir.is_symlink()
        or target_dir.stat().st_mode & 0o077
    ):
        pytest.fail("exact private temporary installation environment required")

    calls = []

    def keychain_runner(argv, **kwargs):
        if (
            type(argv) is not list
            or argv[:2] != ["/usr/bin/security", "find-generic-password"]
            or "-w" in argv
            or str(keychain) in argv
        ):
            raise OSError("unexpected Keychain command")
        calls.append(tuple(argv))
        return subprocess.run([*argv, str(keychain)], **kwargs)

    issuer = "http://127.0.0.1:18449/realms/qyh-route-worker-native"
    releases = (
        RouteWorkerSignedRelease(
            publisher="aos.local",
            bundleId="ecommerce-growth",
            version="1.13.0",
            contentHash="sha256:" + "b" * 64,
            signatureFingerprint="sha256:" + "c" * 64,
            releaseEvidenceRevision="release-7",
        ),
    )
    document = RouteWorkerIdentityInstallation(
        schemaVersion="aos.route-worker-identity-installation/v1",
        orgId="org-org",
        projectId="dev-project",
        issuer=issuer,
        audience="aos-api",
        tokenEndpoint=issuer + "/protocol/openid-connect/token",
        clientId="aos-route-worker",
        expectedSubject="aos-route-worker-native-subject",
        secretVersion="v1",
        installationId="00000000-0000-0000-0000-000000000107",
        installationRevision=7,
        installationEtag=7,
        lockHash="sha256:" + "a" * 64,
        releases=releases,
        releaseSetHash=release_set_hash(releases),
    )
    client = MacOSKeychainClient(runner=keychain_runner)
    store = RouteWorkerIdentityInstallationStore(secret_client=client)

    class Authority:
        def __init__(self):
            self.calls = []

        def assert_current(self, value):
            self.calls.append(value)
            return True

    authority = Authority()
    coordinator = RouteWorkerSignedInstallationCoordinator(
        store=store, authority=authority
    )
    path = target_dir / "route-worker-identity.json"

    content_hash = coordinator.install(path, document)
    for name, value in {
        "AOS_AUTH_EXTERNAL_ONLY": "1",
        "AOS_AUTH_ALLOW_DEV": "0",
        "AOS_OIDC_ISSUER": document.issuer,
        "AOS_OIDC_AUDIENCE": document.audience,
        "AOS_OIDC_TOKEN_URL": document.tokenEndpoint,
        "AOS_ROUTE_WORKER_IDENTITY_FILE": str(path),
    }.items():
        monkeypatch.setenv(name, value)
    assert RouteWorkerIdentityConfig.from_env().secret_version == "v1"

    coordinator.uninstall(path, expected_current_hash=content_hash)
    with pytest.raises(RouteWorkerIdentityBlocked):
        RouteWorkerIdentityConfig.from_env()
    assert client.exists(document.locator()) is True

    assert coordinator.install(path, document) == content_hash
    assert store.load(path) == document
    assert len(calls) == 3
    assert authority.calls == [document] * 5

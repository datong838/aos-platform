from __future__ import annotations

import pytest

from aos_api.aip_route_worker_installation import (
    RouteWorkerIdentityInstallation,
    RouteWorkerIdentityInstallationStore,
    RouteWorkerInstallationBlocked,
    RouteWorkerSignedRelease,
    release_set_hash,
)


class Secrets:
    def __init__(self, *, exists: bool = True) -> None:
        self.available = exists
        self.probes = []

    def exists(self, locator) -> bool:
        self.probes.append(locator)
        return self.available

    def read(self, locator):
        raise AssertionError("installation must not read secret payload")


def document(**updates) -> RouteWorkerIdentityInstallation:
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
    value = {
        "schemaVersion": "aos.route-worker-identity-installation/v1",
        "orgId": "org-org",
        "projectId": "dev-project",
        "issuer": "http://127.0.0.1:18448/realms/qyh-local",
        "audience": "aos-api",
        "tokenEndpoint": (
            "http://127.0.0.1:18448/realms/qyh-local/protocol/openid-connect/token"
        ),
        "clientId": "aos-route-worker",
        "expectedSubject": "service-account-aos-route-worker",
        "secretVersion": "v1",
        "installationId": "00000000-0000-0000-0000-000000000107",
        "installationRevision": 7,
        "installationEtag": 7,
        "lockHash": "sha256:" + "a" * 64,
        "releases": releases,
        "releaseSetHash": release_set_hash(releases),
    }
    value.update(updates)
    return RouteWorkerIdentityInstallation.model_validate(value)


def test_install_publishes_one_canonical_owner_only_document(tmp_path):
    secrets = Secrets()
    store = RouteWorkerIdentityInstallationStore(secret_client=secrets)
    path = tmp_path / "route-worker.json"

    content_hash = store.install(path, document())

    assert content_hash == document().content_hash()
    assert store.load(path) == document()
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert path.read_bytes() == document().canonical_bytes()
    assert len(secrets.probes) == 1
    assert secrets.probes[0].account.endswith("client-secret/v1")


def test_missing_exact_secret_version_never_publishes_or_overwrites(tmp_path):
    path = tmp_path / "route-worker.json"
    present = RouteWorkerIdentityInstallationStore(secret_client=Secrets())
    original_hash = present.install(path, document())

    missing = RouteWorkerIdentityInstallationStore(secret_client=Secrets(exists=False))
    with pytest.raises(RouteWorkerInstallationBlocked, match="INSTALLATION_REJECTED"):
        missing.install(
            path,
            document(secretVersion="v2"),
            expected_current_hash=original_hash,
        )

    assert present.load(path) == document()


@pytest.mark.parametrize(
    "updates",
    [
        {"orgId": "dev-org"},
        {"tokenEndpoint": "https://attacker.example/token"},
        {"secretVersion": "v1/other"},
    ],
)
def test_noncurrent_or_ambiguous_installation_is_rejected(updates):
    with pytest.raises(ValueError):
        document(**updates)


def test_secret_or_unknown_fields_are_forbidden():
    payload = document().wire()
    payload["clientSecret"] = "must-never-be-stored"
    with pytest.raises(ValueError):
        RouteWorkerIdentityInstallation.model_validate(payload)


@pytest.mark.parametrize(
    "updates",
    [
        {"installationRevision": 6},
        {"lockHash": "sha256:" + "0" * 64},
        {"releases": ()},
        {"releaseSetHash": "sha256:" + "d" * 64},
    ],
)
def test_signed_installation_reference_must_be_complete_and_exact(updates):
    with pytest.raises(ValueError):
        document(**updates)


def test_update_requires_exact_current_hash_and_rolls_back_post_publish_failure(
    tmp_path, monkeypatch
):
    secrets = Secrets()
    store = RouteWorkerIdentityInstallationStore(secret_client=secrets)
    path = tmp_path / "route-worker.json"
    original = document()
    original_hash = store.install(path, original)
    updated = document(secretVersion="v2")

    with pytest.raises(RouteWorkerInstallationBlocked, match="INSTALLATION_REJECTED"):
        store.install(path, updated, expected_current_hash="sha256:" + "0" * 64)
    assert store.load(path) == original

    original_load = store.load
    calls = 0

    def fail_second_read(value):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RouteWorkerInstallationBlocked("injected_readback_failure")
        return original_load(value)

    monkeypatch.setattr(store, "load", fail_second_read)
    with pytest.raises(
        RouteWorkerInstallationBlocked, match="injected_readback_failure"
    ):
        store.install(path, updated, expected_current_hash=original_hash)

    assert RouteWorkerIdentityInstallationStore.load(path) == original


def test_post_publish_authority_failure_rolls_back_first_and_updated_install(tmp_path):
    store = RouteWorkerIdentityInstallationStore(secret_client=Secrets())
    path = tmp_path / "route-worker.json"

    with pytest.raises(RouteWorkerInstallationBlocked, match="INSTALLATION_REJECTED"):
        store.install(path, document(), post_publish_check=lambda _: False)
    assert not path.exists()

    original_hash = store.install(path, document())
    with pytest.raises(RouteWorkerInstallationBlocked, match="INSTALLATION_REJECTED"):
        store.install(
            path,
            document(secretVersion="v2"),
            expected_current_hash=original_hash,
            post_publish_check=lambda _: False,
        )
    assert store.load(path) == document()


def test_uninstall_denies_runtime_then_same_manifest_can_be_reinstalled(tmp_path):
    secrets = Secrets()
    store = RouteWorkerIdentityInstallationStore(secret_client=secrets)
    path = tmp_path / "route-worker.json"
    content_hash = store.install(path, document())

    removed = store.uninstall(path, expected_current_hash=content_hash)

    assert removed == document()
    assert not path.exists()
    with pytest.raises(RouteWorkerInstallationBlocked, match="UNAVAILABLE"):
        store.load(path)

    assert store.install(path, removed) == content_hash
    assert store.load(path) == document()
    assert len(secrets.probes) == 2


def test_uninstall_wrong_hash_preserves_configuration(tmp_path):
    store = RouteWorkerIdentityInstallationStore(secret_client=Secrets())
    path = tmp_path / "route-worker.json"
    store.install(path, document())

    with pytest.raises(RouteWorkerInstallationBlocked, match="UNINSTALL_REJECTED"):
        store.uninstall(path, expected_current_hash="sha256:" + "0" * 64)

    assert store.load(path) == document()


def test_runtime_rejects_relative_symlink_and_unsafe_permissions(tmp_path):
    store = RouteWorkerIdentityInstallationStore(secret_client=Secrets())
    path = tmp_path / "route-worker.json"
    store.install(path, document())

    with pytest.raises(RouteWorkerInstallationBlocked, match="PATH_INVALID"):
        store.load("relative.json")

    path.chmod(0o644)
    with pytest.raises(RouteWorkerInstallationBlocked, match="UNAVAILABLE"):
        store.load(path)
    path.chmod(0o600)

    link = tmp_path / "route-worker-link.json"
    link.symlink_to(path)
    with pytest.raises(RouteWorkerInstallationBlocked, match="UNAVAILABLE"):
        store.load(link)


def test_install_requires_absolute_existing_parent(tmp_path):
    store = RouteWorkerIdentityInstallationStore(secret_client=Secrets())
    with pytest.raises(RouteWorkerInstallationBlocked, match="PATH_INVALID"):
        store.install("relative.json", document())
    with pytest.raises(RouteWorkerInstallationBlocked, match="PATH_INVALID"):
        store.install(tmp_path / "missing" / "route-worker.json", document())

    unsafe = tmp_path / "unsafe"
    unsafe.mkdir(mode=0o777)
    unsafe.chmod(0o777)
    with pytest.raises(RouteWorkerInstallationBlocked, match="PATH_INVALID"):
        store.install(unsafe / "route-worker.json", document())

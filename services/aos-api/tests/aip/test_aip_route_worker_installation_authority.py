from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.aip_route_worker_installation import (
    RouteWorkerIdentityInstallationStore,
    RouteWorkerInstallationBlocked,
)
from aos_api.aip_route_worker_installation_authority import (
    CurrentRouteWorkerInstallationAuthority,
    RouteWorkerSignedInstallationCoordinator,
)
from aos_api.extension_runtime.current_installation_release_evidence import (
    CurrentInstallationReleaseEvidence,
    SelectedReleaseEvidence,
)
from tests.aip.test_aip_route_worker_installation import Secrets, document


def evidence(**updates) -> CurrentInstallationReleaseEvidence:
    value = {
        "scope": ("org-org", "dev-project"),
        "installation_id": "00000000-0000-0000-0000-000000000107",
        "current_revision": 7,
        "active_revision": 7,
        "etag_version": 7,
        "lock_hash": "sha256:" + "a" * 64,
        "releases": (
            SelectedReleaseEvidence(
                publisher="aos.local",
                bundle_id="ecommerce-growth",
                version="1.13.0",
                content_hash="sha256:" + "b" * 64,
                signature_fingerprint="sha256:" + "c" * 64,
                release_evidence_revision="release-7",
            ),
        ),
        "runtime_members": (),
        "checked_at": datetime.now(UTC),
    }
    value.update(updates)
    return CurrentInstallationReleaseEvidence(**value)


class Reader:
    def __init__(self, *views):
        self.views = list(views)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.views.pop(0)


def test_exact_current_active_signed_installation_is_accepted():
    reader = Reader(evidence())
    authority = CurrentRouteWorkerInstallationAuthority(reader=reader)

    assert authority.assert_current(document()) is True
    assert reader.calls == [
        {
            "scope": reader.calls[0]["scope"],
            "installation_id": document().installationId,
        }
    ]
    assert reader.calls[0]["scope"].key == ("org-org", "dev-project")


@pytest.mark.parametrize(
    "view",
    [
        evidence(active_revision=None),
        evidence(etag_version=8),
        evidence(lock_hash="sha256:" + "d" * 64),
        evidence(releases=()),
        evidence(
            releases=(
                SelectedReleaseEvidence(
                    publisher="aos.local",
                    bundle_id="ecommerce-growth",
                    version="1.13.0",
                    content_hash="sha256:" + "d" * 64,
                    signature_fingerprint="sha256:" + "c" * 64,
                    release_evidence_revision="release-7",
                ),
            )
        ),
    ],
)
def test_any_current_installation_drift_is_rejected(view):
    authority = CurrentRouteWorkerInstallationAuthority(reader=Reader(view))
    with pytest.raises(
        RouteWorkerInstallationBlocked,
        match="ROUTE_WORKER_SIGNED_INSTALLATION_REQUIRED",
    ):
        authority.assert_current(document())


def test_coordinator_rolls_back_when_authority_drifts_after_publish(tmp_path):
    reader = Reader(evidence(), evidence(etag_version=8))
    authority = CurrentRouteWorkerInstallationAuthority(reader=reader)
    store = RouteWorkerIdentityInstallationStore(secret_client=Secrets())
    coordinator = RouteWorkerSignedInstallationCoordinator(
        store=store, authority=authority
    )
    path = tmp_path / "route-worker.json"

    with pytest.raises(RouteWorkerInstallationBlocked):
        coordinator.install(path, document())
    assert not path.exists()


def test_uninstall_preserves_file_when_current_authority_has_drifted(tmp_path):
    store = RouteWorkerIdentityInstallationStore(secret_client=Secrets())
    path = tmp_path / "route-worker.json"
    content_hash = store.install(path, document())
    coordinator = RouteWorkerSignedInstallationCoordinator(
        store=store,
        authority=CurrentRouteWorkerInstallationAuthority(
            reader=Reader(evidence(active_revision=None))
        ),
    )

    with pytest.raises(RouteWorkerInstallationBlocked):
        coordinator.uninstall(path, expected_current_hash=content_hash)
    assert store.load(path) == document()

"""Transition-time selected release revalidation tests."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from aos_api.asset_registry.errors import RegistrySnapshotStaleError, RuntimeOperationRequiredError
from aos_api.asset_registry.installation_revalidation import InstallationRevalidator


def test_missing_selected_release_is_stale_after_transaction_lock() -> None:
    lock = MagicMock()
    lock.payload.resolved = [
        MagicMock(publisher="aos", id="solution.example", version="1.0.0")
    ]
    policy = MagicMock()
    policy.snapshot.return_value = policy
    clock = MagicMock()
    clock.fetchone.return_value = {"checked_at": datetime(2026, 8, 3, tzinfo=UTC)}
    rows = MagicMock()
    rows.fetchall.return_value = []
    conn = MagicMock()
    conn.execute.side_effect = [MagicMock(), clock, rows]

    with (
        patch(
            "aos_api.asset_registry.installation_revalidation.StoredCompositionLock.model_validate",
            return_value=lock,
        ),
        pytest.raises(RegistrySnapshotStaleError),
    ):
        InstallationRevalidator(release_policy=policy).revalidate_in_transaction(
            conn, lock=lock
        )

    assert conn.execute.call_args_list[0].args == (
        "SELECT pg_advisory_xact_lock(228, 1)",
    )
    policy.snapshot.assert_called_once_with()


def test_runtime_release_cannot_pass_legacy_installation_revalidation():
    lock = MagicMock()
    lock.payload.resolved = [MagicMock(publisher="aos", id="example", version="1.0.0")]
    policy = MagicMock()
    policy.snapshot.return_value = policy
    conn = MagicMock()
    clock = MagicMock()
    clock.fetchone.return_value = {"checked_at": datetime(2026, 9, 5, tzinfo=UTC)}
    rows = MagicMock()
    rows.fetchall.return_value = [{"publisher": "aos", "bundle_id": "example", "version": "1.0.0"}]
    conn.execute.side_effect = [MagicMock(), clock, rows]
    record = MagicMock()
    record.manifest.spec.runtime = object()
    with (
        patch("aos_api.asset_registry.installation_revalidation.StoredCompositionLock.model_validate", return_value=lock),
        patch("aos_api.asset_registry.installation_revalidation._record_from_row", return_value=record),
        pytest.raises(RuntimeOperationRequiredError, match="isolated installation lifecycle"),
    ):
        InstallationRevalidator(release_policy=policy).revalidate_in_transaction(conn, lock=lock)
    policy.evaluate.assert_not_called()


def test_pure_content_release_keeps_legacy_revalidation_path():
    selected = MagicMock(publisher="aos", id="content", version="1.0.0", content_hash="sha256:" + "a" * 64)
    lock = MagicMock()
    lock.payload.resolved = [selected]
    policy = MagicMock()
    policy.snapshot.return_value = policy
    checked_at = datetime(2026, 9, 5, tzinfo=UTC)
    conn = MagicMock()
    conn.execute.side_effect = [MagicMock(), MagicMock(fetchone=lambda: {"checked_at": checked_at}),
                                MagicMock(fetchall=lambda: [{"publisher": "aos", "bundle_id": "content", "version": "1.0.0"}])]
    record = MagicMock()
    record.manifest.spec.runtime = None
    record.content_hash = selected.content_hash
    with (
        patch("aos_api.asset_registry.installation_revalidation.StoredCompositionLock.model_validate", return_value=lock),
        patch("aos_api.asset_registry.installation_revalidation._record_from_row", return_value=record),
    ):
        result = InstallationRevalidator(release_policy=policy).revalidate_in_transaction(conn, lock=lock)
    assert result.checked_at == checked_at
    policy.evaluate.assert_called_once()

"""Transition-time selected release revalidation tests."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from aos_api.asset_registry.errors import RegistrySnapshotStaleError
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

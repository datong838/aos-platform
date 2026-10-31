"""Offline admission tests for the one-shot native166 savepoint runner."""

from hashlib import sha256
import importlib.util
from pathlib import Path

import pytest


RUNNER = Path(__file__).with_name("run_native166_savepoint_r882.py")
SPEC = importlib.util.spec_from_file_location("native166_savepoint_r882", RUNNER)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_missing_database_url_is_rejected():
    with pytest.raises(RuntimeError, match="exact local database URL required"):
        runner.admitted_database_url({})


@pytest.mark.parametrize("value", [
    runner.EXPECTED_DATABASE_URL.replace("127.0.0.1", "localhost"),
    runner.EXPECTED_DATABASE_URL.replace(":18458", ":18455"),
    runner.EXPECTED_DATABASE_URL.replace("aos_app@", "postgres@"),
    runner.EXPECTED_DATABASE_URL.replace("aos_refresh_activation_native", "postgres"),
    runner.EXPECTED_DATABASE_URL.replace("aos_app@", "aos_app:secret@"),
])
def test_any_connection_identity_or_secret_drift_is_rejected(value):
    with pytest.raises(RuntimeError, match="exact local database URL required"):
        runner.admitted_database_url({runner.DATABASE_URL_ENV: value})


def test_exact_no_password_loopback_url_is_admitted():
    assert runner.admitted_database_url({
        runner.DATABASE_URL_ENV: runner.EXPECTED_DATABASE_URL,
    }) == runner.EXPECTED_DATABASE_URL


def test_file_pin_accepts_exact_bytes_and_rejects_drift(tmp_path):
    source = tmp_path / "source.py"
    source.write_bytes(b"exact-source\n")
    expected = sha256(source.read_bytes()).hexdigest()
    assert runner.require_file_pin(source, expected) == expected
    with pytest.raises(RuntimeError, match="source pin differs"):
        runner.require_file_pin(source, "0" * 64)


def test_history_digest_is_order_sensitive_and_never_returns_rows():
    first = runner.history_summary(("row-a", "row-b"))
    second = runner.history_summary(("row-b", "row-a"))
    assert first == {
        "count": 2,
        "sha256": sha256(b"row-a\nrow-b").hexdigest(),
    }
    assert first != second
    assert "row-a" not in repr(first)


def test_public_result_has_fixed_secret_free_shape():
    result = runner.public_result(
        before={"key": "old", "history": {"count": 2, "sha256": "a" * 64}},
        after={"key": "old", "history": {"count": 2, "sha256": "a" * 64}},
        source_hashes={"migration": "b" * 64, "native_test": "c" * 64},
    )
    assert result["schema"] == "aos-native166-savepoint-result/v1"
    assert result["knownOutcome"] == "SAVEPOINT_UPGRADE_AND_ROLLBACK_GREEN"
    assert set(result) == {
        "schema", "knownOutcome", "database", "databaseOid", "clusterName",
        "administratorRole", "tenant", "sourceHashes", "before", "after",
        "persistentStateRestored", "businessAcceptance",
    }
    rendered = repr(result).lower()
    assert "database_url" not in rendered
    assert "password" not in rendered
    assert "secret" not in rendered

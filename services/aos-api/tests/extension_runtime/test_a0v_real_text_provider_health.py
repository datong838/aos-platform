"""Pure controls for the one-attempt A0-V Provider health executor."""

from __future__ import annotations

import importlib.util
import json
import stat
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_real_text_provider_health.py"
SPEC = importlib.util.spec_from_file_location("a0v_real_text_provider_health", SCRIPT)
assert SPEC and SPEC.loader
HEALTH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HEALTH)


def test_preflight_is_one_attempt_metadata_only_and_exactly_scoped():
    result = HEALTH.run(HEALTH.parse_args([]))

    assert result["outcome"] == "PREFLIGHT_GREEN"
    assert result["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert result["probeCount"] == result["maxAttempts"] == 1
    assert result["timeoutMs"] == 10_000
    assert result["maxOutputTokens"] == 32
    assert result["outputPolicy"] == "metadata-only"
    assert "35-R1-C" not in json.dumps(result)


def test_apply_requires_exact_database_before_connector(monkeypatch):
    monkeypatch.setattr(
        HEALTH,
        "_load_first_installer",
        lambda: (_ for _ in ()).throw(AssertionError("connector loaded")),
    )
    with pytest.raises(HEALTH.ProviderHealthBlocked) as captured:
        HEALTH.run(HEALTH.parse_args(["--apply", "--database-name", "aos_meta"]))
    assert captured.value.code == "EXPLICIT_ISOLATED_DATABASE_REQUIRED"


def test_attempt_journal_is_atomic_private_and_contains_no_bodies(tmp_path):
    payload = {
        "attemptId": HEALTH.ATTEMPT_ID,
        "status": "submitted",
        "providerCalls": 1,
    }
    HEALTH._write_journal(tmp_path, payload)

    path = tmp_path / "attempt-v2.json"
    assert HEALTH._read_journal(tmp_path) == payload
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "prompt" not in path.read_text(encoding="utf-8").lower()
    assert "answer" not in path.read_text(encoding="utf-8").lower()


def test_invalid_or_foreign_attempt_journal_fails_closed(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "attempt-v2.json").write_text(
        '{"attemptId":"other","status":"submitted"}\n', encoding="utf-8"
    )
    with pytest.raises(HEALTH.ProviderHealthBlocked) as captured:
        HEALTH._read_journal(tmp_path)
    assert captured.value.code == "HEALTH_ATTEMPT_JOURNAL_INVALID"

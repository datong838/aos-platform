import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_current_preview_http.py"


@pytest.fixture
def preview():
    spec = importlib.util.spec_from_file_location("a0v_current_preview_http", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_missing_signed_root_rejected_before_database_access(preview, tmp_path, monkeypatch):
    receipt = tmp_path / "signing-receipt.json"
    receipt.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(preview, "_load", lambda *_: pytest.fail("loaded module before signature check"))
    with pytest.raises(preview.PreviewBlocked, match="SIGNING_RECEIPT_DRIFT"):
        preview.preflight(signed_receipt=receipt)


def test_all_execution_flags_are_explicitly_disabled(preview):
    assert preview.EXPECTED_SCHEMA_HEAD == "a0v_107"
    assert preview.FLAGS["AOS_EXTENSION_RUNTIME_HOST_ENABLED"] == "0"
    assert preview.FLAGS["AOS_QYH_CRON_ENABLED"] == "false"
    assert preview.FLAGS["AOS_DB_MIGRATION_MODE"] == "disabled"
    assert all(value == "false" for key, value in preview.FLAGS.items() if "WORKER_ENABLED" in key)

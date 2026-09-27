import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_current_preview_registry_publish.py"


@pytest.fixture
def publisher():
    spec = importlib.util.spec_from_file_location("current_preview_registry_publish", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_missing_signed_tree_rejected_before_database_access(publisher, tmp_path, monkeypatch):
    receipt = tmp_path / "signed.json"
    receipt.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(publisher, "_connect_factory", lambda: pytest.fail("database accessed"))
    with pytest.raises(publisher.PublishBlocked, match="SIGNED_TREE_UNAVAILABLE"):
        publisher.preflight(signed_receipt=receipt)


def test_existing_publish_state_retained_without_mutation(publisher, tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    marker = state / "keep"
    marker.write_text("retained", encoding="utf-8")
    monkeypatch.setattr(publisher, "preflight", lambda **_: pytest.fail("preflight after state exists"))
    with pytest.raises(publisher.PublishBlocked, match="STATE_MUST_BE_NEW_OUTSIDE_REPOSITORY"):
        publisher.publish(signed_receipt=tmp_path, state=state)
    assert marker.read_text(encoding="utf-8") == "retained"

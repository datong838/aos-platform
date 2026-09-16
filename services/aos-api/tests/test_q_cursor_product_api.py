from pathlib import Path
import sys
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import a0v_q_cursor_product_api as module


def test_q_cursor_reload_preserves_natural_profile(monkeypatch):
    expected = {
        "AOS_SNAPSHOT_GROUP_WORKER_ENABLED": "true",
        "AOS_SNAPSHOT_GROUP_WORKER_TOPOLOGY": "independent",
        "AOS_QYH_CRON_ENABLED": "true",
        "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "0",
    }
    launcher = SimpleNamespace(API_FLAGS=expected.copy())
    monkeypatch.setattr(module.natural_api, "load_launcher", lambda: launcher)

    assert module.load_launcher() is launcher
    assert launcher.API_FLAGS == expected
    assert module.TASK == "A0V-NATURAL-CHAIN-MAIN-UPGRADE-20260915"

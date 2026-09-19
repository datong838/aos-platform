"""BA terminal monitor is read-only and blocks a second natural attempt."""
import importlib.util
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_ba_terminal_monitor.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("a0v_ba_terminal_monitor", SCRIPT)
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)


def test_wait_running_terminal_and_second_attempt_stop():
    assert monitor.classify([])["outcome"] == "WAITING_FOR_NATURAL_ATTEMPT"
    assert monitor.classify([{"state": "running"}])["outcome"] == "NATURAL_ATTEMPT_RUNNING"
    terminal = monitor.classify([{"state": "failed", "attempt_id": "one"}])
    assert terminal == {"outcome": "FIRST_NATURAL_ATTEMPT_TERMINAL", "terminal": True,
                        "state": "failed", "attempt_id": "one"}
    assert monitor.classify([{"state": "failed"}, {"state": "running"}])["outcome"] == (
        "SAFE_BLOCKED_MULTIPLE_ATTEMPTS")


def test_monitor_is_select_only():
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden = re.compile(r"\b(?:insert|update|delete|call|run_definition|transition)\b", re.I)
    assert forbidden.search(source) is None
    assert "ORDER BY accepted_at,attempt_id" in source

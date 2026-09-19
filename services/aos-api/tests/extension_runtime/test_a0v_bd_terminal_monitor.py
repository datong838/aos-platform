"""BD monitor derives its budget from immutable attempt accepted_at."""
import importlib.util
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bd_terminal_monitor.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("a0v_bd_terminal_monitor", SCRIPT)
monitor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(monitor)


def test_wait_running_budget_terminal_and_second_attempt():
    assert monitor.classify([])["outcome"] == "WAITING_FOR_NATURAL_ATTEMPT"
    assert monitor.classify([{"state": "running", "attempt_elapsed_seconds": 1799}])["outcome"] == (
        "NATURAL_ATTEMPT_RUNNING")
    assert monitor.classify([{"state": "running", "attempt_elapsed_seconds": 1800}])["outcome"] == (
        "ATTEMPT_ELAPSED_BUDGET_EXHAUSTED")
    assert monitor.classify([{"state": "failed", "attempt_elapsed_seconds": 1801}])["outcome"] == (
        "FIRST_NATURAL_ATTEMPT_TERMINAL")
    assert monitor.classify([{"state": "failed"}, {"state": "running"}])["outcome"] == (
        "SAFE_BLOCKED_MULTIPLE_ATTEMPTS")


def test_monitor_is_select_only():
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden = re.compile(r"\b(?:insert|update|delete|call|run_definition|transition)\b", re.I)
    assert forbidden.search(source) is None
    assert "clock_timestamp()-accepted_at" in source

"""BK supervisor couples the database stop decision to the exact worker process."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock, call, patch
import sys


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_bk_terminal_supervisor.py"
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("a0v_bk_terminal_supervisor", SCRIPT)
supervisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supervisor)


def test_wait_running_budget_terminal_and_second_attempt():
    assert supervisor.classify([])["outcome"] == "WAITING_FOR_NATURAL_ATTEMPT"
    assert supervisor.classify([{"state": "running", "attempt_elapsed_seconds": 1799}])["outcome"] == (
        "NATURAL_ATTEMPT_RUNNING")
    assert supervisor.classify([{"state": "running", "attempt_elapsed_seconds": 1800}])["outcome"] == (
        "ATTEMPT_ELAPSED_BUDGET_EXHAUSTED")
    assert supervisor.classify([{"state": "failed", "attempt_elapsed_seconds": 1801}])["outcome"] == (
        "FIRST_NATURAL_ATTEMPT_TERMINAL")
    assert supervisor.classify([{"state": "failed"}, {"state": "running"}])["outcome"] == (
        "SAFE_BLOCKED_MULTIPLE_ATTEMPTS")


def test_stop_worker_targets_exact_process_group_and_waits():
    worker = Mock(pid=43210)
    worker.poll.side_effect = [None, 0]
    worker.wait.return_value = 0
    with patch.object(supervisor.os, "killpg") as killpg:
        result = supervisor.stop_worker(worker, timeout_seconds=7)
    killpg.assert_called_once_with(43210, supervisor.signal.SIGTERM)
    worker.wait.assert_called_once_with(timeout=7)
    assert result == {"workerPid": 43210, "workerReturnCode": 0, "workerStopped": True,
                      "workerKillEscalated": False}


def test_stop_worker_escalates_only_exact_process_group_after_timeout():
    worker = Mock(pid=43210)
    worker.poll.side_effect = [None, -9]
    worker.wait.side_effect = [supervisor.subprocess.TimeoutExpired("worker", 180), -9]
    with patch.object(supervisor.os, "killpg") as killpg:
        result = supervisor.stop_worker(worker, timeout_seconds=180, kill_timeout_seconds=30)
    assert killpg.call_args_list == [
        call(43210, supervisor.signal.SIGTERM),
        call(43210, supervisor.signal.SIGKILL),
    ]
    assert result == {"workerPid": 43210, "workerReturnCode": -9, "workerStopped": True,
                      "workerKillEscalated": True}


def test_supervisor_never_calls_manual_definition_execution():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "run_definition" not in source
    assert "start_new_session=True" in source
    assert '"--output", str(worker_output)' in source
    assert "stop_requested = True" in source
    assert "stop_worker(worker)" in source
    assert 'default=50' in source

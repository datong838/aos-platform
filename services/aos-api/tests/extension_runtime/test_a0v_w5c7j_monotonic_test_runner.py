"""The bounded runner must stop once and preserve explicit test outcomes."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

import a0v_w5c7j_monotonic_test_runner as runner


SCRIPT = Path(runner.__file__)


def _run(timeout, code, *, grace="0.2"):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--timeout-seconds", str(timeout),
         "--grace-seconds", grace, "--", sys.executable, "-c", code],
        capture_output=True, text=True, timeout=5,
    )
    summary = json.loads(result.stdout.split("A0V_BOUNDED_TEST ")[-1])
    return result, summary


def test_success_preserves_child_zero_without_retry():
    result, summary = _run(2, "print('child_once', flush=True)")
    assert result.returncode == 0
    assert result.stdout.count("child_once") == 1
    assert summary["outcome"] == "CHILD_EXITED"
    assert summary["childExitCode"] == summary["runnerExitCode"] == 0
    assert summary["timedOut"] is False


def test_nonzero_child_is_not_rewritten_or_retried():
    result, summary = _run(2, "import sys; print('child_once', flush=True); sys.exit(7)")
    assert result.returncode == 7
    assert result.stdout.count("child_once") == 1
    assert summary["childExitCode"] == summary["runnerExitCode"] == 7
    assert summary["outcome"] == "CHILD_EXITED"


def test_monotonic_timeout_interrupts_process_group_once():
    result, summary = _run(
        0.15, "import time; print('child_once', flush=True); time.sleep(5)")
    assert result.returncode == 124
    assert result.stdout.count("child_once") == 1
    assert summary["outcome"] == "MONOTONIC_TIMEOUT"
    assert summary["timedOut"] is True
    assert summary["monotonicSeconds"] < 3


@pytest.mark.parametrize("budget", ["0", "nan", "inf", "1801"])
def test_invalid_budget_never_starts_child(budget):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--timeout-seconds", budget,
         "--", sys.executable, "-c", "print('must_not_run')"],
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 2
    assert "must_not_run" not in result.stdout


def test_missing_executable_is_explicit_start_failure():
    result = runner.run(["/nonexistent/a0v-bounded-test"], timeout_seconds=1)
    assert result["outcome"] == "START_FAILED"
    assert result["runnerExitCode"] == 125
    assert result["childExitCode"] is None

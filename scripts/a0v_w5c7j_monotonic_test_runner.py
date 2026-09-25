"""Bound one explicitly supplied isolated test command by monotonic time."""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import subprocess
import sys
import time


def _exit_code(code):
    return code if code >= 0 else 128 - code


def _stop_group(child, grace_seconds):
    try:
        os.killpg(child.pid, signal.SIGINT)
    except ProcessLookupError:
        pass
    try:
        return child.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            return child.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            return None


def run(command, *, timeout_seconds, grace_seconds=5.0):
    """Run once, never retry, and always report the measured child outcome."""
    if (not command or type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 1800
            or type(grace_seconds) not in (int, float)
            or not math.isfinite(grace_seconds) or not 0 < grace_seconds <= 30):
        raise ValueError("exact command and bounded monotonic budget required")
    start = time.monotonic()
    try:
        child = subprocess.Popen(command, start_new_session=True)
    except OSError:
        return {"outcome": "START_FAILED", "timedOut": False,
                "monotonicSeconds": round(time.monotonic() - start, 3),
                "childExitCode": None, "runnerExitCode": 125}
    try:
        code = child.wait(timeout=timeout_seconds)
        return {"outcome": "CHILD_EXITED", "timedOut": False,
                "monotonicSeconds": round(time.monotonic() - start, 3),
                "childExitCode": code, "runnerExitCode": _exit_code(code)}
    except subprocess.TimeoutExpired:
        code = _stop_group(child, grace_seconds)
        return {"outcome": "MONOTONIC_TIMEOUT", "timedOut": True,
                "monotonicSeconds": round(time.monotonic() - start, 3),
                "childExitCode": code, "runnerExitCode": 124}
    except KeyboardInterrupt:
        code = _stop_group(child, grace_seconds)
        return {"outcome": "RUNNER_INTERRUPTED", "timedOut": False,
                "monotonicSeconds": round(time.monotonic() - start, 3),
                "childExitCode": code, "runnerExitCode": 130}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--grace-seconds", type=float, default=5.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        result = run(command, timeout_seconds=args.timeout_seconds,
                     grace_seconds=args.grace_seconds)
    except ValueError as exc:
        parser.error(str(exc))
    print("A0V_BOUNDED_TEST " + json.dumps(result, sort_keys=True), flush=True)
    return result["runnerExitCode"]


if __name__ == "__main__":
    sys.exit(main())

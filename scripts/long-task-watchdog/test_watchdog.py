import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import watchdog


def record(timestamp, role, phase=None):
    return {
        "timestamp": timestamp,
        "type": "response_item",
        "payload": {"type": "message", "role": role, "phase": phase},
    }


def task_event(timestamp, event_type):
    return {
        "timestamp": timestamp,
        "type": "event_msg",
        "payload": {"type": event_type},
    }


class WatchdogTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.transcript = self.root / "rollout.jsonl"

    def tearDown(self):
        self.temp.cleanup()

    def write(self, *records):
        self.transcript.write_text(
            "".join(json.dumps(item) + "\n" for item in records), encoding="utf-8"
        )
        os.utime(self.transcript, (100, 100))

    def config(self):
        return {
            "enabled": True,
            "thread_id": "thread-1",
            "rollout_path": str(self.transcript),
            "project_root": str(self.root),
            "resume_prompt": "continue from checkpoint",
            "grace_seconds": 10,
            "max_tool_silence_seconds": 100,
            "retry_interval_seconds": 300,
            "max_retry_interval_seconds": 3600,
            "config_revision": "workshop-watchdog-v2",
            "ack_path": str(self.root / "recovery-ack.json"),
            "expected_branch": "w2-workshop",
            "sandbox_mode": "workspace-write",
            "network_access": True,
            "writable_roots": [
                str(self.root / "git-common"),
                str(self.root / "docs"),
            ],
        }

    def append(self, *records):
        with self.transcript.open("a", encoding="utf-8") as handle:
            for item in records:
                handle.write(json.dumps(item) + "\n")

    def write_ack(self, *, outcome="resumed-progress", **overrides):
        value = {
            "schema": "aos-watchdog-recovery-ack/v1",
            "episode_id": "recovery-1000000",
            "thread_id": "thread-1",
            "project_root": str(self.root),
            "expected_branch": "w2-workshop",
            "actual_branch": "w2-workshop",
            "outcome": outcome,
            "permission_status": "GREEN",
            "authority_revision": "AOS-000019",
            "head_before": "abc1234",
            "head_after": "def5678",
            "task_id": "workshop-test",
            "next_task": "workshop-next",
            "reason_code": "PROGRESS_CHECKPOINTED",
            "blocker_fingerprint": None,
            "evidence_refs": ["commit:def5678"],
            "written_at": time.time(),
        }
        value.update(overrides)
        Path(self.config()["ack_path"]).write_text(json.dumps(value), encoding="utf-8")

    def test_user_without_final_is_active(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        status = watchdog.inspect_transcript(self.transcript)
        self.assertTrue(status.active)

    def test_error_words_in_completed_chat_do_not_trigger(self):
        item = record("1970-01-01T00:00:10Z", "user")
        item["payload"]["content"] = [
            {"type": "input_text", "text": "stream disconnected before completion"}
        ]
        self.write(item, record("1970-01-01T00:00:20Z", "assistant", "final"))
        self.assertFalse(watchdog.inspect_transcript(self.transcript).active)

    def test_pending_tool_call_prevents_recovery(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            {
                "timestamp": "1970-01-01T00:00:20Z",
                "type": "response_item",
                "payload": {"type": "custom_tool_call", "call_id": "call-1"},
            },
        )
        decision, status = watchdog.evaluate(
            self.config(), {}, now=50, rollout_path=self.transcript
        )
        self.assertEqual(1, status.pending_tool_calls)
        self.assertEqual("tool-running", decision)

    def test_running_turn_prevents_recovery_even_after_grace(self):
        self.write(
            task_event("1970-01-01T00:00:05Z", "task_started"),
            record("1970-01-01T00:00:10Z", "user"),
        )
        decision, status = watchdog.evaluate(
            self.config(), {}, now=1000, rollout_path=self.transcript
        )
        self.assertTrue(status.turn_running)
        self.assertEqual("turn-running", decision)

    def test_completed_failed_turn_allows_recovery(self):
        self.write(
            task_event("1970-01-01T00:00:05Z", "task_started"),
            record("1970-01-01T00:00:10Z", "user"),
            task_event("1970-01-01T00:00:20Z", "task_complete"),
        )
        decision, status = watchdog.evaluate(
            self.config(), {}, now=1000, rollout_path=self.transcript
        )
        self.assertFalse(status.turn_running)
        self.assertEqual("recover", decision)

    def test_completed_tool_call_allows_recovery(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            {
                "timestamp": "1970-01-01T00:00:20Z",
                "type": "response_item",
                "payload": {"type": "custom_tool_call", "call_id": "call-1"},
            },
            {
                "timestamp": "1970-01-01T00:00:30Z",
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "call_id": "call-1",
                },
            },
        )
        decision, status = watchdog.evaluate(
            self.config(), {}, now=1000, rollout_path=self.transcript
        )
        self.assertEqual(0, status.pending_tool_calls)
        self.assertEqual("recover", decision)

    def test_stale_pending_tool_eventually_allows_recovery(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            {
                "timestamp": "1970-01-01T00:00:20Z",
                "type": "response_item",
                "payload": {"type": "custom_tool_call", "call_id": "call-1"},
            },
        )
        decision, _ = watchdog.evaluate(
            self.config(), {}, now=1000, rollout_path=self.transcript
        )
        self.assertEqual("recover", decision)

    def test_later_final_is_idle(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:00:20Z", "assistant", "final"),
        )
        status = watchdog.inspect_transcript(self.transcript)
        self.assertFalse(status.active)

    def test_later_final_answer_is_idle(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:00:20Z", "assistant", "final_answer"),
        )
        status = watchdog.inspect_transcript(self.transcript)
        self.assertFalse(status.active)

    def test_commentary_is_not_terminal(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:00:20Z", "assistant", "commentary"),
        )
        self.assertTrue(watchdog.inspect_transcript(self.transcript).active)

    def test_work_activity_after_foreign_final_keeps_turn_active(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:00:20Z", "assistant", "final_answer"),
            record("1970-01-01T00:00:30Z", "assistant", "commentary"),
        )
        status = watchdog.inspect_transcript(self.transcript)
        self.assertTrue(status.post_final_activity)
        self.assertTrue(status.active)

    def test_resume_command_uses_scoped_permissions_without_bypass(self):
        command = watchdog.resume_command(
            self.config(), episode_id="recovery-1"
        )
        self.assertIn("--sandbox", command)
        self.assertIn("workspace-write", command)
        self.assertEqual(2, command.count("--add-dir"))
        self.assertIn("sandbox_workspace_write.network_access=true", command)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)
        self.assertEqual("resume", command[-4])
        self.assertEqual("thread-1", command[-2])

    def test_resume_command_rejects_broad_or_unbounded_sandbox(self):
        for sandbox_mode, roots in (
            ("danger-full-access", [str(self.root / "docs")]),
            ("workspace-write", ["/"]),
            ("workspace-write", [str(Path.home())]),
        ):
            with self.subTest(sandbox_mode=sandbox_mode, roots=roots):
                config = self.config()
                config["sandbox_mode"] = sandbox_mode
                config["writable_roots"] = roots
                with self.assertRaises(RuntimeError):
                    watchdog.resume_command(config, episode_id="recovery-1")

    def test_first_detection_attempts_once_then_backs_off_five_minutes(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.config()), encoding="utf-8")
        calls = []

        def runner(*args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args[0], 1, "", "network")

        decision = watchdog.run_once(
            config_path, state_path, now=1000, runner=runner
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("retry-scheduled", decision)
        self.assertEqual(1, len(calls))
        self.assertEqual(1, state["consecutive_failures"])
        self.assertEqual(300, state["retry_delay_seconds"])
        self.assertEqual(1300, state["next_retry_at"])

    def test_backoff_prevents_early_retry(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        decision, _ = watchdog.evaluate(
            self.config(), {"next_retry_at": 1200}, now=1000, rollout_path=self.transcript
        )
        self.assertEqual("backoff", decision)

    def test_invalid_backoff_config_fails_before_waking_runner(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config = self.config()
        config["retry_interval_seconds"] = 0
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args[0], 1, "", "network")

        with self.assertRaises(RuntimeError):
            watchdog.run_once(config_path, state_path, now=1000, runner=runner)
        self.assertEqual([], calls)

    def test_resumed_progress_ack_and_final_answer_stop_retry_chain(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.config()), encoding="utf-8")

        def runner(*args, **kwargs):
            self.write_ack()
            self.append(record("1970-01-01T00:16:41Z", "assistant", "final_answer"))
            return subprocess.CompletedProcess(args[0], 0, "completed", "")

        decision = watchdog.run_once(
            config_path, state_path, now=1000, runner=runner
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("resumed-progress", decision)
        self.assertEqual(0, state["next_retry_at"])
        self.assertEqual(0, state["consecutive_failures"])
        self.assertEqual("resumed-progress", state["last_recovery_outcome"])
        self.assertIsNotNone(state["visible_ack_at"])

    def test_safe_blocked_ack_stops_retry_and_next_tick_does_not_resume(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.config()), encoding="utf-8")
        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            self.write_ack(
                outcome="safe-blocked",
                permission_status="BLOCKED",
                reason_code="RECOVERY_ENVIRONMENT_INSUFFICIENT",
                blocker_fingerprint="git-docs-network",
                evidence_refs=["preflight:permission-blocked"],
            )
            self.append(record("1970-01-01T00:16:41Z", "assistant", "final_answer"))
            return subprocess.CompletedProcess(args[0], 0, "blocked", "")

        self.assertEqual(
            "safe-blocked",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        self.assertEqual(
            "idle",
            watchdog.run_once(config_path, state_path, now=1100, runner=runner),
        )
        self.assertEqual(1, len(calls))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("safe-blocked", state["last_recovery_outcome"])
        self.assertEqual(0, state["next_retry_at"])

    def test_completed_and_reentry_noop_are_terminal_outcomes(self):
        for outcome in ("completed", "reentry-noop"):
            with self.subTest(outcome=outcome):
                self.write(record("1970-01-01T00:00:10Z", "user"))
                config_path = self.root / f"config-{outcome}.json"
                state_path = self.root / f"state-{outcome}.json"
                config_path.write_text(json.dumps(self.config()), encoding="utf-8")

                def runner(*args, **kwargs):
                    self.write_ack(
                        outcome=outcome,
                        reason_code=outcome.upper().replace("-", "_"),
                        blocker_fingerprint=("active-turn" if outcome == "reentry-noop" else None),
                    )
                    self.append(record("1970-01-01T00:16:41Z", "assistant", "final_answer"))
                    return subprocess.CompletedProcess(args[0], 0, outcome, "")

                self.assertEqual(
                    outcome,
                    watchdog.run_once(config_path, state_path, now=1000, runner=runner),
                )

    def test_final_without_ack_is_protocol_failed_and_not_retried(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.config()), encoding="utf-8")
        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            self.append(record("1970-01-01T00:16:41Z", "assistant", "final_answer"))
            return subprocess.CompletedProcess(args[0], 0, "completed", "")

        self.assertEqual(
            "protocol-failed",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        self.assertEqual(
            "protocol-failed",
            watchdog.run_once(config_path, state_path, now=1100, runner=runner),
        )
        self.assertEqual(1, len(calls))

    def test_stale_or_wrong_episode_ack_is_protocol_failed(self):
        for overrides in (
            {"written_at": 1},
            {"episode_id": "recovery-old"},
            {"thread_id": "other-thread"},
            {"project_root": "/other"},
            {"actual_branch": "w1-aip"},
        ):
            with self.subTest(overrides=overrides):
                self.write(record("1970-01-01T00:00:10Z", "user"))
                config_path = self.root / "config.json"
                state_path = self.root / "state.json"
                config_path.write_text(json.dumps(self.config()), encoding="utf-8")

                def runner(*args, **kwargs):
                    self.write_ack(**overrides)
                    self.append(record("1970-01-01T00:16:41Z", "assistant", "final_answer"))
                    return subprocess.CompletedProcess(args[0], 0, "completed", "")

                self.assertEqual(
                    "protocol-failed",
                    watchdog.run_once(config_path, state_path, now=1000, runner=runner),
                )

    def test_ack_without_final_is_outcome_uncertain_and_not_retried(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.config()), encoding="utf-8")

        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            self.write_ack()
            return subprocess.CompletedProcess(args[0], 0, "completed", "")

        self.assertEqual(
            "outcome-uncertain",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        self.assertEqual(
            "outcome-uncertain",
            watchdog.run_once(config_path, state_path, now=2000, runner=runner),
        )
        self.assertEqual(1, len(calls))

    def test_transport_failures_continue_after_third_failure(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config = self.config()
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args[0], 1, "", "network")

        self.assertEqual(
            "retry-scheduled",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        self.assertEqual(
            "retry-scheduled",
            watchdog.run_once(config_path, state_path, now=1300, runner=runner),
        )
        self.assertEqual(
            "retry-scheduled",
            watchdog.run_once(config_path, state_path, now=1900, runner=runner),
        )
        self.assertEqual(
            "retry-scheduled",
            watchdog.run_once(config_path, state_path, now=2800, runner=runner),
        )
        self.assertEqual(4, len(calls))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("transport-failed", state["last_recovery_outcome"])
        self.assertEqual(4, state["consecutive_failures"])
        self.assertEqual(1200, state["retry_delay_seconds"])
        self.assertEqual(4000, state["next_retry_at"])

    def test_transport_backoff_decays_and_caps_without_third_failure_break(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.config()), encoding="utf-8")
        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args[0], 1, "", "network")

        now = 1000
        expected = [
            300, 600, 900, 1200, 1500, 1800, 2100,
            2400, 2700, 3000, 3300, 3600, 3600,
        ]
        for failure_number, delay in enumerate(expected, start=1):
            self.assertEqual(
                "retry-scheduled",
                watchdog.run_once(config_path, state_path, now=now, runner=runner),
            )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(failure_number, state["consecutive_failures"])
            self.assertEqual(delay, state["retry_delay_seconds"])
            self.assertEqual(now + delay, state["next_retry_at"])
            now += delay
        self.assertEqual(13, len(calls))

    def test_exit_zero_without_visible_final_is_not_recovered(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.config()), encoding="utf-8")
        state_path.write_text(
            json.dumps({"last_recovered_at": 50, "consecutive_failures": 0}),
            encoding="utf-8",
        )

        def runner(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0, "completed", "")

        decision = watchdog.run_once(
            config_path, state_path, now=1000, runner=runner
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("retry-scheduled", decision)
        self.assertEqual("transport-failed", state["last_recovery_outcome"])
        self.assertIsNone(state["last_recovered_at"])
        self.assertIsNone(state["visible_ack_at"])
        self.assertTrue(state["recovery_episode_id"].startswith("recovery-"))

    def test_resume_environment_removes_api_keys(self):
        previous = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "must-not-leak"
        try:
            self.assertNotIn("OPENAI_API_KEY", watchdog._sanitized_environment())
        finally:
            if previous is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous

    def test_record_ack_captures_actual_branch_permissions_and_mode(self):
        subprocess.run(
            ["git", "init", "-b", "w2-workshop"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        (self.root / "git-common").mkdir()
        (self.root / "docs").mkdir()
        authority = self.root / "authority.json"
        authority.write_text(
            json.dumps({"project_revision": "AOS-000019"}), encoding="utf-8"
        )
        config = self.config()
        config["authority_path"] = str(authority)
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        state_path.write_text(
            json.dumps(
                {
                    "recovery_episode_id": "recovery-live",
                    "episode_head_before": None,
                }
            ),
            encoding="utf-8",
        )

        ack = watchdog.record_recovery_ack(
            config_path,
            state_path,
            episode_id="recovery-live",
            outcome="resumed-progress",
            task_id="workshop-test",
            next_task="workshop-next",
            reason_code="PROGRESS_CHECKPOINTED",
            blocker_fingerprint=None,
            evidence_refs=["test:green"],
        )

        self.assertEqual("w2-workshop", ack["actual_branch"])
        self.assertEqual("GREEN", ack["permission_status"])
        self.assertEqual("AOS-000019", ack["authority_revision"])
        self.assertTrue(ack["permission_preflight"]["git_common_dir"].endswith("/.git"))
        mode = Path(config["ack_path"]).stat().st_mode & 0o777
        self.assertEqual(0o600, mode)

    def test_isolated_full_loop_detects_wakes_records_progress_and_stops(self):
        subprocess.run(
            ["git", "init", "-b", "w2-workshop"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        (self.root / "git-common").mkdir()
        (self.root / "docs").mkdir()
        sentinel = self.root / "business-data.sentinel"
        sentinel.write_text("must-stay-unchanged", encoding="utf-8")
        authority = self.root / "authority.json"
        authority.write_text(
            json.dumps({"project_revision": "AOS-000019"}), encoding="utf-8"
        )
        self.write(
            task_event("1970-01-01T00:00:05Z", "task_started"),
            record("1970-01-01T00:00:10Z", "user"),
            task_event("1970-01-01T00:00:20Z", "task_complete"),
        )
        config = self.config()
        config["authority_path"] = str(authority)
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            self.assertIn("WORKSHOP_WATCHDOG_RECOVERY_PROTOCOL", kwargs["input"])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            watchdog.record_recovery_ack(
                config_path,
                state_path,
                episode_id=state["recovery_episode_id"],
                outcome="resumed-progress",
                task_id="workshop-test",
                next_task="workshop-next",
                reason_code="PROGRESS_CHECKPOINTED",
                blocker_fingerprint=None,
                evidence_refs=["fixture:checkpoint-green"],
            )
            self.append(
                record("1970-01-01T00:16:41Z", "assistant", "final_answer"),
                task_event("1970-01-01T00:16:42Z", "task_complete"),
            )
            return subprocess.CompletedProcess(command, 0, "completed", "")

        self.assertEqual(
            "resumed-progress",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        self.assertEqual(
            "idle",
            watchdog.run_once(config_path, state_path, now=2000, runner=runner),
        )
        self.assertEqual(1, len(calls))
        self.assertEqual("must-stay-unchanged", sentinel.read_text(encoding="utf-8"))

    def test_subprocess_full_loop_uses_scoped_command_ack_final_and_stops(self):
        subprocess.run(
            ["git", "init", "-b", "w2-workshop"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        (self.root / "git-common").mkdir()
        (self.root / "docs").mkdir()
        sentinel = self.root / "business-data.sentinel"
        sentinel.write_text("must-stay-unchanged", encoding="utf-8")
        self.write(
            task_event("1970-01-01T00:00:05Z", "task_started"),
            record("1970-01-01T00:00:10Z", "user"),
            task_event("1970-01-01T00:00:20Z", "task_complete"),
        )
        config = self.config()
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        fake_codex = self.root / "fake-codex.py"
        fake_codex.write_text(
            """#!/usr/bin/env python3
import json
import re
import subprocess
import sys

args = sys.argv[1:]
assert "--sandbox" in args and "workspace-write" in args
assert "--add-dir" in args
assert "--dangerously-bypass-approvals-and-sandbox" not in args
prompt = sys.stdin.read()
episode = re.search(r"^episode_id=(.+)$", prompt, re.MULTILINE).group(1)
config_path = re.search(r"^config_path=(.+)$", prompt, re.MULTILINE).group(1)
state_path = re.search(r"^state_path=(.+)$", prompt, re.MULTILINE).group(1)
ack_script = re.search(r"^ack_command=python3 (.+?) --config", prompt, re.MULTILINE).group(1)
config = json.load(open(config_path, encoding="utf-8"))
subprocess.run([
    sys.executable, ack_script,
    "--config", config_path,
    "--state", state_path,
    "--record-ack",
    "--episode-id", episode,
    "--outcome", "resumed-progress",
    "--task-id", "workshop-subprocess-test",
    "--next-task", "workshop-next",
    "--reason-code", "PROGRESS_CHECKPOINTED",
    "--evidence-ref", "fixture:subprocess-green",
], check=True, capture_output=True, text=True)
with open(config["rollout_path"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "timestamp": "1970-01-01T00:16:41Z",
        "type": "response_item",
        "payload": {"type": "message", "role": "assistant", "phase": "final_answer"},
    }) + "\\n")
    handle.write(json.dumps({
        "timestamp": "1970-01-01T00:16:42Z",
        "type": "event_msg",
        "payload": {"type": "task_complete"},
    }) + "\\n")
print(json.dumps({"outcome": "resumed-progress"}))
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o700)
        config["codex_path"] = str(fake_codex)
        config_path.write_text(json.dumps(config), encoding="utf-8")

        self.assertEqual(
            "resumed-progress",
            watchdog.run_once(config_path, state_path, now=1000),
        )
        self.assertEqual("idle", watchdog.run_once(config_path, state_path, now=2000))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(1, state["total_attempts"])
        self.assertEqual("resumed-progress", state["last_recovery_outcome"])
        self.assertEqual("must-stay-unchanged", sentinel.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

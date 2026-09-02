import json
import os
import sys
import re
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import watchdog


def record(timestamp, role, phase=None, content=None):
    payload = {"type": "message", "role": role, "phase": phase}
    if content is not None:
        payload["content"] = [{"type": "input_text", "text": content}]
    return {
        "timestamp": timestamp,
        "type": "response_item",
        "payload": payload,
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
            "retry_schedule_seconds": [300, 600, 900, 1800, 3600, 7200],
            "max_transport_failures": 12,
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

    def dependency_config(self):
        config = self.config()
        config["dependency_watch"] = {
            "enabled": True,
            "leases_path": str(self.root / "leases.json"),
            "scope_tokens": ["services/aos-api/alembic/versions"],
            "ignore_task_ids": ["workshop-test"],
        }
        return config

    def fact_config(self):
        config = self.config()
        config["fact_watch"] = {
            "enabled": True,
            "paths": [
                str(self.root / "authority.json"),
                str(self.root / "deliveries"),
            ],
        }
        return config

    def probe_fact_config(self):
        config = self.config()
        probe = self.root / "fact-probe.py"
        probe.write_text("print('stable-secret-fixture')\n", encoding="utf-8")
        config["fact_watch"] = {
            "enabled": True,
            "paths": [],
            "probes": [
                {
                    "name": "w2-data",
                    "argv": [os.path.abspath(sys.executable), str(probe)],
                    "cwd": str(self.root),
                    "timeout_seconds": 5,
                    "max_output_bytes": 1024,
                }
            ],
        }
        return config

    def continuation_config(self):
        config = self.config()
        config["continuation_watch"] = {
            "enabled": True,
            "delay_seconds": 300,
        }
        return config

    def blocked_recheck_config(self):
        config = self.config()
        config["blocked_recheck_watch"] = {
            "enabled": True,
            "delay_seconds": 1800,
        }
        return config

    def visibility_config(self, *, desktop_notification=False):
        config = self.config()
        config["visibility_watch"] = {
            "enabled": True,
            "desktop_notification": desktop_notification,
        }
        return config

    def write_leases(self, *leases):
        (self.root / "leases.json").write_text(
            json.dumps({"schema": "aos-memory-leases/v1", "leases": list(leases)}),
            encoding="utf-8",
        )

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

    def test_recent_running_turn_prevents_recovery(self):
        self.write(
            task_event("1970-01-01T00:00:05Z", "task_started"),
            record("1970-01-01T00:00:10Z", "user"),
        )
        decision, status = watchdog.evaluate(
            self.config(), {}, now=150, rollout_path=self.transcript
        )
        self.assertTrue(status.turn_running)
        self.assertEqual("turn-running", decision)

    def test_stale_running_turn_without_activity_allows_recovery(self):
        self.write(
            task_event("1970-01-01T00:00:05Z", "task_started"),
            record("1970-01-01T00:00:10Z", "user"),
        )
        decision, status = watchdog.evaluate(
            self.config(), {}, now=1000, rollout_path=self.transcript
        )
        self.assertTrue(status.turn_running)
        self.assertEqual("recover", decision)

    def test_stale_running_turn_with_production_watches_allows_recovery(self):
        self.write(
            task_event("1970-01-01T00:00:05Z", "task_started"),
            record("1970-01-01T00:00:10Z", "user"),
        )
        config = self.blocked_recheck_config()
        config["fact_watch"] = {"enabled": True, "paths": []}
        config["dependency_watch"] = {"enabled": False}
        decision, status = watchdog.evaluate(
            config, {}, now=1000, rollout_path=self.transcript
        )
        self.assertTrue(status.turn_running)
        self.assertEqual("recover", decision)

    def test_invalid_turn_silence_configuration_fails_closed(self):
        self.write(
            task_event("1970-01-01T00:00:05Z", "task_started"),
            record("1970-01-01T00:00:10Z", "user"),
        )
        config = self.config()
        config["max_turn_silence_seconds"] = 0
        with self.assertRaisesRegex(RuntimeError, "max_turn_silence_seconds"):
            watchdog.evaluate(config, {}, now=1000, rollout_path=self.transcript)

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
        config["retry_schedule_seconds"] = []
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

    def test_resumed_progress_arms_one_shot_continuation_after_delay(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(
            json.dumps(self.continuation_config()), encoding="utf-8"
        )
        calls = []

        def first_runner(*args, **kwargs):
            calls.append(kwargs["input"])
            self.write_ack(next_task="W3-09")
            self.append(record("1970-01-01T00:16:41Z", "assistant", "final_answer"))
            return subprocess.CompletedProcess(args[0], 0, "completed", "")

        self.assertEqual(
            "resumed-progress",
            watchdog.run_once(config_path, state_path, now=1000, runner=first_runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(state["continuation_armed"])
        self.assertEqual("W3-09", state["continuation_next_task"])
        self.assertEqual(
            "idle",
            watchdog.run_once(config_path, state_path, now=1299, runner=first_runner),
        )
        self.assertEqual(1, len(calls))

        def continuation_runner(*args, **kwargs):
            prompt = kwargs["input"]
            calls.append(prompt)
            episode = re.search(r"^episode_id=(.+)$", prompt, re.MULTILINE).group(1)
            self.write_ack(
                outcome="completed",
                episode_id=episode,
                next_task="NONE",
            )
            self.append(record("1970-01-01T00:21:41Z", "assistant", "final_answer"))
            return subprocess.CompletedProcess(args[0], 0, "completed", "")

        self.assertEqual(
            "completed",
            watchdog.run_once(
                config_path, state_path, now=1300, runner=continuation_runner
            ),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertFalse(state["continuation_armed"])
        self.assertIn("trigger=continuation", calls[1])
        self.assertTrue(calls[1].startswith("continue from checkpoint\n"))

    def test_manual_user_message_consumes_pending_continuation(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:16:41Z", "assistant", "final_answer"),
        )
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(
            json.dumps(self.continuation_config()), encoding="utf-8"
        )
        state_path.write_text(
            json.dumps(
                {
                    "continuation_armed": True,
                    "continuation_next_task": "W3-09",
                    "continuation_ready_at": 1300,
                    "continuation_user_cutoff_at": 10,
                    "last_recovery_outcome": "resumed-progress",
                }
            ),
            encoding="utf-8",
        )
        self.append(record("1970-01-01T00:18:20Z", "user", content="继续"))
        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args[0], 1, "", "must not run")

        self.assertEqual(
            "continuation-manual-reentry",
            watchdog.run_once(config_path, state_path, now=1200, runner=runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertFalse(state["continuation_armed"])
        self.assertEqual([], calls)

    def test_dependency_lease_keeps_continuation_armed_without_runner(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:16:41Z", "assistant", "final_answer"),
        )
        config = self.dependency_config()
        config["continuation_watch"] = {"enabled": True, "delay_seconds": 300}
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        state_path.write_text(
            json.dumps(
                {
                    "continuation_armed": True,
                    "continuation_next_task": "W3-09",
                    "continuation_ready_at": 900,
                    "continuation_user_cutoff_at": 10,
                    "last_recovery_outcome": "resumed-progress",
                }
            ),
            encoding="utf-8",
        )
        self.write_leases(
            {
                "task_id": "aip-migration",
                "owner": "w1-aip",
                "status": "ACTIVE",
                "scope": ["services/aos-api/alembic/versions"],
                "lease_expires_at": "2099-01-01T00:00:00+00:00",
            }
        )
        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args[0], 1, "", "must not run")

        self.assertEqual(
            "dependency-blocked",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(state["continuation_armed"])
        self.assertEqual([], calls)

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

    def test_safe_blocked_arms_periodic_recheck_and_wakes_when_due(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(
            json.dumps(self.blocked_recheck_config()), encoding="utf-8"
        )
        calls = []

        def first_runner(*args, **kwargs):
            calls.append(kwargs["input"])
            self.write_ack(
                outcome="safe-blocked",
                next_task="W2-00B",
                reason_code="DEPENDENCIES_NOT_GREEN",
                blocker_fingerprint="p07-and-source-readiness",
                evidence_refs=["probe:11-of-12"],
            )
            self.append(record("1970-01-01T00:16:41Z", "assistant", "final_answer"))
            return subprocess.CompletedProcess(args[0], 0, "blocked", "")

        self.assertEqual(
            "safe-blocked",
            watchdog.run_once(config_path, state_path, now=1000, runner=first_runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(state["blocked_recheck_armed"])
        self.assertEqual(2800, state["blocked_recheck_ready_at"])
        self.assertEqual(
            "idle",
            watchdog.run_once(config_path, state_path, now=2799, runner=first_runner),
        )
        self.assertEqual(1, len(calls))

        def recheck_runner(*args, **kwargs):
            prompt = kwargs["input"]
            calls.append(prompt)
            episode = re.search(r"^episode_id=(.+)$", prompt, re.MULTILINE).group(1)
            self.write_ack(
                outcome="safe-blocked",
                episode_id=episode,
                next_task="W2-00B",
                reason_code="DEPENDENCIES_STILL_NOT_GREEN",
                blocker_fingerprint="p07-and-source-readiness",
                evidence_refs=["probe:11-of-12"],
            )
            self.append(record("1970-01-01T00:46:41Z", "assistant", "final_answer"))
            return subprocess.CompletedProcess(args[0], 0, "blocked", "")

        self.assertEqual(
            "safe-blocked",
            watchdog.run_once(config_path, state_path, now=2800, runner=recheck_runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(state["blocked_recheck_armed"])
        self.assertEqual(4600, state["blocked_recheck_ready_at"])
        self.assertIn("trigger=blocked-recheck", calls[1])
        self.assertIn("rules=live-read AGENTS.md + ADR25", calls[1])
        self.assertNotIn("第一条用户可见消息", calls[1])

    def test_visible_wake_prompt_contains_metadata_and_marker_contract(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.visibility_config()), encoding="utf-8")

        def runner(command, **kwargs):
            prompt = kwargs["input"]
            self.assertIn("wake_sequence=1", prompt)
            self.assertRegex(
                prompt,
                r"wake_started_at=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
            )
            self.assertIn("[DOG_VISIBLE_STATUS]", prompt)
            self.write_ack()
            self.append(
                record(
                    "1970-01-01T00:16:41Z",
                    "assistant",
                    "final_answer",
                    "[DOG_VISIBLE_STATUS] outcome=resumed-progress",
                )
            )
            return subprocess.CompletedProcess(command, 0, "completed", "")

        self.assertEqual(
            "resumed-progress",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )

    def test_compact_visible_wake_prompt_keeps_machine_episode_contract(self):
        config = self.config()
        config["wake_visible_prompt"] = (
            "接续前面中断 继续Loop下去\n"
            "每一波都执行完整闭环；外加 独立 prime agent独立长记忆支持"
        )
        config["visibility_watch"] = {"enabled": True}
        config["_config_path"] = str(self.root / "config.json")
        config["_state_path"] = str(self.root / "state.json")

        prompt = watchdog._resume_prompt(
            config,
            "episode-compact",
            trigger="blocked-recheck",
            wake_sequence=9,
            wake_started_at=1000,
        )

        self.assertTrue(prompt.startswith("接续前面中断 继续Loop下去\n"))
        self.assertIn("独立 prime agent独立长记忆支持", prompt)
        self.assertIn("episode_id=episode-compact", prompt)
        self.assertIn("trigger=blocked-recheck", prompt)
        self.assertIn("wake_sequence=9", prompt)
        self.assertIn("ack_command=", prompt)
        self.assertNotIn("第一条用户可见消息必须以此句开头", prompt)
        self.assertNotIn("醒来后必须独立重新核验前后真实情况", prompt)

    def test_visible_wake_rejects_final_without_status_marker(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.visibility_config()), encoding="utf-8")

        def runner(command, **kwargs):
            self.write_ack()
            self.append(
                record(
                    "1970-01-01T00:16:41Z",
                    "assistant",
                    "final_answer",
                    "result without required visibility marker",
                )
            )
            return subprocess.CompletedProcess(command, 0, "completed", "")

        self.assertEqual(
            "protocol-failed",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("visible status marker missing", state["last_error"])

    def test_visible_safe_blocked_rejects_summary_without_blocker_details(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.visibility_config()), encoding="utf-8")

        def runner(command, **kwargs):
            self.write_ack(
                outcome="safe-blocked",
                reason_code="DEPENDENCY_NOT_GREEN",
                blocker_fingerprint="sha256:blocker",
            )
            self.append(
                record(
                    "1970-01-01T00:16:41Z",
                    "assistant",
                    "final_answer",
                    "[DOG_VISIBLE_STATUS] outcome=safe-blocked 阻断摘要：依赖未就绪",
                )
            )
            return subprocess.CompletedProcess(command, 0, "blocked", "")

        self.assertEqual(
            "protocol-failed",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("safe-blocked detail contract missing", state["last_error"])

    def test_visible_safe_blocked_accepts_structured_blocker_details(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.visibility_config()), encoding="utf-8")

        def runner(command, **kwargs):
            prompt = kwargs["input"]
            self.assertIn("[DOG_BLOCKER_DETAILS]", prompt)
            self.assertIn("独立核验证据", prompt)
            self.assertIn("责任边界", prompt)
            self.assertIn("解除条件", prompt)
            self.write_ack(
                outcome="safe-blocked",
                reason_code="DEPENDENCY_NOT_GREEN",
                blocker_fingerprint="sha256:blocker",
            )
            self.append(
                record(
                    "1970-01-01T00:16:41Z",
                    "assistant",
                    "final_answer",
                    """[DOG_VISIBLE_STATUS] outcome=safe-blocked
[DOG_BLOCKER_DETAILS]
- 阻断任务：W2-00B
- 缺失条件：canonical owner 尚未进入 m1
- 独立核验证据：m1 exact read-only 核验未命中
- 责任边界：m1/AIP owner 负责交付，w2 不代写
- 解除条件：owner、Receipt 与 CAS 同时 GREEN
- 下次复核策略：按 blocked recheck 周期重新独立核验""",
                )
            )
            return subprocess.CompletedProcess(command, 0, "blocked", "")

        self.assertEqual(
            "safe-blocked",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )

    def test_visible_safe_blocked_rejects_incomplete_blocker_fields(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.visibility_config()), encoding="utf-8")

        def runner(command, **kwargs):
            self.write_ack(
                outcome="safe-blocked",
                reason_code="DEPENDENCY_NOT_GREEN",
                blocker_fingerprint="sha256:blocker",
            )
            self.append(
                record(
                    "1970-01-01T00:16:41Z",
                    "assistant",
                    "final_answer",
                    """[DOG_VISIBLE_STATUS] outcome=safe-blocked
[DOG_BLOCKER_DETAILS]
- 阻断任务：W2-00B
- 缺失条件：canonical owner 尚未进入 m1
- 独立核验证据：m1 exact read-only 核验未命中
- 责任边界：m1/AIP owner 负责交付，w2 不代写
- 解除条件：owner、Receipt 与 CAS 同时 GREEN""",
                )
            )
            return subprocess.CompletedProcess(command, 0, "blocked", "")

        self.assertEqual(
            "protocol-failed",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )

    def test_visible_wake_invalid_enabled_value_fails_closed(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:00:20Z", "assistant", "final_answer"),
        )
        config = self.visibility_config()
        config["visibility_watch"]["enabled"] = "yes"
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "enabled must be a boolean"):
            watchdog.run_once(config_path, state_path, now=1000)

        config = self.visibility_config()
        config["visibility_watch"]["desktop_notification"] = "yes"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(
            RuntimeError, "desktop_notification must be a boolean"
        ):
            watchdog.run_once(config_path, state_path, now=1000)

    def test_visible_wake_persists_status_and_delivers_desktop_notifications(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(
            json.dumps(self.visibility_config(desktop_notification=True)),
            encoding="utf-8",
        )
        notifications = []

        def notification_runner(command, **kwargs):
            notifications.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, "", "")

        def runner(command, **kwargs):
            self.write_ack(
                evidence_refs=["secret-evidence-must-not-leak"],
                blocker_fingerprint="secret-fingerprint-must-not-leak",
            )
            self.append(
                record(
                    "1970-01-01T00:16:41Z",
                    "assistant",
                    "final_answer",
                    "[DOG_VISIBLE_STATUS] outcome=resumed-progress",
                )
            )
            return subprocess.CompletedProcess(command, 0, "completed", "")

        self.assertEqual(
            "resumed-progress",
            watchdog.run_once(
                config_path,
                state_path,
                now=1000,
                runner=runner,
                notification_runner=notification_runner,
            ),
        )
        visible_path = self.root / "visible-status.json"
        visible = json.loads(visible_path.read_text(encoding="utf-8"))
        self.assertEqual("closed", visible["stage"])
        self.assertEqual("resumed-progress", visible["outcome"])
        self.assertEqual("workshop-test", visible["task_id"])
        self.assertEqual("workshop-next", visible["next_task"])
        self.assertEqual("delivered", visible["notification_status"])
        self.assertEqual(0o600, visible_path.stat().st_mode & 0o777)
        self.assertEqual(2, len(notifications))
        rendered = visible_path.read_text(encoding="utf-8")
        self.assertNotIn("secret-evidence-must-not-leak", rendered)
        self.assertNotIn("secret-fingerprint-must-not-leak", rendered)

    def test_visible_notification_failure_is_audited_without_replaying_outcome(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(
            json.dumps(self.visibility_config(desktop_notification=True)),
            encoding="utf-8",
        )

        def notification_runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, "", "notification denied")

        def runner(command, **kwargs):
            self.write_ack()
            self.append(
                record(
                    "1970-01-01T00:16:41Z",
                    "assistant",
                    "final_answer",
                    "[DOG_VISIBLE_STATUS] outcome=resumed-progress",
                )
            )
            return subprocess.CompletedProcess(command, 0, "completed", "")

        self.assertEqual(
            "resumed-progress",
            watchdog.run_once(
                config_path,
                state_path,
                now=1000,
                runner=runner,
                notification_runner=notification_runner,
            ),
        )
        visible = json.loads(
            (self.root / "visible-status.json").read_text(encoding="utf-8")
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("failed", visible["notification_status"])
        self.assertEqual("desktop notification exit 1", visible["delivery_error"])
        self.assertEqual(
            "desktop notification exit 1", state["visibility_delivery_error"]
        )
        self.assertEqual("resumed-progress", state["last_recovery_outcome"])

    def test_visible_transport_failure_persists_retry_result(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(
            json.dumps(self.visibility_config(desktop_notification=True)),
            encoding="utf-8",
        )
        notifications = []

        def notification_runner(command, **kwargs):
            notifications.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, "", "network")

        self.assertEqual(
            "retry-scheduled",
            watchdog.run_once(
                config_path,
                state_path,
                now=1000,
                runner=runner,
                notification_runner=notification_runner,
            ),
        )
        visible = json.loads(
            (self.root / "visible-status.json").read_text(encoding="utf-8")
        )
        self.assertEqual("retry-scheduled", visible["stage"])
        self.assertEqual("transport-failed", visible["outcome"])
        self.assertEqual("next-launchd-check", visible["next_strategy"])
        self.assertEqual(2, len(notifications))

    def test_existing_safe_blocked_state_is_bootstrapped_without_runner(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:16:41Z", "assistant", "final_answer"),
        )
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(
            json.dumps(self.blocked_recheck_config()), encoding="utf-8"
        )
        state_path.write_text(
            json.dumps(
                {
                    "recovery_episode_id": "dependency-fact-existing",
                    "last_recovery_outcome": "safe-blocked",
                    "last_ack": {
                        "task_id": "W2-00B",
                        "blocker_fingerprint": "p07-and-source-readiness",
                    },
                }
            ),
            encoding="utf-8",
        )
        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args[0], 1, "", "must not run")

        self.assertEqual(
            "idle",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(state["blocked_recheck_armed"])
        self.assertEqual(2800, state["blocked_recheck_ready_at"])
        self.assertEqual(1000, state["blocked_recheck_bootstrapped_at"])
        self.assertEqual([], calls)

    def test_dependency_lease_keeps_blocked_recheck_armed_without_runner(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:16:41Z", "assistant", "final_answer"),
        )
        config = self.dependency_config()
        config["blocked_recheck_watch"] = {
            "enabled": True,
            "delay_seconds": 1800,
        }
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        state_path.write_text(
            json.dumps(
                {
                    "blocked_recheck_armed": True,
                    "blocked_recheck_ready_at": 900,
                    "last_recovery_outcome": "safe-blocked",
                    "last_ack": {
                        "task_id": "W2-00B",
                        "blocker_fingerprint": "p07-and-source-readiness",
                    },
                }
            ),
            encoding="utf-8",
        )
        self.write_leases(
            {
                "task_id": "aip-migration",
                "owner": "w1-aip",
                "status": "ACTIVE",
                "scope": ["services/aos-api/alembic/versions"],
                "lease_expires_at": "2099-01-01T00:00:00+00:00",
            }
        )
        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args[0], 1, "", "must not run")

        self.assertEqual(
            "dependency-blocked",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(state["blocked_recheck_armed"])
        self.assertEqual([], calls)

    def test_blocked_recheck_progress_disarms_recheck_and_arms_continuation(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:16:41Z", "assistant", "final_answer"),
        )
        config = self.blocked_recheck_config()
        config["continuation_watch"] = {"enabled": True, "delay_seconds": 300}
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        state_path.write_text(
            json.dumps(
                {
                    "blocked_recheck_armed": True,
                    "blocked_recheck_ready_at": 900,
                    "last_recovery_outcome": "safe-blocked",
                    "last_ack": {
                        "task_id": "W2-00B",
                        "blocker_fingerprint": "old-blocker",
                    },
                }
            ),
            encoding="utf-8",
        )

        def runner(*args, **kwargs):
            episode = re.search(
                r"^episode_id=(.+)$", kwargs["input"], re.MULTILINE
            ).group(1)
            self.write_ack(
                outcome="resumed-progress",
                episode_id=episode,
                next_task="W2-01",
                reason_code="DEPENDENCIES_GREEN_PROGRESS_STARTED",
                blocker_fingerprint=None,
                evidence_refs=["commit:new-progress"],
            )
            self.append(record("1970-01-01T00:20:01Z", "assistant", "final_answer"))
            return subprocess.CompletedProcess(args[0], 0, "progress", "")

        self.assertEqual(
            "resumed-progress",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertFalse(state["blocked_recheck_armed"])
        self.assertEqual("resumed-progress", state["blocked_recheck_disarm_reason"])
        self.assertTrue(state["continuation_armed"])
        self.assertEqual("W2-01", state["continuation_next_task"])

    def test_blocked_recheck_invalid_delay_fails_closed(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:16:41Z", "assistant", "final_answer"),
        )
        config = self.blocked_recheck_config()
        config["blocked_recheck_watch"]["delay_seconds"] = 0
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "delay_seconds"):
            watchdog.run_once(config_path, state_path, now=1000)

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

    def test_transport_failures_pause_at_limit_and_stop_runner(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config = self.config()
        config["max_transport_failures"] = 3
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
            "paused-failure",
            watchdog.run_once(config_path, state_path, now=1900, runner=runner),
        )
        self.assertEqual(
            "paused-failure",
            watchdog.run_once(config_path, state_path, now=10000, runner=runner),
        )
        self.assertEqual(3, len(calls))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("paused-failure", state["last_recovery_outcome"])
        self.assertEqual(0, state["next_retry_at"])

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
        expected = [300, 600, 900, 1800, 3600, 7200, 7200]
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
        self.assertEqual(7, len(calls))

    def test_dependency_lease_blocks_idle_and_arms_without_runner(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:00:20Z", "assistant", "final_answer"),
        )
        self.write_leases({
            "task_id": "aip-w2d1",
            "owner": "codex-aip-w1",
            "status": "ACTIVE",
            "scope": ["services/aos-api/alembic/versions"],
            "lease_expires_at": "2099-01-01T00:00:00+08:00",
        })
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.dependency_config()), encoding="utf-8")
        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args[0], 0, "", "")

        self.assertEqual(
            "dependency-blocked",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        self.assertEqual(
            "dependency-blocked",
            watchdog.run_once(config_path, state_path, now=1300, runner=runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(state["dependency_wait_armed"])
        self.assertEqual(["aip-w2d1"], state["dependency_blocking_task_ids"])
        self.assertEqual([], calls)

    def test_dependency_directory_token_matches_descendant_file_lease(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:00:20Z", "assistant", "final_answer"),
        )
        self.write_leases({
            "task_id": "aip-p8-2",
            "owner": "codex-aip-w1",
            "status": "ACTIVE",
            "scope": [
                "services/aos-api/alembic/versions/"
                "aip8_001_analyst_query_authority.py"
            ],
            "lease_expires_at": "2099-01-01T00:00:00+08:00",
        })
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.dependency_config()), encoding="utf-8")

        self.assertEqual(
            "dependency-blocked",
            watchdog.run_once(config_path, state_path, now=1000),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(state["dependency_wait_armed"])
        self.assertEqual(["aip-p8-2"], state["dependency_blocking_task_ids"])

    def test_dependency_directory_token_does_not_match_adjacent_prefix(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:00:20Z", "assistant", "final_answer"),
        )
        self.write_leases({
            "task_id": "aip-unrelated",
            "owner": "codex-aip-w1",
            "status": "ACTIVE",
            "scope": [
                "services/aos-api/alembic/versions-old/"
                "aip8_001_analyst_query_authority.py"
            ],
            "lease_expires_at": "2099-01-01T00:00:00+08:00",
        })
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.dependency_config()), encoding="utf-8")

        self.assertEqual("idle", watchdog.run_once(config_path, state_path, now=1000))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertFalse(state.get("dependency_wait_armed", False))

    def test_dependency_release_waits_while_turn_is_running(self):
        self.write(
            task_event("1970-01-01T00:00:05Z", "task_started"),
            record("1970-01-01T00:00:10Z", "user"),
        )
        self.write_leases()
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.dependency_config()), encoding="utf-8")
        state_path.write_text(json.dumps({"dependency_wait_armed": True}), encoding="utf-8")
        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args[0], 0, "", "")

        self.assertEqual(
            "turn-running",
            watchdog.run_once(config_path, state_path, now=150, runner=runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(state["dependency_wait_armed"])
        self.assertEqual([], calls)

    def test_dependency_release_wakes_once_with_exact_prompt_and_ack(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:00:20Z", "assistant", "final_answer"),
        )
        self.write_leases()
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.dependency_config()), encoding="utf-8")
        state_path.write_text(json.dumps({"dependency_wait_armed": True}), encoding="utf-8")
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            self.assertIn("trigger=dependency-released", kwargs["input"])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.write_ack(episode_id=state["recovery_episode_id"])
            self.append(record("1970-01-01T00:16:41Z", "assistant", "final_answer"))
            return subprocess.CompletedProcess(command, 0, "completed", "")

        self.assertEqual(
            "resumed-progress",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        self.assertEqual(
            "idle",
            watchdog.run_once(config_path, state_path, now=1300, runner=runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertFalse(state["dependency_wait_armed"])
        self.assertEqual("dependency-released", state["episode_trigger"])
        self.assertEqual(1, len(calls))

    def test_manual_reentry_consumes_failed_dependency_release_episode(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:00:20Z", "assistant", "final_answer"),
        )
        self.write_leases()
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.dependency_config()), encoding="utf-8")
        state_path.write_text(json.dumps({"dependency_wait_armed": True}), encoding="utf-8")
        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args[0], 1, "", "network")

        self.assertEqual(
            "retry-scheduled",
            watchdog.run_once(config_path, state_path, now=1000, runner=runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["last_attempt_at"] = 1000
        state_path.write_text(json.dumps(state), encoding="utf-8")
        self.append(record("1970-01-01T00:18:20Z", "user", content="继续开发"))

        self.assertEqual(
            "manual-reentry",
            watchdog.run_once(config_path, state_path, now=1100, runner=runner),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("reentry-noop", state["last_recovery_outcome"])
        self.assertFalse(state["dependency_wait_armed"])
        self.assertEqual(0, state["consecutive_failures"])
        self.assertEqual(0, state["next_retry_at"])
        self.assertIsNone(state["last_recovered_at"])
        self.assertEqual(1, len(calls))

    def test_watchdog_resume_prompt_does_not_count_as_manual_reentry(self):
        marker = "[WORKSHOP_WATCHDOG_RECOVERY_PROTOCOL]"
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:00:20Z", "assistant", "final_answer"),
            record("1970-01-01T00:18:20Z", "user", content=marker),
        )
        self.write_leases()
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.dependency_config()), encoding="utf-8")
        state_path.write_text(
            json.dumps(
                {
                    "dependency_wait_armed": True,
                    "episode_trigger": "dependency-released",
                    "last_recovery_outcome": "transport-failed",
                    "last_attempt_at": 1000,
                    "consecutive_failures": 1,
                    "next_retry_at": 1300,
                }
            ),
            encoding="utf-8",
        )

        self.assertEqual(
            "live",
            watchdog.run_once(config_path, state_path, now=1100),
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("transport-failed", state["last_recovery_outcome"])
        self.assertTrue(state["dependency_wait_armed"])

    def test_nonmatching_lease_does_not_arm_dependency_watch(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:00:20Z", "assistant", "final_answer"),
        )
        self.write_leases({
            "task_id": "aip-ui",
            "owner": "codex-aip-w1",
            "status": "ACTIVE",
            "scope": ["apps/web/src/pages/aip"],
            "lease_expires_at": "2099-01-01T00:00:00+08:00",
        })
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.dependency_config()), encoding="utf-8")
        self.assertEqual("idle", watchdog.run_once(config_path, state_path, now=1000))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertFalse(state.get("dependency_wait_armed", False))

    def test_fact_watch_baselines_then_wakes_once_on_idle_change(self):
        self.write(
            record("1970-01-01T00:00:10Z", "user"),
            record("1970-01-01T00:00:20Z", "assistant", "final_answer"),
        )
        (self.root / "authority.json").write_text(
            json.dumps({"project_revision": "AOS-000019"}), encoding="utf-8"
        )
        deliveries = self.root / "deliveries"
        deliveries.mkdir()
        (deliveries / "one.json").write_text("{}", encoding="utf-8")
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.fact_config()), encoding="utf-8")
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            self.assertIn("trigger=dependency-fact-changed", kwargs["input"])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.write_ack(episode_id=state["recovery_episode_id"])
            self.append(record("1970-01-01T00:21:41Z", "assistant", "final_answer"))
            return subprocess.CompletedProcess(command, 0, "completed", "")

        self.assertEqual("idle", watchdog.run_once(config_path, state_path, now=1000, runner=runner))
        (deliveries / "two.json").write_text('{"result":"GREEN"}', encoding="utf-8")
        self.assertEqual(
            "resumed-progress",
            watchdog.run_once(config_path, state_path, now=1300, runner=runner),
        )
        self.assertEqual("idle", watchdog.run_once(config_path, state_path, now=1600, runner=runner))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("dependency-fact-changed", state["episode_trigger"])
        self.assertEqual(1, len(calls))

    def test_fact_watch_active_turn_absorbs_change_without_wake(self):
        self.write(
            task_event("1970-01-01T00:00:05Z", "task_started"),
            record("1970-01-01T00:00:10Z", "user"),
        )
        authority = self.root / "authority.json"
        authority.write_text('{"project_revision":"AOS-000019"}', encoding="utf-8")
        deliveries = self.root / "deliveries"
        deliveries.mkdir()
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config = self.fact_config()
        config["max_turn_silence_seconds"] = 2000
        config_path.write_text(json.dumps(config), encoding="utf-8")
        calls = []

        def runner(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args[0], 0, "", "")

        self.assertEqual("turn-running", watchdog.run_once(config_path, state_path, now=1000, runner=runner))
        authority.write_text('{"project_revision":"AOS-000020"}', encoding="utf-8")
        self.assertEqual("turn-running", watchdog.run_once(config_path, state_path, now=1300, runner=runner))
        self.append(
            task_event("1970-01-01T00:21:41Z", "task_complete"),
            record("1970-01-01T00:21:42Z", "assistant", "final_answer"),
        )
        self.assertEqual("idle", watchdog.run_once(config_path, state_path, now=1600, runner=runner))
        self.assertEqual([], calls)

    def test_fact_watch_rejects_symlink(self):
        target = self.root / "target.json"
        target.write_text("{}", encoding="utf-8")
        link = self.root / "authority.json"
        link.symlink_to(target)
        deliveries = self.root / "deliveries"
        deliveries.mkdir()
        with self.assertRaisesRegex(RuntimeError, "symbolic links"):
            watchdog._fact_fingerprint(self.fact_config())

    def test_fact_watch_applies_max_files_to_individual_roots(self):
        first = self.root / "authority.json"
        second = self.root / "receipt.json"
        first.write_text("{}", encoding="utf-8")
        second.write_text("{}", encoding="utf-8")
        config = self.config()
        config["fact_watch"] = {
            "enabled": True,
            "paths": [str(first), str(second)],
            "max_files": 1,
        }
        with self.assertRaisesRegex(RuntimeError, "exceeds max_files"):
            watchdog._fact_fingerprint(config)

    def test_fact_watch_probe_is_deterministic_and_stores_only_digest(self):
        config = self.probe_fact_config()
        first = watchdog._fact_fingerprint(config)
        second = watchdog._fact_fingerprint(config)
        self.assertEqual(first, second)
        self.assertNotIn("stable-secret-fixture", str(first))
        probe = Path(config["fact_watch"]["probes"][0]["argv"][1])
        probe.write_text("print('changed')\n", encoding="utf-8")
        self.assertNotEqual(first, watchdog._fact_fingerprint(config))

    def test_fact_watch_probe_rejects_relative_executable_and_nonzero_exit(self):
        config = self.probe_fact_config()
        config["fact_watch"]["probes"][0]["argv"][0] = "python3"
        with self.assertRaisesRegex(RuntimeError, "existing absolute path"):
            watchdog._fact_fingerprint(config)

        config = self.probe_fact_config()
        probe = Path(config["fact_watch"]["probes"][0]["argv"][1])
        probe.write_text("raise SystemExit(2)\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "exited nonzero"):
            watchdog._fact_fingerprint(config)

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

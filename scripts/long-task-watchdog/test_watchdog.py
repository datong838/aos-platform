import json
import os
import subprocess
import tempfile
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
            "immediate_retry_delay_seconds": 0,
        }

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

    def test_first_detection_retries_twice_then_backs_off(self):
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
        self.assertEqual(2, len(calls))
        self.assertEqual(2, state["consecutive_failures"])
        self.assertGreater(state["next_retry_at"], 1000)

    def test_backoff_prevents_early_retry(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        decision, _ = watchdog.evaluate(
            self.config(), {"next_retry_at": 1200}, now=1000, rollout_path=self.transcript
        )
        self.assertEqual("backoff", decision)

    def test_success_stops_retry_chain(self):
        self.write(record("1970-01-01T00:00:10Z", "user"))
        config_path = self.root / "config.json"
        state_path = self.root / "state.json"
        config_path.write_text(json.dumps(self.config()), encoding="utf-8")

        def runner(*args, **kwargs):
            with self.transcript.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(record("1970-01-01T00:16:41Z", "assistant", "final"))
                    + "\n"
                )
            return subprocess.CompletedProcess(args[0], 0, "completed", "")

        decision = watchdog.run_once(
            config_path, state_path, now=1000, runner=runner
        )
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("recovered", decision)
        self.assertEqual(0, state["next_retry_at"])
        self.assertEqual(0, state["consecutive_failures"])
        self.assertEqual("recovered", state["last_recovery_outcome"])
        self.assertIsNotNone(state["visible_ack_at"])

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
        self.assertEqual("failed", state["last_recovery_outcome"])
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


if __name__ == "__main__":
    unittest.main()

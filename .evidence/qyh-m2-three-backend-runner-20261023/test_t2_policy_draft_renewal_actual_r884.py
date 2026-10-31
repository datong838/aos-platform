"""Offline state-machine tests for the four-step renewal actual."""

from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import sys

import pytest


BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
sys.path[:0] = [str(BASE), str(ROOT / "services/aos-api"),
                str(ROOT / "services/aos-api/tests/extension_runtime")]
MODULE = BASE / "t2_policy_draft_renewal_actual_r884.py"
SPEC = importlib.util.spec_from_file_location("t2_policy_draft_renewal_actual_r884", MODULE)
actual = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(actual)


def identity():
    return actual.expected_journal_identity()


class Reader:
    def __init__(self):
        self.values = {}
        self.calls = []

    def read(self, step):
        self.calls.append(step)
        return self.values.get(step)


class Publisher:
    def __init__(self, reader, *, fail=False):
        self.reader = reader
        self.fail = fail
        self.calls = []

    def __call__(self, step, request, descriptor):
        self.calls.append(step)
        if self.fail:
            raise RuntimeError("injected unknown")
        value = {
            "operationId": "aip10r-" + "1" * 20,
            "factHash": "sha256:" + str(len(self.calls)) * 64,
        }
        self.reader.values[step] = value
        return value


def session(tmp_path, *, fail=False):
    journal = actual.RenewalJournal.create(tmp_path / "journal", identity())
    reader = Reader()
    publisher = Publisher(reader, fail=fail)
    return actual.RenewalSession(
        journal=journal,
        reader=reader,
        publish=publisher,
        admit_current=lambda: None,
    ), reader, publisher


def test_journal_identity_drift_is_rejected(tmp_path):
    value = identity()
    value["scope"] = {"orgId": "dev-org", "projectId": "dev-project"}
    with pytest.raises(ValueError, match="renewal identity differs"):
        actual.RenewalJournal.create(tmp_path / "journal", value)


def test_old_idempotency_key_is_rejected(tmp_path):
    journal = actual.RenewalJournal.create(tmp_path / "journal", identity())
    descriptor = dict(actual.renewal_descriptors()[0])
    descriptor["idempotencyKey"] = "m2-three-t2-draft-budget"
    with pytest.raises(ValueError, match="renewal descriptor differs"):
        journal.freeze_attempt("budget", descriptor)


def test_each_known_return_is_settled_before_next_step(tmp_path):
    current, reader, publisher = session(tmp_path)
    for expected in actual.STEPS:
        state = current.issue_one()
        assert state.mode in {"ISSUE", "COMPLETE"}
        assert publisher.calls[-1] == expected
        assert reader.calls[-1] == expected
    assert current.recover().mode == "COMPLETE"
    assert publisher.calls == list(actual.STEPS)


def test_unknown_attempt_without_receipt_never_replays(tmp_path):
    current, reader, publisher = session(tmp_path, fail=True)
    with pytest.raises(RuntimeError, match="unknown; readonly reconciliation only"):
        current.issue_one()
    assert publisher.calls == ["budget"]
    with pytest.raises(LookupError, match="outcome unknown"):
        current.recover()
    with pytest.raises(LookupError, match="outcome unknown"):
        current.issue_one()
    assert publisher.calls == ["budget"]


def test_unknown_attempt_can_only_settle_from_exact_readback(tmp_path):
    current, reader, publisher = session(tmp_path, fail=True)
    with pytest.raises(RuntimeError):
        current.issue_one()
    reader.values["budget"] = {
        "operationId": "aip10r-" + "2" * 20,
        "factHash": "sha256:" + "a" * 64,
    }
    state = current.recover()
    assert state.mode == "ISSUE" and state.step == "egress"
    assert publisher.calls == ["budget"]


def test_settled_readback_drift_is_rejected(tmp_path):
    current, reader, unused = session(tmp_path)
    current.issue_one()
    reader.values["budget"] = {
        "operationId": "aip10r-" + "9" * 20,
        "factHash": "sha256:" + "f" * 64,
    }
    with pytest.raises(ValueError, match="readback differs"):
        current.recover()


def test_complete_session_cannot_publish_again(tmp_path):
    current, unused, publisher = session(tmp_path)
    for _ in actual.STEPS:
        current.issue_one()
    with pytest.raises(FileExistsError, match="already complete"):
        current.issue_one()
    assert len(publisher.calls) == 4

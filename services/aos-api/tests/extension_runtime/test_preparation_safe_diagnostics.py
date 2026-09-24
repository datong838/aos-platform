"""Preparation diagnostics expose code locations, never exception values."""

import asyncio
import pytest

from aos_api.extension_runtime import preparation_worker
from aos_api.extension_runtime.preparation_worker import PreparedJob, _safe_failure_trace


def _raise_secret():
    raise RuntimeError("secret-password-and-customer-payload")


def test_bounded_trace_omits_exception_message():
    try:
        _raise_secret()
    except RuntimeError as error:
        observed = _safe_failure_trace(error)
    assert observed[0]["type"] == "RuntimeError"
    assert observed[0]["frames"][-1][1] == "_raise_secret"
    assert "secret-password" not in str(observed)
    assert all(not frame[0].startswith("/") for item in observed for frame in item["frames"])


def test_failed_job_logs_safe_trace_and_keeps_finalize(monkeypatch):
    recorded = []

    class Logger:
        def error(self, template, payload):
            recorded.append(template % payload)

    monkeypatch.setattr(preparation_worker, "_LOG", Logger())

    async def run():
        finalized = []

        class Owner:
            async def wait_closed(self):
                _raise_secret()

        job = PreparedJob(None, Owner(), finalized.append)
        with pytest.raises(RuntimeError, match="secret-password"):
            await job.wait_closed()
        assert finalized == ["PREPARATION_EXECUTION_FAILED"]

    asyncio.run(run())
    assert len(recorded) == 1
    assert "preparation_failed_safe_trace=" in recorded[0]
    assert "RuntimeError" in recorded[0]
    assert "secret-password-and-customer-payload" not in recorded[0]

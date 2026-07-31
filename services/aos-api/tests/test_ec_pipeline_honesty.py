from __future__ import annotations

import threading
import time

import pytest

from aos_api.phase5_pipeline_engine import get_engine


@pytest.fixture(autouse=True)
def reset_engine():
    get_engine().reset()
    yield


def _evidence_executor(**kwargs):
    assert kwargs["execution_kind"] in {"schedule", "trial"}
    return {
        "input_ref": "dataset://input/v1",
        "output_ref": "dataset://output/v2",
        "rows_read": 3,
        "rows_written": 2,
        "lineage_ref": "lineage://run/1",
        "quality_ref": "quality://run/1",
        "output_rows": [{"id": "a"}, {"id": "b"}],
    }


def test_schedule_without_executor_never_succeeds():
    eng = get_engine()
    pl = eng.create_pipeline(name="p")
    sc = eng.create_schedule(name="s", pipeline_id=pl.id)

    run = eng.run_schedule(sc.id)

    assert run.status == "unsupported"
    assert run.error_code == "PIPELINE_EXECUTOR_MISSING"
    assert run.rows_written == 0
    assert run.output_ref == ""


def test_registered_executor_produces_traceable_success():
    eng = get_engine()
    eng.register_executor("synthetic-test", _evidence_executor)
    pl = eng.create_pipeline(name="p", executor_id="synthetic-test", execution_mode="live")
    sc = eng.create_schedule(name="s", pipeline_id=pl.id)

    run = eng.run_schedule(sc.id)

    assert run.status == "succeeded"
    assert run.executor_id == "synthetic-test"
    assert run.output_ref == "dataset://output/v2"
    assert run.rows_read == 3
    assert run.rows_written == 2
    assert run.rows_processed == 2


def test_trial_run_calls_executor_and_returns_actual_rows():
    eng = get_engine()
    eng.register_executor("synthetic-test", _evidence_executor)
    pl = eng.create_pipeline(name="p", executor_id="synthetic-test", execution_mode="live")
    node = eng.add_node(pl.id, "transform", node_type="transform")

    result = eng.trial_run(pl.id, node.id, {"safe": True})

    assert result["status"] == "succeeded"
    assert result["output_rows"] == [{"id": "a"}, {"id": "b"}]
    assert result["output_ref"] == "dataset://output/v2"


@pytest.mark.parametrize(
    ("node_type", "config"),
    [
        ("join", {}),
        ("Join", {}),
        ("sql", {}),
        ("SQL", {}),
        ("transform", {"sql": "select 1"}),
        ("transform", {"nested": {"CustomSQL": "select 1"}}),
    ],
)
def test_unsupported_nodes_are_not_dispatched(node_type, config):
    eng = get_engine()
    called = False

    def executor(**_kwargs):
        nonlocal called
        called = True
        return _evidence_executor(**_kwargs)

    eng.register_executor("live", executor)
    pl = eng.create_pipeline(name="p", executor_id="live", execution_mode="live")
    eng.add_node(pl.id, "unsafe", node_type=node_type, config=config)
    sc = eng.create_schedule(name="s", pipeline_id=pl.id)

    run = eng.run_schedule(sc.id)

    assert run.status == "unsupported"
    assert run.error_code == "PIPELINE_NODE_UNSUPPORTED"
    assert called is False


def test_paused_schedule_is_not_dispatched():
    eng = get_engine()
    eng.register_executor("live", _evidence_executor)
    pl = eng.create_pipeline(name="p", executor_id="live", execution_mode="live")
    sc = eng.create_schedule(name="s", pipeline_id=pl.id, status="paused")

    run = eng.run_schedule(sc.id)

    assert run.status == "unsupported"
    assert run.error_code == "SCHEDULE_NOT_ACTIVE"


def test_executor_exception_is_failed_and_secret_is_not_exposed():
    eng = get_engine()

    def failing(**_kwargs):
        raise RuntimeError("Authorization: Bearer top-secret-token")

    eng.register_executor("broken", failing)
    pl = eng.create_pipeline(name="p", executor_id="broken", execution_mode="live")
    sc = eng.create_schedule(name="s", pipeline_id=pl.id)

    run = eng.run_schedule(sc.id)

    assert run.status == "failed"
    assert run.error_code == "PIPELINE_EXECUTOR_FAILED"
    assert "top-secret-token" not in run.error_message
    assert run.output_ref == ""


def test_missing_output_evidence_cannot_be_success():
    eng = get_engine()
    eng.register_executor("bad", lambda **_kwargs: {"rows_read": 1, "rows_written": 1})
    pl = eng.create_pipeline(name="p", executor_id="bad", execution_mode="live")
    sc = eng.create_schedule(name="s", pipeline_id=pl.id)

    run = eng.run_schedule(sc.id)

    assert run.status == "failed"
    assert run.error_code == "PIPELINE_EVIDENCE_INVALID"


def test_stored_demo_pipeline_cannot_execute_live():
    eng = get_engine()
    eng.register_executor("live", _evidence_executor)
    pl = eng.create_pipeline(name="demo", executor_id="live", execution_mode="demo", tags=["demo"])
    sc = eng.create_schedule(name="s", pipeline_id=pl.id)

    run = eng.run_schedule(sc.id)

    assert run.status == "unsupported"
    assert run.error_code == "PIPELINE_MODE_UNSUPPORTED"


def test_executor_sees_running_record_and_only_mutates_snapshots():
    eng = get_engine()
    observed = {}

    def executor(**kwargs):
        observed["statuses"] = [r.status for r in eng.list_schedule_runs(observed["schedule_id"])]
        kwargs["pipeline"].executor_id = "forged"
        kwargs["nodes"][0].config["sql"] = "mutated"
        return _evidence_executor(**kwargs)

    eng.register_executor("real", executor)
    pl = eng.create_pipeline(name="p", executor_id="real", execution_mode="live")
    node = eng.add_node(pl.id, "n", node_type="transform")
    sc = eng.create_schedule(name="s", pipeline_id=pl.id)
    observed["schedule_id"] = sc.id

    run = eng.run_schedule(sc.id)

    assert "running" in observed["statuses"]
    assert run.executor_id == "real"
    assert eng.get_pipeline(pl.id).executor_id == "real"
    assert eng.get_node(node.id).config == {}


def test_executor_timeout_sets_cancel_signal_and_fails():
    eng = get_engine()
    cancelled = threading.Event()

    def executor(**kwargs):
        while not kwargs["cancel_event"].wait(0.001):
            if time.monotonic() > kwargs["deadline"] + 1:
                break
        cancelled.set()
        return _evidence_executor(**kwargs)

    eng.register_executor("slow", executor)
    pl = eng.create_pipeline(
        name="p",
        executor_id="slow",
        execution_mode="live",
        execution_timeout_seconds=0.01,
    )
    sc = eng.create_schedule(name="s", pipeline_id=pl.id)

    run = eng.run_schedule(sc.id)

    assert run.status == "failed"
    assert run.error_code == "PIPELINE_EXECUTOR_TIMEOUT"
    assert cancelled.wait(0.2)


@pytest.mark.parametrize(
    "output_ref",
    ["ok", "https://example.test/result", "dataset://user:secret@output/v1", "dataset://output/v1?token=x"],
)
def test_untraceable_or_sensitive_output_ref_cannot_succeed(output_ref):
    eng = get_engine()
    eng.register_executor(
        "bad-ref",
        lambda **_kwargs: {"output_ref": output_ref, "rows_read": 1, "rows_written": 1},
    )
    pl = eng.create_pipeline(name="p", executor_id="bad-ref", execution_mode="live")
    sc = eng.create_schedule(name="s", pipeline_id=pl.id)

    run = eng.run_schedule(sc.id)

    assert run.status == "failed"
    assert run.error_code == "PIPELINE_EVIDENCE_INVALID"
    assert output_ref not in run.error_message


def test_preview_and_health_are_explicitly_synthetic():
    eng = get_engine()
    pl = eng.create_pipeline(name="p")
    node = eng.add_node(pl.id, "n")
    ds = eng.create_dataset(name="d", schema=[{"name": "id", "datatype": "int"}])

    assert eng.preview_node(pl.id, node.id)["synthetic"] is True
    assert eng.preview_dataset(ds.id)["mode"] == "demo"
    health = eng.check_health(ds.id)
    assert health.synthetic is True
    assert health.mode == "demo"


def test_demo_trial_route_is_explicitly_unsupported(client):
    response = client.post(
        "/v1/pipelines/demo-pipeline/nodes/demo-transform/trial-run",
        json={"sample_input": {"secret": "must-not-be-echoed"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "demo"
    assert body["status"] == "unsupported"
    assert body["output_rows"] == []
    assert "must-not-be-echoed" not in response.text

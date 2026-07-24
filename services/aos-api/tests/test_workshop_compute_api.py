"""W2-AQ · Workshop Compute API 组测试（#147 / #151 / #152）.

覆盖 WorkshopVariableEngine / ComputeJobPollingEngine / AppEntryConventionEngine 三引擎。
"""
from __future__ import annotations

from datetime import datetime

import pytest

from aos_api.workshop_compute_api import (
    AppEntry,
    AppEntryConventionEngine,
    AppEntryError,
    ComputeJob,
    ComputeJobError,
    ComputeJobPollingEngine,
    VariableEvent,
    WorkshopVariable,
    WorkshopVariableEngine,
    WorkshopVariableError,
    _MAX_APP_ENTRIES,
    _MAX_COMPUTE_JOBS,
    _MAX_WORKSHOP_VARIABLES,
    get_app_entry_convention_engine,
    get_compute_job_polling_engine,
    get_workshop_variable_engine,
)


# ════════════════════════════════════════════════════════════════
# #147 WorkshopVariableEngine
# ════════════════════════════════════════════════════════════════


class TestWorkshopVariable:
    """#147 · WorkshopVariableEngine."""

    def setup_method(self):
        self.eng = WorkshopVariableEngine()
        self.eng._variables = {}
        self.eng._events = []

    def test_register(self):
        out = self.eng.register(
            WorkshopVariable(name="v1", var_type="string", definition_type="static", value="hello")
        )
        assert out.var_id.startswith("var-")
        assert out.status == "active"
        assert out.created_at is not None

    def test_get(self):
        out = self.eng.register(
            WorkshopVariable(name="v1", var_type="string", definition_type="static", value="x")
        )
        got = self.eng.get(out.var_id)
        assert got.name == "v1"
        assert got.value == "x"

    def test_list(self):
        self.eng.register(WorkshopVariable(name="a", var_type="string", definition_type="static"))
        self.eng.register(WorkshopVariable(name="b", var_type="numeric", definition_type="static"))
        assert len(self.eng.list()) == 2

    def test_list_filter_var_type(self):
        self.eng.register(WorkshopVariable(name="a", var_type="string", definition_type="static"))
        self.eng.register(WorkshopVariable(name="b", var_type="numeric", definition_type="static"))
        items = self.eng.list(var_type="string")
        assert len(items) == 1
        assert items[0].var_type == "string"

    def test_list_filter_definition_type(self):
        self.eng.register(WorkshopVariable(name="a", var_type="string", definition_type="static"))
        self.eng.register(
            WorkshopVariable(name="b", var_type="string", definition_type="function")
        )
        items = self.eng.list(definition_type="function")
        assert len(items) == 1
        assert items[0].definition_type == "function"

    def test_list_filter_module_id(self):
        self.eng.register(
            WorkshopVariable(name="a", var_type="string", definition_type="static", module_id="m1")
        )
        self.eng.register(
            WorkshopVariable(name="b", var_type="numeric", definition_type="static", module_id="m2")
        )
        items = self.eng.list(module_id="m1")
        assert len(items) == 1
        assert items[0].module_id == "m1"

    def test_update(self):
        out = self.eng.register(
            WorkshopVariable(name="v", var_type="string", definition_type="static", value="old")
        )
        self.eng.update(out.var_id, {"value": "new"})
        assert self.eng.get(out.var_id).value == "new"

    def test_update_var_type(self):
        out = self.eng.register(
            WorkshopVariable(name="v", var_type="string", definition_type="static")
        )
        self.eng.update(out.var_id, {"var_type": "numeric"})
        assert self.eng.get(out.var_id).var_type == "numeric"

    def test_delete(self):
        out = self.eng.register(
            WorkshopVariable(name="v", var_type="string", definition_type="static")
        )
        self.eng.delete(out.var_id)
        with pytest.raises(WorkshopVariableError) as exc:
            self.eng.get(out.var_id)
        assert exc.value.code == "NOT_FOUND"

    def test_delete_removes_from_depends_on(self):
        b = self.eng.register(
            WorkshopVariable(name="b", var_type="string", definition_type="static", value="1")
        )
        a = self.eng.register(
            WorkshopVariable(
                name="a",
                var_type="string",
                definition_type="variable_transformation",
                depends_on=[b.var_id],
            )
        )
        self.eng.delete(b.var_id)
        assert b.var_id not in self.eng.get(a.var_id).depends_on

    def test_evaluate_static(self):
        out = self.eng.register(
            WorkshopVariable(name="v", var_type="string", definition_type="static", value="hello")
        )
        assert self.eng.evaluate(out.var_id) == {"value": "hello"}

    def test_evaluate_function(self):
        out = self.eng.register(
            WorkshopVariable(name="v", var_type="string", definition_type="function")
        )
        assert self.eng.evaluate(out.var_id) == {"value": f"func_result_{out.var_id}"}

    def test_evaluate_transformation(self):
        base = self.eng.register(
            WorkshopVariable(
                name="base", var_type="string", definition_type="static", value="baseval"
            )
        )
        t = self.eng.register(
            WorkshopVariable(
                name="t",
                var_type="string",
                definition_type="variable_transformation",
                depends_on=[base.var_id],
            )
        )
        res = self.eng.evaluate(t.var_id)
        assert isinstance(res, dict)
        assert "value" in res

    def test_evaluate_circular(self):
        a = self.eng.register(
            WorkshopVariable(name="a", var_type="string", definition_type="static", value="1")
        )
        b = self.eng.register(
            WorkshopVariable(name="b", var_type="string", definition_type="static", value="2")
        )
        # 手动构造环：A→B→A（同时切换为 transformation 才会走依赖解析路径）
        self.eng._variables[a.var_id].definition_type = "variable_transformation"
        self.eng._variables[a.var_id].depends_on = [b.var_id]
        self.eng._variables[b.var_id].definition_type = "variable_transformation"
        self.eng._variables[b.var_id].depends_on = [a.var_id]
        with pytest.raises(WorkshopVariableError) as exc:
            self.eng.evaluate(a.var_id)
        assert exc.value.code == "CIRCULAR_DEPENDENCY"

    def test_resolve_dependencies(self):
        c = self.eng.register(
            WorkshopVariable(name="c", var_type="string", definition_type="static", value="1")
        )
        b = self.eng.register(
            WorkshopVariable(
                name="b",
                var_type="string",
                definition_type="variable_transformation",
                depends_on=[c.var_id],
            )
        )
        a = self.eng.register(
            WorkshopVariable(
                name="a",
                var_type="string",
                definition_type="variable_transformation",
                depends_on=[b.var_id],
            )
        )
        deps = self.eng.resolve_dependencies(a.var_id)
        assert deps == [b.var_id, c.var_id]

    def test_get_lineage(self):
        b = self.eng.register(
            WorkshopVariable(name="b", var_type="string", definition_type="static", value="1")
        )
        a = self.eng.register(
            WorkshopVariable(
                name="a",
                var_type="string",
                definition_type="variable_transformation",
                depends_on=[b.var_id],
            )
        )
        lin = self.eng.get_lineage(b.var_id)
        assert a.var_id in lin["downstream"]

    def test_record_event(self):
        out = self.eng.register(
            WorkshopVariable(name="v", var_type="string", definition_type="static")
        )
        ev = self.eng.record_event(out.var_id, "updated", {"k": "v"})
        assert ev.event_id.startswith("ve-")
        assert ev.var_id == out.var_id

    def test_list_events(self):
        a = self.eng.register(
            WorkshopVariable(name="a", var_type="string", definition_type="static")
        )
        b = self.eng.register(
            WorkshopVariable(name="b", var_type="string", definition_type="static")
        )
        self.eng.record_event(a.var_id, "updated", {})
        self.eng.record_event(b.var_id, "updated", {})
        self.eng.record_event(a.var_id, "updated", {})
        evs = self.eng.list_events(var_id=a.var_id)
        assert len(evs) == 2
        assert all(e.var_id == a.var_id for e in evs)

    def test_missing_name(self):
        with pytest.raises(WorkshopVariableError) as exc:
            self.eng.register(
                WorkshopVariable(name="", var_type="string", definition_type="static")
            )
        assert exc.value.code == "MISSING_NAME"

    def test_invalid_var_type(self):
        with pytest.raises(WorkshopVariableError) as exc:
            self.eng.register(
                WorkshopVariable(name="v", var_type="bad", definition_type="static")
            )
        assert exc.value.code == "INVALID_VAR_TYPE"

    def test_invalid_definition_type(self):
        with pytest.raises(WorkshopVariableError) as exc:
            self.eng.register(
                WorkshopVariable(name="v", var_type="string", definition_type="bad")
            )
        assert exc.value.code == "INVALID_DEFINITION_TYPE"

    def test_dependency_not_found(self):
        with pytest.raises(WorkshopVariableError) as exc:
            self.eng.register(
                WorkshopVariable(
                    name="t",
                    var_type="string",
                    definition_type="variable_transformation",
                    depends_on=["var-nonexist"],
                )
            )
        assert exc.value.code == "DEPENDENCY_NOT_FOUND"

    def test_not_found_get(self):
        with pytest.raises(WorkshopVariableError) as exc:
            self.eng.get("nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_evaluate(self):
        with pytest.raises(WorkshopVariableError) as exc:
            self.eng.evaluate("nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_max_variables_eviction(self):
        for i in range(_MAX_WORKSHOP_VARIABLES + 5):
            self.eng.register(
                WorkshopVariable(name=f"v{i}", var_type="string", definition_type="static")
            )
        assert len(self.eng._variables) == _MAX_WORKSHOP_VARIABLES


# ════════════════════════════════════════════════════════════════
# #151 ComputeJobPollingEngine
# ════════════════════════════════════════════════════════════════


class TestComputeJobPolling:
    """#151 · ComputeJobPollingEngine."""

    def setup_method(self):
        self.eng = ComputeJobPollingEngine()
        self.eng._jobs = {}

    def test_submit(self):
        job = self.eng.submit("m1", "fn", {"x": 1})
        assert job.job_id.startswith("job-")
        assert job.polling_token.startswith("pt-")
        assert job.status == "queued"

    def test_get(self):
        job = self.eng.submit("m1", "fn", {"x": 1})
        got = self.eng.get(job.job_id)
        assert got.module_id == "m1"
        assert got.function_name == "fn"

    def test_list(self):
        self.eng.submit("m1", "fn1")
        self.eng.submit("m1", "fn2")
        assert len(self.eng.list()) == 2

    def test_list_filter_module(self):
        self.eng.submit("m1", "fn1")
        self.eng.submit("m2", "fn2")
        items = self.eng.list(module_id="m1")
        assert len(items) == 1
        assert items[0].module_id == "m1"

    def test_list_filter_status(self):
        j1 = self.eng.submit("m1", "fn1")
        self.eng.submit("m1", "fn2")
        # j1 → running
        self.eng.poll(j1.job_id, j1.polling_token)
        running = self.eng.list(status="running")
        assert len(running) == 1
        assert running[0].status == "running"

    def test_poll_queued_to_running(self):
        job = self.eng.submit("m1", "fn")
        self.eng.poll(job.job_id, job.polling_token)
        got = self.eng.get(job.job_id)
        assert got.status == "running"
        assert got.started_at is not None

    def test_poll_running_to_succeeded(self):
        job = self.eng.submit("m1", "fn", {"x": 1})
        self.eng.poll(job.job_id, job.polling_token)  # queued → running
        self.eng.poll(job.job_id, job.polling_token)  # running → succeeded
        got = self.eng.get(job.job_id)
        assert got.status == "succeeded"
        assert got.finished_at is not None
        assert got.result  # 非空

    def test_poll_terminal_unchanged(self):
        job = self.eng.submit("m1", "fn")
        self.eng.poll(job.job_id, job.polling_token)  # running
        self.eng.poll(job.job_id, job.polling_token)  # succeeded
        self.eng.poll(job.job_id, job.polling_token)  # terminal 不变
        assert self.eng.get(job.job_id).status == "succeeded"

    def test_poll_count_increments(self):
        job = self.eng.submit("m1", "fn")
        self.eng.poll(job.job_id, job.polling_token)
        self.eng.poll(job.job_id, job.polling_token)
        assert self.eng.get(job.job_id).poll_count == 2

    def test_get_result_succeeded(self):
        job = self.eng.submit("m1", "fn", {"x": 1})
        self.eng.poll(job.job_id, job.polling_token)
        self.eng.poll(job.job_id, job.polling_token)
        res = self.eng.get_result(job.job_id)
        assert res.get("ok") is True

    def test_get_result_not_completed(self):
        job = self.eng.submit("m1", "fn")
        self.eng.poll(job.job_id, job.polling_token)  # running
        with pytest.raises(ComputeJobError) as exc:
            self.eng.get_result(job.job_id)
        assert exc.value.code == "JOB_NOT_COMPLETED"

    def test_cancel_queued(self):
        job = self.eng.submit("m1", "fn")
        self.eng.cancel(job.job_id)
        got = self.eng.get(job.job_id)
        assert got.status == "failed"
        assert got.error == "cancelled"

    def test_cancel_running(self):
        job = self.eng.submit("m1", "fn")
        self.eng.poll(job.job_id, job.polling_token)  # running
        self.eng.cancel(job.job_id)
        assert self.eng.get(job.job_id).status == "failed"

    def test_cancel_terminal(self):
        job = self.eng.submit("m1", "fn")
        self.eng.poll(job.job_id, job.polling_token)
        self.eng.poll(job.job_id, job.polling_token)  # succeeded
        with pytest.raises(ComputeJobError) as exc:
            self.eng.cancel(job.job_id)
        assert exc.value.code == "ALREADY_TERMINAL"

    def test_invalid_token(self):
        job = self.eng.submit("m1", "fn")
        with pytest.raises(ComputeJobError) as exc:
            self.eng.poll(job.job_id, "pt-wrong")
        assert exc.value.code == "INVALID_TOKEN"

    def test_check_timeouts(self):
        job = self.eng.submit("m1", "fn")
        self.eng.poll(job.job_id, job.polling_token)  # running, started_at=now
        # 手动模拟 started_at 很早，使其超时
        self.eng._jobs[job.job_id].started_at = datetime(2020, 1, 1)
        timed_out = self.eng.check_timeouts()
        assert any(j.job_id == job.job_id for j in timed_out)
        assert self.eng.get(job.job_id).status == "timeout"

    def test_missing_module(self):
        with pytest.raises(ComputeJobError) as exc:
            self.eng.submit("", "fn")
        assert exc.value.code == "MISSING_MODULE"

    def test_missing_function(self):
        with pytest.raises(ComputeJobError) as exc:
            self.eng.submit("m1", "")
        assert exc.value.code == "MISSING_FUNCTION"

    def test_not_found_get(self):
        with pytest.raises(ComputeJobError) as exc:
            self.eng.get("nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_poll(self):
        with pytest.raises(ComputeJobError) as exc:
            self.eng.poll("nonexist", "pt-x")
        assert exc.value.code == "NOT_FOUND"

    def test_max_jobs_eviction(self):
        for i in range(_MAX_COMPUTE_JOBS + 5):
            self.eng.submit("m1", f"fn{i}")
        assert len(self.eng._jobs) == _MAX_COMPUTE_JOBS


# ════════════════════════════════════════════════════════════════
# #152 AppEntryConventionEngine
# ════════════════════════════════════════════════════════════════


class TestAppEntryConvention:
    """#152 · AppEntryConventionEngine."""

    def setup_method(self):
        self.eng = AppEntryConventionEngine()
        self.eng._entries = {}

    def test_register(self):
        e = self.eng.register(AppEntry(module_id="m1", function_name="get_user"))
        assert e.entry_id.startswith("entry-")
        assert e.endpoint_path  # 非空

    def test_endpoint_derivation(self):
        e = self.eng.register(AppEntry(module_id="m1", function_name="get_user_data"))
        assert e.endpoint_path == "/get/user/data"

    def test_get(self):
        e = self.eng.register(AppEntry(module_id="m1", function_name="get_user"))
        got = self.eng.get(e.entry_id)
        assert got.function_name == "get_user"

    def test_list(self):
        self.eng.register(AppEntry(module_id="m1", function_name="fn1"))
        self.eng.register(AppEntry(module_id="m1", function_name="fn2"))
        assert len(self.eng.list()) == 2

    def test_list_filter_module(self):
        self.eng.register(AppEntry(module_id="m1", function_name="fn1"))
        self.eng.register(AppEntry(module_id="m2", function_name="fn2"))
        items = self.eng.list(module_id="m1")
        assert len(items) == 1
        assert items[0].module_id == "m1"

    def test_list_filter_status(self):
        self.eng.register(
            AppEntry(module_id="m1", function_name="good", relative_imports=[".h"], return_type="dict")
        )
        self.eng.register(
            AppEntry(module_id="m1", function_name="bad", relative_imports=["os"], return_type="DataFrame")
        )
        valids = self.eng.list(status="valid")
        assert len(valids) == 1
        assert valids[0].status == "valid"

    def test_validate_valid(self):
        e = self.eng.register(
            AppEntry(
                module_id="m1",
                function_name="fn",
                relative_imports=[".helper"],
                return_type="dict",
            )
        )
        assert e.status == "valid"
        assert e.validation_errors == []

    def test_validate_invalid_import(self):
        e = self.eng.register(
            AppEntry(
                module_id="m1",
                function_name="fn",
                relative_imports=["os"],
                return_type="dict",
            )
        )
        assert e.status == "invalid"
        assert e.validation_errors  # 非空

    def test_validate_invalid_return_type(self):
        e = self.eng.register(
            AppEntry(
                module_id="m1",
                function_name="fn",
                relative_imports=[".helper"],
                return_type="DataFrame",
            )
        )
        assert e.status == "invalid"
        assert e.json_serializable is False

    def test_list_invalid(self):
        self.eng.register(
            AppEntry(module_id="m1", function_name="good", relative_imports=[".h"], return_type="dict")
        )
        self.eng.register(
            AppEntry(module_id="m1", function_name="bad", relative_imports=["os"], return_type="DataFrame")
        )
        invalids = self.eng.list_invalid()
        assert len(invalids) == 1
        assert invalids[0].status == "invalid"

    def test_update(self):
        e = self.eng.register(AppEntry(module_id="m1", function_name="get_user"))
        self.eng.update(e.entry_id, {"function_name": "get_order"})
        got = self.eng.get(e.entry_id)
        assert got.function_name == "get_order"

    def test_delete(self):
        e = self.eng.register(AppEntry(module_id="m1", function_name="get_user"))
        self.eng.delete(e.entry_id)
        with pytest.raises(AppEntryError) as exc:
            self.eng.get(e.entry_id)
        assert exc.value.code == "NOT_FOUND"

    def test_get_endpoint(self):
        e = self.eng.register(AppEntry(module_id="m1", function_name="get_user"))
        assert self.eng.get_endpoint(e.entry_id) == e.endpoint_path

    def test_missing_module(self):
        with pytest.raises(AppEntryError) as exc:
            self.eng.register(AppEntry(module_id="", function_name="fn"))
        assert exc.value.code == "MISSING_MODULE"

    def test_missing_function(self):
        with pytest.raises(AppEntryError) as exc:
            self.eng.register(AppEntry(module_id="m1", function_name=""))
        assert exc.value.code == "MISSING_FUNCTION"

    def test_not_found_get(self):
        with pytest.raises(AppEntryError) as exc:
            self.eng.get("nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_validate(self):
        with pytest.raises(AppEntryError) as exc:
            self.eng.validate("nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_max_entries_eviction(self):
        for i in range(_MAX_APP_ENTRIES + 5):
            self.eng.register(AppEntry(module_id="m1", function_name=f"fn{i}"))
        assert len(self.eng._entries) == _MAX_APP_ENTRIES


# ════════════════════════════════════════════════════════════════
# 单例工厂
# ════════════════════════════════════════════════════════════════


class TestSingletons:
    """三个引擎的单例工厂应返回同一实例。"""

    def test_workshop_variable_singleton(self):
        assert get_workshop_variable_engine() is get_workshop_variable_engine()

    def test_compute_job_singleton(self):
        assert get_compute_job_polling_engine() is get_compute_job_polling_engine()

    def test_app_entry_singleton(self):
        assert get_app_entry_convention_engine() is get_app_entry_convention_engine()

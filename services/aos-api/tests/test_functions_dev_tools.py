"""W2-AO · Functions Dev Tools 组测试（#143 / #144 / #146）.

覆盖 FunctionsTestDebugEngine / ExternalApiCallEngine / DatasetPreviewTabsEngine 三引擎。
"""
from __future__ import annotations

import pytest

from aos_api.functions_dev_tools import (
    # 模型
    CallResult,
    ComparisonTab,
    DatasetPreviewTabs,
    DatasetPreviewTabsEngine,
    DatasetPreviewTabsError,
    ExternalApiCall,
    ExternalApiCallEngine,
    ExternalApiCallError,
    FunctionDebugSession,
    FunctionTestCase,
    FunctionsTestDebugEngine,
    FunctionsTestDebugError,
    HealthTab,
    HistoryTab,
    ProfileResult,
    StreamViewTab,
    # getter
    get_dataset_preview_tabs_engine,
    get_external_api_call_engine,
    get_functions_test_debug_engine,
)


# ════════════════════ FunctionsTestDebugEngine ════════════════════

class TestFunctionsTestDebug:
    def setup_method(self) -> None:
        self.eng = FunctionsTestDebugEngine()
        self.eng._tests = {}
        self.eng._sessions = {}
        self.eng._profiles = {}

    def test_register_test(self) -> None:
        case = self.eng.register_test(
            FunctionTestCase(
                function_id="fn-1",
                test_name="basic",
                test_code="assert 1 == 1",
            )
        )
        assert case.case_id.startswith("ftc-")
        assert case.function_id == "fn-1"
        assert case.test_name == "basic"
        assert case.status == "pending"
        assert case.created_at is not None

    def test_get_test(self) -> None:
        case = self.eng.register_test(
            FunctionTestCase(
                function_id="fn-1",
                test_name="basic",
                test_code="assert 1 == 1",
            )
        )
        fetched = self.eng.get_test(case.case_id)
        assert fetched.case_id == case.case_id
        assert fetched.function_id == "fn-1"
        assert fetched.test_code == "assert 1 == 1"

    def test_list_tests(self) -> None:
        self.eng.register_test(
            FunctionTestCase(function_id="fn-1", test_name="t1", test_code="assert 1")
        )
        self.eng.register_test(
            FunctionTestCase(function_id="fn-2", test_name="t2", test_code="assert 2")
        )
        assert len(self.eng.list_tests()) == 2
        only_fn1 = self.eng.list_tests(function_id="fn-1")
        assert len(only_fn1) == 1
        assert only_fn1[0].function_id == "fn-1"

    def test_list_tests_filter_status(self) -> None:
        case = self.eng.register_test(
            FunctionTestCase(function_id="fn-1", test_name="t1", test_code="assert 1 == 1")
        )
        self.eng.run_test(case.case_id)
        passed = self.eng.list_tests(status="passed")
        failed = self.eng.list_tests(status="failed")
        assert len(passed) == 1
        assert len(failed) == 0
        assert passed[0].status == "passed"

    def test_run_test_python_pass(self) -> None:
        case = self.eng.register_test(
            FunctionTestCase(
                function_id="fn-1", test_name="pass", test_code="assert 1 == 1"
            )
        )
        run = self.eng.run_test(case.case_id)
        assert run.status == "passed"

    def test_run_test_python_fail(self) -> None:
        case = self.eng.register_test(
            FunctionTestCase(
                function_id="fn-1", test_name="fail", test_code="assert fail"
            )
        )
        run = self.eng.run_test(case.case_id)
        assert run.status == "failed"

    def test_run_test_typescript(self) -> None:
        case = self.eng.register_test(
            FunctionTestCase(
                function_id="fn-1",
                test_name="ts",
                language="typescript",
                test_code="whatever",
            )
        )
        run = self.eng.run_test(case.case_id)
        assert run.status == "passed"

    def test_register_debug(self) -> None:
        sess = self.eng.register_debug(
            function_id="fn-1",
            inputs={"x": 1},
            breakpoints=[2, 5],
        )
        assert sess.session_id.startswith("fds-")
        assert sess.function_id == "fn-1"
        assert sess.state == "created"
        assert sess.breakpoints == [2, 5]
        assert sess.inputs == {"x": 1}

    def test_get_debug_session(self) -> None:
        sess = self.eng.register_debug("fn-1", {"x": 1}, [])
        fetched = self.eng.get_debug_session(sess.session_id)
        assert fetched.session_id == sess.session_id
        assert fetched.function_id == "fn-1"

    def test_start_debug(self) -> None:
        sess = self.eng.register_debug("fn-1", {}, [])
        started = self.eng.start_debug(sess.session_id)
        assert started.state == "running"

    def test_start_debug_already_started(self) -> None:
        sess = self.eng.register_debug("fn-1", {}, [])
        self.eng.start_debug(sess.session_id)
        with pytest.raises(FunctionsTestDebugError) as exc:
            self.eng.start_debug(sess.session_id)
        assert exc.value.code == "ALREADY_STARTED"

    def test_step(self) -> None:
        sess = self.eng.register_debug("fn-1", {}, [])
        self.eng.start_debug(sess.session_id)
        stepped = self.eng.step(sess.session_id)
        assert stepped.current_line == 1
        assert stepped.state == "running"

    def test_step_breakpoint(self) -> None:
        sess = self.eng.register_debug("fn-1", {}, [2])
        self.eng.start_debug(sess.session_id)
        self.eng.step(sess.session_id)  # current_line=1, running
        stepped = self.eng.step(sess.session_id)  # current_line=2, paused
        assert stepped.current_line == 2
        assert stepped.state == "paused"

    def test_step_completion(self) -> None:
        sess = self.eng.register_debug("fn-1", {}, [])
        self.eng.start_debug(sess.session_id)
        last = None
        for _ in range(10):
            last = self.eng.step(sess.session_id)
        assert last is not None
        assert last.state == "completed"

    def test_step_invalid_state(self) -> None:
        sess = self.eng.register_debug("fn-1", {}, [])
        with pytest.raises(FunctionsTestDebugError) as exc:
            self.eng.step(sess.session_id)
        assert exc.value.code == "INVALID_STATE"

    def test_profile(self) -> None:
        result = self.eng.profile(function_id="fn-1", inputs={"x": 1})
        assert result.profile_id.startswith("fpr-")
        assert result.function_id == "fn-1"
        assert result.duration_ms > 0
        assert isinstance(result.hotspots, list)

    def test_list_profiles(self) -> None:
        self.eng.profile("fn-1", {"x": 1})
        self.eng.profile("fn-1", {"x": 2})
        items = self.eng.list_profiles("fn-1")
        assert len(items) == 2

    def test_missing_function_register_test(self) -> None:
        with pytest.raises(FunctionsTestDebugError) as exc:
            self.eng.register_test(
                FunctionTestCase(function_id="", test_name="t", test_code="assert 1")
            )
        assert exc.value.code == "MISSING_FUNCTION"

    def test_missing_name_register_test(self) -> None:
        with pytest.raises(FunctionsTestDebugError) as exc:
            self.eng.register_test(
                FunctionTestCase(
                    function_id="fn-1", test_name="", test_code="assert 1"
                )
            )
        assert exc.value.code == "MISSING_NAME"

    def test_invalid_language(self) -> None:
        with pytest.raises(FunctionsTestDebugError) as exc:
            self.eng.register_test(
                FunctionTestCase(
                    function_id="fn-1",
                    test_name="t",
                    language="rust",
                    test_code="assert 1",
                )
            )
        assert exc.value.code == "INVALID_LANGUAGE"

    def test_not_found_get_test(self) -> None:
        with pytest.raises(FunctionsTestDebugError) as exc:
            self.eng.get_test("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_run_test(self) -> None:
        with pytest.raises(FunctionsTestDebugError) as exc:
            self.eng.run_test("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_get_debug(self) -> None:
        with pytest.raises(FunctionsTestDebugError) as exc:
            self.eng.get_debug_session("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_start_debug(self) -> None:
        with pytest.raises(FunctionsTestDebugError) as exc:
            self.eng.start_debug("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_step(self) -> None:
        with pytest.raises(FunctionsTestDebugError) as exc:
            self.eng.step("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_missing_function_profile(self) -> None:
        with pytest.raises(FunctionsTestDebugError) as exc:
            self.eng.profile(function_id="", inputs={})
        assert exc.value.code == "MISSING_FUNCTION"

    def test_max_test_cases_eviction(self) -> None:
        from aos_api.functions_dev_tools import _MAX_TEST_CASES
        for i in range(_MAX_TEST_CASES + 5):
            self.eng.register_test(
                FunctionTestCase(
                    function_id=f"fn-{i}",
                    test_name=f"t-{i}",
                    test_code="assert 1",
                )
            )
        assert len(self.eng._tests) == _MAX_TEST_CASES


# ════════════════════ ExternalApiCallEngine ════════════════════

class TestExternalApiCall:
    def setup_method(self) -> None:
        self.eng = ExternalApiCallEngine()
        self.eng._calls = {}
        self.eng._results = {}

    def test_register(self) -> None:
        call = self.eng.register(
            ExternalApiCall(name="n", endpoint_url="http://x")
        )
        assert call.call_id.startswith("eac-")
        assert call.name == "n"
        assert call.endpoint_url == "http://x"
        assert call.status == "active"
        assert call.created_at is not None

    def test_get(self) -> None:
        call = self.eng.register(
            ExternalApiCall(name="n", endpoint_url="http://x")
        )
        fetched = self.eng.get(call.call_id)
        assert fetched.call_id == call.call_id
        assert fetched.name == "n"

    def test_list(self) -> None:
        self.eng.register(ExternalApiCall(name="n1", endpoint_url="http://x1"))
        self.eng.register(ExternalApiCall(name="n2", endpoint_url="http://x2"))
        assert len(self.eng.list()) == 2

    def test_list_filter_language(self) -> None:
        self.eng.register(
            ExternalApiCall(name="n1", language="typescript", endpoint_url="http://x1")
        )
        self.eng.register(
            ExternalApiCall(name="n2", language="python", endpoint_url="http://x2")
        )
        items = self.eng.list(language="python")
        assert len(items) == 1
        assert items[0].language == "python"

    def test_list_filter_status(self) -> None:
        call = self.eng.register(ExternalApiCall(name="n1", endpoint_url="http://x1"))
        self.eng.disable(call.call_id)
        inactive = self.eng.list(status="inactive")
        active = self.eng.list(status="active")
        assert len(inactive) == 1
        assert len(active) == 0
        assert inactive[0].status == "inactive"

    def test_update(self) -> None:
        call = self.eng.register(ExternalApiCall(name="n", endpoint_url="http://x"))
        updated = self.eng.update(call.call_id, {"method": "POST"})
        assert updated.method == "POST"
        assert updated.updated_at is not None

    def test_update_invalid_method(self) -> None:
        call = self.eng.register(ExternalApiCall(name="n", endpoint_url="http://x"))
        with pytest.raises(ExternalApiCallError) as exc:
            self.eng.update(call.call_id, {"method": "INVALID"})
        assert exc.value.code == "INVALID_METHOD"

    def test_delete(self) -> None:
        call = self.eng.register(ExternalApiCall(name="n", endpoint_url="http://x"))
        self.eng.delete(call.call_id)
        with pytest.raises(ExternalApiCallError) as exc:
            self.eng.get(call.call_id)
        assert exc.value.code == "NOT_FOUND"

    def test_execute(self) -> None:
        call = self.eng.register(ExternalApiCall(name="n", endpoint_url="http://x"))
        result = self.eng.execute(call.call_id, payload={"k": "v"})
        assert result.result_id.startswith("cr-")
        assert result.call_id == call.call_id
        assert result.status == "success"
        assert result.status_code == 200
        assert "ok" in result.response_body
        assert result.duration_ms > 0
        assert result.executed_at is not None

    def test_list_results(self) -> None:
        call = self.eng.register(ExternalApiCall(name="n", endpoint_url="http://x"))
        self.eng.execute(call.call_id, {"a": 1})
        self.eng.execute(call.call_id, {"b": 2})
        items = self.eng.list_results(call.call_id)
        assert len(items) == 2

    def test_enable(self) -> None:
        call = self.eng.register(ExternalApiCall(name="n", endpoint_url="http://x"))
        self.eng.disable(call.call_id)
        enabled = self.eng.enable(call.call_id)
        assert enabled.status == "active"

    def test_disable(self) -> None:
        call = self.eng.register(ExternalApiCall(name="n", endpoint_url="http://x"))
        disabled = self.eng.disable(call.call_id)
        assert disabled.status == "inactive"

    def test_missing_name(self) -> None:
        with pytest.raises(ExternalApiCallError) as exc:
            self.eng.register(ExternalApiCall(name="", endpoint_url="http://x"))
        assert exc.value.code == "MISSING_NAME"

    def test_missing_url(self) -> None:
        with pytest.raises(ExternalApiCallError) as exc:
            self.eng.register(ExternalApiCall(name="n", endpoint_url=""))
        assert exc.value.code == "MISSING_URL"

    def test_invalid_language(self) -> None:
        with pytest.raises(ExternalApiCallError) as exc:
            self.eng.register(
                ExternalApiCall(name="n", language="rust", endpoint_url="http://x")
            )
        assert exc.value.code == "INVALID_LANGUAGE"

    def test_invalid_method(self) -> None:
        with pytest.raises(ExternalApiCallError) as exc:
            self.eng.register(
                ExternalApiCall(name="n", method="HEAD", endpoint_url="http://x")
            )
        assert exc.value.code == "INVALID_METHOD"

    def test_invalid_auth_type(self) -> None:
        with pytest.raises(ExternalApiCallError) as exc:
            self.eng.register(
                ExternalApiCall(
                    name="n", auth_type="oauth", endpoint_url="http://x"
                )
            )
        assert exc.value.code == "INVALID_AUTH_TYPE"

    def test_not_found_get(self) -> None:
        with pytest.raises(ExternalApiCallError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_update(self) -> None:
        with pytest.raises(ExternalApiCallError) as exc:
            self.eng.update("nonexistent", {})
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_delete(self) -> None:
        with pytest.raises(ExternalApiCallError) as exc:
            self.eng.delete("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_execute(self) -> None:
        with pytest.raises(ExternalApiCallError) as exc:
            self.eng.execute("nonexistent", {})
        assert exc.value.code == "NOT_FOUND"

    def test_max_calls_eviction(self) -> None:
        from aos_api.functions_dev_tools import _MAX_EXTERNAL_CALLS
        for i in range(_MAX_EXTERNAL_CALLS + 5):
            self.eng.register(
                ExternalApiCall(name=f"n-{i}", endpoint_url=f"http://x-{i}")
            )
        assert len(self.eng._calls) == _MAX_EXTERNAL_CALLS


# ════════════════════ DatasetPreviewTabsEngine ════════════════════

class TestDatasetPreviewTabs:
    def setup_method(self) -> None:
        self.eng = DatasetPreviewTabsEngine()
        self.eng._tabs = {}
        self.eng._dataset_index = {}

    def test_register(self) -> None:
        tabs = self.eng.register("ds-1")
        assert tabs.tabs_id.startswith("dpt-")
        assert tabs.dataset_rid == "ds-1"
        assert tabs.created_at is not None
        # 默认 4 Tab 子模型
        assert isinstance(tabs.history_tab, HistoryTab)
        assert isinstance(tabs.health_tab, HealthTab)
        assert isinstance(tabs.comparison_tab, ComparisonTab)
        assert isinstance(tabs.stream_view_tab, StreamViewTab)
        # 默认值
        assert tabs.history_tab.enabled is True
        assert tabs.health_tab.enabled is True
        assert tabs.comparison_tab.enabled is False
        assert tabs.stream_view_tab.enabled is False

    def test_register_idempotent(self) -> None:
        t1 = self.eng.register("ds-1")
        t2 = self.eng.register("ds-1")
        assert t1.tabs_id == t2.tabs_id
        assert len(self.eng._tabs) == 1

    def test_get(self) -> None:
        tabs = self.eng.register("ds-1")
        fetched = self.eng.get(tabs.tabs_id)
        assert fetched.tabs_id == tabs.tabs_id
        assert fetched.dataset_rid == "ds-1"

    def test_get_by_dataset(self) -> None:
        self.eng.register("ds-1")
        self.eng.register("ds-2")
        fetched = self.eng.get_by_dataset("ds-1")
        assert fetched.dataset_rid == "ds-1"

    def test_list(self) -> None:
        self.eng.register("ds-1")
        self.eng.register("ds-2")
        assert len(self.eng.list()) == 2

    def test_list_filter_dataset(self) -> None:
        self.eng.register("ds-1")
        self.eng.register("ds-2")
        items = self.eng.list(dataset_rid="ds-1")
        assert len(items) == 1
        assert items[0].dataset_rid == "ds-1"

    def test_enable_tab(self) -> None:
        self.eng.register("ds-1")
        updated = self.eng.enable_tab("ds-1", "comparison")
        assert updated.comparison_tab.enabled is True

    def test_disable_tab(self) -> None:
        self.eng.register("ds-1")
        updated = self.eng.disable_tab("ds-1", "history")
        assert updated.history_tab.enabled is False

    def test_enable_tab_invalid_name(self) -> None:
        self.eng.register("ds-1")
        with pytest.raises(DatasetPreviewTabsError) as exc:
            self.eng.enable_tab("ds-1", "invalid")
        assert exc.value.code == "INVALID_TAB_NAME"

    def test_update_history_tab(self) -> None:
        self.eng.register("ds-1")
        updated = self.eng.update_history_tab("ds-1", 20, True)
        assert updated.history_tab.last_n_versions == 20
        assert updated.history_tab.snapshot_diff is True
        assert updated.updated_at is not None

    def test_update_health_tab(self) -> None:
        self.eng.register("ds-1")
        updated = self.eng.update_health_tab(
            "ds-1", "warning", {"total": 5, "passed": 3, "failed": 1, "warning": 1}
        )
        assert updated.health_tab.overall_status == "warning"
        assert updated.health_tab.checks_summary["total"] == 5
        assert updated.updated_at is not None

    def test_update_health_tab_invalid_status(self) -> None:
        self.eng.register("ds-1")
        with pytest.raises(DatasetPreviewTabsError) as exc:
            self.eng.update_health_tab("ds-1", "bad", {})
        assert exc.value.code == "INVALID_HEALTH_STATUS"

    def test_update_comparison_tab(self) -> None:
        self.eng.register("ds-1")
        updated = self.eng.update_comparison_tab("ds-1", "ds-baseline", "content")
        assert updated.comparison_tab.baseline_dataset_rid == "ds-baseline"
        assert updated.comparison_tab.compare_mode == "content"
        assert updated.updated_at is not None

    def test_update_comparison_tab_invalid_mode(self) -> None:
        self.eng.register("ds-1")
        with pytest.raises(DatasetPreviewTabsError) as exc:
            self.eng.update_comparison_tab("ds-1", "", "bad")
        assert exc.value.code == "INVALID_COMPARE_MODE"

    def test_update_stream_view_tab(self) -> None:
        self.eng.register("ds-1")
        updated = self.eng.update_stream_view_tab(
            "ds-1", "kafka", 3, 100, "running"
        )
        assert updated.stream_view_tab.stream_type == "kafka"
        assert updated.stream_view_tab.partition == 3
        assert updated.stream_view_tab.offset == 100
        assert updated.stream_view_tab.status == "running"
        assert updated.updated_at is not None

    def test_update_stream_view_tab_invalid_type(self) -> None:
        self.eng.register("ds-1")
        with pytest.raises(DatasetPreviewTabsError) as exc:
            self.eng.update_stream_view_tab("ds-1", "bad", 0, 0, "stopped")
        assert exc.value.code == "INVALID_STREAM_TYPE"

    def test_update_stream_view_tab_invalid_status(self) -> None:
        self.eng.register("ds-1")
        with pytest.raises(DatasetPreviewTabsError) as exc:
            self.eng.update_stream_view_tab("ds-1", "kafka", 0, 0, "bad")
        assert exc.value.code == "INVALID_STREAM_STATUS"

    def test_missing_dataset_register(self) -> None:
        with pytest.raises(DatasetPreviewTabsError) as exc:
            self.eng.register("")
        assert exc.value.code == "MISSING_DATASET"

    def test_missing_dataset_get_by_dataset(self) -> None:
        with pytest.raises(DatasetPreviewTabsError) as exc:
            self.eng.get_by_dataset("")
        assert exc.value.code == "MISSING_DATASET"

    def test_not_found_get(self) -> None:
        with pytest.raises(DatasetPreviewTabsError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_get_by_dataset(self) -> None:
        with pytest.raises(DatasetPreviewTabsError) as exc:
            self.eng.get_by_dataset("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_enable_tab(self) -> None:
        with pytest.raises(DatasetPreviewTabsError) as exc:
            self.eng.enable_tab("nonexistent", "history")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_update_history(self) -> None:
        with pytest.raises(DatasetPreviewTabsError) as exc:
            self.eng.update_history_tab("nonexistent", 10, False)
        assert exc.value.code == "NOT_FOUND"

    def test_max_tabs_eviction(self) -> None:
        from aos_api.functions_dev_tools import _MAX_PREVIEW_TABS
        for i in range(_MAX_PREVIEW_TABS + 5):
            self.eng.register(f"ds-{i}")
        assert len(self.eng._tabs) == _MAX_PREVIEW_TABS


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_functions_test_debug_singleton(self) -> None:
        a = get_functions_test_debug_engine()
        b = get_functions_test_debug_engine()
        assert a is b

    def test_external_api_call_singleton(self) -> None:
        a = get_external_api_call_engine()
        b = get_external_api_call_engine()
        assert a is b

    def test_dataset_preview_tabs_singleton(self) -> None:
        a = get_dataset_preview_tabs_engine()
        b = get_dataset_preview_tabs_engine()
        assert a is b

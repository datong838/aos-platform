"""W2-AD · 开发者工具组测试（#104 / #105 / #106）.

覆盖 PythonDebuggerEngine / UnitTestEngine / ArtifactRegistryEngine 三引擎。
对齐 docs/palantier/20_tech/220tech_w2-ad-dev-tooling.md §6 测试计划。
"""
from __future__ import annotations

import pytest

from aos_api.dev_tooling import (
    Artifact,
    ArtifactRegistryEngine,
    DevToolingError,
    PythonDebuggerEngine,
    TestCase,
    TestResult,
    UnitTestEngine,
    get_artifact_engine,
    get_debugger_engine,
    get_unittest_engine,
    _MAX_SESSIONS,
    _MAX_RESULTS,
    _MAX_ARTIFACTS,
)


# ════════════════════ PythonDebuggerEngine ════════════════════

class TestPythonDebugger:
    def setup_method(self) -> None:
        self.eng = PythonDebuggerEngine()

    def test_create_session(self) -> None:
        s = self.eng.create_session("x = 1\ny = 2\n")
        assert s.id.startswith("dbg-")
        assert s.state == "created"
        assert s.current_line == 0

    def test_create_session_missing_code(self) -> None:
        with pytest.raises(DevToolingError) as exc:
            self.eng.create_session("")
        assert exc.value.code == "MISSING_CODE"

    def test_get_not_found(self) -> None:
        with pytest.raises(DevToolingError) as exc:
            self.eng.get_session("missing")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.create_session("x = 1\n")
        self.eng.create_session("y = 2\n")
        assert len(self.eng.list_sessions()) == 2

    def test_list_filter_by_state(self) -> None:
        s1 = self.eng.create_session("x = 1\ny = 2\n")
        s2 = self.eng.create_session("y = 2\n")
        self.eng.step(s1.id)  # s1 → paused（2 行代码，step 后仍 paused）
        items = self.eng.list_sessions(state="paused")
        assert len(items) == 1
        assert items[0].id == s1.id

    def test_step_advances_line(self) -> None:
        s = self.eng.create_session("x = 1\ny = 2\n")
        step = self.eng.step(s.id)
        assert step.line == 1
        assert s.current_line == 1
        assert s.state == "paused"
        assert "x" in s.variables

    def test_step_hits_breakpoint(self) -> None:
        # 断点设在第 2 行；3 行代码，step 第二行后仍 paused（非末行）
        s = self.eng.create_session("x = 1\ny = 2\nz = 3\n", breakpoints=[2])
        self.eng.step(s.id)  # 执行第1行
        step2 = self.eng.step(s.id)  # 执行第2行
        assert step2.is_breakpoint is True
        assert s.state == "paused"

    def test_step_completed(self) -> None:
        s = self.eng.create_session("x = 1\n")
        self.eng.step(s.id)  # 执行唯一一行 → completed
        with pytest.raises(DevToolingError) as exc:
            self.eng.step(s.id)
        assert exc.value.code == "SESSION_COMPLETED"

    def test_run_to_completion(self) -> None:
        s = self.eng.create_session("a = 1\nb = 2\nc = a + b\n")
        result = self.eng.run_to_completion(s.id)
        assert result.state == "completed"
        assert result.current_line == 3

    def test_run_to_completion_hits_breakpoint(self) -> None:
        # 断点在第 3 行；run 应执行 1-2 行后在到达第 3 行前暂停
        s = self.eng.create_session("a = 1\nb = 2\nc = a + b\n", breakpoints=[3])
        result = self.eng.run_to_completion(s.id)
        assert result.state == "paused"
        assert result.current_line == 2  # 执行完第2行，暂停在第3行前

    def test_get_variables(self) -> None:
        s = self.eng.create_session("x = 42\n")
        self.eng.step(s.id)
        variables = self.eng.get_variables(s.id)
        assert variables.get("x") == 42

    def test_step_error(self) -> None:
        s = self.eng.create_session("raise ValueError('boom')\n")
        with pytest.raises(DevToolingError) as exc:
            self.eng.step(s.id)
        assert exc.value.code == "STEP_ERROR"
        assert s.state == "error"

    def test_delete_session(self) -> None:
        s = self.eng.create_session("x = 1\n")
        assert self.eng.delete_session(s.id) is True
        assert self.eng.delete_session(s.id) is False

    def test_sessions_cap_eviction(self) -> None:
        for _ in range(_MAX_SESSIONS + 10):
            self.eng.create_session("x = 1\n")
        assert len(self.eng._sessions) == _MAX_SESSIONS


# ════════════════════ UnitTestEngine ════════════════════

class TestUnitTestEngine:
    def setup_method(self) -> None:
        self.eng = UnitTestEngine()

    def _mk(self, **kw: object) -> TestCase:
        defaults: dict[str, object] = {
            "name": "test-1",
            "language": "python",
            "code": "assert 1 + 1 == 2\n",
        }
        defaults.update(kw)
        return TestCase(**defaults)

    def test_register(self) -> None:
        c = self.eng.register(self._mk())
        assert c.id.startswith("tc-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(DevToolingError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_invalid_language(self) -> None:
        with pytest.raises(DevToolingError) as exc:
            self.eng.register(self._mk(language="rust"))
        assert exc.value.code == "INVALID_LANGUAGE"

    def test_get_not_found(self) -> None:
        with pytest.raises(DevToolingError) as exc:
            self.eng.get("missing")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(name="t1"))
        self.eng.register(self._mk(name="t2"))
        assert len(self.eng.list()) == 2

    def test_list_filter_by_language(self) -> None:
        self.eng.register(self._mk(name="t1", language="python"))
        self.eng.register(self._mk(name="t2", language="java", code="class T {}"))
        items = self.eng.list(language="java")
        assert len(items) == 1
        assert items[0].language == "java"

    def test_update(self) -> None:
        c = self.eng.register(self._mk(name="old"))
        out = self.eng.update(c.id, {"name": "new", "target_function": "foo"})
        assert out.name == "new"
        assert out.target_function == "foo"

    def test_delete(self) -> None:
        c = self.eng.register(self._mk())
        assert self.eng.delete(c.id) is True
        assert self.eng.delete(c.id) is False

    def test_run_python_passed(self) -> None:
        c = self.eng.register(self._mk(code="assert 1 + 1 == 2\n"))
        r = self.eng.run(c.id)
        assert r.status == "passed"

    def test_run_python_failed(self) -> None:
        c = self.eng.register(self._mk(code="assert 1 + 1 == 3\n"))
        r = self.eng.run(c.id)
        assert r.status == "failed"
        assert r.error_message  # 非空

    def test_run_python_error(self) -> None:
        c = self.eng.register(self._mk(code="raise RuntimeError('boom')\n"))
        r = self.eng.run(c.id)
        assert r.status == "error"
        assert "boom" in r.error_message

    def test_run_java_simulated(self) -> None:
        c = self.eng.register(self._mk(
            name="java-test", language="java", code="class T { void test() {} }",
        ))
        r = self.eng.run(c.id)
        assert r.status == "passed"
        assert "simulated" in r.output

    def test_list_results(self) -> None:
        c = self.eng.register(self._mk())
        self.eng.run(c.id)
        self.eng.run(c.id)
        items = self.eng.list_results(case_id=c.id)
        assert len(items) == 2
        assert all(r.case_id == c.id for r in items)

    def test_results_cap_eviction(self) -> None:
        c = self.eng.register(self._mk())
        for _ in range(_MAX_RESULTS + 10):
            self.eng.run(c.id)
        assert len(self.eng._results) == _MAX_RESULTS


# ════════════════════ ArtifactRegistryEngine ════════════════════

class TestArtifactRegistry:
    def setup_method(self) -> None:
        self.eng = ArtifactRegistryEngine()

    def _mk(self, **kw: object) -> Artifact:
        defaults: dict[str, object] = {
            "name": "my-pkg",
            "version": "1.0.0",
            "format": "conda",
        }
        defaults.update(kw)
        return Artifact(**defaults)

    def test_register(self) -> None:
        a = self.eng.register(self._mk())
        assert a.id.startswith("art-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(DevToolingError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_invalid_format(self) -> None:
        with pytest.raises(DevToolingError) as exc:
            self.eng.register(self._mk(format="rpm"))
        assert exc.value.code == "INVALID_FORMAT"

    def test_register_name_version_duplicate(self) -> None:
        self.eng.register(self._mk(name="pkg", version="1.0.0"))
        with pytest.raises(DevToolingError) as exc:
            self.eng.register(self._mk(name="pkg", version="1.0.0"))
        assert exc.value.code == "NAME_VERSION_DUPLICATE"

    def test_get_not_found(self) -> None:
        with pytest.raises(DevToolingError) as exc:
            self.eng.get("missing")
        assert exc.value.code == "NOT_FOUND"

    def test_get_by_name_version(self) -> None:
        a = self.eng.register(self._mk(name="pkg", version="1.0.0"))
        found = self.eng.get_by_name_version("pkg", "1.0.0")
        assert found is not None
        assert found.id == a.id
        assert self.eng.get_by_name_version("pkg", "2.0.0") is None

    def test_list_default(self) -> None:
        self.eng.register(self._mk(name="p1", version="1.0.0"))
        self.eng.register(self._mk(name="p2", version="1.0.0"))
        assert len(self.eng.list()) == 2

    def test_list_filter_by_format(self) -> None:
        self.eng.register(self._mk(name="p1", version="1.0.0", format="conda"))
        self.eng.register(self._mk(name="p2", version="1.0.0", format="docker"))
        items = self.eng.list(format="docker")
        assert len(items) == 1
        assert items[0].format == "docker"

    def test_list_filter_by_tag(self) -> None:
        self.eng.register(self._mk(name="p1", version="1.0.0", tags=["latest"]))
        self.eng.register(self._mk(name="p2", version="1.0.0", tags=["stable"]))
        items = self.eng.list(tag="stable")
        assert len(items) == 1
        assert "stable" in items[0].tags

    def test_update(self) -> None:
        a = self.eng.register(self._mk(name="p1", version="1.0.0"))
        out = self.eng.update(a.id, {"description": "updated", "size_bytes": 1024})
        assert out.description == "updated"
        assert out.size_bytes == 1024

    def test_delete(self) -> None:
        a = self.eng.register(self._mk(name="p1", version="1.0.0"))
        assert self.eng.delete(a.id) is True
        assert self.eng.delete(a.id) is False

    def test_list_versions(self) -> None:
        self.eng.register(self._mk(name="pkg", version="1.0.0"))
        self.eng.register(self._mk(name="pkg", version="2.0.0"))
        self.eng.register(self._mk(name="other", version="1.0.0"))
        versions = self.eng.list_versions("pkg")
        assert len(versions) == 2
        assert all(v.name == "pkg" for v in versions)

    def test_list_dependencies(self) -> None:
        dep = self.eng.register(self._mk(name="dep", version="1.0.0"))
        main = self.eng.register(self._mk(
            name="main", version="1.0.0", dependencies=[dep.id],
        ))
        deps = self.eng.list_dependencies(main.id)
        assert len(deps) == 1
        assert deps[0].id == dep.id

    def test_artifacts_cap_eviction(self) -> None:
        for i in range(_MAX_ARTIFACTS + 10):
            self.eng.register(self._mk(name=f"pkg-{i}", version="1.0.0"))
        assert len(self.eng._artifacts) == _MAX_ARTIFACTS


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_debugger_engine_singleton(self) -> None:
        a = get_debugger_engine()
        b = get_debugger_engine()
        assert a is b

    def test_unittest_engine_singleton(self) -> None:
        a = get_unittest_engine()
        b = get_unittest_engine()
        assert a is b

    def test_artifact_engine_singleton(self) -> None:
        a = get_artifact_engine()
        b = get_artifact_engine()
        assert a is b

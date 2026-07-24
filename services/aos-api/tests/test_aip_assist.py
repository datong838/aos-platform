"""W2-AE · AIP 辅助与仓库配置组测试（#107 / #108 / #110）.

覆盖 AIPAssistEngine / RepoSettingsEngine / ProjectStructureEngine 三引擎。
"""
from __future__ import annotations

import pytest

from aos_api.aip_assist import (
    AIPAssistEngine,
    AIPAssistError,
    AIPAssistRequest,
    ProjectStructure,
    ProjectStructureEngine,
    RepoSettings,
    RepoSettingsEngine,
    StructureComponent,
    get_assist_engine,
    get_settings_engine,
    get_structure_engine,
)


# ════════════════════ AIPAssistEngine ════════════════════

class TestAIPAssist:
    def setup_method(self) -> None:
        self.eng = AIPAssistEngine.__new__(AIPAssistEngine)
        self.eng._requests = {}
        self.eng._results = []
        self.eng._lock = __import__("threading").Lock()

    def _mk(self, **kw: object) -> AIPAssistRequest:
        defaults: dict[str, object] = {
            "kind": "explain",
            "code": "print('hi')\nx = 1\n",
            "language": "python",
        }
        defaults.update(kw)
        return AIPAssistRequest(**defaults)

    def test_register_returns_with_id(self) -> None:
        r = self.eng.register(self._mk())
        assert r.id.startswith("aip-")

    def test_register_missing_code(self) -> None:
        with pytest.raises(AIPAssistError) as exc:
            self.eng.register(self._mk(code=""))
        assert exc.value.code == "MISSING_CODE"

    def test_register_invalid_kind(self) -> None:
        with pytest.raises(AIPAssistError) as exc:
            self.eng.register(self._mk(kind="unknown"))
        assert exc.value.code == "INVALID_KIND"

    def test_register_invalid_language(self) -> None:
        with pytest.raises(AIPAssistError) as exc:
            self.eng.register(self._mk(language="ruby"))
        assert exc.value.code == "INVALID_LANGUAGE"

    def test_get_not_found(self) -> None:
        with pytest.raises(AIPAssistError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk(kind="vulnerability"))
        assert len(self.eng.list()) == 2

    def test_list_filter_kind(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk(kind="vulnerability"))
        items = self.eng.list(kind="vulnerability")
        assert len(items) == 1
        assert items[0].kind == "vulnerability"

    def test_list_filter_status(self) -> None:
        r = self.eng.register(self._mk())
        self.eng.run(r.id)
        items = self.eng.list(status="completed")
        assert len(items) == 1
        assert items[0].status == "completed"

    def test_update(self) -> None:
        r = self.eng.register(self._mk())
        updated = self.eng.update(r.id, {"code": "x = 2\n", "context": "test"})
        assert updated.code == "x = 2\n"
        assert updated.context == "test"

    def test_delete(self) -> None:
        r = self.eng.register(self._mk())
        assert self.eng.delete(r.id) is True
        assert self.eng.delete(r.id) is False

    def test_run_explain(self) -> None:
        r = self.eng.register(self._mk(kind="explain"))
        result = self.eng.run(r.id)
        assert result.status == "completed"
        assert "summary" in result.result
        assert result.result["lines"] == 2

    def test_run_vulnerability(self) -> None:
        r = self.eng.register(self._mk(
            kind="vulnerability",
            code="open('f')\neval('x')\nsafe_call()\n",
        ))
        result = self.eng.run(r.id)
        assert result.status == "completed"
        assert result.result["count"] >= 2  # open + eval
        names = {v["builtin"] for v in result.result["vulnerabilities"]}
        assert "open" in names
        assert "eval" in names

    def test_run_translate(self) -> None:
        r = self.eng.register(self._mk(
            kind="translate", code="def foo(x):\n    return True\n",
        ))
        result = self.eng.run(r.id)
        assert result.status == "completed"
        assert "translated" in result.result
        assert result.result["target_language"] == "java"
        assert "true" in result.result["translated"]

    def test_run_complete(self) -> None:
        r = self.eng.register(self._mk(
            kind="complete", code="def \n",
        ))
        result = self.eng.run(r.id)
        assert result.status == "completed"
        assert "suggestion" in result.result

    def test_run_already_completed(self) -> None:
        r = self.eng.register(self._mk())
        self.eng.run(r.id)
        with pytest.raises(AIPAssistError) as exc:
            self.eng.run(r.id)
        assert exc.value.code == "ALREADY_COMPLETED"

    def test_results_cap_eviction(self) -> None:
        from aos_api.aip_assist import _MAX_RESULTS
        for i in range(_MAX_RESULTS + 5):
            r = self.eng.register(self._mk(code=f"# {i}\n"))
            self.eng.run(r.id)
        assert len(self.eng._results) == _MAX_RESULTS


# ════════════════════ RepoSettingsEngine ════════════════════

class TestRepoSettings:
    def setup_method(self) -> None:
        self.eng = RepoSettingsEngine.__new__(RepoSettingsEngine)
        self.eng._settings = {}
        self.eng._lock = __import__("threading").Lock()

    def _mk(self, **kw: object) -> RepoSettings:
        defaults: dict[str, object] = {
            "repo_id": "repo-1",
            "label_validation": {
                "required_prefixes": ["bug:", "feat:"],
                "color_required": False,
            },
            "pr_template": "## PR\n作者：{author}\n标题：{title}\n",
            "validation_rules": [
                {"kind": "branch_protection", "config": {"branch": "main"}},
            ],
        }
        defaults.update(kw)
        return RepoSettings(**defaults)

    def test_register_returns_with_id(self) -> None:
        s = self.eng.register(self._mk())
        assert s.id.startswith("rs-")

    def test_register_missing_repo(self) -> None:
        with pytest.raises(AIPAssistError) as exc:
            self.eng.register(self._mk(repo_id=""))
        assert exc.value.code == "MISSING_REPO"

    def test_get_not_found(self) -> None:
        with pytest.raises(AIPAssistError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_get_by_repo(self) -> None:
        s = self.eng.register(self._mk(repo_id="r-a"))
        found = self.eng.get_by_repo("r-a")
        assert found is not None
        assert found.id == s.id
        assert self.eng.get_by_repo("nope") is None

    def test_list_default(self) -> None:
        self.eng.register(self._mk(repo_id="r1"))
        self.eng.register(self._mk(repo_id="r2"))
        assert len(self.eng.list()) == 2

    def test_list_filter_repo_id(self) -> None:
        self.eng.register(self._mk(repo_id="r1"))
        self.eng.register(self._mk(repo_id="r2"))
        items = self.eng.list(repo_id="r1")
        assert len(items) == 1
        assert items[0].repo_id == "r1"

    def test_update(self) -> None:
        s = self.eng.register(self._mk())
        updated = self.eng.update(s.id, {
            "pr_template": "new template",
            "enforce_branch_protection": True,
        })
        assert updated.pr_template == "new template"
        assert updated.enforce_branch_protection is True

    def test_delete(self) -> None:
        s = self.eng.register(self._mk())
        assert self.eng.delete(s.id) is True
        assert self.eng.delete(s.id) is False

    def test_validate_label_pass(self) -> None:
        s = self.eng.register(self._mk())
        result = self.eng.validate_label(s.id, "bug: fix something")
        assert result["valid"] is True

    def test_validate_label_missing_prefix(self) -> None:
        s = self.eng.register(self._mk())
        result = self.eng.validate_label(s.id, "no-prefix")
        assert result["valid"] is False
        assert "prefix" in result["reason"]

    def test_validate_label_color_required(self) -> None:
        s = self.eng.register(self._mk(label_validation={
            "required_prefixes": ["bug:"],
            "color_required": True,
        }))
        # 有前缀但无颜色（无第二个 :）
        result = self.eng.validate_label(s.id, "bug: fix")
        assert result["valid"] is False
        assert "color" in result["reason"]

    def test_render_pr_template(self) -> None:
        s = self.eng.register(self._mk())
        rendered = self.eng.render_pr_template(s.id, {"author": "张三", "title": "修复"})
        assert "张三" in rendered
        assert "修复" in rendered
        assert "{author}" not in rendered

    def test_update_invalid_rule_kind(self) -> None:
        s = self.eng.register(self._mk())
        with pytest.raises(AIPAssistError) as exc:
            self.eng.update(s.id, {
                "validation_rules": [{"kind": "unknown_rule", "config": {}}],
            })
        assert exc.value.code == "INVALID_RULE_KIND"


# ════════════════════ ProjectStructureEngine ════════════════════

class TestProjectStructure:
    def setup_method(self) -> None:
        self.eng = ProjectStructureEngine.__new__(ProjectStructureEngine)
        self.eng._structures = {}
        self.eng._lock = __import__("threading").Lock()

    def _mk(self, **kw: object) -> ProjectStructure:
        defaults: dict[str, object] = {
            "name": "tpl-1",
            "description": "test template",
            "layers": ["datasource", "transform", "ontology", "workflow"],
            "components": [
                StructureComponent(layer="datasource", name="raw_ds", type="dataset", rid_prefix="ds.", required=True),
                StructureComponent(layer="transform", name="etl", type="transform", rid_prefix="tf.", required=False),
                StructureComponent(layer="ontology", name="ont", type="ontology", rid_prefix="ont.", required=True),
            ],
        }
        defaults.update(kw)
        return ProjectStructure(**defaults)

    def test_register_returns_with_id(self) -> None:
        s = self.eng.register(self._mk())
        assert s.id.startswith("ps-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(AIPAssistError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_invalid_layer(self) -> None:
        with pytest.raises(AIPAssistError) as exc:
            self.eng.register(self._mk(layers=["datasource", "unknown_layer"]))
        assert exc.value.code == "INVALID_LAYER"

    def test_register_invalid_component_type(self) -> None:
        with pytest.raises(AIPAssistError) as exc:
            self.eng.register(self._mk(components=[
                StructureComponent(layer="datasource", name="x", type="bad_type"),
            ]))
        assert exc.value.code == "INVALID_COMPONENT_TYPE"

    def test_get_not_found(self) -> None:
        with pytest.raises(AIPAssistError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(name="a"))
        self.eng.register(self._mk(name="b"))
        assert len(self.eng.list()) == 2

    def test_list_filter_name(self) -> None:
        self.eng.register(self._mk(name="a"))
        self.eng.register(self._mk(name="b"))
        items = self.eng.list(name="b")
        assert len(items) == 1
        assert items[0].name == "b"

    def test_update(self) -> None:
        s = self.eng.register(self._mk())
        updated = self.eng.update(s.id, {"description": "updated", "name": "tpl-2"})
        assert updated.description == "updated"
        assert updated.name == "tpl-2"

    def test_delete(self) -> None:
        s = self.eng.register(self._mk())
        assert self.eng.delete(s.id) is True
        assert self.eng.delete(s.id) is False

    def test_render_template(self) -> None:
        s = self.eng.register(self._mk())
        rendered = self.eng.render_template(s.id)
        assert rendered["name"] == "tpl-1"
        assert "datasource" in rendered["layers"]
        assert len(rendered["components"]) == 3
        assert rendered["components"][0]["layer"] == "datasource"

    def test_validate_project_pass(self) -> None:
        s = self.eng.register(self._mk())
        project = [
            {"layer": "datasource", "name": "raw_ds"},
            {"layer": "transform", "name": "etl"},
            {"layer": "ontology", "name": "ont"},
            {"layer": "workflow", "name": "wf"},  # 额外组件
        ]
        result = self.eng.validate_project(s.id, project)
        assert result["valid"] is True
        assert len(result["missing"]) == 0

    def test_validate_project_missing_required(self) -> None:
        s = self.eng.register(self._mk())
        project = [
            {"layer": "transform", "name": "etl"},
            # 缺 raw_ds (required) 和 ont (required)
        ]
        result = self.eng.validate_project(s.id, project)
        assert result["valid"] is False
        missing_names = {m["name"] for m in result["missing"]}
        assert "raw_ds" in missing_names
        assert "ont" in missing_names

    def test_validate_project_extra(self) -> None:
        s = self.eng.register(self._mk())
        project = [
            {"layer": "datasource", "name": "raw_ds"},
            {"layer": "transform", "name": "etl"},
            {"layer": "ontology", "name": "ont"},
            {"layer": "workflow", "name": "extra_wf"},  # 不在模板中
        ]
        result = self.eng.validate_project(s.id, project)
        # extra_wf 不在模板的 components 中 → extra
        extra_names = {e["name"] for e in result["extra"]}
        assert "extra_wf" in extra_names


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_assist_singleton(self) -> None:
        a = get_assist_engine()
        b = get_assist_engine()
        assert a is b

    def test_settings_singleton(self) -> None:
        a = get_settings_engine()
        b = get_settings_engine()
        assert a is b

    def test_structure_singleton(self) -> None:
        a = get_structure_engine()
        b = get_structure_engine()
        assert a is b

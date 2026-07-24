"""W2-AT · Compute Module Extras 测试（#155 / #156 / #157）.

覆盖 ContainerConfigEngine / ScaleToZeroEngine / DevScaffoldEngine 三引擎。
"""
from __future__ import annotations

import pytest

from aos_api.compute_module_extras import (
    # 模型
    ColdStartAlert,
    ContainerConfigEngine,
    ContainerConfigError,
    ContainerTabConfig,
    DevScaffoldEngine,
    DevScaffoldError,
    GeneratedScaffold,
    ScaleToZeroEngine,
    ScaleToZeroError,
    ScaleToZeroPolicy,
    ScaffoldFile,
    ScaffoldTemplate,
    # getter
    get_container_config_engine,
    get_dev_scaffold_engine,
    get_scale_to_zero_engine,
)


# ════════════════════ ContainerConfigEngine ════════════════════

class TestContainerConfig:
    def setup_method(self) -> None:
        self.eng = ContainerConfigEngine()
        self.eng._configs = {}

    def test_register_config(self) -> None:
        config = self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="configure")
        )
        assert config.tab_config_id.startswith("tc-")
        assert config.module_id == "m1"
        assert config.tab_name == "configure"
        assert config.status == "active"
        assert config.created_at is not None

    def test_get_config(self) -> None:
        c = self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="configure")
        )
        fetched = self.eng.get_config(c.tab_config_id)
        assert fetched.tab_config_id == c.tab_config_id
        assert fetched.module_id == "m1"

    def test_list_configs(self) -> None:
        self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="configure")
        )
        self.eng.register_config(
            ContainerTabConfig(module_id="m2", tab_name="query")
        )
        items = self.eng.list_configs()
        assert len(items) == 2

    def test_list_filter_module(self) -> None:
        self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="configure")
        )
        self.eng.register_config(
            ContainerTabConfig(module_id="m2", tab_name="query")
        )
        items = self.eng.list_configs(module_id="m1")
        assert len(items) == 1
        assert items[0].module_id == "m1"

    def test_list_filter_tab(self) -> None:
        self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="configure")
        )
        self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="query")
        )
        items = self.eng.list_configs(tab="query")
        assert len(items) == 1
        assert items[0].tab_name == "query"

    def test_list_filter_status(self) -> None:
        self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="configure", status="inactive")
        )
        self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="query", status="active")
        )
        active = self.eng.list_configs(status="active")
        inactive = self.eng.list_configs(status="inactive")
        assert len(active) == 1
        assert active[0].status == "active"
        assert len(inactive) == 1
        assert inactive[0].status == "inactive"

    def test_update_config(self) -> None:
        c = self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="configure")
        )
        updated = self.eng.update_config(c.tab_config_id, {"status": "inactive"})
        assert updated.status == "inactive"
        assert updated.updated_at is not None

    def test_delete_config(self) -> None:
        c = self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="configure")
        )
        self.eng.delete_config(c.tab_config_id)
        with pytest.raises(ContainerConfigError) as exc:
            self.eng.get_config(c.tab_config_id)
        assert exc.value.code == "NOT_FOUND"

    def test_get_module_overview(self) -> None:
        c1 = self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="configure")
        )
        self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="query")
        )
        self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="overview")
        )
        overview = self.eng.get_module_overview("m1")
        assert overview["configure"] == c1
        assert overview["query"] is not None
        assert overview["overview"] is not None

    def test_missing_module(self) -> None:
        with pytest.raises(ContainerConfigError) as exc:
            self.eng.register_config(
                ContainerTabConfig(module_id="", tab_name="configure")
            )
        assert exc.value.code == "MISSING_MODULE"

    def test_missing_tab_name(self) -> None:
        with pytest.raises(ContainerConfigError) as exc:
            self.eng.register_config(
                ContainerTabConfig(module_id="m1", tab_name="")
            )
        assert exc.value.code == "MISSING_TAB_NAME"

    def test_invalid_tab_name(self) -> None:
        with pytest.raises(ContainerConfigError) as exc:
            self.eng.register_config(
                ContainerTabConfig(module_id="m1", tab_name="invalid")
            )
        assert exc.value.code == "INVALID_TAB_NAME"

    def test_invalid_status(self) -> None:
        with pytest.raises(ContainerConfigError) as exc:
            self.eng.register_config(
                ContainerTabConfig(module_id="m1", tab_name="configure", status="bad")
            )
        assert exc.value.code == "INVALID_STATUS"

    def test_not_found_get(self) -> None:
        with pytest.raises(ContainerConfigError) as exc:
            self.eng.get_config("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_update(self) -> None:
        with pytest.raises(ContainerConfigError) as exc:
            self.eng.update_config("nonexistent", {"status": "inactive"})
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_delete(self) -> None:
        with pytest.raises(ContainerConfigError) as exc:
            self.eng.delete_config("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_update_invalid_tab_name(self) -> None:
        c = self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="configure")
        )
        with pytest.raises(ContainerConfigError) as exc:
            self.eng.update_config(c.tab_config_id, {"tab_name": "bad"})
        assert exc.value.code == "INVALID_TAB_NAME"

    def test_update_invalid_status(self) -> None:
        c = self.eng.register_config(
            ContainerTabConfig(module_id="m1", tab_name="configure")
        )
        with pytest.raises(ContainerConfigError) as exc:
            self.eng.update_config(c.tab_config_id, {"status": "bad"})
        assert exc.value.code == "INVALID_STATUS"

    def test_max_configs_eviction(self) -> None:
        from aos_api.compute_module_extras import _MAX_CONTAINER_CONFIGS

        for i in range(_MAX_CONTAINER_CONFIGS + 5):
            self.eng.register_config(
                ContainerTabConfig(module_id=f"m-{i}", tab_name="configure")
            )
        assert len(self.eng._configs) == _MAX_CONTAINER_CONFIGS


# ════════════════════ ScaleToZeroEngine ════════════════════

class TestScaleToZero:
    def setup_method(self) -> None:
        self.eng = ScaleToZeroEngine()
        self.eng._policies = {}
        self.eng._alerts = {}

    def test_register_policy(self) -> None:
        policy = self.eng.register_policy(ScaleToZeroPolicy(module_id="m1"))
        assert policy.policy_id.startswith("sz-")
        assert policy.module_id == "m1"
        assert policy.status == "active"
        assert policy.created_at is not None

    def test_get_policy(self) -> None:
        p = self.eng.register_policy(ScaleToZeroPolicy(module_id="m1"))
        fetched = self.eng.get_policy(p.policy_id)
        assert fetched.policy_id == p.policy_id
        assert fetched.module_id == "m1"

    def test_list_policies(self) -> None:
        self.eng.register_policy(ScaleToZeroPolicy(module_id="m1"))
        self.eng.register_policy(ScaleToZeroPolicy(module_id="m2"))
        items = self.eng.list_policies()
        assert len(items) == 2

    def test_list_filter_module(self) -> None:
        self.eng.register_policy(ScaleToZeroPolicy(module_id="m1"))
        self.eng.register_policy(ScaleToZeroPolicy(module_id="m2"))
        items = self.eng.list_policies(module_id="m1")
        assert len(items) == 1
        assert items[0].module_id == "m1"

    def test_list_filter_status(self) -> None:
        p1 = self.eng.register_policy(ScaleToZeroPolicy(module_id="m1"))
        self.eng.register_policy(ScaleToZeroPolicy(module_id="m2"))
        self.eng.update_policy(p1.policy_id, {"status": "inactive"})
        active = self.eng.list_policies(status="active")
        inactive = self.eng.list_policies(status="inactive")
        assert len(active) == 1
        assert active[0].status == "active"
        assert len(inactive) == 1
        assert inactive[0].status == "inactive"

    def test_update_policy(self) -> None:
        p = self.eng.register_policy(ScaleToZeroPolicy(module_id="m1"))
        updated = self.eng.update_policy(p.policy_id, {"idle_timeout_seconds": 600})
        assert updated.idle_timeout_seconds == 600

    def test_delete_policy(self) -> None:
        p = self.eng.register_policy(ScaleToZeroPolicy(module_id="m1"))
        self.eng.delete_policy(p.policy_id)
        with pytest.raises(ScaleToZeroError) as exc:
            self.eng.get_policy(p.policy_id)
        assert exc.value.code == "NOT_FOUND"

    def test_trigger_alert(self) -> None:
        alert = self.eng.trigger_alert("m1", "cold_start", 250, "warning")
        assert alert.alert_id.startswith("al-")
        assert alert.module_id == "m1"
        assert alert.alert_type == "cold_start"
        assert alert.wait_duration_ms == 250
        assert alert.severity == "warning"
        assert alert.cleared is False

    def test_list_alerts(self) -> None:
        self.eng.trigger_alert("m1", "cold_start", 100, "info")
        self.eng.trigger_alert("m2", "scale_up", 200, "warning")
        items = self.eng.list_alerts()
        assert len(items) == 2

    def test_list_filter_module(self) -> None:
        self.eng.trigger_alert("m1", "cold_start", 100, "info")
        self.eng.trigger_alert("m2", "cold_start", 100, "info")
        items = self.eng.list_alerts(module_id="m1")
        assert len(items) == 1
        assert items[0].module_id == "m1"

    def test_list_filter_alert_type(self) -> None:
        self.eng.trigger_alert("m1", "cold_start", 100, "info")
        self.eng.trigger_alert("m1", "scale_up", 200, "warning")
        items = self.eng.list_alerts(alert_type="cold_start")
        assert len(items) == 1
        assert items[0].alert_type == "cold_start"

    def test_list_filter_cleared(self) -> None:
        a = self.eng.trigger_alert("m1", "cold_start", 100, "info")
        self.eng.trigger_alert("m1", "scale_up", 200, "warning")
        self.eng.clear_alert(a.alert_id)
        cleared = self.eng.list_alerts(cleared=True)
        uncleared = self.eng.list_alerts(cleared=False)
        assert len(cleared) == 1
        assert cleared[0].alert_id == a.alert_id
        assert len(uncleared) == 1
        assert uncleared[0].alert_type == "scale_up"

    def test_clear_alert(self) -> None:
        a = self.eng.trigger_alert("m1", "cold_start", 100, "info")
        cleared = self.eng.clear_alert(a.alert_id)
        assert cleared.cleared is True

    def test_simulate_cold_start(self) -> None:
        delay = self.eng.simulate_cold_start("m1")
        assert isinstance(delay, int)
        assert delay > 0

    def test_missing_module(self) -> None:
        with pytest.raises(ScaleToZeroError) as exc:
            self.eng.register_policy(ScaleToZeroPolicy(module_id=""))
        assert exc.value.code == "MISSING_MODULE"

    def test_invalid_idle_timeout(self) -> None:
        with pytest.raises(ScaleToZeroError) as exc:
            self.eng.register_policy(
                ScaleToZeroPolicy(module_id="m1", idle_timeout_seconds=0)
            )
        assert exc.value.code == "INVALID_IDLE_TIMEOUT"

    def test_invalid_min_replicas(self) -> None:
        with pytest.raises(ScaleToZeroError) as exc:
            self.eng.register_policy(
                ScaleToZeroPolicy(module_id="m1", min_replicas=-1)
            )
        assert exc.value.code == "INVALID_MIN_REPLICAS"

    def test_invalid_scale_up_delay(self) -> None:
        with pytest.raises(ScaleToZeroError) as exc:
            self.eng.register_policy(
                ScaleToZeroPolicy(module_id="m1", scale_up_delay_seconds=-1)
            )
        assert exc.value.code == "INVALID_SCALE_UP_DELAY"

    def test_invalid_status(self) -> None:
        with pytest.raises(ScaleToZeroError) as exc:
            self.eng.register_policy(
                ScaleToZeroPolicy(module_id="m1", status="bad")
            )
        assert exc.value.code == "INVALID_STATUS"

    def test_invalid_alert_type(self) -> None:
        with pytest.raises(ScaleToZeroError) as exc:
            self.eng.trigger_alert("m1", "bad_type", 100, "info")
        assert exc.value.code == "INVALID_ALERT_TYPE"

    def test_not_found_get(self) -> None:
        with pytest.raises(ScaleToZeroError) as exc:
            self.eng.get_policy("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_clear(self) -> None:
        with pytest.raises(ScaleToZeroError) as exc:
            self.eng.clear_alert("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_max_policies_eviction(self) -> None:
        from aos_api.compute_module_extras import _MAX_SCALE_POLICIES

        for i in range(_MAX_SCALE_POLICIES + 5):
            self.eng.register_policy(ScaleToZeroPolicy(module_id=f"m-{i}"))
        assert len(self.eng._policies) == _MAX_SCALE_POLICIES

    def test_max_alerts_eviction(self) -> None:
        from aos_api.compute_module_extras import _MAX_ALERTS

        for i in range(_MAX_ALERTS + 5):
            self.eng.trigger_alert("m1", "cold_start", 100, "info")
        assert len(self.eng._alerts) == _MAX_ALERTS


# ════════════════════ DevScaffoldEngine ════════════════════

class TestDevScaffold:
    def setup_method(self) -> None:
        self.eng = DevScaffoldEngine()
        self.eng._templates = {}
        self.eng._scaffolds = {}
        self.eng._init_default_templates()

    def test_register_template(self) -> None:
        tmpl = self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[ScaffoldFile(filename="a.py", content="code")],
            )
        )
        assert tmpl.template_id.startswith("st-")
        assert tmpl.name == "T1"
        assert tmpl.language == "python"
        assert tmpl.created_at is not None

    def test_get_template(self) -> None:
        t = self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[ScaffoldFile(filename="a.py", content="code")],
            )
        )
        fetched = self.eng.get_template(t.template_id)
        assert fetched.template_id == t.template_id

    def test_list_templates(self) -> None:
        self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[ScaffoldFile(filename="a.py", content="code")],
            )
        )
        self.eng.register_template(
            ScaffoldTemplate(
                name="T2",
                language="typescript",
                file_templates=[ScaffoldFile(filename="a.ts", content="code")],
            )
        )
        items = self.eng.list_templates()
        assert len(items) == 5  # 3 built-in + 2 registered

    def test_list_filter_language(self) -> None:
        self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[ScaffoldFile(filename="a.py", content="code")],
            )
        )
        self.eng.register_template(
            ScaffoldTemplate(
                name="T2",
                language="typescript",
                file_templates=[ScaffoldFile(filename="a.ts", content="code")],
            )
        )
        items = self.eng.list_templates(language="python")
        assert len(items) == 3  # 2 built-in python + 1 registered
        assert items[0].language == "python"

    def test_update_template(self) -> None:
        t = self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[ScaffoldFile(filename="a.py", content="code")],
            )
        )
        updated = self.eng.update_template(t.template_id, {"name": "T1-new"})
        assert updated.name == "T1-new"
        assert updated.updated_at is not None

    def test_delete_template(self) -> None:
        t = self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[ScaffoldFile(filename="a.py", content="code")],
            )
        )
        self.eng.delete_template(t.template_id)
        with pytest.raises(DevScaffoldError) as exc:
            self.eng.get_template(t.template_id)
        assert exc.value.code == "NOT_FOUND"

    def test_generate_scaffold(self) -> None:
        t = self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[
                    ScaffoldFile(filename="a.py", content="# {{module_id}}")
                ],
            )
        )
        scaffold = self.eng.generate_scaffold("mod-1", t.template_id)
        assert scaffold.scaffold_id.startswith("gs-")
        assert scaffold.module_id == "mod-1"
        assert scaffold.template_id == t.template_id
        assert scaffold.rendered_files[0].content == "# mod-1"
        assert scaffold.status == "generated"

    def test_get_scaffold(self) -> None:
        t = self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[ScaffoldFile(filename="a.py", content="code")],
            )
        )
        s = self.eng.generate_scaffold("mod-1", t.template_id)
        fetched = self.eng.get_scaffold(s.scaffold_id)
        assert fetched.scaffold_id == s.scaffold_id

    def test_list_scaffolds(self) -> None:
        t = self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[ScaffoldFile(filename="a.py", content="code")],
            )
        )
        self.eng.generate_scaffold("mod-1", t.template_id)
        self.eng.generate_scaffold("mod-2", t.template_id)
        items = self.eng.list_scaffolds()
        assert len(items) == 2

    def test_list_filter_module(self) -> None:
        t = self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[ScaffoldFile(filename="a.py", content="code")],
            )
        )
        self.eng.generate_scaffold("mod-1", t.template_id)
        self.eng.generate_scaffold("mod-2", t.template_id)
        items = self.eng.list_scaffolds(module_id="mod-1")
        assert len(items) == 1
        assert items[0].module_id == "mod-1"

    def test_list_filter_status(self) -> None:
        t = self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[ScaffoldFile(filename="a.py", content="code")],
            )
        )
        s = self.eng.generate_scaffold("mod-1", t.template_id)
        self.eng.apply_scaffold(s.scaffold_id)
        items = self.eng.list_scaffolds(status="applied")
        assert len(items) == 1
        assert items[0].status == "applied"

    def test_apply_scaffold(self) -> None:
        t = self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[ScaffoldFile(filename="a.py", content="code")],
            )
        )
        s = self.eng.generate_scaffold("mod-1", t.template_id)
        applied = self.eng.apply_scaffold(s.scaffold_id)
        assert applied.status == "applied"

    def test_default_templates_exist(self) -> None:
        eng = DevScaffoldEngine()
        assert len(eng._templates) == 3

    def test_missing_name(self) -> None:
        with pytest.raises(DevScaffoldError) as exc:
            self.eng.register_template(
                ScaffoldTemplate(name="", language="python")
            )
        assert exc.value.code == "MISSING_NAME"

    def test_missing_module(self) -> None:
        t = self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[ScaffoldFile(filename="a.py", content="code")],
            )
        )
        with pytest.raises(DevScaffoldError) as exc:
            self.eng.generate_scaffold("", t.template_id)
        assert exc.value.code == "MISSING_MODULE"

    def test_invalid_language(self) -> None:
        with pytest.raises(DevScaffoldError) as exc:
            self.eng.register_template(
                ScaffoldTemplate(name="T1", language="go")
            )
        assert exc.value.code == "INVALID_LANGUAGE"

    def test_template_not_found(self) -> None:
        with pytest.raises(DevScaffoldError) as exc:
            self.eng.generate_scaffold("mod-1", "nonexistent")
        assert exc.value.code == "TEMPLATE_NOT_FOUND"

    def test_scaffold_not_found(self) -> None:
        with pytest.raises(DevScaffoldError) as exc:
            self.eng.get_scaffold("nonexistent")
        assert exc.value.code == "SCAFFOLD_NOT_FOUND"

    def test_not_found_get_template(self) -> None:
        with pytest.raises(DevScaffoldError) as exc:
            self.eng.get_template("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_get_scaffold(self) -> None:
        with pytest.raises(DevScaffoldError) as exc:
            self.eng.apply_scaffold("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_max_templates_eviction(self) -> None:
        from aos_api.compute_module_extras import _MAX_SCAFFOLD_TEMPLATES

        for i in range(_MAX_SCAFFOLD_TEMPLATES + 5):
            self.eng.register_template(
                ScaffoldTemplate(name=f"T-{i}", language="python")
            )
        assert len(self.eng._templates) == _MAX_SCAFFOLD_TEMPLATES

    def test_max_scaffolds_eviction(self) -> None:
        from aos_api.compute_module_extras import _MAX_GENERATED_SCAFFOLDS

        t = self.eng.register_template(
            ScaffoldTemplate(
                name="T1",
                language="python",
                file_templates=[ScaffoldFile(filename="a.py", content="code")],
            )
        )
        for i in range(_MAX_GENERATED_SCAFFOLDS + 5):
            self.eng.generate_scaffold(f"mod-{i}", t.template_id)
        assert len(self.eng._scaffolds) == _MAX_GENERATED_SCAFFOLDS


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_container_config_singleton(self) -> None:
        a = get_container_config_engine()
        b = get_container_config_engine()
        assert a is b

    def test_scale_to_zero_singleton(self) -> None:
        a = get_scale_to_zero_engine()
        b = get_scale_to_zero_engine()
        assert a is b

    def test_dev_scaffold_singleton(self) -> None:
        a = get_dev_scaffold_engine()
        b = get_dev_scaffold_engine()
        assert a is b

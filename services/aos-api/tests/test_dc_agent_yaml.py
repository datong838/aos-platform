"W4 · Agent 高级 YAML 配置（220w L102） 测试."""
from __future__ import annotations

import pytest

from aos_api.dc_agent_yaml import (
    AgentYaml,
    AgentYamlEngine,
    AgentYamlError,
    get_engine,
)


class TestAgentYamlEngine:
    def setup_method(self) -> None:
        self.eng = AgentYamlEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> AgentYaml:
        return AgentYaml(**kw)

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "ay_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "ay_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(AgentYamlError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "ay_id"), {"name": "updated"})
        assert updated.name == "updated"

    def test_update_not_found(self) -> None:
        with pytest.raises(AgentYamlError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "ay_id"))
        with pytest.raises(AgentYamlError):
            self.eng.get(getattr(item, "ay_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestAgentYamlSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()

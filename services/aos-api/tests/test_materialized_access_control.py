"""Test cases for Materialized Access Control engines."""
from __future__ import annotations

import pytest

from aos_api.materialized_access_control import (
    _MAX_ENTRIES,
    AgentToolsEngine,
    AgentToolsEngineError,
    ColumnLevelEngine,
    ColumnLevelEngineError,
    MaterializationEngine,
    MaterializationEngineError,
    RowLevelEngine,
    RowLevelEngineError,
)


class TestMaterializationEngine:
    def setup_method(self) -> None:
        self.engine = MaterializationEngine()

    def test_create_task_success(self) -> None:
        task = self.engine.create_task("User", "scheduled", interval_hours=6)
        assert task.task_id.startswith("mt-")
        assert task.object_id == "User"
        assert task.materialization_type == "scheduled"

    def test_create_task_missing_object_id(self) -> None:
        with pytest.raises(MaterializationEngineError) as exc_info:
            self.engine.create_task("", "auto")
        assert exc_info.value.code == "MISSING_OBJECT_ID"

    def test_create_task_invalid_type(self) -> None:
        with pytest.raises(MaterializationEngineError) as exc_info:
            self.engine.create_task("User", "invalid")
        assert exc_info.value.code == "INVALID_MATERIALIZATION_TYPE"

    def test_get_task_success(self) -> None:
        task = self.engine.create_task("User", "auto")
        result = self.engine.get_task(task.task_id)
        assert result is not None
        assert result.task_id == task.task_id

    def test_get_task_not_found(self) -> None:
        with pytest.raises(MaterializationEngineError) as exc_info:
            self.engine.get_task("mt-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_tasks(self) -> None:
        self.engine.create_task("User", "auto")
        self.engine.create_task("Product", "scheduled")
        tasks = self.engine.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_by_object_id(self) -> None:
        self.engine.create_task("User", "auto")
        self.engine.create_task("User", "scheduled")
        self.engine.create_task("Product", "auto")
        tasks = self.engine.list_tasks(object_id="User")
        assert len(tasks) == 2

    def test_update_task_success(self) -> None:
        task = self.engine.create_task("User", "auto")
        updated = self.engine.update_task(task.task_id, interval_hours=12)
        assert updated.interval_hours == 12

    def test_update_task_not_found(self) -> None:
        with pytest.raises(MaterializationEngineError) as exc_info:
            self.engine.update_task("mt-nonexistent", interval_hours=12)
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_task_success(self) -> None:
        task = self.engine.create_task("User", "auto")
        result = self.engine.delete_task(task.task_id)
        assert result is True

    def test_delete_task_not_found(self) -> None:
        result = self.engine.delete_task("mt-nonexistent")
        assert result is False

    def test_run_materialization(self) -> None:
        task = self.engine.create_task("User", "auto")
        result = self.engine.run_materialization(task.task_id)
        assert result.status == "completed"

    def test_fifo_eviction(self) -> None:
        for i in range(_MAX_ENTRIES + 5):
            self.engine.create_task(f"Type{i}", "auto")
        assert len(self.engine.list_tasks()) == _MAX_ENTRIES


class TestRowLevelEngine:
    def setup_method(self) -> None:
        self.engine = RowLevelEngine()

    def test_create_policy_success(self) -> None:
        policy = self.engine.create_policy("view1", "doctor_policy", "filter", "department == 'cardiology'")
        assert policy.policy_id.startswith("rlp-")
        assert policy.view_id == "view1"
        assert policy.name == "doctor_policy"
        assert policy.policy_type == "filter"

    def test_create_policy_missing_view_id(self) -> None:
        with pytest.raises(RowLevelEngineError) as exc_info:
            self.engine.create_policy("", "policy", "filter", "1=1")
        assert exc_info.value.code == "MISSING_VIEW_ID"

    def test_create_policy_missing_name(self) -> None:
        with pytest.raises(RowLevelEngineError) as exc_info:
            self.engine.create_policy("view1", "", "filter", "1=1")
        assert exc_info.value.code == "MISSING_NAME"

    def test_create_policy_invalid_type(self) -> None:
        with pytest.raises(RowLevelEngineError) as exc_info:
            self.engine.create_policy("view1", "policy", "invalid", "1=1")
        assert exc_info.value.code == "INVALID_POLICY_TYPE"

    def test_get_policy_success(self) -> None:
        policy = self.engine.create_policy("view1", "policy1", "filter", "1=1")
        result = self.engine.get_policy(policy.policy_id)
        assert result is not None
        assert result.policy_id == policy.policy_id

    def test_get_policy_not_found(self) -> None:
        with pytest.raises(RowLevelEngineError) as exc_info:
            self.engine.get_policy("rlp-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_policies(self) -> None:
        self.engine.create_policy("view1", "policy1", "filter", "1=1")
        self.engine.create_policy("view2", "policy2", "mask", "1=1")
        policies = self.engine.list_policies()
        assert len(policies) == 2

    def test_list_policies_by_view_id(self) -> None:
        self.engine.create_policy("view1", "policy1", "filter", "1=1")
        self.engine.create_policy("view1", "policy2", "mask", "1=1")
        self.engine.create_policy("view2", "policy3", "filter", "1=1")
        policies = self.engine.list_policies(view_id="view1")
        assert len(policies) == 2

    def test_evaluate_policy(self) -> None:
        policy = self.engine.create_policy("view1", "policy1", "filter", "1=1")
        result = self.engine.evaluate(policy.policy_id, "user1")
        assert result is not None
        assert result.policy_id == policy.policy_id
        assert result.user_id == "user1"

    def test_evaluate_all(self) -> None:
        self.engine.create_policy("view1", "policy1", "filter", "1=1")
        self.engine.create_policy("view1", "policy2", "mask", "1=1")
        results = self.engine.evaluate_all("view1", "user1")
        assert len(results) == 2

    def test_update_policy_success(self) -> None:
        policy = self.engine.create_policy("view1", "policy1", "filter", "1=1")
        updated = self.engine.update_policy(policy.policy_id, description="updated")
        assert updated.description == "updated"

    def test_update_policy_not_found(self) -> None:
        with pytest.raises(RowLevelEngineError) as exc_info:
            self.engine.update_policy("rlp-nonexistent", description="updated")
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_policy_success(self) -> None:
        policy = self.engine.create_policy("view1", "policy1", "filter", "1=1")
        result = self.engine.delete_policy(policy.policy_id)
        assert result is True

    def test_delete_policy_not_found(self) -> None:
        result = self.engine.delete_policy("rlp-nonexistent")
        assert result is False

    def test_fifo_eviction(self) -> None:
        for i in range(_MAX_ENTRIES + 5):
            self.engine.create_policy(f"view{i}", f"policy{i}", "filter", "1=1")
        assert len(self.engine.list_policies()) == _MAX_ENTRIES


class TestColumnLevelEngine:
    def setup_method(self) -> None:
        self.engine = ColumnLevelEngine()

    def test_create_policy_success(self) -> None:
        policy = self.engine.create_policy("mdo1", "mdo_policy", "include")
        assert policy.policy_id.startswith("clp-")
        assert policy.mdo_id == "mdo1"
        assert policy.name == "mdo_policy"
        assert policy.policy_type == "include"

    def test_create_policy_missing_mdo_id(self) -> None:
        with pytest.raises(ColumnLevelEngineError) as exc_info:
            self.engine.create_policy("", "policy", "include")
        assert exc_info.value.code == "MISSING_MDO_ID"

    def test_create_policy_missing_name(self) -> None:
        with pytest.raises(ColumnLevelEngineError) as exc_info:
            self.engine.create_policy("mdo1", "", "include")
        assert exc_info.value.code == "MISSING_NAME"

    def test_create_policy_invalid_type(self) -> None:
        with pytest.raises(ColumnLevelEngineError) as exc_info:
            self.engine.create_policy("mdo1", "policy", "invalid")
        assert exc_info.value.code == "INVALID_POLICY_TYPE"

    def test_get_policy_success(self) -> None:
        policy = self.engine.create_policy("mdo1", "policy1", "include")
        result = self.engine.get_policy(policy.policy_id)
        assert result is not None
        assert result.policy_id == policy.policy_id

    def test_get_policy_not_found(self) -> None:
        with pytest.raises(ColumnLevelEngineError) as exc_info:
            self.engine.get_policy("clp-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_policies(self) -> None:
        self.engine.create_policy("mdo1", "policy1", "include")
        self.engine.create_policy("mdo2", "policy2", "exclude")
        policies = self.engine.list_policies()
        assert len(policies) == 2

    def test_list_policies_by_mdo_id(self) -> None:
        self.engine.create_policy("mdo1", "policy1", "include")
        self.engine.create_policy("mdo1", "policy2", "mask")
        self.engine.create_policy("mdo2", "policy3", "include")
        policies = self.engine.list_policies(mdo_id="mdo1")
        assert len(policies) == 2

    def test_evaluate_policy(self) -> None:
        policy = self.engine.create_policy("mdo1", "policy1", "include")
        result = self.engine.evaluate(policy.policy_id, "user1")
        assert result is not None

    def test_update_policy_success(self) -> None:
        policy = self.engine.create_policy("mdo1", "policy1", "include")
        updated = self.engine.update_policy(policy.policy_id, description="updated")
        assert updated.description == "updated"

    def test_update_policy_not_found(self) -> None:
        with pytest.raises(ColumnLevelEngineError) as exc_info:
            self.engine.update_policy("clp-nonexistent", description="updated")
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_policy_success(self) -> None:
        policy = self.engine.create_policy("mdo1", "policy1", "include")
        result = self.engine.delete_policy(policy.policy_id)
        assert result is True

    def test_delete_policy_not_found(self) -> None:
        result = self.engine.delete_policy("clp-nonexistent")
        assert result is False

    def test_fifo_eviction(self) -> None:
        for i in range(_MAX_ENTRIES + 5):
            self.engine.create_policy(f"mdo{i}", f"policy{i}", "include")
        assert len(self.engine.list_policies()) == _MAX_ENTRIES


class TestAgentToolsEngine:
    def setup_method(self) -> None:
        self.engine = AgentToolsEngine()

    def test_create_tool_success(self) -> None:
        tool = self.engine.create_tool("send_email", "Action")
        assert tool.tool_id.startswith("at-")
        assert tool.name == "send_email"
        assert tool.tool_type == "Action"

    def test_create_tool_missing_name(self) -> None:
        with pytest.raises(AgentToolsEngineError) as exc_info:
            self.engine.create_tool("", "Action")
        assert exc_info.value.code == "MISSING_NAME"

    def test_create_tool_invalid_type_empty(self) -> None:
        with pytest.raises(AgentToolsEngineError) as exc_info:
            self.engine.create_tool("tool", "")
        assert exc_info.value.code == "INVALID_TOOL_TYPE"

    def test_create_tool_invalid_type(self) -> None:
        with pytest.raises(AgentToolsEngineError) as exc_info:
            self.engine.create_tool("tool", "Invalid")
        assert exc_info.value.code == "INVALID_TOOL_TYPE"

    def test_get_tool_success(self) -> None:
        tool = self.engine.create_tool("tool1", "Action")
        result = self.engine.get_tool(tool.tool_id)
        assert result is not None
        assert result.tool_id == tool.tool_id

    def test_get_tool_not_found(self) -> None:
        with pytest.raises(AgentToolsEngineError) as exc_info:
            self.engine.get_tool("at-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_tools(self) -> None:
        self.engine.create_tool("tool1", "Action")
        self.engine.create_tool("tool2", "Query")
        tools = self.engine.list_tools()
        assert len(tools) == 2

    def test_list_tools_by_type(self) -> None:
        self.engine.create_tool("tool1", "Action")
        self.engine.create_tool("tool2", "Action")
        self.engine.create_tool("tool3", "Query")
        tools = self.engine.list_tools(tool_type="Action")
        assert len(tools) == 2

    def test_execute_tool(self) -> None:
        tool = self.engine.create_tool("tool1", "Action")
        result = self.engine.execute_tool(tool.tool_id, "user1")
        assert result is not None

    def test_execute_tool_not_found(self) -> None:
        with pytest.raises(AgentToolsEngineError) as exc_info:
            self.engine.execute_tool("at-nonexistent", "user1")
        assert exc_info.value.code == "NOT_FOUND"

    def test_get_tool_types(self) -> None:
        types = self.engine.get_tool_types()
        assert len(types) == 6
        assert "Action" in types
        assert "Query" in types
        assert "Function" in types
        assert "Var" in types
        assert "Command" in types
        assert "Clarify" in types

    def test_update_tool_success(self) -> None:
        tool = self.engine.create_tool("tool1", "Action")
        updated = self.engine.update_tool(tool.tool_id, description="updated")
        assert updated.description == "updated"

    def test_update_tool_not_found(self) -> None:
        with pytest.raises(AgentToolsEngineError) as exc_info:
            self.engine.update_tool("at-nonexistent", description="updated")
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_tool_success(self) -> None:
        tool = self.engine.create_tool("tool1", "Action")
        result = self.engine.delete_tool(tool.tool_id)
        assert result is True

    def test_delete_tool_not_found(self) -> None:
        result = self.engine.delete_tool("at-nonexistent")
        assert result is False

    def test_fifo_eviction(self) -> None:
        for i in range(_MAX_ENTRIES + 5):
            self.engine.create_tool(f"tool{i}", "Action")
        assert len(self.engine.list_tools()) == _MAX_ENTRIES

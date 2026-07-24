"""W2-AY · Connection CDC + Schedule + Storage Route 单元测试。"""
from __future__ import annotations

import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.connection_cdc_schedule import (
    ConnectionCdcEngine,
    ScheduleTriggerEngine,
    StorageRouteGuideEngine,
    CdcConfigError,
    ScheduleTriggerError,
    StorageRouteError,
)

app = FastAPI()


class TestConnectionCdcEngine:
    def setup_method(self):
        ConnectionCdcEngine._instance = None
        ConnectionCdcEngine._lock = threading.Lock()

    def test_configure_cdc_success(self):
        engine = ConnectionCdcEngine()
        cdc = engine.configure_cdc(connection_id="conn-1", capture_mode="incremental")
        assert cdc.cdc_id.startswith("cdc-")
        assert cdc.connection_id == "conn-1"
        assert cdc.capture_mode == "incremental"

    def test_configure_cdc_missing_connection(self):
        engine = ConnectionCdcEngine()
        with pytest.raises(CdcConfigError) as exc_info:
            engine.configure_cdc(connection_id="")
        assert exc_info.value.code == "MISSING_CONNECTION"

    def test_configure_cdc_invalid_capture_mode(self):
        engine = ConnectionCdcEngine()
        with pytest.raises(CdcConfigError) as exc_info:
            engine.configure_cdc(connection_id="conn-1", capture_mode="invalid")
        assert exc_info.value.code == "INVALID_CAPTURE_MODE"

    def test_get_cdc_success(self):
        engine = ConnectionCdcEngine()
        cdc = engine.configure_cdc(connection_id="conn-1")
        retrieved = engine.get_cdc(cdc.cdc_id)
        assert retrieved.cdc_id == cdc.cdc_id

    def test_get_cdc_not_found(self):
        engine = ConnectionCdcEngine()
        with pytest.raises(CdcConfigError) as exc_info:
            engine.get_cdc("nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_cdc_empty(self):
        engine = ConnectionCdcEngine()
        result = engine.list_cdc()
        assert len(result) == 0

    def test_list_cdc_with_items(self):
        engine = ConnectionCdcEngine()
        engine.configure_cdc(connection_id="conn-1")
        engine.configure_cdc(connection_id="conn-2")
        result = engine.list_cdc()
        assert len(result) == 2

    def test_list_cdc_filter_by_connection_id(self):
        engine = ConnectionCdcEngine()
        engine.configure_cdc(connection_id="conn-1")
        engine.configure_cdc(connection_id="conn-2")
        result = engine.list_cdc(connection_id="conn-1")
        assert len(result) == 1
        assert result[0].connection_id == "conn-1"

    def test_list_cdc_filter_by_status(self):
        engine = ConnectionCdcEngine()
        engine.configure_cdc(connection_id="conn-1", enabled=True)
        engine.configure_cdc(connection_id="conn-2", enabled=False)
        result = engine.list_cdc(status="running")
        assert len(result) == 1
        assert result[0].connection_id == "conn-1"

    def test_list_cdc_invalid_status(self):
        engine = ConnectionCdcEngine()
        with pytest.raises(CdcConfigError) as exc_info:
            engine.list_cdc(status="invalid")
        assert exc_info.value.code == "INVALID_STATUS"

    def test_update_cdc_success(self):
        engine = ConnectionCdcEngine()
        cdc = engine.configure_cdc(connection_id="conn-1")
        updated = engine.update_cdc(cdc.cdc_id, enabled=False)
        assert updated.enabled is False
        assert updated.status == "stopped"

    def test_update_cdc_not_found(self):
        engine = ConnectionCdcEngine()
        with pytest.raises(CdcConfigError) as exc_info:
            engine.update_cdc("nonexistent", enabled=False)
        assert exc_info.value.code == "NOT_FOUND"

    def test_update_cdc_invalid_capture_mode(self):
        engine = ConnectionCdcEngine()
        cdc = engine.configure_cdc(connection_id="conn-1")
        with pytest.raises(CdcConfigError) as exc_info:
            engine.update_cdc(cdc.cdc_id, capture_mode="invalid")
        assert exc_info.value.code == "INVALID_CAPTURE_MODE"

    def test_delete_cdc_success(self):
        engine = ConnectionCdcEngine()
        cdc = engine.configure_cdc(connection_id="conn-1")
        result = engine.delete_cdc(cdc.cdc_id)
        assert result is True

    def test_delete_cdc_not_found(self):
        engine = ConnectionCdcEngine()
        result = engine.delete_cdc("nonexistent")
        assert result is False

    def test_toggle_cdc_success(self):
        engine = ConnectionCdcEngine()
        cdc = engine.configure_cdc(connection_id="conn-1", enabled=True)
        toggled = engine.toggle_cdc(cdc.cdc_id, enabled=False)
        assert toggled.enabled is False

    def test_toggle_cdc_not_found(self):
        engine = ConnectionCdcEngine()
        with pytest.raises(CdcConfigError) as exc_info:
            engine.toggle_cdc("nonexistent", enabled=False)
        assert exc_info.value.code == "NOT_FOUND"

    def test_cdc_200_limit_eviction(self):
        engine = ConnectionCdcEngine()
        for i in range(201):
            engine.configure_cdc(connection_id=f"conn-{i}")
        assert len(engine._cdc_configs) == 200


class TestScheduleTriggerEngine:
    def setup_method(self):
        ScheduleTriggerEngine._instance = None
        ScheduleTriggerEngine._lock = threading.Lock()

    def test_create_trigger_success(self):
        engine = ScheduleTriggerEngine()
        trigger = engine.create_trigger(name="test-trigger", cron_expression="0 9 * * *")
        assert trigger.trigger_id.startswith("str-")
        assert trigger.name == "test-trigger"

    def test_create_trigger_missing_name(self):
        engine = ScheduleTriggerEngine()
        with pytest.raises(ScheduleTriggerError) as exc_info:
            engine.create_trigger(name="", cron_expression="0 9 * * *")
        assert exc_info.value.code == "MISSING_NAME"

    def test_create_trigger_invalid_cron(self):
        engine = ScheduleTriggerEngine()
        with pytest.raises(ScheduleTriggerError) as exc_info:
            engine.create_trigger(name="test", cron_expression="invalid")
        assert exc_info.value.code == "INVALID_CRON"

    def test_create_trigger_invalid_target_type(self):
        engine = ScheduleTriggerEngine()
        with pytest.raises(ScheduleTriggerError) as exc_info:
            engine.create_trigger(name="test", cron_expression="0 9 * * *", target_type="invalid")
        assert exc_info.value.code == "INVALID_TARGET_TYPE"

    def test_get_trigger_success(self):
        engine = ScheduleTriggerEngine()
        trigger = engine.create_trigger(name="test", cron_expression="0 9 * * *")
        retrieved = engine.get_trigger(trigger.trigger_id)
        assert retrieved.trigger_id == trigger.trigger_id

    def test_get_trigger_not_found(self):
        engine = ScheduleTriggerEngine()
        with pytest.raises(ScheduleTriggerError) as exc_info:
            engine.get_trigger("nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_triggers_empty(self):
        engine = ScheduleTriggerEngine()
        result = engine.list_triggers()
        assert len(result) == 0

    def test_list_triggers_with_items(self):
        engine = ScheduleTriggerEngine()
        engine.create_trigger(name="t1", cron_expression="0 9 * * *")
        engine.create_trigger(name="t2", cron_expression="0 10 * * *")
        result = engine.list_triggers()
        assert len(result) == 2

    def test_list_triggers_filter_by_name(self):
        engine = ScheduleTriggerEngine()
        engine.create_trigger(name="t1", cron_expression="0 9 * * *")
        engine.create_trigger(name="t2", cron_expression="0 10 * * *")
        result = engine.list_triggers(name="t1")
        assert len(result) == 1
        assert result[0].name == "t1"

    def test_list_triggers_filter_by_target_type(self):
        engine = ScheduleTriggerEngine()
        engine.create_trigger(name="t1", cron_expression="0 9 * * *", target_type="pipeline")
        engine.create_trigger(name="t2", cron_expression="0 10 * * *", target_type="workflow")
        result = engine.list_triggers(target_type="pipeline")
        assert len(result) == 1
        assert result[0].target_type == "pipeline"

    def test_list_triggers_filter_by_status(self):
        engine = ScheduleTriggerEngine()
        engine.create_trigger(name="t1", cron_expression="0 9 * * *", enabled=True)
        engine.create_trigger(name="t2", cron_expression="0 10 * * *", enabled=False)
        result = engine.list_triggers(status="active")
        assert len(result) == 1
        assert result[0].name == "t1"

    def test_list_triggers_invalid_target_type(self):
        engine = ScheduleTriggerEngine()
        with pytest.raises(ScheduleTriggerError) as exc_info:
            engine.list_triggers(target_type="invalid")
        assert exc_info.value.code == "INVALID_TARGET_TYPE"

    def test_list_triggers_invalid_status(self):
        engine = ScheduleTriggerEngine()
        with pytest.raises(ScheduleTriggerError) as exc_info:
            engine.list_triggers(status="invalid")
        assert exc_info.value.code == "INVALID_STATUS"

    def test_update_trigger_success(self):
        engine = ScheduleTriggerEngine()
        trigger = engine.create_trigger(name="t1", cron_expression="0 9 * * *")
        updated = engine.update_trigger(trigger.trigger_id, name="updated")
        assert updated.name == "updated"

    def test_update_trigger_not_found(self):
        engine = ScheduleTriggerEngine()
        with pytest.raises(ScheduleTriggerError) as exc_info:
            engine.update_trigger("nonexistent", name="updated")
        assert exc_info.value.code == "NOT_FOUND"

    def test_update_trigger_missing_name(self):
        engine = ScheduleTriggerEngine()
        trigger = engine.create_trigger(name="t1", cron_expression="0 9 * * *")
        with pytest.raises(ScheduleTriggerError) as exc_info:
            engine.update_trigger(trigger.trigger_id, name="")
        assert exc_info.value.code == "MISSING_NAME"

    def test_update_trigger_invalid_cron(self):
        engine = ScheduleTriggerEngine()
        trigger = engine.create_trigger(name="t1", cron_expression="0 9 * * *")
        with pytest.raises(ScheduleTriggerError) as exc_info:
            engine.update_trigger(trigger.trigger_id, cron_expression="invalid")
        assert exc_info.value.code == "INVALID_CRON"

    def test_update_trigger_invalid_target_type(self):
        engine = ScheduleTriggerEngine()
        trigger = engine.create_trigger(name="t1", cron_expression="0 9 * * *")
        with pytest.raises(ScheduleTriggerError) as exc_info:
            engine.update_trigger(trigger.trigger_id, target_type="invalid")
        assert exc_info.value.code == "INVALID_TARGET_TYPE"

    def test_delete_trigger_success(self):
        engine = ScheduleTriggerEngine()
        trigger = engine.create_trigger(name="t1", cron_expression="0 9 * * *")
        result = engine.delete_trigger(trigger.trigger_id)
        assert result is True

    def test_delete_trigger_not_found(self):
        engine = ScheduleTriggerEngine()
        result = engine.delete_trigger("nonexistent")
        assert result is False

    def test_toggle_trigger_success(self):
        engine = ScheduleTriggerEngine()
        trigger = engine.create_trigger(name="t1", cron_expression="0 9 * * *", enabled=True)
        toggled = engine.toggle_trigger(trigger.trigger_id, enabled=False)
        assert toggled.enabled is False

    def test_toggle_trigger_not_found(self):
        engine = ScheduleTriggerEngine()
        with pytest.raises(ScheduleTriggerError) as exc_info:
            engine.toggle_trigger("nonexistent", enabled=False)
        assert exc_info.value.code == "NOT_FOUND"

    def test_trigger_200_limit(self):
        engine = ScheduleTriggerEngine()
        for i in range(201):
            engine.create_trigger(name=f"t{i}", cron_expression="0 9 * * *")
        assert len(engine._triggers) == 200


class TestStorageRouteGuideEngine:
    def setup_method(self):
        StorageRouteGuideEngine._instance = None
        StorageRouteGuideEngine._lock = threading.Lock()

    def test_create_route_success(self):
        engine = StorageRouteGuideEngine()
        route = engine.create_route(name="test-route", source_path="/src", target_path="/dst")
        assert route.route_id.startswith("srg-")
        assert route.name == "test-route"

    def test_create_route_missing_name(self):
        engine = StorageRouteGuideEngine()
        with pytest.raises(StorageRouteError) as exc_info:
            engine.create_route(name="", source_path="/src", target_path="/dst")
        assert exc_info.value.code == "MISSING_NAME"

    def test_create_route_missing_source_path(self):
        engine = StorageRouteGuideEngine()
        with pytest.raises(StorageRouteError) as exc_info:
            engine.create_route(name="test", source_path="", target_path="/dst")
        assert exc_info.value.code == "MISSING_SOURCE_PATH"

    def test_create_route_missing_target_path(self):
        engine = StorageRouteGuideEngine()
        with pytest.raises(StorageRouteError) as exc_info:
            engine.create_route(name="test", source_path="/src", target_path="")
        assert exc_info.value.code == "MISSING_TARGET_PATH"

    def test_create_route_invalid_route_type(self):
        engine = StorageRouteGuideEngine()
        with pytest.raises(StorageRouteError) as exc_info:
            engine.create_route(name="test", source_path="/src", target_path="/dst", route_type="invalid")
        assert exc_info.value.code == "INVALID_ROUTE_TYPE"

    def test_create_route_invalid_schedule_type(self):
        engine = StorageRouteGuideEngine()
        with pytest.raises(StorageRouteError) as exc_info:
            engine.create_route(name="test", source_path="/src", target_path="/dst", schedule_type="invalid")
        assert exc_info.value.code == "INVALID_SCHEDULE_TYPE"

    def test_get_route_success(self):
        engine = StorageRouteGuideEngine()
        route = engine.create_route(name="test", source_path="/src", target_path="/dst")
        retrieved = engine.get_route(route.route_id)
        assert retrieved.route_id == route.route_id

    def test_get_route_not_found(self):
        engine = StorageRouteGuideEngine()
        with pytest.raises(StorageRouteError) as exc_info:
            engine.get_route("nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_routes_empty(self):
        engine = StorageRouteGuideEngine()
        result = engine.list_routes()
        assert len(result) == 0

    def test_list_routes_with_items(self):
        engine = StorageRouteGuideEngine()
        engine.create_route(name="r1", source_path="/src1", target_path="/dst1")
        engine.create_route(name="r2", source_path="/src2", target_path="/dst2")
        result = engine.list_routes()
        assert len(result) == 2

    def test_list_routes_filter_by_name(self):
        engine = StorageRouteGuideEngine()
        engine.create_route(name="r1", source_path="/src1", target_path="/dst1")
        engine.create_route(name="r2", source_path="/src2", target_path="/dst2")
        result = engine.list_routes(name="r1")
        assert len(result) == 1
        assert result[0].name == "r1"

    def test_list_routes_filter_by_route_type(self):
        engine = StorageRouteGuideEngine()
        engine.create_route(name="r1", source_path="/src1", target_path="/dst1", route_type="copy")
        engine.create_route(name="r2", source_path="/src2", target_path="/dst2", route_type="move")
        result = engine.list_routes(route_type="copy")
        assert len(result) == 1
        assert result[0].route_type == "copy"

    def test_list_routes_filter_by_schedule_type(self):
        engine = StorageRouteGuideEngine()
        engine.create_route(name="r1", source_path="/src1", target_path="/dst1", schedule_type="on_demand")
        engine.create_route(name="r2", source_path="/src2", target_path="/dst2", schedule_type="periodic")
        result = engine.list_routes(schedule_type="on_demand")
        assert len(result) == 1
        assert result[0].schedule_type == "on_demand"

    def test_list_routes_filter_by_status(self):
        engine = StorageRouteGuideEngine()
        engine.create_route(name="r1", source_path="/src1", target_path="/dst1", enabled=True)
        engine.create_route(name="r2", source_path="/src2", target_path="/dst2", enabled=False)
        result = engine.list_routes(status="active")
        assert len(result) == 1
        assert result[0].name == "r1"

    def test_list_routes_invalid_route_type(self):
        engine = StorageRouteGuideEngine()
        with pytest.raises(StorageRouteError) as exc_info:
            engine.list_routes(route_type="invalid")
        assert exc_info.value.code == "INVALID_ROUTE_TYPE"

    def test_list_routes_invalid_schedule_type(self):
        engine = StorageRouteGuideEngine()
        with pytest.raises(StorageRouteError) as exc_info:
            engine.list_routes(schedule_type="invalid")
        assert exc_info.value.code == "INVALID_SCHEDULE_TYPE"

    def test_list_routes_invalid_status(self):
        engine = StorageRouteGuideEngine()
        with pytest.raises(StorageRouteError) as exc_info:
            engine.list_routes(status="invalid")
        assert exc_info.value.code == "INVALID_STATUS"

    def test_update_route_success(self):
        engine = StorageRouteGuideEngine()
        route = engine.create_route(name="r1", source_path="/src", target_path="/dst")
        updated = engine.update_route(route.route_id, name="updated")
        assert updated.name == "updated"

    def test_update_route_not_found(self):
        engine = StorageRouteGuideEngine()
        with pytest.raises(StorageRouteError) as exc_info:
            engine.update_route("nonexistent", name="updated")
        assert exc_info.value.code == "NOT_FOUND"

    def test_update_route_missing_name(self):
        engine = StorageRouteGuideEngine()
        route = engine.create_route(name="r1", source_path="/src", target_path="/dst")
        with pytest.raises(StorageRouteError) as exc_info:
            engine.update_route(route.route_id, name="")
        assert exc_info.value.code == "MISSING_NAME"

    def test_update_route_missing_source_path(self):
        engine = StorageRouteGuideEngine()
        route = engine.create_route(name="r1", source_path="/src", target_path="/dst")
        with pytest.raises(StorageRouteError) as exc_info:
            engine.update_route(route.route_id, source_path="")
        assert exc_info.value.code == "MISSING_SOURCE_PATH"

    def test_update_route_missing_target_path(self):
        engine = StorageRouteGuideEngine()
        route = engine.create_route(name="r1", source_path="/src", target_path="/dst")
        with pytest.raises(StorageRouteError) as exc_info:
            engine.update_route(route.route_id, target_path="")
        assert exc_info.value.code == "MISSING_TARGET_PATH"

    def test_update_route_invalid_route_type(self):
        engine = StorageRouteGuideEngine()
        route = engine.create_route(name="r1", source_path="/src", target_path="/dst")
        with pytest.raises(StorageRouteError) as exc_info:
            engine.update_route(route.route_id, route_type="invalid")
        assert exc_info.value.code == "INVALID_ROUTE_TYPE"

    def test_update_route_invalid_schedule_type(self):
        engine = StorageRouteGuideEngine()
        route = engine.create_route(name="r1", source_path="/src", target_path="/dst")
        with pytest.raises(StorageRouteError) as exc_info:
            engine.update_route(route.route_id, schedule_type="invalid")
        assert exc_info.value.code == "INVALID_SCHEDULE_TYPE"

    def test_delete_route_success(self):
        engine = StorageRouteGuideEngine()
        route = engine.create_route(name="r1", source_path="/src", target_path="/dst")
        result = engine.delete_route(route.route_id)
        assert result is True

    def test_delete_route_not_found(self):
        engine = StorageRouteGuideEngine()
        result = engine.delete_route("nonexistent")
        assert result is False

    def test_execute_route_success(self):
        engine = StorageRouteGuideEngine()
        route = engine.create_route(name="r1", source_path="/src", target_path="/dst", enabled=True)
        executed = engine.execute_route(route.route_id)
        assert executed.status == "completed"
        assert executed.last_run_at is not None

    def test_execute_route_not_found(self):
        engine = StorageRouteGuideEngine()
        with pytest.raises(StorageRouteError) as exc_info:
            engine.execute_route("nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_route_200_limit(self):
        engine = StorageRouteGuideEngine()
        for i in range(201):
            engine.create_route(name=f"r{i}", source_path="/src", target_path="/dst")
        assert len(engine._routes) == 200
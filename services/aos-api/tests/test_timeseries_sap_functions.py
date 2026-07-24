"""W2-AS · TimeSeries SAP Functions 组测试（#164 / #165 / #166）.

覆盖 TimeSeriesEngine / SapIntegrationEngine / PbFunctionsEngine 三引擎。
"""
from __future__ import annotations

import pytest

from aos_api.timeseries_sap_functions import (
    PbFunction,
    PbFunctionCategory,
    PbFunctionsEngine,
    PbFunctionsError,
    SapConnection,
    SapImportJob,
    SapIntegrationEngine,
    SapIntegrationError,
    Sensor,
    TimeSeriesEngine,
    TimeSeriesError,
    TimeSeriesObject,
    TimeSeriesPoint,
    get_pb_functions_engine,
    get_sap_integration_engine,
    get_time_series_engine,
)


# ════════════════════ TimeSeriesEngine (#164) ════════════════════

class TestTimeSeries:
    def setup_method(self) -> None:
        self.eng = TimeSeriesEngine()
        self.eng._objects = {}
        self.eng._sensors = {}
        self.eng._points = []

    # ── TS Object ──

    def test_register_object(self) -> None:
        obj = self.eng.register_object(TimeSeriesObject(name="obj1"))
        assert obj.ts_id.startswith("ts-")
        assert obj.name == "obj1"
        assert obj.sync_index_status == "pending"
        assert obj.created_at is not None

    def test_get_object(self) -> None:
        obj = self.eng.register_object(TimeSeriesObject(name="obj1"))
        fetched = self.eng.get_object(obj.ts_id)
        assert fetched.ts_id == obj.ts_id
        assert fetched.name == "obj1"

    def test_list_objects(self) -> None:
        self.eng.register_object(TimeSeriesObject(name="obj1"))
        self.eng.register_object(TimeSeriesObject(name="obj2"))
        assert len(self.eng.list_objects()) == 2

    def test_list_objects_filter_type(self) -> None:
        self.eng.register_object(TimeSeriesObject(name="o1", object_type="TSP"))
        self.eng.register_object(TimeSeriesObject(name="o2", object_type="sensor"))
        tsp = self.eng.list_objects(object_type="TSP")
        assert len(tsp) == 1
        assert tsp[0].object_type == "TSP"

    def test_update_object(self) -> None:
        obj = self.eng.register_object(TimeSeriesObject(name="obj1"))
        updated = self.eng.update_object(obj.ts_id, {"description": "new desc"})
        assert updated.description == "new desc"
        assert updated.updated_at is not None

    def test_delete_object(self) -> None:
        obj = self.eng.register_object(TimeSeriesObject(name="obj1"))
        self.eng.delete_object(obj.ts_id)
        with pytest.raises(TimeSeriesError) as exc:
            self.eng.get_object(obj.ts_id)
        assert exc.value.code == "NOT_FOUND"

    def test_build_sync_index(self) -> None:
        obj = self.eng.register_object(TimeSeriesObject(name="obj1"))
        built = self.eng.build_sync_index(obj.ts_id)
        assert built.sync_index_status == "built"

    def test_invalid_object_type(self) -> None:
        with pytest.raises(TimeSeriesError) as exc:
            self.eng.register_object(TimeSeriesObject(name="o1", object_type="bad"))
        assert exc.value.code == "INVALID_OBJECT_TYPE"

    # ── Sensor ──

    def test_register_sensor(self) -> None:
        s = self.eng.register_sensor(Sensor(name="s1", ts_object_id="ts-1"))
        assert s.sensor_id.startswith("sensor-")
        assert s.name == "s1"
        assert s.ts_object_id == "ts-1"
        assert s.created_at is not None

    def test_get_sensor(self) -> None:
        s = self.eng.register_sensor(Sensor(name="s1", ts_object_id="ts-1"))
        fetched = self.eng.get_sensor(s.sensor_id)
        assert fetched.sensor_id == s.sensor_id
        assert fetched.name == "s1"

    def test_list_sensors(self) -> None:
        self.eng.register_sensor(Sensor(name="s1", ts_object_id="ts-1"))
        self.eng.register_sensor(Sensor(name="s2", ts_object_id="ts-1"))
        self.eng.register_sensor(Sensor(name="s3", ts_object_id="ts-2"))
        items = self.eng.list_sensors(ts_object_id="ts-1")
        assert len(items) == 2
        for s in items:
            assert s.ts_object_id == "ts-1"

    def test_update_sensor(self) -> None:
        s = self.eng.register_sensor(Sensor(name="s1", ts_object_id="ts-1"))
        updated = self.eng.update_sensor(s.sensor_id, {"unit": "Celsius"})
        assert updated.unit == "Celsius"

    def test_delete_sensor(self) -> None:
        s = self.eng.register_sensor(Sensor(name="s1", ts_object_id="ts-1"))
        self.eng.delete_sensor(s.sensor_id)
        with pytest.raises(TimeSeriesError) as exc:
            self.eng.get_sensor(s.sensor_id)
        assert exc.value.code == "NOT_FOUND"

    def test_invalid_data_type(self) -> None:
        with pytest.raises(TimeSeriesError) as exc:
            self.eng.register_sensor(
                Sensor(name="s1", ts_object_id="ts-1", data_type="bad")
            )
        assert exc.value.code == "INVALID_DATA_TYPE"

    def test_missing_ts_object(self) -> None:
        with pytest.raises(TimeSeriesError) as exc:
            self.eng.register_sensor(Sensor(name="s1", ts_object_id=""))
        assert exc.value.code == "MISSING_TS_OBJECT"

    # ── Points ──

    def test_ingest_points(self) -> None:
        s = self.eng.register_sensor(Sensor(name="s1", ts_object_id="ts-1"))
        pts = self.eng.ingest_points(s.sensor_id, [1.0, 2.0, 3.0])
        assert len(pts) == 3
        for p in pts:
            assert p.point_id.startswith("pt-")
            assert p.sensor_id == s.sensor_id
            assert p.timestamp is not None
        assert [p.value for p in pts] == [1.0, 2.0, 3.0]

    def test_list_points(self) -> None:
        s = self.eng.register_sensor(Sensor(name="s1", ts_object_id="ts-1"))
        self.eng.ingest_points(s.sensor_id, [1.0, 2.0, 3.0])
        items = self.eng.list_points(s.sensor_id)
        assert len(items) == 3
        # 按 timestamp desc
        assert items[0].timestamp >= items[1].timestamp >= items[2].timestamp

    def test_get_latest_point(self) -> None:
        s = self.eng.register_sensor(Sensor(name="s1", ts_object_id="ts-1"))
        self.eng.ingest_points(s.sensor_id, [1.0, 2.0, 3.0])
        latest = self.eng.get_latest_point(s.sensor_id)
        assert latest is not None
        # 所有点共享同一 timestamp，latest 应为其中之一
        assert latest.value in (1.0, 2.0, 3.0)

    def test_get_latest_point_empty(self) -> None:
        s = self.eng.register_sensor(Sensor(name="s1", ts_object_id="ts-1"))
        latest = self.eng.get_latest_point(s.sensor_id)
        assert latest is None

    def test_ingest_points_sensor_not_found(self) -> None:
        with pytest.raises(TimeSeriesError) as exc:
            self.eng.ingest_points("sensor-nonexist", [1.0])
        assert exc.value.code == "NOT_FOUND"

    # ── 边界 ──

    def test_not_found_get_object(self) -> None:
        with pytest.raises(TimeSeriesError) as exc:
            self.eng.get_object("nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_max_objects_eviction(self) -> None:
        from aos_api.timeseries_sap_functions import _MAX_TS_OBJECTS
        for i in range(_MAX_TS_OBJECTS + 5):
            self.eng.register_object(TimeSeriesObject(name=f"obj{i}"))
        assert len(self.eng._objects) == _MAX_TS_OBJECTS


# ════════════════════ SapIntegrationEngine (#165) ════════════════════

class TestSapIntegration:
    def setup_method(self) -> None:
        self.eng = SapIntegrationEngine()
        self.eng._connections = {}
        self.eng._jobs = {}

    # ── Connection ──

    def test_register_connection(self) -> None:
        conn = self.eng.register_connection(SapConnection(name="c1", host="h1"))
        assert conn.conn_id.startswith("sap-")
        assert conn.name == "c1"
        assert conn.status == "disconnected"
        assert conn.created_at is not None

    def test_get_connection(self) -> None:
        conn = self.eng.register_connection(SapConnection(name="c1", host="h1"))
        fetched = self.eng.get_connection(conn.conn_id)
        assert fetched.conn_id == conn.conn_id
        assert fetched.name == "c1"

    def test_list_connections(self) -> None:
        self.eng.register_connection(SapConnection(name="c1", host="h1", system_type="S4HANA"))
        self.eng.register_connection(SapConnection(name="c2", host="h2", system_type="ECC"))
        self.eng.register_connection(SapConnection(name="c3", host="h3", system_type="S4HANA"))
        s4 = self.eng.list_connections(system_type="S4HANA")
        assert len(s4) == 2
        for c in s4:
            assert c.system_type == "S4HANA"

    def test_update_connection(self) -> None:
        conn = self.eng.register_connection(SapConnection(name="c1", host="h1"))
        updated = self.eng.update_connection(conn.conn_id, {"username": "alice"})
        assert updated.username == "alice"
        assert updated.updated_at is not None

    def test_delete_connection(self) -> None:
        conn = self.eng.register_connection(SapConnection(name="c1", host="h1"))
        self.eng.delete_connection(conn.conn_id)
        with pytest.raises(SapIntegrationError) as exc:
            self.eng.get_connection(conn.conn_id)
        assert exc.value.code == "NOT_FOUND"

    def test_test_connection(self) -> None:
        conn = self.eng.register_connection(SapConnection(name="c1", host="h1"))
        tested = self.eng.test_connection(conn.conn_id)
        assert tested.status == "connected"

    def test_invalid_system_type(self) -> None:
        with pytest.raises(SapIntegrationError) as exc:
            self.eng.register_connection(
                SapConnection(name="c1", host="h1", system_type="bad")
            )
        assert exc.value.code == "INVALID_SYSTEM_TYPE"

    def test_missing_host(self) -> None:
        with pytest.raises(SapIntegrationError) as exc:
            self.eng.register_connection(SapConnection(name="c1", host=""))
        assert exc.value.code == "MISSING_HOST"

    # ── Import Job ──

    def test_create_import_job(self) -> None:
        job = self.eng.create_import_job(
            SapImportJob(conn_id="sap-1", source_object="MARA")
        )
        assert job.job_id.startswith("sapjob-")
        assert job.status == "pending"
        assert job.created_at is not None

    def test_get_import_job(self) -> None:
        job = self.eng.create_import_job(
            SapImportJob(conn_id="sap-1", source_object="MARA")
        )
        fetched = self.eng.get_import_job(job.job_id)
        assert fetched.job_id == job.job_id
        assert fetched.source_object == "MARA"

    def test_list_import_jobs(self) -> None:
        self.eng.create_import_job(SapImportJob(conn_id="sap-1", source_object="M1"))
        self.eng.create_import_job(SapImportJob(conn_id="sap-1", source_object="M2"))
        self.eng.create_import_job(SapImportJob(conn_id="sap-2", source_object="M3"))
        items = self.eng.list_import_jobs(conn_id="sap-1")
        assert len(items) == 2
        for j in items:
            assert j.conn_id == "sap-1"

    def test_run_import_job(self) -> None:
        job = self.eng.create_import_job(
            SapImportJob(conn_id="sap-1", source_object="MARA")
        )
        run = self.eng.run_import_job(job.job_id)
        assert run.status == "completed"
        assert run.imported_rows == 100
        assert run.total_rows == 100
        assert run.finished_at is not None

    def test_cancel_import_job(self) -> None:
        job = self.eng.create_import_job(
            SapImportJob(conn_id="sap-1", source_object="MARA")
        )
        cancelled = self.eng.cancel_import_job(job.job_id)
        assert cancelled.status == "failed"
        assert cancelled.error == "cancelled"
        assert cancelled.finished_at is not None

    def test_invalid_object_type_job(self) -> None:
        with pytest.raises(SapIntegrationError) as exc:
            self.eng.create_import_job(
                SapImportJob(conn_id="sap-1", source_object="MARA", object_type="bad")
            )
        assert exc.value.code == "INVALID_OBJECT_TYPE"

    def test_missing_source_object(self) -> None:
        with pytest.raises(SapIntegrationError) as exc:
            self.eng.create_import_job(
                SapImportJob(conn_id="sap-1", source_object="")
            )
        assert exc.value.code == "MISSING_SOURCE_OBJECT"

    def test_missing_connection(self) -> None:
        with pytest.raises(SapIntegrationError) as exc:
            self.eng.create_import_job(
                SapImportJob(conn_id="", source_object="MARA")
            )
        assert exc.value.code == "MISSING_CONNECTION"

    # ── 边界 ──

    def test_not_found_get_connection(self) -> None:
        with pytest.raises(SapIntegrationError) as exc:
            self.eng.get_connection("nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_max_connections_eviction(self) -> None:
        from aos_api.timeseries_sap_functions import _MAX_SAP_CONNECTIONS
        for i in range(_MAX_SAP_CONNECTIONS + 5):
            self.eng.register_connection(SapConnection(name=f"c{i}", host=f"h{i}"))
        assert len(self.eng._connections) == _MAX_SAP_CONNECTIONS


# ════════════════════ PbFunctionsEngine (#166) ════════════════════

class TestPbFunctions:
    def setup_method(self) -> None:
        self.eng = PbFunctionsEngine()
        self.eng._functions = {}
        self.eng._categories = {}

    # ── Function ──

    def test_register_function(self) -> None:
        f = self.eng.register_function(PbFunction(name="f1"))
        assert f.func_id.startswith("pbf-")
        assert f.name == "f1"
        assert f.created_at is not None

    def test_get_function(self) -> None:
        f = self.eng.register_function(PbFunction(name="f1"))
        fetched = self.eng.get_function(f.func_id)
        assert fetched.func_id == f.func_id
        assert fetched.name == "f1"

    def test_list_functions(self) -> None:
        self.eng.register_function(PbFunction(name="f1"))
        self.eng.register_function(PbFunction(name="f2"))
        assert len(self.eng.list_functions()) == 2

    def test_list_functions_filter_category(self) -> None:
        self.eng.register_function(PbFunction(name="f1", category="expression"))
        self.eng.register_function(PbFunction(name="f2", category="transform"))
        self.eng.register_function(PbFunction(name="f3", category="expression"))
        items = self.eng.list_functions(category="expression")
        assert len(items) == 2
        for f in items:
            assert f.category == "expression"

    def test_search_functions(self) -> None:
        self.eng.register_function(PbFunction(name="upper_case"))
        self.eng.register_function(PbFunction(name="lower"))
        results = self.eng.search_functions("upper")
        assert len(results) >= 1
        assert any("upper" in f.name for f in results)

    def test_search_functions_description(self) -> None:
        self.eng.register_function(
            PbFunction(name="f1", description="convert case for strings")
        )
        results = self.eng.search_functions("case")
        assert len(results) >= 1
        assert any("case" in (f.description or "") for f in results)

    def test_update_function(self) -> None:
        f = self.eng.register_function(PbFunction(name="f1"))
        updated = self.eng.update_function(f.func_id, {"description": "new desc"})
        assert updated.description == "new desc"
        assert updated.updated_at is not None

    def test_delete_function(self) -> None:
        f = self.eng.register_function(PbFunction(name="f1"))
        self.eng.delete_function(f.func_id)
        with pytest.raises(PbFunctionsError) as exc:
            self.eng.get_function(f.func_id)
        assert exc.value.code == "NOT_FOUND"

    def test_invalid_category(self) -> None:
        with pytest.raises(PbFunctionsError) as exc:
            self.eng.register_function(PbFunction(name="f1", category="bad"))
        assert exc.value.code == "INVALID_CATEGORY"

    # ── Category ──

    def test_register_category(self) -> None:
        c = self.eng.register_category(PbFunctionCategory(name="cat1"))
        assert c.category_id.startswith("pbcat-")
        assert c.name == "cat1"
        assert c.created_at is not None

    def test_get_category(self) -> None:
        c = self.eng.register_category(PbFunctionCategory(name="cat1"))
        fetched = self.eng.get_category(c.category_id)
        assert fetched.category_id == c.category_id
        assert fetched.name == "cat1"

    def test_list_categories(self) -> None:
        self.eng.register_category(PbFunctionCategory(name="c1"))
        self.eng.register_category(PbFunctionCategory(name="c2"))
        assert len(self.eng.list_categories()) == 2

    def test_delete_category(self) -> None:
        c = self.eng.register_category(PbFunctionCategory(name="cat1"))
        self.eng.delete_category(c.category_id)
        with pytest.raises(PbFunctionsError) as exc:
            self.eng.get_category(c.category_id)
        assert exc.value.code == "NOT_FOUND"

    def test_missing_name_category(self) -> None:
        with pytest.raises(PbFunctionsError) as exc:
            self.eng.register_category(PbFunctionCategory(name=""))
        assert exc.value.code == "MISSING_NAME"

    # ── 边界 ──

    def test_not_found_get_function(self) -> None:
        with pytest.raises(PbFunctionsError) as exc:
            self.eng.get_function("nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_max_functions_eviction(self) -> None:
        from aos_api.timeseries_sap_functions import _MAX_PB_FUNCTIONS
        for i in range(_MAX_PB_FUNCTIONS + 5):
            self.eng.register_function(PbFunction(name=f"f{i}"))
        assert len(self.eng._functions) == _MAX_PB_FUNCTIONS


# ════════════════════ Singletons ════════════════════

class TestSingletons:
    def test_time_series_singleton(self) -> None:
        a = get_time_series_engine()
        b = get_time_series_engine()
        assert a is b

    def test_sap_integration_singleton(self) -> None:
        a = get_sap_integration_engine()
        b = get_sap_integration_engine()
        assert a is b

    def test_pb_functions_singleton(self) -> None:
        a = get_pb_functions_engine()
        b = get_pb_functions_engine()
        assert a is b

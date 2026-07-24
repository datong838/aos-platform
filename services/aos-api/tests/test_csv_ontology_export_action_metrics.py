"""W2-BI · CSV / Ontology 导出 / 用量 / Action 指标 引擎测试.

覆盖四个引擎：
- CsvParsingEngine
- OntologyExchangeEngine
- OntologyUsageEngine
- ActionMetricsEngine
"""
from __future__ import annotations

import time

import pytest

from aos_api.csv_ontology_export_action_metrics import (
    CsvParsingEngine, CsvParseConfig, CsvParseResult,
    OntologyExchangeEngine, OntologyExportPackage, OntologyImportResult,
    OntologyUsageEngine, UsageRecord, UsageSummary,
    ActionMetricsEngine, ActionMetric, ActionMetricSummary,
    ExchangeMetricsError,
    get_csv_parsing_engine, get_ontology_exchange_engine,
    get_ontology_usage_engine, get_action_metrics_engine,
)


# ════════════════════ #1 CsvParsingEngine ════════════════════

class TestCsvParsingEngine:
    def setup_method(self):
        self.engine = CsvParsingEngine()

    def test_parse_dict_reader(self):
        content = "name,age,city\nAlice,30,Beijing\nBob,25,Shanghai\n"
        result = self.engine.parse(content, parser_type="dict_reader")
        assert result.parser_type == "dict_reader"
        assert result.headers == ["name", "age", "city"]
        assert result.row_count == 2
        assert result.rows[0]["name"] == "Alice"
        assert result.rows[0]["age"] == "30"
        assert result.rows[0]["city"] == "Beijing"
        assert result.rows[1]["name"] == "Bob"
        assert result.rows[1]["city"] == "Shanghai"

    def test_parse_csv_reader(self):
        content = "name,age,city\nAlice,30,Beijing\nBob,25,Shanghai\n"
        result = self.engine.parse(content, parser_type="csv_reader")
        assert result.parser_type == "csv_reader"
        # csv_reader 使用基于索引的键，且表头行也作为数据行
        assert result.headers == ["0", "1", "2"]
        assert result.row_count == 3  # 表头 + 2 数据行
        assert result.rows[0]["0"] == "name"
        assert result.rows[1]["0"] == "Alice"
        assert result.rows[2]["0"] == "Bob"

    def test_parse_pandas(self):
        content = "name,age\nAlice,30\nBob,25\n"
        result = self.engine.parse(content, parser_type="pandas")
        assert result.parser_type == "pandas"
        assert result.headers == ["name", "age"]
        assert result.row_count == 2
        assert result.rows[0] == {"name": "Alice", "age": "30"}
        assert result.rows[1] == {"name": "Bob", "age": "25"}

    def test_parse_text_dataframe(self):
        content = "x,y\n1,2\n3,4\n"
        result = self.engine.parse(content, parser_type="text_dataframe")
        assert result.parser_type == "text_dataframe"
        assert result.headers == ["x", "y"]
        assert result.row_count == 2
        assert result.rows[0] == {"x": "1", "y": "2"}
        assert result.rows[1] == {"x": "3", "y": "4"}

    def test_parse_with_config(self):
        content = "name;age\nAlice;30\nBob;25\n"
        cfg = CsvParseConfig(delimiter=";")
        result = self.engine.parse(content, config=cfg, parser_type="dict_reader")
        assert result.headers == ["name", "age"]
        assert result.row_count == 2
        assert result.rows[0]["name"] == "Alice"
        assert result.rows[0]["age"] == "30"
        assert result.config_used.delimiter == ";"

    def test_parse_skiprows(self):
        content = "name,age\nAlice,30\nBob,25\nCarol,40\n"
        cfg = CsvParseConfig(skiprows=1)
        result = self.engine.parse(content, config=cfg, parser_type="dict_reader")
        assert result.headers == ["name", "age"]
        assert result.row_count == 2
        assert result.rows[0]["name"] == "Bob"
        assert result.rows[1]["name"] == "Carol"

    def test_parse_max_rows(self):
        content = "name,age\nAlice,30\nBob,25\nCarol,40\nDave,50\n"
        cfg = CsvParseConfig(max_rows=2)
        result = self.engine.parse(content, config=cfg, parser_type="dict_reader")
        assert result.row_count == 2
        assert result.rows[0]["name"] == "Alice"
        assert result.rows[1]["name"] == "Bob"

    def test_parse_invalid_parser_type(self):
        with pytest.raises(ExchangeMetricsError) as exc_info:
            self.engine.parse("a,b\n1,2\n", parser_type="invalid_type")
        assert exc_info.value.code == "INVALID_PARSER_TYPE"

    def test_get_result(self):
        result = self.engine.parse("name,age\nAlice,30\n", parser_type="dict_reader")
        fetched = self.engine.get_result(result.id)
        assert fetched.id == result.id
        assert fetched.row_count == result.row_count
        assert fetched.headers == result.headers

    def test_get_result_not_found(self):
        with pytest.raises(ExchangeMetricsError) as exc_info:
            self.engine.get_result("nonexistent-id")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_results(self):
        r1 = self.engine.parse("a,b\n1,2\n", parser_type="dict_reader")
        r2 = self.engine.parse("a,b\n1,2\n", parser_type="csv_reader")
        all_results = self.engine.list_results()
        assert len(all_results) == 2
        dict_only = self.engine.list_results(parser_type="dict_reader")
        assert len(dict_only) == 1
        assert dict_only[0].id == r1.id
        csv_only = self.engine.list_results(parser_type="csv_reader")
        assert len(csv_only) == 1
        assert csv_only[0].id == r2.id

    def test_delete_result(self):
        result = self.engine.parse("a,b\n1,2\n", parser_type="dict_reader")
        assert self.engine.delete_result(result.id) is True
        with pytest.raises(ExchangeMetricsError) as exc_info:
            self.engine.get_result(result.id)
        assert exc_info.value.code == "NOT_FOUND"
        # 再次删除返回 False
        assert self.engine.delete_result(result.id) is False

    def test_fifo_eviction(self):
        max_results = CsvParsingEngine._MAX_RESULTS
        for _ in range(max_results + 5):
            self.engine.parse("a,b\n1,2\n", parser_type="dict_reader")
        all_results = self.engine.list_results()
        assert len(all_results) == max_results


# ════════════════════ #2 OntologyExchangeEngine ════════════════════

class TestOntologyExchangeEngine:
    def setup_method(self):
        self.engine = OntologyExchangeEngine()

    def test_export_ontology(self):
        package = self.engine.export_ontology(
            source_ontology_id="ont-1",
            object_types=[{"name": "WorkOrder"}],
            link_types=[{"name": "assignedTo"}],
            properties=[{"key": "status"}],
            metadata={"exporter": "test"},
        )
        assert package.id.startswith("oexp-")
        assert package.source_ontology_id == "ont-1"
        assert package.version == "1.0"
        assert len(package.object_types) == 1
        assert package.object_types[0]["name"] == "WorkOrder"
        assert len(package.link_types) == 1
        assert package.link_types[0]["name"] == "assignedTo"
        assert len(package.properties) == 1
        assert package.properties[0]["key"] == "status"
        assert package.metadata == {"exporter": "test"}
        assert package.created_at > 0

    def test_get_export(self):
        package = self.engine.export_ontology(source_ontology_id="ont-1")
        fetched = self.engine.get_export(package.id)
        assert fetched.id == package.id
        assert fetched.source_ontology_id == "ont-1"

    def test_get_export_not_found(self):
        with pytest.raises(ExchangeMetricsError) as exc_info:
            self.engine.get_export("nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_exports(self):
        self.engine.export_ontology(source_ontology_id="ont-1")
        self.engine.export_ontology(source_ontology_id="ont-2")
        self.engine.export_ontology(source_ontology_id="ont-1")
        all_exports = self.engine.list_exports()
        assert len(all_exports) == 3
        ont1 = self.engine.list_exports(source_ontology_id="ont-1")
        assert len(ont1) == 2
        assert all(p.source_ontology_id == "ont-1" for p in ont1)
        ont2 = self.engine.list_exports(source_ontology_id="ont-2")
        assert len(ont2) == 1

    def test_delete_export(self):
        package = self.engine.export_ontology(source_ontology_id="ont-1")
        assert self.engine.delete_export(package.id) is True
        with pytest.raises(ExchangeMetricsError):
            self.engine.get_export(package.id)
        assert self.engine.delete_export(package.id) is False

    def test_import_ontology(self):
        package = self.engine.export_ontology(
            source_ontology_id="ont-1",
            object_types=[{"name": "A"}, {"name": "B"}],
            link_types=[{"name": "L"}],
            properties=[{"k": "p1"}, {"k": "p2"}, {"k": "p3"}],
        )
        result = self.engine.import_ontology(package, target_ontology_id="ont-2")
        assert result.id.startswith("oimp-")
        assert result.target_ontology_id == "ont-2"
        assert result.imported_object_types == 2
        assert result.imported_link_types == 1
        assert result.imported_properties == 3
        assert result.skipped == []
        # overwrite=False 会产生一条 warning
        assert len(result.warnings) >= 1

    def test_get_list_delete_import(self):
        package = self.engine.export_ontology(
            source_ontology_id="ont-1",
            object_types=[{"name": "A"}],
        )
        result = self.engine.import_ontology(package, target_ontology_id="ont-2")
        # get_import
        fetched = self.engine.get_import(result.id)
        assert fetched.id == result.id
        assert fetched.target_ontology_id == "ont-2"
        # list_imports
        self.engine.import_ontology(package, target_ontology_id="ont-3")
        all_imports = self.engine.list_imports()
        assert len(all_imports) == 2
        ont2 = self.engine.list_imports(target_ontology_id="ont-2")
        assert len(ont2) == 1
        assert ont2[0].id == result.id
        # delete_import
        assert self.engine.delete_import(result.id) is True
        with pytest.raises(ExchangeMetricsError):
            self.engine.get_import(result.id)
        assert self.engine.delete_import(result.id) is False

    def test_fifo_eviction(self):
        max_records = OntologyExchangeEngine._MAX_RECORDS
        for _ in range(max_records + 5):
            self.engine.export_ontology(source_ontology_id="ont-x")
        all_exports = self.engine.list_exports()
        assert len(all_exports) == max_records


# ════════════════════ #3 OntologyUsageEngine ════════════════════

class TestOntologyUsageEngine:
    def setup_method(self):
        self.engine = OntologyUsageEngine()

    def test_record_usage(self):
        record = self.engine.record_usage(
            ontology_id="ont-1",
            resource_type="compute_seconds_vcpu",
            amount=3600.0,
            description="1 hour vCPU",
        )
        assert record.id.startswith("use-")
        assert record.ontology_id == "ont-1"
        assert record.resource_type == "compute_seconds_vcpu"
        assert record.amount == 3600.0
        assert record.description == "1 hour vCPU"
        assert record.recorded_at > 0

    def test_record_usage_invalid_resource_type(self):
        with pytest.raises(ExchangeMetricsError) as exc_info:
            self.engine.record_usage(
                ontology_id="ont-1",
                resource_type="invalid_type",
                amount=100.0,
            )
        assert exc_info.value.code == "INVALID_RESOURCE_TYPE"

    def test_record_usage_missing_ontology_id(self):
        with pytest.raises(ExchangeMetricsError) as exc_info:
            self.engine.record_usage(
                ontology_id="",
                resource_type="compute_seconds_vcpu",
                amount=100.0,
            )
        assert exc_info.value.code == "MISSING_ONTOLOGY_ID"

    def test_get_usage(self):
        record = self.engine.record_usage(
            ontology_id="ont-1",
            resource_type="compute_seconds_vcpu",
            amount=100.0,
        )
        fetched = self.engine.get_usage(record.id)
        assert fetched.id == record.id
        assert fetched.amount == 100.0
        assert fetched.ontology_id == "ont-1"

    def test_get_usage_not_found(self):
        with pytest.raises(ExchangeMetricsError) as exc_info:
            self.engine.get_usage("nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_usage(self):
        self.engine.record_usage(
            ontology_id="ont-1", resource_type="compute_seconds_vcpu", amount=100.0
        )
        self.engine.record_usage(
            ontology_id="ont-1", resource_type="storage_v1_gb", amount=50.0
        )
        self.engine.record_usage(
            ontology_id="ont-2", resource_type="compute_seconds_vcpu", amount=200.0
        )
        all_records = self.engine.list_usage()
        assert len(all_records) == 3
        # 按 ontology_id 过滤
        ont1 = self.engine.list_usage(ontology_id="ont-1")
        assert len(ont1) == 2
        # 按 resource_type 过滤
        vcpu = self.engine.list_usage(resource_type="compute_seconds_vcpu")
        assert len(vcpu) == 2
        # 同时过滤
        ont1_vcpu = self.engine.list_usage(
            ontology_id="ont-1", resource_type="compute_seconds_vcpu"
        )
        assert len(ont1_vcpu) == 1

    def test_get_summary(self):
        self.engine.record_usage(
            ontology_id="ont-1", resource_type="compute_seconds_vcpu", amount=3600.0
        )
        self.engine.record_usage(
            ontology_id="ont-1", resource_type="compute_seconds_gpu_t4", amount=1800.0
        )
        self.engine.record_usage(
            ontology_id="ont-1", resource_type="compute_seconds_gpu_v100", amount=900.0
        )
        self.engine.record_usage(
            ontology_id="ont-1", resource_type="compute_seconds_gpu_a10g", amount=450.0
        )
        self.engine.record_usage(
            ontology_id="ont-1", resource_type="storage_v1_gb", amount=100.0
        )
        self.engine.record_usage(
            ontology_id="ont-1", resource_type="storage_v2_gb", amount=200.0
        )
        # 另一个 ontology 的记录不应计入
        self.engine.record_usage(
            ontology_id="ont-2", resource_type="compute_seconds_vcpu", amount=999.0
        )
        summary = self.engine.get_summary("ont-1")
        assert summary.ontology_id == "ont-1"
        assert summary.total_compute_vcpu_seconds == 3600.0
        assert summary.total_compute_gpu_t4_seconds == 1800.0
        assert summary.total_compute_gpu_v100_seconds == 900.0
        assert summary.total_compute_gpu_a10g_seconds == 450.0
        assert summary.total_storage_v1_gb == 100.0
        assert summary.total_storage_v2_gb == 200.0
        # gb_month = v * (days_in_month / 30) = v * 1.0
        assert summary.gb_month_v1 == 100.0
        assert summary.gb_month_v2 == 200.0
        assert summary.record_count == 6
        assert summary.last_recorded_at > 0

    def test_get_summary_empty(self):
        summary = self.engine.get_summary("ont-empty")
        assert summary.ontology_id == "ont-empty"
        assert summary.total_compute_vcpu_seconds == 0
        assert summary.total_storage_v1_gb == 0
        assert summary.gb_month_v1 == 0
        assert summary.record_count == 0
        assert summary.last_recorded_at == 0

    def test_delete_usage(self):
        record = self.engine.record_usage(
            ontology_id="ont-1",
            resource_type="compute_seconds_vcpu",
            amount=100.0,
        )
        assert self.engine.delete_usage(record.id) is True
        with pytest.raises(ExchangeMetricsError):
            self.engine.get_usage(record.id)
        assert self.engine.delete_usage(record.id) is False

    def test_fifo_eviction(self):
        max_records = OntologyUsageEngine._MAX_RECORDS
        for _ in range(max_records + 5):
            self.engine.record_usage(
                ontology_id="ont-1",
                resource_type="compute_seconds_vcpu",
                amount=1.0,
            )
        all_records = self.engine.list_usage()
        assert len(all_records) == max_records


# ════════════════════ #4 ActionMetricsEngine ════════════════════

class TestActionMetricsEngine:
    def setup_method(self):
        self.engine = ActionMetricsEngine()

    def test_record_metric_success(self):
        metric = self.engine.record_metric(
            action_id="act-1",
            status="success",
            duration_ms=150.0,
            metadata={"route": "/api/v1"},
        )
        assert metric.id.startswith("am-")
        assert metric.action_id == "act-1"
        assert metric.status == "success"
        assert metric.duration_ms == 150.0
        assert metric.error_code == ""
        assert metric.metadata == {"route": "/api/v1"}
        assert metric.recorded_at > 0

    def test_record_metric_failure(self):
        metric = self.engine.record_metric(
            action_id="act-1",
            status="failure",
            duration_ms=300.0,
            error_code="TIMEOUT",
        )
        assert metric.status == "failure"
        assert metric.error_code == "TIMEOUT"
        assert metric.duration_ms == 300.0

    def test_record_metric_invalid_status(self):
        with pytest.raises(ExchangeMetricsError) as exc_info:
            self.engine.record_metric(action_id="act-1", status="invalid")
        assert exc_info.value.code == "INVALID_STATUS"

    def test_record_metric_missing_action_id(self):
        with pytest.raises(ExchangeMetricsError) as exc_info:
            self.engine.record_metric(action_id="", status="success")
        assert exc_info.value.code == "MISSING_ACTION_ID"

    def test_get_metric(self):
        metric = self.engine.record_metric(
            action_id="act-1", status="success", duration_ms=100.0
        )
        fetched = self.engine.get_metric(metric.id)
        assert fetched.id == metric.id
        assert fetched.action_id == "act-1"
        assert fetched.status == "success"

    def test_get_metric_not_found(self):
        with pytest.raises(ExchangeMetricsError) as exc_info:
            self.engine.get_metric("nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_metrics(self):
        self.engine.record_metric(
            action_id="act-1", status="success", duration_ms=100.0
        )
        self.engine.record_metric(
            action_id="act-1", status="failure", duration_ms=200.0
        )
        self.engine.record_metric(
            action_id="act-2", status="success", duration_ms=150.0
        )
        # 全部（默认 days=30，刚创建的都在窗口内）
        all_metrics = self.engine.list_metrics()
        assert len(all_metrics) == 3
        # 按 action_id 过滤
        act1 = self.engine.list_metrics(action_id="act-1")
        assert len(act1) == 2
        # 按 status 过滤
        successes = self.engine.list_metrics(status="success")
        assert len(successes) == 2
        # 同时过滤
        act1_success = self.engine.list_metrics(action_id="act-1", status="success")
        assert len(act1_success) == 1
        # days 过滤：days=30 应包含全部
        all_30 = self.engine.list_metrics(days=30)
        assert len(all_30) == 3
        # days=0 应排除全部（recorded_at >= now，几乎不可能等于 now）
        none_0 = self.engine.list_metrics(days=0)
        assert len(none_0) == 0

    def test_list_metrics_sorted_descending(self):
        m1 = self.engine.record_metric(
            action_id="act-1", status="success", duration_ms=100.0
        )
        time.sleep(0.01)
        m2 = self.engine.record_metric(
            action_id="act-1", status="success", duration_ms=200.0
        )
        time.sleep(0.01)
        m3 = self.engine.record_metric(
            action_id="act-1", status="success", duration_ms=300.0
        )
        result = self.engine.list_metrics(action_id="act-1")
        # 按 recorded_at 降序排列
        assert result[0].id == m3.id
        assert result[1].id == m2.id
        assert result[2].id == m1.id

    def test_get_summary(self):
        self.engine.record_metric(
            action_id="act-1", status="success", duration_ms=100.0
        )
        self.engine.record_metric(
            action_id="act-1", status="success", duration_ms=200.0
        )
        self.engine.record_metric(
            action_id="act-1", status="failure", duration_ms=300.0
        )
        self.engine.record_metric(
            action_id="act-1", status="timeout", duration_ms=500.0
        )
        # 另一个 action 的记录不应计入
        self.engine.record_metric(
            action_id="act-2", status="success", duration_ms=999.0
        )
        summary = self.engine.get_summary("act-1")
        assert summary.action_id == "act-1"
        assert summary.total_calls == 4
        assert summary.success_count == 2
        assert summary.failure_count == 1
        assert summary.timeout_count == 1
        # failure_rate = (failure + timeout) / total = (1+1)/4 = 0.5
        assert summary.failure_rate == 0.5
        # avg_duration = (100+200+300+500)/4 = 275.0
        assert summary.avg_duration_ms == 275.0
        assert summary.last_recorded_at > 0

    def test_get_summary_no_data(self):
        summary = self.engine.get_summary("act-empty")
        assert summary.action_id == "act-empty"
        assert summary.total_calls == 0
        assert summary.success_count == 0
        assert summary.failure_count == 0
        assert summary.timeout_count == 0
        assert summary.failure_rate == 0.0
        assert summary.avg_duration_ms == 0.0
        assert summary.last_recorded_at == 0

    def test_get_dashboard(self):
        self.engine.record_metric(
            action_id="act-1", status="success", duration_ms=100.0
        )
        self.engine.record_metric(
            action_id="act-2", status="failure", duration_ms=200.0
        )
        self.engine.record_metric(
            action_id="act-3", status="success", duration_ms=150.0
        )
        dashboard = self.engine.get_dashboard()
        assert len(dashboard) == 3
        action_ids = [s.action_id for s in dashboard]
        # dashboard 按 action_id 排序
        assert action_ids == sorted(action_ids)
        assert "act-1" in action_ids
        assert "act-2" in action_ids
        assert "act-3" in action_ids
        for s in dashboard:
            assert s.total_calls >= 1

    def test_delete_metric(self):
        metric = self.engine.record_metric(
            action_id="act-1", status="success", duration_ms=100.0
        )
        assert self.engine.delete_metric(metric.id) is True
        with pytest.raises(ExchangeMetricsError):
            self.engine.get_metric(metric.id)
        assert self.engine.delete_metric(metric.id) is False

    def test_fifo_eviction(self):
        max_metrics = ActionMetricsEngine._MAX_METRICS
        for _ in range(max_metrics + 5):
            self.engine.record_metric(
                action_id="act-1", status="success", duration_ms=1.0
            )
        all_metrics = self.engine.list_metrics()
        assert len(all_metrics) == max_metrics


# ════════════════════ 单例 getter 验证 ════════════════════

def test_singleton_getters_return_same_instance():
    assert get_csv_parsing_engine() is get_csv_parsing_engine()
    assert get_ontology_exchange_engine() is get_ontology_exchange_engine()
    assert get_ontology_usage_engine() is get_ontology_usage_engine()
    assert get_action_metrics_engine() is get_action_metrics_engine()

"""W2-AI · Data Connection 推送与导出组测试（#119 / #120 / #121）."""
from __future__ import annotations

import threading

import pytest

from aos_api.data_connection_export import (
    DataConnectionExportError,
    FileExportEngine,
    FileExportTask,
    PushIngestionEngine,
    PushIngestionSource,
    TableExportEngine,
    TableExportTask,
    get_file_export_engine,
    get_push_ingestion_engine,
    get_table_export_engine,
)


# ════════════════════ PushIngestionEngine ════════════════════

class TestPushIngestion:
    def setup_method(self) -> None:
        self.eng = PushIngestionEngine.__new__(PushIngestionEngine)
        self.eng._sources = {}
        self.eng._messages = {}
        self.eng._minute_buckets = {}
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> PushIngestionSource:
        defaults: dict[str, object] = {
            "name": "my-source",
            "auth_type": "none",
            "rate_limit_per_minute": 60,
        }
        defaults.update(kw)
        return PushIngestionSource(**defaults)

    def test_register_returns_with_id(self) -> None:
        s = self.eng.register(self._mk())
        assert s.id.startswith("pis-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_invalid_auth_type(self) -> None:
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.register(self._mk(auth_type="jwt"))
        assert exc.value.code == "INVALID_AUTH_TYPE"

    def test_register_invalid_rate_limit(self) -> None:
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.register(self._mk(rate_limit_per_minute=0))
        assert exc.value.code == "INVALID_RATE_LIMIT"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_filter_enabled(self) -> None:
        self.eng.register(self._mk(name="a", enabled=True))
        self.eng.register(self._mk(name="b", enabled=False))
        assert len(self.eng.list(enabled=True)) == 1

    def test_update(self) -> None:
        s = self.eng.register(self._mk())
        updated = self.eng.update(s.id, {"name": "new-name", "enabled": False})
        assert updated.name == "new-name"
        assert updated.enabled is False

    def test_delete(self) -> None:
        s = self.eng.register(self._mk())
        assert self.eng.delete(s.id) is True
        assert self.eng.delete(s.id) is False

    def test_receive_message_success(self) -> None:
        s = self.eng.register(self._mk())
        msg = self.eng.receive_message(s.id, {"key": "value"})
        assert msg.status == "accepted"
        assert msg.message_id.startswith("msg-")
        s2 = self.eng.get(s.id)
        assert s2.total_messages == 1

    def test_receive_message_disabled(self) -> None:
        s = self.eng.register(self._mk(enabled=False))
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.receive_message(s.id, {"k": "v"})
        assert exc.value.code == "SOURCE_DISABLED"

    def test_receive_message_empty_payload(self) -> None:
        s = self.eng.register(self._mk())
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.receive_message(s.id, {})
        assert exc.value.code == "EMPTY_PAYLOAD"

    def test_receive_message_api_key_auth_success(self) -> None:
        s = self.eng.register(self._mk(
            auth_type="api_key",
            auth_config={"api_key": "secret-123"},
        ))
        msg = self.eng.receive_message(s.id, {"k": "v"}, auth_token="secret-123")
        assert msg.status == "accepted"

    def test_receive_message_api_key_auth_failed(self) -> None:
        s = self.eng.register(self._mk(
            auth_type="api_key",
            auth_config={"api_key": "secret-123"},
        ))
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.receive_message(s.id, {"k": "v"}, auth_token="wrong")
        assert exc.value.code == "AUTH_FAILED"

    def test_receive_message_rate_limit(self) -> None:
        s = self.eng.register(self._mk(rate_limit_per_minute=3))
        for i in range(3):
            self.eng.receive_message(s.id, {"i": i})
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.receive_message(s.id, {"i": 99})
        assert exc.value.code == "RATE_LIMIT_EXCEEDED"

    def test_receive_batch_mixed(self) -> None:
        s = self.eng.register(self._mk(rate_limit_per_minute=2))
        result = self.eng.receive_batch(s.id, [{"a": 1}, {"b": 2}, {"c": 3}])
        assert result.accepted == 2
        assert result.rejected == 1
        assert len(result.messages) == 3

    def test_list_messages_reverse_order(self) -> None:
        s = self.eng.register(self._mk())
        for i in range(5):
            self.eng.receive_message(s.id, {"i": i})
        msgs = self.eng.list_messages(s.id)
        assert len(msgs) == 5
        assert msgs[0].received_at >= msgs[-1].received_at

    def test_validate_token_none_auth(self) -> None:
        s = self.eng.register(self._mk(auth_type="none"))
        assert self.eng.validate_token(s.id, "") is True

    def test_max_sources_eviction(self) -> None:
        from aos_api.data_connection_export import _MAX_SOURCES
        for i in range(_MAX_SOURCES + 5):
            self.eng.register(PushIngestionSource(name=f"s-{i}"))
        assert len(self.eng._sources) == _MAX_SOURCES


# ════════════════════ FileExportEngine ════════════════════

class TestFileExport:
    def setup_method(self) -> None:
        self.eng = FileExportEngine.__new__(FileExportEngine)
        self.eng._tasks = {}
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> FileExportTask:
        defaults: dict[str, object] = {
            "name": "export-csv",
            "dataset_rid": "ds-abc",
            "target_type": "s3",
            "target_path": "s3://bucket/path",
            "file_format": "csv",
            "compression": "gzip",
        }
        defaults.update(kw)
        return FileExportTask(**defaults)

    def test_register_returns_with_id(self) -> None:
        t = self.eng.register(self._mk())
        assert t.id.startswith("fex-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_missing_dataset(self) -> None:
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.register(self._mk(dataset_rid=""))
        assert exc.value.code == "MISSING_DATASET_RID"

    def test_register_invalid_target_type(self) -> None:
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.register(self._mk(target_type="ftp"))
        assert exc.value.code == "INVALID_TARGET_TYPE"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_filter_status(self) -> None:
        t1 = self.eng.register(self._mk(name="a"))
        self.eng.register(self._mk(name="b"))
        self.eng.start(t1.id)
        assert len(self.eng.list(status="running")) == 1

    def test_update_pending(self) -> None:
        t = self.eng.register(self._mk())
        updated = self.eng.update(t.id, {"name": "new-name", "row_limit": 100})
        assert updated.name == "new-name"
        assert updated.row_limit == 100

    def test_update_not_pending(self) -> None:
        t = self.eng.register(self._mk())
        self.eng.start(t.id)
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.update(t.id, {"name": "x"})
        assert exc.value.code == "TASK_NOT_PENDING"

    def test_delete(self) -> None:
        t = self.eng.register(self._mk())
        assert self.eng.delete(t.id) is True
        assert self.eng.delete(t.id) is False

    def test_start(self) -> None:
        t = self.eng.register(self._mk())
        started = self.eng.start(t.id)
        assert started.status == "running"
        assert started.started_at > 0

    def test_start_not_pending(self) -> None:
        t = self.eng.register(self._mk())
        self.eng.start(t.id)
        with pytest.raises(DataConnectionExportError):
            self.eng.start(t.id)

    def test_complete(self) -> None:
        t = self.eng.register(self._mk(total_rows=100))
        self.eng.start(t.id)
        completed = self.eng.complete(t.id, 100, 10240, ["s3://bucket/file.csv.gz"])
        assert completed.status == "completed"
        assert completed.exported_rows == 100
        assert completed.file_size_bytes == 10240
        assert len(completed.output_files) == 1

    def test_complete_already_completed(self) -> None:
        t = self.eng.register(self._mk())
        self.eng.start(t.id)
        self.eng.complete(t.id, 10, 100, ["f.csv"])
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.complete(t.id, 10, 100, ["f.csv"])
        assert exc.value.code == "ALREADY_COMPLETED"

    def test_cancel(self) -> None:
        t = self.eng.register(self._mk())
        self.eng.start(t.id)
        cancelled = self.eng.cancel(t.id)
        assert cancelled.status == "failed"
        assert "cancelled" in cancelled.error_message

    def test_get_progress_percent(self) -> None:
        t = self.eng.register(self._mk(total_rows=200))
        self.eng.start(t.id)
        self.eng.complete(t.id, 100, 0, [])
        prog = self.eng.get_progress(t.id)
        assert prog["status"] == "completed"
        assert prog["progress_percent"] == 50.0

    def test_max_tasks_eviction(self) -> None:
        from aos_api.data_connection_export import _MAX_FILE_EXPORTS
        for i in range(_MAX_FILE_EXPORTS + 5):
            self.eng.register(FileExportTask(name=f"t-{i}", dataset_rid=f"ds-{i}"))
        assert len(self.eng._tasks) == _MAX_FILE_EXPORTS


# ════════════════════ TableExportEngine ════════════════════

class TestTableExport:
    def setup_method(self) -> None:
        self.eng = TableExportEngine.__new__(TableExportEngine)
        self.eng._tasks = {}
        self.eng._runs = {}
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> TableExportTask:
        defaults: dict[str, object] = {
            "name": "daily-export",
            "source_dataset_rid": "ds-source",
            "target_table": "target_tbl",
            "export_mode": "full",
        }
        defaults.update(kw)
        return TableExportTask(**defaults)

    def test_register_returns_with_id(self) -> None:
        t = self.eng.register(self._mk())
        assert t.id.startswith("tex-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_invalid_mode(self) -> None:
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.register(self._mk(export_mode="delta"))
        assert exc.value.code == "INVALID_MODE"

    def test_register_incremental_requires_watermark(self) -> None:
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.register(self._mk(export_mode="incremental"))
        assert exc.value.code == "INCREMENTAL_REQUIRES_WATERMARK"

    def test_register_incremental_with_watermark(self) -> None:
        t = self.eng.register(self._mk(
            export_mode="incremental",
            watermark_column="updated_at",
        ))
        assert t.watermark_column == "updated_at"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_filter_mode(self) -> None:
        self.eng.register(self._mk(name="a", export_mode="full"))
        self.eng.register(self._mk(name="b", export_mode="snapshot"))
        assert len(self.eng.list(mode="full")) == 1

    def test_update(self) -> None:
        t = self.eng.register(self._mk())
        updated = self.eng.update(t.id, {"name": "new-name", "target_table": "new_tbl"})
        assert updated.name == "new-name"
        assert updated.target_table == "new_tbl"

    def test_delete(self) -> None:
        t = self.eng.register(self._mk())
        assert self.eng.delete(t.id) is True
        assert self.eng.delete(t.id) is False

    def test_start_run(self) -> None:
        t = self.eng.register(self._mk())
        run = self.eng.start_run(t.id)
        assert run.run_id.startswith("ter-")
        assert run.status == "running"
        assert run.mode == "full"
        t2 = self.eng.get(t.id)
        assert t2.status == "running"

    def test_start_run_snapshot_truncate(self) -> None:
        t = self.eng.register(self._mk(export_mode="snapshot", truncate_on_snapshot=True))
        run = self.eng.start_run(t.id)
        assert run.truncated is True

    def test_complete_run_advances_watermark(self) -> None:
        t = self.eng.register(self._mk(
            export_mode="incremental",
            watermark_column="updated_at",
            last_watermark="2024-01-01",
        ))
        run = self.eng.start_run(t.id)
        completed = self.eng.complete_run(run.run_id, {
            "rows_processed": 100,
            "rows_inserted": 50,
            "rows_updated": 30,
            "rows_deleted": 20,
            "watermark": "2024-01-02",
        })
        assert completed.status == "completed"
        assert completed.watermark_before == "2024-01-01"
        assert completed.watermark_after == "2024-01-02"
        t2 = self.eng.get(t.id)
        assert t2.last_watermark == "2024-01-02"
        assert t2.processed_rows == 100
        assert t2.inserted_rows == 50

    def test_fail_run(self) -> None:
        t = self.eng.register(self._mk())
        run = self.eng.start_run(t.id)
        failed = self.eng.fail_run(run.run_id, "network error")
        assert failed.status == "failed"
        assert failed.error_message == "network error"
        t2 = self.eng.get(t.id)
        assert t2.status == "failed"

    def test_complete_run_not_found(self) -> None:
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.complete_run("nonexistent", {})
        assert exc.value.code == "RUN_NOT_FOUND"

    def test_complete_run_already_completed(self) -> None:
        t = self.eng.register(self._mk())
        run = self.eng.start_run(t.id)
        self.eng.complete_run(run.run_id, {"rows_processed": 10})
        with pytest.raises(DataConnectionExportError) as exc:
            self.eng.complete_run(run.run_id, {"rows_processed": 10})
        assert exc.value.code == "ALREADY_COMPLETED"

    def test_list_runs_reverse_order(self) -> None:
        t = self.eng.register(self._mk())
        r1 = self.eng.start_run(t.id)
        self.eng.complete_run(r1.run_id, {"rows_processed": 10})
        r2 = self.eng.start_run(t.id)
        runs = self.eng.list_runs(t.id)
        assert len(runs) == 2
        assert runs[0].run_id == r2.run_id

    def test_get_latest_run(self) -> None:
        t = self.eng.register(self._mk())
        self.eng.start_run(t.id)
        latest = self.eng.get_latest_run(t.id)
        assert latest is not None
        assert latest.status == "running"

    def test_get_latest_run_empty(self) -> None:
        t = self.eng.register(self._mk())
        assert self.eng.get_latest_run(t.id) is None

    def test_max_tasks_eviction(self) -> None:
        from aos_api.data_connection_export import _MAX_TABLE_EXPORTS
        for i in range(_MAX_TABLE_EXPORTS + 5):
            self.eng.register(TableExportTask(name=f"t-{i}", source_dataset_rid=f"ds-{i}"))
        assert len(self.eng._tasks) == _MAX_TABLE_EXPORTS


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_push_singleton(self) -> None:
        a = get_push_ingestion_engine()
        b = get_push_ingestion_engine()
        assert a is b

    def test_file_export_singleton(self) -> None:
        a = get_file_export_engine()
        b = get_file_export_engine()
        assert a is b

    def test_table_export_singleton(self) -> None:
        a = get_table_export_engine()
        b = get_table_export_engine()
        assert a is b

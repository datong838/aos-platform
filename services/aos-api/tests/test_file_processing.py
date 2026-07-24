"""W2-AH · Data Connection 文件处理组测试（#116 / #117 / #118）.

覆盖 FileFilterEngine / FileTransformEngine / StreamingSyncEngine 三引擎。
"""
from __future__ import annotations

import threading

import pytest

from aos_api.file_processing import (
    FileEntry,
    FileFilterEngine,
    FileFilterRule,
    FileProcessingError,
    FileTransform,
    FileTransformEngine,
    StreamEvent,
    StreamingSync,
    StreamingSyncEngine,
    SyncRecord,
    get_filter_engine,
    get_streaming_engine,
    get_transform_engine,
)


# ════════════════════ FileFilterEngine ════════════════════

class TestFileFilter:
    def setup_method(self) -> None:
        self.eng = FileFilterEngine.__new__(FileFilterEngine)
        self.eng._filters = {}
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> FileFilterRule:
        defaults: dict[str, object] = {
            "name": "csv-filter",
            "path_pattern": "",
            "min_size_bytes": 0,
            "max_size_bytes": 0,
            "modified_after": 0.0,
            "modified_before": 0.0,
            "exclude_synced": False,
        }
        defaults.update(kw)
        return FileFilterRule(**defaults)

    def test_register_returns_with_id(self) -> None:
        r = self.eng.register(self._mk())
        assert r.id.startswith("ffr-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(FileProcessingError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_get_not_found(self) -> None:
        with pytest.raises(FileProcessingError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(name="a"))
        self.eng.register(self._mk(name="b"))
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        r = self.eng.register(self._mk())
        updated = self.eng.update(r.id, {"name": "new-name", "min_size_bytes": 100})
        assert updated.name == "new-name"
        assert updated.min_size_bytes == 100

    def test_delete(self) -> None:
        r = self.eng.register(self._mk())
        assert self.eng.delete(r.id) is True
        assert self.eng.delete(r.id) is False

    def test_apply_filter_path_pattern(self) -> None:
        r = self.eng.register(self._mk(path_pattern=r"\.csv$"))
        files = [
            FileEntry(path="data/a.csv", size_bytes=100),
            FileEntry(path="data/b.txt", size_bytes=200),
            FileEntry(path="data/c.csv", size_bytes=300),
        ]
        result = self.eng.apply_filter(r.id, files)
        assert result.total_files == 3
        assert result.matched_files == 2
        assert [f.path for f in result.files] == ["data/a.csv", "data/c.csv"]

    def test_apply_filter_size_range(self) -> None:
        r = self.eng.register(self._mk(min_size_bytes=100, max_size_bytes=200))
        files = [
            FileEntry(path="a", size_bytes=50),
            FileEntry(path="b", size_bytes=150),
            FileEntry(path="c", size_bytes=250),
        ]
        result = self.eng.apply_filter(r.id, files)
        assert result.matched_files == 1
        assert result.files[0].path == "b"

    def test_apply_filter_mtime_range(self) -> None:
        r = self.eng.register(self._mk(modified_after=1000.0, modified_before=2000.0))
        files = [
            FileEntry(path="a", modified_at=500.0),
            FileEntry(path="b", modified_at=1500.0),
            FileEntry(path="c", modified_at=2500.0),
        ]
        result = self.eng.apply_filter(r.id, files)
        assert result.matched_files == 1
        assert result.files[0].path == "b"

    def test_apply_filter_exclude_synced(self) -> None:
        r = self.eng.register(self._mk(exclude_synced=True))
        files = [
            FileEntry(path="a", is_synced=True),
            FileEntry(path="b", is_synced=False),
        ]
        result = self.eng.apply_filter(r.id, files)
        assert result.matched_files == 1
        assert result.files[0].path == "b"

    def test_apply_filter_combined_conditions(self) -> None:
        r = self.eng.register(self._mk(
            path_pattern=r"\.log$",
            min_size_bytes=100,
            exclude_synced=True,
        ))
        files = [
            FileEntry(path="a.log", size_bytes=50, is_synced=False),
            FileEntry(path="b.log", size_bytes=150, is_synced=False),
            FileEntry(path="c.log", size_bytes=200, is_synced=True),
            FileEntry(path="d.txt", size_bytes=200, is_synced=False),
        ]
        result = self.eng.apply_filter(r.id, files)
        assert result.matched_files == 1
        assert result.files[0].path == "b.log"

    def test_apply_filter_empty_input(self) -> None:
        r = self.eng.register(self._mk())
        result = self.eng.apply_filter(r.id, [])
        assert result.total_files == 0
        assert result.matched_files == 0

    def test_apply_filter_no_match(self) -> None:
        r = self.eng.register(self._mk(path_pattern=r"nonexistent"))
        files = [FileEntry(path="a.txt"), FileEntry(path="b.csv")]
        result = self.eng.apply_filter(r.id, files)
        assert result.matched_files == 0

    def test_max_filters_eviction(self) -> None:
        from aos_api.file_processing import _MAX_FILTERS
        for i in range(_MAX_FILTERS + 5):
            self.eng.register(FileFilterRule(name=f"f-{i}"))
        assert len(self.eng._filters) == _MAX_FILTERS


# ════════════════════ FileTransformEngine ════════════════════

class TestFileTransform:
    def setup_method(self) -> None:
        self.eng = FileTransformEngine.__new__(FileTransformEngine)
        self.eng._transforms = {}
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> FileTransform:
        defaults: dict[str, object] = {
            "name": "gzip-files",
            "transform_type": "gzip",
            "config": {},
        }
        defaults.update(kw)
        return FileTransform(**defaults)

    def test_register_returns_with_id(self) -> None:
        t = self.eng.register(self._mk())
        assert t.id.startswith("ftr-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(FileProcessingError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_invalid_type(self) -> None:
        with pytest.raises(FileProcessingError) as exc:
            self.eng.register(self._mk(transform_type="unknown"))
        assert exc.value.code == "INVALID_TRANSFORM_TYPE"

    def test_get_not_found(self) -> None:
        with pytest.raises(FileProcessingError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(name="a", transform_type="gzip"))
        self.eng.register(self._mk(name="b", transform_type="merge"))
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        t = self.eng.register(self._mk())
        updated = self.eng.update(t.id, {"name": "new-name"})
        assert updated.name == "new-name"

    def test_delete(self) -> None:
        t = self.eng.register(self._mk())
        assert self.eng.delete(t.id) is True
        assert self.eng.delete(t.id) is False

    def test_apply_gzip(self) -> None:
        t = self.eng.register(self._mk(transform_type="gzip"))
        result = self.eng.apply_transform(t.id, ["a.csv", "b.csv"])
        assert result.status == "success"
        assert result.output_files == ["a.csv.gz", "b.csv.gz"]

    def test_apply_merge(self) -> None:
        t = self.eng.register(self._mk(transform_type="merge"))
        result = self.eng.apply_transform(t.id, ["a.csv", "b.csv", "c.csv"])
        assert result.status == "success"
        assert len(result.output_files) == 1
        assert result.output_files[0].startswith("merged_")
        assert result.output_files[0].endswith(".dat")

    def test_apply_rename(self) -> None:
        t = self.eng.register(self._mk(
            transform_type="rename",
            config={"pattern": "processed_{name}"},
        ))
        result = self.eng.apply_transform(t.id, ["data/old.csv"])
        assert result.status == "success"
        assert result.output_files == ["processed_old.csv"]

    def test_apply_pgp_decrypt(self) -> None:
        t = self.eng.register(self._mk(transform_type="pgp_decrypt"))
        result = self.eng.apply_transform(t.id, ["file.pgp"])
        assert result.status == "success"
        assert result.output_files == ["file.pgp.decrypted"]

    def test_apply_add_timestamp(self) -> None:
        t = self.eng.register(self._mk(transform_type="add_timestamp"))
        result = self.eng.apply_transform(t.id, ["data.csv"])
        assert result.status == "success"
        assert len(result.output_files) == 1
        assert result.output_files[0].endswith("_data.csv")

    def test_apply_empty_input(self) -> None:
        t = self.eng.register(self._mk(transform_type="gzip"))
        result = self.eng.apply_transform(t.id, [])
        assert result.status == "skipped"
        assert result.output_files == []


# ════════════════════ StreamingSyncEngine ════════════════════

class TestStreamingSync:
    def setup_method(self) -> None:
        self.eng = StreamingSyncEngine.__new__(StreamingSyncEngine)
        self.eng._syncs = {}
        self.eng._records = {}
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> StreamingSync:
        defaults: dict[str, object] = {
            "name": "kafka-sync",
            "source_type": "kafka",
            "source_config": {"brokers": "localhost:9092", "topic": "test"},
            "target_stream": "target-stream",
        }
        defaults.update(kw)
        return StreamingSync(**defaults)

    def test_register_returns_with_id(self) -> None:
        s = self.eng.register(self._mk())
        assert s.id.startswith("ssy-")

    def test_register_missing_name(self) -> None:
        with pytest.raises(FileProcessingError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_invalid_source_type(self) -> None:
        with pytest.raises(FileProcessingError) as exc:
            self.eng.register(self._mk(source_type="unknown"))
        assert exc.value.code == "INVALID_SOURCE_TYPE"

    def test_get_not_found(self) -> None:
        with pytest.raises(FileProcessingError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(name="a", source_type="kafka"))
        self.eng.register(self._mk(name="b", source_type="kinesis"))
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        s = self.eng.register(self._mk())
        updated = self.eng.update(s.id, {"name": "new-name", "target_stream": "new-stream"})
        assert updated.name == "new-name"
        assert updated.target_stream == "new-stream"

    def test_delete(self) -> None:
        s = self.eng.register(self._mk())
        assert self.eng.delete(s.id) is True
        assert self.eng.delete(s.id) is False

    def test_start(self) -> None:
        s = self.eng.register(self._mk())
        started = self.eng.start(s.id)
        assert started.status == "running"

    def test_stop(self) -> None:
        s = self.eng.register(self._mk())
        self.eng.start(s.id)
        stopped = self.eng.stop(s.id)
        assert stopped.status == "stopped"

    def test_consume_success(self) -> None:
        s = self.eng.register(self._mk())
        self.eng.start(s.id)
        events = [
            StreamEvent(key="k1", value="v1", offset=10),
            StreamEvent(key="k2", value="v2", offset=11),
        ]
        records = self.eng.consume(s.id, events)
        assert len(records) == 2
        assert records[0].event_key == "k1"
        assert records[1].event_key == "k2"
        assert all(r.status == "synced" for r in records)
        s2 = self.eng.get(s.id)
        assert s2.offset == 11
        assert s2.last_consumed_at > 0

    def test_consume_not_running(self) -> None:
        s = self.eng.register(self._mk())
        with pytest.raises(FileProcessingError) as exc:
            self.eng.consume(s.id, [StreamEvent(key="k", value="v")])
        assert exc.value.code == "NOT_RUNNING"

    def test_consume_multiple_events_offset_max(self) -> None:
        s = self.eng.register(self._mk())
        self.eng.start(s.id)
        events = [
            StreamEvent(key="k1", value="v1", offset=5),
            StreamEvent(key="k2", value="v2", offset=100),
            StreamEvent(key="k3", value="v3", offset=50),
        ]
        self.eng.consume(s.id, events)
        assert self.eng.get(s.id).offset == 100

    def test_list_records(self) -> None:
        s = self.eng.register(self._mk())
        self.eng.start(s.id)
        self.eng.consume(s.id, [StreamEvent(key="k1", value="v1")])
        self.eng.consume(s.id, [StreamEvent(key="k2", value="v2")])
        records = self.eng.list_records(s.id)
        assert len(records) == 2
        assert records[0].event_key == "k2"

    def test_list_records_limit(self) -> None:
        s = self.eng.register(self._mk())
        self.eng.start(s.id)
        for i in range(10):
            self.eng.consume(s.id, [StreamEvent(key=f"k{i}", value=f"v{i}")])
        records = self.eng.list_records(s.id, limit=3)
        assert len(records) == 3

    def test_max_syncs_eviction(self) -> None:
        from aos_api.file_processing import _MAX_SYNCS
        for i in range(_MAX_SYNCS + 5):
            self.eng.register(StreamingSync(name=f"s-{i}", source_type="kafka"))
        assert len(self.eng._syncs) == _MAX_SYNCS

    def test_max_records_eviction(self) -> None:
        from aos_api.file_processing import _MAX_RECORDS
        s = self.eng.register(self._mk())
        self.eng.start(s.id)
        for i in range(_MAX_RECORDS + 10):
            self.eng.consume(s.id, [StreamEvent(key=f"k{i}", value=f"v{i}")])
        assert len(self.eng._records[s.id]) == _MAX_RECORDS


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_filter_singleton(self) -> None:
        a = get_filter_engine()
        b = get_filter_engine()
        assert a is b

    def test_transform_singleton(self) -> None:
        a = get_transform_engine()
        b = get_transform_engine()
        assert a is b

    def test_streaming_singleton(self) -> None:
        a = get_streaming_engine()
        b = get_streaming_engine()
        assert a is b

"""Test cases for Object Storage Indexing engines."""
from __future__ import annotations

import pytest

from aos_api.object_storage_indexing import (
    MAX_ENTRIES,
    DeltaIndexEngine,
    DeltaIndexError,
    ObjectStorageEngine,
    ObjectStorageError,
    StreamIndexEngine,
    StreamIndexError,
)


class TestObjectStorageEngine:
    def setup_method(self) -> None:
        ObjectStorageEngine._instance = None
        self.engine = ObjectStorageEngine()

    def test_singleton_instance(self) -> None:
        engine2 = ObjectStorageEngine()
        assert self.engine is engine2

    def test_create_index_success(self) -> None:
        index = self.engine.create_index("User", "email_idx", "secondary", fields=["email"])
        assert index.index_id.startswith("osi-")
        assert index.object_type == "User"
        assert index.index_name == "email_idx"
        assert index.index_type == "secondary"
        assert index.fields == ["email"]

    def test_create_index_missing_object_type(self) -> None:
        with pytest.raises(ObjectStorageError) as exc_info:
            self.engine.create_index("", "idx", "secondary")
        assert exc_info.value.code == "MISSING_OBJECT_TYPE"

    def test_create_index_missing_name(self) -> None:
        with pytest.raises(ObjectStorageError) as exc_info:
            self.engine.create_index("User", "", "secondary")
        assert exc_info.value.code == "MISSING_INDEX_NAME"

    def test_create_index_invalid_type(self) -> None:
        with pytest.raises(ObjectStorageError) as exc_info:
            self.engine.create_index("User", "idx", "invalid")
        assert exc_info.value.code == "INVALID_INDEX_TYPE"

    def test_get_index_success(self) -> None:
        index = self.engine.create_index("User", "email_idx", "secondary")
        result = self.engine.get_index(index.index_id)
        assert result is not None
        assert result.index_id == index.index_id

    def test_get_index_not_found(self) -> None:
        result = self.engine.get_index("osi-nonexistent")
        assert result is None

    def test_list_indices(self) -> None:
        self.engine.create_index("User", "email_idx", "secondary")
        self.engine.create_index("Product", "sku_idx", "primary")
        indices = self.engine.list_indices()
        assert len(indices) == 2

    def test_list_indices_by_object_type(self) -> None:
        self.engine.create_index("User", "email_idx", "secondary")
        self.engine.create_index("User", "name_idx", "secondary")
        self.engine.create_index("Product", "sku_idx", "primary")
        indices = self.engine.list_indices(object_type="User")
        assert len(indices) == 2

    def test_list_indices_by_status(self) -> None:
        self.engine.create_index("User", "email_idx", "secondary")
        self.engine.create_index("Product", "sku_idx", "primary")
        indices = self.engine.list_indices(status="building")
        assert len(indices) >= 1

    def test_update_index_success(self) -> None:
        index = self.engine.create_index("User", "email_idx", "secondary")
        updated = self.engine.update_index(index.index_id, status="active", shard_count=3)
        assert updated.status == "active"
        assert updated.shard_count == 3

    def test_update_index_not_found(self) -> None:
        with pytest.raises(ObjectStorageError) as exc_info:
            self.engine.update_index("osi-nonexistent", status="active")
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_index_success(self) -> None:
        index = self.engine.create_index("User", "email_idx", "secondary")
        result = self.engine.delete_index(index.index_id)
        assert result is True

    def test_delete_index_not_found(self) -> None:
        result = self.engine.delete_index("osi-nonexistent")
        assert result is False

    def test_rebuild_index(self) -> None:
        index = self.engine.create_index("User", "email_idx", "secondary")
        rebuilt = self.engine.rebuild_index(index.index_id)
        assert rebuilt.status == "rebuilding"

    def test_get_stats(self) -> None:
        self.engine.create_index("User", "email_idx", "secondary")
        stats = self.engine.get_stats("User")
        assert stats.object_type == "User"

    def test_fifo_eviction(self) -> None:
        for i in range(MAX_ENTRIES + 5):
            self.engine.create_index(f"Type{i}", f"idx{i}", "secondary")
        assert len(self.engine.list_indices()) == MAX_ENTRIES


class TestDeltaIndexEngine:
    def setup_method(self) -> None:
        DeltaIndexEngine._instance = None
        self.engine = DeltaIndexEngine()

    def test_singleton_instance(self) -> None:
        engine2 = DeltaIndexEngine()
        assert self.engine is engine2

    def test_create_delta_success(self) -> None:
        delta = self.engine.create_delta("User", 1, 2, changed_objects=[{"id": "1"}])
        assert delta.delta_id.startswith("di-")
        assert delta.object_type == "User"
        assert delta.base_version == 1
        assert delta.delta_version == 2

    def test_create_delta_missing_object_type(self) -> None:
        with pytest.raises(DeltaIndexError) as exc_info:
            self.engine.create_delta("", 1, 2)
        assert exc_info.value.code == "MISSING_OBJECT_TYPE"

    def test_create_delta_invalid_version(self) -> None:
        with pytest.raises(DeltaIndexError) as exc_info:
            self.engine.create_delta("User", 2, 1)
        assert exc_info.value.code == "INVALID_VERSION"

    def test_get_delta_success(self) -> None:
        delta = self.engine.create_delta("User", 1, 2)
        result = self.engine.get_delta(delta.delta_id)
        assert result is not None
        assert result.delta_id == delta.delta_id

    def test_get_delta_not_found(self) -> None:
        result = self.engine.get_delta("di-nonexistent")
        assert result is None

    def test_list_deltas(self) -> None:
        self.engine.create_delta("User", 1, 2)
        self.engine.create_delta("Product", 1, 2)
        deltas = self.engine.list_deltas()
        assert len(deltas) == 2

    def test_list_deltas_by_object_type(self) -> None:
        self.engine.create_delta("User", 1, 2)
        self.engine.create_delta("User", 2, 3)
        self.engine.create_delta("Product", 1, 2)
        deltas = self.engine.list_deltas(object_type="User")
        assert len(deltas) == 2

    def test_list_deltas_by_status(self) -> None:
        self.engine.create_delta("User", 1, 2)
        self.engine.create_delta("Product", 1, 2)
        deltas = self.engine.list_deltas(status="pending")
        assert len(deltas) >= 1

    def test_apply_delta(self) -> None:
        delta = self.engine.create_delta("User", 1, 2)
        applied = self.engine.apply_delta(delta.delta_id)
        assert applied.status == "applied"

    def test_apply_delta_not_found(self) -> None:
        with pytest.raises(DeltaIndexError) as exc_info:
            self.engine.apply_delta("di-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_revert_delta(self) -> None:
        delta = self.engine.create_delta("User", 1, 2)
        reverted = self.engine.revert_delta(delta.delta_id)
        assert reverted.status == "reverted"

    def test_revert_delta_not_found(self) -> None:
        with pytest.raises(DeltaIndexError) as exc_info:
            self.engine.revert_delta("di-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_get_delta_stats(self) -> None:
        self.engine.create_delta("User", 1, 2)
        stats = self.engine.get_delta_stats("User")
        assert stats["object_type"] == "User"

    def test_fifo_eviction(self) -> None:
        for i in range(MAX_ENTRIES + 5):
            self.engine.create_delta(f"Type{i}", i, i + 1)
        assert len(self.engine.list_deltas()) == MAX_ENTRIES


class TestStreamIndexEngine:
    def setup_method(self) -> None:
        StreamIndexEngine._instance = None
        self.engine = StreamIndexEngine()

    def test_singleton_instance(self) -> None:
        engine2 = StreamIndexEngine()
        assert self.engine is engine2

    def test_create_pipeline_success(self) -> None:
        pipeline = self.engine.create_pipeline("User", "kafka", {"topic": "user_updates"})
        assert pipeline.pipeline_id.startswith("sip-")
        assert pipeline.object_type == "User"
        assert pipeline.source_type == "kafka"

    def test_create_pipeline_missing_object_type(self) -> None:
        with pytest.raises(StreamIndexError) as exc_info:
            self.engine.create_pipeline("", "kafka", {"topic": "test"})
        assert exc_info.value.code == "MISSING_OBJECT_TYPE"

    def test_create_pipeline_invalid_source_type(self) -> None:
        with pytest.raises(StreamIndexError) as exc_info:
            self.engine.create_pipeline("User", "invalid", {"topic": "test"})
        assert exc_info.value.code == "INVALID_SOURCE_TYPE"

    def test_get_pipeline_success(self) -> None:
        pipeline = self.engine.create_pipeline("User", "kafka", {"topic": "test"})
        result = self.engine.get_pipeline(pipeline.pipeline_id)
        assert result is not None
        assert result.pipeline_id == pipeline.pipeline_id

    def test_get_pipeline_not_found(self) -> None:
        result = self.engine.get_pipeline("sip-nonexistent")
        assert result is None

    def test_list_pipelines(self) -> None:
        self.engine.create_pipeline("User", "kafka", {"topic": "test1"})
        self.engine.create_pipeline("Product", "flink", {"topic": "test2"})
        pipelines = self.engine.list_pipelines()
        assert len(pipelines) == 2

    def test_list_pipelines_by_object_type(self) -> None:
        self.engine.create_pipeline("User", "kafka", {"topic": "test1"})
        self.engine.create_pipeline("User", "cdc", {"topic": "test2"})
        self.engine.create_pipeline("Product", "flink", {"topic": "test3"})
        pipelines = self.engine.list_pipelines(object_type="User")
        assert len(pipelines) == 2

    def test_list_pipelines_by_source_type(self) -> None:
        self.engine.create_pipeline("User", "kafka", {"topic": "test1"})
        self.engine.create_pipeline("Product", "kafka", {"topic": "test2"})
        self.engine.create_pipeline("Order", "flink", {"topic": "test3"})
        pipelines = self.engine.list_pipelines(source_type="kafka")
        assert len(pipelines) == 2

    def test_list_pipelines_by_status(self) -> None:
        self.engine.create_pipeline("User", "kafka", {"topic": "test"})
        self.engine.create_pipeline("Product", "flink", {"topic": "test"})
        pipelines = self.engine.list_pipelines(status="stopped")
        assert len(pipelines) >= 1

    def test_update_pipeline_success(self) -> None:
        pipeline = self.engine.create_pipeline("User", "kafka", {"topic": "test"})
        updated = self.engine.update_pipeline(pipeline.pipeline_id, processing_rate=1000)
        assert updated.processing_rate == 1000

    def test_update_pipeline_not_found(self) -> None:
        with pytest.raises(StreamIndexError) as exc_info:
            self.engine.update_pipeline("sip-nonexistent", processing_rate=1000)
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_pipeline_success(self) -> None:
        pipeline = self.engine.create_pipeline("User", "kafka", {"topic": "test"})
        result = self.engine.delete_pipeline(pipeline.pipeline_id)
        assert result is True

    def test_delete_pipeline_not_found(self) -> None:
        result = self.engine.delete_pipeline("sip-nonexistent")
        assert result is False

    def test_start_pipeline(self) -> None:
        pipeline = self.engine.create_pipeline("User", "kafka", {"topic": "test"})
        started = self.engine.start_pipeline(pipeline.pipeline_id)
        assert started.status == "running"

    def test_stop_pipeline(self) -> None:
        pipeline = self.engine.create_pipeline("User", "kafka", {"topic": "test"})
        self.engine.start_pipeline(pipeline.pipeline_id)
        stopped = self.engine.stop_pipeline(pipeline.pipeline_id)
        assert stopped.status == "stopped"

    def test_pause_pipeline(self) -> None:
        pipeline = self.engine.create_pipeline("User", "kafka", {"topic": "test"})
        self.engine.start_pipeline(pipeline.pipeline_id)
        paused = self.engine.pause_pipeline(pipeline.pipeline_id)
        assert paused.status == "paused"

    def test_get_pipeline_stats(self) -> None:
        pipeline = self.engine.create_pipeline("User", "kafka", {"topic": "test"})
        stats = self.engine.get_pipeline_stats(pipeline.pipeline_id)
        assert stats["pipeline_id"] == pipeline.pipeline_id

    def test_fifo_eviction(self) -> None:
        for i in range(MAX_ENTRIES + 5):
            self.engine.create_pipeline(f"Type{i}", "kafka", {"topic": f"topic{i}"})
        assert len(self.engine.list_pipelines()) == MAX_ENTRIES

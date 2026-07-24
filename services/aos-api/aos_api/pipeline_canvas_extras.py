"""W2-BA · Pipeline Canvas Extras 引擎（#2 Pipeline 画布 / #3 Code Repositories / #5 MediaSet 分片）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel

_MAX_NODES = 200
_MAX_EDGES = 200
_MAX_REPOS = 200
_MAX_FILES = 200
_MAX_SHARDS = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


# ════════════════════ Error Classes ════════════════════


class PipelineCanvasExtrasError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PipelineCanvasError(PipelineCanvasExtrasError):
    pass


class CodeRepositoryError(PipelineCanvasExtrasError):
    pass


class MediaSetShardingError(PipelineCanvasExtrasError):
    pass


# ════════════════════ #2 Pipeline Canvas Engine ════════════════════


class NodeType(str, Enum):
    TRANSFORM = "transform"
    INPUT = "input"
    OUTPUT = "output"
    BRANCH = "branch"
    MERGE = "merge"
    LOOP = "loop"
    CONDITIONAL = "conditional"


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EdgeType(str, Enum):
    DATA = "data"
    CONTROL = "control"
    CONDITIONAL = "conditional"


_VALID_NODE_TYPES = {e.value for e in NodeType}
_VALID_NODE_STATUSES = {e.value for e in NodeStatus}
_VALID_EDGE_TYPES = {e.value for e in EdgeType}


class PipelineNode(BaseModel):
    node_id: str = ""
    pipeline_id: str
    node_type: str
    name: str
    config: Optional[dict] = None
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    status: str = NodeStatus.PENDING.value
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PipelineEdge(BaseModel):
    edge_id: str = ""
    pipeline_id: str
    source_node_id: str
    source_port: str
    target_node_id: str
    target_port: str
    edge_type: str = EdgeType.DATA.value
    created_at: Optional[datetime] = None


class PipelineCanvasEngine:
    """Pipeline 画布引擎."""

    _instance: Optional[PipelineCanvasEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._nodes: dict[str, PipelineNode] = {}
        self._edges: dict[str, PipelineEdge] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> PipelineCanvasEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def create_node(
        self,
        pipeline_id: str,
        node_type: str,
        name: str,
        config: Optional[dict] = None,
        x: float = 0,
        y: float = 0,
    ) -> PipelineNode:
        if not pipeline_id or not pipeline_id.strip():
            raise PipelineCanvasError("MISSING_PIPELINE", "pipeline_id is required")
        if not name or not name.strip():
            raise PipelineCanvasError("MISSING_NAME", "name is required")
        if node_type not in _VALID_NODE_TYPES:
            raise PipelineCanvasError(
                "INVALID_NODE_TYPE",
                f"node_type must be one of {_VALID_NODE_TYPES}",
            )

        now = _utcnow()
        nid = f"pn-{uuid.uuid4().hex[:8]}"
        node = PipelineNode(
            node_id=nid,
            pipeline_id=pipeline_id,
            node_type=node_type,
            name=name,
            config=config,
            x=x,
            y=y,
            width=0.0,
            height=0.0,
            status=NodeStatus.PENDING.value,
            error_message=None,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            if len(self._nodes) >= _MAX_NODES:
                oldest = min(
                    self._nodes.values(),
                    key=lambda x: x.updated_at or datetime.min,
                )
                del self._nodes[oldest.node_id]
            self._nodes[nid] = node

        return node

    def get_node(self, node_id: str) -> PipelineNode:
        with self._lock:
            node = self._nodes.get(node_id)
        if node is None:
            raise PipelineCanvasError("NOT_FOUND", f"node {node_id} not found")
        return node

    def list_nodes(
        self,
        pipeline_id: Optional[str] = None,
        node_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[PipelineNode]:
        with self._lock:
            results = list(self._nodes.values())
        if pipeline_id:
            results = [n for n in results if n.pipeline_id == pipeline_id]
        if node_type:
            results = [n for n in results if n.node_type == node_type]
        if status:
            results = [n for n in results if n.status == status]
        return sorted(
            results,
            key=lambda n: n.updated_at or datetime.min,
            reverse=True,
        )

    def update_node(
        self,
        node_id: str,
        name: Optional[str] = None,
        config: Optional[dict] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        status: Optional[str] = None,
    ) -> PipelineNode:
        if status is not None and status not in _VALID_NODE_STATUSES:
            raise PipelineCanvasError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_NODE_STATUSES}",
            )

        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                raise PipelineCanvasError("NOT_FOUND", f"node {node_id} not found")

            data = node.model_dump()
            if name is not None:
                data["name"] = name
            if config is not None:
                data["config"] = config
            if x is not None:
                data["x"] = x
            if y is not None:
                data["y"] = y
            if status is not None:
                data["status"] = status
            data["updated_at"] = _utcnow()

            updated = PipelineNode(**data)
            self._nodes[node_id] = updated

        return updated

    def delete_node(self, node_id: str) -> bool:
        with self._lock:
            if node_id not in self._nodes:
                return False
            del self._nodes[node_id]
        return True

    def create_edge(
        self,
        pipeline_id: str,
        source_node_id: str,
        source_port: str,
        target_node_id: str,
        target_port: str,
        edge_type: str = "data",
    ) -> PipelineEdge:
        if not pipeline_id or not pipeline_id.strip():
            raise PipelineCanvasError("MISSING_PIPELINE", "pipeline_id is required")
        if edge_type not in _VALID_EDGE_TYPES:
            raise PipelineCanvasError(
                "INVALID_EDGE_TYPE",
                f"edge_type must be one of {_VALID_EDGE_TYPES}",
            )

        now = _utcnow()
        eid = f"pe-{uuid.uuid4().hex[:8]}"
        edge = PipelineEdge(
            edge_id=eid,
            pipeline_id=pipeline_id,
            source_node_id=source_node_id,
            source_port=source_port,
            target_node_id=target_node_id,
            target_port=target_port,
            edge_type=edge_type,
            created_at=now,
        )

        with self._lock:
            if len(self._edges) >= _MAX_EDGES:
                oldest = min(
                    self._edges.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._edges[oldest.edge_id]
            self._edges[eid] = edge

        return edge

    def get_edge(self, edge_id: str) -> PipelineEdge:
        with self._lock:
            edge = self._edges.get(edge_id)
        if edge is None:
            raise PipelineCanvasError("NOT_FOUND", f"edge {edge_id} not found")
        return edge

    def list_edges(
        self,
        pipeline_id: Optional[str] = None,
        source_node_id: Optional[str] = None,
        target_node_id: Optional[str] = None,
    ) -> List[PipelineEdge]:
        with self._lock:
            results = list(self._edges.values())
        if pipeline_id:
            results = [e for e in results if e.pipeline_id == pipeline_id]
        if source_node_id:
            results = [e for e in results if e.source_node_id == source_node_id]
        if target_node_id:
            results = [e for e in results if e.target_node_id == target_node_id]
        return sorted(
            results,
            key=lambda e: e.created_at or datetime.min,
            reverse=True,
        )

    def delete_edge(self, edge_id: str) -> bool:
        with self._lock:
            if edge_id not in self._edges:
                return False
            del self._edges[edge_id]
        return True

    def validate_dag(self, pipeline_id: str) -> dict:
        nodes = self.list_nodes(pipeline_id=pipeline_id)
        edges = self.list_edges(pipeline_id=pipeline_id)

        node_ids = {n.node_id for n in nodes}
        source_nodes = {e.source_node_id for e in edges}
        target_nodes = {e.target_node_id for e in edges}

        isolated_nodes = [n.node_id for n in nodes if n.node_id not in source_nodes and n.node_id not in target_nodes]

        dangling_edges = []
        for edge in edges:
            if edge.source_node_id not in node_ids:
                dangling_edges.append({"edge_id": edge.edge_id, "reason": "source node not found"})
            if edge.target_node_id not in node_ids:
                dangling_edges.append({"edge_id": edge.edge_id, "reason": "target node not found"})

        cycles = []
        adjacency = {}
        for n in nodes:
            adjacency[n.node_id] = []
        for e in edges:
            adjacency[e.source_node_id].append(e.target_node_id)

        def has_cycle(node: str, visited: set, rec_stack: set) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    cycles.append(list(rec_stack) + [neighbor])
                    return True
            rec_stack.discard(node)
            return False

        visited = set()
        rec_stack = set()
        for node_id in node_ids:
            if node_id not in visited:
                has_cycle(node_id, visited, rec_stack)

        return {
            "valid": not cycles and not dangling_edges,
            "cycles": cycles,
            "isolated_nodes": isolated_nodes,
            "dangling_edges": dangling_edges,
        }


_canvas_engine: Optional[PipelineCanvasEngine] = None
_canvas_engine_lock = threading.Lock()


def get_canvas_engine() -> PipelineCanvasEngine:
    global _canvas_engine
    if _canvas_engine is None:
        with _canvas_engine_lock:
            if _canvas_engine is None:
                _canvas_engine = PipelineCanvasEngine.get_instance()
    return _canvas_engine


# ════════════════════ #3 Code Repository Engine ════════════════════


class RepositoryType(str, Enum):
    GIT = "git"
    LOCAL = "local"
    S3 = "s3"


class RepositoryStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SYNCING = "syncing"
    ERROR = "error"


_VALID_REPOSITORY_TYPES = {e.value for e in RepositoryType}
_VALID_REPOSITORY_STATUSES = {e.value for e in RepositoryStatus}


class CodeRepository(BaseModel):
    repo_id: str = ""
    name: str
    repository_type: str
    location: str
    branch: str
    commit_hash: str = ""
    last_sync_at: Optional[datetime] = None
    status: str = RepositoryStatus.INACTIVE.value
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CodeFile(BaseModel):
    file_id: str = ""
    repo_id: str
    file_path: str
    content: Optional[str] = None
    last_modified_at: Optional[datetime] = None
    version: str = ""


class CodeRepositoryEngine:
    """代码仓库引擎."""

    _instance: Optional[CodeRepositoryEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._repos: dict[str, CodeRepository] = {}
        self._files: dict[str, CodeFile] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> CodeRepositoryEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def create_repo(
        self,
        name: str,
        repository_type: str,
        location: str,
        branch: str = "main",
    ) -> CodeRepository:
        if not name or not name.strip():
            raise CodeRepositoryError("MISSING_NAME", "name is required")
        if not location or not location.strip():
            raise CodeRepositoryError("MISSING_LOCATION", "location is required")
        if repository_type not in _VALID_REPOSITORY_TYPES:
            raise CodeRepositoryError(
                "INVALID_REPOSITORY_TYPE",
                f"repository_type must be one of {_VALID_REPOSITORY_TYPES}",
            )

        now = _utcnow()
        rid = f"cr-{uuid.uuid4().hex[:8]}"
        repo = CodeRepository(
            repo_id=rid,
            name=name,
            repository_type=repository_type,
            location=location,
            branch=branch,
            commit_hash="",
            last_sync_at=None,
            status=RepositoryStatus.INACTIVE.value,
            error_message=None,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            if len(self._repos) >= _MAX_REPOS:
                oldest = min(
                    self._repos.values(),
                    key=lambda x: x.updated_at or datetime.min,
                )
                del self._repos[oldest.repo_id]
            self._repos[rid] = repo

        return repo

    def get_repo(self, repo_id: str) -> CodeRepository:
        with self._lock:
            repo = self._repos.get(repo_id)
        if repo is None:
            raise CodeRepositoryError("NOT_FOUND", f"repo {repo_id} not found")
        return repo

    def list_repos(
        self,
        name: Optional[str] = None,
        repository_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[CodeRepository]:
        with self._lock:
            results = list(self._repos.values())
        if name:
            results = [r for r in results if r.name == name]
        if repository_type:
            results = [r for r in results if r.repository_type == repository_type]
        if status:
            results = [r for r in results if r.status == status]
        return sorted(
            results,
            key=lambda r: r.updated_at or datetime.min,
            reverse=True,
        )

    def update_repo(
        self,
        repo_id: str,
        name: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> CodeRepository:
        with self._lock:
            repo = self._repos.get(repo_id)
            if repo is None:
                raise CodeRepositoryError("NOT_FOUND", f"repo {repo_id} not found")

            data = repo.model_dump()
            if name is not None:
                data["name"] = name
            if branch is not None:
                data["branch"] = branch
            data["updated_at"] = _utcnow()

            updated = CodeRepository(**data)
            self._repos[repo_id] = updated

        return updated

    def delete_repo(self, repo_id: str) -> bool:
        with self._lock:
            if repo_id not in self._repos:
                return False
            del self._repos[repo_id]
            self._files = {fid: f for fid, f in self._files.items() if f.repo_id != repo_id}
        return True

    def sync_repo(self, repo_id: str) -> CodeRepository:
        with self._lock:
            repo = self._repos.get(repo_id)
            if repo is None:
                raise CodeRepositoryError("NOT_FOUND", f"repo {repo_id} not found")

            data = repo.model_dump()
            data["status"] = RepositoryStatus.SYNCING.value
            data["updated_at"] = _utcnow()
            syncing = CodeRepository(**data)
            self._repos[repo_id] = syncing

        now = _utcnow()
        with self._lock:
            data = self._repos[repo_id].model_dump()
            data["status"] = RepositoryStatus.ACTIVE.value
            data["last_sync_at"] = now
            data["commit_hash"] = uuid.uuid4().hex[:12]
            data["updated_at"] = now

            updated = CodeRepository(**data)
            self._repos[repo_id] = updated

        return updated

    def list_files(self, repo_id: str) -> List[CodeFile]:
        with self._lock:
            repo = self._repos.get(repo_id)
            if repo is None:
                raise CodeRepositoryError("NOT_FOUND", f"repo {repo_id} not found")
            results = [f for f in self._files.values() if f.repo_id == repo_id]
        return sorted(
            results,
            key=lambda f: f.last_modified_at or datetime.min,
            reverse=True,
        )

    def get_file(self, file_id: str) -> CodeFile:
        with self._lock:
            file = self._files.get(file_id)
        if file is None:
            raise CodeRepositoryError("NOT_FOUND", f"file {file_id} not found")
        return file

    def update_file(self, file_id: str, content: str) -> CodeFile:
        with self._lock:
            file = self._files.get(file_id)
            if file is None:
                raise CodeRepositoryError("NOT_FOUND", f"file {file_id} not found")

            data = file.model_dump()
            data["content"] = content
            data["last_modified_at"] = _utcnow()
            data["version"] = str(int(data.get("version", "0")) + 1)

            updated = CodeFile(**data)
            self._files[file_id] = updated

        return updated

    def delete_file(self, file_id: str) -> bool:
        with self._lock:
            if file_id not in self._files:
                return False
            del self._files[file_id]
        return True


_repo_engine: Optional[CodeRepositoryEngine] = None
_repo_engine_lock = threading.Lock()


def get_repo_engine() -> CodeRepositoryEngine:
    global _repo_engine
    if _repo_engine is None:
        with _repo_engine_lock:
            if _repo_engine is None:
                _repo_engine = CodeRepositoryEngine.get_instance()
    return _repo_engine


# ════════════════════ #5 MediaSet Sharding Engine ════════════════════


class ShardStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


_VALID_SHARD_STATUSES = {e.value for e in ShardStatus}


class MediaShard(BaseModel):
    shard_id: str = ""
    media_set_id: str
    shard_index: int
    total_shards: int
    file_path: str
    size_bytes: int
    checksum: str
    status: str = ShardStatus.PENDING.value
    uploaded_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


class MediaSetShardingEngine:
    """MediaSet 分片引擎."""

    _instance: Optional[MediaSetShardingEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._shards: dict[str, MediaShard] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> MediaSetShardingEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def create_shard(
        self,
        media_set_id: str,
        shard_index: int,
        total_shards: int,
        file_path: str,
        size_bytes: int,
        checksum: str,
    ) -> MediaShard:
        if not media_set_id or not media_set_id.strip():
            raise MediaSetShardingError("MISSING_MEDIA_SET", "media_set_id is required")
        if shard_index < 0 or shard_index >= total_shards:
            raise MediaSetShardingError("INVALID_SHARD_INDEX", "shard_index is invalid")

        now = _utcnow()
        sid = f"ms-{uuid.uuid4().hex[:8]}"
        shard = MediaShard(
            shard_id=sid,
            media_set_id=media_set_id,
            shard_index=shard_index,
            total_shards=total_shards,
            file_path=file_path,
            size_bytes=size_bytes,
            checksum=checksum,
            status=ShardStatus.PENDING.value,
            uploaded_at=None,
            error_message=None,
            created_at=now,
        )

        with self._lock:
            if len(self._shards) >= _MAX_SHARDS:
                oldest = min(
                    self._shards.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._shards[oldest.shard_id]
            self._shards[sid] = shard

        return shard

    def get_shard(self, shard_id: str) -> MediaShard:
        with self._lock:
            shard = self._shards.get(shard_id)
        if shard is None:
            raise MediaSetShardingError("NOT_FOUND", f"shard {shard_id} not found")
        return shard

    def list_shards(
        self,
        media_set_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[MediaShard]:
        with self._lock:
            results = list(self._shards.values())
        if media_set_id:
            results = [s for s in results if s.media_set_id == media_set_id]
        if status:
            results = [s for s in results if s.status == status]
        return sorted(
            results,
            key=lambda s: s.created_at or datetime.min,
            reverse=True,
        )

    def update_shard(
        self,
        shard_id: str,
        status: Optional[str] = None,
        uploaded_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ) -> MediaShard:
        if status is not None and status not in _VALID_SHARD_STATUSES:
            raise MediaSetShardingError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_SHARD_STATUSES}",
            )

        with self._lock:
            shard = self._shards.get(shard_id)
            if shard is None:
                raise MediaSetShardingError("NOT_FOUND", f"shard {shard_id} not found")

            data = shard.model_dump()
            if status is not None:
                data["status"] = status
            if uploaded_at is not None:
                data["uploaded_at"] = uploaded_at
            if error_message is not None:
                data["error_message"] = error_message

            updated = MediaShard(**data)
            self._shards[shard_id] = updated

        return updated

    def delete_shard(self, shard_id: str) -> bool:
        with self._lock:
            if shard_id not in self._shards:
                return False
            del self._shards[shard_id]
        return True

    def complete_upload(self, shard_id: str) -> MediaShard:
        with self._lock:
            shard = self._shards.get(shard_id)
            if shard is None:
                raise MediaSetShardingError("NOT_FOUND", f"shard {shard_id} not found")

            if shard.status not in (ShardStatus.PENDING.value, ShardStatus.UPLOADING.value):
                raise MediaSetShardingError(
                    "INVALID_STATUS",
                    f"cannot complete upload with status {shard.status}",
                )

            data = shard.model_dump()
            data["status"] = ShardStatus.COMPLETED.value
            data["uploaded_at"] = _utcnow()

            updated = MediaShard(**data)
            self._shards[shard_id] = updated

        return updated

    def fail_upload(self, shard_id: str, error_message: str) -> MediaShard:
        with self._lock:
            shard = self._shards.get(shard_id)
            if shard is None:
                raise MediaSetShardingError("NOT_FOUND", f"shard {shard_id} not found")

            if shard.status not in (ShardStatus.PENDING.value, ShardStatus.UPLOADING.value):
                raise MediaSetShardingError(
                    "INVALID_STATUS",
                    f"cannot fail upload with status {shard.status}",
                )

            data = shard.model_dump()
            data["status"] = ShardStatus.FAILED.value
            data["error_message"] = error_message

            updated = MediaShard(**data)
            self._shards[shard_id] = updated

        return updated

    def get_upload_status(self, media_set_id: str) -> dict:
        shards = self.list_shards(media_set_id=media_set_id)

        if not shards:
            return {
                "media_set_id": media_set_id,
                "total_shards": 0,
                "completed_shards": 0,
                "failed_shards": 0,
                "pending_shards": 0,
                "uploading_shards": 0,
                "status": "not_found",
            }

        total = len(shards)
        completed = sum(1 for s in shards if s.status == ShardStatus.COMPLETED.value)
        failed = sum(1 for s in shards if s.status == ShardStatus.FAILED.value)
        pending = sum(1 for s in shards if s.status == ShardStatus.PENDING.value)
        uploading = sum(1 for s in shards if s.status == ShardStatus.UPLOADING.value)

        overall_status = "completed" if completed == total else "failed" if failed > 0 else "uploading" if uploading > 0 else "pending"

        return {
            "media_set_id": media_set_id,
            "total_shards": total,
            "completed_shards": completed,
            "failed_shards": failed,
            "pending_shards": pending,
            "uploading_shards": uploading,
            "status": overall_status,
        }


_sharding_engine: Optional[MediaSetShardingEngine] = None
_sharding_engine_lock = threading.Lock()


def get_sharding_engine() -> MediaSetShardingEngine:
    global _sharding_engine
    if _sharding_engine is None:
        with _sharding_engine_lock:
            if _sharding_engine is None:
                _sharding_engine = MediaSetShardingEngine.get_instance()
    return _sharding_engine
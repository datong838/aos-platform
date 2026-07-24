"""W2-BA · Pipeline Canvas Extras 路由."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.errors import ApiError
from aos_api.pipeline_canvas_extras import (
    CodeFile,
    CodeRepository,
    CodeRepositoryError,
    MediaShard,
    MediaSetShardingError,
    PipelineCanvasError,
    PipelineEdge,
    PipelineNode,
    get_canvas_engine,
    get_repo_engine,
    get_sharding_engine,
)

router = APIRouter(prefix="/pipeline-canvas-extras", tags=["Pipeline Canvas Extras"])


# ════════════════════ Error Mapping ════════════════════

def _map_canvas_err(err: PipelineCanvasError) -> ApiError:
    mapping = {
        "MISSING_PIPELINE": (400, "缺少 pipeline_id"),
        "MISSING_NAME": (400, "缺少 name"),
        "INVALID_NODE_TYPE": (400, "节点类型无效"),
        "INVALID_EDGE_TYPE": (400, "边类型无效"),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(err.code, (400, err.message))
    return ApiError(code=err.code, message=msg, status_code=status)


def _map_repo_err(err: CodeRepositoryError) -> ApiError:
    mapping = {
        "MISSING_NAME": (400, "缺少 name"),
        "MISSING_LOCATION": (400, "缺少 location"),
        "INVALID_REPOSITORY_TYPE": (400, "仓库类型无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(err.code, (400, err.message))
    return ApiError(code=err.code, message=msg, status_code=status)


def _map_shard_err(err: MediaSetShardingError) -> ApiError:
    mapping = {
        "MISSING_MEDIA_SET": (400, "缺少 media_set_id"),
        "INVALID_SHARD_INDEX": (400, "分片索引无效"),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(err.code, (400, err.message))
    return ApiError(code=err.code, message=msg, status_code=status)


# ════════════════════ PipelineCanvasEngine Endpoints ════════════════════

class CreateNodeRequest(BaseModel):
    pipeline_id: str
    node_type: str
    name: str
    config: Optional[dict] = None
    x: float = 0.0
    y: float = 0.0


class UpdateNodeRequest(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    x: Optional[float] = None
    y: Optional[float] = None
    status: Optional[str] = None


class CreateEdgeRequest(BaseModel):
    pipeline_id: str
    source_node_id: str
    source_port: str
    target_node_id: str
    target_port: str
    edge_type: str = "data"


@router.post("/nodes", response_model=PipelineNode)
def create_node(req: CreateNodeRequest, _=require_principal):
    try:
        return get_canvas_engine().create_node(
            pipeline_id=req.pipeline_id,
            node_type=req.node_type,
            name=req.name,
            config=req.config,
            x=req.x,
            y=req.y,
        )
    except PipelineCanvasError as err:
        raise _map_canvas_err(err) from err


@router.get("/nodes", response_model=list[PipelineNode])
def list_nodes(
    pipeline_id: Optional[str] = Query(None),
    node_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    _=require_principal,
):
    return get_canvas_engine().list_nodes(
        pipeline_id=pipeline_id,
        node_type=node_type,
        status=status,
    )


@router.get("/nodes/{node_id}", response_model=PipelineNode)
def get_node(node_id: str, _=require_principal):
    try:
        return get_canvas_engine().get_node(node_id)
    except PipelineCanvasError as err:
        raise _map_canvas_err(err) from err


@router.put("/nodes/{node_id}", response_model=PipelineNode)
def update_node(node_id: str, req: UpdateNodeRequest, _=require_principal):
    try:
        return get_canvas_engine().update_node(
            node_id=node_id,
            name=req.name,
            config=req.config,
            x=req.x,
            y=req.y,
            status=req.status,
        )
    except PipelineCanvasError as err:
        raise _map_canvas_err(err) from err


@router.delete("/nodes/{node_id}")
def delete_node(node_id: str, _=require_principal):
    deleted = get_canvas_engine().delete_node(node_id)
    if not deleted:
        raise ApiError(code="NOT_FOUND", message="节点不存在", status_code=404)
    return {"deleted": node_id}


@router.post("/edges", response_model=PipelineEdge)
def create_edge(req: CreateEdgeRequest, _=require_principal):
    try:
        return get_canvas_engine().create_edge(
            pipeline_id=req.pipeline_id,
            source_node_id=req.source_node_id,
            source_port=req.source_port,
            target_node_id=req.target_node_id,
            target_port=req.target_port,
            edge_type=req.edge_type,
        )
    except PipelineCanvasError as err:
        raise _map_canvas_err(err) from err


@router.get("/edges", response_model=list[PipelineEdge])
def list_edges(
    pipeline_id: Optional[str] = Query(None),
    source_node_id: Optional[str] = Query(None),
    target_node_id: Optional[str] = Query(None),
    _=require_principal,
):
    return get_canvas_engine().list_edges(
        pipeline_id=pipeline_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
    )


@router.get("/edges/{edge_id}", response_model=PipelineEdge)
def get_edge(edge_id: str, _=require_principal):
    try:
        return get_canvas_engine().get_edge(edge_id)
    except PipelineCanvasError as err:
        raise _map_canvas_err(err) from err


@router.delete("/edges/{edge_id}")
def delete_edge(edge_id: str, _=require_principal):
    deleted = get_canvas_engine().delete_edge(edge_id)
    if not deleted:
        raise ApiError(code="NOT_FOUND", message="边不存在", status_code=404)
    return {"deleted": edge_id}


@router.post("/validate-dag/{pipeline_id}")
def validate_dag(pipeline_id: str, _=require_principal):
    return get_canvas_engine().validate_dag(pipeline_id)


# ════════════════════ CodeRepositoryEngine Endpoints ════════════════════

class CreateRepoRequest(BaseModel):
    name: str
    repository_type: str
    location: str
    branch: str = "main"


class UpdateRepoRequest(BaseModel):
    name: Optional[str] = None
    branch: Optional[str] = None


class UpdateFileRequest(BaseModel):
    content: str


@router.post("/repos", response_model=CodeRepository)
def create_repo(req: CreateRepoRequest, _=require_principal):
    try:
        return get_repo_engine().create_repo(
            name=req.name,
            repository_type=req.repository_type,
            location=req.location,
            branch=req.branch,
        )
    except CodeRepositoryError as err:
        raise _map_repo_err(err) from err


@router.get("/repos", response_model=list[CodeRepository])
def list_repos(
    name: Optional[str] = Query(None),
    repository_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    _=require_principal,
):
    return get_repo_engine().list_repos(
        name=name,
        repository_type=repository_type,
        status=status,
    )


@router.get("/repos/{repo_id}", response_model=CodeRepository)
def get_repo(repo_id: str, _=require_principal):
    try:
        return get_repo_engine().get_repo(repo_id)
    except CodeRepositoryError as err:
        raise _map_repo_err(err) from err


@router.put("/repos/{repo_id}", response_model=CodeRepository)
def update_repo(repo_id: str, req: UpdateRepoRequest, _=require_principal):
    try:
        return get_repo_engine().update_repo(
            repo_id=repo_id,
            name=req.name,
            branch=req.branch,
        )
    except CodeRepositoryError as err:
        raise _map_repo_err(err) from err


@router.delete("/repos/{repo_id}")
def delete_repo(repo_id: str, _=require_principal):
    deleted = get_repo_engine().delete_repo(repo_id)
    if not deleted:
        raise ApiError(code="NOT_FOUND", message="仓库不存在", status_code=404)
    return {"deleted": repo_id}


@router.post("/repos/{repo_id}/sync", response_model=CodeRepository)
def sync_repo(repo_id: str, _=require_principal):
    try:
        return get_repo_engine().sync_repo(repo_id)
    except CodeRepositoryError as err:
        raise _map_repo_err(err) from err


@router.get("/repos/{repo_id}/files", response_model=list[CodeFile])
def list_files(repo_id: str, _=require_principal):
    try:
        return get_repo_engine().list_files(repo_id)
    except CodeRepositoryError as err:
        raise _map_repo_err(err) from err


@router.get("/files/{file_id}", response_model=CodeFile)
def get_file(file_id: str, _=require_principal):
    try:
        return get_repo_engine().get_file(file_id)
    except CodeRepositoryError as err:
        raise _map_repo_err(err) from err


@router.put("/files/{file_id}", response_model=CodeFile)
def update_file(file_id: str, req: UpdateFileRequest, _=require_principal):
    try:
        return get_repo_engine().update_file(file_id, req.content)
    except CodeRepositoryError as err:
        raise _map_repo_err(err) from err


@router.delete("/files/{file_id}")
def delete_file(file_id: str, _=require_principal):
    deleted = get_repo_engine().delete_file(file_id)
    if not deleted:
        raise ApiError(code="NOT_FOUND", message="文件不存在", status_code=404)
    return {"deleted": file_id}


# ════════════════════ MediaSetShardingEngine Endpoints ════════════════════

class CreateShardRequest(BaseModel):
    media_set_id: str
    shard_index: int
    total_shards: int
    file_path: str
    size_bytes: int
    checksum: str


class UpdateShardRequest(BaseModel):
    status: Optional[str] = None
    uploaded_at: Optional[str] = None
    error_message: Optional[str] = None


@router.post("/shards", response_model=MediaShard)
def create_shard(req: CreateShardRequest, _=require_principal):
    try:
        return get_sharding_engine().create_shard(
            media_set_id=req.media_set_id,
            shard_index=req.shard_index,
            total_shards=req.total_shards,
            file_path=req.file_path,
            size_bytes=req.size_bytes,
            checksum=req.checksum,
        )
    except MediaSetShardingError as err:
        raise _map_shard_err(err) from err


@router.get("/shards", response_model=list[MediaShard])
def list_shards(
    media_set_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    _=require_principal,
):
    return get_sharding_engine().list_shards(
        media_set_id=media_set_id,
        status=status,
    )


@router.get("/shards/{shard_id}", response_model=MediaShard)
def get_shard(shard_id: str, _=require_principal):
    try:
        return get_sharding_engine().get_shard(shard_id)
    except MediaSetShardingError as err:
        raise _map_shard_err(err) from err


@router.put("/shards/{shard_id}", response_model=MediaShard)
def update_shard(shard_id: str, req: UpdateShardRequest, _=require_principal):
    try:
        return get_sharding_engine().update_shard(
            shard_id=shard_id,
            status=req.status,
            uploaded_at=_utcnow() if req.uploaded_at else None,
            error_message=req.error_message,
        )
    except MediaSetShardingError as err:
        raise _map_shard_err(err) from err


def _utcnow():
    from datetime import datetime
    return datetime.utcnow()


@router.delete("/shards/{shard_id}")
def delete_shard(shard_id: str, _=require_principal):
    deleted = get_sharding_engine().delete_shard(shard_id)
    if not deleted:
        raise ApiError(code="NOT_FOUND", message="分片不存在", status_code=404)
    return {"deleted": shard_id}


@router.post("/shards/{shard_id}/complete", response_model=MediaShard)
def complete_upload(shard_id: str, _=require_principal):
    try:
        return get_sharding_engine().complete_upload(shard_id)
    except MediaSetShardingError as err:
        raise _map_shard_err(err) from err


@router.post("/shards/{shard_id}/fail", response_model=MediaShard)
def fail_upload(shard_id: str, error_message: str = Query(None), _=require_principal):
    try:
        return get_sharding_engine().fail_upload(shard_id, error_message or "upload failed")
    except MediaSetShardingError as err:
        raise _map_shard_err(err) from err


@router.get("/shards/upload-status/{media_set_id}")
def get_upload_status(media_set_id: str, _=require_principal):
    return get_sharding_engine().get_upload_status(media_set_id)
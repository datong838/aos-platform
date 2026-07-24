"""W1-13 · Data Lineage DAG API 路由。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.errors import ApiError
from aos_api.lineage_graph import LineageEdge, LineageError, LineageGraph, LineageNode, get_graph

router = APIRouter(tags=["lineage"])


def _map_error(err: LineageError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


class AddNodeRequest(BaseModel):
    id: str
    type: str
    name: str = ""
    metadata: dict = {}


class AddEdgeRequest(BaseModel):
    source: str
    target: str


@router.post("/v1/lineage/nodes")
def add_node(req: AddNodeRequest):
    try:
        return get_graph().add_node(LineageNode(**req.model_dump()))
    except LineageError as err:
        raise _map_error(err) from err


@router.post("/v1/lineage/edges")
def add_edge(req: AddEdgeRequest):
    try:
        get_graph().add_edge(req.source, req.target)
        return {"ok": True}
    except LineageError as err:
        raise _map_error(err) from err


@router.get("/v1/lineage/graph")
def get_graph_dict():
    return get_graph().to_dict()


@router.get("/v1/lineage/{node_id}/upstream")
def get_upstream(node_id: str, depth: int = -1):
    try:
        return {"nodes": get_graph().get_upstream(node_id, depth)}
    except LineageError as err:
        raise _map_error(err) from err


@router.get("/v1/lineage/{node_id}/downstream")
def get_downstream(node_id: str, depth: int = -1):
    try:
        return {"nodes": get_graph().get_downstream(node_id, depth)}
    except LineageError as err:
        raise _map_error(err) from err


@router.post("/v1/lineage/color")
def color_nodes(by: str = "type"):
    return {"colors": get_graph().color_nodes(by)}


@router.get("/v1/lineage/topological")
def topological_sort():
    try:
        return {"order": get_graph().topological_sort()}
    except LineageError as err:
        raise _map_error(err) from err

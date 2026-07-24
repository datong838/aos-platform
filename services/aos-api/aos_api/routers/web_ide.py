"""W2-#22 · Web IDE API 路由。

详见 docs/palantier/20_tech/220tech_w2-e-media-lineage-ide.md §2.4。
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.errors import ApiError
from aos_api.web_ide import IdeError, get_engine

router = APIRouter(tags=["web-ide"])


def _map_error(err: IdeError) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=400)


class CreateSessionRequest(BaseModel):
    name: str = "default"


class CreateFileRequest(BaseModel):
    path: str
    content: str = ""
    language: str = "python"


class WriteFileRequest(BaseModel):
    content: str


class CompletionRequest(BaseModel):
    prefix: str = ""
    path: str | None = None


@router.post("/v1/web-ide/sessions")
def create_session(req: CreateSessionRequest):
    return get_engine().create_session(req.name).model_dump()


@router.get("/v1/web-ide/sessions")
def list_sessions():
    return {"items": [s.model_dump() for s in get_engine().list_sessions()]}


@router.get("/v1/web-ide/sessions/{session_id}")
def get_session(session_id: str):
    try:
        return get_engine().get_session(session_id).model_dump()
    except IdeError as err:
        raise _map_error(err) from err


@router.delete("/v1/web-ide/sessions/{session_id}")
def delete_session(session_id: str):
    ok = get_engine().delete_session(session_id)
    return {"session_id": session_id, "deleted": ok}


@router.get("/v1/web-ide/sessions/{session_id}/files")
def list_files(session_id: str):
    try:
        files = get_engine().list_files(session_id)
    except IdeError as err:
        raise _map_error(err) from err
    return {"items": [f.model_dump() for f in files]}


@router.post("/v1/web-ide/sessions/{session_id}/files")
def create_file(session_id: str, req: CreateFileRequest):
    try:
        f = get_engine().create_file(session_id, req.path, req.content, req.language)
    except IdeError as err:
        raise _map_error(err) from err
    return f.model_dump()


@router.put("/v1/web-ide/sessions/{session_id}/files/{path}")
def write_file(session_id: str, path: str, req: WriteFileRequest):
    try:
        f = get_engine().write_file(session_id, path, req.content)
    except IdeError as err:
        raise _map_error(err) from err
    return f.model_dump()


@router.delete("/v1/web-ide/sessions/{session_id}/files/{path}")
def delete_file(session_id: str, path: str):
    try:
        ok = get_engine().delete_file(session_id, path)
    except IdeError as err:
        raise _map_error(err) from err
    return {"path": path, "deleted": ok}


@router.get("/v1/web-ide/sessions/{session_id}/diagnostics")
def get_diagnostics(session_id: str, path: str | None = None):
    try:
        diags = get_engine().diagnostics(session_id, path)
    except IdeError as err:
        raise _map_error(err) from err
    return {"items": [d.model_dump() for d in diags]}


@router.post("/v1/web-ide/sessions/{session_id}/completions")
def get_completions(session_id: str, req: CompletionRequest):
    try:
        comps = get_engine().completions(session_id, req.prefix, req.path)
    except IdeError as err:
        raise _map_error(err) from err
    return {"items": [c.model_dump() for c in comps]}


@router.get("/v1/web-ide/sessions/{session_id}/symbols")
def get_symbols(session_id: str, path: str | None = None):
    try:
        symbols = get_engine().symbols(session_id, path)
    except IdeError as err:
        raise _map_error(err) from err
    return {"items": [s.model_dump() for s in symbols]}


@router.get("/v1/web-ide/sessions/{session_id}/hover/{line}")
def get_hover(session_id: str, line: int, path: str | None = None):
    try:
        hover = get_engine().hover(session_id, line, path)
    except IdeError as err:
        raise _map_error(err) from err
    return hover.model_dump()

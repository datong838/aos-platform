"""W2-#26 · Functions 运行时 API 路由。

详见 docs/palantier/20_tech/220tech_w2-b-aip-functions.md §2.5。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.functions_runtime import (
    FunctionsRuntimeError,
    OntologyApi,
    RuntimeFunction,
    get_runtime,
)

router = APIRouter(tags=["functions-runtime"])


def _map_error(err: FunctionsRuntimeError) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=400)


class RegisterFunctionRequest(BaseModel):
    name: str
    language: str
    source: str
    description: str = ""
    params_schema: dict[str, str] = Field(default_factory=dict)
    return_type: str = "any"
    ontology_refs: list[str] = Field(default_factory=list)
    workshop_binding: str | None = None


class InvokeFunctionRequest(BaseModel):
    function_id: str
    payload: Any = None


class BindWorkshopRequest(BaseModel):
    workshop_module: str


@router.get("/v1/functions-runtime/functions")
def list_functions():
    return {"items": [f.model_dump() for f in get_runtime().list_all()]}


@router.post("/v1/functions-runtime/functions")
def register_function(req: RegisterFunctionRequest):
    fn = RuntimeFunction(
        name=req.name,
        language=req.language,
        source=req.source,
        description=req.description,
        params_schema=req.params_schema,
        return_type=req.return_type,
        ontology_refs=req.ontology_refs,
        workshop_binding=req.workshop_binding,
    )
    try:
        registered = get_runtime().register(fn)
    except FunctionsRuntimeError as err:
        raise _map_error(err) from err
    return registered.model_dump()


@router.get("/v1/functions-runtime/functions/{fn_id}")
def get_function(fn_id: str):
    fn = get_runtime().get(fn_id)
    if fn is None:
        raise ApiError(code="NOT_FOUND", message=f"Function {fn_id} 不存在", status_code=404)
    return fn.model_dump()


@router.post("/v1/functions-runtime/functions/invoke")
def invoke_function(req: InvokeFunctionRequest):
    try:
        result = get_runtime().invoke(req.function_id, req.payload)
    except FunctionsRuntimeError as err:
        raise _map_error(err) from err
    return {"function_id": req.function_id, "result": result}


@router.post("/v1/functions-runtime/functions/{fn_id}/bind-workshop")
def bind_workshop(fn_id: str, req: BindWorkshopRequest):
    try:
        fn = get_runtime().bind_workshop(fn_id, req.workshop_module)
    except FunctionsRuntimeError as err:
        raise _map_error(err) from err
    return fn.model_dump()


@router.get("/v1/functions-runtime/functions/{fn_id}/ts-signature")
def ts_signature(fn_id: str):
    try:
        sig = get_runtime().typescript_signature(fn_id)
    except FunctionsRuntimeError as err:
        raise _map_error(err) from err
    return {"function_id": fn_id, "signature": sig}


@router.get("/v1/functions-runtime/workshops/{module}/functions")
def list_by_workshop(module: str):
    return {"items": [f.model_dump() for f in get_runtime().list_by_workshop(module)]}


@router.delete("/v1/functions-runtime/functions/{fn_id}")
def delete_function(fn_id: str):
    ok = get_runtime().delete(fn_id)
    return {"function_id": fn_id, "deleted": ok}


@router.get("/v1/functions-runtime/ontology/types")
def list_ontology_types():
    return {"items": OntologyApi().list_object_types()}


@router.get("/v1/functions-runtime/ontology/types/{otd_id}")
def get_ontology_type(otd_id: str):
    otd = OntologyApi().get_object_type(otd_id)
    if otd is None:
        raise ApiError(code="NOT_FOUND", message=f"对象类型 {otd_id} 不存在", status_code=404)
    return otd

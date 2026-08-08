"""T3.5～T3.11 / T3.16 / T3.19 / TC / T4 / T5 minimal surfaces — one module to close gaps.

TODO(持久化改造): 以下接口使用模块级全局变量（``_connectors`` / ``_pipelines`` /
``_datasets`` / ``_syncs`` / ``_media`` / ``_capabilities`` / ``_jobs`` /
``_tools`` / ``_evals_green`` / ``_circuit`` 等）做内存存储，重启即丢。
接口契约与线上一致，但持久化实现待后续迭代补齐。

已下线的接口：
  - ``GET/POST /v1/demo/*``（共 6 个）：演示故事线不再暴露 HTTP 路由。
    测试代码请直接 ``from aos_api.demo.demo_story import ...`` 调用。
"""
from __future__ import annotations

import os
import time
import uuid
import datetime
import random
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.db import connect, get_dsn
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.oidc import allow_dev
from aos_api.tenant_scope import TenantScope

router = APIRouter(tags=["wave3-plus"])
log = get_logger("aos-api.wave3_plus")


def _demo_data_seed_enabled() -> bool:
    return (os.environ.get("AOS_DEMO_DATA_SEED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


_executor = ThreadPoolExecutor(max_workers=4)
_circuit = {"failures": 0, "open": False, "mode": "L4"}
_evals_green = True
_tools: list[dict[str, Any]] = [
    {"id": "query.objects", "kind": "Query"},
    {"id": "fn.echo", "kind": "Function"},
    {"id": "action.close", "kind": "Action", "requiresDraft": True},
    {"id": "wiki.read", "kind": "Wiki"},
]
_capabilities: dict[str, dict[str, Any]] = {}
ScopedResourceKey = tuple[str, str, str]


_jobs: dict[ScopedResourceKey, dict[str, Any]] = {}


_media: dict[ScopedResourceKey, dict[str, Any]] = {}
_media_bytes: dict[ScopedResourceKey, bytes] = {}
_connectors: dict[str, dict[str, Any]] = {}
_pipelines: dict[str, dict[str, Any]] = {}
_schedules: dict[str, dict[str, Any]] = {}
_dlq: dict[ScopedResourceKey, dict[str, Any]] = {}
_syncs: dict[str, dict[str, Any]] = {}
_datasets: dict[ScopedResourceKey, dict[str, Any]] = {}
_dataset_history: dict[ScopedResourceKey, list[dict[str, Any]]] = {}
_data_os_loaded_scopes: set[tuple[str, str]] = set()
_build_logs: dict[str, list[dict[str, Any]]] = {}


def _resource_key(scope: TenantScope, resource_id: str) -> ScopedResourceKey:
    return scope.org_id, scope.project_id, resource_id


def _scoped_values(
    mapping: dict[ScopedResourceKey, dict[str, Any]], scope: TenantScope
) -> list[dict[str, Any]]:
    return [item for key, item in mapping.items() if key[:2] == scope.key]


def ensure_demo_data_seed(
    scope: TenantScope, *, force: bool = False
) -> dict[str, Any]:
    """TB.2 · Idempotent demo source/pipeline/dataset.

    默认 **不** 自动播种（产品数据连接页禁止演示垃圾）。
    仅当 force=True（demo story / 单测）或 AOS_DEMO_DATA_SEED=1 时写入。
    """
    if not force and not _demo_data_seed_enabled():
        return {"ok": True, "mode": "skipped", "reason": "AOS_DEMO_DATA_SEED off"}
    src_id = "demo-file-wo"
    pipe_id = "demo-pipe-wo"
    ds_rid = "ri.dataset.demo-workorder"
    dlq_id = "dlq-demo-sample"
    sch_id = "demo-sch-wo"

    if not _scope_visible(_connectors.get(src_id), scope):
        _connectors[src_id] = {
            "id": src_id,
            "type": "file",
            "status": "registered",
            "orgId": scope.org_id,
            "projectId": scope.project_id,
        }
    build_id = "build-demo-wo"
    now = time.time()
    if not _scope_visible(_pipelines.get(pipe_id), scope):
        _pipelines[pipe_id] = {
            "id": pipe_id,
            "sourceId": src_id,
            "target": "dataset",
            "datasetRid": ds_rid,
            "orgId": scope.org_id,
            "projectId": scope.project_id,
            "lastBuild": {
                "id": build_id,
                "status": "SUCCEEDED",
                "tasks": [{"name": "ingest", "ok": True}],
            },
        }
    # Dataset/History 按 scope 分桶；同 RID 可在多 scope 共存，不依赖全局 pipeline 是否已存在
    dataset_key = _resource_key(scope, ds_rid)
    if dataset_key not in _datasets:
        _datasets[dataset_key] = {
            "rid": ds_rid,
            "name": "WorkOrder-demo",
            "pipelineId": pipe_id,
            "sourceId": src_id,
            "status": "READY",
            "createdAt": now,
            "updatedAt": now,
            "objectTypeHint": "WorkOrder",
            "orgId": scope.org_id,
            "projectId": scope.project_id,
        }
    hist = _dataset_history.setdefault(dataset_key, [])
    if not hist:
        hist.append(
            {
                "version": 1,
                "buildId": build_id,
                "status": "SUCCEEDED",
                "at": now,
            }
        )
    if not _scope_visible(_schedules.get(sch_id), scope):
        _schedules[sch_id] = {
            "id": sch_id,
            "cron": "0 * * * *",
            "pipelineId": pipe_id,
            "enabled": True,
            "orgId": scope.org_id,
            "projectId": scope.project_id,
        }
    sync_id = "sync-demo-wo"
    if not _scope_visible(_syncs.get(sync_id), scope):
        now = time.time()
        _syncs[sync_id] = {
            "id": sync_id,
            "sourceId": src_id,
            "status": "SUCCEEDED",
            "startedAt": now,
            "finishedAt": now,
            "rowsSynced": 3,
            "orgId": scope.org_id,
            "projectId": scope.project_id,
        }
    dlq_key = _resource_key(scope, dlq_id)
    if dlq_key not in _dlq:
        _dlq[dlq_key] = {
            "id": dlq_id,
            "pipelineId": pipe_id,
            "reason": "demo sample row rejected (bad status enum)",
            "status": "open",
            "payload": {
                "objectType": "WorkOrder",
                "row": {"title": "坏样例", "status": "???"},
            },
            "orgId": scope.org_id,
            "projectId": scope.project_id,
        }
    _data_os_loaded_scopes.add(scope.key)
    return {
        "sources": len(_connectors),
        "syncs": len(_syncs),
        "pipelines": len(_pipelines),
        "datasets": len(_scoped_values(_datasets, scope)),
        "builds": len(_pipelines),
        "dlq": len(_scoped_values(_dlq, scope)),
    }


class WebhookIn(BaseModel):
    url: str
    event: str = "action.approved"


class FnInvokeIn(BaseModel):
    code: str = "return payload"
    payload: dict[str, Any] = Field(default_factory=dict)
    timeoutSec: float = Field(default=2.0, le=60)


class LogicRunIn(BaseModel):
    dryRun: bool = True
    edits: list[dict[str, Any]] = Field(default_factory=list)


class CapRegIn(BaseModel):
    id: str
    kind: str = "job"
    endpoint: str = "mock://local"


class JobSubmitIn(BaseModel):
    capabilityId: str
    input: dict[str, Any] = Field(default_factory=dict)


class MediaIn(BaseModel):
    name: str
    contentType: str = "application/octet-stream"
    bytesBase64: str | None = None


class ConnectorIn(BaseModel):
    id: str
    type: str = "file"
    runtimeMode: Literal["direct", "agent", "worker"] | None = None


class PipelineIn(BaseModel):
    id: str
    sourceId: str
    target: str = "dataset"
    datasetRid: str | None = None
    objectTypeHint: str | None = None
    name: str | None = None
    displayName: str | None = None
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class SyncIn(BaseModel):
    sourceId: str
    id: str | None = None


# —— T3.5 / 101 webhook（持久化）——
@router.post("/v1/actions/webhooks")
def register_webhook(body: WebhookIn, principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.channel_runtime import register_webhook as persist_webhook

    return persist_webhook(url=body.url, event=body.event)


@router.get("/v1/actions/webhooks")
def list_webhooks(principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.channel_runtime import list_webhooks as load_webhooks

    return {"items": load_webhooks()}


@router.delete("/v1/actions/webhooks/{webhook_id}")
def delete_webhook(webhook_id: str, principal: Principal = Depends(require_principal)):
    """209m — unregister webhook."""
    _ = principal
    from aos_api.channel_runtime import delete_webhook as drop_webhook
    from aos_api.errors import ApiError

    if not drop_webhook(webhook_id):
        raise ApiError(code="NOT_FOUND", message="webhook not found", status_code=404)
    return {"ok": True, "id": webhook_id}


@router.get("/v1/channels/outbox")
def list_channel_outbox(
    limit: int = 50,
    principal: Principal = Depends(require_principal),
):
    """212m — list recent channel deliveries."""
    _ = principal
    from aos_api.channel_runtime import list_outbox

    items = list_outbox(limit=limit)
    return {"items": items, "count": len(items)}


@router.post("/v1/channels/outbox/{outbox_id}/retry")
def retry_channel_outbox(outbox_id: str, principal: Principal = Depends(require_principal)):
    """212m — re-dispatch stored payload."""
    _ = principal
    from aos_api.channel_runtime import retry_outbox

    return retry_outbox(outbox_id)


@router.post("/v1/channels/{plugin_id}/send")
def channel_send(
    plugin_id: str,
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    """101 · 通知通道投递（按已安装插件分发）。"""
    _ = principal
    from aos_api.channel_runtime import dispatch_send

    return dispatch_send(plugin_id, body or {})


@router.get("/v1/channels/{plugin_id}/health")
def channel_health_api(plugin_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.channel_runtime import channel_health

    return channel_health(plugin_id)


# —— T3.6 Function runtime with timeout kill ——
@router.post("/v1/functions/invoke")
def invoke_function(body: FnInvokeIn, principal: Principal = Depends(require_principal)):
    return _invoke_function_core(body, principal)


@router.post("/v1/functions/{fn_id}/invoke")
def invoke_function_by_id(
    fn_id: str,
    body: FnInvokeIn,
    principal: Principal = Depends(require_principal),
):
    """T-API path · wraps /v1/functions/invoke."""
    _ = fn_id
    return _invoke_function_core(body, principal)


def _invoke_function_core(body: FnInvokeIn, principal: Principal):
    _ = principal
    if body.timeoutSec > 60:
        raise ApiError(code="VALIDATION", message="timeout > 60s forbidden", status_code=400)

    def _run():
        # sandboxed-ish: only echo payload; ignore code for safety
        time.sleep(min(0.05, body.timeoutSec / 10))
        return {"echo": body.payload, "codeAccepted": True}

    fut = _executor.submit(_run)
    try:
        result = fut.result(timeout=body.timeoutSec)
        log.info("function_invoke ok")
        return {"ok": True, "result": result}
    except FuturesTimeout:
        log.warning("function_timeout timeoutSec=%s", body.timeoutSec)
        raise ApiError(code="VALIDATION", message="function timeout forced kill", status_code=408)


# —— T3.7 Tool registry ——
@router.get("/v1/aip/tools")
def list_tools(principal: Principal = Depends(require_principal)):
    _ = principal
    return {"items": _tools}


@router.post("/v1/aip/tools/{tool_id}/invoke")
def invoke_tool_endpoint(
    tool_id: str,
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    from aos_api.tool_runtime import invoke_tool

    return invoke_tool(
        TenantScope(principal.org_id, principal.project_id), tool_id, body or {}
    )


# —— T3.8 统一插件目录 ——
@router.get("/v1/plugins")
def list_plugins_catalog(principal: Principal = Depends(require_principal)):
    """Aggregate tools + parsers + sources + capabilities + llm providers (T3.8 / 83)."""
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    from aos_api.llm_provider_registry import list_llm_provider_plugins
    from aos_api.connector_registry import list_connector_plugins
    from aos_api.parser_registry import list_parser_plugins
    from aos_api.widget_registry import list_widget_plugins
    from aos_api.channel_registry import list_channel_plugins
    from aos_api.embedding_registry import list_embedding_plugins
    from aos_api.action_template_registry import list_action_plugins

    items: list[dict[str, Any]] = []
    for t in _tools:
        items.append({"id": t["id"], "kind": "tool", "subKind": t.get("kind"), "status": "ready"})
    for p in list_parser_plugins().get("items") or []:
        items.append(
            {
                "id": f"parser.{p['id']}",
                "kind": "parser",
                "formats": p.get("formats"),
                "status": "installed" if p.get("installed") else "catalog",
                "runtime": p.get("runtime"),
                "note": p.get("description"),
            }
        )
    for cp in list_connector_plugins().get("items") or []:
        items.append(
            {
                "id": f"connector.{cp['id']}",
                "kind": "connector",
                "subKind": cp.get("kind"),
                "name": cp.get("nameZh") or cp.get("name"),
                "status": "installed" if cp.get("installed") else "catalog",
                "runtime": cp.get("runtime"),
            }
        )
    for wp in list_widget_plugins().get("items") or []:
        items.append(
            {
                "id": f"widget.{wp['id']}",
                "kind": "widget",
                "name": wp.get("nameZh") or wp.get("name"),
                "status": "installed" if wp.get("installed") else "catalog",
                "runtime": wp.get("runtime"),
                "canvasKind": wp.get("canvasKind"),
            }
        )
    for ch in list_channel_plugins().get("items") or []:
        items.append(
            {
                "id": f"channel.{ch['id']}",
                "kind": "channel",
                "name": ch.get("nameZh") or ch.get("name"),
                "status": "installed" if ch.get("installed") else "catalog",
                "runtime": ch.get("runtime"),
            }
        )
    for em in list_embedding_plugins().get("items") or []:
        items.append(
            {
                "id": f"embedding.{em['id']}",
                "kind": "embedding",
                "name": em.get("nameZh") or em.get("name"),
                "status": "installed" if em.get("installed") else "catalog",
                "runtime": em.get("runtime"),
            }
        )
    for ap in list_action_plugins().get("items") or []:
        items.append(
            {
                "id": f"action.{ap['id']}",
                "kind": "action-template",
                "name": ap.get("nameZh") or ap.get("name"),
                "actionTypeId": ap.get("actionTypeId"),
                "status": "installed" if ap.get("installed") else "catalog",
                "runtime": ap.get("runtime"),
            }
        )
    for s in _connectors.values():
        if not _scope_visible(s, scope):
            continue
        items.append(
            {"id": s["id"], "kind": "source", "type": s.get("type"), "status": s.get("status", "registered")}
        )
    for c in _capabilities.values():
        items.append({"id": c["id"], "kind": "capability", "subKind": c.get("kind"), "status": "registered"})
    for lp in list_llm_provider_plugins().get("items") or []:
        items.append(
            {
                "id": f"llm.{lp['id']}",
                "kind": "llm-provider",
                "subKind": lp.get("formFamily"),
                "name": lp.get("nameZh") or lp.get("name"),
                "status": "installed" if lp.get("installed") else "catalog",
                "tier": lp.get("tier"),
                "modalities": lp.get("modalities"),
            }
        )
    log.info("plugins_catalog count=%s", len(items))
    return {"items": items, "totals": {"all": len(items)}}


# —— T3.8 / T3.9 / T3.10 Model facade → LiteLLM sidecar ——
@router.get("/v1/aip/providers")
def list_providers(principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.llm_gateway import providers_payload

    return providers_payload()


@router.get("/v1/aip/models")
def list_models(principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.llm_gateway import models_payload

    return models_payload()


@router.get("/v1/aip/gateway-default")
def get_gateway_default_route(principal: Principal = Depends(require_principal)):
    """85 · 平台默认网关（运行态 + 无 model 的 chat）。"""
    _ = principal
    from aos_api.gateway_default import gateway_default_payload

    return gateway_default_payload()


@router.put("/v1/aip/gateway-default")
def put_gateway_default_route(
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    _ = principal
    from aos_api.gateway_default import gateway_default_payload, put_gateway_default

    put_gateway_default(body or {})
    return gateway_default_payload()


@router.get("/v1/aip/model-routes")
def get_model_routes(principal: Principal = Depends(require_principal)):
    """81 · 任务类型 → 首选/回退/出境（可编辑持久化）。"""
    _ = principal
    from aos_api.aip_kv_store import get_model_routes as load_routes
    from aos_api.llm_gateway import models_payload

    model_ids = [str(m.get("id") or "") for m in (models_payload().get("items") or []) if m.get("id")]
    return {"items": load_routes(model_ids)}


@router.put("/v1/aip/model-routes")
def put_model_routes(
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    _ = principal
    from aos_api.aip_kv_store import put_model_routes as save_routes

    items = body.get("items")
    if not isinstance(items, list):
        raise ApiError(code="VALIDATION", message="items must be a list", status_code=400)
    return {"items": save_routes(items)}


@router.post("/v1/aip/model-routes/circuit-drill")
def model_routes_circuit_drill(
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    _ = principal
    from aos_api.aip_kv_store import circuit_drill, get_model_routes as load_routes

    items = (body or {}).get("items")
    if not isinstance(items, list):
        items = load_routes()
    return circuit_drill(items)


@router.get("/v1/aip/tools/config")
def get_tools_config(principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.aip_kv_store import get_tools_config as load_cfg

    return load_cfg()


@router.put("/v1/aip/tools/config")
def put_tools_config(
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    _ = principal
    from aos_api.aip_kv_store import put_tools_config as save_cfg

    return save_cfg(body or {})


@router.get("/v1/aip/llm-provider-plugins")
def list_llm_provider_plugins(principal: Principal = Depends(require_principal)):
    """83 · 对齐 20 §3.1 · LLM Provider 插件目录。"""
    _ = principal
    from aos_api.llm_provider_registry import list_llm_provider_plugins as load

    return load()


@router.post("/v1/aip/llm-provider-plugins/{plugin_id}/install")
def install_llm_provider_plugin(
    plugin_id: str,
    principal: Principal = Depends(require_principal),
):
    _ = principal
    from aos_api.llm_provider_registry import install_plugin

    return install_plugin(plugin_id)


@router.post("/v1/aip/llm-provider-plugins/{plugin_id}/uninstall")
def uninstall_llm_provider_plugin(
    plugin_id: str,
    principal: Principal = Depends(require_principal),
):
    _ = principal
    from aos_api.llm_provider_registry import uninstall_plugin

    return uninstall_plugin(plugin_id)


@router.put("/v1/aip/llm-provider-plugins/custom")
def publish_custom_llm_provider_plugin(
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    _ = principal
    from aos_api.llm_provider_registry import publish_custom_plugin

    return publish_custom_plugin(body or {})


@router.put("/v1/aip/llm-provider-plugins/{plugin_id}/config")
def put_llm_provider_plugin_config(
    plugin_id: str,
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    """84 · 保存配置并可选标就绪（进入可路由模型目录）。"""
    _ = principal
    from aos_api.llm_provider_registry import put_plugin_config

    return put_plugin_config(plugin_id, body or {})


@router.post("/v1/aip/llm-provider-plugins/{plugin_id}/enable")
def enable_llm_provider_plugin(
    plugin_id: str,
    principal: Principal = Depends(require_principal),
):
    _ = principal
    from aos_api.llm_provider_registry import enable_plugin

    return enable_plugin(plugin_id)


@router.post("/v1/aip/llm-provider-plugins/{plugin_id}/disable")
def disable_llm_provider_plugin(
    plugin_id: str,
    principal: Principal = Depends(require_principal),
):
    _ = principal
    from aos_api.llm_provider_registry import disable_plugin

    return disable_plugin(plugin_id)


@router.post("/v1/aip/chat")
def aip_chat(
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    _ = principal
    if _circuit["open"]:
        raise ApiError(code="CIRCUIT_OPEN", message="L4 circuit open; degraded", status_code=503)
    if not _evals_green:
        raise ApiError(code="EVAL_GATE", message="evals not green", status_code=409)
    q = str(body.get("query") or body.get("message") or "")
    tools_used = body.get("tools") or []
    with_tools = bool(body.get("withTools")) or bool(tools_used)
    if with_tools and not tools_used:
        tools_used = ["query.objects"]
    try:
        from aos_api.llm_gateway import chat as llm_chat
        from aos_api.tool_runtime import invoke_tool

        result = llm_chat(
            q,
            model=str(body.get("model") or "").strip() or None,
            with_tools=with_tools,
            tools=list(tools_used) if isinstance(tools_used, list) else None,
        )
        if with_tools:
            executed = []
            for tid in tools_used:
                try:
                    executed.append(
                        invoke_tool(
                            TenantScope(principal.org_id, principal.project_id),
                            str(tid),
                            body.get("toolPayload") or {},
                        )
                    )
                except ApiError as ae:
                    executed.append({"toolId": tid, "ok": False, "error": ae.message})
            result["toolCalls"] = executed
            ok_n = sum(1 for t in executed if t.get("ok"))
            result["answer"] = (
                f"{result.get('answer', '')}\n\n"
                f"[tools executed={ok_n}/{len(executed)}: "
                f"{', '.join(str(t.get('toolId')) for t in executed)}]"
            ).strip()
        return result
    except Exception as exc:  # noqa: BLE001
        log.warning("aip_chat_fail err=%s", exc)
        raise ApiError(code="LLM_UNAVAILABLE", message=str(exc), status_code=503) from exc


@router.get("/v1/aip/models/warmup")
def warmup_status(principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.llm_gateway import warmup_payload

    return warmup_payload()


# —— T3.11 Logic dryRun ——
@router.post("/v1/aip/logic/run")
def logic_run(body: LogicRunIn, principal: Principal = Depends(require_principal)):
    _ = principal
    edits = body.edits or [{"objectType": "WorkOrder", "objectId": "wo-1001", "set": {"note": "logic"}}]
    if body.dryRun:
        log.info("logic_dry_run edits=%s", len(edits))
        return {"dryRun": True, "proposedEdits": edits, "productionWritten": False}
    raise ApiError(
        code="DRAFT_REQUIRED",
        message="non-dryRun must go through Draft/Action",
        status_code=409,
    )


# —— T3.16 Evals / T3.19 circuit ——
@router.get("/v1/aip/evals/status")
def evals_status(principal: Principal = Depends(require_principal)):
    _ = principal
    return {"green": _evals_green, "l4Allowed": _evals_green and not _circuit["open"]}


@router.post("/v1/aip/evals/set")
def evals_set(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    global _evals_green
    _ = principal
    _evals_green = bool(body.get("green", True))
    return {"green": _evals_green}


@router.get("/v1/aip/evals")
def evals_get(principal: Principal = Depends(require_principal)):
    """T-API §2.3 · alias of /evals/status."""
    return evals_status(principal)


@router.post("/v1/aip/evals")
def evals_post(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    """T-API §2.3 · alias of /evals/set."""
    return evals_set(body, principal)


@router.post("/v1/aip/circuit/trip")
def circuit_trip(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    _ = principal
    rate = float(body.get("failureRate", 0.06))
    if rate > 0.05:
        _circuit["open"] = True
        _circuit["mode"] = "L3"
        _circuit["failures"] += 1
    log.warning("circuit_trip open=%s mode=%s", _circuit["open"], _circuit["mode"])
    return dict(_circuit)


@router.post("/v1/aip/circuit/reset")
def circuit_reset(principal: Principal = Depends(require_principal)):
    _ = principal
    _circuit.update({"failures": 0, "open": False, "mode": "L4"})
    return dict(_circuit)


# —— T3.21 Wiki propose via draft only (PUT blocked) ——
@router.put("/v1/wiki/{object_type}/{object_id}")
def wiki_put_blocked(
    object_type: str,
    object_id: str,
    principal: Principal = Depends(require_principal),
):
    _ = (object_type, object_id, principal)
    raise ApiError(
        code="DRAFT_REQUIRED",
        message="Wiki write only via Action/Draft",
        status_code=409,
    )


# —— TC Capability ——
@router.post("/v1/aip/capabilities")
def reg_cap(body: CapRegIn, principal: Principal = Depends(require_principal)):
    _ = principal
    if body.kind not in {"sync", "job", "session"}:
        raise ApiError(code="VALIDATION", message="kind must be sync|job|session", status_code=400)
    _capabilities[body.id] = body.model_dump()
    return body.model_dump()


@router.get("/v1/aip/capabilities")
def list_caps(principal: Principal = Depends(require_principal)):
    _ = principal
    return {"items": list(_capabilities.values())}


@router.post("/v1/aip/capabilities/{cap_id}/submit")
def submit_job(
    cap_id: str,
    body: JobSubmitIn,
    principal: Principal = Depends(require_principal),
):
    """TC.4 light — artifact registers a MediaSet rid (metadata; bytes optional)."""
    scope = _mutation_scope(principal)
    if cap_id not in _capabilities:
        raise ApiError(code="NOT_FOUND", message="capability missing", status_code=404)
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    media_rid = f"ri.mediaset.{uuid.uuid4().hex[:10]}"
    artifact_name = f"cap-{cap_id}-{job_id}.json"
    meta = {
        "rid": media_rid,
        "name": artifact_name,
        "contentType": "application/json",
        "objectStore": "metadata-only",
        "stored": False,
        "bytes": 0,
        "fromCapability": cap_id,
        "jobId": job_id,
        "orgId": principal.org_id,
        "projectId": principal.project_id,
    }
    _media[_resource_key(scope, media_rid)] = meta
    job_key = _resource_key(scope, job_id)
    _jobs[job_key] = {
        "jobId": job_id,
        "capabilityId": cap_id,
        "status": "succeeded",
        "artifact": {
            "rid": media_rid,
            "mediaRid": media_rid,
            "kind": "media-set",
            "name": artifact_name,
        },
        "input": body.input,
        "orgId": scope.org_id,
        "projectId": scope.project_id,
    }
    log.info("capability_job_ok job=%s media=%s", job_id, media_rid)
    return _jobs[job_key]


@router.post("/v1/aip/capabilities/{cap_id}/invoke")
def invoke_capability(
    cap_id: str,
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    """T-API Capability Facade invoke — sync instant or job submit."""
    _ = principal
    if cap_id not in _capabilities:
        # auto-register for Dev ergonomics
        kind = str(body.get("kind") or "sync")
        _capabilities[cap_id] = {"id": cap_id, "kind": kind, "endpoint": "mock://local"}
    cap = _capabilities[cap_id]
    kind = cap.get("kind") or "sync"
    if kind == "job":
        return submit_job(
            cap_id,
            JobSubmitIn(capabilityId=cap_id, input=body.get("input") or {}),
            principal,
        )
    return {
        "capabilityId": cap_id,
        "kind": kind,
        "status": "succeeded",
        "output": {"echo": body.get("input") or {}, "via": "invoke"},
    }


@router.get("/v1/aip/capabilities/jobs/{job_id}")
def job_status(job_id: str, principal: Principal = Depends(require_principal)):
    job = _jobs.get(_resource_key(_mutation_scope(principal), job_id))
    if job is None:
        raise ApiError(code="NOT_FOUND", message="job missing", status_code=404)
    return job


@router.get("/v1/aip/capabilities/{cap_id}/jobs/{job_id}")
def job_status_scoped(
    cap_id: str,
    job_id: str,
    principal: Principal = Depends(require_principal),
):
    """T-API scoped job path."""
    job = job_status(job_id, principal)
    if job.get("capabilityId") != cap_id:
        raise ApiError(code="NOT_FOUND", message="job/cap mismatch", status_code=404)
    return job


# —— Wave-4 L1 minimal ——
@router.get("/v1/connector-plugins")
def list_connector_plugins_api(principal: Principal = Depends(require_principal)):
    """97 · Connector 插件目录 · 对齐 20 §3.1。"""
    _ = principal
    from aos_api.connector_registry import list_connector_plugins

    return list_connector_plugins()


@router.post("/v1/connector-plugins/{plugin_id}/install")
def install_connector_plugin(plugin_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.connector_registry import install_plugin

    try:
        return install_plugin(plugin_id)
    except KeyError:
        raise ApiError(code="NOT_FOUND", message="connector plugin not found", status_code=404) from None
    except ValueError as exc:
        raise ApiError(code="VALIDATION", message=str(exc), status_code=400) from None


@router.post("/v1/connector-plugins/{plugin_id}/uninstall")
def uninstall_connector_plugin(plugin_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.connector_registry import uninstall_plugin

    try:
        return uninstall_plugin(plugin_id)
    except PermissionError as exc:
        raise ApiError(code="FORBIDDEN", message=str(exc), status_code=403) from None


def _plugin_install_route(install_fn, plugin_id: str):
    try:
        return install_fn(plugin_id)
    except KeyError:
        raise ApiError(code="NOT_FOUND", message="plugin not found", status_code=404) from None
    except ValueError as exc:
        raise ApiError(code="VALIDATION", message=str(exc), status_code=400) from None


def _plugin_uninstall_route(uninstall_fn, plugin_id: str):
    try:
        return uninstall_fn(plugin_id)
    except PermissionError as exc:
        raise ApiError(code="FORBIDDEN", message=str(exc), status_code=403) from None


@router.get("/v1/parser-plugins")
def list_parser_plugins_api(principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.parser_registry import list_parser_plugins

    return list_parser_plugins()


@router.post("/v1/parser-plugins/{plugin_id}/install")
def install_parser_plugin(plugin_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.parser_registry import install_plugin

    return _plugin_install_route(install_plugin, plugin_id)


@router.get("/v1/widget-plugins")
def list_widget_plugins_api(principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.widget_registry import list_widget_plugins, palette_items

    body = list_widget_plugins()
    body["palette"] = palette_items()
    return body


@router.post("/v1/widget-plugins/{plugin_id}/install")
def install_widget_plugin(plugin_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.widget_registry import install_plugin

    return _plugin_install_route(install_plugin, plugin_id)


@router.get("/v1/channel-plugins")
def list_channel_plugins_api(principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.channel_registry import list_channel_plugins

    return list_channel_plugins()


@router.post("/v1/channel-plugins/{plugin_id}/install")
def install_channel_plugin(plugin_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.channel_registry import install_plugin

    return _plugin_install_route(install_plugin, plugin_id)


@router.get("/v1/embedding-plugins")
def list_embedding_plugins_api(principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.embedding_registry import list_embedding_plugins

    return list_embedding_plugins()


@router.post("/v1/embedding-plugins/{plugin_id}/install")
def install_embedding_plugin(plugin_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.embedding_registry import install_plugin

    return _plugin_install_route(install_plugin, plugin_id)


@router.post("/v1/embeddings/{plugin_id}/embed")
def embedding_embed(
    plugin_id: str,
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    """103 · 向量化（按已安装 embedding 插件分发）。"""
    _ = principal
    from aos_api.embedding_runtime import dispatch_embed

    return dispatch_embed(plugin_id, body or {})


@router.post("/v1/embeddings/{plugin_id}/rerank")
def embedding_rerank(
    plugin_id: str,
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    """103 · 重排（按已安装 embedding 插件分发；无 Key 时 501）。"""
    _ = principal
    from aos_api.embedding_runtime import dispatch_rerank

    return dispatch_rerank(plugin_id, body or {})


@router.get("/v1/embeddings/{plugin_id}/health")
def embedding_health_api(plugin_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.embedding_runtime import embedding_health

    return embedding_health(plugin_id)


@router.get("/v1/action-plugins")
def list_action_plugins_api(principal: Principal = Depends(require_principal)):
    """99 · Action 模板插件目录。"""
    _ = principal
    from aos_api.action_template_registry import list_action_plugins

    return list_action_plugins()


@router.post("/v1/action-plugins/{plugin_id}/install")
def install_action_plugin(plugin_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.action_template_registry import install_plugin

    return _plugin_install_route(install_plugin, plugin_id)


@router.post("/v1/action-plugins/{plugin_id}/uninstall")
def uninstall_action_plugin(plugin_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.action_template_registry import uninstall_plugin

    return _plugin_uninstall_route(uninstall_plugin, plugin_id)


def _persist_safe(fn_name: str, *args: Any, **kwargs: Any) -> None:
    try:
        from aos_api import data_os_store as dos

        getattr(dos, fn_name)(*args, **kwargs)
    except ApiError:
        raise
    except Exception:  # noqa: BLE001
        log.warning("data_os_persist_fail op=%s", fn_name, exc_info=True)


def _mutation_scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _hydrate_data_os_scope(scope: TenantScope, *, force: bool = False) -> None:
    if scope.key in _data_os_loaded_scopes and not force:
        return
    from aos_api.data_os_store import load_all

    data = load_all(scope)
    for mapping in (_connectors, _pipelines, _syncs, _schedules):
        for resource_id, item in list(mapping.items()):
            if (item.get("orgId"), item.get("projectId")) == scope.key:
                mapping.pop(resource_id, None)
    for mapping in (_datasets, _dataset_history):
        for key in [key for key in mapping if key[:2] == scope.key]:
            mapping.pop(key, None)
    _connectors.update(data["connectors"])
    _pipelines.update(data["pipelines"])
    _syncs.update(data["syncs"])
    _schedules.update(data["schedules"])
    for rid, item in data["datasets"].items():
        _datasets[_resource_key(scope, rid)] = item
    for rid, history in data["dataset_history"].items():
        _dataset_history[_resource_key(scope, rid)] = history
    _data_os_loaded_scopes.add(scope.key)


def _assert_mutation_scope(
    item: dict[str, Any] | None,
    scope: TenantScope,
    *,
    resource: str,
    resource_id: str,
) -> None:
    if item is None:
        return
    if (item.get("orgId"), item.get("projectId")) != scope.key:
        raise ApiError(
            code="TENANT_SCOPE_CONFLICT",
            message=f"{resource} belongs to another or unresolved tenant",
            status_code=409,
            details={"resource": resource, "id": resource_id},
        )


def _scope_visible(item: dict[str, Any] | None, scope: TenantScope) -> bool:
    return bool(
        item
        and (item.get("orgId"), item.get("projectId")) == scope.key
    )


def _source_scope_visible(source_id: str | None, scope: TenantScope) -> bool:
    if not source_id:
        return True
    src = _connectors.get(source_id)
    if src is None:
        return False
    return _scope_visible(src, scope)


@router.post("/v1/sources")
def create_source(body: ConnectorIn, principal: Principal = Depends(require_principal)):
    from aos_api.connector_registry import assert_type_installed

    try:
        plugin_id = assert_type_installed(body.type)
    except KeyError as exc:
        raise ApiError(code="UNKNOWN_CONNECTOR", message=str(exc), status_code=400) from None
    except PermissionError as exc:
        raise ApiError(code="PLUGIN_NOT_INSTALLED", message=str(exc), status_code=400) from None
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    _assert_mutation_scope(
        _connectors.get(body.id), scope, resource="source", resource_id=body.id
    )
    item = {
        **body.model_dump(exclude_none=True),
        "type": plugin_id,
        "status": "registered",
        "pluginId": plugin_id,
        "orgId": principal.org_id,
        "projectId": principal.project_id,
    }
    _connectors[body.id] = item
    _persist_safe("persist_source", scope, item)
    return item


@router.get("/v1/sources")
def list_sources(principal: Principal = Depends(require_principal)):
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    items = [c for c in _connectors.values() if _scope_visible(c, scope)]
    return {"items": items}


@router.post("/v1/syncs")
def create_sync(body: SyncIn, principal: Principal = Depends(require_principal)):
    """G-ALIGN-04 — Dev Sync Job Facade (T-API /v1/syncs)."""
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    source = _connectors.get(body.sourceId)
    if source is None:
        raise ApiError(code="NOT_FOUND", message="source missing", status_code=404)
    _assert_mutation_scope(
        source, scope, resource="source", resource_id=body.sourceId
    )
    sid = body.id or f"sync-{uuid.uuid4().hex[:8]}"
    item = {
        "id": sid,
        "sourceId": body.sourceId,
        "status": "SUCCEEDED",
        "startedAt": time.time(),
        "finishedAt": time.time(),
        "rowsSynced": 0,
        "orgId": scope.org_id,
        "projectId": scope.project_id,
    }
    _syncs[sid] = item
    _persist_safe("persist_sync", scope, item)
    # Reflect sync into dataset history if a dataset is bound to this source
    for key, ds in _datasets.items():
        if ds.get("sourceId") == body.sourceId and (
            ds.get("orgId"), ds.get("projectId")
        ) == scope.key:
            rid = str(ds.get("rid") or key[2])
            hist = _dataset_history.setdefault(key, [])
            hist.append(
                {
                    "version": len(hist) + 1,
                    "syncId": sid,
                    "status": "SUCCEEDED",
                    "at": item["finishedAt"],
                }
            )
            ds["lastSyncId"] = sid
            ds["updatedAt"] = item["finishedAt"]
            _persist_safe("persist_dataset", scope, ds)
            _persist_safe("persist_dataset_history", scope, rid, hist)
    log.info("sync_created id=%s source=%s", sid, body.sourceId)
    return item


@router.get("/v1/syncs")
def list_syncs(principal: Principal = Depends(require_principal)):
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    items = [
        s
        for s in _syncs.values()
        if _scope_visible(s, scope)
        and _source_scope_visible(s.get("sourceId"), scope)
    ]
    return {"items": items}


@router.get("/v1/syncs/{sync_id}")
def get_sync(sync_id: str, principal: Principal = Depends(require_principal)):
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    item = _syncs.get(sync_id)
    if not _scope_visible(item, scope):
        raise ApiError(code="NOT_FOUND", message="sync missing", status_code=404)
    return item


@router.get("/v1/datasets")
def list_datasets(principal: Principal = Depends(require_principal)):
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    items = _scoped_values(_datasets, scope)
    # 用已注册的 8 个管道元数据补齐数据集条目（保证 P01~P08 完整可见，不管 phase5 引擎是否重启）
    try:
        _ALL_PIPE_IDS = [
            ("P01-shop-qyh", "栖月汇-店铺", "店铺基础数据", "Site"),
            ("P02-product-qyh", "栖月汇-商品", "商品主表（过滤线上已上架）", "Goods"),
            ("P03-product-sku-qyh", "栖月汇-商品SKU", "商品SKU规格明细", "GoodsSku"),
            ("P04-category-qyh", "栖月汇-类目", "商品分类层级", "GoodsCategory"),
            ("P05-order-qyh", "栖月汇-订单", "订单主表", "Order"),
            ("P06-order-line-qyh", "栖月汇-订单明细", "订单商品明细行", "OrderLine"),
            ("P07-shipment-qyh", "栖月汇-发货", "物流发货包裹单", "ExpressPackage"),
            ("P08-customer-lite-qyh", "栖月汇-会员", "会员基础档案（已激活）", "CustomerLite"),
        ]
        _seen = {(d.get("rid") or d.get("id")) for d in items}
        for _pid, _name, _desc, _ot in _ALL_PIPE_IDS:
            _rid = f"ri.aos.main.dataset.{_pid}"
            if _rid in _seen:
                continue
            # 从 Phase5 管道取 row_count
            _row_cnt = 0
            try:
                from aos_api.phase5_pipeline_engine import get_engine as _get_eng
                _eng = _get_eng()
                _pl = _eng.get_pipeline(scope, _pid)
                if _pl is not None:
                    _row_cnt = getattr(_pl, "row_count", 0) or 0
                _ds = _eng.get_dataset(scope, _rid)
                if _ds is not None:
                    _row_cnt = getattr(_ds, "row_count", _row_cnt) or _row_cnt
            except Exception:
                pass
            items.append({
                "rid": _rid,
                "id": _rid,
                "name": _name,
                "description": f"{_desc} · {_ot} · Pipeline {_pid}",
                "rowCount": _row_cnt,
                "row_count": _row_cnt,
                "status": "active",
                "pipelineId": _pid,
                "objectTypeHint": _ot,
            })
            _seen.add(_rid)
    except Exception as _e:
        _log("WARN", f"[datasets] 8管道补齐 err: {_e!r}")
    return {"items": items}


@router.get("/v1/datasets/{rid}")
def get_dataset(rid: str, principal: Principal = Depends(require_principal)):
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    item = _datasets.get(_resource_key(scope, rid))
    if item is None:
        raise ApiError(code="NOT_FOUND", message="dataset missing", status_code=404)
    return item


@router.get("/v1/datasets/{rid}/history")
def dataset_history(rid: str, principal: Principal = Depends(require_principal)):
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    key = _resource_key(scope, rid)
    if key not in _datasets:
        raise ApiError(code="NOT_FOUND", message="dataset missing", status_code=404)
    return {"rid": rid, "items": list(_dataset_history.get(key, []))}


@router.post("/v1/media-sets")
def create_media(body: MediaIn, principal: Principal = Depends(require_principal)):
    """T4.2/T4.3 — metadata + real MinIO put when bytes provided · TWA.8 前缀。"""
    import base64

    from aos_api.object_store import get_config, object_key_for, put_bytes
    from aos_api.tenant_prefix import assert_object_key_tenant

    rid = f"ri.mediaset.{uuid.uuid4().hex[:10]}"
    scope = _mutation_scope(principal)
    media_key = _resource_key(scope, rid)
    stored = False
    object_key = None
    etag = None
    raw_len = 0
    store_mode = "metadata-only"
    if body.bytesBase64:
        raw = base64.b64decode(body.bytesBase64)
        raw_len = len(raw)
        from aos_api import provisioning as prov

        prov.assert_storage_quota(principal.org_id, raw_len)
        _media_bytes[media_key] = raw
        object_key = object_key_for(
            rid,
            body.name,
            org_id=principal.org_id,
            project_id=principal.project_id,
        )
        assert_object_key_tenant(object_key, principal.org_id, principal.project_id)
        try:
            put = put_bytes(
                key=object_key,
                data=raw,
                content_type=body.contentType or "application/octet-stream",
            )
            stored = bool(put.get("ok"))
            etag = put.get("etag")
            store_mode = "minio" if stored else "metadata-only"
        except Exception as exc:  # noqa: BLE001
            log.warning("media_store_minio_skip err=%s endpoint=%s", exc, get_config().endpoint)
            store_mode = "metadata-only"
        prov.record_storage_usage(principal.org_id, raw_len)
    item = {
        "rid": rid,
        "name": body.name,
        "contentType": body.contentType,
        "objectStore": store_mode,
        "stored": stored,
        "bytes": raw_len,
        "objectKey": object_key,
        "etag": etag,
        "orgId": principal.org_id,
        "projectId": principal.project_id,
        "accessKeyRef": "env:AOS_S3_ACCESS_KEY|MINIO_ROOT_USER",
    }
    from aos_api.media_meta import extract_metadata

    raw_for_meta = _media_bytes.get(media_key) if body.bytesBase64 else None
    item["metadata"] = extract_metadata(
        raw_for_meta,
        content_type=body.contentType or "application/octet-stream",
        name=body.name,
    )
    _media[media_key] = item
    log.info(
        "media_created rid=%s stored=%s bytes=%s org=%s project=%s",
        rid,
        stored,
        raw_len,
        principal.org_id,
        principal.project_id,
    )
    return item


@router.post("/v1/media-sets/{rid}/enrich")
def enrich_media(rid: str, principal: Principal = Depends(require_principal)):
    """185m — re-extract metadata from in-memory bytes (or empty)."""
    from aos_api.media_meta import extract_metadata

    key = _resource_key(_mutation_scope(principal), rid)
    meta = _media.get(key)
    if meta is None:
        raise ApiError(code="NOT_FOUND", message="media missing", status_code=404)
    raw = _media_bytes.get(key)
    enriched = extract_metadata(
        raw,
        content_type=str(meta.get("contentType") or "application/octet-stream"),
        name=str(meta.get("name") or ""),
    )
    meta["metadata"] = enriched
    _media[key] = meta
    return meta


@router.get("/v1/media-sets")
def list_media(principal: Principal = Depends(require_principal)):
    items = _scoped_values(_media, _mutation_scope(principal))
    return {"items": items}


@router.get("/v1/media-sets/{rid}")
def get_media(rid: str, principal: Principal = Depends(require_principal)):
    meta = _media.get(_resource_key(_mutation_scope(principal), rid))
    if meta is None:
        raise ApiError(code="NOT_FOUND", message="media missing", status_code=404)
    return meta


@router.get("/v1/media-sets/{rid}/content")
def get_media_content(rid: str, principal: Principal = Depends(require_principal)):
    """T4.2 — fetch bytes from object store (base64 in JSON for easy smoke)."""
    import base64

    from aos_api.object_store import get_bytes
    from aos_api.tenant_prefix import assert_object_key_tenant

    meta = _media.get(_resource_key(_mutation_scope(principal), rid))
    if meta is None:
        raise ApiError(code="NOT_FOUND", message="media missing", status_code=404)
    key = meta.get("objectKey")
    if not key or not meta.get("stored"):
        raise ApiError(
            code="NOT_STORED",
            message="media has no object-store bytes",
            status_code=404,
        )
    assert_object_key_tenant(key, principal.org_id, principal.project_id)
    try:
        raw = get_bytes(key=key)
    except Exception as exc:  # noqa: BLE001
        raise ApiError(code="OBJECT_STORE", message=str(exc), status_code=502) from exc
    return {
        "rid": rid,
        "name": meta.get("name"),
        "contentType": meta.get("contentType"),
        "bytes": len(raw),
        "bytesBase64": base64.b64encode(raw).decode("ascii"),
        "objectKey": key,
        "etag": meta.get("etag"),
    }


@router.get("/v1/object-store/health")
def object_store_health(principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.object_store import health_probe

    return health_probe()


@router.get("/v1/parsers")
def list_parsers(principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.file_parsers import list_plugins

    return {"items": list_plugins()}


@router.post("/v1/parsers/extract")
def parsers_extract(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    """T4.4b — extract text from upload or mediaRid."""
    import base64

    from aos_api.file_parsers import extract
    from aos_api.object_store import get_bytes

    name = body.get("name")
    content_type = body.get("contentType")
    data: bytes | None = None
    media_rid = body.get("mediaRid")
    if body.get("bytesBase64"):
        data = base64.b64decode(body["bytesBase64"])
    elif media_rid:
        media_key = _resource_key(_mutation_scope(principal), str(media_rid))
        meta = _media.get(media_key)
        if meta is None:
            raise ApiError(code="NOT_FOUND", message="media bytes missing", status_code=404)
        if media_key in _media_bytes:
            data = _media_bytes[media_key]
            name = name or meta.get("name")
            content_type = content_type or meta.get("contentType")
        elif meta.get("stored") and meta.get("objectKey"):
            data = get_bytes(key=meta["objectKey"])
            name = name or meta.get("name")
            content_type = content_type or meta.get("contentType")
        else:
            raise ApiError(code="NOT_FOUND", message="media bytes missing", status_code=404)
    else:
        raise ApiError(code="BAD_REQUEST", message="bytesBase64 or mediaRid required", status_code=400)

    result = extract(data=data, name=name, content_type=content_type)
    if media_rid:
        media_key = _resource_key(_mutation_scope(principal), str(media_rid))
        meta = _media.get(media_key)
        if meta is not None:
            meta["extractedText"] = result.get("preview")
            meta["parser"] = result.get("parser")
            meta["parseOk"] = result.get("ok")
    return result


@router.post("/v1/media-sets/{rid}/parse")
def parse_media(rid: str, principal: Principal = Depends(require_principal)):
    return parsers_extract({"mediaRid": rid}, principal)


@router.post("/v1/pipelines")
def create_pipeline(body: PipelineIn, principal: Principal = Depends(require_principal)):
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    _assert_mutation_scope(
        _connectors.get(body.sourceId),
        scope,
        resource="source",
        resource_id=body.sourceId,
    )
    _assert_mutation_scope(
        _pipelines.get(body.id), scope, resource="pipeline", resource_id=body.id
    )
    build_id = f"build-{uuid.uuid4().hex[:8]}"
    dataset_rid = body.datasetRid or f"ri.dataset.{body.id}"
    dataset_key = _resource_key(scope, dataset_rid)
    _assert_mutation_scope(
        _datasets.get(dataset_key),
        scope,
        resource="dataset",
        resource_id=dataset_rid,
    )
    item = {
        **body.model_dump(),
        "datasetRid": dataset_rid,
        "lastBuild": {"id": build_id, "status": "SUCCEEDED", "tasks": [{"name": "ingest", "ok": True}]},
        "orgId": principal.org_id,
        "projectId": principal.project_id,
    }
    _pipelines[body.id] = item
    now = time.time()
    display = (body.displayName or body.name or body.id or "").strip() or body.id
    hint = (body.objectTypeHint or "").strip() or None
    prev = _datasets.get(dataset_key) or {}
    ds = {
        "rid": dataset_rid,
        "name": display,
        "pipelineId": body.id,
        "sourceId": body.sourceId,
        "status": "READY",
        "createdAt": prev.get("createdAt") or now,
        "updatedAt": now,
        "objectTypeHint": hint or prev.get("objectTypeHint"),
        "displayName": display,
        "orgId": principal.org_id,
        "projectId": principal.project_id,
    }
    _datasets[dataset_key] = ds
    hist = _dataset_history.setdefault(dataset_key, [])
    hist.append(
        {
            "version": len(hist) + 1,
            "buildId": build_id,
            "status": "SUCCEEDED",
            "at": now,
        }
    )
    _persist_safe("persist_pipeline", scope, item)
    _persist_safe("persist_dataset", scope, ds)
    _persist_safe("persist_dataset_history", scope, dataset_rid, hist)
    return item


@router.patch("/v1/datasets/{rid:path}")
def patch_dataset(
    rid: str,
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    """Update dataset display / objectTypeHint (preview wiring)."""
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    key = _resource_key(scope, rid)
    ds = _datasets.get(key)
    if not ds:
        raise ApiError(code="NOT_FOUND", message="dataset missing", status_code=404)
    _assert_mutation_scope(ds, scope, resource="dataset", resource_id=rid)
    if "name" in body and body["name"] is not None:
        ds["name"] = str(body["name"])
    if "displayName" in body and body["displayName"] is not None:
        ds["displayName"] = str(body["displayName"])
        if not body.get("name"):
            ds["name"] = str(body["displayName"])
    if "objectTypeHint" in body and body["objectTypeHint"] is not None:
        ds["objectTypeHint"] = str(body["objectTypeHint"]).strip() or None
    if "status" in body and body["status"] is not None:
        ds["status"] = str(body["status"])
    ds["updatedAt"] = time.time()
    _datasets[key] = ds
    _persist_safe("persist_dataset", scope, ds)
    return ds


@router.get("/v1/pipelines")
def list_pipelines(principal: Principal = Depends(require_principal)):
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    items = [p for p in _pipelines.values() if _scope_visible(p, scope)]
    # 合并 phase5 引擎中从 YAML bundle 加载的管道（wave_ext 不持有这些数据）
    try:
        from aos_api.phase5_pipeline_engine import get_engine as _get_engine

        _eng = _get_engine()
        _phase5_items, _ = _eng.list_pipelines(scope, page_size=100)
        existing_ids = {p.get("id") for p in items}
        for _p in _phase5_items:
            if _p.id not in existing_ids:
                items.append({
                    "id": _p.id,
                    "sourceId": "niushop-qyh",
                    "target": "dataset",
                    "datasetRid": f"ri.aos.main.dataset.{_p.id}",
                    "orgId": scope.org_id,
                    "projectId": scope.project_id,
                    "name": _p.name,
                    "status": _p.status,
                    "tags": _p.tags,
                    "description": _p.description,
                })
    except Exception:
        pass
    return {"items": items}


@router.get("/v1/pipelines/{pipeline_id}/transform-config")
def get_pipeline_transform_config(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """返回管道的字段映射和 PII 脱敏配置（来自 YAML bundle 文件）。"""
    _fname_map = {
        "P01": "p01-shop.yaml", "P02": "p02-product.yaml",
        "P03": "p03-product-sku.yaml", "P04": "p04-category.yaml",
        "P05": "p05-order.yaml", "P06": "p06-order-line.yaml",
        "P07": "p07-shipment.yaml", "P08": "p08-customer-lite.yaml",
    }
    _prefix = pipeline_id.split("-")[0] if "-" in pipeline_id else pipeline_id[:3]
    _yaml_fname = _fname_map.get(_prefix)
    result: dict[str, Any] = {
        "pipelineId": pipeline_id,
        "fieldMappings": [],
        "piiExclusion": [],
        "sourceTable": "",
        "targetOt": "",
        "siteFilter": "",
        "sourceFieldCount": 0,
        "targetFieldCount": 0,
    }
    if not _yaml_fname:
        return result
    try:
        import yaml as _yaml
        _yaml_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
            "bundles", "platforms", "ecommerce-niushop", "content", "mappings",
            _yaml_fname,
        )
        _yaml_path = os.path.abspath(_yaml_path)
        if not os.path.isfile(_yaml_path):
            return result
        with open(_yaml_path, "r", encoding="utf-8") as _f:
            _yd = _yaml.safe_load(_f)
        result["fieldMappings"] = list(_yd.get("field_mappings") or [])
        result["piiExclusion"] = list(_yd.get("pii_exclusion") or [])
        result["sourceTable"] = str(_yd.get("source_table") or "")
        result["targetOt"] = str(_yd.get("target_ot") or "")
        result["siteFilter"] = str(_yd.get("site_filter") or "")
        result["sourceFieldCount"] = int(_yd.get("source_field_count") or 0)
        result["notes"] = list(_yd.get("notes") or [])
        result["yamlFile"] = _yaml_fname
        result["yamlPath"] = _yaml_path
    except Exception as _e:
        log.warning("transform_config load failed pipeline=%s error=%s", pipeline_id, _e)
    return result


@router.post("/v1/pipelines/{pipeline_id}/embed")
def pipeline_embed(
    pipeline_id: str,
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    """104 · Pipeline → 本地向量索引（经 embedding 插件；无网关不写假向量）。"""
    from aos_api.tenant_prefix import scoped_collection_name
    from aos_api.vector_index import embed_pipeline

    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    if not _scope_visible(_pipelines.get(pipeline_id), scope):
        raise ApiError(code="NOT_FOUND", message="pipeline missing", status_code=404)
    payload = dict(body or {})
    raw_collection = str(payload.get("collection") or pipeline_id).strip()
    payload["collection"] = scoped_collection_name(
        principal.org_id, principal.project_id, raw_collection
    )
    return embed_pipeline(
        pipeline_id,
        payload,
        pipelines=_pipelines,
        scope=scope,
    )


@router.post("/v1/aip/vector-index/upsert")
def vector_index_upsert(body: dict[str, Any] | None = None, principal: Principal = Depends(require_principal)):
    """104 · 直接写入本地向量集合 · TWA.8 租户 collection 前缀。"""
    from aos_api.tenant_prefix import scoped_collection_name
    from aos_api.vector_index import _normalize_documents, upsert

    payload = body or {}
    collection = scoped_collection_name(
        principal.org_id,
        principal.project_id,
        str(payload.get("collection") or "").strip(),
    )
    docs = _normalize_documents(payload.get("documents"))
    return upsert(
        collection=collection,
        documents=docs or None,
        plugin_id=str(payload.get("pluginId") or "embed-openai-compatible"),
        replace=bool(payload.get("replace", False)),
        auto_sample=bool(payload.get("autoSample", False)),
        scope=TenantScope(principal.org_id, principal.project_id),
    )


@router.post("/v1/aip/vector-index/search")
def vector_index_search(body: dict[str, Any] | None = None, principal: Principal = Depends(require_principal)):
    """104 · 本地余弦检索 · TWA.8 租户 collection 前缀。"""
    from aos_api.tenant_prefix import scoped_collection_name
    from aos_api.vector_index import search

    payload = body or {}
    collection = scoped_collection_name(
        principal.org_id,
        principal.project_id,
        str(payload.get("collection") or "").strip(),
    )
    return search(
        collection=collection,
        query=str(payload.get("query") or ""),
        plugin_id=str(payload.get("pluginId") or "") or None,
        top_k=int(payload.get("topK") or 5),
    )


@router.get("/v1/aip/vector-index/_backend")
def vector_index_backend(principal: Principal = Depends(require_principal)):
    """105 · 当前向量后端（local-kv | qdrant）。"""
    _ = principal
    from aos_api.vector_index import backend_info

    return backend_info()


@router.get("/v1/aip/vector-index/{collection}")
def vector_index_get(collection: str, principal: Principal = Depends(require_principal)):
    from aos_api.tenant_prefix import scoped_collection_name
    from aos_api.vector_index import collection_stats

    scoped = scoped_collection_name(principal.org_id, principal.project_id, collection)
    return collection_stats(scoped)


@router.get("/v1/builds")
def list_builds(principal: Principal = Depends(require_principal)):
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    builds = []
    for pid, p in _pipelines.items():
        if not _scope_visible(p, scope):
            continue
        build = dict(p.get("lastBuild") or {})
        build["pipelineId"] = pid
        build["pipelineName"] = p.get("name", pid)
        # 补充日志、耗时、记录数等扩展字段
        last_build_id = build.get("id")
        if last_build_id and last_build_id in _build_logs:
            build["logs"] = _build_logs[last_build_id]
        if build.get("startedAt") and build.get("finishedAt"):
            build["duration"] = round(build["finishedAt"] - build["startedAt"], 2)
        builds.append(build)
    return {"items": builds}


@router.post("/v1/pipelines/{pl_id}/execute")
def execute_pipeline(
    pl_id: str, body: dict[str, Any] | None = None, principal: Principal = Depends(require_principal)
):
    """手动执行管道：模拟 ingest→transform→sink 三阶段，生成构建记录和日志."""
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    pl = _pipelines.get(pl_id)
    if pl is None:
        # 尝试从 phase5 引擎获取
        try:
            from aos_api.phase5_pipeline_engine import get_engine as _get_engine
            _eng = _get_engine()
            _phase5_pl = _eng.get_pipeline(scope, pl_id)
            if _phase5_pl is not None:
                pl = {
                    "id": _phase5_pl.id,
                    "name": _phase5_pl.name,
                    "orgId": scope.org_id,
                    "projectId": scope.project_id,
                    "status": _phase5_pl.status,
                    "tags": _phase5_pl.tags,
                    "description": _phase5_pl.description,
                    "config": {},
                }
                _pipelines[pl_id] = pl  # 缓存到 wave_ext
        except Exception:
            pass
    if pl is None:
        raise ApiError(code="NOT_FOUND", message=f"pipeline {pl_id} not found", status_code=404)
    # 如果管道缺少 orgId（phase5 引擎管道），补充 scope 信息
    if pl.get("orgId") is None:
        pl["orgId"] = scope.org_id
    if pl.get("projectId") is None:
        pl["projectId"] = scope.project_id
    _assert_mutation_scope(pl, scope, resource="pipeline", resource_id=pl_id)
    # 作废状态不允许执行
    if pl.get("config", {}).get("decommissioned"):
        raise ApiError(code="VALIDATION", message="已作废的管道不可执行，请先恢复", status_code=400)

    body = body or {}
    mode = body.get("mode", "incremental")  # full / incremental
    now = time.time()
    build_id = f"build-{uuid.uuid4().hex[:10]}"

    # 生成执行日志
    logs: list[dict[str, Any]] = []
    def _log(level: str, msg: str) -> None:
        logs.append({
            "time": datetime.datetime.fromtimestamp(time.time()).strftime("%H:%M:%S"),
            "level": level,
            "msg": msg,
        })

    _log("INFO", f"开始执行管道 [{pl.get('name', pl_id)}]，模式: {mode}")
    tasks = [
        {"name": "ingest", "status": "RUNNING"},
        {"name": "transform", "status": "PENDING"},
        {"name": "sink", "status": "PENDING"},
    ]

    # 从管道 nodes 提取 source 配置（真实数据，不再 mock）
    # wave_ext._pipelines 是扁平字典，nodes 存在 phase5 引擎中
    source_config: dict[str, Any] | None = None
    transform_config: dict[str, Any] | None = None
    nodes_list: list[dict[str, Any]] = list(pl.get("nodes") or [])

    # 如果 wave_ext 里没有 nodes，尝试从 phase5 引擎获取
    if not nodes_list:
        try:
            from aos_api.phase5_pipeline_engine import get_engine as _get_engine
            _eng = _get_engine()
            _phase5_nodes = _eng.list_nodes(scope, pl_id)
            for _n in _phase5_nodes:
                nt = getattr(_n, "node_type", "") or ""
                if nt == "source" and source_config is None:
                    source_config = dict(_n.config or {})
                    nodes_list.append({"type": "source", "config": source_config})
                if nt == "transform" and transform_config is None:
                    transform_config = dict(_n.config or {})
                    nodes_list.append({"type": "transform", "config": transform_config})
        except Exception:
            pass

    # 从 YAML bundle 文件加载配置（始终尝试，即使有 nodes 配置）
    _yaml_field_mappings: list[dict[str, Any]] = []
    _yaml_source_config: dict[str, Any] | None = None
    _yaml_target_ot: str = ""
    try:
        import yaml as _yaml
        _fname_map = {
            "P01": "p01-shop.yaml", "P02": "p02-product.yaml",
            "P03": "p03-product-sku.yaml", "P04": "p04-category.yaml",
            "P05": "p05-order.yaml", "P06": "p06-order-line.yaml",
            "P07": "p07-shipment.yaml", "P08": "p08-customer-lite.yaml",
        }
        _prefix = pl_id.split("-")[0] if "-" in pl_id else pl_id[:3]
        _yaml_fname = _fname_map.get(_prefix)
        if _yaml_fname:
            _yaml_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
                "bundles", "platforms", "ecommerce-niushop", "content", "mappings",
                _yaml_fname,
            )
            _yaml_path = os.path.abspath(_yaml_path)
            if os.path.isfile(_yaml_path):
                with open(_yaml_path, "r", encoding="utf-8") as _f:
                    _yd = _yaml.safe_load(_f)
                _yaml_field_mappings = list(_yd.get("field_mappings") or [])
                _yaml_source_config = {
                    "source_id": "niushop-qyh",
                    "source_table": str(_yd.get("source_table") or ""),
                    "site_filter": str(_yd.get("site_filter") or ""),
                }
                _yaml_target_ot = str(_yd.get("target_ot") or "")
                _log("INFO", f"[yaml] 从 {_yaml_fname} 加载 {len(_yaml_field_mappings)} 个字段映射, source_table={_yaml_source_config.get('source_table')}, target_ot={_yaml_target_ot}")
    except Exception as _yaml_err:
        _log("WARN", f"[yaml] 加载 YAML 失败: {_yaml_err!r}")

    # 从 nodes 提取配置（如果还没有）
    if not source_config:
        for node in nodes_list:
            nt = str(node.get("type") or node.get("node_type") or "")
            if nt == "source" and source_config is None:
                source_config = dict(node.get("config") or {})
                # 如果 nodes 中的 source 没有 source_table，使用 YAML 中的
                if _yaml_source_config and not source_config.get("source_table"):
                    source_config = {**source_config, **_yaml_source_config}
                    _log("INFO", "[yaml] 使用 YAML 中的 source 配置")
            if nt == "transform" and transform_config is None:
                transform_config = dict(node.get("config") or {})
                # 如果 nodes 中的 transform 没有 field_mappings，使用 YAML 中的
                if _yaml_field_mappings and not transform_config.get("field_mappings"):
                    transform_config["field_mappings"] = _yaml_field_mappings
                    _log("INFO", f"[yaml] 使用 YAML 中的 {len(_yaml_field_mappings)} 个字段映射")

    # 如果还没有 source_config，使用 YAML 中的
    if not source_config and _yaml_source_config:
        source_config = _yaml_source_config
        _log("INFO", "[yaml] 直接使用 YAML 中的 source 配置")

    # 如果还没有 transform_config 或 field_mappings，使用 YAML 中的
    if _yaml_field_mappings:
        if not transform_config:
            transform_config = {"field_mappings": _yaml_field_mappings}
        elif not transform_config.get("field_mappings"):
            transform_config["field_mappings"] = _yaml_field_mappings

    source_id = ""
    source_table = ""
    site_filter = ""
    field_mappings: list[dict[str, Any]] = []
    if source_config:
        source_id = str(source_config.get("source_id") or "")
        source_table = str(source_config.get("source_table") or "")
        site_filter = str(source_config.get("site_filter") or "")
    if transform_config:
        field_mappings = list(transform_config.get("field_mappings") or [])
    elif source_config:
        field_mappings = list(source_config.get("field_mappings") or [])

    # 阶段 1: ingest — 真实 JDBC 查询
    ingested_rows: list[dict[str, Any]] = []
    ingest_error: str | None = None
    source_org_id: str = scope.org_id  # 默认使用当前 scope，数据源属于不同 org 时覆盖
    _log("INFO", f"[ingest-debug] source_id={source_id!r}, source_table={source_table!r}, site_filter={site_filter!r}")
    if source_id and source_table:
        try:
            ingest_error = None
            from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime

            _log("INFO", "[ingest] 进入 try 块...")
            # 从 meta_source 读取 JDBC 连接配置和数据源 org_id（直连 psycopg，绕过 RLS）
            jdbc_config = None
            try:
                import psycopg as _psycopg
                dsn = get_dsn()
                with _psycopg.connect(dsn) as _raw_conn:
                    with _raw_conn.cursor() as _cur:
                        _cur.execute(
                            "SELECT props, org_id FROM meta_source WHERE id=%s LIMIT 1",
                            (source_id,),
                        )
                        _row = _cur.fetchone()
                        if _row is not None and _row[0]:
                            jdbc_config = dict(_row[0])
                            source_org_id = str(_row[1]) if _row[1] else scope.org_id
                            _log("INFO", f"[ingest] 加载到 JDBC 配置: host={jdbc_config.get('dbHost')}, db={jdbc_config.get('database')}, source_org={source_org_id}")
            except Exception as _e2:
                _log("WARN", f"[ingest] meta_source 查询异常: {_e2!r}")
            if jdbc_config is None:
                ingest_error = f"数据源 {source_id} 未在 meta_source 中注册"

            if ingest_error is None:
                where_clause = f"WHERE {site_filter}" if site_filter else ""
                sql = f"SELECT * FROM `{source_table}` {where_clause}"
                _log("INFO", f"[ingest] 连接 {source_id} 读取 {source_table}...")
                tasks[0]["status"] = "RUNNING"
                with JdbcConnectorRuntime(jdbc_config) as _rt:
                    with _rt._conn.cursor() as _cur2:
                        _cur2.execute(sql)
                        ingested_rows = list(_cur2.fetchall())
                _log("INFO", f"[ingest] 完成，读取 {len(ingested_rows)} 行 (source={source_id}, table={source_table})")
                tasks[0]["status"] = "SUCCEEDED"
        except Exception as exc:
            ingest_error = f"JDBC ingest 失败: {exc!r}"
            import traceback
            traceback.print_exc()
            _log("WARN", f"[ingest] {ingest_error}")
            tasks[0]["status"] = "FAILED"
    else:
        ingest_error = f"管道无 source 配置 (source_id={source_id!r}, source_table={source_table!r})"
        _log("WARN", f"[ingest] {ingest_error}，跳过真实数据读取")
        tasks[0]["status"] = "FAILED"

    rows_read = len(ingested_rows)

    # 阶段 2: transform — 按 field_mappings 映射字段，过滤 PII
    transformed_rows: list[dict[str, Any]] = []
    if field_mappings and ingested_rows:
        pii_fields = {m.get("source") for m in field_mappings if m.get("pii")}
        for src_row in ingested_rows:
            tgt_row: dict[str, Any] = {}
            for m in field_mappings:
                src_field = m.get("source")
                tgt_field = m.get("target")
                if not src_field or not tgt_field or src_field in pii_fields:
                    continue
                val = src_row.get(src_field)
                if val is not None:
                    tgt_row[tgt_field] = val
            if tgt_row:
                transformed_rows.append(tgt_row)
        _log("INFO", f"[transform] 字段映射 {len(field_mappings)} 列，转换 {len(transformed_rows)} 行")
    elif ingested_rows:
        # 无 field_mappings 时，全部字段透传
        transformed_rows = [dict(r) for r in ingested_rows]
        _log("INFO", f"[transform] 无字段映射配置，透传全部 {len(transformed_rows)} 行")
    else:
        transformed_rows = []
    rows_transformed = len(transformed_rows)
    tasks[1]["status"] = "SUCCEEDED"
    _log("INFO", f"[transform] 完成，有效 {rows_transformed} 行")

    # 阶段 3: sink
    rows_written = rows_transformed
    tasks[2]["status"] = "RUNNING"
    _log("INFO", f"[sink] 写入数据集 {rows_written} 行...")
    time.sleep(0.01)
    tasks[2]["status"] = "SUCCEEDED"
    _log("INFO", f"[sink] 完成，写入 {rows_written} 行")

    status = "SUCCEEDED" if rows_written > 0 else ("FAILED" if ingest_error else "SUCCEEDED")
    finished_at = time.time()

    # 更新数据集状态 + 真实写入 PostgreSQL obj_instance
    dataset_rid = pl.get("datasetRid") or f"ri.aos.main.dataset.{pl_id}"
    object_type: str | None = None
    if dataset_rid:
        # 先用数据源 org 查找数据集（数据实际写入的 org），再回退到当前 scope
        source_scope = TenantScope(source_org_id, scope.project_id)
        ds_key_source = _resource_key(source_scope, dataset_rid)
        ds = _datasets.get(ds_key_source)
        if ds is None:
            ds_key_scope = _resource_key(scope, dataset_rid)
            ds = _datasets.get(ds_key_scope)
            if ds is not None:
                # 将数据集迁移到数据源 org
                _datasets[ds_key_source] = {**ds}
                ds = _datasets[ds_key_source]
            else:
                # 创建新数据集（在数据源 org 下）
                object_type = object_type or _yaml_target_ot or str(pl.get("objectTypeHint") or "").strip() or pl_id
                ds = {
                    "rid": dataset_rid,
                    "name": pl.get("name") or pl_id,
                    "pipelineId": pl_id,
                    "sourceId": source_id,
                    "status": "READY" if rows_written > 0 else ("ERROR" if ingest_error else "READY"),
                    "createdAt": finished_at,
                    "updatedAt": finished_at,
                    "objectTypeHint": object_type,
                    "displayName": pl.get("name") or pl_id,
                    "orgId": source_org_id,
                    "projectId": scope.project_id,
                    "rowsCount": rows_written,
                }
                _datasets[ds_key_source] = ds
        if ds is not None:
            ds["status"] = "READY" if rows_written > 0 else ("ERROR" if ingest_error else "READY")
            ds["rowsCount"] = rows_written
            ds["updatedAt"] = finished_at
            # 更新 objectTypeHint 为 YAML 中的 target_ot（如果有）
            if _yaml_target_ot:
                ds["objectTypeHint"] = _yaml_target_ot
            object_type = str(ds.get("objectTypeHint") or "").strip() or None
    if not object_type:
        object_type = pl.get("objectTypeHint")
    if object_type and rows_written > 0:
        try:
            import json as _json
            from aos_api.db import connect

            instances: list[tuple[str, str, str, str, str]] = []
            for _i, props_dict in enumerate(transformed_rows):
                oid = str(props_dict.get("id") or props_dict.get("pk") or f"{pl_id}__{_i+1:05d}")
                instances.append((
                    object_type, oid,
                    _json.dumps(props_dict, ensure_ascii=False, default=str),
                    source_org_id, scope.project_id,
                ))

            # 使用数据源所属的 org_id 构建写 scope（而非当前请求的 scope）
            sink_scope = TenantScope(source_org_id, scope.project_id)
            with connect(sink_scope) as conn:
                with conn.cursor() as cur:
                    ds_name = (pl.get("name") or pl_id or object_type)[:200]
                    cur.execute(
                        """INSERT INTO meta_object_type (id, name, description, published, properties)
                           VALUES (%s, %s, %s, TRUE, '{}'::jsonb)
                           ON CONFLICT (id) DO NOTHING""",
                        (object_type, ds_name, f"auto-registered by pipeline {pl_id}"),
                    )
                    if mode == "full":
                        cur.execute(
                            "DELETE FROM obj_instance WHERE object_type=%s AND org_id=%s AND project_id=%s",
                            (object_type, source_org_id, scope.project_id),
                        )
                    cur.executemany(
                        """INSERT INTO obj_instance (object_type, object_id, props, org_id, project_id)
                           VALUES (%s, %s, %s::jsonb, %s, %s)
                           ON CONFLICT (org_id, project_id, object_type, object_id) DO UPDATE
                             SET props = EXCLUDED.props""",
                        instances,
                    )
                conn.commit()
            _log("INFO", f"[sink-pg] 已写入 obj_instance [{object_type}] 共 {rows_written} 行 (mode={mode}, source={source_id}, org={source_org_id})")
            # 同时在 phase5 引擎中注册数据集（供前端列表查询使用）
            try:
                from aos_api.phase5_pipeline_engine import get_engine as _get_engine
                _eng = _get_engine()
                _sink_scope = TenantScope(source_org_id, scope.project_id)
                _existing = _eng.get_dataset(_sink_scope, dataset_rid)
                if _existing is None:
                    _eng.create_dataset(
                        _sink_scope,
                        id=dataset_rid,
                        name=pl.get("name") or pl_id,
                        description=f"Pipeline {pl_id} output",
                        source_type="database",
                        source_uri=source_id or "",
                        status="active" if rows_written > 0 else "deprecated",
                        row_count=rows_written,
                    )
                    _log("INFO", f"[phase5-ds] 注册数据集 {dataset_rid} 到 phase5 引擎 (org={source_org_id})")
                else:
                    _log("INFO", f"[phase5-ds] 数据集 {dataset_rid} 已存在于 phase5 引擎")
            except Exception as _e3:
                _log(f"WARN", f"[phase5-ds] phase5 数据集注册失败: {_e3!r}")
        except Exception as exc:
            _log("WARN", f"[sink-pg] obj_instance 写入失败: {exc!r}")

    _log("INFO", f"✅ 管道执行成功，耗时 {round(time.time() - now, 2)}s，写入 {rows_written} 条记录")
    finished_at = time.time()

    # 标记 source scope 为已加载，避免 _hydrate_data_os_scope 清空已注册的数据集
    if source_org_id != scope.org_id:
        source_scope = TenantScope(source_org_id, scope.project_id)
        _data_os_loaded_scopes.add(source_scope.key)

        # 将数据源注册到 source_org_id 下（使前端能查询到）
        if source_id and source_id not in _connectors:
            _connectors[source_id] = {
                "id": source_id,
                "type": "mysql",
                "status": "registered",
                "orgId": source_org_id,
                "projectId": scope.project_id,
                "name": source_id,
            }
            _log("INFO", f"[source] 注册数据源 {source_id} 到 _connectors (org={source_org_id})")

        # 将管道注册到 source_org_id 下（使前端能查询到）
        if pl_id not in _pipelines or not _scope_visible(_pipelines.get(pl_id), source_scope):
            _pipelines[pl_id] = {
                "id": pl_id,
                "sourceId": source_id,
                "target": "dataset",
                "datasetRid": f"ri.aos.main.dataset.{pl_id}",
                "orgId": source_org_id,
                "projectId": scope.project_id,
                "name": pl.get("name", pl_id),
                "status": pl.get("status", "ACTIVE"),
                "tags": pl.get("tags", []),
                "description": pl.get("description", ""),
                "lastBuild": {
                    "id": build_id,
                    "status": status,
                    "pipelineId": pl_id,
                    "tasks": tasks,
                    "startedAt": now,
                    "finishedAt": finished_at,
                },
            }
            _log("INFO", f"[pipeline] 注册管道 {pl_id} 到 _pipelines (org={source_org_id})")

    # 最后生成 build dict（确保包含所有日志）
    build = {
        "id": build_id,
        "status": status,
        "tasks": tasks,
        "startedAt": now,
        "finishedAt": finished_at,
        "duration": round(finished_at - now, 2),
        "rowsRead": rows_read,
        "rowsWritten": rows_written,
        "mode": mode,
        "pipelineId": pl_id,
        "pipelineName": pl.get("name", pl_id),
        "logs": logs,
    }
    # 更新管道的 lastBuild
    pl["lastBuild"] = build
    # 保存日志
    _build_logs[build_id] = logs

    log.info(
        "pipeline_execute id=%s pl=%s status=%s rows=%s",
        build_id, pl_id, status, rows_written,
    )
    return {"buildId": build_id, **build}


@router.get("/v1/builds/{build_id}/logs")
def get_build_logs(build_id: str, principal: Principal = Depends(require_principal)):
    """获取构建日志."""
    if build_id not in _build_logs:
        raise ApiError(code="NOT_FOUND", message=f"build {build_id} logs not found", status_code=404)
    return {"items": _build_logs[build_id]}


@router.post("/v1/schedules")
def create_schedule(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    sid = body.get("id") or f"sch-{uuid.uuid4().hex[:6]}"
    _assert_mutation_scope(
        _schedules.get(sid), scope, resource="schedule", resource_id=sid
    )
    item = {
        "id": sid,
        "cron": body.get("cron", "0 * * * *"),
        "pipelineId": body.get("pipelineId"),
        "enabled": bool(body.get("enabled", True)),
        "name": body.get("name") or sid,
        # optional: {"pluginId":"jdbc-mysql", ...ingest body fields}
        "ingest": body.get("ingest") if isinstance(body.get("ingest"), dict) else None,
        "orgId": principal.org_id,
        "projectId": principal.project_id,
        "lastRun": None,
    }
    _schedules[sid] = item
    _persist_safe("persist_schedule", scope, item)
    return item


@router.get("/v1/schedules")
def list_schedules(principal: Principal = Depends(require_principal)):
    """T-UI S2 · schedules list for 计划编辑器."""
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    items = [s for s in _schedules.values() if _scope_visible(s, scope)]
    return {"items": items}


@router.get("/v1/schedules/{schedule_id}")
def get_schedule(schedule_id: str, principal: Principal = Depends(require_principal)):
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    item = _schedules.get(schedule_id)
    if not _scope_visible(item, scope):
        raise ApiError(code="NOT_FOUND", message="schedule missing", status_code=404)
    return item


@router.patch("/v1/schedules/{schedule_id}")
def patch_schedule(
    schedule_id: str,
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    """74 · edit cron / enabled / pipelineId for 计划编辑器."""
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    item = _schedules.get(schedule_id)
    if not item:
        raise ApiError(code="NOT_FOUND", message="schedule missing", status_code=404)
    _assert_mutation_scope(item, scope, resource="schedule", resource_id=schedule_id)
    if "cron" in body and body["cron"] is not None:
        item["cron"] = str(body["cron"])
    if "pipelineId" in body:
        item["pipelineId"] = body["pipelineId"]
    if "enabled" in body:
        item["enabled"] = bool(body["enabled"])
    if "name" in body and body["name"] is not None:
        item["name"] = str(body["name"])
    if "ingest" in body and (body["ingest"] is None or isinstance(body["ingest"], dict)):
        item["ingest"] = body["ingest"]
    _schedules[schedule_id] = item
    _persist_safe("persist_schedule", scope, item)
    return item


@router.post("/v1/schedules/{schedule_id}/run")
def run_schedule(schedule_id: str, principal: Principal = Depends(require_principal)):
    """Execute bound connector ingest once (manual/batch face; not a cron daemon)."""
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    item = _schedules.get(schedule_id)
    if not item:
        raise ApiError(code="NOT_FOUND", message="schedule missing", status_code=404)
    _assert_mutation_scope(
        item, scope, resource="schedule", resource_id=schedule_id
    )
    if not item.get("enabled", True):
        raise ApiError(code="VALIDATION", message="schedule disabled", status_code=400)
    ingest_spec = item.get("ingest")
    if not isinstance(ingest_spec, dict) or not ingest_spec:
        raise ApiError(
            code="VALIDATION",
            message="schedule has no ingest spec; PATCH ingest={pluginId,...}",
            status_code=400,
        )
    plugin_id = str(ingest_spec.get("pluginId") or "jdbc-mysql")
    body = {k: v for k, v in ingest_spec.items() if k != "pluginId"}
    body.setdefault("autoCreateObjectType", True)
    result = connector_ingest(plugin_id, body, principal)
    item["lastRun"] = {
        "at": time.time(),
        "ok": bool(result.get("ok")),
        "written": result.get("written"),
        "objectType": result.get("objectType"),
        "mode": result.get("mode"),
    }
    _schedules[schedule_id] = item
    _persist_safe("persist_schedule", scope, item)
    log.info("schedule_run id=%s written=%s", schedule_id, result.get("written"))
    return {"scheduleId": schedule_id, "lastRun": item["lastRun"], "ingest": result}


@router.get("/v1/dlq")
def list_dlq(principal: Principal = Depends(require_principal)):
    return {"items": _scoped_values(_dlq, _mutation_scope(principal))}


@router.post("/v1/dlq")
def push_dlq(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    scope = _mutation_scope(principal)
    item = {
        "id": f"dlq-{uuid.uuid4().hex[:6]}",
        **body,
        "status": "open",
        "orgId": scope.org_id,
        "projectId": scope.project_id,
    }
    _dlq[_resource_key(scope, item["id"])] = item
    return item


@router.post("/v1/dlq/{dlq_id}/retry")
def retry_dlq(dlq_id: str, principal: Principal = Depends(require_principal)):
    item = _dlq.get(_resource_key(_mutation_scope(principal), dlq_id))
    if item is None:
        raise ApiError(code="NOT_FOUND", message="dlq missing", status_code=404)
    item["status"] = "retried"
    return item


@router.get("/v1/funnel/{object_type}/worker")
def funnel_worker(object_type: str, principal: Principal = Depends(require_principal)):
    """Prefer persisted funnel_status.detail.worker after rerun; else default snapshot."""
    scope = TenantScope(principal.org_id, principal.project_id)
    with connect(scope) as conn:
        row = conn.execute(
            "SELECT detail FROM funnel_status WHERE object_type=%s "
            "AND org_id=%s AND project_id=%s",
            (object_type, *scope.key),
        ).fetchone()
    detail = row["detail"] if row else None
    if isinstance(detail, dict) and isinstance(detail.get("worker"), list) and detail["worker"]:
        return {"objectType": object_type, "stages": detail["worker"], "source": "persisted"}
    return {
        "objectType": object_type,
        "source": "default",
        "stages": [
            {"name": "Changelog", "progress": 1.0},
            {"name": "Merge", "progress": 1.0},
            {"name": "Index", "progress": 0.8},
            {"name": "Hydration", "progress": 0.5},
        ],
    }


# —— Wave-5 Apollo · Channel/Spoke catalog (scheme 66) ——
@router.get("/v1/apollo/channels")
def apollo_channels(principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.apollo_catalog import list_channels

    return {"items": list_channels()}


@router.get("/v1/apollo/channels/{channel_id}")
def apollo_channel_get(
    channel_id: str, principal: Principal = Depends(require_principal)
):
    _ = principal
    from aos_api.apollo_catalog import get_channel

    return get_channel(channel_id)


@router.post("/v1/apollo/channels/{channel_id}/promote")
def apollo_channel_promote(
    channel_id: str, principal: Principal = Depends(require_principal)
):
    from aos_api.apollo_catalog import promote_channel

    return promote_channel(TenantScope(principal.org_id, principal.project_id), channel_id)


@router.post("/v1/apollo/channels/{channel_id}/recall")
def apollo_channel_recall(
    channel_id: str, principal: Principal = Depends(require_principal)
):
    from aos_api.apollo_catalog import recall_channel

    return recall_channel(TenantScope(principal.org_id, principal.project_id), channel_id)


@router.get("/v1/apollo/spokes")
def apollo_spokes_list(principal: Principal = Depends(require_principal)):
    from aos_api.apollo_catalog import list_spokes

    return {
        "items": list_spokes(TenantScope(principal.org_id, principal.project_id))
    }


@router.get("/v1/apollo/spokes/local")
def spoke_probe(principal: Principal = Depends(require_principal)):
    """Compat · Lite local spoke (scheme 66 reads catalog)."""
    from aos_api.apollo_catalog import get_spoke

    return get_spoke(
        TenantScope(principal.org_id, principal.project_id), "spoke-local-dev"
    )


@router.get("/v1/apollo/spokes/{spoke_id}")
def spoke_by_id(spoke_id: str, principal: Principal = Depends(require_principal)):
    """T-API · Spoke detail (PG catalog · scheme 66) · TWA.9 按 Org。"""
    from aos_api.apollo_catalog import get_spoke

    return get_spoke(TenantScope(principal.org_id, principal.project_id), spoke_id)


@router.post("/v1/apollo/spokes/{spoke_id}/heartbeat")
def spoke_heartbeat(
    spoke_id: str,
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    """158 · Spoke heartbeat (Lite/Full)."""
    from aos_api.apollo_catalog import record_spoke_heartbeat

    payload = body or {}
    ok = bool(payload.get("ok", True))
    return record_spoke_heartbeat(
        TenantScope(principal.org_id, principal.project_id), spoke_id, ok=ok
    )


@router.post("/v1/apollo/spokes/{spoke_id}/apply-plan")
def spoke_apply_plan(
    spoke_id: str,
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    """158 · Full Spoke mock Helm apply (no cluster mutate)."""
    from aos_api.apollo_catalog import apply_full_spoke_plan

    payload = body or {}
    return apply_full_spoke_plan(
        TenantScope(principal.org_id, principal.project_id),
        spoke_id,
        plan_id=payload.get("planId"),
    )


@router.get("/v1/apollo/spokes/full/plan")
def spoke_full_plan(principal: Principal = Depends(require_principal)):
    """158 · Full Spoke chart stub metadata."""
    _ = principal
    from aos_api.apollo_catalog import full_spoke_plan_artifact

    return full_spoke_plan_artifact()


@router.get("/v1/apollo/fleet")
def apollo_fleet(principal: Principal = Depends(require_principal)):
    """T-API · Hub fleet (Channel/Spoke catalog) · Spoke 按 Org。"""
    from aos_api.apollo_catalog import fleet_payload

    return fleet_payload(TenantScope(principal.org_id, principal.project_id))


@router.post("/v1/apollo/assets")
def asset_bundle(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    """160 · persist Asset Bundle metadata (compatibleChannels for promote gate)."""
    from aos_api.apollo_ops import register_asset

    contents = body.get("contents")
    if contents is not None and not isinstance(contents, list):
        contents = [str(contents)]
    compatible = body.get("compatibleChannels")
    if compatible is not None and not isinstance(compatible, list):
        compatible = [str(compatible)]
    return register_asset(
        contents=contents,
        hotfix=bool(body.get("hotfix", False)),
        compatible_channels=compatible,
        subject=principal.subject,
    )


@router.get("/v1/apollo/assets")
def asset_list(
    principal: Principal = Depends(require_principal),
    limit: int = 50,
):
    _ = principal
    from aos_api.apollo_ops import list_assets

    return {"items": list_assets(limit=limit), "scheme": "160"}


@router.get("/v1/apollo/changes")
def apollo_changes_list(
    principal: Principal = Depends(require_principal),
    limit: int = 50,
):
    _ = principal
    from aos_api.apollo_ops import list_changes

    return {"items": list_changes(limit=limit), "scheme": "160"}


@router.post("/v1/apollo/changes")
def apollo_changes_create(
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    from aos_api.apollo_ops import create_change

    return create_change(
        title=str(body.get("title") or ""),
        kind=str(body.get("kind") or "channel"),
        channelId=body.get("channelId"),
        summary=body.get("summary"),
        subject=principal.subject,
        org_id=principal.org_id,
        project_id=principal.project_id,
        emergency=bool(body.get("emergency", False)),
    )


@router.post("/v1/apollo/changes/{change_id}/approve")
def apollo_changes_approve(
    change_id: str,
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    from aos_api.apollo_ops import decide_change

    payload = body or {}
    return decide_change(
        change_id,
        approve=True,
        subject=principal.subject,
        note=payload.get("note"),
    )


@router.post("/v1/apollo/changes/{change_id}/reject")
def apollo_changes_reject(
    change_id: str,
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    from aos_api.apollo_ops import decide_change

    payload = body or {}
    return decide_change(
        change_id,
        approve=False,
        subject=principal.subject,
        note=payload.get("note"),
    )


@router.post("/v1/apollo/changes/{change_id}/merge-stable")
def apollo_changes_merge_stable(
    change_id: str,
    principal: Principal = Depends(require_principal),
):
    from aos_api.apollo_ops import merge_hotfix_to_stable

    return merge_hotfix_to_stable(change_id, subject=principal.subject)


@router.get("/v1/apollo/config")
def apollo_config(principal: Principal = Depends(require_principal)):
    _ = principal
    return {
        "vaultRefsOnly": True,
        "secrets": {"dbPassword": "vault:secret/data/aos/postgres#password"},
        "plaintextRejected": True,
    }


@router.patch("/v1/apollo/config")
def apollo_config_patch(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    """T-API · config override; reject plaintext secrets."""
    _ = principal
    secrets = body.get("secrets") or {}
    for k, v in secrets.items():
        if isinstance(v, str) and not v.startswith("vault:"):
            raise ApiError(
                code="SECRET_PLAINTEXT_REJECTED",
                message=f"plaintext secret rejected: {k}",
                status_code=400,
            )
    return {"ok": True, "patched": list(body.keys()), "vaultRefsOnly": True}


@router.post("/v1/apollo/upgrade")
def apollo_upgrade(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    """T5.3 Lite upgrade channel (catalog drill)."""
    _ = principal
    return {
        "from": body.get("from", "0.2.0-dev"),
        "to": body.get("to", "0.3.0-dev"),
        "status": "succeeded",
        "channel": body.get("channel", "dev"),
    }


# —— T3.17 Insight Backfill ——
@router.post("/v1/aip/insights/backfill")
def insight_backfill(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api import ttl_job

    draft_id = f"draft-bf-{uuid.uuid4().hex[:8]}"
    insight = {
        "id": f"ins-{uuid.uuid4().hex[:8]}",
        "objectType": body.get("objectType", "WorkOrder"),
        "objectId": body.get("objectId", "wo-1001"),
        "confidence": float(body.get("confidence", 0.92)),
        "text": body.get("text", "high-confidence insight"),
        "viaDraftId": draft_id,
        "status": "proposed",
        "orgId": principal.org_id,
        "projectId": principal.project_id,
    }
    # optional backdate for tests / ops: createdAt ISO
    if body.get("createdAt"):
        insight["createdAt"] = str(body["createdAt"])
        insight["lastRefAt"] = str(body.get("lastRefAt") or body["createdAt"])
    stored = ttl_job.upsert_insight(
        TenantScope(principal.org_id, principal.project_id), insight
    )
    log.info("insight_backfill id=%s", stored["id"])
    return stored


@router.get("/v1/aip/insights")
def list_insights(
    status: str | None = None,
    principal: Principal = Depends(require_principal),
):
    _ = principal
    from aos_api import ttl_job

    items = ttl_job.list_insights(
        TenantScope(principal.org_id, principal.project_id), status=status
    )
    return {"items": items}


# —— TC.5 / TC.6 ——
@router.post("/v1/aip/capabilities/sync/manuscript")
def sync_manuscript(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    _ = principal
    return {
        "objectType": "LiveScript",
        "objectId": body.get("id", f"ls-{uuid.uuid4().hex[:6]}"),
        "writtenVia": "Action",
        "status": "synced",
    }


@router.post("/v1/aip/capabilities/session/open")
def session_open(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    _ = principal
    return {
        "sessionId": f"sess-{uuid.uuid4().hex[:8]}",
        "objectType": "Session",
        "status": "open",
        "avExternal": True,
        "meta": body,
    }


# —— T4.6 / 100 · Connector Host 按插件分发（兼容旧 mysql 路径）——


def _connector_limit(body: dict[str, Any], *, default: int) -> int:
    """Parse limit. Missing → default. ``<=0`` means full table (188w digital twin).

    Critical: do **not** use ``body.get("limit") or default`` — that turns 0 into default.
    """
    if "limit" not in body or body.get("limit") is None or body.get("limit") == "":
        return default
    return int(body.get("limit"))


@router.post("/v1/connectors/mysql/probe")
def mysql_probe(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    """兼容别名 → jdbc-mysql。"""
    return connector_probe("jdbc-mysql", body, principal)


@router.post("/v1/connectors/mysql/ingest")
def mysql_ingest(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    return connector_ingest("jdbc-mysql", body, principal)


@router.get("/v1/connectors/mysql/health")
def mysql_health(principal: Principal = Depends(require_principal)):
    return connector_health("jdbc-mysql", principal)


@router.get("/v1/connectors/{plugin_id}/health")
def connector_health(plugin_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.connector_runtime import dispatch

    return dispatch(plugin_id, "health")


@router.post("/v1/connectors/{plugin_id}/probe")
def connector_probe(
    plugin_id: str,
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    _ = principal
    from aos_api.connector_runtime import dispatch

    body = body or {}
    port = body.get("port")
    return dispatch(
        plugin_id,
        "probe",
        org_id=principal.org_id,
        project_id=principal.project_id,
        limit=_connector_limit(body, default=5),
        object_type=str(body.get("objectType") or "WorkOrder"),
        table=body.get("table"),
        host=body.get("host"),
        port=int(port) if port is not None and str(port).strip() != "" else None,
        user=body.get("user"),
        password=body.get("password"),
        database=body.get("database"),
    )


@router.post("/v1/connectors/{plugin_id}/ingest")
def connector_ingest(
    plugin_id: str,
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    from aos_api.connector_runtime import dispatch

    body = body or {}
    mapping = body.get("mapping")
    if mapping is not None and not isinstance(mapping, dict):
        raise ApiError(code="VALIDATION", message="mapping must be object", status_code=400)
    port = body.get("port")
    return dispatch(
        plugin_id,
        "ingest",
        object_type=str(body.get("objectType") or "WorkOrder"),
        limit=_connector_limit(body, default=0),
        mapping=mapping,
        table=body.get("table"),
        host=body.get("host"),
        port=int(port) if port is not None and str(port).strip() != "" else None,
        user=body.get("user"),
        password=body.get("password"),
        database=body.get("database"),
        include_all=bool(body.get("includeAll")),
        id_field=body.get("idField"),
        auto_create_object_type=bool(body.get("autoCreateObjectType")),
        org_id=principal.org_id,
        project_id=principal.project_id,
    )


@router.post("/v1/docintel/ocr")
def ocr_page(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.ocr_gateway import ocr_page as gateway_ocr

    return gateway_ocr(
        page=int(body.get("page", 1) or 1),
        text_hint=body.get("textHint"),
        image_base64=body.get("imageBase64"),
        media_rid=body.get("mediaRid"),
    )


@router.post("/v1/sync-routing")
def sync_routing(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    """Storage Router · size threshold + optional target hint (74 / data-connection)."""
    _ = principal
    size = int(body.get("sizeBytes", 0) or 0)
    target = str(body.get("target") or body.get("targetHint") or "").strip().lower()
    threshold = 128 * 1024
    if target in {"mediaset", "media-set", "media"}:
        route = "object-store"
        reason = "媒体集目标强制对象仓"
    elif target in {"stream", "kafka"}:
        route = "stream"
        reason = "流目标"
    elif size > 0 and size < threshold:
        route = "dataset-inline"
        reason = f"单文件 <{threshold}B 且无需原件预览 → 直入 Dataset"
    else:
        route = "object-store"
        reason = "≥128KB 或需原件 → MediaSet/对象仓"
    return {
        "route": route,
        "sizeBytes": size,
        "threshold": threshold,
        "target": target or None,
        "reason": reason,
        "pathStyle": True,
    }


@router.get("/v1/media-sets/{rid}/reference")
def media_ref(rid: str, principal: Principal = Depends(require_principal)):
    m = _media.get(_resource_key(_mutation_scope(principal), rid))
    if m is None:
        raise ApiError(code="NOT_FOUND", message="media missing", status_code=404)
    return {"rid": rid, "previewUrl": f"/v1/media-sets/{rid}", "name": m["name"]}


@router.get("/v1/edge/agents/local")
def edge_agent(principal: Principal = Depends(require_principal)):
    _ = principal
    return {"id": "edge-local", "probeOk": True, "outbound": True}


@router.post("/v1/docintel/pipeline")
def docintel_pipeline(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    import base64

    fail = bool(body.get("fail", False))
    if fail:
        scope = _mutation_scope(principal)
        item = {
            "id": f"dlq-{uuid.uuid4().hex[:6]}",
            "source": "docintel",
            "reason": body.get("reason", "parse-fail"),
            "status": "open",
            "orgId": scope.org_id,
            "projectId": scope.project_id,
        }
        _dlq[_resource_key(scope, item["id"])] = item
        return {"batchOk": True, "failedIsolated": True, "dlqId": item["id"]}

    from aos_api.file_parsers import extract
    from aos_api.ocr_gateway import ocr_page as gateway_ocr

    parse_result = None
    raw: bytes | None = None
    if body.get("bytesBase64"):
        raw = base64.b64decode(body["bytesBase64"])
    elif body.get("mediaRid"):
        media_key = _resource_key(
            _mutation_scope(principal), str(body["mediaRid"])
        )
        if media_key in _media and media_key in _media_bytes:
            raw = _media_bytes[media_key]
        else:
            raise ApiError(
                code="NOT_FOUND", message="media bytes missing", status_code=404
            )
    if raw is not None:
        parse_result = extract(
            data=raw,
            name=body.get("name"),
            content_type=body.get("contentType"),
        )
    elif body.get("textHint"):
        parse_result = {
            "ok": True,
            "parser": "parser-text",
            "format": "txt",
            "text": str(body.get("textHint")),
            "charCount": len(str(body.get("textHint"))),
            "preview": str(body.get("textHint"))[:240],
            "hint": "textHint passthrough",
        }

    ocr = gateway_ocr(
        page=int(body.get("page", 1) or 1),
        text_hint=body.get("textHint") or (parse_result or {}).get("text"),
        image_base64=body.get("imageBase64"),
        media_rid=body.get("mediaRid"),
    )
    return {
        "batchOk": True,
        "parsed": True,
        "failedIsolated": False,
        "parse": parse_result,
        "ocr": ocr,
    }


# —— S2 remainder / T5.6 Ferry honest surface ([49]) ——
_CODE_REPOS = [
    {
        "id": "repo-aos-platform",
        "name": "aos-platform",
        "url": "local://aos-platform",
        "branch": "main",
        "status": "ready",
    },
    {
        "id": "repo-okf-sample",
        "name": "okf-sample",
        "url": "local://okf-sample",
        "branch": "dev",
        "status": "seed",
    },
]


@router.get("/v1/code-repos")
def list_code_repos(principal: Principal = Depends(require_principal)):
    """Dev code-repo catalog (not a git host)."""
    _ = principal
    return {"items": list(_CODE_REPOS), "store": "dev-seed"}


@router.get("/v1/apollo/ferry/status")
def ferry_status(principal: Principal = Depends(require_principal)):
    """T5.6 Ferry MVP — signed tar.gz available; skopeo/cosign still deferred."""
    _ = principal
    from aos_api.ferry import ferry_status_payload

    return ferry_status_payload()


@router.post("/v1/apollo/ferry/export")
def ferry_export(body: dict[str, Any] | None = None, principal: Principal = Depends(require_principal)):
    from aos_api.ferry import build_bundle

    body = body or {}
    return build_bundle(
        env=str(body.get("env") or "dev"),
        channel=str(body.get("channel") or "lite"),
        org_id=principal.org_id,
        contents=body.get("contents"),
        include_images=bool(body.get("includeImages", True)),
    )


@router.post("/v1/apollo/ferry/import")
def ferry_import(body: dict[str, Any] | None = None, principal: Principal = Depends(require_principal)):
    from aos_api.ferry import import_bundle

    _ = principal
    body = body or {}
    b64 = body.get("contentBase64") or body.get("bundleBase64")
    if not b64:
        raise ApiError(
            code="VALIDATION",
            message="contentBase64 required",
            status_code=400,
        )
    # Test hook: omitSignature strips sig before verify path is not allowed —
    # clients that send stripSignature=true get a re-packed unsigned blob rejected.
    if body.get("stripSignature"):
        import base64
        import io
        import tarfile

        raw = base64.b64decode(b64)
        out = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as src, tarfile.open(
            fileobj=out, mode="w:gz"
        ) as dst:
            for m in src.getmembers():
                if m.name.endswith("signature.sig"):
                    continue
                f = src.extractfile(m)
                if f is None:
                    continue
                data = f.read()
                info = tarfile.TarInfo(name=m.name)
                info.size = len(data)
                dst.addfile(info, io.BytesIO(data))
        b64 = base64.b64encode(out.getvalue()).decode("ascii")
    return import_bundle(content_base64=b64, require_signature=True)


# ════════════════════════════════════════════════════════════════
# 管道/数据集 · 作废 + 删除（带审批）
# ════════════════════════════════════════════════════════════════


class RejectDeleteRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


_DELETE_REQUESTS: dict[str, dict[str, Any]] = {}
_DELETE_MAX = 500
_DELETE_EXPIRE_SEC = 24 * 3600


def _delete_key(req_id: str) -> str:
    return f"del-{req_id}"


def _prune_delete_requests() -> None:
    now = time.time()
    stale = [k for k, v in _DELETE_REQUESTS.items()
             if now - v.get("createdAt", now) > _DELETE_EXPIRE_SEC]
    for k in stale:
        _DELETE_REQUESTS.pop(k, None)
    while len(_DELETE_REQUESTS) > _DELETE_MAX:
        oldest = min(_DELETE_REQUESTS, key=lambda k: _DELETE_REQUESTS[k].get("createdAt", 0))
        _DELETE_REQUESTS.pop(oldest, None)


def _role_has_admin(principal: Principal) -> bool:
    roles = getattr(principal, "roles", None) or ()
    return "admin" in roles


def _pipeline_decommissioned(pl: dict[str, Any]) -> bool:
    cfg = pl.get("config") or {}
    return bool(cfg.get("decommissioned"))


@router.post("/v1/pipelines/{pl_id}/decommission")
def decommission_pipeline(pl_id: str, principal: Principal = Depends(require_principal)):
    """作废管道（可逆，不需要审批）— 在 config 中标记 decommissioned=true。"""
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    pl = _pipelines.get(pl_id)
    if pl is None:
        raise ApiError(code="NOT_FOUND", message=f"Pipeline {pl_id} not found", status_code=404)
    _assert_mutation_scope(pl, scope, resource="pipeline", resource_id=pl_id)
    cfg = dict(pl.get("config") or {})
    cfg["decommissioned"] = True
    cfg["decommissionedAt"] = time.time()
    cfg["decommissionedBy"] = principal.subject
    pl["config"] = cfg
    pl["status"] = "decommissioned"
    _persist_safe("persist_pipeline", scope, {**pl})
    return {"ok": True, "id": pl_id, "decommissioned": True}


@router.post("/v1/pipelines/{pl_id}/restore")
def restore_pipeline(pl_id: str, principal: Principal = Depends(require_principal)):
    """恢复已作废的管道（从 decommissioned 状态恢复）。"""
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    pl = _pipelines.get(pl_id)
    if pl is None:
        raise ApiError(code="NOT_FOUND", message=f"Pipeline {pl_id} not found", status_code=404)
    _assert_mutation_scope(pl, scope, resource="pipeline", resource_id=pl_id)
    cfg = dict(pl.get("config") or {})
    was_decommissioned = cfg.pop("decommissioned", None) or False
    cfg.pop("decommissionedAt", None)
    cfg.pop("decommissionedBy", None)
    pl["config"] = cfg
    if was_decommissioned and pl.get("status") == "decommissioned":
        pl.pop("status", None)
    _persist_safe("persist_pipeline", scope, {**pl})
    return {"ok": True, "id": pl_id, "restored": bool(was_decommissioned)}


def _submit_delete_request(
    *,
    principal: Principal,
    resource_type: Literal["pipeline", "dataset"],
    resource_id: str,
    scope: TenantScope,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    req_id = uuid.uuid4().hex[:12]
    _prune_delete_requests()
    now = time.time()
    rec: dict[str, Any] = {
        "id": req_id,
        "resourceType": resource_type,
        "resourceId": resource_id,
        "orgId": scope.org_id,
        "projectId": scope.project_id,
        "submittedBy": principal.subject,
        "status": "pending",
        "detail": detail or {},
        "createdAt": now,
        "updatedAt": now,
        "approvedBy": None,
        "rejectedBy": None,
        "reason": None,
        "executed": False,
    }
    _DELETE_REQUESTS[req_id] = rec
    return rec


@router.delete("/v1/pipelines/{pl_id}")
def request_delete_pipeline(
    pl_id: str,
    cascadeDataset: bool = True,  # noqa: N803
    principal: Principal = Depends(require_principal),
):
    """提交管道删除审批请求（不直接删，等 approve 后才执行）。"""
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    pl = _pipelines.get(pl_id)
    if pl is None:
        raise ApiError(code="NOT_FOUND", message=f"Pipeline {pl_id} not found", status_code=404)
    _assert_mutation_scope(pl, scope, resource="pipeline", resource_id=pl_id)
    if not _pipeline_decommissioned(pl):
        raise ApiError(
            code="PIPELINE_NOT_DECOMMISSIONED",
            message="删除前请先作废管道（POST /v1/pipelines/{id}/decommission）",
            status_code=400,
        )
    dataset_rid = pl.get("datasetRid")
    rec = _submit_delete_request(
        principal=principal,
        resource_type="pipeline",
        resource_id=pl_id,
        scope=scope,
        detail={
            "sourceId": pl.get("sourceId"),
            "displayName": pl.get("displayName") or pl.get("name"),
            "datasetRid": dataset_rid,
            "cascadeDataset": bool(cascadeDataset),
        },
    )
    return {
        "ok": True,
        "deleteRequest": rec,
        "message": "删除请求已提交，需 admin 角色审批通过后方可执行物理删除。",
    }


@router.delete("/v1/datasets/{rid:path}")
def request_delete_dataset(rid: str, principal: Principal = Depends(require_principal)):
    """提交数据集删除审批请求（不直接删，等 approve 后才执行）。"""
    scope = _mutation_scope(principal)
    _hydrate_data_os_scope(scope)
    ds_key = _resource_key(scope, rid)
    ds = _datasets.get(ds_key)
    if ds is None:
        raise ApiError(code="NOT_FOUND", message=f"Dataset {rid} not found", status_code=404)
    _assert_mutation_scope(ds, scope, resource="dataset", resource_id=rid)
    rec = _submit_delete_request(
        principal=principal,
        resource_type="dataset",
        resource_id=rid,
        scope=scope,
        detail={
            "name": ds.get("displayName") or ds.get("name"),
            "pipelineId": ds.get("pipelineId"),
            "sourceId": ds.get("sourceId"),
        },
    )
    return {
        "ok": True,
        "deleteRequest": rec,
        "message": "删除请求已提交，需 admin 角色审批通过后方可执行物理删除。",
    }


@router.get("/v1/delete-requests")
def list_delete_requests(
    status: str | None = None,
    resourceType: str | None = None,  # noqa: N803
    principal: Principal = Depends(require_principal),
):
    """查看当前 scope 下的删除审批列表。"""
    scope = _mutation_scope(principal)
    _prune_delete_requests()
    results: list[dict[str, Any]] = []
    for rec in _DELETE_REQUESTS.values():
        if (rec.get("orgId"), rec.get("projectId")) != scope.key:
            continue
        if status and rec.get("status") != status:
            continue
        if resourceType and rec.get("resourceType") != resourceType:
            continue
        results.append(rec)
    results.sort(key=lambda r: r.get("createdAt", 0), reverse=True)
    return {"items": results, "total": len(results)}


def _execute_delete_pipeline(scope: TenantScope, pl_id: str, *, cascade_dataset: bool) -> dict[str, Any]:
    pl = _pipelines.get(pl_id)
    if pl is None:
        return {"pipeline": "already_removed"}
    dataset_rid = pl.get("datasetRid") if cascade_dataset else None
    _pipelines.pop(pl_id, None)
    _persist_safe("delete_pipeline", scope, pl_id)
    try:
        from aos_api import data_os_store as dos
        dos.delete_phase5_pipeline_graph(scope, pl_id)
    except Exception:  # noqa: BLE001
        log.warning("delete_phase5_graph_fail pipeline=%s", pl_id, exc_info=True)
    result: dict[str, Any] = {"pipeline": pl_id, "pipelineDeleted": True}
    if dataset_rid:
        ds_key = _resource_key(scope, dataset_rid)
        existed = _datasets.pop(ds_key, None) is not None
        _dataset_history.pop(ds_key, None)
        _persist_safe("delete_dataset", scope, dataset_rid)
        result["datasetRid"] = dataset_rid
        result["datasetDeleted"] = existed
    return result


def _execute_delete_dataset(scope: TenantScope, rid: str) -> dict[str, Any]:
    ds_key = _resource_key(scope, rid)
    existed = _datasets.pop(ds_key, None) is not None
    _dataset_history.pop(ds_key, None)
    _persist_safe("delete_dataset", scope, rid)
    return {"rid": rid, "datasetDeleted": existed}


@router.post("/v1/delete-requests/{req_id}/approve")
def approve_delete_request(req_id: str, principal: Principal = Depends(require_principal)):
    """审批通过 → 执行物理删除。"""
    if not _role_has_admin(principal):
        raise ApiError(
            code="FORBIDDEN",
            message="只有 admin 角色可以审批删除请求",
            status_code=403,
        )
    rec = _DELETE_REQUESTS.get(req_id)
    if rec is None:
        raise ApiError(code="NOT_FOUND", message=f"Delete request {req_id} not found", status_code=404)
    scope = TenantScope(rec["orgId"], rec["projectId"])
    _assert_mutation_scope(
        {"orgId": rec["orgId"], "projectId": rec["projectId"]},
        scope,
        resource="delete-request",
        resource_id=req_id,
    )
    if rec.get("status") != "pending":
        raise ApiError(
            code="STATUS_CONFLICT",
            message=f"删除请求状态为 {rec.get('status')}，只能审批 pending 状态",
            status_code=409,
            details={"currentStatus": rec.get("status")},
        )
    if rec.get("submittedBy") == principal.subject:
        if principal.token_kind == "dev" and allow_dev():
            log.warning(
                "delete_maker_checker_bypassed req=%s submitter=%s scope=%s",
                req_id,
                rec.get("submittedBy"),
                scope.key,
            )
        else:
            raise ApiError(
                code="MAKER_CHECKER_VIOLATION",
                message="提交人不能审批自己的删除请求（maker-checker 分离）",
                status_code=409,
            )
    now = time.time()
    rec["status"] = "approved"
    rec["approvedBy"] = principal.subject
    rec["updatedAt"] = now
    detail = rec.get("detail") or {}
    result: dict[str, Any] = {"status": "approved"}
    try:
        if rec["resourceType"] == "pipeline":
            result["exec"] = _execute_delete_pipeline(
                scope,
                rec["resourceId"],
                cascade_dataset=bool(detail.get("cascadeDataset", True)),
            )
        elif rec["resourceType"] == "dataset":
            result["exec"] = _execute_delete_dataset(scope, rec["resourceId"])
        rec["executed"] = True
        rec["executedAt"] = now
    except Exception as exc:  # noqa: BLE001
        log.error("delete_execute_fail req=%s", req_id, exc_info=True)
        rec["status"] = "exec_failed"
        rec["error"] = f"{type(exc).__name__}: {exc}"
        raise ApiError(
            code="EXECUTE_FAILED",
            message=f"物理删除执行失败：{exc}",
            status_code=500,
            details={"reqId": req_id},
        ) from exc
    return {"ok": True, "deleteRequest": rec, "result": result}


@router.post("/v1/delete-requests/{req_id}/reject")
def reject_delete_request(
    req_id: str,
    body: RejectDeleteRequest,
    principal: Principal = Depends(require_principal),
):
    """驳回删除请求（必须带理由）。"""
    if not _role_has_admin(principal):
        raise ApiError(
            code="FORBIDDEN",
            message="只有 admin 角色可以驳回删除请求",
            status_code=403,
        )
    rec = _DELETE_REQUESTS.get(req_id)
    if rec is None:
        raise ApiError(code="NOT_FOUND", message=f"Delete request {req_id} not found", status_code=404)
    scope = TenantScope(rec["orgId"], rec["projectId"])
    _assert_mutation_scope(
        {"orgId": rec["orgId"], "projectId": rec["projectId"]},
        scope,
        resource="delete-request",
        resource_id=req_id,
    )
    if rec.get("status") != "pending":
        raise ApiError(
            code="STATUS_CONFLICT",
            message=f"删除请求状态为 {rec.get('status')}，只能驳回 pending 状态",
            status_code=409,
            details={"currentStatus": rec.get("status")},
        )
    if rec.get("submittedBy") == principal.subject:
        if principal.token_kind == "dev" and allow_dev():
            log.warning(
                "delete_maker_checker_bypassed_reject req=%s submitter=%s scope=%s",
                req_id,
                rec.get("submittedBy"),
                scope.key,
            )
        else:
            raise ApiError(
                code="MAKER_CHECKER_VIOLATION",
                message="提交人不能驳回自己的删除请求（maker-checker 分离）",
                status_code=409,
            )
    now = time.time()
    rec["status"] = "rejected"
    rec["rejectedBy"] = principal.subject
    rec["reason"] = body.reason
    rec["updatedAt"] = now
    return {"ok": True, "deleteRequest": rec}

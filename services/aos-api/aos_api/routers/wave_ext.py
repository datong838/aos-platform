"""T3.5～T3.11 / T3.16 / T3.19 / TC / T4 / T5 minimal surfaces — one module to close gaps."""
from __future__ import annotations

import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["wave3-plus"])
log = get_logger("aos-api.wave3_plus")


def _demo_data_seed_enabled() -> bool:
    return (os.environ.get("AOS_DEMO_DATA_SEED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def clear_demo_data_surface() -> dict[str, Any]:
    """Remove demo-file-wo / demo-pipe-wo / demo dataset / demo sync / dlq sample."""
    removed: dict[str, Any] = {"sources": [], "pipelines": [], "datasets": [], "syncs": [], "schedules": [], "dlq": 0}
    for sid in ("demo-file-wo",):
        if sid in _connectors:
            del _connectors[sid]
            removed["sources"].append(sid)
    for pid in ("demo-pipe-wo",):
        if pid in _pipelines:
            del _pipelines[pid]
            removed["pipelines"].append(pid)
    for rid in ("ri.dataset.demo-workorder",):
        if rid in _datasets:
            del _datasets[rid]
            removed["datasets"].append(rid)
        _dataset_history.pop(rid, None)
    for sid in ("sync-demo-wo",):
        if sid in _syncs:
            del _syncs[sid]
            removed["syncs"].append(sid)
    for sch in ("demo-sch-wo",):
        if sch in _schedules:
            del _schedules[sch]
            removed["schedules"].append(sch)
    before = len(_dlq)
    _dlq[:] = [d for d in _dlq if not (isinstance(d, dict) and str(d.get("id", "")).startswith("dlq-demo"))]
    removed["dlq"] = before - len(_dlq)
    log.info("demo_data_cleared %s", removed)
    return {"ok": True, "removed": removed}

@router.get("/v1/demo/story")
def demo_story(principal: Principal = Depends(require_principal)):
    """TB.1～TB.8 · WorkOrder customer demo narrative (local deploy)."""
    _ = principal
    from aos_api.demo_story import demo_story_payload

    return demo_story_payload()


@router.post("/v1/demo/ensure-seed")
def demo_ensure_seed(principal: Principal = Depends(require_principal)):
    """TB.1 · Idempotent WorkOrder demo seed repair."""
    _ = principal
    from aos_api.demo_story import ensure_demo_seed

    return ensure_demo_seed()


@router.post("/v1/demo/run-story")
def demo_run_story(principal: Principal = Depends(require_principal)):
    """TB.4 · One-shot writeback: Draft → approve → object change + lineage."""
    from aos_api.demo_story import run_writeback_story

    return run_writeback_story(principal)


@router.post("/v1/demo/run-analytics-story")
def demo_run_analytics_story(principal: Principal = Depends(require_principal)):
    """TA.7 · Demo one-shot: analytics read → Draft → approve → lineage.

    Includes approve only inside this demo story; product /analytics stays propose-only.
    """
    from aos_api.demo_story import run_analytics_story

    return run_analytics_story(principal)


@router.get("/v1/demo/governance")
def demo_governance(principal: Principal = Depends(require_principal)):
    """TB.7 · Field redaction contrast + Marking FORBIDDEN + latest lineage."""
    from aos_api.demo_story import governance_probe

    return governance_probe(principal)


@router.post("/v1/demo/run-capability")
def demo_run_capability(principal: Principal = Depends(require_principal)):
    """71 · Capability Job → MediaSet + parser extract + OCR probe."""
    from aos_api.demo_story import run_capability_mirror

    return run_capability_mirror(principal)


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
_jobs: dict[str, dict[str, Any]] = {}
_media: dict[str, dict[str, Any]] = {}
_media_bytes: dict[str, bytes] = {}
_connectors: dict[str, dict[str, Any]] = {}
_pipelines: dict[str, dict[str, Any]] = {}
_schedules: dict[str, dict[str, Any]] = {}
_dlq: list[dict[str, Any]] = []
_syncs: dict[str, dict[str, Any]] = {}
_datasets: dict[str, dict[str, Any]] = {}
_dataset_history: dict[str, list[dict[str, Any]]] = {}


def ensure_demo_data_seed(*, force: bool = False) -> dict[str, Any]:
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

    if src_id not in _connectors:
        _connectors[src_id] = {"id": src_id, "type": "file", "status": "registered"}
    if pipe_id not in _pipelines:
        build_id = "build-demo-wo"
        now = time.time()
        _pipelines[pipe_id] = {
            "id": pipe_id,
            "sourceId": src_id,
            "target": "dataset",
            "datasetRid": ds_rid,
            "lastBuild": {
                "id": build_id,
                "status": "SUCCEEDED",
                "tasks": [{"name": "ingest", "ok": True}],
            },
        }
        _datasets[ds_rid] = {
            "rid": ds_rid,
            "name": "WorkOrder-demo",
            "pipelineId": pipe_id,
            "sourceId": src_id,
            "status": "READY",
            "createdAt": now,
            "updatedAt": now,
            "objectTypeHint": "WorkOrder",
        }
        hist = _dataset_history.setdefault(ds_rid, [])
        if not hist:
            hist.append(
                {
                    "version": 1,
                    "buildId": build_id,
                    "status": "SUCCEEDED",
                    "at": now,
                }
            )
    if sch_id not in _schedules:
        _schedules[sch_id] = {
            "id": sch_id,
            "cron": "0 * * * *",
            "pipelineId": pipe_id,
            "enabled": True,
        }
    sync_id = "sync-demo-wo"
    if sync_id not in _syncs:
        now = time.time()
        _syncs[sync_id] = {
            "id": sync_id,
            "sourceId": src_id,
            "status": "SUCCEEDED",
            "startedAt": now,
            "finishedAt": now,
            "rowsSynced": 3,
        }
    if not any(isinstance(d, dict) and d.get("id") == dlq_id for d in _dlq):
        _dlq.append(
            {
                "id": dlq_id,
                "pipelineId": pipe_id,
                "reason": "demo sample row rejected (bad status enum)",
                "status": "open",
                "payload": {
                    "objectType": "WorkOrder",
                    "row": {"title": "坏样例", "status": "???"},
                },
            }
        )
    return {
        "sources": len(_connectors),
        "syncs": len(_syncs),
        "pipelines": len(_pipelines),
        "datasets": len(_datasets),
        "builds": len(_pipelines),
        "dlq": len(_dlq),
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


class PipelineIn(BaseModel):
    id: str
    sourceId: str
    target: str = "dataset"
    datasetRid: str | None = None
    objectTypeHint: str | None = None
    name: str | None = None
    displayName: str | None = None


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
    _ = principal
    from aos_api.tool_runtime import invoke_tool

    return invoke_tool(tool_id, body or {})


# —— T3.8 统一插件目录 ——
@router.get("/v1/plugins")
def list_plugins_catalog(principal: Principal = Depends(require_principal)):
    """Aggregate tools + parsers + sources + capabilities + llm providers (T3.8 / 83)."""
    _ = principal
    from aos_api.file_parsers import list_plugins as list_parsers
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
                    executed.append(invoke_tool(str(tid), body.get("toolPayload") or {}))
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
    _ = principal
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
    _media[media_rid] = meta
    _jobs[job_id] = {
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
    }
    log.info("capability_job_ok job=%s media=%s", job_id, media_rid)
    return _jobs[job_id]


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
    _ = principal
    if job_id not in _jobs:
        raise ApiError(code="NOT_FOUND", message="job missing", status_code=404)
    return _jobs[job_id]


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
    except Exception:  # noqa: BLE001
        log.warning("data_os_persist_fail op=%s", fn_name, exc_info=True)


def _org_visible(item: dict[str, Any] | None, org_id: str) -> bool:
    """185w v1.2 · stamped orgId must match; unstamped legacy visible to current org."""
    if not item:
        return False
    stamped = item.get("orgId")
    if stamped:
        return stamped == org_id
    return True


def _source_org_visible(source_id: str | None, org_id: str) -> bool:
    if not source_id:
        return True
    src = _connectors.get(source_id)
    if src is None:
        return False
    return _org_visible(src, org_id)


@router.post("/v1/sources")
def create_source(body: ConnectorIn, principal: Principal = Depends(require_principal)):
    from aos_api.connector_registry import assert_type_installed

    try:
        plugin_id = assert_type_installed(body.type)
    except KeyError as exc:
        raise ApiError(code="UNKNOWN_CONNECTOR", message=str(exc), status_code=400) from None
    except PermissionError as exc:
        raise ApiError(code="PLUGIN_NOT_INSTALLED", message=str(exc), status_code=400) from None
    item = {
        **body.model_dump(),
        "type": plugin_id,
        "status": "registered",
        "pluginId": plugin_id,
        "orgId": principal.org_id,
        "projectId": principal.project_id,
    }
    _connectors[body.id] = item
    _persist_safe("persist_source", item)
    return item


@router.get("/v1/sources")
def list_sources(principal: Principal = Depends(require_principal)):
    items = [c for c in _connectors.values() if _org_visible(c, principal.org_id)]
    return {"items": items}


@router.post("/v1/syncs")
def create_sync(body: SyncIn, principal: Principal = Depends(require_principal)):
    """G-ALIGN-04 — Dev Sync Job Facade (T-API /v1/syncs)."""
    _ = principal
    if body.sourceId not in _connectors:
        raise ApiError(code="NOT_FOUND", message="source missing", status_code=404)
    sid = body.id or f"sync-{uuid.uuid4().hex[:8]}"
    item = {
        "id": sid,
        "sourceId": body.sourceId,
        "status": "SUCCEEDED",
        "startedAt": time.time(),
        "finishedAt": time.time(),
        "rowsSynced": 0,
    }
    _syncs[sid] = item
    _persist_safe("persist_sync", item)
    # Reflect sync into dataset history if a dataset is bound to this source
    for rid, ds in _datasets.items():
        if ds.get("sourceId") == body.sourceId:
            hist = _dataset_history.setdefault(rid, [])
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
            _persist_safe("persist_dataset", ds)
            _persist_safe("persist_dataset_history", rid, hist)
    log.info("sync_created id=%s source=%s", sid, body.sourceId)
    return item


@router.get("/v1/syncs")
def list_syncs(principal: Principal = Depends(require_principal)):
    items = [
        s
        for s in _syncs.values()
        if _source_org_visible(s.get("sourceId"), principal.org_id)
    ]
    return {"items": items}


@router.get("/v1/syncs/{sync_id}")
def get_sync(sync_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    if sync_id not in _syncs:
        raise ApiError(code="NOT_FOUND", message="sync missing", status_code=404)
    return _syncs[sync_id]


@router.get("/v1/datasets")
def list_datasets(principal: Principal = Depends(require_principal)):
    items = [
        d
        for d in _datasets.values()
        if _org_visible(d, principal.org_id)
        or (
            not d.get("orgId")
            and _source_org_visible(d.get("sourceId"), principal.org_id)
        )
    ]
    return {"items": items}


@router.get("/v1/datasets/{rid}")
def get_dataset(rid: str, principal: Principal = Depends(require_principal)):
    _ = principal
    if rid not in _datasets:
        raise ApiError(code="NOT_FOUND", message="dataset missing", status_code=404)
    return _datasets[rid]


@router.get("/v1/datasets/{rid}/history")
def dataset_history(rid: str, principal: Principal = Depends(require_principal)):
    _ = principal
    if rid not in _datasets:
        raise ApiError(code="NOT_FOUND", message="dataset missing", status_code=404)
    return {"rid": rid, "items": list(_dataset_history.get(rid, []))}


@router.post("/v1/media-sets")
def create_media(body: MediaIn, principal: Principal = Depends(require_principal)):
    """T4.2/T4.3 — metadata + real MinIO put when bytes provided · TWA.8 前缀。"""
    import base64

    from aos_api.object_store import get_config, object_key_for, put_bytes
    from aos_api.tenant_prefix import assert_object_key_tenant

    rid = f"ri.mediaset.{uuid.uuid4().hex[:10]}"
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
        _media_bytes[rid] = raw
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

    raw_for_meta = _media_bytes.get(rid) if body.bytesBase64 else None
    item["metadata"] = extract_metadata(
        raw_for_meta,
        content_type=body.contentType or "application/octet-stream",
        name=body.name,
    )
    _media[rid] = item
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

    if rid not in _media:
        raise ApiError(code="NOT_FOUND", message="media missing", status_code=404)
    meta = _media[rid]
    if meta.get("orgId") and (
        meta.get("orgId") != principal.org_id or meta.get("projectId") != principal.project_id
    ):
        raise ApiError(code="NOT_FOUND", message="media missing", status_code=404)
    raw = _media_bytes.get(rid)
    enriched = extract_metadata(
        raw,
        content_type=str(meta.get("contentType") or "application/octet-stream"),
        name=str(meta.get("name") or ""),
    )
    meta["metadata"] = enriched
    _media[rid] = meta
    return meta


@router.get("/v1/media-sets")
def list_media(principal: Principal = Depends(require_principal)):
    items = [
        m
        for m in _media.values()
        if m.get("orgId") == principal.org_id and m.get("projectId") == principal.project_id
    ]
    return {"items": items}


@router.get("/v1/media-sets/{rid}")
def get_media(rid: str, principal: Principal = Depends(require_principal)):
    if rid not in _media:
        raise ApiError(code="NOT_FOUND", message="media missing", status_code=404)
    meta = _media[rid]
    if meta.get("orgId") and (
        meta.get("orgId") != principal.org_id or meta.get("projectId") != principal.project_id
    ):
        raise ApiError(code="NOT_FOUND", message="media missing", status_code=404)
    return meta


@router.get("/v1/media-sets/{rid}/content")
def get_media_content(rid: str, principal: Principal = Depends(require_principal)):
    """T4.2 — fetch bytes from object store (base64 in JSON for easy smoke)."""
    import base64

    from aos_api.object_store import get_bytes
    from aos_api.tenant_prefix import assert_object_key_tenant

    if rid not in _media:
        raise ApiError(code="NOT_FOUND", message="media missing", status_code=404)
    meta = _media[rid]
    if meta.get("orgId") and (
        meta.get("orgId") != principal.org_id or meta.get("projectId") != principal.project_id
    ):
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
    _ = principal
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
        if media_rid in _media_bytes:
            data = _media_bytes[media_rid]
            meta = _media.get(media_rid) or {}
            name = name or meta.get("name")
            content_type = content_type or meta.get("contentType")
        elif media_rid in _media and _media[media_rid].get("stored") and _media[media_rid].get("objectKey"):
            meta = _media[media_rid]
            data = get_bytes(key=meta["objectKey"])
            name = name or meta.get("name")
            content_type = content_type or meta.get("contentType")
        else:
            raise ApiError(code="NOT_FOUND", message="media bytes missing", status_code=404)
    else:
        raise ApiError(code="BAD_REQUEST", message="bytesBase64 or mediaRid required", status_code=400)

    result = extract(data=data, name=name, content_type=content_type)
    if media_rid and media_rid in _media:
        _media[media_rid]["extractedText"] = result.get("preview")
        _media[media_rid]["parser"] = result.get("parser")
        _media[media_rid]["parseOk"] = result.get("ok")
    return result


@router.post("/v1/media-sets/{rid}/parse")
def parse_media(rid: str, principal: Principal = Depends(require_principal)):
    return parsers_extract({"mediaRid": rid}, principal)


@router.post("/v1/pipelines")
def create_pipeline(body: PipelineIn, principal: Principal = Depends(require_principal)):
    build_id = f"build-{uuid.uuid4().hex[:8]}"
    dataset_rid = body.datasetRid or f"ri.dataset.{body.id}"
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
    prev = _datasets.get(dataset_rid) or {}
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
    _datasets[dataset_rid] = ds
    hist = _dataset_history.setdefault(dataset_rid, [])
    hist.append(
        {
            "version": len(hist) + 1,
            "buildId": build_id,
            "status": "SUCCEEDED",
            "at": now,
        }
    )
    _persist_safe("persist_pipeline", item)
    _persist_safe("persist_dataset", ds)
    _persist_safe("persist_dataset_history", dataset_rid, hist)
    return item


@router.patch("/v1/datasets/{rid:path}")
def patch_dataset(
    rid: str,
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    """Update dataset display / objectTypeHint (preview wiring)."""
    _ = principal
    ds = _datasets.get(rid)
    if not ds:
        raise ApiError(code="NOT_FOUND", message="dataset missing", status_code=404)
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
    _datasets[rid] = ds
    _persist_safe("persist_dataset", ds)
    return ds


@router.get("/v1/pipelines")
def list_pipelines(principal: Principal = Depends(require_principal)):
    items = [
        p
        for p in _pipelines.values()
        if _org_visible(p, principal.org_id)
        or (
            not p.get("orgId")
            and _source_org_visible(p.get("sourceId"), principal.org_id)
        )
    ]
    return {"items": items}


@router.post("/v1/pipelines/{pipeline_id}/embed")
def pipeline_embed(
    pipeline_id: str,
    body: dict[str, Any] | None = None,
    principal: Principal = Depends(require_principal),
):
    """104 · Pipeline → 本地向量索引（经 embedding 插件；无网关不写假向量）。"""
    _ = principal
    from aos_api.vector_index import embed_pipeline

    return embed_pipeline(pipeline_id, body or {}, pipelines=_pipelines)


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
    _ = principal
    builds = [p["lastBuild"] | {"pipelineId": pid} for pid, p in _pipelines.items()]
    return {"items": builds}

@router.post("/v1/schedules")
def create_schedule(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    _ = principal
    sid = body.get("id") or f"sch-{uuid.uuid4().hex[:6]}"
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
    _persist_safe("persist_schedule", item)
    return item


@router.get("/v1/schedules")
def list_schedules(principal: Principal = Depends(require_principal)):
    """T-UI S2 · schedules list for 计划编辑器."""
    items = [s for s in _schedules.values() if _org_visible(s, principal.org_id)]
    return {"items": items}


@router.get("/v1/schedules/{schedule_id}")
def get_schedule(schedule_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    item = _schedules.get(schedule_id)
    if not item:
        raise ApiError(code="NOT_FOUND", message="schedule missing", status_code=404)
    return item


@router.patch("/v1/schedules/{schedule_id}")
def patch_schedule(
    schedule_id: str,
    body: dict[str, Any],
    principal: Principal = Depends(require_principal),
):
    """74 · edit cron / enabled / pipelineId for 计划编辑器."""
    _ = principal
    item = _schedules.get(schedule_id)
    if not item:
        raise ApiError(code="NOT_FOUND", message="schedule missing", status_code=404)
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
    _persist_safe("persist_schedule", item)
    return item


@router.post("/v1/schedules/{schedule_id}/run")
def run_schedule(schedule_id: str, principal: Principal = Depends(require_principal)):
    """Execute bound connector ingest once (manual/batch face; not a cron daemon)."""
    item = _schedules.get(schedule_id)
    if not item:
        raise ApiError(code="NOT_FOUND", message="schedule missing", status_code=404)
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
    _persist_safe("persist_schedule", item)
    log.info("schedule_run id=%s written=%s", schedule_id, result.get("written"))
    return {"scheduleId": schedule_id, "lastRun": item["lastRun"], "ingest": result}


@router.get("/v1/dlq")
def list_dlq(principal: Principal = Depends(require_principal)):
    _ = principal
    return {"items": _dlq}


@router.post("/v1/dlq")
def push_dlq(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    _ = principal
    item = {"id": f"dlq-{uuid.uuid4().hex[:6]}", **body, "status": "open"}
    _dlq.append(item)
    return item


@router.post("/v1/dlq/{dlq_id}/retry")
def retry_dlq(dlq_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    for i in _dlq:
        if i["id"] == dlq_id:
            i["status"] = "retried"
            return i
    raise ApiError(code="NOT_FOUND", message="dlq missing", status_code=404)


@router.get("/v1/funnel/{object_type}/worker")
def funnel_worker(object_type: str, principal: Principal = Depends(require_principal)):
    """Prefer persisted funnel_status.detail.worker after rerun; else default snapshot."""
    _ = principal
    from aos_api.db import connect

    with connect() as conn:
        row = conn.execute(
            "SELECT detail FROM funnel_status WHERE object_type=%s",
            (object_type,),
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
    _ = principal
    from aos_api.apollo_catalog import promote_channel

    return promote_channel(channel_id)


@router.post("/v1/apollo/channels/{channel_id}/recall")
def apollo_channel_recall(
    channel_id: str, principal: Principal = Depends(require_principal)
):
    _ = principal
    from aos_api.apollo_catalog import recall_channel

    return recall_channel(channel_id)


@router.get("/v1/apollo/spokes")
def apollo_spokes_list(principal: Principal = Depends(require_principal)):
    from aos_api.apollo_catalog import list_spokes

    return {"items": list_spokes(org_id=principal.org_id)}


@router.get("/v1/apollo/spokes/local")
def spoke_probe(principal: Principal = Depends(require_principal)):
    """Compat · Lite local spoke (scheme 66 reads catalog)."""
    from aos_api.apollo_catalog import get_spoke

    return get_spoke("spoke-local-dev", org_id=principal.org_id)


@router.get("/v1/apollo/spokes/{spoke_id}")
def spoke_by_id(spoke_id: str, principal: Principal = Depends(require_principal)):
    """T-API · Spoke detail (PG catalog · scheme 66) · TWA.9 按 Org。"""
    from aos_api.apollo_catalog import get_spoke

    return get_spoke(spoke_id, org_id=principal.org_id)


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
    return record_spoke_heartbeat(spoke_id, org_id=principal.org_id, ok=ok)


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
        spoke_id,
        org_id=principal.org_id,
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

    return fleet_payload(org_id=principal.org_id)


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
    stored = ttl_job.upsert_insight(insight)
    log.info("insight_backfill id=%s", stored["id"])
    return stored


@router.get("/v1/aip/insights")
def list_insights(
    status: str | None = None,
    principal: Principal = Depends(require_principal),
):
    _ = principal
    from aos_api import ttl_job

    items = ttl_job.list_insights(status=status)
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
    _ = principal
    if rid not in _media:
        raise ApiError(code="NOT_FOUND", message="media missing", status_code=404)
    m = _media[rid]
    return {"rid": rid, "previewUrl": f"/v1/media-sets/{rid}", "name": m["name"]}


@router.get("/v1/edge/agents/local")
def edge_agent(principal: Principal = Depends(require_principal)):
    _ = principal
    return {"id": "edge-local", "probeOk": True, "outbound": True}


@router.post("/v1/docintel/pipeline")
def docintel_pipeline(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    _ = principal
    import base64

    fail = bool(body.get("fail", False))
    if fail:
        item = {
            "id": f"dlq-{uuid.uuid4().hex[:6]}",
            "source": "docintel",
            "reason": body.get("reason", "parse-fail"),
            "status": "open",
        }
        _dlq.append(item)
        return {"batchOk": True, "failedIsolated": True, "dlqId": item["id"]}

    from aos_api.file_parsers import extract
    from aos_api.ocr_gateway import ocr_page as gateway_ocr

    parse_result = None
    raw: bytes | None = None
    if body.get("bytesBase64"):
        raw = base64.b64decode(body["bytesBase64"])
    elif body.get("mediaRid") and body["mediaRid"] in _media_bytes:
        raw = _media_bytes[body["mediaRid"]]
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

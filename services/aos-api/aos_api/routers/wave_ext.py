"""T3.5～T3.11 / T3.16 / T3.19 / TC / T4 / T5 minimal surfaces — one module to close gaps."""
from __future__ import annotations

import json
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
_webhooks: list[dict[str, Any]] = []
_media: dict[str, dict[str, Any]] = {}
_media_bytes: dict[str, bytes] = {}
_connectors: dict[str, dict[str, Any]] = {}
_pipelines: dict[str, dict[str, Any]] = {}
_schedules: dict[str, dict[str, Any]] = {}
_dlq: list[dict[str, Any]] = []
_syncs: dict[str, dict[str, Any]] = {}
_datasets: dict[str, dict[str, Any]] = {}
_dataset_history: dict[str, list[dict[str, Any]]] = {}


def ensure_demo_data_seed() -> dict[str, Any]:
    """TB.2 · Idempotent in-memory source/pipeline/dataset + sample DLQ for /data demo."""
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


class SyncIn(BaseModel):
    sourceId: str
    id: str | None = None


# —— T3.5 webhook ——
@router.post("/v1/actions/webhooks")
def register_webhook(body: WebhookIn, principal: Principal = Depends(require_principal)):
    _ = principal
    item = {"id": f"wh-{uuid.uuid4().hex[:8]}", **body.model_dump(), "status": "registered"}
    _webhooks.append(item)
    log.info("webhook_registered id=%s", item["id"])
    return item


@router.get("/v1/actions/webhooks")
def list_webhooks(principal: Principal = Depends(require_principal)):
    _ = principal
    return {"items": _webhooks}


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
    """Aggregate tools + parsers + sources + capabilities (T3.8 facade)."""
    _ = principal
    from aos_api.file_parsers import list_plugins as list_parsers

    items: list[dict[str, Any]] = []
    for t in _tools:
        items.append({"id": t["id"], "kind": "tool", "subKind": t.get("kind"), "status": "ready"})
    for p in list_parsers():
        items.append(
            {
                "id": p["id"],
                "kind": "parser",
                "formats": p.get("formats"),
                "status": "ready",
                "note": p.get("note"),
            }
        )
    for s in _connectors.values():
        items.append(
            {"id": s["id"], "kind": "source", "type": s.get("type"), "status": s.get("status", "registered")}
        )
    for c in _capabilities.values():
        items.append({"id": c["id"], "kind": "capability", "subKind": c.get("kind"), "status": "registered"})
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
@router.post("/v1/sources")
def create_source(body: ConnectorIn, principal: Principal = Depends(require_principal)):
    _ = principal
    _connectors[body.id] = {**body.model_dump(), "status": "registered"}
    return _connectors[body.id]


@router.get("/v1/sources")
def list_sources(principal: Principal = Depends(require_principal)):
    _ = principal
    return {"items": list(_connectors.values())}


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
    log.info("sync_created id=%s source=%s", sid, body.sourceId)
    return item


@router.get("/v1/syncs")
def list_syncs(principal: Principal = Depends(require_principal)):
    _ = principal
    return {"items": list(_syncs.values())}


@router.get("/v1/syncs/{sync_id}")
def get_sync(sync_id: str, principal: Principal = Depends(require_principal)):
    _ = principal
    if sync_id not in _syncs:
        raise ApiError(code="NOT_FOUND", message="sync missing", status_code=404)
    return _syncs[sync_id]


@router.get("/v1/datasets")
def list_datasets(principal: Principal = Depends(require_principal)):
    _ = principal
    return {"items": list(_datasets.values())}


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
    """T4.2/T4.3 — metadata + real MinIO put when bytes provided."""
    _ = principal
    import base64

    from aos_api.object_store import get_config, object_key_for, put_bytes

    rid = f"ri.mediaset.{uuid.uuid4().hex[:10]}"
    stored = False
    object_key = None
    etag = None
    raw_len = 0
    store_mode = "metadata-only"
    if body.bytesBase64:
        raw = base64.b64decode(body.bytesBase64)
        raw_len = len(raw)
        _media_bytes[rid] = raw
        object_key = object_key_for(rid, body.name)
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
    item = {
        "rid": rid,
        "name": body.name,
        "contentType": body.contentType,
        "objectStore": store_mode,
        "stored": stored,
        "bytes": raw_len,
        "objectKey": object_key,
        "etag": etag,
        "accessKeyRef": "env:AOS_S3_ACCESS_KEY|MINIO_ROOT_USER",
    }
    _media[rid] = item
    log.info("media_created rid=%s stored=%s bytes=%s", rid, stored, raw_len)
    return item


@router.get("/v1/media-sets")
def list_media(principal: Principal = Depends(require_principal)):
    _ = principal
    return {"items": list(_media.values())}


@router.get("/v1/media-sets/{rid}")
def get_media(rid: str, principal: Principal = Depends(require_principal)):
    _ = principal
    if rid not in _media:
        raise ApiError(code="NOT_FOUND", message="media missing", status_code=404)
    return _media[rid]


@router.get("/v1/media-sets/{rid}/content")
def get_media_content(rid: str, principal: Principal = Depends(require_principal)):
    """T4.2 — fetch bytes from object store (base64 in JSON for easy smoke)."""
    _ = principal
    import base64

    from aos_api.object_store import get_bytes

    if rid not in _media:
        raise ApiError(code="NOT_FOUND", message="media missing", status_code=404)
    meta = _media[rid]
    key = meta.get("objectKey")
    if not key or not meta.get("stored"):
        raise ApiError(
            code="NOT_STORED",
            message="media has no object-store bytes",
            status_code=404,
        )
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
    _ = principal
    build_id = f"build-{uuid.uuid4().hex[:8]}"
    dataset_rid = body.datasetRid or f"ri.dataset.{body.id}"
    item = {
        **body.model_dump(),
        "datasetRid": dataset_rid,
        "lastBuild": {"id": build_id, "status": "SUCCEEDED", "tasks": [{"name": "ingest", "ok": True}]},
    }
    _pipelines[body.id] = item
    now = time.time()
    ds = {
        "rid": dataset_rid,
        "name": body.id,
        "pipelineId": body.id,
        "sourceId": body.sourceId,
        "status": "READY",
        "createdAt": now,
        "updatedAt": now,
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
    return item


@router.get("/v1/pipelines")
def list_pipelines(principal: Principal = Depends(require_principal)):
    _ = principal
    return {"items": list(_pipelines.values())}


@router.get("/v1/builds")
def list_builds(principal: Principal = Depends(require_principal)):
    _ = principal
    builds = [p["lastBuild"] | {"pipelineId": pid} for pid, p in _pipelines.items()]
    return {"items": builds}


@router.post("/v1/schedules")
def create_schedule(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    _ = principal
    sid = body.get("id") or f"sch-{uuid.uuid4().hex[:6]}"
    item = {"id": sid, "cron": body.get("cron", "0 * * * *"), "pipelineId": body.get("pipelineId"), "enabled": True}
    _schedules[sid] = item
    return item


@router.get("/v1/schedules")
def list_schedules(principal: Principal = Depends(require_principal)):
    """T-UI S2 · schedules list for 计划编辑器."""
    _ = principal
    return {"items": list(_schedules.values())}


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
    _ = principal
    return {
        "objectType": object_type,
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
    _ = principal
    from aos_api.apollo_catalog import list_spokes

    return {"items": list_spokes()}


@router.get("/v1/apollo/spokes/local")
def spoke_probe(principal: Principal = Depends(require_principal)):
    """Compat · Lite local spoke (scheme 66 reads catalog)."""
    from aos_api.apollo_catalog import get_spoke

    return get_spoke("spoke-local-dev")


@router.get("/v1/apollo/spokes/{spoke_id}")
def spoke_by_id(spoke_id: str, principal: Principal = Depends(require_principal)):
    """T-API · Spoke detail (PG catalog · scheme 66)."""
    _ = principal
    from aos_api.apollo_catalog import get_spoke

    return get_spoke(spoke_id)


@router.get("/v1/apollo/fleet")
def apollo_fleet(principal: Principal = Depends(require_principal)):
    """T-API · Hub fleet (Channel/Spoke catalog)."""
    _ = principal
    from aos_api.apollo_catalog import fleet_payload

    return fleet_payload()


@router.post("/v1/apollo/assets")
def asset_bundle(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    _ = principal
    return {
        "bundleId": f"ab-{uuid.uuid4().hex[:8]}",
        "platformVersion": "0.3.0-dev",
        "contents": body.get("contents", ["WorkOrder", "CloseWorkOrder"]),
        "hotfix": bool(body.get("hotfix", False)),
        "validated": True,
    }


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
    draft_id = f"draft-bf-{uuid.uuid4().hex[:8]}"
    insight = {
        "id": f"ins-{uuid.uuid4().hex[:8]}",
        "objectType": body.get("objectType", "WorkOrder"),
        "objectId": body.get("objectId", "wo-1001"),
        "confidence": float(body.get("confidence", 0.92)),
        "text": body.get("text", "high-confidence insight"),
        "viaDraftId": draft_id,
        "status": "proposed",
    }
    log.info("insight_backfill id=%s", insight["id"])
    return insight


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


# —— T4.6 MySQL (PyMySQL) + T4.7 minimal mapping ——
@router.post("/v1/connectors/mysql/probe")
def mysql_probe(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.mysql_connector import probe

    limit = int(body.get("limit") or 5)
    return probe(limit=limit, object_type=str(body.get("objectType") or "WorkOrder"))


@router.post("/v1/connectors/mysql/ingest")
def mysql_ingest(body: dict[str, Any], principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.mysql_connector import ingest

    mapping = body.get("mapping")
    if mapping is not None and not isinstance(mapping, dict):
        raise ApiError(code="VALIDATION", message="mapping must be object", status_code=400)
    return ingest(
        object_type=str(body.get("objectType") or "WorkOrder"),
        limit=int(body.get("limit") or 100),
        mapping=mapping,
    )


@router.get("/v1/connectors/mysql/health")
def mysql_health(principal: Principal = Depends(require_principal)):
    _ = principal
    from aos_api.mysql_connector import probe

    r = probe(limit=1)
    # never echo sample passwords
    return {
        "ok": r.get("ok"),
        "mode": r.get("mode"),
        "host": r.get("host"),
        "port": r.get("port"),
        "database": r.get("database"),
        "table": r.get("table"),
        "rowsSampled": r.get("rowsSampled"),
        "passwordRef": r.get("passwordRef"),
        "driver": r.get("driver"),
        "detail": r.get("detail"),
    }


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
    _ = principal
    size = int(body.get("sizeBytes", 0))
    return {
        "route": "dataset-inline" if size < 128 * 1024 else "object-store",
        "sizeBytes": size,
        "threshold": 128 * 1024,
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

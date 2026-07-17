"""TB.1～TB.8 · Customer demo story surface (WorkOrder narrative)."""
from __future__ import annotations

import json
import uuid
from typing import Any

from aos_api.auth import Principal
from aos_api.db import connect, repair_demo_workorders, seed_if_empty
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo_story")

STORY_ID = "workorder-local-demo"
STORY_TITLE = "工单运营演示（本地可部署）"


def ensure_demo_seed(*, repair: bool = True) -> dict[str, Any]:
    """Idempotent: schema seed + optional WorkOrder repair for customer demo."""
    seed_if_empty()
    from aos_api.routers.actions import ensure_action_schema
    from aos_api.routers.drafts import ensure_draft_schema
    from aos_api.routers.wave_ext import ensure_demo_data_seed

    ensure_action_schema()
    ensure_draft_schema()
    data_surface = ensure_demo_data_seed()
    if repair:
        repair_demo_workorders()
    else:
        # Ensure demo rows exist without clobbering status (TB.4 writeback toggle)
        with connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM obj_instance WHERE object_type=%s AND object_id=%s",
                ("WorkOrder", "wo-1001"),
            ).fetchone()
            if not row:
                repair_demo_workorders(conn)
                conn.commit()
    snap = story_snapshot()
    snap["dataSurface"] = data_surface
    log.info(
        "demo_seed_ensured objects=%s type=%s repair=%s datasets=%s dlq=%s",
        snap.get("objectCount"),
        snap.get("objectType"),
        repair,
        data_surface.get("datasets"),
        data_surface.get("dlq"),
    )
    return {"ok": True, "storyId": STORY_ID, "snapshot": snap}


def story_snapshot() -> dict[str, Any]:
    seed_if_empty()
    with connect() as conn:
        ot = conn.execute(
            "SELECT id, name, published FROM meta_object_type WHERE id=%s",
            ("WorkOrder",),
        ).fetchone()
        objs = conn.execute(
            """
            SELECT object_id, props
            FROM obj_instance
            WHERE object_type=%s
            ORDER BY object_id
            LIMIT 20
            """,
            ("WorkOrder",),
        ).fetchall()
        try:
            drafts = conn.execute(
                """
                SELECT COUNT(*) AS c FROM draft_dataset
                WHERE status = 'proposed'
                """
            ).fetchone()
        except Exception:
            drafts = {"c": 0}
        try:
            modules = conn.execute("SELECT COUNT(*) AS c FROM meta_module").fetchone()
        except Exception:
            modules = {"c": 0}
    items = []
    for r in objs:
        props = r["props"] if isinstance(r["props"], dict) else {}
        items.append(
            {
                "id": r["object_id"],
                "title": props.get("title"),
                "status": props.get("status"),
                "site": props.get("site"),
                "priority": props.get("priority"),
            }
        )
    return {
        "objectType": "WorkOrder",
        "objectTypePublished": bool(ot["published"]) if ot else False,
        "objectCount": len(items),
        "objects": items,
        "pendingDrafts": int(drafts["c"]) if drafts else 0,
        "modules": int(modules["c"]) if modules else 0,
    }


def run_writeback_story(principal: Principal) -> dict[str, Any]:
    """TB.4 · One-shot: Draft → approve → object props change + lineage."""
    from aos_api.routers.actions import ensure_action_schema
    from aos_api.routers.drafts import ensure_draft_schema
    from aos_api.routers.runtime_write import apply_draft_approval

    ensure_demo_seed(repair=False)
    ensure_action_schema()
    ensure_draft_schema()

    object_type = "WorkOrder"
    object_id = "wo-1001"
    with connect() as conn:
        row = conn.execute(
            "SELECT props FROM obj_instance WHERE object_type=%s AND object_id=%s",
            (object_type, object_id),
        ).fetchone()
    before = dict(row["props"]) if row and isinstance(row["props"], dict) else {}
    cur_status = str(before.get("status") or "open")
    next_status = "closed" if cur_status != "closed" else "open"
    proposed = {
        "reason": f"demo-story-{next_status}",
        "status": next_status,
    }

    draft_id = f"demo-{uuid.uuid4().hex[:10]}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO draft_dataset (
              id, action_type_id, object_type, object_id, title, proposed,
              status, created_by, org_id, project_id
            )
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,'proposed',%s,%s,%s)
            """,
            (
                draft_id,
                "CloseWorkOrder",
                object_type,
                object_id,
                f"演示写回 → {next_status}",
                json.dumps(proposed),
                principal.subject,
                principal.org_id,
                principal.project_id,
            ),
        )
        conn.commit()

    approved = apply_draft_approval(
        draft_id=draft_id,
        principal=principal,
        allow_conflicts=True,
    )
    with connect() as conn:
        row2 = conn.execute(
            "SELECT props FROM obj_instance WHERE object_type=%s AND object_id=%s",
            (object_type, object_id),
        ).fetchone()
    after = dict(row2["props"]) if row2 and isinstance(row2["props"], dict) else {}
    return {
        "ok": True,
        "storyId": STORY_ID,
        "objectType": object_type,
        "objectId": object_id,
        "draftId": draft_id,
        "before": {"status": before.get("status")},
        "after": {"status": after.get("status")},
        "proposed": proposed,
        "lineageId": approved.get("lineageId"),
        "productionWritten": True,
        "uiPaths": {
            "inbox": "/workshop/inbox",
            "drafts": "/aip/drafts",
            "lineage": "/aip/lineage",
            "demo": "/demo",
        },
    }


def governance_probe(principal: Principal) -> dict[str, Any]:
    """TB.7 · Marking redaction contrast + latest lineage for demo narrative."""
    from aos_api.errors import ApiError
    from aos_api.marking import apply_field_redaction, ensure_markings

    ensure_demo_seed(repair=False)
    object_type = "WorkOrder"
    object_id = "wo-1001"
    with connect() as conn:
        ot = conn.execute(
            "SELECT properties FROM meta_object_type WHERE id=%s",
            (object_type,),
        ).fetchone()
        row = conn.execute(
            "SELECT props FROM obj_instance WHERE object_type=%s AND object_id=%s",
            (object_type, object_id),
        ).fetchone()
        try:
            lin = conn.execute(
                """
                SELECT id, draft_id, action_type_id, object_type, object_id, steps
                FROM decision_lineage
                WHERE object_type=%s AND object_id=%s
                ORDER BY id DESC
                LIMIT 1
                """,
                (object_type, object_id),
            ).fetchone()
        except Exception:
            lin = None
        prop_defs = ot["properties"] if ot else []
        if isinstance(prop_defs, str):
            prop_defs = json.loads(prop_defs)
        raw = dict(row["props"]) if row and isinstance(row["props"], dict) else {}
        as_caller = apply_field_redaction(principal, dict(raw), prop_defs, conn=conn)
        public_only = Principal(
            subject="demo:public-viewer",
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=["viewer"],
            markings=["public"],
            token_kind="demo-probe",
        )
        as_public = apply_field_redaction(public_only, dict(raw), prop_defs, conn=conn)

    forbidden: dict[str, Any] = {"ok": False}
    try:
        ensure_markings(public_only, ["secret"])
        forbidden = {"ok": True, "note": "unexpected allow"}
    except ApiError as exc:
        forbidden = {
            "ok": False,
            "code": exc.code,
            "message": exc.message,
            "statusCode": exc.status_code,
            "details": exc.details,
        }

    lineage = None
    if lin:
        steps = lin["steps"]
        if isinstance(steps, str):
            steps = json.loads(steps)
        lineage = {
            "id": lin["id"],
            "draftId": lin["draft_id"],
            "actionTypeId": lin["action_type_id"],
            "objectType": lin["object_type"],
            "objectId": lin["object_id"],
            "steps": steps,
        }

    return {
        "ok": True,
        "storyId": STORY_ID,
        "objectType": object_type,
        "objectId": object_id,
        "field": "internalCost",
        "requiredMarkings": ["secret"],
        "rawHasInternalCost": "internalCost" in raw,
        "asCaller": {
            "markings": list(principal.markings or []),
            "roles": list(principal.roles or []),
            "internalCost": as_caller.get("internalCost"),
            "redactedFields": as_caller.get("_redactedFields") or [],
        },
        "asPublicViewer": {
            "markings": ["public"],
            "roles": ["viewer"],
            "internalCost": as_public.get("internalCost"),
            "redactedFields": as_public.get("_redactedFields") or [],
        },
        "markingForbidden": forbidden,
        "latestLineage": lineage,
        "uiPaths": {"lineage": "/aip/lineage", "demo": "/demo", "data": "/data"},
        "say": "无 secret 标记时 internalCost 脱敏；Marking 不足返回 FORBIDDEN；写回后可查谱系",
    }


def run_capability_mirror(principal: Principal) -> dict[str, Any]:
    """71 · Capability Job → MediaSet + CSV parser extract + OCR sidecar probe."""
    import base64

    from aos_api.ocr_gateway import probe_sidecar
    from aos_api.routers.wave_ext import (
        JobSubmitIn,
        _capabilities,
        _media,
        _media_bytes,
        parsers_extract,
        submit_job,
    )

    _ = principal
    ensure_demo_seed(repair=False)
    cap_id = "demo-wo-cap"
    if cap_id not in _capabilities:
        _capabilities[cap_id] = {
            "id": cap_id,
            "kind": "job",
            "endpoint": "mock://local",
        }
    job = submit_job(
        cap_id,
        JobSubmitIn(
            capabilityId=cap_id,
            input={"objectType": "WorkOrder", "objectId": "wo-1001", "clip": "demo"},
        ),
        principal,
    )
    media_rid = (job.get("artifact") or {}).get("mediaRid") or (job.get("artifact") or {}).get(
        "rid"
    )

    csv_text = "title,status\n机房巡检-A区,open\n"
    csv_b64 = base64.b64encode(csv_text.encode("utf-8")).decode("ascii")
    parse_media_rid = f"ri.mediaset.demo-parse-{uuid.uuid4().hex[:8]}"
    _media[parse_media_rid] = {
        "rid": parse_media_rid,
        "name": "demo-workorder.csv",
        "contentType": "text/csv",
        "objectStore": "memory",
        "stored": True,
        "bytes": len(csv_text.encode("utf-8")),
        "fromDemo": True,
    }
    _media_bytes[parse_media_rid] = csv_text.encode("utf-8")
    extracted = parsers_extract(
        {
            "mediaRid": parse_media_rid,
            "name": "demo-workorder.csv",
            "contentType": "text/csv",
            "bytesBase64": csv_b64,
        },
        principal,
    )
    ocr = probe_sidecar()

    return {
        "ok": True,
        "storyId": STORY_ID,
        "capabilityId": cap_id,
        "job": {
            "jobId": job.get("jobId"),
            "status": job.get("status"),
            "mediaRid": media_rid,
        },
        "parser": {
            "mediaRid": parse_media_rid,
            "ok": bool(extracted.get("ok")),
            "parser": extracted.get("parser"),
            "preview": (extracted.get("preview") or "")[:240],
        },
        "ocrProbe": ocr,
        "uiPaths": {
            "capabilities": "/aip/capabilities",
            "mediaSets": "/data/media-sets",
            "demo": "/demo",
        },
        "say": "Capability Job 产物挂 MediaSet；CSV 解析可指；OCR 边车有则绿、无则诚实 unset/mock",
    }


def demo_story_payload() -> dict[str, Any]:
    snap = story_snapshot()
    steps = [
        {
            "id": "TB.0",
            "title": "本地启动",
            "uiPath": "/",
            "api": "GET /v1/health",
            "say": "本机 Docker + API + Web，10 分钟可亮",
        },
        {
            "id": "TB.1",
            "title": "行业种子",
            "uiPath": "/ontology",
            "api": "GET /v1/demo/story",
            "say": f"Object Type WorkOrder · {snap['objectCount']} 条样例对象",
        },
        {
            "id": "TB.2",
            "title": "数据进故事",
            "uiPath": "/data",
            "api": "GET /v1/datasets · GET /v1/builds · GET /v1/dlq",
            "say": "确保种子后 Dataset/Build/DLQ 可指屏；文件→Pipeline→对象",
        },
        {
            "id": "TB.3",
            "title": "本体运营",
            "uiPath": "/ontology/funnel",
            "api": "GET /v1/funnel/WorkOrder/status · 对象详情/邻接",
            "say": "Funnel 状态深页 + Ontology hub 实例/邻居可点",
        },
        {
            "id": "TB.4",
            "title": "写回闭环",
            "uiPath": "/aip/drafts",
            "api": "POST /v1/demo/run-story",
            "say": "一键 Draft→批准→对象 status 变→谱系",
        },
        {
            "id": "TB.5",
            "title": "Workshop 画布",
            "uiPath": "/workshop/canvas",
            "api": "POST /v1/object-sets/query",
            "say": "Object Table + Filter 预览运行态",
        },
        {
            "id": "TB.6",
            "title": "AIP / Buddy",
            "uiPath": "/workshop/buddy",
            "api": "POST /v1/buddy/ask · context.objectType",
            "say": "问答绑定工单上下文",
        },
        {
            "id": "TB.7",
            "title": "治理可见",
            "uiPath": "/demo",
            "api": "GET /v1/demo/governance",
            "say": "internalCost 脱敏对比 + Marking FORBIDDEN + 最近谱系",
        },
        {
            "id": "TB.8",
            "title": "彩排脚本",
            "uiPath": "/demo",
            "api": "scripts/demo/CUSTOMER-DEMO.md",
            "say": "15～20 分钟客户演示；Apollo 运维不讲",
        },
        {
            "id": "TB.9",
            "title": "Capability / OCR 一镜（可选）",
            "uiPath": "/aip/capabilities",
            "api": "POST /v1/demo/run-capability",
            "say": "Job→MediaSet + CSV 解析 + OCR probe（不宣称生产 GPU）",
        },
    ]
    return {
        "storyId": STORY_ID,
        "title": STORY_TITLE,
        "deferred": {
            "apolloOps": True,
            "analyticsNotebook": True,
            "note": "Apollo 运维加深与产品 1.3 Jupyter/R/SQL 后置",
        },
        "snapshot": snap,
        "steps": steps,
    }

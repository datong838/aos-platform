"""d2_6_qiyuehui_integration_case.py — D2.6 子任务 B-1.

创建栖月汇商贸微商城接入案例到 IntegrationCase 表，让 /apollo/cases 页面可见。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
与 d2_qiyuehui_init_load.py 的关系
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  d2_qiyuehui_init_load.py:    落地 8 OT 数字孪生数据（pipeline 数据层）
  d2_6_qiyuehui_integration_case.py (本脚本): 创建接入案例（展示层）
  两者共享同一 scope: org_id=org-org / project_id=dev-project

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
角色与职责分离
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CREATE_CASE_OPERATION    需要 role: integration-case-maker
  PROJECT_CASE_OPERATION   需要 role: integration-case-projector
  本脚本用 subject=d2-6-case-creator 持有 maker 角色（创建案例），
  用 subject=d2-6-evidence-projector 持有 projector 角色（写证据快照），
  满足 IntegrationCase 的操作授权。

幂等:
  通过 idempotency_key 保证。重复运行返回同一 case_id，不会创建重复案例。
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICES_API = REPO_ROOT / "services" / "aos-api"
sys.path.insert(0, str(SERVICES_API))

from aos_api.asset_registry.control_wiring import (  # noqa: E402
    build_integration_case_service,
)
from aos_api.asset_registry.integration_contracts import (  # noqa: E402
    CreateIntegrationCaseRequest,
    CreateIntegrationEvidenceSnapshotRequest,
)
from aos_api.asset_registry.integration_service import (  # noqa: E402
    IntegrationRequestContext,
)
from aos_api.db import get_dsn  # noqa: E402

# ─────────────────────────────────────────────────────────
# scope（与 d2_qiyuehui_init_load.py 一致）
# ─────────────────────────────────────────────────────────
ORG_ID = "org-org"
PROJECT_ID = "dev-project"

# 栖月汇案例参数
INSTALLATION_ID = "7f3c1a2e-5b6d-4c8e-9f0a-1b2c3d4e5f60"  # 固定 UUID（幂等可追溯）
OVERLAY_REVISION = "d2.6-qiyuehui-v1"
DISPLAY_NAME = "栖月汇商贸微商城接入"
CASE_IDEMPOTENCY_KEY = "d2-6-qiyuehui-case-create"
EVIDENCE_IDEMPOTENCY_KEY = "d2-6-evidence-1"

MAKER_SUBJECT = "d2-6-case-creator"
PROJECTOR_SUBJECT = "d2-6-evidence-projector"
MAKER_ROLES = ("integration-case-maker",)
PROJECTOR_ROLES = ("integration-case-projector",)

# 开发环境 installation 占位 composition_pk（绕过 FK；
# resolver 只校验 installation + revision 的 JOIN，不验证 composition 真实性）
DEV_COMPOSITION_PK = "00000000-0000-0000-0000-000000000d7e"  # dev-composition 占位（合法 UUID）
DEV_LOCK_HASH = "sha256:" + "0" * 64


def ensure_installation_binding() -> None:
    """确保 bundle_installation + revision 存在（state=active）。

    Development-only 简化：用 session_replication_role=replica 绕过 FK 与触发器，
    直插最小记录。resolver (integration_reader.required_markings_for_create_in_transaction)
    只校验 installation + revision JOIN 且 state='active'，不验证 composition 真实性。

    生产环境应通过完整 composition→lock→installation service 链路创建。
    """
    installation_pk = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"qiyuehui-{ORG_ID}-{PROJECT_ID}"))
    composition_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"qiyuehui-comp-{ORG_ID}-{PROJECT_ID}"))
    now = datetime.now(UTC)
    # composition 最小记录（让 integration_store 的三表 JOIN 通过）
    comp_request_json = json.dumps({"bundleIds": ["domain.ecommerce.core"]})
    comp_request_hash = "sha256:" + "0" * 64
    registry_snap = json.dumps({"bundles": {}})
    registry_snap_hash = "sha256:" + "0" * 64
    with psycopg.connect(get_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute("SET session_replication_role = 'replica'")
            # 层 1: bundle_composition
            cur.execute(
                """
                INSERT INTO bundle_composition
                  (org_id, project_id, composition_pk, composition_id,
                   request_json, request_hash,
                   registry_snapshot_json, registry_snapshot_hash,
                   resolver_version, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (org_id, project_id, composition_pk) DO NOTHING
                """,
                (
                    ORG_ID, PROJECT_ID, DEV_COMPOSITION_PK, composition_id,
                    comp_request_json, comp_request_hash,
                    registry_snap, registry_snap_hash,
                    "d2.6-dev", MAKER_SUBJECT, now,
                ),
            )
            # 层 2: bundle_installation_revision
            cur.execute(
                """
                INSERT INTO bundle_installation_revision
                  (org_id, project_id, installation_pk, revision, parent_revision,
                   state, composition_pk, lock_revision, lock_hash,
                   permission_diff_hash, migration_plan_hash, contribution_diff_hash,
                   overlay_revision, requested_by, decision_id, created_at)
                VALUES (%s, %s, %s, 1, NULL, 'active', %s, 1, %s, %s, %s, %s, %s, %s, NULL, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    ORG_ID, PROJECT_ID, installation_pk,
                    DEV_COMPOSITION_PK, DEV_LOCK_HASH,
                    DEV_LOCK_HASH, DEV_LOCK_HASH, DEV_LOCK_HASH,
                    OVERLAY_REVISION, MAKER_SUBJECT, now,
                ),
            )
            # 层 3: bundle_installation
            cur.execute(
                """
                INSERT INTO bundle_installation
                  (org_id, project_id, installation_pk, installation_id, display_name,
                   current_revision, active_revision, previous_active_revision,
                   etag_version, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 1, 1, NULL, 1, %s, %s, %s)
                ON CONFLICT (org_id, project_id, installation_id) DO UPDATE SET
                   active_revision = EXCLUDED.active_revision,
                   current_revision = EXCLUDED.current_revision
                """,
                (
                    ORG_ID, PROJECT_ID, installation_pk, INSTALLATION_ID,
                    DISPLAY_NAME, MAKER_SUBJECT, now, now,
                ),
            )
            cur.execute("SET session_replication_role = 'origin'")
        conn.commit()
    print(f"[ensure_installation] binding ready installation_id={INSTALLATION_ID}")


def _make_context(subject: str, roles: tuple[str, ...]) -> IntegrationRequestContext:
    return IntegrationRequestContext(
        org_id=ORG_ID,
        project_id=PROJECT_ID,
        subject=subject,
        roles=roles,
        markings=(),
    )


def main() -> int:
    # 步骤 0: 确保 installation binding 存在（create_case 前置条件）
    ensure_installation_binding()

    service = build_integration_case_service()

    # 步骤 1: create_case（幂等）
    maker_ctx = _make_context(MAKER_SUBJECT, MAKER_ROLES)
    create_request = CreateIntegrationCaseRequest(
        installationId=INSTALLATION_ID,
        overlayRevision=OVERLAY_REVISION,
        displayName=DISPLAY_NAME,
    )
    print(f"[create_case] {DISPLAY_NAME} ...")
    receipt = service.create_case(
        context=maker_ctx,
        request=create_request,
        idempotency_key=CASE_IDEMPOTENCY_KEY,
    )
    case_detail = json.loads(receipt.response_json)
    case_id = case_detail["caseId"]
    case_etag = receipt.response_etag
    print(
        f"[ok] case created/fetched case_id={case_id} "
        f"status={receipt.status_code} etag={case_etag}"
    )

    # 步骤 2: project evidence snapshot（写入证据快照，让案例有可读证据）
    projector_ctx = _make_context(PROJECTOR_SUBJECT, PROJECTOR_ROLES)
    snapshot_request = CreateIntegrationEvidenceSnapshotRequest()
    print(f"[evidence_snapshot] case_id={case_id} ...")
    try:
        evidence_receipt = service.create_evidence_snapshot(
            context=projector_ctx,
            case_id=case_id,
            request=snapshot_request,
            idempotency_key=EVIDENCE_IDEMPOTENCY_KEY,
            if_match=case_etag,
        )
        print(f"[ok] evidence snapshot status={evidence_receipt.status_code}")
    except Exception as exc:
        # 证据快照失败不阻断主流程（案例已创建，页面可见）
        print(f"[warn] evidence snapshot failed (non-fatal): {exc}")

    # 验证：list_cases 应包含栖月汇案例
    list_ctx = _make_context(MAKER_SUBJECT, MAKER_ROLES)
    cases = service.list_cases(
        context=list_ctx,
        scope="current",
        limit=50,
        offset=0,
    )
    cases_json = json.loads(cases.model_dump_json(by_alias=True)) if hasattr(cases, "model_dump_json") else cases
    items = cases_json.get("items", []) if isinstance(cases_json, dict) else []
    found = [c for c in items if c.get("caseId") == case_id]
    if not found:
        print(f"[FAIL] case {case_id} not in list_cases output")
        return 1
    print(f"[verified] case visible: {found[0].get('displayName')}")

    # get_case_detail 二次验证
    detail = service.get_case(context=list_ctx, case_id=case_id)
    print(
        f"[verified] case detail: stage={detail.computed_stage} "
        f"snapshots={len(detail.snapshots) if hasattr(detail, 'snapshots') else 'n/a'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

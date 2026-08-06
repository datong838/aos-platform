"""d3_integration_case_roles_fix.py — D3 IntegrationCase 角色名补齐 + stage4 补跑。

背景:
  原 d3_qiyuehui_full_fde_case_creation.py 的 stage4_create_integration_case 函数有两处错误:
    1. 角色名错误：使用 `aip-case-maker` / `aip-case-approver`，
       正确应为 `integration-case-maker` (CREATE_CASE_OPERATION) /
       `integration-case-projector` (PROJECT_CASE_OPERATION)。
       参见 aos_api/asset_registry/integration_policy.py:39-45。
    2. create_evidence_snapshot 缺少必传参数 idempotency_key + if_match。
       参见 aos_api/asset_registry/integration_service.py:279-294。
  原 stage4 调用被 try/except 静默吞错，导致:
    - integration_case_command 表 0 条
    - integration_case 表 0 条
    - integration_evidence_snapshot 表 0 条

最小更改原则:
  不修改原 d3_qiyuehui_full_fde_case_creation.py（保护历史脚本完整性）。
  本脚本独立补建两个 active installation 对应的 IntegrationCase + EvidenceSnapshot:
    - v1: installation_id=56c200af-9308-4125-af02-1035100785dd
          overlay_revision=d3-qiyuehui-v1-full-stack
    - v2: installation_id=1286521e-6d6e-42b4-8aad-b5daaa1b01bb
          overlay_revision=d3-qiyuehui-v2-decision-tags

验证标准:
  - integration_case 表 ≥ 2 条记录（v1 + v2 各一）
  - integration_evidence_snapshot 表 ≥ 2 条记录
  - 字段 required_markings 为 []（空 markings 满足校验）
  - case 与 installation 通过 integration_instance_revision 关联
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICES_API = REPO_ROOT / "services" / "aos-api"
sys.path.insert(0, str(SERVICES_API))

from aos_api.asset_registry.control_wiring import build_integration_case_service
from aos_api.asset_registry.integration_contracts import (
    CreateIntegrationCaseRequest,
    CreateIntegrationEvidenceSnapshotRequest,
)
from aos_api.asset_registry.integration_service import (
    IntegrationCaseService,
    IntegrationRequestContext,
)
from aos_api.db import connect

# ============================================================
# 全局参数
# ============================================================
ORG_ID = "org-org"
PROJECT_ID = "dev-project"

# 角色契约（来自 integration_policy.py:39-45）
# CREATE_CASE_OPERATION: frozenset({"integration-case-maker"})
# PROJECT_CASE_OPERATION: frozenset({"integration-case-projector"})
CASE_MAKER_SUBJECT = "d3-roles-fix-case-maker"
CASE_MAKER_ROLES = frozenset({"integration-case-maker"})
CASE_PROJECTOR_SUBJECT = "d3-roles-fix-case-projector"
CASE_PROJECTOR_ROLES = frozenset({"integration-case-projector"})

# 两个 active installation 目标（从 DB 查询确认）
TARGET_INSTALLATIONS = [
    {
        "installation_id": "56c200af-9308-4125-af02-1035100785dd",
        "overlay_revision": "d3-qiyuehui-v1-full-stack",
        "display_name": "栖月汇商贸 · 微商城全栈接入（D3：W03 客户台 + L05 分润异常）",
        "idempotency_suffix": "v1-roles-fix",
    },
    {
        "installation_id": "1286521e-6d6e-42b4-8aad-b5daaa1b01bb",
        "overlay_revision": "d3-qiyuehui-v2-decision-tags",
        "display_name": "栖月汇商贸 · 微商城全栈接入（D3 叠加：W03 decision_tag 注入）",
        "idempotency_suffix": "v2-roles-fix",
    },
]

REGISTRY_PREFIX = "d3-roles-fix"


# ============================================================
# 工具函数
# ============================================================
def _mk_ctx(subject: str, roles: frozenset[str]) -> IntegrationRequestContext:
    """构造 IntegrationRequestContext（markings 为空满足 installation 无 markings 要求）。"""
    return IntegrationRequestContext(
        org_id=ORG_ID,
        project_id=PROJECT_ID,
        subject=subject,
        roles=tuple(roles),
        markings=(),
    )


def _verify_installation_active(installation_id: str, overlay_revision: str) -> bool:
    """在 DB 校验 installation 当前状态为 active 且 overlay_revision 匹配。"""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT i.installation_id, r.state, r.overlay_revision
              FROM bundle_installation i
              JOIN bundle_installation_revision r
                ON r.org_id=i.org_id AND r.project_id=i.project_id
               AND r.installation_pk=i.installation_pk
               AND r.revision=i.active_revision
             WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s
            """,
            (ORG_ID, PROJECT_ID, installation_id),
        ).fetchone()
    if row is None:
        print(f"    ❌ installation {installation_id} 不存在")
        return False
    state_ok = str(row["state"]).lower() == "active"
    overlay_ok = row["overlay_revision"] == overlay_revision
    if not state_ok:
        print(f"    ❌ state={row['state']} (期望 active)")
    if not overlay_ok:
        print(f"    ❌ overlay_revision={row['overlay_revision']} (期望 {overlay_revision})")
    return state_ok and overlay_ok


def _check_existing_case(installation_id: str) -> str | None:
    """检查 installation 是否已绑定 case，返回 case_id 或 None。"""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT c.case_id
              FROM integration_case c
              JOIN integration_instance ii
                ON ii.org_id=c.org_id AND ii.project_id=c.project_id
               AND ii.case_pk=c.case_pk
              JOIN integration_instance_revision iir
                ON iir.org_id=ii.org_id AND iir.project_id=ii.project_id
               AND iir.instance_pk=ii.instance_pk
              JOIN bundle_installation bi
                ON bi.installation_pk=iir.installation_pk
             WHERE c.org_id=%s AND c.project_id=%s AND bi.installation_id=%s
             LIMIT 1
            """,
            (ORG_ID, PROJECT_ID, installation_id),
        ).fetchone()
    return str(row["case_id"]) if row else None


# ============================================================
# 阶段 1: 为单个 installation 创建 IntegrationCase + EvidenceSnapshot
# ============================================================
def create_case_for_installation(target: dict[str, str]) -> dict[str, Any] | None:
    """对单个 installation 执行 create_case + create_evidence_snapshot。"""
    inst_id = target["installation_id"]
    overlay_rev = target["overlay_revision"]
    display_name = target["display_name"]
    suffix = target["idempotency_suffix"]

    print(f"\n── installation {inst_id} (overlay={overlay_rev}) ──")

    # 1.1 校验 installation active + overlay_revision 匹配
    if not _verify_installation_active(inst_id, overlay_rev):
        print(f"  ⚠️  installation 校验失败，跳过")
        return None

    # 1.2 检查是否已存在 case（幂等避免重复）
    existing_case_id = _check_existing_case(inst_id)
    if existing_case_id:
        print(f"  ✅ 已存在 case_id={existing_case_id}，跳过 create_case")
        return {"case_id": existing_case_id, "skipped_create": True}

    # 1.3 调用 create_case
    service: IntegrationCaseService = build_integration_case_service()
    create_req = CreateIntegrationCaseRequest.model_validate({
        "installationId": inst_id,
        "overlayRevision": overlay_rev,
        "displayName": display_name,
    })
    try:
        receipt = service.create_case(
            context=_mk_ctx(CASE_MAKER_SUBJECT, CASE_MAKER_ROLES),
            request=create_req,
            idempotency_key=f"{REGISTRY_PREFIX}-create-case-{suffix}",
        )
    except Exception as e:
        print(f"  ❌ create_case 失败: {type(e).__name__}: {e}")
        traceback.print_exc()
        return None

    assert receipt.status_code == 201, f"create_case status={receipt.status_code}"
    case_id = receipt.response_json.get("caseId")
    etag_version = receipt.response_etag  # 形如 '"1"'
    print(f"  ✅ create_case OK: case_id={case_id} etag={etag_version}")

    # 1.4 调用 create_evidence_snapshot（PROJECT_CASE_OPERATION）
    snap_req = CreateIntegrationEvidenceSnapshotRequest.model_validate({})
    try:
        snap_receipt = service.create_evidence_snapshot(
            context=_mk_ctx(CASE_PROJECTOR_SUBJECT, CASE_PROJECTOR_ROLES),
            case_id=case_id,
            request=snap_req,
            idempotency_key=f"{REGISTRY_PREFIX}-evidence-snap-{suffix}",
            if_match=etag_version,
        )
    except Exception as e:
        print(f"  ⚠️  create_evidence_snapshot 失败（不阻断 case 创建）: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {"case_id": case_id, "snapshot_skipped": True}

    print(f"  ✅ create_evidence_snapshot OK: status={snap_receipt.status_code} etag={snap_receipt.response_etag}")
    return {"case_id": case_id, "snapshot_etag": snap_receipt.response_etag}


# ============================================================
# 阶段 2: 验证回读
# ============================================================
def verify_results() -> None:
    print(f"\n{'='*60}")
    print("[阶段2] 验证回读")
    print(f"{'='*60}")

    with connect() as conn:
        # 2.1 integration_case 行数
        rows = conn.execute(
            """
            SELECT c.case_id, c.display_name, c.owner, c.required_markings,
                   bi.installation_id, iir.overlay_revision, c.created_at
              FROM integration_case c
              JOIN integration_instance ii
                ON ii.org_id=c.org_id AND ii.project_id=c.project_id AND ii.case_pk=c.case_pk
              JOIN integration_instance_revision iir
                ON iir.org_id=ii.org_id AND iir.project_id=ii.project_id
               AND iir.instance_pk=ii.instance_pk AND iir.revision=ii.current_revision
              JOIN bundle_installation bi
                ON bi.installation_pk=iir.installation_pk
             WHERE c.org_id=%s AND c.project_id=%s
             ORDER BY c.created_at
            """,
            (ORG_ID, PROJECT_ID),
        ).fetchall()
        print(f"\n[integration_case] 共 {len(rows)} 条:")
        for r in rows:
            mark = "✅"
            print(f"  {mark} case_id={r['case_id']}")
            print(f"      display_name={r['display_name']}")
            print(f"      installation_id={r['installation_id']}")
            print(f"      overlay_revision={r['overlay_revision']}")
            print(f"      required_markings={r['required_markings']}")
            print(f"      owner={r['owner']}")

        # 2.2 integration_evidence_snapshot 行数
        snap_rows = conn.execute(
            """
            SELECT s.snapshot_revision, s.instance_pk, s.instance_revision,
                   s.computed_stage, s.evidence_count, s.created_at
              FROM integration_evidence_snapshot s
             WHERE s.org_id=%s AND s.project_id=%s
             ORDER BY s.created_at
            """,
            (ORG_ID, PROJECT_ID),
        ).fetchall()
        print(f"\n[integration_evidence_snapshot] 共 {len(snap_rows)} 条:")
        for r in snap_rows:
            print(f"  ✅ snapshot_revision={r['snapshot_revision']} instance_pk={r['instance_pk']} stage={r['computed_stage']} evidence_count={r['evidence_count']}")

        # 2.3 integration_case_command 幂等记录
        cmd_rows = conn.execute(
            """
            SELECT operation, idempotency_key, subject, status_code, created_at
              FROM integration_case_command
             WHERE org_id=%s AND project_id=%s
             ORDER BY created_at
            """,
            (ORG_ID, PROJECT_ID),
        ).fetchall()
        print(f"\n[integration_case_command] 共 {len(cmd_rows)} 条:")
        for r in cmd_rows:
            print(f"  ✅ op={r['operation']:30s} status={r['status_code']} subj={r['subject']} key={r['idempotency_key']}")

    # 2.4 断言
    print(f"\n{'='*60}")
    print("[断言]")
    print(f"{'='*60}")
    assert len(rows) >= 2, f"integration_case 应 ≥ 2 条（v1+v2 各一），实际 {len(rows)}"
    print(f"  ✅ integration_case 行数 {len(rows)} ≥ 2")
    assert len(snap_rows) >= 2, f"integration_evidence_snapshot 应 ≥ 2 条，实际 {len(snap_rows)}"
    print(f"  ✅ integration_evidence_snapshot 行数 {len(snap_rows)} ≥ 2")
    assert len(cmd_rows) >= 4, f"integration_case_command 应 ≥ 4 条（2 create + 2 snapshot），实际 {len(cmd_rows)}"
    print(f"  ✅ integration_case_command 行数 {len(cmd_rows)} ≥ 4")

    # 2.5 overlay_revision 覆盖
    overlays = {r["overlay_revision"] for r in rows}
    assert "d3-qiyuehui-v1-full-stack" in overlays, "缺少 v1 overlay_revision"
    assert "d3-qiyuehui-v2-decision-tags" in overlays, "缺少 v2 overlay_revision"
    print(f"  ✅ overlay_revision 覆盖 v1 + v2: {sorted(overlays)}")

    print(f"""
  ════════════════════════════════════════════════
  D3 IntegrationCase roles marking 补齐完成:
    ✅ integration_case ≥ 2 条（v1 + v2）
    ✅ integration_evidence_snapshot ≥ 2 条
    ✅ integration_case_command 幂等记录 ≥ 4 条
    ✅ 角色契约修正: integration-case-maker / integration-case-projector
    ✅ IntegrationCase 通过 integration_instance_revision 关联 installation
  ════════════════════════════════════════════════
""")


# ============================================================
# MAIN
# ============================================================
def main() -> int:
    print("=" * 70)
    print("D3 IntegrationCase 角色名补齐 + stage4 补跑")
    print("=" * 70)
    print(f"目标: 为 v1 + v2 两个 active installation 各补建 IntegrationCase + EvidenceSnapshot")
    print(f"角色契约: CREATE_CASE→integration-case-maker / PROJECT_CASE→integration-case-projector")

    results = []
    for target in TARGET_INSTALLATIONS:
        result = create_case_for_installation(target)
        results.append({"target": target, "result": result})

    # 汇总
    print(f"\n{'='*60}")
    print("[汇总]")
    print(f"{'='*60}")
    for r in results:
        t = r["target"]
        res = r["result"]
        if res is None:
            status = "❌ 失败"
        elif res.get("skipped_create"):
            status = f"⏭️ 跳过（已存在 case_id={res['case_id']}）"
        elif res.get("snapshot_skipped"):
            status = f"⚠️ case 已建但 snapshot 失败 (case_id={res['case_id']})"
        else:
            status = f"✅ 全通过 (case_id={res['case_id']} snap_etag={res.get('snapshot_etag')})"
        print(f"  [{t['idempotency_suffix']}] {status}")

    # 验证
    verify_results()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""后端提案API端到端验证：创建→列取→审批→合并"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 直接导入引擎验证核心逻辑（不依赖 HTTP 认证）
from aos_api.tenant_scope import TenantScope
from aos_api.phase5_pipeline_engine import get_engine

def main():
    print("=" * 60)
    print("后端提案引擎核心逻辑验证")
    print("=" * 60)
    results = []

    scope = TenantScope("org-org", "dev-project")
    eng = get_engine()

    # ---- Step 0: 确保有测试管道 ----
    print("\n[0/5] 准备测试管道")
    test_pl_id = "P-TEST-PROPOSAL"
    pl = eng.get_pipeline(scope, test_pl_id)
    if pl is None:
        pl = eng.create_pipeline(scope, "测试管道-提案验证", description="用于验证提案流程", pipeline_type="Batch", status="active")
        # 修正为固定ID
        rand_id = pl.id
        from aos_api.phase5_pipeline_engine import _LOCK
        with _LOCK:
            eng._pipelines.pop(eng._tenant_key(scope, rand_id), None)
            pl.id = test_pl_id
            eng._pipelines[eng._tenant_key(scope, test_pl_id)] = pl
    print(f"  管道ID: {pl.id}")
    results.append(("准备测试管道", True))

    # ---- Step 1: 创建提案 ----
    print("\n[1/5] 创建提案")
    pp = eng.create_proposal(
        scope,
        pipeline_id=test_pl_id,
        title="字段映射优化 & PII脱敏",
        description="会员数据常见字段映射，密码等敏感字段剔除",
        proposed_by="tester",
        diff_summary="新增常见字段28个，PII排除13个敏感字段",
    )
    print(f"  提案ID: {pp.id}, 状态: {pp.status}")
    assert pp.status == "pending", f"expected pending, got {pp.status}"
    results.append(("创建提案 (pending)", True))
    print("  → PASS")

    # ---- Step 2: 列出提案 ----
    print("\n[2/5] 列出管道提案")
    items = eng.list_proposals(scope, test_pl_id)
    print(f"  提案数: {len(items)}")
    found = any(p.id == pp.id for p in items)
    assert found, "新创建的提案未在列表中找到"
    results.append(("列表提案", True))
    print("  → PASS")

    # ---- Step 3: 直接合并（应当失败，因为未审批） ----
    print("\n[3/5] 未审批直接合并（预期失败）")
    try:
        eng.merge_proposal(scope, test_pl_id, pp.id)
        print("  → FAIL: 居然成功了（错误）")
        results.append(("未审批合并被拒绝", False))
    except ValueError as e:
        print(f"  正确拒绝: {e}")
        results.append(("未审批合并被拒绝", True))
        print("  → PASS")

    # ---- Step 4: 审批提案 ----
    print("\n[4/5] 审批提案")
    pp2 = eng.approve_proposal(scope, test_pl_id, pp.id)
    print(f"  审批后状态: {pp2.status}")
    assert pp2.status == "approved", f"expected approved, got {pp2.status}"
    results.append(("审批提案 (approved)", True))
    print("  → PASS")

    # ---- Step 5: 合并提案 ----
    print("\n[5/5] 合并提案")
    pp3 = eng.merge_proposal(scope, test_pl_id, pp.id)
    print(f"  合并后状态: {pp3.status}")
    assert pp3.status == "merged", f"expected merged, got {pp3.status}"
    results.append(("合并提案 (merged)", True))
    print("  → PASS")

    # ---- 清理 ----
    print("\n清理测试数据...")
    # 删除测试管道（可选）
    # eng.delete_pipeline(scope, test_pl_id)

    # 汇总
    print("\n" + "=" * 60)
    print("验证结果汇总")
    print("=" * 60)
    all_pass = True
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  {name}")
        if not ok:
            all_pass = False
    print("=" * 60)
    if all_pass:
        print("🎉 提案引擎核心逻辑全部验证通过！")
        print("  状态机: pending → approved → merged ✅")
        print("  Maker-Checker 门禁：未审批合并被拒绝 ✅")
    else:
        print("⚠️  有失败项")
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())

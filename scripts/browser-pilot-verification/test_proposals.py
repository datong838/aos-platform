#!/usr/bin/env python3
"""提案系统自测脚本：创建 → 审批 → 合并 → Diff预览"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine_adapter import BrowserPilot

SS_DIR = "/Users/ddt/work/projects/ai_agent/aos-platform/plugins/agents/browser-pilot/screenshots"
os.makedirs(SS_DIR, exist_ok=True)

def main():
    print("=" * 60)
    print("提案系统端到端自测")
    print("=" * 60)
    results = []

    with BrowserPilot() as pilot:
        # ---- Step 1: 打开提案页面 ----
        print("\n[1/6] 打开提案页面 /data/pipeline-proposals")
        r = pilot.navigate("http://127.0.0.1:5173/data/pipeline-proposals")
        pilot.wait_for(text="管道提案", timeout_ms=15000)
        pilot.screenshot(output_path=f"{SS_DIR}/01_proposals_page.png")
        ok = "管道提案" in (r.text or "")
        results.append(("打开提案页面", ok))
        print(f"  → {'PASS' if ok else 'FAIL'}")

        # ---- Step 2: 点击新建提案 ----
        print("\n[2/6] 点击「新建提案」按钮")
        try:
            pilot.click("button:has-text('新建提案')", timeout_ms=5000)
            pilot.wait_for(text="新建管道提案", timeout_ms=5000)
            pilot.screenshot(output_path=f"{SS_DIR}/02_create_proposal_modal.png")
            results.append(("新建提案弹窗", True))
            print("  → PASS")
        except Exception as e:
            print(f"  → FAIL: {e}")
            results.append(("新建提案弹窗", False))

        # ---- Step 3: 填写提案表单 ----
        print("\n[3/6] 填写提案表单（选择管道+标题+说明）")
        try:
            # 选择第一个管道
            pilot.select_option("select", label_contains="栖月汇")
            # 填写标题
            pilot.type_text("input[placeholder*='标题']", "字段映射优化 & PII脱敏更新", clear=True)
            # 填写说明
            pilot.type_text("textarea", "背景：会员数据字段映射优化\n目的：展示常见字段，剔除敏感信息\n影响：P08会员管道", clear=True)
            pilot.screenshot(output_path=f"{SS_DIR}/03_proposal_form_filled.png")
            # 提交
            pilot.click("button:has-text('提交提案')")
            pilot.wait_for(text="提案已创建", timeout_ms=10000)
            pilot.screenshot(output_path=f"{SS_DIR}/04_proposal_created.png")
            results.append(("创建提案", True))
            print("  → PASS")
        except Exception as e:
            print(f"  → FAIL: {e}")
            results.append(("创建提案", False))

        # ---- Step 4: 预览Diff ----
        print("\n[4/6] 点击「预览 Diff」")
        try:
            pilot.click("button:has-text('预览 Diff')", timeout_ms=5000)
            pilot.wait_for(text="Diff 预览", timeout_ms=5000)
            pilot.screenshot(output_path=f"{SS_DIR}/05_diff_preview.png")
            # 关闭
            pilot.click("button:has-text('关闭 Diff')")
            results.append(("Diff预览", True))
            print("  → PASS")
        except Exception as e:
            print(f"  → FAIL: {e}")
            results.append(("Diff预览", False))

        # ---- Step 5: 审批提案 ----
        print("\n[5/6] 点击「审批」按钮")
        try:
            pilot.click("button.btn-primary:has-text('审批')", timeout_ms=5000)
            pilot.wait_for(text="提案已审批通过", timeout_ms=10000)
            pilot.screenshot(output_path=f"{SS_DIR}/06_proposal_approved.png")
            results.append(("审批提案", True))
            print("  → PASS")
        except Exception as e:
            print(f"  → FAIL: {e}")
            results.append(("审批提案", False))

        # ---- Step 6: 合并提案 ----
        print("\n[6/6] 点击「合并到主分支」按钮")
        try:
            pilot.click("button.btn-primary:has-text('合并')", timeout_ms=5000)
            pilot.wait_for(text="已合并到主分支", timeout_ms=10000)
            pilot.screenshot(output_path=f"{SS_DIR}/07_proposal_merged.png")
            # 切换到"已处理"Tab
            pilot.click("button:has-text('已处理')")
            pilot.wait_for(text="已合并", timeout_ms=5000)
            pilot.screenshot(output_path=f"{SS_DIR}/08_history_tab.png")
            results.append(("合并提案", True))
            print("  → PASS")
        except Exception as e:
            print(f"  → FAIL: {e}")
            results.append(("合并提案", False))

    # 汇总
    print("\n" + "=" * 60)
    print("自测结果汇总")
    print("=" * 60)
    all_pass = True
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  {name}")
        if not ok:
            all_pass = False
    print("=" * 60)
    if all_pass:
        print("🎉 全部通过！截图保存到:", SS_DIR)
    else:
        print("⚠️  有失败项，请检查截图")
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())

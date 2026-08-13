#!/usr/bin/env python3
"""
Browser Pilot 验收：画布节点中文名 + 连线 + 属性面板数据
验证对象：P08-customer-lite-qyh 管道画布
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine_adapter import BrowserPilot


BASE_URL = "http://127.0.0.1:5173"
ORG_INJECT_JS = """
(async function() {
    try {
        await fetch("http://127.0.0.1:8080/v1/orgs/org-org/enter", {
            method: "POST",
            headers: {
                "Authorization": "Bearer dev",
                "X-Org-Id": "org-org",
                "X-Project-Id": "dev-project",
                "Content-Type": "application/json"
            }
        });
        sessionStorage.setItem("aos-tenant-v1", JSON.stringify({orgId:"org-org", projectId:"dev-project", workspaceName:"默认工作区"}));
        localStorage.setItem("aos-api-base-v1", "http://127.0.0.1:8080");
        return "ok";
    } catch(e) { return "err:" + e.message; }
})()
"""

def main():
    print("=" * 70)
    print("  Browser Pilot 画布验收：中文名 + 连线 + 属性面板")
    print("=" * 70)

    pages = [
        {
            "name": "01_画布_P08",
            "url": f"{BASE_URL}/data/pipelines/P08-customer-lite-qyh",
            "wait_for": ".bp-pipe-canvas, .app-loaded",
            "wait_ms_before_check": 6000,
            "inject_js_before": ORG_INJECT_JS,
            "refresh_after_inject": True,
            "asserts": [
                # 节点中文标题
                {"text": "栖月汇微商城", "should_exist": True,
                 "desc": "输入节点显示数据源中文名（栖月汇微商城）"},
                {"text": "数据抽取", "should_exist": True,
                 "desc": "变换节点标题为中文（数据抽取）"},
                {"text": "会员基础档案", "should_exist": True,
                 "desc": "输出节点显示中文名称（会员基础档案）"},
                # 画布页面标题
                {"text": "管道构建", "should_exist": True,
                 "desc": "页面 lede 为中文（管道构建·画布）"},
                # 不应出现原始英文/ID
                {"text": "niushop-qyh Source", "should_exist": False,
                 "desc": "输入节点不出现原始 niushop-qyh Source ID"},
                {"text": "ri.aos.main.dataset.P08", "should_exist": False,
                 "desc": "输出节点不出现完整 RID"},
                # 属性面板（默认选中输出节点）
                {"text": "源表", "should_exist": True,
                 "desc": "属性面板有源表字段"},
                {"text": "ns_member", "should_exist": True,
                 "desc": "源表值为 ns_member（需点击输入节点）"},
            ],
            "screenshot": True,
            "screenshot_dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots"),
            "check_console_errors": True,
        },
    ]

    all_passed = True
    with BrowserPilot() as pilot:
        for page_cfg in pages:
            name = page_cfg["name"]
            url = page_cfg["url"]
            print(f"\n--- 验收 {name} ---")
            print(f"  URL: {url}")

            # 导航
            r = pilot.navigate(url)
            if not r.success:
                print(f"  ❌ 导航失败: {r.error}")
                all_passed = False
                continue
            print(f"  ✅ 导航成功")

            # 注入组织切换
            if page_cfg.get("inject_js_before"):
                pilot.call_raw("browser_evaluate", {
                    "expression": page_cfg["inject_js_before"],
                    "returnByValue": True,
                    "awaitPromise": True,
                })
                print(f"  ✅ 组织切换注入完成")

            # 等待基础加载
            wf = page_cfg.get("wait_for")
            if wf:
                pilot.wait_for(selector=wf, timeout_ms=8000)

            wait_ms = page_cfg.get("wait_ms_before_check", 3000)
            import time
            time.sleep(wait_ms / 1000)

            # 刷新后再等
            if page_cfg.get("refresh_after_inject"):
                pilot.call_raw("browser_evaluate", {
                    "expression": "location.reload()"
                })
                time.sleep((wait_ms + 2000) / 1000)

            # 先点击输入节点，激活属性面板显示源表等信息
            print(f"  🖱  点击输入节点以查看属性面板")
            pilot.call_raw("browser_evaluate", {
                "expression": """
                    (function() {
                        const els = document.querySelectorAll('div');
                        for (const el of els) {
                            if (el.textContent.trim() === '栖月汇微商城') {
                                const rect = el.getBoundingClientRect();
                                const x = rect.left + rect.width / 2;
                                const y = rect.top + rect.height / 2;
                                el.dispatchEvent(new MouseEvent('click', {
                                    bubbles: true, cancelable: true, clientX: x, clientY: y
                                }));
                                return 'clicked at x=' + x + ', y=' + y;
                            }
                        }
                        return 'not found';
                    })()
                """,
                "returnByValue": True,
            })
            time.sleep(1.5)

            # 断言
            for ass in page_cfg["asserts"]:
                text = ass["text"]
                desc = ass.get("desc", text)
                should = ass.get("should_exist", True)
                ar = pilot.assert_text(text)
                passed = should == ar.passed
                status = "✅" if passed else "❌"
                print(f"  {status} {desc}")
                if not passed:
                    all_passed = False

            # 截图
            if page_cfg.get("screenshot"):
                ss_dir = page_cfg.get("screenshot_dir", "/tmp/browser-pilot")
                os.makedirs(ss_dir, exist_ok=True)
                ss_path = os.path.join(ss_dir, f"{name}.png")
                pilot.screenshot(output_path=ss_path, full_page=True)
                print(f"  📸 截图保存: {ss_path}")

    print("\n" + "=" * 70)
    if all_passed:
        print("  ✅ 所有验收通过")
    else:
        print("  ❌ 存在验收失败项，请查看上方日志")
    print("=" * 70)
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())

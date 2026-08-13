#!/usr/bin/env python3
"""
Kitewright — 快速演示 (v0.3)
展示如何用 3 行代码完成前端页面验收
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine_adapter import Kitewright


def demo_single_page():
    """演示：单页面导航 + 截图 + 断言"""
    print("\n>>> 演示 1: 单页面导航 + 截图 + 断言")

    with Kitewright() as pilot:
        # 导航
        result = pilot.navigate("http://127.0.0.1:5173/")
        print(f"  成功: {result.success}")
        print(f"  文本长度: {len(result.text)} chars")

        # 截图
        pilot.screenshot(output_path="/tmp/kitewright/demo_home.png")
        print("  截图: /tmp/kitewright/demo_home.png")

        # 无障碍树快照（穿透 Shadow DOM）
        tree = pilot.snapshot()
        print(f"  无障碍树: {len(tree)} chars")

        # 断言
        r = pilot.assert_text("AOS")
        print(f"  断言 'AOS' 存在: {'PASS' if r.passed else 'FAIL'}")


def demo_batch_verify():
    """演示：批量验收（AOS 5 标准页面）"""
    print("\n>>> 演示 2: AOS 5 标准页面批量验收")

    pages = [
        {
            "name": "01_连接器目录",
            "url": "http://127.0.0.1:5173/data/connections",
            "wait_for": "[data-testid='connector-grid'], .ant-table, .app-loaded",
            "asserts": [
                {"text": "Error", "should_exist": False},
            ],
            "screenshot": True,
            "check_console_errors": True,
        },
        {
            "name": "02_数据源列表",
            "url": "http://127.0.0.1:5173/data",
            "asserts": [
                {"text": "Error", "should_exist": False},
            ],
            "screenshot": True,
        },
        {
            "name": "03_Pipeline",
            "url": "http://127.0.0.1:5173/data/pipelines",
            "asserts": [],
            "screenshot": True,
        },
        {
            "name": "04_资产包",
            "url": "http://127.0.0.1:5173/data/asset-bundles",
            "asserts": [],
            "screenshot": True,
        },
        {
            "name": "05_接入案例",
            "url": "http://127.0.0.1:5173/data/integration-cases",
            "asserts": [],
            "screenshot": True,
        },
    ]

    with Kitewright() as pilot:
        results = pilot.verify_pages(pages)
        return results


def demo_form_fill():
    """演示：表单填写"""
    print("\n>>> 演示 3: 表单填写 + 提交")

    with Kitewright() as pilot:
        pilot.navigate("http://127.0.0.1:5173/data/source/new")
        pilot.wait_for(selector="input[name='name']", timeout_ms=10000)

        pilot.type_text("input[name='name']", "测试数据源", clear=True)
        pilot.click("button[type='submit']")

        pilot.wait_for(text="创建成功", timeout_ms=5000)
        result = pilot.assert_text("创建成功")
        print(f"  表单提交: {'PASS' if result.passed else 'FAIL'}")


def demo_state_persistence():
    """演示：登录状态持久化"""
    print("\n>>> 演示 4: 状态持久化（登录一次，后续复用）")

    state = None
    with Kitewright() as pilot:
        pilot.navigate("http://127.0.0.1:5173/login")
        pilot.type_text("input[name='username']", "admin")
        pilot.type_text("input[name='password']", "password")
        pilot.click("button[type='submit']")
        pilot.wait_for(text="仪表盘", timeout_ms=10000)
        state = pilot.save_state()
        print(f"  状态已保存 ({len(str(state))} chars)")

    with Kitewright() as pilot:
        pilot.restore_state(state)
        pilot.navigate("http://127.0.0.1:5173/data")
        result = pilot.assert_text("数据源")
        print(f"  免登录访问: {'PASS' if result.passed else 'FAIL'}")


def demo_call_raw():
    """演示：直通调用 Kitewright MCP 工具"""
    print("\n>>> 演示 5: 直通调用（call_raw）")

    with Kitewright() as pilot:
        pilot.navigate("http://127.0.0.1:5173/")
        # 直接调用 engine_adapter 没有包装的工具
        result = pilot.call_raw("browser_snapshot", {"diff": False})
        text = result.get("result", {}).get("content", [{}])[0].get("text", "")
        print(f"  snapshot via call_raw: {len(text)} chars")


if __name__ == "__main__":
    print("=" * 60)
    print("  Kitewright v0.3 — 独立 Chrome/Chromium MCP 演示")
    print("=" * 60)

    try:
        demo_single_page()
    except Exception as e:
        print(f"  演示 1 失败: {e}")

    try:
        demo_batch_verify()
    except Exception as e:
        print(f"  演示 2 失败: {e}")

    # demo_form_fill()       # 需要真实表单
    # demo_state_persistence() # 需要真实登录
    # demo_call_raw()         # 需要页面在线

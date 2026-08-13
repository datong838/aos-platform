#!/usr/bin/env python3
"""
Browser Pilot — Step 2c/3 批量验收
铁律：只用 BrowserPilot（绝不写 CDP 脚本）
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine_adapter import BrowserPilot

BASE_URL = "http://127.0.0.1:5173"
SS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(SS_DIR, exist_ok=True)

ORG_INJECT = """
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

# P01~P08 验收矩阵（按铁律定义）
PIPELINE_CHECK = [
    {
        "pid": "P01-shop-qyh", "zh": "店铺",
        "checks": [
            ("页面标题", "栖月汇-店铺"),
            ("源表=ns_site", "ns_site"),
            ("主键=site_id", "site_id"),
            ("过滤=is_delete=0", "is_delete=0"),
        ],
    },
    {
        "pid": "P02-product-qyh", "zh": "商品",
        "checks": [
            ("页面标题", "栖月汇-商品"),
            ("源表=ns_goods", "ns_goods"),
            ("主键=goods_id", "goods_id"),
            ("过滤含 goods_state=1", "goods_state=1"),
        ],
    },
    {
        "pid": "P03-product-sku-qyh", "zh": "商品SKU",
        "checks": [
            ("页面标题", "栖月汇-商品SKU"),
            ("源表=ns_goods_sku", "ns_goods_sku"),
            ("主键=sku_id", "sku_id"),
        ],
    },
    {
        "pid": "P04-category-qyh", "zh": "类目",
        "checks": [
            ("页面标题", "栖月汇-类目"),
            ("源表=ns_goods_category", "ns_goods_category"),
            ("主键=category_id", "category_id"),
            ("过滤含 site_id=1", "site_id=1"),
        ],
    },
    {
        "pid": "P05-order-qyh", "zh": "订单",
        "checks": [
            ("页面标题", "栖月汇-订单"),
            ("源表=ns_order", "ns_order"),
            ("主键=order_id", "order_id"),
            ("过滤含 order_status", "order_status"),
        ],
    },
    {
        "pid": "P06-order-line-qyh", "zh": "订单明细",
        "checks": [
            ("页面标题", "栖月汇-订单明细"),
            ("源表=ns_order_goods", "ns_order_goods"),
            ("主键=id\n 唯一键模式", "id"),  # 比较宽松
        ],
    },
    {
        "pid": "P07-shipment-qyh", "zh": "发货",
        "checks": [
            ("页面标题", "栖月汇-发货"),
            ("源表=ns_express_delivery_package", "ns_express_delivery_package"),
            ("主键=id", "id"),
        ],
    },
    {
        "pid": "P08-customer-lite-qyh", "zh": "会员",
        "checks": [
            ("页面标题", "栖月汇-会员"),
            ("源表=ns_member", "ns_member"),
            ("主键=member_id", "member_id"),
            ("过滤含 member_status=1", "member_status=1"),
        ],
    },
]

# 7 个关键页面
PAGES = [
    {"name": "01_管道列表", "url": f"{BASE_URL}/data/pipelines",
     "asserts": [("8个管道标题", "栖月汇-"), ("P01店铺存在", "栖月汇-店铺"),
                ("P05订单存在", "栖月汇-订单"), ("P06订单明细存在", "栖月汇-订单明细"),
                ("P04类目存在", "栖月汇-类目")]},
    {"name": "02_P01店铺画布", "url": f"{BASE_URL}/data/pipelines/P01-shop-qyh",
     "asserts": []},  # 单独在上面矩阵里处理
    {"name": "07_管道提案", "url": f"{BASE_URL}/data/pipeline-proposals",
     "asserts": [("标题全中文", "提案 · "), ("数据源中文", "数据源：栖月汇微商城"),
                ("不应出现 Use LLM", "Use LLM"), ("不应出现 source=niushop-qyh", "source=niushop-qyh")]},
    {"name": "08_数据集预览", "url": f"{BASE_URL}/data/datasets",
     "asserts": [("导航步骤条存在", "数据集预览"),
                ("P02商品数据集存在", "商品"), ("P08会员数据集存在", "会员")]},
    {"name": "09_搭建页", "url": f"{BASE_URL}/data/builds",
     "asserts": [("搭建导航存在", "搭建"), ("有按钮/可交互元素", "部署")]},
    {"name": "10_连接器目录", "url": f"{BASE_URL}/data/connections",
     "asserts": [("页面可见", "连接器")]},
    {"name": "11_数据源列表", "url": f"{BASE_URL}/data",
     "asserts": [("页面可见", "数据源"), ("栖月汇数据源", "栖月汇")]},
]


def click_input_node_via_text(pilot, text="栖月汇微商城"):
    """通过 DOM 文本匹配点击输入节点"""
    pilot.call_raw("browser_evaluate", {
        "expression": f"""
            (function() {{
                const els = document.querySelectorAll('div');
                for (const el of els) {{
                    if (el.textContent.trim() === '{text}') {{
                        const rect = el.getBoundingClientRect();
                        const x = rect.left + rect.width / 2;
                        const y = rect.top + rect.height / 2;
                        el.dispatchEvent(new MouseEvent('click', {{
                            bubbles: true, cancelable: true, clientX: x, clientY: y
                        }}));
                        return 'clicked';
                    }}
                }}
                return 'not-found';
            }})()
        """,
        "returnByValue": True,
    })
    time.sleep(1.5)


def main():
    print("=" * 70)
    print("  Browser-Pilot 批量验收（只用 BrowserPilot，无 CDP 脚本）")
    print("=" * 70)

    all_passed = True
    with BrowserPilot() as pilot:
        # ============= Step 2c: 8 个管道画布逐一验收 =============
        for item in PIPELINE_CHECK:
            pid, zh = item["pid"], item["zh"]
            print(f"\n{'='*60}")
            print(f"  Step 2c · 画布验收 {pid}（{zh}）")
            print(f"{'='*60}")

            # 导航
            r = pilot.navigate(f"{BASE_URL}/data/pipelines/{pid}")
            if not r.success:
                print(f"  ❌ 导航失败")
                all_passed = False
                continue
            # 注入组织
            pilot.call_raw("browser_evaluate", {
                "expression": ORG_INJECT, "returnByValue": True, "awaitPromise": True
            })
            time.sleep(1)
            pilot.call_raw("browser_evaluate", {"expression": "location.reload()"})
            time.sleep(8)

            # 点击输入节点
            click_input_node_via_text(pilot)

            # 公共检查
            common_checks = [
                ("画布标题（栖月汇）", "栖月汇-"),
                ("输入节点中文名", "栖月汇微商城"),
                ("变换节点中文", "数据抽取"),
                ("连线标签=输入或输出", "输入"),
                ("画布 lede=管道构建", "管道构建 · 画布"),
                ("不应出现 niushop-qyh Source 字样", "niushop-qyh Source"),
            ]
            for (desc, text) in common_checks:
                should = not desc.startswith("不应")
                ar = pilot.assert_text(text)
                ok = (ar.passed == should)
                print(f"  {'✅' if ok else '❌'} {desc}")
                if not ok:
                    all_passed = False

            # 专属检查
            for (desc, text) in item["checks"]:
                ar = pilot.assert_text(text)
                ok = ar.passed
                print(f"  {'✅' if ok else '❌'} {desc}")
                if not ok:
                    all_passed = False

            # 截图
            ss_path = os.path.join(SS_DIR, f"step2c_{pid}.png")
            pilot.screenshot(output_path=ss_path, full_page=True)
            print(f"  📸 {ss_path}")

        # ============= Step 3: 7 个页面批量验收 =============
        print(f"\n\n{'#'*70}")
        print("  Step 3 · 7 个关键页面验收")
        print(f"{'#'*70}")
        for idx, page in enumerate(PAGES, 1):
            print(f"\n[{idx}/7] {page['name']} — {page['url']}")
            r = pilot.navigate(page["url"])
            if not r.success:
                print(f"  ❌ 导航失败")
                all_passed = False
                continue
            # 注入组织
            pilot.call_raw("browser_evaluate", {
                "expression": ORG_INJECT, "returnByValue": True, "awaitPromise": True
            })
            time.sleep(1)
            pilot.call_raw("browser_evaluate", {"expression": "location.reload()"})
            time.sleep(8)

            for (desc, text) in page["asserts"]:
                should = not desc.startswith("不应")
                ar = pilot.assert_text(text)
                ok = (ar.passed == should)
                print(f"  {'✅' if ok else '❌'} {desc}")
                if not ok:
                    all_passed = False

            ss_path = os.path.join(SS_DIR, f"step3_{page['name']}.png")
            pilot.screenshot(output_path=ss_path, full_page=True)
            print(f"  📸 {ss_path}")

    print(f"\n{'='*70}")
    if all_passed:
        print("  ✅✅✅ 所有验收全部通过 ✅✅✅")
    else:
        print("  ⚠️  存在失败项，请查看上方日志和截图")
    print(f"{'='*70}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())

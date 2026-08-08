#!/usr/bin/env python3
"""验证页面不再显示技术型ID（#build-xxx, raw_orders），改为业务语义中文文案。"""
import sys, os, time, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
os.environ.setdefault("WSS_URL", "ws://127.0.0.1:9001/ws")
SCREENSHOTS_DIR = pathlib.Path(__file__).parent / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

from engine_adapter import BrowserPilot


def get_body(pilot) -> str:
    try:
        r = pilot.call_raw("browser_snapshot", {"diff": False})
    except Exception as e:
        return f"[err snapshot {e}]"
    parts = []
    for item in r.get("result", {}).get("content", []) or []:
        parts.append(item.get("name") or "")
        parts.append(item.get("text") or "")
        parts.append(item.get("aria_label") or "")
    return "\n".join(parts)


def main() -> int:
    urls = [
        ("计划编辑器", "http://127.0.0.1:5173/data/schedules", "09_schedules_trigger_labels.png"),
        ("数据血缘", "http://127.0.0.1:5173/data/lineage", "10_lineage_chinese_labels.png"),
        ("数据质量", "http://127.0.0.1:5173/data/health", "11_health_chinese_targets.png"),
        ("审计日志", "http://127.0.0.1:5173/operations/audit", "12_audit_chinese_resource_ids.png"),
    ]
    all_ok = True
    try:
        with BrowserPilot() as pilot:
            for (title, url, fname) in urls:
                print(f"\n=== {title} ===")
                try:
                    r = pilot.navigate(url)
                    if not getattr(r, "success", True):
                        print(f"  ❌ navigate 失败: {getattr(r, 'error', r)}")
                        all_ok = False
                        continue
                except Exception as e:
                    print(f"  ❌ navigate 异常: {e}")
                    all_ok = False
                    continue
                time.sleep(3.5)
                try:
                    shot = pilot.screenshot(str(SCREENSHOTS_DIR / fname))
                    print(f"  📸 截图保存: {fname}")
                except Exception as e:
                    print(f"  ⚠️  截图失败: {e}")
                body = get_body(pilot)

                checks = []
                if "schedule" in url:
                    checks = [
                        ("❌ 残留 '#build-' 技术ID", "#build-" not in body, "上游触发标签含 #build-8842 未替换"),
                        ("❌ 残留 'raw_orders' 技术ID", "raw_orders" not in body, "上游触发标签含 raw_orders 未替换"),
                        ("✅ '栖月汇-订单' 出现", "栖月汇-订单" in body, "缺少 栖月汇-订单 中文标签"),
                        ("✅ '栖月汇-发货' 出现", "栖月汇-发货" in body, "缺少 栖月汇-发货 中文标签"),
                        ("✅ '栖月汇微商城' 出现", "栖月汇微商城" in body, "缺少栖月汇微商城显示名"),
                    ]
                elif "lineage" in url:
                    bad_terms = ["raw_orders", "raw_products", "clean_pipeline", "curated_orders", "dim_products", "OrderType", "SalesFunnel"]
                    checks = [
                        ("❌ 残留英文技术节点名", not any(x in body for x in bad_terms),
                         f"血缘节点含英文技术名: {[x for x in bad_terms if x in body]}"),
                        ("✅ '栖月汇-订单' 出现", "栖月汇-订单" in body, "缺少栖月汇中文业务名"),
                        ("✅ '销售漏斗 分析模型' 或 '销售漏斗'", "销售漏斗" in body, "缺少销售漏斗中文"),
                    ]
                elif "health" in url:
                    bad_terms = ["curated_orders", "curated_customers", "sync_orders", "curated_addresses", "dim_skus"]
                    checks = [
                        ("❌ 残留英文目标名", not any(x in body for x in bad_terms),
                         f"规则 target 列含英文技术名: {[x for x in bad_terms if x in body]}"),
                        ("✅ '栖月汇-订单' 作为目标出现", "栖月汇-订单" in body, "缺少栖月汇-订单目标"),
                        ("✅ '栖月汇-会员' 作为目标出现", "栖月汇-会员" in body, "缺少栖月汇-会员目标"),
                    ]
                elif "audit" in url:
                    bad_terms = [
                        "pipe-orders-001", "model-gpt-4o", "sched-old-batch",
                        "ds-orders-curated", "type-customer",
                    ]
                    checks = [
                        ("❌ 残留技术ID (pipe/model/sched/ds/type)",
                         not any(x in body for x in bad_terms),
                         f"审计 resourceId 含技术型ID: {[x for x in bad_terms if x in body]}"),
                        ("✅ 'P05-栖月汇-订单' 出现", "P05-栖月汇-订单" in body, "缺少 P05 管道中文ID"),
                        ("✅ '对象类型-会员' 出现", "对象类型-会员" in body, "缺少对象类型业务名"),
                    ]

                for label, cond, reason in checks:
                    ok = bool(cond)
                    print(f"  {'✅' if ok else '❌'} {label}{'' if ok else '  → ' + reason}")
                    if not ok:
                        all_ok = False

        print("\n" + ("=" * 60))
        if all_ok:
            print("🎉 全部断言通过：业务语义中文文案生效")
        else:
            print("⚠️  存在失败断言，见上方 ❌ 标记")
        return 0 if all_ok else 1

    except Exception as e:
        print(f"[FATAL] {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        return 3


if __name__ == "__main__":
    sys.exit(main())

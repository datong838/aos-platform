#!/usr/bin/env python3
"""用 browser_snapshot + 直接call_raw，验证页面内容。"""
import sys, os, time, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).parent))
os.environ.setdefault("WSS_URL", "ws://127.0.0.1:9001/ws")
from engine_adapter import BrowserPilot

def main() -> int:
    pages = [
        ("计划编辑器", "http://127.0.0.1:5173/data/schedules"),
        ("审计日志", "http://127.0.0.1:5173/operations/audit"),
        ("搭建任务", "http://127.0.0.1:5173/data/builds/847"),
    ]
    with BrowserPilot() as pilot:
        for name, url in pages:
            print(f"\n{'='*60}\n  {name}\n{'='*60}")
            pilot.navigate(url)
            time.sleep(3.2)
            r = pilot.call_raw("browser_snapshot", {"diff": False})
            body = json.dumps(r, ensure_ascii=False)

            if name == "计划编辑器":
                bad = ["raw_orders", "#build-", "prod-mysql-orders"]
                good = ["栖月汇-订单", "栖月汇-发货", "栖月汇微商城"]
            elif name == "审计日志":
                bad = ["pipe-orders-001", "model-gpt-4o", "spoke-prod-", "sched-old-batch", "ds-orders-curated", "type-customer"]
                good = ["P05-栖月汇-订单", "对象类型-会员", "智能路由模型", "栖月汇-订单 数据集", "栖月汇 旧版批量同步计划"]
            else:
                bad = ["Build #", "worker-3"]
                good = ["栖月汇-会员（P08）· 搭建任务", "阶段 1/4：数据源连接探测",
                        "阶段 2/4：字段映射与 PII 脱敏加载", "阶段 3/4：真实数据抽取", "阶段 4/4：PostgreSQL"]
            ok = True
            for b in bad:
                exists = b in body
                mark = "❌残留" if exists else "✅消失"
                if exists: ok = False
                print(f"  {mark} 技术ID: {b}")
            for g in good:
                exists = g in body
                mark = "✅出现" if exists else "❌缺失"
                if not exists: ok = False
                print(f"  {mark} 中文文案: {g}")
            print(f"  → 本页: {'🎉 PASS' if ok else '⚠️  FAIL'}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

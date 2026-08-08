#!/usr/bin/env python3
"""直接提取页面body文本 → 验证中文业务语义文案 确实在页面中。"""
import sys, os, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
os.environ.setdefault("WSS_URL", "ws://127.0.0.1:9001/ws")
from engine_adapter import BrowserPilot

def extract(pilot):
    try:
        r = pilot.call_raw("browser_evaluate", {
            "script": "() => { const s = new Set(); document.querySelectorAll('*').forEach(n => { if (n.childNodes.length === 1 && n.childNodes[0].nodeType === 3) { const t = n.textContent.trim(); if (t) s.add(t); } }); const a = [...s].join('\\n'); return a.slice(0, 15000); }"
        })
        if isinstance(r, dict):
            if isinstance(r.get("result"), str):
                return r["result"]
            return r.get("result", {}).get("value", r.get("content", str(r)))
        return str(r)
    except Exception as e:
        return f"[err {e}]"

def main() -> int:
    pages = [
        ("计划编辑器(上游触发Tab)", "http://127.0.0.1:5173/data/schedules",
         "document.querySelectorAll('button, a, div[role=tab]').forEach(e=>{if((e.innerText||'').includes('上游触发'))e.click()}); window.scrollBy(0,180);"),
        ("审计日志", "http://127.0.0.1:5173/operations/audit", ""),
        ("搭建任务详情", "http://127.0.0.1:5173/data/builds/847", ""),
    ]
    with BrowserPilot() as pilot:
        for (name, url, extra_js) in pages:
            print(f"\n{'='*60}\n  {name}\n{'='*60}")
            pilot.navigate(url)
            time.sleep(3.2)
            if extra_js:
                pilot.call_raw("browser_evaluate", {"script": extra_js})
                time.sleep(1.0)
            text = extract(pilot)
            s_body = str(text)
            print(f"[BODY SAMPLE]\n{s_body[:1800]}\n")

            if "计划" in name:
                hits = {t: (t in s_body) for t in ["raw_orders", "#build-", "栖月汇-订单", "栖月汇-发货", "栖月汇微商城", "prod-mysql-orders"]}
            elif "审计" in name:
                hits = {t: (t in s_body) for t in ["pipe-orders-001", "model-gpt-4o", "spoke-prod", "sched-old-batch", "ds-orders-curated", "type-customer",
                                                 "P05-栖月汇-订单", "对象类型-会员", "智能路由模型", "栖月汇-订单 数据集", "运行节点-美东-生产", "栖月汇 旧版批量同步计划"]}
            else:
                hits = {t: (t in s_body) for t in ["Build #", "build-847", "worker-3",
                                                 "栖月汇-会员（P08）· 搭建任务", "栖月汇-会员（P08）· 搭建任务启动", "执行节点-3",
                                                 "阶段 1/4：数据源连接探测", "阶段 2/4：字段映射与 PII 脱敏加载", "阶段 3/4：真实数据抽取", "阶段 4/4：PostgreSQL"]}
            for k, v in hits.items():
                print(f"  {'✅' if v else '❌'}  {'(技术ID必须消失)' if k in ['raw_orders','#build-','pipe-orders-001','model-gpt-4o','spoke-prod','sched-old-batch','ds-orders-curated','type-customer','Build #','worker-3','prod-mysql-orders'] else '(中文必须出现)'} : {k}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

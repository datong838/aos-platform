"""d4_phase_c_c4_setup.py — D4 Phase C · C4 SyncTask 批量创建 + 验证

1. 创建内存 source（如果不存在）
2. 批量创建 12 条 SyncTask（P01-P12）
3. 验证列表 API 可见（租户隔离）
4. 触发一次同步并验证 SyncRun 历史
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
from typing import Any

os.environ["no_proxy"] = "*"
os.environ["NO_PROXY"] = "*"

BASE = "http://127.0.0.1:8080"
AUTH_HEADERS = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "org-org",
    "X-Project-Id": "dev-project",
    "Content-Type": "application/json",
}

# P01-P12 管道定义
PIPELINES: list[dict[str, str]] = [
    {"p": "P01", "name": "P01-店铺",       "tbl": "ns_site",                    "ot": "Shop"},
    {"p": "P02", "name": "P02-商品",       "tbl": "ns_goods",                   "ot": "Product"},
    {"p": "P03", "name": "P03-SKU",        "tbl": "ns_goods_sku",               "ot": "ProductSku"},
    {"p": "P04", "name": "P04-类目",       "tbl": "ns_goods_category",          "ot": "Category"},
    {"p": "P05", "name": "P05-订单",       "tbl": "ns_order",                   "ot": "Order"},
    {"p": "P06", "name": "P06-订单明细",   "tbl": "ns_order_goods",             "ot": "OrderLine"},
    {"p": "P07", "name": "P07-包裹",       "tbl": "ns_express_delivery_package","ot": "Shipment"},
    {"p": "P08", "name": "P08-会员",       "tbl": "ns_member",                  "ot": "CustomerLite"},
    {"p": "P09", "name": "P09-小程序",     "tbl": "ns_weapp",                   "ot": "Weapp"},
    {"p": "P10", "name": "P10-系统配置",   "tbl": "ns_config",                  "ot": "SystemConfig"},
    {"p": "P11", "name": "P11-商品评价",   "tbl": "ns_goods_evaluate",          "ot": "ProductReview"},
    {"p": "P12", "name": "P12-支付",       "tbl": "ns_pay",                     "ot": "Payment"},
]


def _req(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=AUTH_HEADERS, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    print("=" * 60)
    print("C4 · SyncTask 批量创建 + 验证")
    print("=" * 60)

    # Step 1: 创建内存 source
    print("\n[Step 1] 创建内存 source...")
    try:
        src = _req("POST", "/api/datasource/sources", {
            "name": "栖月汇Niushop库",
            "source_type": "database",
            "config": {"connector_type": "niushop-mysql"},
            "status": "active",
            "owner": "qiyuehui",
        })
        src_id = src["id"]
        print(f"  source_id={src_id} name={src['name']}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ❌ 创建 source 失败: HTTP {e.code} {body[:200]}")
        return 1

    # Step 2: 批量创建 12 条 SyncTask
    print("\n[Step 2] 批量创建 12 条 SyncTask (P01-P12)...")
    created: list[dict[str, Any]] = []
    for pdef in PIPELINES:
        ot_lower = pdef["ot"].lower()
        pipeline_id = f"{pdef['p']}-{ot_lower}-qyh"
        body = {
            "name": pdef["name"],
            "source_id": src_id,
            "target_dataset": f"ot_{pdef['ot']}",
            "mode": "full",
            "cron_expr": "0 * * * *",
            "status": "active",
            "config": {
                "pipeline_id": pipeline_id,
                "source_table": pdef["tbl"],
                "target_ot": pdef["ot"],
            },
        }
        try:
            st = _req("POST", "/api/datasource/syncs", body)
            created.append(st)
            print(f"  {pdef['p']} {pdef['name']} → sync_id={st['id']} status={st['status']}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"  ❌ {pdef['p']} 创建失败: HTTP {e.code} {body[:200]}")
        except Exception as e:
            print(f"  ❌ {pdef['p']} 创建失败: {e}")

    print(f"\n  创建成功: {len(created)}/12")

    # Step 3: 验证列表 API 可见（租户隔离）
    print("\n[Step 3] 验证列表 API (租户隔离 org-org/dev-project)...")
    try:
        lst = _req("GET", "/api/datasource/syncs?page=1&page_size=50")
        items = lst.get("items", [])
        total = lst.get("total", 0)
        print(f"  列表返回: total={total}, items={len(items)}")
        for it in items[:12]:
            cfg = it.get("config", {})
            print(f"    {it['name']} | sync_id={it['id']} | pipeline={cfg.get('pipeline_id','?')} | status={it['status']}")
        visible_ok = total >= 12
        print(f"  {'✅ PASS' if visible_ok else '❌ FAIL'} 12 条 SyncTask 可见")
    except Exception as e:
        print(f"  ❌ 列表查询失败: {e}")
        visible_ok = False

    # Step 4: 触发一次同步 + 验证 SyncRun 历史
    print("\n[Step 4] 触发一次同步 + 验证 SyncRun 历史...")
    if not created:
        print("  ⚠️ 无可触发的 SyncTask，跳过")
        run_ok = False
    else:
        target = created[0]  # 用 P01 测试
        print(f"  触发 {target['name']} (sync_id={target['id']})...")
        try:
            run = _req("POST", f"/api/datasource/syncs/{target['id']}/run")
            print(f"  SyncRun: id={run.get('id','?')} status={run.get('status','?')} rows={run.get('rows_synced','?')}")
            # 查运行历史
            time.sleep(1)
            runs = _req("GET", f"/api/datasource/syncs/{target['id']}/runs")
            run_items = runs.get("items", [])
            print(f"  运行历史: count={len(run_items)}")
            for r in run_items[:3]:
                print(f"    run_id={r['id']} status={r['status']} duration={r.get('duration_ms','?')}ms rows={r.get('rows_synced','?')}")
            run_ok = len(run_items) >= 1
            print(f"  {'✅ PASS' if run_ok else '❌ FAIL'} SyncRun 历史可见")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"  ❌ 触发同步失败: HTTP {e.code} {body[:300]}")
            run_ok = False
        except Exception as e:
            print(f"  ❌ 触发同步失败: {e}")
            run_ok = False

    # Step 5: 越租户隔离验证
    print("\n[Step 5] 越租户隔离验证 (其他租户应看不到 org-org 的 SyncTask)...")
    other_headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "other-org",
        "X-Project-Id": "other-project",
        "Content-Type": "application/json",
    }
    try:
        url = f"{BASE}/api/datasource/syncs?page=1&page_size=50"
        req = urllib.request.Request(url, headers=other_headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            other_lst = json.loads(resp.read().decode("utf-8"))
        other_total = other_lst.get("total", 0)
        other_items = other_lst.get("items", [])
        print(f"  other-org 租户: total={other_total} items={len(other_items)}")
        iso_ok = other_total == 0
        print(f"  {'✅ PASS' if iso_ok else '❌ FAIL'} 越租户隔离（其他租户看不到 org-org 的 SyncTask）")
    except Exception as e:
        print(f"  ❌ 越租户验证失败: {e}")
        iso_ok = False

    # 汇总
    print("\n" + "=" * 60)
    print("C4 验收汇总")
    print("=" * 60)
    print(f"  12 SyncTask 创建: {'✅' if len(created) >= 12 else '❌'} {len(created)}/12")
    print(f"  列表 API 可见:    {'✅' if visible_ok else '❌'}")
    print(f"  SyncRun 历史:     {'✅' if run_ok else '❌'}")
    print(f"  越租户隔离:       {'✅' if iso_ok else '❌'}")
    all_ok = len(created) >= 12 and visible_ok and run_ok and iso_ok
    print(f"\n  C4 结果: {'✅ PASS' if all_ok else '❌ FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

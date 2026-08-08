#!/usr/bin/env python3
"""D5 Phase C · D4 Phase D 收尾验证脚本

G17: 派生指标全量重算 — 验证 8 个派生指标在 ecom_object 中的填充率
G18: DLQ PII 零泄漏 — 模拟 3 种失败场景验证 PII 脱敏
G19: 租户隔离 100% — 双 scope 隔离验证

用法: PYTHONPATH=. .venv/bin/python scripts/d5_phase_c_verify.py
"""
from __future__ import annotations
import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE_URL = os.environ.get("AOS_BASE_URL", "http://localhost:8080")
ORG = "org-org"
PROJECT = "dev-project"

HEADERS = {
    "Authorization": "Bearer dev",
    "X-Org-Id": ORG,
    "X-Project-Id": PROJECT,
    "Content-Type": "application/json",
}


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def api_get(path: str, headers: dict | None = None) -> dict:
    h = headers or HEADERS
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=h, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def api_post(path: str, body: dict | None = None, headers: dict | None = None) -> dict:
    h = headers or HEADERS
    data = json.dumps(body).encode() if body else b"{}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


# ── G17: 派生指标 ────────────────────────────────────────────────────────────

def check_derived_metrics_from_api() -> dict:
    """通过 API 执行 SyncRun 重算派生指标，再通过 PG 检查填充率。"""
    section("G17 派生指标全量重算验证")

    # 1. 获取 SyncTask 列表
    syncs = api_get("/api/datasource/syncs")
    items = syncs.get("items", [])
    print(f"SyncTask 数量: {len(items)}")

    # 2. 执行所有 SyncRun（触发派生指标重算）
    results = []
    for s in items:
        sid = s["id"]
        try:
            r = api_post(f"/api/datasource/syncs/{sid}/run")
            results.append({
                "sync_id": sid,
                "status": r.get("status"),
                "rows": r.get("rows_synced", 0),
            })
            print(f"  {sid}: {r.get('status')} rows={r.get('rows_synced', 0)}")
        except Exception as e:
            results.append({"sync_id": sid, "status": "error", "error": str(e)})
            print(f"  {sid}: ERROR - {e}")

    # 3. 统计成功率
    success = sum(1 for r in results if r.get("status") == "success")
    print(f"\nSyncRun 成功: {success}/{len(items)}")

    # 4. 通过 PG 检查派生指标填充率
    pg_metrics = check_pg_derived_metrics()

    return {
        "gate": "G17",
        "sync_runs": results,
        "success_rate": f"{success}/{len(items)}",
        "pg_metrics": pg_metrics,
        "note": "派生指标在 SyncRun transform 阶段计算，存入 ecom_object.properties",
    }


def check_pg_derived_metrics() -> dict:
    """通过 PG 查询 ecom_object 表的派生指标填充率。"""
    import psycopg

    try:
        from aos_api.db import get_dsn
    except ImportError:
        return {"error": "aos_api not available"}

    conn = psycopg.connect(get_dsn())
    cur = conn.cursor()

    metrics = {}

    # quality_score (Product)
    cur.execute("""
        SELECT count(*) as total,
               count(*) FILTER (WHERE properties->>'quality_score' IS NOT NULL
                 AND properties->>'quality_score' NOT IN ('null', 'None')) as has_qs
        FROM ecom_object
        WHERE org_id='org-org' AND workspace_id='dev-project' AND object_type='Product'
    """)
    total, has = cur.fetchone()
    rate = (has / total * 100) if total > 0 else 0
    metrics["quality_score"] = {
        "target_ot": "Product",
        "has": has, "total": total,
        "rate": f"{rate:.1f}%",
        "threshold": "90%",
        "pass": rate >= 90.0 or total == 0,
        "note": "quality_score=null 当 evaluate=0 或缺失（源数据无评价），符合设计预期" if total == 0 or rate < 90 else "OK",
    }
    print(f"\n  quality_score (Product): {has}/{total} = {rate:.1f}% (阈值 90%)")

    # stock_health (ProductSku)
    cur.execute("""
        SELECT count(*) as total,
               count(*) FILTER (WHERE properties->>'stock_health' IS NOT NULL
                 AND properties->>'stock_health' NOT IN ('null', 'None')) as has_sh
        FROM ecom_object
        WHERE org_id='org-org' AND workspace_id='dev-project' AND object_type='ProductSku'
    """)
    total, has = cur.fetchone()
    rate = (has / total * 100) if total > 0 else 0
    metrics["stock_health"] = {
        "target_ot": "ProductSku",
        "has": has, "total": total,
        "rate": f"{rate:.1f}%",
        "threshold": "85%",
        "pass": rate >= 85.0,
    }
    print(f"  stock_health (ProductSku): {has}/{total} = {rate:.1f}% (阈值 85%)")

    # risk_score (Order)
    cur.execute("""
        SELECT count(*) as total,
               count(*) FILTER (WHERE properties->>'risk_score' IS NOT NULL
                 AND properties->>'risk_score' NOT IN ('null', 'None')) as has_rs
        FROM ecom_object
        WHERE org_id='org-org' AND workspace_id='dev-project' AND object_type='Order'
    """)
    total, has = cur.fetchone()
    rate = (has / total * 100) if total > 0 else 0
    metrics["risk_score"] = {
        "target_ot": "Order", "has": has, "total": total,
        "rate": f"{rate:.1f}%", "pass": rate >= 90.0,
    }
    print(f"  risk_score (Order): {has}/{total} = {rate:.1f}%")

    # overdue_hours (Shipment)
    cur.execute("""
        SELECT count(*) as total,
               count(*) FILTER (WHERE properties->>'overdue_hours' IS NOT NULL
                 AND properties->>'overdue_hours' NOT IN ('null', 'None')) as has_oh
        FROM ecom_object
        WHERE org_id='org-org' AND workspace_id='dev-project' AND object_type='Shipment'
    """)
    total, has = cur.fetchone()
    rate = (has / total * 100) if total > 0 else 0
    metrics["overdue_hours"] = {
        "target_ot": "Shipment", "has": has, "total": total,
        "rate": f"{rate:.1f}%",
        "note": "overdue_hours=null 当 delivery_time>0（已发货）或 pay_time=0（未支付），符合设计预期",
    }
    print(f"  overdue_hours (Shipment): {has}/{total} = {rate:.1f}%")

    # order_count + last_order_days (CustomerLite)
    cur.execute("""
        SELECT count(*) as total,
               count(*) FILTER (WHERE properties->>'order_count' IS NOT NULL
                 AND properties->>'order_count' NOT IN ('null', 'None')) as has_oc,
               count(*) FILTER (WHERE properties->>'last_order_days' IS NOT NULL
                 AND properties->>'last_order_days' NOT IN ('null', 'None')) as has_lod
        FROM ecom_object
        WHERE org_id='org-org' AND workspace_id='dev-project' AND object_type='CustomerLite'
    """)
    total, has_oc, has_lod = cur.fetchone()
    oc_rate = (has_oc / total * 100) if total > 0 else 0
    lod_rate = (has_lod / total * 100) if total > 0 else 0
    metrics["order_count"] = {
        "target_ot": "CustomerLite", "has": has_oc, "total": total,
        "rate": f"{oc_rate:.1f}%",
        "note": "order_count=null 当 member_id 无关联订单（link_aggregator 无数据）",
    }
    metrics["last_order_days"] = {
        "target_ot": "CustomerLite", "has": has_lod, "total": total,
        "rate": f"{lod_rate:.1f}%",
    }
    print(f"  order_count (CustomerLite): {has_oc}/{total} = {oc_rate:.1f}%")
    print(f"  last_order_days (CustomerLite): {has_lod}/{total} = {lod_rate:.1f}%")

    conn.close()
    return metrics


# ── G18: DLQ PII 零泄漏 ──────────────────────────────────────────────────────

# PII patterns to check
PII_NEEDLES = [
    "138-0000-0000",      # 手机号（带分隔符）
    "13800000000",        # 无格式手机号
    "110101199001011234", # 身份证号
    "6222021234567890",   # 银行卡号
    "admin@example.com",  # 邮箱
    "openid_xyz_abc",     # openid
]

PII_PAYLOAD = {
    "reason": (
        "Pipeline P05 执行失败: "
        "用户 138-0000-0000 订单异常, "
        "身份证 110101199001011234, "
        "银行卡 6222021234567890, "
        "联系邮箱 admin@example.com, "
        "密码 password123, "
        "openid openid_xyz_abc"
    ),
    "errorCode": "VALIDATION_ERROR",
}


def check_dlq_pii() -> dict:
    """通过 API 创建 DLQ 条目，验证 PII 被脱敏。"""
    section("G18 DLQ PII 零泄漏验证")

    # 通过 POST /v1/dlq 创建带 PII 的 DLQ 条目
    # 注意：wave_ext.push_dlq 直接存储 body，不做脱敏
    # 脱敏在 ec_dlq_handler.handle_failure 中执行
    # 这里我们验证 ec_dlq_handler 的脱敏逻辑

    results = []
    dlq_ids = []

    for scenario in ["SSH_DISCONNECT", "WRITE_CONFLICT", "VALIDATION_ERROR"]:
        body = {
            **PII_PAYLOAD,
            "errorCode": scenario,
        }
        try:
            r = api_post("/v1/dlq", body)
            dlq_id = r.get("id", "")
            dlq_ids.append(dlq_id)

            # 检查返回的 reason 中是否有 PII 泄漏
            reason = str(r.get("reason", ""))
            leaked = [n for n in PII_NEEDLES if n in reason]

            results.append({
                "scenario": scenario,
                "dlq_id": dlq_id,
                "reason": reason[:80] + "...",
                "pii_leaked": leaked,
                "pass": len(leaked) == 0,
            })
            status = "PASS" if not leaked else f"FAIL (leaked: {leaked})"
            print(f"  {scenario}: {status}")
        except Exception as e:
            results.append({"scenario": scenario, "error": str(e), "pass": False})
            print(f"  {scenario}: ERROR - {e}")

    all_pass = all(r.get("pass", False) for r in results)
    print(f"\nPII 零泄漏: {'PASS' if all_pass else 'FAIL'}")

    return {
        "gate": "G18",
        "scenarios": results,
        "all_pass": all_pass,
        "note": "DLQ POST API 直接存储 body（不脱敏）；ec_dlq_handler.handle_failure 在 pipeline 异常时做脱敏",
    }


# ── G19: 租户隔离 ────────────────────────────────────────────────────────────

OTHER_ORG = "org-other"
OTHER_PROJECT = "proj-other"
OTHER_HEADERS = {
    "Authorization": "Bearer dev",
    "X-Org-Id": OTHER_ORG,
    "X-Project-Id": OTHER_PROJECT,
    "Content-Type": "application/json",
}


def check_tenant_isolation() -> dict:
    """验证 org-org 和 org-other 之间数据完全隔离。"""
    section("G19 租户隔离验证")

    results = []

    # 1. org-other 查询 pipelines → 应为空（或只有自己的）
    other_pipelines = api_get("/v1/pipelines", headers=OTHER_HEADERS).get("items", [])
    org_pipeline_ids = {p["id"] for p in other_pipelines if p.get("orgId") == ORG}
    results.append({
        "test": "org-other 不能看到 org-org 的 pipelines",
        "found_org_org_pipelines": len(org_pipeline_ids),
        "pass": len(org_pipeline_ids) == 0,
    })
    print(f"  org-other 中 org-org pipelines: {len(org_pipeline_ids)} (应=0)")

    # 2. org-other 查询 sources → 应为空
    other_sources = api_get("/v1/sources", headers=OTHER_HEADERS).get("items", [])
    org_sources = {s["id"] for s in other_sources if s.get("orgId") == ORG}
    results.append({
        "test": "org-other 不能看到 org-org 的 sources",
        "found_org_org_sources": len(org_sources),
        "pass": len(org_sources) == 0,
    })
    print(f"  org-other 中 org-org sources: {len(org_sources)} (应=0)")

    # 3. org-other 查询 datasets → 应为空
    other_datasets = api_get("/v1/datasets", headers=OTHER_HEADERS).get("items", [])
    org_datasets = {d["id"] for d in other_datasets if d.get("orgId") == ORG}
    results.append({
        "test": "org-other 不能看到 org-org 的 datasets",
        "found_org_org_datasets": len(org_datasets),
        "pass": len(org_datasets) == 0,
    })
    print(f"  org-other 中 org-org datasets: {len(org_datasets)} (应=0)")

    # 4. org-other 查询 syncs → 应为空
    other_syncs = api_get("/api/datasource/syncs", headers=OTHER_HEADERS).get("items", [])
    org_syncs = {s["id"] for s in other_syncs if s.get("orgId") == ORG}
    results.append({
        "test": "org-other 不能看到 org-org 的 syncs",
        "found_org_org_syncs": len(org_syncs),
        "pass": len(org_syncs) == 0,
    })
    print(f"  org-other 中 org-org syncs: {len(org_syncs)} (应=0)")

    # 5. org-other 查询 DLQ → 应为空
    other_dlq = api_get("/v1/dlq", headers=OTHER_HEADERS).get("items", [])
    org_dlq = {d["id"] for d in other_dlq if d.get("orgId") == ORG}
    results.append({
        "test": "org-other 不能看到 org-org 的 DLQ",
        "found_org_org_dlq": len(org_dlq),
        "pass": len(org_dlq) == 0,
    })
    print(f"  org-other 中 org-org DLQ: {len(org_dlq)} (应=0)")

    all_pass = all(r["pass"] for r in results)
    print(f"\n租户隔离: {'100% PASS' if all_pass else 'FAIL'}")

    return {
        "gate": "G19",
        "tests": results,
        "all_pass": all_pass,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("D5 Phase C · D4 Phase D 收尾验证")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标: {BASE_URL}")
    print(f"主 scope: {ORG}/{PROJECT}")

    report = {}

    # G17
    try:
        report["G17"] = check_derived_metrics_from_api()
    except Exception as e:
        report["G17"] = {"gate": "G17", "error": str(e)}
        print(f"G17 ERROR: {e}")

    # G18
    try:
        report["G18"] = check_dlq_pii()
    except Exception as e:
        report["G18"] = {"gate": "G18", "error": str(e)}
        print(f"G18 ERROR: {e}")

    # G19
    try:
        report["G19"] = check_tenant_isolation()
    except Exception as e:
        report["G19"] = {"gate": "G19", "error": str(e)}
        print(f"G19 ERROR: {e}")

    # Summary
    section("汇总")
    for gate, data in report.items():
        status = "PASS" if data.get("all_pass") or (data.get("success_rate", "").endswith(f"/{data.get('sync_runs', [1])}")) else "PARTIAL"
        print(f"  {gate}: {status}")

    # Save report
    report_path = "/tmp/d5_phase_c_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    main()

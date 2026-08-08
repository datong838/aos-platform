#!/usr/bin/env python3
"""D5-E1: Run all 12 pipelines in dependency order and report results.

Usage:
  cd aos-platform/services/aos-api && python3 scripts/d5e1_run_all_pipelines.py

Prerequisites:
  - Docker PG running (aos-dev-pg:5433)
  - SSH tunnel to niushop MySQL (118.195.194.208:22 → 127.0.0.1:13306)
  - Backend API on http://localhost:8000

Pipeline execution order (dependency-aware):
  L1: P01(Shop) P04(Category) P08(CustomerLite) P10(SystemConfig)
  L2: P02(Product) P09(Weapp)
  L3: P03(ProductSku)
  L4: P05(Order) P11(ProductReview)
  L5: P06(OrderLine) P07(Shipment) P12(Payment)
"""

import json
import sys
import time
from urllib.request import Request, urlopen

API_BASE = "http://localhost:8000"
ORG_ID = "org-org"
PROJECT_ID = "dev-project"

# Execution order by dependency layer
PIPELINE_ORDER = [
    "P01-shop-qyh",
    "P04-category-qyh",
    "P08-customer-lite-qyh",
    "P10-system-config-qyh",
    "P02-product-qyh",
    "P09-weapp-qyh",
    "P03-product-sku-qyh",
    "P05-order-qyh",
    "P11-product-review-qyh",
    "P06-order-line-qyh",
    "P07-shipment-qyh",
    "P12-payment-qyh",
]


def api_request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    headers = {
        "Content-Type": "application/json",
        "X-Org-Id": ORG_ID,
        "X-Project-Id": PROJECT_ID,
        "Authorization": "Bearer dev",
    }
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def main():
    results = {}
    passed = 0
    failed = 0

    print("=" * 70)
    print("D5-E1 Pipeline Execution — 12 pipelines")
    print("=" * 70)

    for pid in PIPELINE_ORDER:
        print(f"\n▶ Executing {pid}...")
        t0 = time.time()
        result = api_request("POST", f"/v1/pipelines/{pid}/execute", {
            "execution_kind": "manual",
        })
        elapsed = time.time() - t0
        status = result.get("status", "UNKNOWN")
        error = result.get("error") or result.get("detail") or ""

        if status in ("succeeded", "SUCCESS", "completed"):
            passed += 1
            results[pid] = {"status": "PASS", "elapsed": f"{elapsed:.1f}s"}
            print(f"  ✅ PASS ({elapsed:.1f}s)")
            if result.get("evidence", {}).get("output_rows"):
                rows = result["evidence"].get("output_rows", 0)
                print(f"     rows_written={rows}")
        else:
            failed += 1
            results[pid] = {"status": "FAIL", "error": str(error)[:200]}
            print(f"  ❌ FAIL ({elapsed:.1f}s): {error[:200]}")

    print("\n" + "=" * 70)
    print(f"Results: {passed}/{len(PIPELINE_ORDER)} passed, {failed} failed")
    print("=" * 70)

    # Print summary table
    for pid, info in results.items():
        status_icon = "✅" if info["status"] == "PASS" else "❌"
        extra = info.get("error", info.get("elapsed", ""))
        print(f"  {status_icon} {pid}: {info['status']} {extra}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

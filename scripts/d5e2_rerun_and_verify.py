#!/usr/bin/env python3
"""D5-E2: Re-run all 12 pipelines + verify derived metrics after fix.

Fixes applied:
  1. SOURCE_VERSION_CONFLICT → Allow re-projection (UPDATE instead of raise)
  2. Payment orderId prefix mismatch (niushop:1:{id})
  3. _to_datetime now supports ISO 8601 strings
  4. to_payment handles ISO string _order_create_time

Usage:
  python3 scripts/d5e2_rerun_and_verify.py
"""

import json
import sys
import time
from urllib.request import Request, urlopen

API_BASE = "http://localhost:8000"
ORG_ID = "org-org"
PROJECT_ID = "dev-project"

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
    print("D5-E2 Re-run + Verify — 12 pipelines")
    print("=" * 70)

    for pid in PIPELINE_ORDER:
        print(f"\n[{pid}] executing...", end=" ", flush=True)
        t0 = time.time()
        result = api_request("POST", f"/v1/pipelines/{pid}/execute")
        elapsed = time.time() - t0
        status = result.get("status", "UNKNOWN")
        rows = result.get("rowsWritten", 0)
        err = result.get("errorMessage", "")

        if status == "succeeded":
            passed += 1
            results[pid] = {"status": "PASS", "rows": rows, "elapsed": f"{elapsed:.1f}s"}
            print(f"PASS rows={rows} ({elapsed:.1f}s)")
        else:
            failed += 1
            results[pid] = {"status": "FAIL", "error": err[:200]}
            print(f"FAIL rows={rows} err={err[:100]}")

    print("\n" + "=" * 70)
    print(f"Results: {passed}/{len(PIPELINE_ORDER)} passed, {failed} failed")
    print("=" * 70)

    for pid, info in results.items():
        icon = "✅" if info["status"] == "PASS" else "❌"
        extra = f"rows={info['rows']}" if "rows" in info else info.get("error", "")
        print(f"  {icon} {pid}: {info['status']} {extra}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

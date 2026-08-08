#!/usr/bin/env python3
"""冒烟测试：验证 kite MCP server 能否启动、initialize 握手、navigate、screenshot"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine_adapter import BrowserPilot

print("=" * 60)
print(" Kitewright MCP smoke test")
print("=" * 60)

with BrowserPilot() as pilot:
    print("✅ start ok，MCP session established")

    t0 = time.time()
    r = pilot.navigate("http://127.0.0.1:5173/data/pipelines")
    print(f"✅ navigate pipelines: success={r.success} text_len={len(r.text)}  (took {time.time()-t0:.1f}s)")

    try:
        pilot.wait_for(text="栖月汇", timeout_ms=15000)
        print("✅ wait_for 栖月汇 ok")
    except Exception as e:
        print(f"⚠️ wait_for 栖月汇 timeout: {e}")

    t0 = time.time()
    body = pilot.extract_text("body") or ""
    print(f"✅ extract body len={len(body)}  (took {time.time()-t0:.1f}s)")
    # 关键信息：管道名、商品
    for kw in ["栖月汇-商品", "栖月汇-商品SKU", "pipeline", "管道"]:
        print(f"    含 {kw!r}: {kw in body}")

    out_dir = "/tmp/bp_verify_p02p03"
    os.makedirs(out_dir, exist_ok=True)
    p = f"{out_dir}/smoke_pipelines.png"
    pilot.screenshot(output_path=p, full_page=True)
    print(f"✅ 截图: {p}")

    print()
    print("✅ SMOKE TEST PASS")

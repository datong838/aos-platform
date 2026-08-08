#!/usr/bin/env python3
"""D6 治理层三菜单浏览器验收"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine_adapter import BrowserPilot

os.makedirs("/tmp/browser-pilot", exist_ok=True)

pages = [
    {
        "name": "D6_01_数据沿袭",
        "url": "http://127.0.0.1:5173/data/lineage",
        "asserts": [
            {"text": "数据沿袭", "should_exist": True},
            {"text": "Error", "should_exist": False},
        ],
        "screenshot": "/tmp/browser-pilot/d6_lineage.png",
    },
    {
        "name": "D6_02_数据健康",
        "url": "http://127.0.0.1:5173/data/health",
        "asserts": [
            {"text": "数据健康", "should_exist": True},
            {"text": "栖月汇", "should_exist": True},
        ],
        "screenshot": "/tmp/browser-pilot/d6_health.png",
    },
    {
        "name": "D6_03_代码仓库",
        "url": "http://127.0.0.1:5173/data/code-repos",
        "asserts": [
            {"text": "代码仓库", "should_exist": True},
            {"text": "aos-platform", "should_exist": True},
        ],
        "screenshot": "/tmp/browser-pilot/d6_code_repos.png",
    },
]

results = []
with BrowserPilot() as pilot:
    for pg in pages:
        print(f"\n>>> {pg['name']}: {pg['url']}")
        result = pilot.navigate(pg["url"])
        print(f"  navigate success={result.success}")
        import time; time.sleep(3)  # wait for data load

        # Screenshot
        if pg.get("screenshot"):
            pilot.screenshot(output_path=pg["screenshot"])
            print(f"  screenshot: {pg['screenshot']}")

        # Asserts
        all_pass = True
        for a in pg.get("asserts", []):
            r = pilot.assert_text(a["text"])
            passed = r.passed == a.get("should_exist", True)
            status = "PASS" if passed else "FAIL"
            print(f"  assert '{a['text']}' exist={a.get('should_exist', True)}: {status}")
            if not passed:
                all_pass = False

        results.append({"name": pg["name"], "pass": all_pass})

print("\n" + "=" * 60)
print("D6 治理层三菜单验收结果:")
for r in results:
    print(f"  {r['name']}: {'PASS' if r['pass'] else 'FAIL'}")
print("=" * 60)

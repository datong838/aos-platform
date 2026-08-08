#!/usr/bin/env python3
"""D5-E2: Browser-based frontend verification using Browser Pilot."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins", "agents", "browser-pilot"))

from engine_adapter import BrowserPilot

FRONTEND_URL = "http://localhost:5173"
SCREENSHOT_DIR = "/tmp/d5e2-screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

PAGES = [
    {
        "name": "01_home_dashboard",
        "url": f"{FRONTEND_URL}/",
        "asserts": [
            {"text": "AOS", "should_exist": True},
            {"text": "Error", "should_exist": False},
        ],
        "screenshot": True,
    },
    {
        "name": "02_pipeline_list",
        "url": f"{FRONTEND_URL}/data/pipelines",
        "asserts": [
            {"text": "管道", "should_exist": True},
        ],
        "screenshot": True,
    },
    {
        "name": "03_data_connections",
        "url": f"{FRONTEND_URL}/data/connections",
        "asserts": [],
        "screenshot": True,
    },
    {
        "name": "04_ontology_objects",
        "url": f"{FRONTEND_URL}/ontology",
        "asserts": [],
        "screenshot": True,
    },
    {
        "name": "05_apollo_cases",
        "url": f"{FRONTEND_URL}/apollo/cases",
        "asserts": [],
        "screenshot": True,
    },
    {
        "name": "06_aip_logic",
        "url": f"{FRONTEND_URL}/aip/logic",
        "asserts": [],
        "screenshot": True,
    },
]


def main():
    print("=" * 70)
    print("D5-E2 Browser Verification — 6 key pages")
    print("=" * 70)

    with BrowserPilot() as pilot:
        results = pilot.verify_pages(PAGES, screenshot_dir=SCREENSHOT_DIR)

    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r.get("passed"))
    failed = len(results) - passed
    print(f"Results: {passed}/{len(results)} pages passed")
    print("=" * 70)

    for r in results:
        name = r.get("name", "?")
        status = "✅ PASS" if r.get("passed") else "❌ FAIL"
        print(f"  {status} {name}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

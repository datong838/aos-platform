#!/usr/bin/env python3
"""Deterministically reconcile the committed AR2-7E browser evidence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
OUTPUT = EVIDENCE / "ar2-7e-cumulative-closure.json"
AUTHORITY = "AOS-000572"
VIEWPORTS = {(1280, 720), (1440, 900), (1920, 1080)}

RICH_PAGES = (
    "task-cockpit",
    "content-campaign",
    "operations",
    "creator-growth",
    "media-studio",
    "analyst",
    "price-governance",
    "customer",
)

PRODUCT_FILES = (
    "apps/web/src/components/workshop/TaskCockpitPage.tsx",
    "apps/web/src/components/workshop/ContentCampaignPage.tsx",
    "apps/web/src/components/workshop/OperationsPage.tsx",
    "apps/web/src/components/workshop/CreatorGrowthPage.tsx",
    "apps/web/src/components/workshop/MediaStudioPage.tsx",
    "apps/web/src/components/workshop/AnalystPage.tsx",
    "apps/web/src/components/workshop/BusinessInvestigationTab.tsx",
    "apps/web/src/components/workshop/PriceGovernancePage.tsx",
    "apps/web/src/components/workshop/CustomerPage.tsx",
)


def load(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def git_tracked(path: Path) -> bool:
    relative = path.relative_to(REPO)
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", str(relative)],
        cwd=REPO,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def viewport_tuple(result: dict) -> tuple[int, int]:
    viewport = result["viewport"]
    if isinstance(viewport, str):
        width, height = viewport.lower().split("x", 1)
        return int(width), int(height)
    return int(viewport["width"]), int(viewport["height"])


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def authority_revision(value: object) -> str:
    return str(value).split(" / ", 1)[0]


def main() -> int:
    failures: list[str] = []
    checked_files: list[str] = []
    summary: dict[str, object] = {}

    entry_name = "ar2-7e-eight-workbench-browser.json"
    entry = load(entry_name)
    entry_counts = entry["counts"]
    require(entry["result"] == "PASS", "entry matrix result is not PASS", failures)
    require(authority_revision(entry.get("authority")) == AUTHORITY, "entry matrix authority drift", failures)
    require(entry_counts["positivePassed"] == entry_counts["positiveTotal"] == 24, "entry positive matrix is not 24/24", failures)
    require(entry_counts["negativePassed"] == entry_counts["negativeTotal"] == 13, "entry negative matrix is not 13/13", failures)
    for key in ("nonGetWorkshopRequests", "pageErrors", "consoleErrors"):
        require(entry_counts[key] == 0, f"entry matrix {key} is non-zero", failures)
    require(entry_counts["stoppedEarly"] is False, "entry matrix stopped early", failures)
    checked_files.append(entry_name)
    summary["entryMatrix"] = {"passed": 37, "total": 37}

    ready_name = "ar2-7e-eight-workbench-ready-browser.json"
    ready = load(ready_name)
    ready_counts = ready["counts"]
    require(ready["result"] == "PASS", "ready matrix result is not PASS", failures)
    require(authority_revision(ready.get("authority")) == AUTHORITY, "ready matrix authority drift", failures)
    require(ready_counts["passed"] == ready_counts["total"] == 24, "ready matrix is not 24/24", failures)
    require(ready_counts["screenshots"] == 24, "ready matrix screenshot count is not 24", failures)
    for key in ("nonGetWorkshopRequests", "unknownGets", "tenantHeaderDrift", "http5xx", "pageErrors", "consoleErrors", "horizontalOverflow"):
        require(ready_counts[key] == 0, f"ready matrix {key} is non-zero", failures)
    require(ready_counts["stoppedEarly"] is False, "ready matrix stopped early", failures)
    checked_files.append(ready_name)
    summary["readyMatrix"] = {"passed": 24, "total": 24, "screenshots": 24}

    rich_summary: dict[str, object] = {}
    for page in RICH_PAGES:
        names = (
            f"ar2-7e-{page}-rich-browser-plan.md",
            f"ar2-7e-{page}-rich-browser.mjs",
            f"ar2-7e-{page}-rich-browser.json",
            f"ar2-7e-{page}-rich-browser-verification.md",
        )
        data = load(names[2])
        counts = data["counts"]
        results = data["results"]
        require(data["result"] == "PASS", f"{page} result is not PASS", failures)
        require(authority_revision(data.get("authority")) == AUTHORITY, f"{page} authority drift", failures)
        require(counts["passed"] == counts["total"] == 3, f"{page} is not 3/3", failures)
        require(len(results) == 3, f"{page} does not contain three viewport results", failures)
        require({viewport_tuple(item) for item in results} == VIEWPORTS, f"{page} viewport set drift", failures)
        require(all(item.get("result") == "PASS" and not item.get("failures") for item in results), f"{page} contains a failing viewport", failures)
        for key in ("otherWrites", "forbiddenWrites", "prohibitedWrites", "unknownGets", "pageErrors", "consoleErrors", "workshopWrites", "preflightPosts"):
            if key in counts:
                require(counts[key] == 0, f"{page} {key} is non-zero", failures)
        require(counts["stoppedEarly"] is False, f"{page} stopped early", failures)
        zero_effects = data.get("zeroEffects", {})
        for key, value in zero_effects.items():
            require(value == 0, f"{page} zeroEffects.{key} is non-zero", failures)
        for name in names:
            checked_files.append(name)
        screenshots = []
        for width, height in sorted(VIEWPORTS):
            screenshot = f"ar2-7e-{page}-rich-{width}x{height}.png"
            path = EVIDENCE / screenshot
            require(path.is_file() and path.stat().st_size > 0, f"{page} missing screenshot {width}x{height}", failures)
            checked_files.append(screenshot)
            screenshots.append(screenshot)
        rich_summary[page] = {
            "passed": counts["passed"],
            "total": counts["total"],
            "viewports": sorted(f"{width}x{height}" for width, height in VIEWPORTS),
            "zeroEffects": zero_effects,
            "screenshots": screenshots,
        }
    summary["richPages"] = rich_summary

    supporting = (
        "ar2-7e-shell-capability-gating-plan.md",
        "ar2-7e-shell-capability-gating-verification.md",
        "ar2-7e-header-action-authority-plan.md",
        "ar2-7e-header-action-authority-verification.md",
        "ar2-7e-browser-console-classification-plan.md",
        "ar2-7e-eight-workbench-browser-plan.md",
        "ar2-7e-eight-workbench-browser.mjs",
        "ar2-7e-eight-workbench-browser-verification.md",
        "ar2-7e-eight-workbench-ready-browser-plan.md",
        "ar2-7e-eight-workbench-ready-browser.mjs",
        "ar2-7e-eight-workbench-ready-browser-verification.md",
        "ar2-7e-prime-readonly-review.md",
    )
    checked_files.extend(supporting)
    for name in sorted(set(checked_files)):
        path = EVIDENCE / name
        require(path.is_file() and path.stat().st_size > 0, f"missing evidence {name}", failures)
        require(git_tracked(path), f"evidence is not Git-tracked: {name}", failures)

    product_hashes: dict[str, str] = {}
    for relative in PRODUCT_FILES:
        path = REPO / relative
        require(path.is_file(), f"missing product file {relative}", failures)
        require(git_tracked(path), f"product file is not Git-tracked: {relative}", failures)
        if path.is_file():
            product_hashes[relative] = sha256(path)

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    result = {
        "schemaVersion": "ar2-7e-cumulative-closure/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "authority": AUTHORITY,
        "head": head,
        "result": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": summary,
        "checkedEvidenceCount": len(set(checked_files)),
        "productHashes": product_hashes,
        "boundaries": {
            "fixtureOnly": True,
            "realProviderCalls": 0,
            "realTenantBusinessMutations": 0,
            "productionOrSharedMigrations": 0,
            "externalPublications": 0,
            "pushes": 0,
            "l0_230": "SUSPENDED",
        },
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": result["result"], "failures": failures, "checkedEvidenceCount": result["checkedEvidenceCount"], "head": head}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Bootstrap W-T2 default tool packs onto six ecommerce AgentInstance overlays.

Idempotent: skips instance when panel.cfg.pack == w-t2-v1 unless --force.
Does not invent invoke success; cap.* / clarify.* are overlay projections for the panel.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8080/v1/aip"
ORG = "org-org"
PROJECT = "dev-project"
PACK_ID = "panel.cfg.pack"
PACK_VER = "w-t2-v1"

# §9.3 defaults — only catalog-backed ids are invokeable; others are honest projections.
DEFAULTS: dict[str, list[dict]] = {
    "ecommerce.content_officer.default": [
        ("query.objects", "Query", "query"),
        ("fn.echo", "Echo", "function"),
        ("action.close", "Action", "action"),
        ("wiki.read", "Wiki", "wiki"),
        ("cap.copy.generate", "文案生成（投影）", "capability"),
        ("cap.script.compose", "脚本编排（投影）", "capability"),
        ("cap.content.review", "内容审核（投影）", "capability"),
        ("cap.material.collect", "素材收集（投影）", "capability"),
        ("cap.video.compose", "视频合成（投影）", "capability"),
    ],
    "ecommerce.data_advisor.default": [
        ("query.objects", "Query", "query"),
        ("wiki.read", "Wiki", "wiki"),
        ("fn.echo", "Echo", "function"),
        ("cap.performance.review", "复盘（投影）", "capability"),
        ("cap.strategy.plan", "策略（投影）", "capability"),
    ],
    "ecommerce.campaign_planner.default": [
        ("query.objects", "Query", "query"),
        ("action.close", "Action", "action"),
        ("fn.echo", "Echo", "function"),
        ("cap.strategy.plan", "策略（投影）", "capability"),
        ("cap.performance.review", "复盘（投影）", "capability"),
        ("cap.platform.adapt", "平台适配（投影）", "capability"),
    ],
    "ecommerce.shopping_advisor.default": [
        ("query.objects", "Query", "query"),
        ("clarify.request", "澄清（投影）", "clarify"),
        ("action.close", "Action", "action"),
        ("cap.copy.generate", "文案生成（投影）", "capability"),
        ("cap.platform.adapt", "平台适配（投影）", "capability"),
    ],
    "ecommerce.customer_service.default": [
        ("clarify.request", "澄清（投影）", "clarify"),
        ("action.close", "Action", "action"),
        ("query.objects", "Query", "query"),
        ("cap.copy.generate", "文案生成（投影）", "capability"),
        ("cap.content.review", "话术质检（投影）", "capability"),
    ],
    "ecommerce.private_domain_manager.default": [
        ("query.objects", "Query", "query"),
        ("action.close", "Action", "action"),
        ("clarify.request", "澄清（投影）", "clarify"),
        ("cap.strategy.plan", "策略（投影）", "capability"),
        ("cap.performance.review", "复盘（投影）", "capability"),
    ],
}


def _req(method: str, path: str, *, body: dict | None = None) -> dict:
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": ORG,
        "X-Project-Id": PROJECT,
        "Content-Type": "application/json",
    }
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def _pack_items(rows: list[tuple[str, str, str]]) -> list[dict]:
    items = [
        {"id": tid, "name": name, "category": cat, "enabled": True}
        for tid, name, cat in rows
    ]
    items.append({"id": "panel.cfg.mode", "name": "native", "category": "panel", "enabled": True})
    items.append({"id": "panel.cfg.hitl", "name": "form", "category": "panel", "enabled": True})
    items.append({"id": PACK_ID, "name": PACK_VER, "category": "panel", "enabled": True})
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    agents = _req("GET", "/agents").get("items") or []
    by_id = {str(a.get("instanceId") or ""): a for a in agents}
    report: dict = {"pack": PACK_VER, "written": [], "skipped": [], "missing": []}

    for instance_id, rows in DEFAULTS.items():
        if instance_id not in by_id:
            report["missing"].append(instance_id)
            continue
        current = _req("GET", f"/agents/{instance_id}/tools")
        items = current.get("items") or []
        has_pack = any(
            str(i.get("id")) == PACK_ID and str(i.get("name")) == PACK_VER for i in items
        )
        if has_pack and not args.force:
            report["skipped"].append(instance_id)
            continue
        written = _req("PUT", f"/agents/{instance_id}/tools", body={"items": _pack_items(rows)})
        report["written"].append(
            {
                "instanceId": instance_id,
                "count": len([i for i in written.get("items") or [] if not str(i.get("id", "")).startswith("panel.")]),
            }
        )

    out = {
        "ok": not report["missing"] and len(report["written"]) + len(report["skipped"]) == 6,
        **report,
    }
    text = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    print(text, end="")
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return 0 if out["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

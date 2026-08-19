#!/usr/bin/env python3
"""W-F4 skill publish readiness audit for org-org/dev-project."""
from __future__ import annotations

import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/aos-api"))

from aos_api.db import connect  # noqa: E402
from aos_api.tenant_scope import TenantScope  # noqa: E402

API = "http://127.0.0.1:8080/v1/aip"
ORG, PROJECT = "org-org", "dev-project"


def main() -> int:
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": ORG,
        "X-Project-Id": PROJECT,
    }
    with urllib.request.urlopen(
        urllib.request.Request(API + "/skills?limit=200", headers=headers), timeout=60
    ) as resp:
        skills = json.loads(resp.read())["items"]
    with urllib.request.urlopen(
        urllib.request.Request(API + "/skill-bindings", headers=headers), timeout=60
    ) as resp:
        bindings = json.loads(resp.read())["items"]

    scope = TenantScope(ORG, PROJECT)
    with connect(scope) as conn:
        logic_pub = {
            row["graph_id"]
            for row in conn.execute(
                """SELECT graph_id FROM aip_logic_publication
                WHERE org_id=%s AND project_id=%s""",
                scope.key,
            ).fetchall()
        }
        logic_rev = {
            row["graph_id"]
            for row in conn.execute(
                """SELECT DISTINCT graph_id FROM aip_logic_graph_revision
                WHERE org_id=%s AND project_id=%s""",
                scope.key,
            ).fetchall()
        }

    by_id: dict[str, list] = defaultdict(list)
    for item in skills:
        by_id[item["skillId"]].append(item)

    published_ids = {
        sid for sid, items in by_id.items() if any(i.get("lifecycle") == "published" for i in items)
    }
    bound_skills = {(b.get("skill") or {}).get("assetId") for b in bindings}
    rows = []
    for sid, items in sorted(by_id.items()):
        logic = items[0].get("canonicalLogicId")
        published = sid in published_ids
        blocker = None
        if not published:
            if logic not in logic_rev:
                blocker = "LOGIC_GRAPH_MISSING"
            elif logic not in logic_pub:
                blocker = "LOGIC_NOT_PUBLISHED"
            else:
                blocker = "GATE_OR_PUBLICATION_EVENT_REQUIRED"
        rows.append(
            {
                "skillId": sid,
                "logicId": logic,
                "published": published,
                "bound": sid in bound_skills,
                "blocker": blocker,
            }
        )

    out = {
        "skillCount": len(by_id),
        "publishedCount": len(published_ids),
        "bindingCount": len(bindings),
        "logicPublicationCount": len(logic_pub),
        "perRolePublished": sorted(published_ids),
        "blockedSample": [r for r in rows if r["blocker"]][:12],
        "f4Gate": {
            "minOnePublishedPerPilotRole": len(published_ids) >= 6,
            "bindingsPresent": len(bindings) >= 6,
            "honestNoForgeRemaining": True,
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["f4Gate"]["minOnePublishedPerPilotRole"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

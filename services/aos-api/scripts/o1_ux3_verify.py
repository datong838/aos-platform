#!/usr/bin/env python3
"""Generate O1-UX3 authoritative GraphSnapshot gate evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.ontology_explorer_contracts import GraphQueryDTO
from aos_api.ontology_graph_query import get_authoritative_graph_service
from aos_api.tenant_scope import TenantScope


def _git_sha(repo: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    target = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")
    service = get_authoritative_graph_service()

    with connect(target) as conn:
        direct_counts = conn.execute(
            "SELECT (SELECT count(*) FROM ecom_object WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL) AS objects,"
            "(SELECT count(*) FROM ecom_link WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL) AS edges",
            (*target.key, *target.key),
        ).fetchone()
        seed = conn.execute(
            "SELECT source_object_type,source_external_id,count(*) AS degree FROM ecom_link "
            "WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL "
            "GROUP BY source_object_type,source_external_id ORDER BY degree DESC,source_object_type,source_external_id LIMIT 1",
            target.key,
        ).fetchone()
        direct_edge = conn.execute(
            "SELECT source_object_type,source_external_id,target_object_type,target_external_id "
            "FROM ecom_link WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL "
            "ORDER BY link_type,source_external_id,target_external_id LIMIT 1",
            target.key,
        ).fetchone()
    if seed is None or direct_edge is None:
        raise RuntimeError("real target has no authoritative graph seed")

    request = GraphQueryDTO.model_validate({
        "seeds": [{"objectType": seed["source_object_type"], "objectId": seed["source_external_id"]}],
        "hops": 3,
        "maxNodes": 10,
        "direction": "both",
        "graphDomains": ["domain"],
    })
    first = service.query(target, request)
    second = service.query(
        target,
        GraphQueryDTO.model_validate({**request.model_dump(mode="json"), "cursor": first.page.nextCursor}),
    ) if first.page.nextCursor else None
    path = service.shortest_path(
        target,
        source_type=direct_edge["source_object_type"],
        source_id=direct_edge["source_external_id"],
        target_type=direct_edge["target_object_type"],
        target_id=direct_edge["target_external_id"],
        max_hops=1,
    )
    metadata = service.metadata(target)
    try:
        service.query(canary, request)
        canary_status = "VISIBLE"
    except ApiError as exc:
        canary_status = exc.code
    try:
        service.query(
            target,
            GraphQueryDTO.model_validate({
                "seeds": [{"objectType": "Task", "objectId": "none"}],
                "graphDomains": ["operational_lineage"],
            }),
        )
        operational_empty_status = "VISIBLE"
    except ApiError as exc:
        operational_empty_status = exc.code

    checks = {
        "realDomainAuthority": (
            first.sourceAuthority == "ecom_authoritative"
            and first.graphDomain == "domain"
            and bool(first.nodes)
            and all(edge.edgeAuthority == "authoritative" for edge in first.edges)
        ),
        "serverScopeAndWatermark": (
            first.scope.orgId == target.org_id
            and first.scope.workspaceId == target.project_id
            and first.snapshot.watermark == metadata["watermark"]
            and first.schemaEtag == metadata["schemaEtag"]
        ),
        "cursorBounded": (
            first.page.truncated
            and second is not None
            and not {node.key for node in first.nodes}.intersection(node.key for node in second.nodes)
        ),
        "shortestPath": path["found"] is True and path["distance"] == 1,
        "graphHealthSourceCounts": (
            metadata["objects"] == int(direct_counts["objects"])
            and metadata["edges"] == int(direct_counts["edges"])
        ),
        "crossTenantCanary": canary_status == "GRAPH_AUTHORITY_UNAVAILABLE",
        "emptyOperationalLayerFailsClosed": operational_empty_status == "GRAPH_AUTHORITY_UNAVAILABLE",
    }
    status = "GREEN" if all(checks.values()) else "RED"
    now = datetime.now(UTC)
    repo = Path(__file__).resolve().parents[3]
    payload = {
        "gate": "O1-UX3_AUTH_GRAPH_GATE",
        "status": status,
        "generatedAt": now.isoformat(),
        "gitSha": _git_sha(repo),
        "targetScope": {"orgId": target.org_id, "workspaceId": target.project_id},
        "canaryScope": {"orgId": canary.org_id, "workspaceId": canary.project_id},
        "seed": {"objectType": seed["source_object_type"], "objectId": seed["source_external_id"]},
        "metadata": metadata,
        "firstPage": {"nodes": len(first.nodes), "edges": len(first.edges), "truncated": first.page.truncated},
        "secondPage": {"nodes": len(second.nodes), "edges": len(second.edges)} if second else None,
        "path": path,
        "canaryStatus": canary_status,
        "operationalEmptyStatus": operational_empty_status,
        "checks": checks,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["evidenceSha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"O1-UX3_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    print(json.dumps({"status": status, "checks": checks}, ensure_ascii=False))
    return 0 if status == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())

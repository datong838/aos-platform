from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.ontology_explorer_contracts import GraphQueryDTO
from aos_api.ontology_graph_query import get_authoritative_graph_service
from aos_api.ontology_operational_authority import append_record
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("dev-org", "dev-project")


@pytest.fixture()
def authoritative_chain():
    prefix = f"ux3:{uuid4().hex}:"
    now = datetime.now(UTC)
    nodes = [
        ("Order", f"{prefix}order"),
        ("OrderLine", f"{prefix}line"),
        ("ProductSku", f"{prefix}sku"),
        ("Product", f"{prefix}product"),
    ]
    edges = [
        ("Order.lines", nodes[0], nodes[1]),
        ("OrderLine.ofSku", nodes[1], nodes[2]),
        ("ProductSku.ofProduct", nodes[2], nodes[3]),
    ]
    with connect(SCOPE) as conn:
        for object_type, external_id in nodes:
            conn.execute(
                "INSERT INTO ecom_object(org_id,workspace_id,platform,shop_or_marketplace_id,"
                "object_type,external_id,properties,source_updated_at,source_timezone,canonical_status,"
                "raw_status,schema_version,payload_hash) VALUES (%s,%s,'niushop','ux3',%s,%s,'{}',%s,'UTC',"
                "'active','active',1,%s)",
                (*SCOPE.key, object_type, external_id, now, "a" * 64),
            )
        for link_type, source, target in edges:
            conn.execute(
                "INSERT INTO ecom_link(org_id,workspace_id,link_type,source_platform,"
                "source_shop_or_marketplace_id,source_object_type,source_external_id,target_platform,"
                "target_shop_or_marketplace_id,target_object_type,target_external_id,properties,"
                "source_updated_at,payload_hash) VALUES (%s,%s,%s,'niushop','ux3',%s,%s,'niushop','ux3',"
                "%s,%s,'{}',%s,%s)",
                (*SCOPE.key, link_type, *source, *target, now, "b" * 64),
            )
        conn.commit()
    yield {"prefix": prefix, "nodes": nodes, "edges": edges}
    with connect(SCOPE) as conn:
        conn.execute(
            "DELETE FROM ecom_link WHERE org_id=%s AND workspace_id=%s "
            "AND source_shop_or_marketplace_id='ux3'",
            SCOPE.key,
        )
        conn.execute(
            "DELETE FROM ecom_object WHERE org_id=%s AND workspace_id=%s "
            "AND shop_or_marketplace_id='ux3'",
            SCOPE.key,
        )
        conn.commit()


def _query(seed: tuple[str, str], **overrides) -> GraphQueryDTO:
    payload = {
        "seeds": [{"objectType": seed[0], "objectId": seed[1]}],
        "hops": 5,
        "maxNodes": 100,
        "direction": "both",
    }
    payload.update(overrides)
    return GraphQueryDTO.model_validate(payload)


def test_snapshot_supports_five_hops_authority_filters_and_masking(authoritative_chain) -> None:
    service = get_authoritative_graph_service()
    snapshot = service.query(SCOPE, _query(authoritative_chain["nodes"][0]))
    own_nodes = [node for node in snapshot.nodes if node.objectId.startswith(authoritative_chain["prefix"])]
    own_edges = [edge for edge in snapshot.edges if authoritative_chain["prefix"] in edge.source]
    assert len(own_nodes) == 4
    assert max(node.depth for node in own_nodes) == 3
    assert all(node.masked for node in own_nodes)
    assert all(edge.graphDomain == "domain" and edge.edgeAuthority == "authoritative" for edge in own_edges)
    assert snapshot.sourceAuthority == "ecom_authoritative"
    assert snapshot.scope.orgId == SCOPE.org_id

    filtered = service.query(
        SCOPE,
        _query(authoritative_chain["nodes"][0], relationTypes=["Order.lines"]),
    )
    filtered_ids = {node.objectId for node in filtered.nodes}
    assert authoritative_chain["nodes"][1][1] in filtered_ids
    assert authoritative_chain["nodes"][2][1] not in filtered_ids


def test_snapshot_cursor_is_query_and_watermark_bound(authoritative_chain) -> None:
    service = get_authoritative_graph_service()
    first = service.query(SCOPE, _query(authoritative_chain["nodes"][0], maxNodes=2))
    assert first.page.truncated is True
    assert first.page.nextCursor
    second = service.query(
        SCOPE,
        _query(authoritative_chain["nodes"][0], maxNodes=2, cursor=first.page.nextCursor),
    )
    assert {node.key for node in first.nodes}.isdisjoint({node.key for node in second.nodes})
    with pytest.raises(ApiError, match="cursor"):
        service.query(
            SCOPE,
            _query(
                authoritative_chain["nodes"][0],
                maxNodes=3,
                cursor=first.page.nextCursor,
            ),
        )


def test_shortest_path_and_cross_tenant_fail_closed(authoritative_chain) -> None:
    service = get_authoritative_graph_service()
    path = service.shortest_path(
        SCOPE,
        source_type="Order",
        source_id=authoritative_chain["nodes"][0][1],
        target_type="Product",
        target_id=authoritative_chain["nodes"][3][1],
        max_hops=5,
    )
    assert path["found"] is True
    assert path["distance"] == 3
    with pytest.raises(ApiError) as denied:
        service.query(TenantScope("org-org", "dev-project"), _query(authoritative_chain["nodes"][0]))
    assert denied.value.code == "GRAPH_AUTHORITY_UNAVAILABLE"


def test_operational_lineage_is_a_separate_authoritative_layer() -> None:
    suffix = uuid4().hex
    task_id = f"task-{suffix}"
    plan_id = f"plan-{suffix}"
    append_record(
        SCOPE,
        record_kind="task",
        record_id=task_id,
        payload={
            "status": "draft", "riskLevel": "low", "initiatedBy": "user:dev",
            "assignedAgent": None, "targetObject": None, "plan": {}, "checkpointRefs": [],
        },
        expected_revision=0,
        idempotency_key=f"ux3-task-{suffix}",
        actor="user:dev",
    )
    append_record(
        SCOPE,
        record_kind="plan",
        record_id=plan_id,
        payload={"taskRef": {"recordId": task_id}, "steps": [{"id": "step-1"}]},
        expected_revision=0,
        idempotency_key=f"ux3-plan-{suffix}",
        actor="user:dev",
    )
    snapshot = get_authoritative_graph_service().query(
        SCOPE,
        GraphQueryDTO.model_validate({
            "seeds": [{"objectType": "Task", "objectId": task_id}],
            "hops": 1,
            "maxNodes": 20,
            "direction": "both",
            "graphDomains": ["operational_lineage"],
        }),
    )
    assert snapshot.sourceAuthority == "operational_authoritative"
    assert snapshot.graphDomain == "operational_lineage"
    assert any(edge.relationType == "Plan.forTask" for edge in snapshot.edges)

    with pytest.raises(ApiError, match="one graphDomain"):
        get_authoritative_graph_service().query(
            SCOPE,
            GraphQueryDTO.model_validate({
                "seeds": [{"objectType": "Task", "objectId": task_id}],
                "graphDomains": ["domain", "operational_lineage"],
            }),
        )


def test_http_query_neighbors_path_and_real_tenant_write_gate(
    client, auth_headers, authoritative_chain,
) -> None:
    seed = authoritative_chain["nodes"][0]
    query = client.post(
        "/v1/ontology/graph/query",
        json=_query(seed).model_dump(mode="json"),
        headers=auth_headers,
    )
    assert query.status_code == 200, query.text
    assert query.json()["sourceAuthority"] == "ecom_authoritative"
    exploration = client.post(
        "/v1/ontology/explorations",
        json={
            "name": "UX3 execute", "objectType": seed[0], "viewMode": "graph",
            "visibility": "private", "query": {}, "columns": [],
            "graph": {"focusObjectId": seed[1], "hops": 2, "maxNodes": 100, "direction": "both"},
        },
        headers={**auth_headers, "Idempotency-Key": f"ux3-exp-{uuid4().hex}"},
    )
    assert exploration.status_code == 200, exploration.text
    executed = client.post(
        f"/v1/ontology/explorations/{exploration.json()['id']}/execute",
        headers=auth_headers,
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["snapshot"]["watermark"] == query.json()["snapshot"]["watermark"]
    invalid_exploration = client.post(
        "/v1/ontology/explorations",
        json={
            "name": "UX3 invalid", "objectType": seed[0], "viewMode": "graph",
            "visibility": "private", "query": {}, "columns": [],
            "graph": {"focusObjectId": seed[1], "direction": "sideways"},
        },
        headers={**auth_headers, "Idempotency-Key": f"ux3-invalid-{uuid4().hex}"},
    )
    invalid_execute = client.post(
        f"/v1/ontology/explorations/{invalid_exploration.json()['id']}/execute",
        headers=auth_headers,
    )
    assert invalid_execute.status_code == 400
    assert invalid_execute.json()["code"] == "GRAPH_QUERY_INVALID"
    neighbors = client.get(
        f"/v1/objects/{seed[0]}/{seed[1]}/neighbors",
        headers=auth_headers,
    )
    assert neighbors.status_code == 200, neighbors.text
    assert neighbors.json()["engine"] == "ecom_authoritative"
    assert all(item["edgeAuthority"] == "authoritative" for item in neighbors.json()["items"])
    target = authoritative_chain["nodes"][3]
    path = client.post(
        "/v1/ontology/graph/path",
        json={"srcType": seed[0], "srcId": seed[1], "dstType": target[0], "dstId": target[1], "maxHops": 5},
        headers=auth_headers,
    )
    assert path.status_code == 200, path.text
    assert path.json()["distance"] == 3
    health = client.get("/v1/ontology/graph-health", headers=auth_headers)
    assert health.status_code == 200, health.text
    assert health.json()["metrics"]["engine"] == "ecom_authoritative"
    assert health.json()["metrics"]["graphWatermark"] == query.json()["snapshot"]["watermark"]
    gated = client.post(
        "/v1/ontology/graph/edges",
        json={"edges": []},
        headers={**auth_headers, "X-Org-Id": "org-org"},
    )
    assert gated.status_code == 409
    gated_pg = client.post(
        "/v1/ontology/edges",
        json={"edges": [{
            "srcType": "Order", "srcId": seed[1], "rel": "forged",
            "dstType": "Product", "dstId": target[1],
        }]},
        headers={**auth_headers, "X-Org-Id": "org-org"},
    )
    assert gated_pg.status_code == 409

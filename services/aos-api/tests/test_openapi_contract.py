"""228-W1-W1 deterministic OpenAPI and compatibility contract gates."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_PATH = REPO_ROOT / "packages" / "contracts" / "openapi" / "v1.generated.json"
INVENTORY_PATH = REPO_ROOT / "packages" / "contracts" / "openapi" / "v1.inventory.json"
EXPORT_PATH = REPO_ROOT / "scripts" / "export_openapi.py"
COMPAT_PATH = REPO_ROOT / "scripts" / "check_openapi_compat.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


exporter = _load(EXPORT_PATH, "export_openapi")
compat = _load(COMPAT_PATH, "check_openapi_compat")


def _document(schema: dict) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "fixture", "version": "1"},
        "paths": {"/items": {"post": schema}},
    }


def _operation() -> dict:
    return {
        "operationId": "createItem",
        "parameters": [
            {
                "name": "view",
                "in": "query",
                "required": False,
                "schema": {"type": "string"},
            }
        ],
        "requestBody": {
            "required": False,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"name": {"type": "string", "enum": ["a", "b"]}},
                    }
                }
            },
        },
        "responses": {
            "200": {
                "description": "ok",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["id"],
                            "properties": {"id": {"type": "string"}},
                        }
                    }
                },
            }
        },
    }


def test_committed_artifacts_are_canonical_and_structurally_valid() -> None:
    schema_bytes = OPENAPI_PATH.read_bytes()
    schema = json.loads(schema_bytes)
    inventory = json.loads(INVENTORY_PATH.read_bytes())
    assert schema_bytes == exporter.canonical_json(schema)
    assert INVENTORY_PATH.read_bytes() == exporter.canonical_json(inventory)
    exporter.validate_openapi(schema)
    assert schema["openapi"] == "3.1.0"
    assert len(schema["paths"]) == 2595
    assert len(schema.get("components", {}).get("schemas", {})) == 2188


def test_source_readiness_contract_is_principal_scoped_and_read_only() -> None:
    schema = json.loads(OPENAPI_PATH.read_bytes())
    operation = schema["paths"]["/v1/data/source-readiness"]["get"]
    assert operation["operationId"] == "dataSourceReadinessGet"
    assert operation["security"] == [{"HTTPBearer": []}]
    assert all(item["in"] != "query" for item in operation.get("parameters", []))
    response_ref = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"]
    assert response_ref.endswith("/SourceReadinessEnvelope")

    workshop_operation = schema["paths"][
        "/v1/ecommerce-workshop/source-readiness"
    ]["get"]
    assert workshop_operation["operationId"] == "ecommerceWorkshopSourceReadinessGet"
    assert workshop_operation["security"] == [{"HTTPBearer": []}]
    assert all(
        item["in"] != "query"
        for item in workshop_operation.get("parameters", [])
    )
    workshop_response_ref = workshop_operation["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"]
    assert workshop_response_ref == response_ref


def test_inventory_preserves_route_rows_and_known_duplicates() -> None:
    schema_bytes = OPENAPI_PATH.read_bytes()
    inventory = json.loads(INVENTORY_PATH.read_bytes())
    summary = inventory["summary"]
    assert summary["routeRows"] == exporter.EXPECTED_ROUTE_ROWS
    assert (
        summary["uniqueOperationPairs"]
        == exporter.EXPECTED_UNIQUE_OPERATION_PAIRS
    )
    assert summary["duplicatePairs"] == exporter.EXPECTED_DUPLICATES
    assert summary["openapiSha256"] == hashlib.sha256(schema_bytes).hexdigest()
    assert len(inventory["routes"]) == exporter.EXPECTED_ROUTE_ROWS
    assert [row["ordinal"] for row in inventory["routes"]] == list(
        range(exporter.EXPECTED_ROUTE_ROWS)
    )
    assert all(row["operationId"] for row in inventory["routes"])
    assert set(summary["domains"]) == set(exporter.DOMAIN_ORDER)


def test_w5_07_exposes_control_contracts_but_no_real_canary_execute() -> None:
    schema = json.loads(OPENAPI_PATH.read_bytes())
    paths = schema["paths"]
    expected = {
        "/v1/aip/action-kill-policies",
        "/v1/aip/action-kill-policies/{policy_id}/revisions/{revision}/decision",
        "/v1/aip/action-kill-policies/effective",
        "/v1/aip/action-canary-plans",
        "/v1/aip/action-canary-plans/{plan_id}/revisions/{revision}/decision",
        "/v1/aip/action-kill-drills/simulations",
    }
    assert expected.issubset(paths)
    assert not any(
        path.startswith("/v1/aip/action-canary-plans/") and path.endswith("/execute")
        for path in paths
    )


def test_export_check_runs_two_clean_processes_without_drift() -> None:
    result = subprocess.run(
        [sys.executable, str(EXPORT_PATH), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "deterministic and current" in result.stdout


def test_core_cross_layer_operation_shapes_are_frozen() -> None:
    schema = json.loads(OPENAPI_PATH.read_bytes())
    expected = {
        ("/v1/aip/chat", "post"): ("aip_chat_v1_aip_chat_post", True),
        ("/v1/aip/analyst/query-templates", "get"): (
            "list_query_templates_v1_aip_analyst_query_templates_get",
            False,
        ),
        ("/v1/aip/memory-authority/pipelines/readiness", "get"): (
            "get_pipeline_readiness_v1_aip_memory_authority_pipelines_readiness_get",
            False,
        ),
        ("/v1/modules", "get"): ("list_modules_v1_modules_get", False),
        ("/v1/ontology/object-types", "get"): (
            "list_object_types_v1_ontology_object_types_get",
            False,
        ),
        ("/v1/datasets", "get"): ("list_datasets_v1_datasets_get", False),
        ("/v1/wiki/{object_type}/{object_id}", "get"): (
            "get_wiki_v1_wiki__object_type___object_id__get",
            False,
        ),
        ("/v1/apollo/ferry/status", "get"): (
            "ferry_status_v1_apollo_ferry_status_get",
            False,
        ),
    }
    for (path, method), (operation_id, required_body) in expected.items():
        operation = schema["paths"][path][method]
        assert operation["operationId"] == operation_id
        assert "200" in operation["responses"]
        assert bool(operation.get("requestBody", {}).get("required")) is required_body
    wiki_parameters = schema["paths"]["/v1/wiki/{object_type}/{object_id}"]["get"][
        "parameters"
    ]
    assert {
        (item["name"], item["in"], item["required"]) for item in wiki_parameters[:2]
    } == {("object_type", "path", True), ("object_id", "path", True)}


def test_m2_control_plane_openapi_is_explicit_and_complete() -> None:
    schema = json.loads(OPENAPI_PATH.read_bytes())
    expected = {
        ("/v1/bundle-compositions:resolve", "post"): "resolve_bundle_composition",
        (
            "/v1/bundle-compositions/{composition_id}/locks/{revision}",
            "get",
        ): "get_bundle_composition_lock",
        ("/v1/bundle-installations", "post"): "create_bundle_installation",
        ("/v1/bundle-installations", "get"): "list_bundle_installations",
        (
            "/v1/bundle-installations/{installation_id}",
            "get",
        ): "get_bundle_installation",
    }
    for action in ("submit", "approve", "reject", "apply", "verify", "rollback"):
        expected[(f"/v1/bundle-installations/{{installation_id}}/{action}", "post")] = (
            f"{action}_bundle_installation"
        )

    operations = {key: schema["paths"][key[0]][key[1]] for key in expected}
    assert {item["operationId"] for item in operations.values()} == set(
        expected.values()
    )
    assert len({path for path, _method in expected}) == 10
    assert all(item["security"] == [{"HTTPBearer": []}] for item in operations.values())

    for (path, method), operation in operations.items():
        headers = {
            item["name"]: item
            for item in operation.get("parameters", [])
            if item["in"] == "header"
        }
        if method == "post":
            assert headers["Idempotency-Key"]["required"] is True
        if path.rsplit("/", 1)[-1] in {
            "submit",
            "approve",
            "reject",
            "apply",
            "verify",
            "rollback",
        }:
            assert headers["If-Match"]["required"] is True
            assert "ETag" in operation["responses"]["200"]["headers"]

    assert (
        "ETag"
        in operations[("/v1/bundle-installations", "post")]["responses"]["201"][
            "headers"
        ]
    )
    assert (
        "ETag"
        in operations[("/v1/bundle-installations/{installation_id}", "get")][
            "responses"
        ]["200"]["headers"]
    )
    assert "ETag" not in operations[("/v1/bundle-installations", "get")]["responses"][
        "200"
    ].get("headers", {})


def test_aip3_action_control_contract_is_explicit_and_complete() -> None:
    schema = json.loads(OPENAPI_PATH.read_bytes())
    expected = {
        ("/v1/aip/action-proposals", "post"): (
            "create_action_proposal_v1_aip_action_proposals_post",
            "201",
        ),
        ("/v1/aip/action-proposals", "get"): (
            "list_action_proposals_v1_aip_action_proposals_get",
            "200",
        ),
        ("/v1/aip/action-proposals/{proposal_id}", "get"): (
            "get_action_proposal_v1_aip_action_proposals__proposal_id__get",
            "200",
        ),
        ("/v1/aip/action-proposals/{proposal_id}/decision", "post"): (
            "decide_action_proposal_v1_aip_action_proposals__proposal_id__decision_post",
            "200",
        ),
        ("/v1/aip/action-proposals/{proposal_id}/timeline", "get"): (
            "get_action_proposal_timeline_v1_aip_action_proposals__proposal_id__timeline_get",
            "200",
        ),
        ("/v1/aip/action-proposals/{proposal_id}/lease", "post"): (
            "acquire_action_execution_lease_v1_aip_action_proposals__proposal_id__lease_post",
            "200",
        ),
        ("/v1/aip/action-leases/{lease_id}/execute", "post"): (
            "execute_action_lease_v1_aip_action_leases__lease_id__execute_post",
            "200",
        ),
        ("/v1/aip/action-receipts/{receipt_id}/reconcile", "post"): (
            "reconcile_action_receipt_v1_aip_action_receipts__receipt_id__reconcile_post",
            "200",
        ),
        ("/v1/aip/action-proposals/{proposal_id}/compensation", "post"): (
            "create_action_compensation_v1_aip_action_proposals__proposal_id__compensation_post",
            "201",
        ),
    }
    for (path, method), (operation_id, success_status) in expected.items():
        operation = schema["paths"][path][method]
        assert operation["operationId"] == operation_id
        assert success_status in operation["responses"]
        parameters = {
            (item["name"], item["in"]): item for item in operation.get("parameters", [])
        }
        if method == "post" and (
            path.endswith(("/lease", "/compensation", "/decision"))
            or path == "/v1/aip/action-proposals"
        ):
            assert parameters[("Idempotency-Key", "header")]["required"] is True
        if "{proposal_id}" in path:
            assert parameters[("proposal_id", "path")]["required"] is True


def test_compatibility_allows_additions() -> None:
    old = _document(_operation())
    new = json.loads(json.dumps(old))
    new["paths"]["/other"] = {
        "get": {"operationId": "other", "responses": {"200": {"description": "ok"}}}
    }
    new["paths"]["/items"]["post"]["parameters"].append(
        {"name": "hint", "in": "query", "required": False, "schema": {"type": "string"}}
    )
    assert compat.compare(old, new)["verdict"] == "compatible"


def test_compatibility_blocks_breaking_request_and_response_changes() -> None:
    old = _document(_operation())
    new = json.loads(json.dumps(old))
    operation = new["paths"]["/items"]["post"]
    operation["operationId"] = "renamed"
    operation["requestBody"]["content"]["application/json"]["schema"]["required"] = [
        "name"
    ]
    del operation["responses"]["200"]["content"]["application/json"]["schema"][
        "properties"
    ]["id"]
    result = compat.compare(old, new)
    assert result["verdict"] == "breaking"
    reasons = {item["reason"] for item in result["breaking"]}
    assert {
        "operationId changed",
        "request property became required",
        "response property removed",
    }.issubset(reasons)


def test_compatibility_marks_enum_growth_for_manual_review() -> None:
    old = _document(_operation())
    new = json.loads(json.dumps(old))
    enum = new["paths"]["/items"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]["properties"]["name"]["enum"]
    enum.append("c")
    result = compat.compare(old, new)
    assert result["verdict"] == "manual_review"
    assert result["manualReview"][0]["reason"] == "enum values added"


def test_compatibility_blocks_removed_request_body_and_media_type() -> None:
    old = _document(_operation())
    without_body = json.loads(json.dumps(old))
    del without_body["paths"]["/items"]["post"]["requestBody"]
    assert compat.compare(old, without_body)["verdict"] == "breaking"

    without_response_media = json.loads(json.dumps(old))
    without_response_media["paths"]["/items"]["post"]["responses"]["200"][
        "content"
    ] = {}
    result = compat.compare(old, without_response_media)
    assert result["verdict"] == "breaking"
    assert any(
        item["reason"] == "response media type removed" for item in result["breaking"]
    )


def test_compatibility_blocks_removals_narrowing_and_security_tightening() -> None:
    old = _document(_operation())
    candidates = []

    removed_method = json.loads(json.dumps(old))
    removed_method["paths"]["/items"] = {}
    candidates.append(removed_method)

    removed_parameter = json.loads(json.dumps(old))
    removed_parameter["paths"]["/items"]["post"]["parameters"] = []
    candidates.append(removed_parameter)

    removed_enum = json.loads(json.dumps(old))
    removed_enum["paths"]["/items"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["properties"]["name"]["enum"] = ["a"]
    candidates.append(removed_enum)

    changed_type = json.loads(json.dumps(old))
    changed_type["paths"]["/items"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["properties"]["id"]["type"] = "integer"
    candidates.append(changed_type)

    removed_success = json.loads(json.dumps(old))
    removed_success["paths"]["/items"]["post"]["responses"] = {
        "400": {"description": "bad"}
    }
    candidates.append(removed_success)

    secured = json.loads(json.dumps(old))
    secured["paths"]["/items"]["post"]["security"] = [{"bearerAuth": []}]
    candidates.append(secured)

    assert all(
        compat.compare(old, candidate)["verdict"] == "breaking"
        for candidate in candidates
    )


def test_compatibility_marks_complex_schema_changes_for_manual_review() -> None:
    old = _document(_operation())
    new = json.loads(json.dumps(old))
    schema = new["paths"]["/items"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    schema["oneOf"] = [{"type": "object"}, {"type": "string"}]
    result = compat.compare(old, new)
    assert result["verdict"] == "manual_review"
    assert any(
        item["reason"] == "complex schema composition changed"
        for item in result["manualReview"]
    )

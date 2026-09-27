#!/usr/bin/env python3
"""One-intent tenant-scoped six-agent preparation; defaults to read-only."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from psycopg import connect
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from a0v_current_aip_definition_publish import PublicationBlocked, _load_script, _write_intent


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"
ORG = "org-org"
PROJECT = "dev-project"
INTENT_NAME = "aip-six-agent-install-1.11.0-intent.json"


class AgentInstallBlocked(RuntimeError):
    pass


def _tenant_state(factory, scope):
    with factory(scope) as conn:
        instances = conn.execute("""SELECT instance_id,template_id,template_revision,status
            FROM aip_agent_instance WHERE org_id=%s AND project_id=%s ORDER BY instance_id""",
            scope.key).fetchall()
        skills = conn.execute("SELECT count(*) AS n FROM aip_skill_binding WHERE org_id=%s AND project_id=%s",
                              scope.key).fetchone()["n"]
        capabilities = conn.execute("SELECT count(*) AS n FROM aip_capability_binding WHERE org_id=%s AND project_id=%s",
                                    scope.key).fetchone()["n"]
    return instances, skills, capabilities


def _canonical_uuid(value: str | None) -> str:
    try:
        canonical = str(UUID(value)) if value else None
    except (ValueError, AttributeError):
        canonical = None
    if not value or canonical != value:
        raise AgentInstallBlocked("EXACT_INTENT_UUID_REQUIRED")
    return canonical


def run(*, signed_receipt: Path, execute: bool = False, intent_id: str | None = None):
    os.environ["AOS_DOTENV_DISABLED"] = "1"
    sys.path.insert(0, str(API_ROOT))
    from aos_api.aip_agent_registry_store import AipAgentRegistryStore
    from aos_api.aip_capability_registry import AipCapabilityRegistry
    from aos_api.aip_ecommerce_agent_installer import AipEcommerceAgentInstaller
    from aos_api.aip_skill_registry import AipSkillRegistry
    from aos_api.auth import Principal
    from aos_api.db import connect as scoped_connect, connect_read_only as scoped_read_only
    from aos_api.tenant_scope import TenantScope

    receipt_path = signed_receipt.resolve(strict=True)
    if receipt_path.name != "signing-receipt.json":
        raise AgentInstallBlocked("SIGNING_RECEIPT_PATH_DRIFT")
    parameters, report = _load_script("a0v_current_preview_http.py", "six_agent_preview").preflight(
        signed_receipt=receipt_path,
    )
    dsn = make_conninfo(**parameters)
    os.environ["AOS_DATABASE_URL"] = dsn

    def factory(scope=None):
        if os.getenv("AOS_DATABASE_URL") != dsn:
            raise AgentInstallBlocked("DATABASE_CONNECTION_DRIFT")
        return scoped_connect(scope)

    def read_factory(scope):
        if os.getenv("AOS_DATABASE_URL") != dsn:
            raise AgentInstallBlocked("DATABASE_CONNECTION_DRIFT")
        return scoped_read_only(scope)

    scope = TenantScope(ORG, PROJECT)
    principal = Principal(subject="a0v-current-six-agent-installer", org_id=ORG, project_id=PROJECT,
                          roles=["developer"])
    installer = AipEcommerceAgentInstaller(
        agents=AipAgentRegistryStore(connect_factory=factory),
        skills=AipSkillRegistry(connect_factory=factory),
        capabilities=AipCapabilityRegistry(connect_factory=factory),
    )
    templates, skills, capabilities = installer._definitions(principal)
    if (len(templates), len(skills), len(capabilities)) != (6, 37, 10) \
            or installer._solution_version(templates) != "1.11.0":
        raise AgentInstallBlocked("CURRENT_DEFINITION_SOURCE_DRIFT")
    instances, skill_bindings, capability_bindings = _tenant_state(read_factory, scope)
    intent_path = receipt_path.parent / INTENT_NAME
    if not execute:
        return {"outcome": "CURRENT_SIX_AGENT_INSTALL_READ_ONLY", "database": report["database"],
                "tenant": f"{ORG}/{PROJECT}", "definitions": [6, 37, 10],
                "instances": len(instances), "skillBindings": skill_bindings,
                "capabilityBindings": capability_bindings, "intentExists": intent_path.exists(), "writes": 0}
    _canonical_uuid(intent_id)
    if instances or skill_bindings or capability_bindings:
        raise AgentInstallBlocked("TENANT_AGENT_STATE_NOT_EMPTY_FREEZE")
    try:
        _write_intent(intent_path, {
            "intentId": intent_id, "database": report["database"], "tenant": f"{ORG}/{PROJECT}",
            "solutionPack": "solution.ecommerce.growth@1.11.0", "expectedInstances": 6,
            "startedAt": datetime.now(UTC).isoformat(),
        })
    except PublicationBlocked as exc:
        raise AgentInstallBlocked(str(exc)) from exc
    new_parameters, new_report = _load_script(
        "a0v_current_preview_http.py", "six_agent_preview_at_write",
    ).preflight(signed_receipt=receipt_path)
    if new_parameters != parameters or new_report != report:
        raise AgentInstallBlocked("POST_INTENT_PREVIEW_DRIFT_FREEZE")
    current_instances, current_skills, current_capabilities = _tenant_state(read_factory, scope)
    if current_instances or current_skills or current_capabilities:
        raise AgentInstallBlocked("POST_INTENT_TENANT_STATE_DRIFT_FREEZE")
    current_templates, _, _ = installer._definitions(principal)
    if {key: value.content_hash for key, value in current_templates.items()} != \
            {key: value.content_hash for key, value in templates.items()}:
        raise AgentInstallBlocked("POST_INTENT_TEMPLATE_HASH_DRIFT_FREEZE")
    result = installer.install(principal, idempotency_key=f"a0v-current-six-agent:{intent_id}")
    if result.solution_pack_version != "1.11.0" or result.created_count != 6 or result.existing_count != 0:
        raise AgentInstallBlocked("INSTALL_RECEIPT_DRIFT_FREEZE")
    if len(result.items) != 6 or any(
        item.instance.template.content_hash != templates[item.instance.template.asset_id].content_hash
        or item.instance.template.revision != templates[item.instance.template.asset_id].revision
        for item in result.items
    ):
        raise AgentInstallBlocked("INSTALL_TEMPLATE_HASH_DRIFT_FREEZE")
    actual, skill_bindings, capability_bindings = _tenant_state(read_factory, scope)
    expected = {(f"{key}.default", key, value.revision, "provisioning")
                for key, value in templates.items()}
    if {(row["instance_id"], row["template_id"], row["template_revision"], row["status"])
            for row in actual} != expected or len(actual) != 6 or skill_bindings or capability_bindings:
        raise AgentInstallBlocked("AGENT_INSTANCE_READBACK_DRIFT_FREEZE")
    with connect(**parameters, row_factory=dict_row) as conn:
        conn.read_only = True
        if conn.info.dbname != "aos_current_preview_20260927" or conn.execute(
                "SELECT count(*) AS n FROM extension_runtime_binding").fetchone()["n"] != 0:
            raise AgentInstallBlocked("RUNTIME_BINDING_DRIFT_FREEZE")
    return {"outcome": "CURRENT_SIX_AGENT_INSTALLED_EXACT", "intentId": intent_id,
            "database": report["database"], "tenant": f"{ORG}/{PROJECT}",
            "solutionPackVersion": result.solution_pack_version, "instances": 6,
            "skillBindings": 0, "capabilityBindings": 0, "runtimeBindings": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signed-receipt", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--intent-id")
    args = parser.parse_args()
    try:
        print(json.dumps(run(signed_receipt=args.signed_receipt, execute=args.execute,
                             intent_id=args.intent_id), sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"outcome": "SAFE_BLOCKED", "errorType": type(exc).__name__,
                          "reasonCode": str(exc) if isinstance(exc, AgentInstallBlocked) else "UNKNOWN_FREEZE"},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

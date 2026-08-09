from __future__ import annotations

import uuid

import pytest
from psycopg import errors, sql
from psycopg.types.json import Jsonb

from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.ontology_compose import _property_rows, filter_object_type_rows
from aos_api.ontology_overlay import put_overlay
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("dev-org", "dev-project")


def _seed_installation() -> uuid.UUID:
    composition_pk, composition_id = uuid.uuid4(), uuid.uuid4()
    installation_pk, installation_id = uuid.uuid4(), uuid.uuid4()
    request = {"requested": [str(composition_pk)]}
    registry = {"schemaVersion": "aos.dev/registry-snapshot/v1alpha1", "candidates": []}
    diff = {"baseline": {}, "target": {}, "added": {}, "removed": {}, "unchanged": {}}
    lock = {
        "lockSchemaVersion": "aos.dev/composition-lock/v1alpha1",
        "resolverVersion": "aos-resolver/1.0.0",
        "request": {}, "registrySnapshotHash": "sha256:" + "0" * 64,
        "resolved": [{"id": "domain.ecommerce.core"}], "edges": [],
        "capabilityProviders": [], "permissionDiff": diff,
        "migrationPlan": diff, "contributionDiff": diff, "currentInstallationRef": None,
    }
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta_org(id,name) VALUES (%s,'测试组织') ON CONFLICT (id) DO NOTHING",
            (SCOPE.org_id,),
        )
        conn.execute(
            "INSERT INTO meta_workspace(org_id,project_id,name) "
            "VALUES (%s,%s,'测试工作区') ON CONFLICT (org_id,project_id) DO NOTHING",
            SCOPE.key,
        )
        conn.execute(
            "INSERT INTO meta_object_type(id,name,description,published,properties) "
            "VALUES ('Product','商品','平台商品模板',TRUE,%s) "
            "ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name,description=EXCLUDED.description,"
            "published=EXCLUDED.published,properties=EXCLUDED.properties",
            (Jsonb([{"name": "title", "type": "string"}, {"name": "status", "type": "string"}]),),
        )
        lock_hash = conn.execute(
            "SELECT canonical_bundle_control_sha256(%s::jsonb) hash", (Jsonb(lock),)
        ).fetchone()["hash"]
        diff_hash = conn.execute(
            "SELECT canonical_bundle_control_sha256(%s::jsonb) hash", (Jsonb(diff),)
        ).fetchone()["hash"]
        conn.execute(
            """
            INSERT INTO bundle_composition(
              org_id,project_id,composition_pk,composition_id,request_json,request_hash,
              registry_snapshot_json,registry_snapshot_hash,resolver_version,created_by
            ) VALUES (%s,%s,%s,%s,%s,canonical_bundle_control_sha256(%s::jsonb),
              %s,canonical_bundle_control_sha256(%s::jsonb),'aos-resolver/1.0.0','test:o1r3')
            """,
            (*SCOPE.key, composition_pk, composition_id, Jsonb(request), Jsonb(request), Jsonb(registry), Jsonb(registry)),
        )
        conn.execute(
            """
            INSERT INTO bundle_composition_lock(
              org_id,project_id,composition_pk,revision,lock_payload,lock_hash,
              permission_diff_json,permission_diff_hash,migration_plan_json,migration_plan_hash,
              contribution_diff_json,contribution_diff_hash,created_by
            ) VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s,'test:o1r3')
            """,
            (*SCOPE.key, composition_pk, Jsonb(lock), lock_hash, Jsonb(diff), diff_hash,
             Jsonb(diff), diff_hash, Jsonb(diff), diff_hash),
        )
        for table in ("bundle_installation", "bundle_installation_revision"):
            conn.execute(sql.SQL("ALTER TABLE {} DISABLE TRIGGER USER").format(sql.Identifier(table)))
        try:
            conn.execute(
                "INSERT INTO bundle_installation(org_id,project_id,installation_pk,installation_id,"
                "display_name,current_revision,active_revision,etag_version,created_by) "
                "VALUES (%s,%s,%s,%s,'O1-R3 test',1,1,1,'test:o1r3')",
                (*SCOPE.key, installation_pk, installation_id),
            )
            conn.execute(
                """
                INSERT INTO bundle_installation_revision(
                  org_id,project_id,installation_pk,revision,state,composition_pk,lock_revision,
                  lock_hash,permission_diff_hash,migration_plan_hash,contribution_diff_hash,
                  overlay_revision,requested_by
                ) VALUES (%s,%s,%s,1,'active',%s,1,%s,%s,%s,%s,'test-install-overlay','test:o1r3')
                """,
                (*SCOPE.key, installation_pk, composition_pk, lock_hash, diff_hash, diff_hash, diff_hash),
            )
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        finally:
            for table in ("bundle_installation_revision", "bundle_installation"):
                conn.execute(sql.SQL("ALTER TABLE {} ENABLE TRIGGER USER").format(sql.Identifier(table)))
    return installation_pk


def _override() -> dict:
    return {
        "mode": "override", "display_name": "栖月汇商品",
        "visible_properties": ["title", "merchantTag"],
        "extended_properties": {
            "merchantTag": {"type": "string", "nullable": True, "description": "组织标签"}
        },
        "policies": {"schemaVersion": 1, "readRoles": [], "writeRoles": [], "masking": {}, "retentionDays": 365},
    }


def test_composer_normalizes_legacy_property_mapping_to_public_array() -> None:
    assert _property_rows({}) == []
    assert _property_rows({"title": {"type": "string"}}) == [
        {"name": "title", "type": "string"}
    ]


def test_overlay_cas_receipt_composition_and_inherit_history() -> None:
    installation_pk = _seed_installation()
    with connect(SCOPE) as conn:
        first, etag1 = put_overlay(
            conn, SCOPE, installation_pk=str(installation_pk), target_kind="ObjectType",
            target_id="Product", body=_override(), if_match='"0"',
            idempotency_key=f"o1r3-{uuid.uuid4()}", actor="user:test",
        )
    assert first["ontologyRevision"] == 1
    assert etag1.startswith('"ontology-overlay-v1:1:')

    replay_key = f"o1r3-{uuid.uuid4()}"
    with connect(SCOPE) as conn:
        second, etag2 = put_overlay(
            conn, SCOPE, installation_pk=str(installation_pk), target_kind="ObjectType",
            target_id="Product", body={"mode": "inherit", "display_name": None,
            "visible_properties": None, "extended_properties": {}, "policies": None},
            if_match=etag1, idempotency_key=replay_key, actor="user:test",
        )
    with connect(SCOPE) as conn:
        replay, replay_etag = put_overlay(
            conn, SCOPE, installation_pk=str(installation_pk), target_kind="ObjectType",
            target_id="Product", body={"mode": "inherit", "display_name": None,
            "visible_properties": None, "extended_properties": {}, "policies": None},
            if_match=etag1, idempotency_key=replay_key, actor="user:test",
        )
        history = conn.execute(
            "SELECT ontology_revision,is_active,mode FROM ontology_overlay "
            "WHERE org_id=%s AND workspace_id=%s AND installation_pk=%s ORDER BY ontology_revision",
            (*SCOPE.key, installation_pk),
        ).fetchall()
    assert second == replay and etag2 == replay_etag
    assert [(r["ontology_revision"], r["is_active"], r["mode"]) for r in history] == [
        (1, False, "override"), (2, True, "inherit")
    ]


def test_overlay_stale_cas_and_history_mutation_fail_closed() -> None:
    installation_pk = _seed_installation()
    key = f"o1r3-{uuid.uuid4()}"
    with connect(SCOPE) as conn:
        _, etag = put_overlay(
            conn, SCOPE, installation_pk=str(installation_pk), target_kind="ObjectType",
            target_id="Product", body=_override(), if_match='"0"', idempotency_key=key,
            actor="user:test",
        )
    with pytest.raises(ApiError, match="revision changed") as caught:
        with connect(SCOPE) as conn:
            put_overlay(
                conn, SCOPE, installation_pk=str(installation_pk), target_kind="ObjectType",
                target_id="Product", body=_override(), if_match='"0"',
                idempotency_key=f"o1r3-{uuid.uuid4()}", actor="user:test",
            )
    assert caught.value.status_code == 412
    with pytest.raises(errors.ObjectNotInPrerequisiteState):
        with connect(SCOPE) as conn:
            conn.execute(
                "UPDATE ontology_overlay SET display_name='tampered' WHERE org_id=%s "
                "AND workspace_id=%s AND installation_pk=%s AND ontology_revision=1",
                (*SCOPE.key, installation_pk),
            )
    assert etag


def test_composer_applies_only_active_organization_overlay(monkeypatch: pytest.MonkeyPatch) -> None:
    installation_pk = _seed_installation()
    with connect(SCOPE) as conn:
        put_overlay(
            conn, SCOPE, installation_pk=str(installation_pk), target_kind="ObjectType",
            target_id="Product", body=_override(), if_match='"0"',
            idempotency_key=f"o1r3-{uuid.uuid4()}", actor="user:test",
        )
        from aos_api import ontology_compose

        monkeypatch.setattr(
            ontology_compose,
            "active_ecommerce_installation",
            lambda _conn, _scope: {
                "installation_pk": str(installation_pk), "installation_revision": 1,
                "installation_overlay_revision": "test-install-overlay",
                "lock_hash": "sha256:" + "1" * 64,
            },
        )
        rows = conn.execute(
            "SELECT id,name,description,published,properties FROM meta_object_type WHERE id='Product'"
        ).fetchall()
        composed, contract = filter_object_type_rows(conn, SCOPE, list(rows))
    assert composed[0]["name"] == "栖月汇商品"
    assert [prop["name"] for prop in composed[0]["properties"]] == ["title", "merchantTag"]
    assert contract["ontology_revision"] == 1
    assert contract["composed_schema_etag"].startswith("composed-schema-v1:sha256:")

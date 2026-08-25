"""W7-05 immutable Artifact family, Master/Variant and selection acceptance."""
from __future__ import annotations

import hashlib
import importlib.util
import uuid
from pathlib import Path

import pytest

from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractConflict,
    ProductionContractDependencyBlocked,
    ProductionContractNotFound,
)
from aos_api.aip_production_contracts import (
    ArtifactFamilyCandidateStatus,
    ArtifactFamilyTopologyStatus,
    AttachArtifactFamilyMemberRequest,
    ExactArtifactRef,
    ExactRevisionRef,
    RegisterArtifactFamilyRequest,
    SelectArtifactFamilyCandidateRequest,
)
from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
ISOLATION_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "test:w7-05"
MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic/versions/w7_003_artifact_family_master_variant.py"
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _headers(key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": SCOPE.org_id,
        "X-Project-Id": SCOPE.project_id,
        "Idempotency-Key": key,
    }


def _started_run(client) -> tuple[str, dict[str, str]]:
    suffix = uuid.uuid4().hex
    headers = _headers(f"w7-05-task-{suffix}")
    task_response = client.post(
        "/v1/aip/tasks",
        headers=headers,
        json={"type": "media", "title": f"W7-05 family {suffix}"},
    )
    assert task_response.status_code == 201, task_response.text
    task = task_response.json()
    plan_response = client.post(
        f"/v1/aip/tasks/{task['id']}/plans",
        headers={**headers, "Idempotency-Key": f"w7-05-plan-{suffix}"},
        json={
            "expectedTaskVersion": task["version"],
            "steps": [{"stepKey": "render", "title": "受控媒体渲染"}],
            "dependencies": [],
        },
    )
    assert plan_response.status_code == 201, plan_response.text
    plan = plan_response.json()
    planning = client.get(f"/v1/aip/tasks/{task['id']}", headers=headers).json()
    approved = client.post(
        f"/v1/aip/tasks/{task['id']}/plans/{plan['revision']}/approve",
        headers={**headers, "Idempotency-Key": f"w7-05-approve-{suffix}"},
        json={
            "expectedTaskVersion": planning["version"],
            "expectedContentHash": plan["contentHash"],
        },
    )
    assert approved.status_code == 200, approved.text
    approved_task = client.get(f"/v1/aip/tasks/{task['id']}", headers=headers).json()
    run_response = client.post(
        f"/v1/aip/tasks/{task['id']}/runs",
        headers={**headers, "Idempotency-Key": f"w7-05-run-{suffix}"},
        json={
            "planRevisionId": plan["id"],
            "expectedTaskVersion": approved_task["version"],
        },
    )
    assert run_response.status_code == 202, run_response.text
    return run_response.json()["id"], headers


def _record_family_artifact(
    run_id: str,
    family_id: str,
    revision: int,
    role: str,
    *,
    artifact_type: str = "media_asset",
) -> ExactArtifactRef:
    token = f"{family_id}:{revision}:{role}:{uuid.uuid4().hex}"
    content_hash = _hash(token)
    artifact_id = AipTaskStore().record_artifact(
        SCOPE,
        run_id,
        ACTOR,
        artifact_type,
        {
            "contentRef": f"memory://{token}",
            "contentHash": content_hash,
            "metadata": {
                "artifactFamily": {
                    "familyId": family_id,
                    "familyRevision": revision,
                    "role": role,
                    "profile": "STANDARD",
                    "platform": "douyin",
                    "renditionSpec": {"ratio": "9:16", "codec": "h264"},
                    "lineageRefs": [
                        {
                            "resourceType": "StageTemplateRevision",
                            "resourceId": "media-standard",
                            "revision": 1,
                            "contentHash": "a" * 64,
                        }
                    ],
                }
            },
        },
    )
    return ExactArtifactRef(artifactId=artifact_id, contentHash=content_hash)


def _family(client) -> tuple[AipProductionContractStore, str, ExactArtifactRef, str]:
    run_id, _ = _started_run(client)
    family_id = f"family-{uuid.uuid4().hex[:20]}"
    manifest = _record_family_artifact(
        run_id,
        family_id,
        1,
        "family_manifest",
        artifact_type="artifact_family_manifest",
    )
    store = AipProductionContractStore()
    store.register_artifact_family(
        SCOPE,
        ACTOR,
        f"register-{family_id}",
        RegisterArtifactFamilyRequest(familyId=family_id, manifestArtifact=manifest),
    )
    return store, family_id, manifest, run_id


def _attach(
    store: AipProductionContractStore,
    family_id: str,
    ref: ExactArtifactRef,
    version: int,
    *,
    master: ExactArtifactRef | None = None,
    supersedes: ExactArtifactRef | None = None,
):
    return store.attach_artifact_family_member(
        SCOPE,
        ACTOR,
        family_id,
        f"attach-{ref.artifact_id}-{ref.content_hash[:8]}-{version}",
        AttachArtifactFamilyMemberRequest(
            artifactRef=ref,
            expectedFamilyVersion=version,
            masterRef=master,
            supersedesRef=supersedes,
            reason="W7-05 controlled family acceptance",
        ),
    )


def test_family_conflict_selection_and_new_supersedes_preserve_history(client) -> None:
    store, family_id, _, run_id = _family(client)
    master = _record_family_artifact(run_id, family_id, 2, "master")
    variant_a = _record_family_artifact(run_id, family_id, 3, "variant")
    variant_b = _record_family_artifact(run_id, family_id, 4, "variant")
    _attach(store, family_id, master, 1)
    _attach(store, family_id, variant_a, 2, master=master)
    conflict = _attach(store, family_id, variant_b, 3, master=master)

    assert conflict.version == 4
    assert conflict.topology_status is ArtifactFamilyTopologyStatus.CONFLICT
    variant_group = next(
        item for item in conflict.candidate_groups if item.role.value == "variant"
    )
    assert variant_group.status is ArtifactFamilyCandidateStatus.CONFLICT
    assert {item.artifact_id for item in variant_group.candidates} == {
        variant_a.artifact_id,
        variant_b.artifact_id,
    }
    selected = store.select_artifact_family_candidate(
        SCOPE,
        ACTOR,
        family_id,
        f"select-{family_id}",
        SelectArtifactFamilyCandidateRequest(
            selectionKey=variant_group.selection_key,
            expectedFamilyVersion=4,
            candidateRefs=variant_group.candidates,
            selectedRef=variant_a,
            policyRef=ExactRevisionRef(
                resourceType="ArtifactFamilySelectionPolicyRevision",
                resourceId="editorial-choice",
                revision=1,
                contentHash="b" * 64,
            ),
            reason="reviewer selected the exact candidate snapshot",
        ),
    )
    assert selected.version == 5
    assert selected.topology_status is ArtifactFamilyTopologyStatus.CURRENT
    assert next(
        item for item in selected.candidate_groups if item.role.value == "variant"
    ).status is ArtifactFamilyCandidateStatus.SELECTED

    replacement = _record_family_artifact(run_id, family_id, 5, "variant")
    diverged = _attach(
        store,
        family_id,
        replacement,
        5,
        master=master,
        supersedes=variant_a,
    )
    assert diverged.version == 6
    assert diverged.topology_status is ArtifactFamilyTopologyStatus.CONFLICT
    assert len(diverged.selection_decisions) == 1
    assert {item.artifact_ref.artifact_id for item in diverged.members} == {
        master.artifact_id,
        variant_a.artifact_id,
        variant_b.artifact_id,
        replacement.artifact_id,
    }
    with connect(SCOPE) as conn:
        historical = conn.execute(
            """SELECT COUNT(*) AS count FROM aip_artifact_family_selection_revision
            WHERE org_id=%s AND project_id=%s AND family_id=%s""",
            (*SCOPE.key, family_id),
        ).fetchone()["count"]
    assert historical == 1


def test_family_rejects_stale_cas_hash_drift_and_cross_tenant_read(client) -> None:
    store, family_id, _, run_id = _family(client)
    master = _record_family_artifact(run_id, family_id, 2, "master")
    _attach(store, family_id, master, 1)
    with pytest.raises(ProductionContractConflict):
        _attach(store, family_id, _record_family_artifact(run_id, family_id, 3, "draft"), 1)
    with pytest.raises(ProductionContractDependencyBlocked, match="ARTIFACT_HASH_DRIFTED"):
        _attach(
            store,
            family_id,
            ExactArtifactRef(artifactId=master.artifact_id, contentHash="f" * 64),
            2,
        )
    with pytest.raises(ProductionContractNotFound):
        store.get_artifact_family(ISOLATION_SCOPE, family_id)


def test_family_api_lists_topology_without_external_effect(client) -> None:
    store, family_id, _, run_id = _family(client)
    master = _record_family_artifact(run_id, family_id, 2, "master")
    _attach(store, family_id, master, 1)
    headers = _headers(f"read-{family_id}")
    response = client.get(
        f"/v1/aip/production-contracts/artifact-families/{family_id}", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["familyId"] == family_id
    assert body["topologyStatus"] == "current"
    assert body["members"][0]["approvalStatus"] == "unknown"
    assert body["members"][0]["executionStatus"] == "unknown"
    listing = client.get(
        "/v1/aip/production-contracts/artifact-families", headers=headers
    )
    assert listing.status_code == 200
    assert family_id in {item["familyId"] for item in listing.json()["items"]}


def test_ordinary_artifact_path_remains_compatible_and_family_metadata_fails_closed(client) -> None:
    run_id, _ = _started_run(client)
    store = AipTaskStore()
    artifact_id = store.record_artifact(
        SCOPE,
        run_id,
        ACTOR,
        "analysis_report",
        {"contentRef": "memory://ordinary", "metadata": {"ordinary": True}},
    )
    with connect(SCOPE) as conn:
        row = conn.execute(
            """SELECT family_id,family_role FROM aip_artifact
            WHERE org_id=%s AND project_id=%s AND artifact_id=%s""",
            (*SCOPE.key, artifact_id),
        ).fetchone()
    assert row["family_id"] is None and row["family_role"] is None
    with pytest.raises(AipTaskTransitionBlocked, match="artifactFamily metadata is incomplete"):
        store.record_artifact(
            SCOPE,
            run_id,
            ACTOR,
            "media_asset",
            {"metadata": {"artifactFamily": {"familyId": "incomplete"}}},
        )


def test_w7_05_migration_chain_rls_append_only_and_downgrade_compatibility() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision: str | Sequence[str] | None = "w7_002"' in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "trg_aip_artifact_append_only_w7_003" in text
    assert "trg_aip_artifact_family_selection_append_only_w7_003" in text
    assert "OLD.current_revision, OLD.current_revision+1" in text
    assert text.rfind("CREATE OR REPLACE FUNCTION validate_aip_artifact_relation_w2") > text.find(
        "DROP COLUMN family_role"
    )
    spec = importlib.util.spec_from_file_location("w7_003", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "w7_003"

#!/usr/bin/env python3
"""Create signed-source EvalPacks and close W0B definition blockers in isolation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"
FIRST_INSTALLER = ROOT / "scripts/a0v_canonical_ecommerce_first_install.py"
RECOVERY_ROOT = ROOT.parent / ".aos-recovery-20260910"
STATE_ROOT = RECOVERY_ROOT / "state/a0v-capability-eval-w0b-authority"
ORG_ID = "org-org"
PROJECT_ID = "dev-project"
CANARY_ORG_ID = "dev-org"
CANARY_PROJECT_ID = "dev-project"
ACTOR = "a0v-capability-eval-w0b-authority"
CAPABILITY_IDS = (
    "material.collect",
    "strategy.plan",
    "copy.generate",
    "script.compose",
    "speech.synthesize",
    "video.compose",
    "content.review",
    "live.orchestrate",
    "platform.adapt",
    "performance.review",
)
SOURCE_RELATIVE = Path("solution.ecommerce.growth/1.4.0/content/agents/ecommerce-capability-catalog.json")
EXPECTED_RELATIVE = Path("solution.ecommerce.growth/1.4.0/evidence/bundle-evals.json")
POLICY_RELATIVE = Path("solution.ecommerce.growth/1.4.0/content/policies/aip6-runtime-policies.json")


class CapabilityAuthorityBlocked(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database-name")
    parser.add_argument("--docker-context", default="colima-aos-extension")
    parser.add_argument("--database-container", default="aos-a0v-recovery-pg")
    parser.add_argument("--state-dir", type=Path, default=STATE_ROOT)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def _load_installer() -> Any:
    spec = importlib.util.spec_from_file_location("a0v_first_install", FIRST_INSTALLER)
    if spec is None or spec.loader is None:
        raise CapabilityAuthorityBlocked("FIRST_INSTALLER_UNAVAILABLE", str(FIRST_INSTALLER))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_hash(value: Any) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def _scoped_factory(connect: Any):
    def scoped(_scope=None):
        return connect()
    return scoped


def _w0b_audit(connect: Any) -> dict[str, Any]:
    from aos_api.aip_capability_w0b_authority import (
        REQUIRED_RELATIONS,
        REQUIRED_STORE_METHODS,
        evaluate_w0b_relations,
    )
    from aos_api.aip_production_contract_store import AipProductionContractStore

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.relname AS relation,c.relrowsecurity AS rls,
                   c.relforcerowsecurity AS force_rls,
                   (SELECT count(*) FROM information_schema.columns i
                     WHERE i.table_schema='public' AND i.table_name=c.relname
                       AND i.column_name IN ('org_id','project_id')) AS tenant_key_columns,
                   (SELECT count(*) FROM pg_policy p WHERE p.polrelid=c.oid) AS policy_count
              FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
             WHERE n.nspname='public' AND c.relname=ANY(%s)
             ORDER BY c.relname
            """,
            (list(REQUIRED_RELATIONS),),
        ).fetchall()
    normalized = [dict(row) for row in rows]
    blockers = evaluate_w0b_relations(normalized)
    missing_methods = sorted(
        method for method in REQUIRED_STORE_METHODS
        if not callable(getattr(AipProductionContractStore, method, None))
    )
    blockers.extend(f"store_method_missing:{item}" for item in missing_methods)
    return {
        "ready": not blockers,
        "relationCount": len(normalized),
        "requiredRelationCount": len(REQUIRED_RELATIONS),
        "storeMethodCount": len(REQUIRED_STORE_METHODS) - len(missing_methods),
        "requiredStoreMethodCount": len(REQUIRED_STORE_METHODS),
        "blockers": sorted(blockers),
        "relations": normalized,
    }


def _counts(connect: Any) -> dict[str, int]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
              (SELECT count(*) FROM aip_eval_dataset_revision WHERE org_id=%s AND project_id=%s AND dataset_id LIKE 'a0v.ecommerce.capability.evalset.%%') AS datasets,
              (SELECT count(*) FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id LIKE 'a0v.ecommerce.capability.evalpack.%%') AS suites,
              (SELECT count(*) FROM aip_capability_revision WHERE capability_id=ANY(%s) AND revision=2) AS capability_revisions
            """,
            (ORG_ID, PROJECT_ID, ORG_ID, PROJECT_ID, list(CAPABILITY_IDS)),
        ).fetchone()
    return {key: int(row[key]) for key in row.keys()}


def _canary_counts(connect: Any) -> dict[str, int]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
              (SELECT count(*) FROM aip_eval_dataset_revision WHERE org_id=%s AND project_id=%s AND dataset_id LIKE 'a0v.ecommerce.capability.evalset.%%') AS datasets,
              (SELECT count(*) FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id LIKE 'a0v.ecommerce.capability.evalpack.%%') AS suites,
              (SELECT count(*) FROM aip_capability_binding WHERE org_id=%s AND project_id=%s) AS capability_bindings
            """,
            (CANARY_ORG_ID, CANARY_PROJECT_ID) * 3,
        ).fetchone()
    counts = {key: int(row[key]) for key in row.keys()}
    if any(counts.values()):
        raise CapabilityAuthorityBlocked("CANARY_AUTHORITY_NOT_EMPTY", str(counts))
    return counts


def _source_files(installer: Any) -> dict[str, Any]:
    verified = installer.verify_v4_inputs(
        build_dir=installer.DEFAULT_BUILD_DIR,
        build_receipt_path=installer.DEFAULT_BUILD_RECEIPT,
        qualification_receipt_path=installer.DEFAULT_QUALIFICATION_RECEIPT,
    )
    files = {
        "source": installer.DEFAULT_BUILD_DIR / SOURCE_RELATIVE,
        "expected": installer.DEFAULT_BUILD_DIR / EXPECTED_RELATIVE,
        "policy": installer.DEFAULT_BUILD_DIR / POLICY_RELATIVE,
    }
    if any(not path.is_file() for path in files.values()):
        raise CapabilityAuthorityBlocked("SIGNED_SOURCE_FILE_MISSING", str(files))
    return {
        "verification": verified,
        "files": files,
        "hashes": {name: _sha(path.read_bytes()) for name, path in files.items()},
    }


def _current_r1(registry: Any, capability_id: str) -> Any:
    item = registry.get(capability_id, 1)
    reasons = set(item.readiness_reasons or [])
    required = {"eval_pack_unavailable", "w0b_contracts_unavailable"}
    if item.lifecycle.value != "published" or not required <= reasons:
        raise CapabilityAuthorityBlocked("CAPABILITY_R1_BASELINE_DRIFT", capability_id)
    return item


def _build_pack(registry: Any, scope: Any, capability: Any, source: dict[str, Any]) -> Any:
    from aos_api.aip_contracts import ArtifactRef
    from aos_api.aip_eval_contracts import (
        AssetRevisionRef,
        AssetType,
        DatasetPiiState,
        DatasetRevisionRef,
        DatasetSourceKind,
        EvalCaseDefinition,
        EvalCaseKind,
        EvalDatasetManifest,
        EvalSuiteRevision,
        JudgeRevisionRef,
    )
    from aos_api.aip_eval_pack_registry import compute_eval_suite_hash

    cid = capability.capability_id
    dataset_id = f"a0v.ecommerce.capability.evalset.{cid}"
    suite_id = f"a0v.ecommerce.capability.evalpack.{cid}"
    input_ref = ArtifactRef(
        artifactId=f"signed-v4-capability-catalog:{cid}", artifactType="eval_input",
        revision="1.4.0", contentHash=source["hashes"]["source"],
    )
    expected_ref = ArtifactRef(
        artifactId=f"signed-v4-bundle-evals:{cid}", artifactType="eval_expected",
        revision="1.4.0", contentHash=source["hashes"]["expected"],
    )
    manifest = EvalDatasetManifest(
        sourceKind=DatasetSourceKind.ARTIFACT_SNAPSHOT,
        sourceId=str(SOURCE_RELATIVE),
        sourceRevision="1.4.0",
        sourceHash=source["hashes"]["source"],
        fieldsAllowlist=["capabilityId", "inputSchema", "outputSchema", "risk"],
        redactionReceipt=ArtifactRef(
            artifactId="signed-v4-aip6-runtime-policies",
            artifactType="redaction_receipt",
            revision="1.4.0",
            contentHash=source["hashes"]["policy"],
        ),
        piiState=DatasetPiiState.NONE,
        caseCount=1,
        capturedAt=datetime(2026, 9, 10, 0, 0, tzinfo=UTC),
    )
    dataset = DatasetRevisionRef(
        datasetId=dataset_id,
        revision=1,
        contentHash=_canonical_hash(manifest.model_dump(mode="json", by_alias=True)),
        sourceHash=source["hashes"]["source"],
        redactionPolicy=AssetRevisionRef(
            assetType=AssetType.POLICY,
            assetId="a0v.signed-v4.redaction-policy",
            revision="1",
            contentHash=source["hashes"]["policy"],
        ),
    )
    registry.register_dataset_revision(scope, dataset, manifest, actor=ACTOR)
    suite = EvalSuiteRevision(
        suiteId=suite_id,
        revision=1,
        contentHash="0" * 64,
        target=AssetRevisionRef(
            assetType=AssetType.SCENARIO,
            assetId=cid,
            revision="1",
            contentHash=capability.content_hash,
        ),
        dataset=dataset,
        judge=JudgeRevisionRef(
            judgeId="a0v.signed-v4.definition-contract-judge",
            revision=1,
            contentHash=source["hashes"]["expected"],
        ),
        cases=[EvalCaseDefinition(
            caseId="signed-v4-definition-contract",
            kind=EvalCaseKind.POSITIVE,
            inputArtifact=input_ref,
            expectedArtifact=expected_ref,
            timeoutMs=5000,
        )],
        gateThreshold=1.0,
    )
    suite = suite.model_copy(update={"content_hash": compute_eval_suite_hash(suite)})
    return registry.register_suite_revision(scope, suite, actor=ACTOR)


def _publish_r2(capability_registry: Any, capability: Any, suite: Any) -> Any:
    from aos_api.aip_agent_registry_contracts import (
        CapabilityReadiness,
        PublishCapabilityRevisionRequest,
        VersionedAssetRef,
    )
    from aos_api.aip_agent_registry_store import AipAgentRegistryStore
    from aos_api.aip_capability_w0b_authority import close_definition_reasons

    payload = capability.model_dump(
        mode="json", by_alias=True, exclude={"content_hash", "created_by", "created_at"}
    )
    reasons = close_definition_reasons(
        list(capability.readiness_reasons or []), eval_pack_ready=True, w0b_ready=True
    )
    payload.update(
        revision=2,
        parentRef=VersionedAssetRef(
            assetType="CapabilityRevision", assetId=capability.capability_id,
            revision=1, contentHash=capability.content_hash,
        ).model_dump(mode="json", by_alias=True),
        evalPackRef=VersionedAssetRef(
            assetType="EvalSuiteRevision", assetId=suite.suite_id,
            revision=suite.revision, contentHash=suite.content_hash,
        ).model_dump(mode="json", by_alias=True),
        readiness=CapabilityReadiness.BLOCKED.value if reasons else CapabilityReadiness.AVAILABLE.value,
        readinessReasons=reasons,
    )
    request = PublishCapabilityRevisionRequest(
        **payload, contentHash=AipAgentRegistryStore._hash(payload)
    )
    return capability_registry.publish(request, actor=ACTOR)


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.database_name != "aos_meta_head":
        raise CapabilityAuthorityBlocked("EXPLICIT_ISOLATED_DATABASE_REQUIRED", "aos_meta_head")
    installer = _load_installer()
    source = _source_files(installer)
    connect = installer.container_database_connect_factory(
        context=args.docker_context,
        container=args.database_container,
        database_name=args.database_name,
    )
    sys.path.insert(0, str(API_ROOT))
    try:
        w0b = _w0b_audit(connect)
        if not w0b["ready"]:
            raise CapabilityAuthorityBlocked("W0B_AUTHORITY_NOT_READY", str(w0b["blockers"]))
        before = _counts(connect)
        canary = _canary_counts(connect)
        if not args.apply:
            return {
                "outcome": "PREFLIGHT_GREEN", "mode": "preflight", "w0b": w0b,
                "sourceHashes": source["hashes"], "before": before, "canaryCounts": canary,
                "effects": {"mutationCount": 0, "providerInvocationCount": 0, "externalPublicationCount": 0},
            }
        backup = installer.create_pre_mutation_backup(
            context=args.docker_context, container=args.database_container,
            database_name=args.database_name, state_dir=args.state_dir,
        )
        from aos_api.aip_capability_registry import AipCapabilityRegistry
        from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
        from aos_api.tenant_scope import TenantScope

        scope = TenantScope(ORG_ID, PROJECT_ID)
        factory = _scoped_factory(connect)
        capabilities = AipCapabilityRegistry(connect_factory=factory)
        evals = AipEvalPackRegistry(connect_factory=factory)
        items = []
        for capability_id in CAPABILITY_IDS:
            current = _current_r1(capabilities, capability_id)
            suite = _build_pack(evals, scope, current, source)
            published = _publish_r2(capabilities, current, suite)
            if set(published.readiness_reasons) != {"provider_unknown", "aip7_route_authority_unavailable"}:
                raise CapabilityAuthorityBlocked("CAPABILITY_R2_REASON_DRIFT", capability_id)
            items.append({
                "capabilityId": capability_id, "revision": published.revision,
                "contentHash": published.content_hash, "evalPackRef": published.eval_pack_ref.model_dump(mode="json", by_alias=True),
                "readiness": published.readiness.value, "readinessReasons": published.readiness_reasons,
            })
        after = _counts(connect)
        _canary_counts(connect)
        mutation_count = sum(after[key] - before[key] for key in before)
        return {
            "outcome": "A0V_CAPABILITY_EVAL_W0B_AUTHORITY_GREEN", "mode": "apply",
            "scope": {"orgId": ORG_ID, "projectId": PROJECT_ID},
            "sourceTreeHash": source["verification"]["outputTreeHash"], "sourceHashes": source["hashes"],
            "w0b": w0b, "backup": backup, "before": before, "after": after,
            "canaryCounts": canary, "items": items,
            "effects": {"mutationCount": mutation_count, "providerInvocationCount": 0, "externalPublicationCount": 0},
        }
    finally:
        sys.path.remove(str(API_ROOT))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run(args)
    except CapabilityAuthorityBlocked as exc:
        result = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.code, "message": str(exc)}
        status = 2
    else:
        status = 0
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return status


if __name__ == "__main__":
    raise SystemExit(main())

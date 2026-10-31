"""Original Model/Route and Eval context in one caller-owned readonly snapshot.

No connection creation, transaction repair, signature proof or execution
authority. Snapshot observations must be locked/rechecked by the actual owner
before effects; these bytes cannot replace persisted signed report proof.
"""
from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import datetime

from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType, EvalRunStatus
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
from aos_api.aip_model_route_eval_subject_binding import (
    _fresh, canonical_eval_subject_binding_bytes,
)
from aos_api.aip_model_runtime_contracts import ModelEvalCandidate, ModelRouteRevision
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
from aos_api.aip_production_contracts import CreateEvalContractRequest
from aos_api.tenant_scope import TenantScope


def _json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _same_original_json(raw, parsed):
    if _json_text(raw) != _json_text(parsed):
        raise ValueError('original persisted JSON must not be normalized or lose fields')


def _original_model_payload(conn, scope, kind, identifier, item):
    # Only these three fixed original tables are admitted; caller input never
    # supplies SQL names. Re-reading retains raw JSON which legacy DTOs normalize.
    if kind not in {'registered_model', 'model_route', 'runtime_policy'}:
        raise ValueError('original model configuration kind required')
    row = conn.execute(
        f'SELECT payload FROM aip_{kind}_revision WHERE org_id=%s AND project_id=%s AND {kind}_id=%s AND revision=%s',
        (*scope.key, identifier, item.revision),
    ).fetchone()
    if row is None:
        raise ValueError('original model configuration payload unavailable')
    _same_original_json(row['payload'], item.model_dump(mode='json', by_alias=True))


def _boundary(conn, expected_database, scope):
    if (conn.autocommit is not False or conn.row_factory is not dict_row
            or conn.info.transaction_status != TransactionStatus.INTRANS):
        raise ValueError('existing caller readonly dict-row transaction required')
    row = conn.execute("""SELECT current_user AS role, current_database() AS database,
        current_setting('aos.org_id',true) AS org_id,
        current_setting('aos.project_id',true) AS project_id,
        current_setting('transaction_isolation') AS isolation,
        current_setting('transaction_read_only') AS read_only,
        transaction_timestamp() AS evaluated_at""").fetchone()
    if (row is None or row['role'] != 'aos_runtime' or row['database'] != expected_database
            or (row['org_id'], row['project_id']) != scope.key or row['read_only'] != 'on'
            or row['isolation'] not in {'repeatable read', 'serializable'}
            or not isinstance(row['evaluated_at'], datetime) or row['evaluated_at'].utcoffset() is None):
        raise ValueError('exact runtime database/tenant/readonly snapshot boundary required')
    return row['evaluated_at']


def read_eval_subject_context_bytes(
    conn, *, expected_database: str, scope: TenantScope, candidate: ModelEvalCandidate,
    run_id: str, expected_run_version: int, expected_run_status: EvalRunStatus,
) -> bytes:
    """Read exact original context, without asserting approval or signed execution.

    Every original store receives only nullcontext(conn). No store injection,
    role changes, commits, connection exit or implicit retry are offered here.
    """
    if (type(scope) is not TenantScope or type(expected_database) is not str
            or not expected_database or expected_database != expected_database.strip()
            or type(run_id) is not str or not 1 <= len(run_id) <= 200 or run_id != run_id.strip()
            or type(expected_run_version) is not int or expected_run_version < 1
            or type(expected_run_status) is not EvalRunStatus
            or type(candidate) is not ModelEvalCandidate
            or type(candidate.execution_allowed) is not bool or candidate.execution_allowed):
        raise ValueError('exact descriptive candidate, tenant, database and Run expectation required')
    claim = _fresh(candidate, ModelEvalCandidate)
    evaluated_at = _boundary(conn, expected_database, scope)

    payload = _read_original_eval_context_payload(
        conn, scope=scope, claim=claim, run_id=run_id,
        expected_run_version=expected_run_version, expected_run_status=expected_run_status,
        evaluated_at=evaluated_at,
    )
    if _boundary(conn, expected_database, scope) != evaluated_at:
        raise ValueError('caller transaction changed during original context reads')
    return _encode_eval_context_payload(payload)


def _read_original_eval_context_payload(
    conn, *, scope, claim, run_id, expected_run_version, expected_run_status, evaluated_at,
):
    """Fixed original DAO composition only; caller admission belongs to wrappers.

    A descriptive nonexecuting payload is never Source, approval or proof.
    No caller-supplied store, connection factory or boundary callback is used.
    """
    def same_connection(requested_scope):
        if type(requested_scope) is not TenantScope or requested_scope != scope:
            raise ValueError('original store requested another tenant')
        return nullcontext(conn)

    models = AipModelRuntimeStore(connect_factory=same_connection)
    authority = AipEvalAuthorityStore(connect_factory=same_connection)
    registry = AipEvalPackRegistry(connect_factory=same_connection)
    contracts = AipProductionContractStore(connect_factory=same_connection)
    matches = [item for item in models.list_eval_candidates(scope) if item == claim]
    if len(matches) != 1:
        raise ValueError('exact current source head candidate unavailable at snapshot')
    if claim.source_ref.asset_type == 'RegisteredModelRevision':
        source = models.get_model(scope, claim.source_ref.asset_id)
        dependencies, policy = (), None
        target_type = AssetType.REGISTERED_MODEL
        _original_model_payload(conn, scope, 'registered_model', source.registered_model_id, source)
    else:
        source = models.get_route(scope, claim.source_ref.asset_id)
        if type(source) is not ModelRouteRevision:
            raise ValueError('original complete Route source required')
        dependencies = [models.get_model(scope, item.model.asset_id) for item in source.candidates]
        policy = models.get_policy(scope, source.runtime_policy_ref.asset_id)
        target_type = AssetType.MODEL_ROUTE
        _original_model_payload(conn, scope, 'model_route', source.route_id, source)
        _original_model_payload(conn, scope, 'runtime_policy', policy.policy_id, policy)
        for dependency in dependencies:
            _original_model_payload(conn, scope, 'registered_model', dependency.registered_model_id, dependency)
    subject_bytes = canonical_eval_subject_binding_bytes(
        scope, claim, source, models=dependencies, runtime_policy=policy,
    )
    run_row = authority._run_row(conn, scope, run_id)
    if run_row is None:
        raise ValueError('original Run unavailable')
    run = authority._run_from_row(run_row)
    for column, field in [('target_ref', 'target'), ('dataset_ref', 'dataset'), ('judge_ref', 'judge'),
                          ('eval_contract_ref', 'eval_contract_ref'), ('subject_artifact_ref', 'subject_artifact_ref'),
                          ('stage_attempt_ref', 'stage_attempt_ref'), ('gate_policy_ref', 'gate_policy_ref')]:
        parsed = getattr(run, field)
        _same_original_json(run_row.get(column), parsed.model_dump(mode='json', by_alias=True) if parsed else None)
    target = AssetRevisionRef(
        assetType=target_type, assetId=claim.target_ref.asset_id,
        revision=str(claim.target_ref.revision), contentHash=claim.target_ref.content_hash,
    )
    if ((run.tenant.org_id, run.tenant.project_id) != scope.key
            or run.run_id != run_id or run.version != expected_run_version
            or run.status is not expected_run_status or run.target != target or run.eval_contract_ref is None):
        raise ValueError('exact original Run tenant/version/status/target/Contract required')
    # Eval refs intentionally use string revision encoding, unlike VersionedAssetRef.
    revision = run.suite_ref.revision
    if not revision.isascii() or not revision.isdecimal() or str(int(revision)) != revision or int(revision) < 1:
        raise ValueError('canonical positive EvalSuite revision required')
    suite_row = registry._suite_row(conn, scope, run.suite_ref.asset_id, int(revision))
    if suite_row is None:
        raise ValueError('original Suite unavailable')
    suite = registry._suite_from_row(suite_row)
    suite_json = suite.model_dump(mode='json', by_alias=True)
    for column, field in [('target_ref', 'target'), ('dataset_ref', 'dataset'), ('judge_ref', 'judge'), ('cases', 'cases')]:
        _same_original_json(suite_row[column], suite_json[field])
    if (suite.suite_id != run.suite_ref.asset_id or str(suite.revision) != revision
            or suite.content_hash != run.suite_ref.content_hash or compute_eval_suite_hash(suite) != suite.content_hash
            or suite.target != target or suite.dataset != run.dataset or suite.judge != run.judge):
        raise ValueError('original Suite hash/target/Dataset/Judge drifted')
    dataset_row = authority._dataset_row(conn, scope, suite.dataset.dataset_id, suite.dataset.revision)
    if dataset_row is None:
        raise ValueError('original Dataset unavailable')
    dataset = authority._dataset_from_row(dataset_row)
    _same_original_json(dataset_row['redaction_policy_ref'], dataset.redaction_policy.model_dump(mode='json', by_alias=True))
    if dataset != suite.dataset:
        raise ValueError('original complete Dataset reference drifted')
    ref = run.eval_contract_ref
    head = conn.execute("""SELECT current_revision FROM aip_eval_contract_head
        WHERE org_id=%s AND project_id=%s AND contract_id=%s""", (*scope.key, ref.resource_id)).fetchone()
    if head is None or head['current_revision'] != ref.revision:
        raise ValueError('current original EvalContract head required')
    contract = contracts.get_eval_contract(scope, ref.resource_id, ref.revision, conn=conn)
    contract_body = CreateEvalContractRequest.model_validate({
        name: getattr(contract, name) for name in CreateEvalContractRequest.model_fields
    })
    contract_row = conn.execute('''SELECT * FROM aip_eval_contract_revision
        WHERE org_id=%s AND project_id=%s AND contract_id=%s AND revision=%s''',
        (*scope.key, ref.resource_id, ref.revision)).fetchone()
    if contract_row is None:
        raise ValueError('original Contract payload unavailable')
    contract_json = contract_body.model_dump(mode='json', by_alias=True)
    for field, definition in CreateEvalContractRequest.model_fields.items():
        _same_original_json(contract_row[field], contract_json[definition.alias or field])
    suite_ref = contract.suite_ref
    if ((contract.tenant.org_id, contract.tenant.project_id) != scope.key
            or contract.contract_id != ref.resource_id or contract.revision != ref.revision
            or contract.content_hash != ref.content_hash
            or canonical_hash(contract_body.model_dump(mode='json', by_alias=True)) != ref.content_hash
            or contract.lifecycle.value != 'frozen' or contract.readiness.value != 'ready' or contract.blockers
            or suite_ref.resource_type != 'EvalSuiteRevision' or suite_ref.resource_id != suite.suite_id
            or suite_ref.revision != suite.revision or suite_ref.content_hash != suite.content_hash):
        raise ValueError('exact frozen ready original Contract and Suite binding required')
    payload = {
        'schemaVersion': 'aos.model-route-eval-context/v1',
        'subject': json.loads(subject_bytes.split(b'\n', 1)[1]),
        'run': run.model_dump(mode='json', by_alias=True),
        'suite': suite.model_dump(mode='json', by_alias=True),
        'dataset': dataset.model_dump(mode='json', by_alias=True),
        'contract': contract.model_dump(mode='json', by_alias=True),
        'snapshotReadAt': evaluated_at.isoformat(), 'executionAllowed': False,
    }
    return payload


def _encode_eval_context_payload(payload):
    return b'AOS-MODEL-ROUTE-EVAL-CONTEXT-v1\n' + json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False,
    ).encode('utf-8')

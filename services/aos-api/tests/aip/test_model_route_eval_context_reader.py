"""Offline SQL protocol tests using original stores, never native authority proof."""
import json
from types import SimpleNamespace
from datetime import timedelta

import pytest
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from aos_api.aip_eval_contracts import EvalRunStatus, EvalSuiteRevision
from aos_api.aip_eval_pack_registry import compute_eval_suite_hash
from aos_api.aip_model_route_eval_context_reader import read_eval_subject_context_bytes
from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
from aos_api.aip_production_contracts import CreateEvalContractRequest
from test_model_route_eval_subject_binding import (
    SCOPE, TENANT, NOW, inputs, candidate, model,
)


class Rows:
    def __init__(self, rows): self.rows = rows
    def fetchone(self): return self.rows[0] if self.rows else None
    def fetchall(self): return list(self.rows)


class SQLSnapshot:
    """Returns fixed rows only; real original store/readiness code still runs."""
    def __init__(self, *, route=True):
        source, models, policy = inputs()
        if not route: source, models, policy = model(lifecycle='draft'), [], None
        self.source, self.models, self.policy = source, models, policy
        self.claim = candidate(source)
        self.autocommit = False
        self.row_factory = dict_row
        self.info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        self.context = dict(role='aos_runtime', org_id=SCOPE.org_id, project_id=SCOPE.project_id,
                            database='unit_only', isolation='repeatable read', read_only='on', evaluated_at=NOW)
        self.calls = []
        self.missing = None
        self.payload_tamper = False
        self.end_context = None
        self.sql_failure = None
        self.head_version = 7
        target = {'assetType': 'model_route' if route else 'registered_model',
                  'assetId': self.claim.target_ref.asset_id,
                  'revision': str(self.claim.target_ref.revision), 'contentHash': self.claim.target_ref.content_hash}
        dataset = dict(datasetId='dataset', revision=1, contentHash='a'*64, sourceHash='b'*64,
                       redactionPolicy=dict(assetType='policy', assetId='redaction', revision='1', contentHash='c'*64))
        judge = dict(judgeId='judge', revision=1, contentHash='d'*64, modelRoute=None)
        suite = EvalSuiteRevision(suiteId='suite', revision=1, contentHash='a'*64,
            target=target, dataset=dataset, judge=judge, cases=[dict(caseId='case', kind='positive',
            inputArtifact=dict(artifactId='input', artifactType='eval_input', revision='1', contentHash='e'*64), timeoutMs=1000)],
            gateThreshold=1.0)
        suite = suite.model_copy(update={'content_hash': compute_eval_suite_hash(suite)})
        self.suite = dict(suite_id=suite.suite_id, revision=1, content_hash=suite.content_hash,
            target_ref=suite.target.model_dump(mode='json', by_alias=True),
            dataset_ref=suite.dataset.model_dump(mode='json', by_alias=True),
            judge_ref=suite.judge.model_dump(mode='json', by_alias=True),
            cases=[c.model_dump(mode='json', by_alias=True) for c in suite.cases], gate_threshold=1.0)
        self.dataset = dict(dataset_id='dataset', revision=1, content_hash='a'*64, source_hash='b'*64,
                            redaction_policy_ref=dataset['redactionPolicy'])
        self.publication = dict(event_id='pub', publication_id='publication', target_ref=target,
            event_type='published', release_gate_decision_id='gate', reason_hash='a'*64, actor='unit-test', occurred_at=NOW)
        pub_hash = canonical_hash(AipProductionContractStore._publication_snapshot(self.publication))
        request = CreateEvalContractRequest(
            suiteRef=dict(resourceType='EvalSuiteRevision', resourceId='suite', revision=1, contentHash=suite.content_hash),
            publicationRef=dict(resourceType='PublicationEvent', resourceId='pub', revision=1, contentHash=pub_hash),
            releaseGateRef=dict(resourceType='ReleaseGateDecision', resourceId='gate', revision=1, contentHash='f'*64),
            artifactSchemaRef=dict(resourceType='ArtifactSchema', resourceId='schema', revision='1', authority='unit-test'),
            severityThresholds={'quality': 1.0}, gatePolicy={}, returnMapping={}, overridePolicy={})
        body = request.model_dump(mode='json', by_alias=True)
        self.contract = dict(contract_id='contract', revision=1, content_hash=canonical_hash(body), lifecycle='frozen',
            suite_ref=body['suiteRef'], publication_ref=body['publicationRef'], release_gate_ref=body['releaseGateRef'],
            artifact_schema_ref=body['artifactSchemaRef'], severity_thresholds=body['severityThresholds'],
            gate_policy=body['gatePolicy'], return_mapping=body['returnMapping'], override_policy=body['overridePolicy'],
            created_by='unit-test', created_at=NOW)
        self.contract_head = dict(current_revision=1, version=2)
        self.gate = dict(status='passed', decision_hash='f'*64)
        self.run = dict(org_id=SCOPE.org_id, project_id=SCOPE.project_id, run_id='run', suite_id='suite',
            suite_revision=1, suite_hash=suite.content_hash,
            eval_contract_ref=dict(resourceType='EvalContractRevision', resourceId='contract', revision=1,
                                   contentHash=self.contract['content_hash']),
            target_ref=target, dataset_ref=dataset, judge_ref=judge, status='running',
            idempotency_key='unit-only', created_by='unit-test', created_at=NOW, started_at=NOW, finished_at=None, version=2)

    def execute(self, sql, params=()):
        sql = ' '.join(sql.split())
        assert sql.startswith('SELECT '), 'reader may never mutate or repair a transaction'
        self.calls.append((sql, params))
        if 'current_user' in sql:
            if sum('current_user' in s for s, _ in self.calls) > 1 and self.end_context:
                return Rows([{**self.context, **self.end_context}])
            return Rows([dict(self.context)])
        assert params[:2] == SCOPE.key, 'all original reads must retain both tenant keys'
        if self.sql_failure and self.sql_failure in sql: raise RuntimeError('known SELECT failure')
        if self.missing and self.missing in sql: return Rows([])
        if 'UNION ALL' in sql:
            return Rows([dict(kind='model_route' if self.claim.source_ref.asset_type == 'ModelRouteRevision' else 'registered_model',
                version=self.head_version, asset_id=self.claim.source_ref.asset_id,
                revision=self.source.revision, payload=self.source.model_dump(mode='json', by_alias=True))])
        if 'aip_eval_run' in sql: return Rows([dict(self.run)])
        if 'aip_eval_suite_revision' in sql: return Rows([dict(self.suite)])
        if 'aip_eval_dataset_revision' in sql: return Rows([dict(self.dataset)])
        if 'aip_eval_contract_head' in sql: return Rows([dict(self.contract_head)])
        if 'aip_eval_contract_revision' in sql: return Rows([dict(self.contract)])
        if 'aip_publication_event' in sql: return Rows([dict(self.publication)])
        if 'aip_release_gate_decision' in sql: return Rows([dict(self.gate)])
        for kind, objects in [('model_route', [self.source]), ('registered_model', [self.source, *self.models]),
                              ('runtime_policy', [self.policy] if self.policy else [])]:
            if f'aip_{kind}_' in sql:
                for item in objects:
                    name = getattr(item, 'route_id', getattr(item, 'registered_model_id', getattr(item, 'policy_id', None)))
                    if name == params[2]:
                        payload = item.model_dump(mode='json', by_alias=True)
                        if self.payload_tamper and kind == 'model_route':
                            payload['candidates'][0]['model']['revision'] = True
                        return Rows([dict(current_revision=item.revision)] if '_head' in sql else
                                    [dict(payload=payload)])
        raise AssertionError('unexpected SQL: ' + sql)

    def commit(self): raise AssertionError('must not commit')
    def rollback(self): raise AssertionError('must not rollback')
    def close(self): raise AssertionError('must not close caller connection')
    def __enter__(self): raise AssertionError('must not enter caller connection context')
    def __exit__(self, *args): raise AssertionError('must not exit caller connection context')


def read(conn, **changes):
    args = dict(expected_database='unit_only', scope=SCOPE, candidate=conn.claim,
                run_id='run', expected_run_version=2, expected_run_status=EvalRunStatus.RUNNING)
    args.update(changes)
    return read_eval_subject_context_bytes(conn, **args)


@pytest.mark.parametrize('route', [False, True])
def test_original_stores_share_one_readonly_snapshot_and_complete_context(route):
    conn = SQLSnapshot(route=route)
    raw = read(conn)
    payload = json.loads(raw.split(b'\n', 1)[1])
    assert payload['executionAllowed'] is False
    assert payload['run']['runId'] == 'run'
    assert payload['suite']['cases'][0]['caseId'] == 'case'
    assert len(payload['subject']['models']) == (2 if route else 0)
    assert len(conn.calls) > 10
    assert conn.info.transaction_status == TransactionStatus.INTRANS


@pytest.mark.parametrize('field,value', [('database', 'other'), ('role', 'aos_app'), ('read_only', 'off'),
    ('isolation', 'read committed'), ('org_id', 'dev-org'), ('project_id', 'other')])
def test_context_boundary_rejected_before_original_data_reads(field, value):
    conn = SQLSnapshot(); conn.context[field] = value
    with pytest.raises(ValueError): read(conn)
    assert len(conn.calls) == 1


@pytest.mark.parametrize('change', ['autocommit', 'row_factory', 'idle', 'run_version_bool', 'run_status_string', 'database_blank'])
def test_invalid_native_call_boundary_has_no_queries(change):
    conn = SQLSnapshot(); args = {}
    if change == 'autocommit': conn.autocommit = True
    elif change == 'row_factory': conn.row_factory = None
    elif change == 'idle': conn.info.transaction_status = TransactionStatus.IDLE
    elif change == 'run_version_bool': args['expected_run_version'] = True
    elif change == 'run_status_string': args['expected_run_status'] = 'running'
    else: args['expected_database'] = ''
    with pytest.raises(ValueError): read(conn, **args)
    assert not conn.calls


@pytest.mark.parametrize('change', ['head', 'run_version', 'run_status', 'target', 'suite_hash', 'dataset',
    'judge', 'contract_ref', 'contract_head', 'contract_hash', 'contract_frozen', 'publication_revoked', 'gate_invalid',
    'run_tenant', 'contract_suite'])
def test_exact_persisted_context_drift_fails_closed(change):
    conn = SQLSnapshot()
    if change == 'head': conn.head_version += 1
    elif change == 'run_version': conn.run['version'] += 1
    elif change == 'run_status': conn.run['status'] = 'unknown'
    elif change == 'target': conn.run['target_ref'] = {**conn.run['target_ref'], 'contentHash': 'b'*64}
    elif change == 'suite_hash': conn.suite['content_hash'] = 'b'*64
    elif change == 'dataset': conn.dataset['source_hash'] = 'c'*64
    elif change == 'judge': conn.suite['judge_ref'] = {**conn.suite['judge_ref'], 'judgeId': 'other'}
    elif change == 'contract_ref': conn.run['eval_contract_ref'] = None
    elif change == 'contract_head': conn.contract_head['current_revision'] = 2
    elif change == 'contract_hash': conn.contract['gate_policy'] = {'changed': True}
    elif change == 'contract_frozen': conn.contract['lifecycle'] = 'draft'
    elif change == 'publication_revoked': conn.publication['event_type'] = 'revoked'
    elif change == 'gate_invalid': conn.gate['status'] = 'invalidated'
    elif change == 'run_tenant': conn.run['org_id'] = 'dev-org'
    else: conn.contract['suite_ref'] = {**conn.contract['suite_ref'], 'resourceId': 'other'}
    with pytest.raises((ValueError, RuntimeError)): read(conn)


@pytest.mark.parametrize('table', ['aip_eval_run', 'aip_eval_suite_revision', 'aip_eval_dataset_revision',
    'aip_eval_contract_head', 'aip_eval_contract_revision'])
def test_missing_original_records_never_return_partial_context(table):
    conn = SQLSnapshot(); conn.missing = table
    with pytest.raises((ValueError, RuntimeError)): read(conn)


@pytest.mark.parametrize('change', ['payload_bool', 'run_ref_bool', 'run_ref_space', 'suite_bool', 'contract_bool'])
def test_legacy_normalization_cannot_hide_changed_persisted_json(change):
    conn = SQLSnapshot()
    if change == 'payload_bool': conn.payload_tamper = True
    elif change == 'run_ref_bool': conn.run['dataset_ref']['revision'] = True
    elif change == 'run_ref_space': conn.run['target_ref']['revision'] = ' 3 '
    elif change == 'suite_bool': conn.suite['cases'][0]['required'] = 1
    else: conn.contract['severity_thresholds']['quality'] = True
    with pytest.raises(ValueError, match='persisted JSON'): read(conn)


@pytest.mark.parametrize('change', [{'role': 'aos_app'}, {'evaluated_at': NOW + timedelta(seconds=1)}])
def test_caller_boundary_must_still_match_when_context_is_returned(change):
    conn = SQLSnapshot(); conn.end_context = change
    with pytest.raises(ValueError): read(conn)


def test_original_select_failure_does_not_retry_or_return_partial_context():
    conn = SQLSnapshot(); conn.sql_failure = 'aip_eval_run'
    with pytest.raises(RuntimeError, match='known SELECT failure'): read(conn)
    assert sum('aip_eval_run' in sql for sql, _ in conn.calls) == 1


def test_original_contract_store_explicit_connection_never_uses_its_factory():
    conn = SQLSnapshot()
    def forbidden_factory(*args, **kwargs):
        raise AssertionError('explicit conn must bypass even the factory')
    contract = AipProductionContractStore(connect_factory=forbidden_factory).get_eval_contract(
        SCOPE, 'contract', 1, conn=conn)
    assert contract.readiness.value == 'ready' and not contract.blockers


def test_missing_run_contract_is_explicitly_rejected_before_contract_lookup():
    conn = SQLSnapshot(); conn.run['eval_contract_ref'] = None
    with pytest.raises(ValueError, match='Run tenant/version/status/target/Contract'):
        read(conn)
    assert not any('aip_eval_contract_' in sql for sql, _ in conn.calls)


@pytest.mark.parametrize('route,expected,count',[
    (False,'593b2a9d9d5f4870424401000075a79cfc48ccf96a24648ea5ddb0b740bbeb4c',17),
    (True,'a0bbe2701cd64e565d93fbf1f8d3d7bb5dfb890634704b7379b10c15792a0b4a',26)])
@pytest.mark.parametrize('isolation',['repeatable read','serializable'])
def test_shared_context_refactor_keeps_preedit_full_bytes_and_sql_count(route,expected,count,isolation):
    import hashlib
    c=SQLSnapshot(route=route);c.context['isolation']=isolation
    assert hashlib.sha256(read(c)).hexdigest()==expected
    assert len(c.calls)==count


def test_shared_original_payload_has_fixed_original_stores_and_no_authority():
    import inspect
    from aos_api import aip_model_route_eval_context_reader as reader
    names=set(inspect.signature(reader._read_original_eval_context_payload).parameters)
    assert names=={'conn','scope','claim','run_id','expected_run_version','expected_run_status','evaluated_at'}
    c=SQLSnapshot();payload=reader._read_original_eval_context_payload(c,scope=SCOPE,claim=c.claim,
        run_id='run',expected_run_version=2,expected_run_status=EvalRunStatus.RUNNING,evaluated_at=NOW)
    assert payload['executionAllowed'] is False and payload['run']['runId']=='run'
    assert all(sql.startswith('SELECT ') for sql,_ in c.calls)
    assert not any('current_user' in sql for sql,_ in c.calls),'caller admission stays in fixed public wrappers'
    assert reader._encode_eval_context_payload(payload)==read(SQLSnapshot())

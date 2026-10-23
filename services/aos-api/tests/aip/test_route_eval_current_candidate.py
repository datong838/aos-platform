"""Pure caller/SQL protocol tests, not actual PG locking or execution proof."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
import json
from types import SimpleNamespace
import unittest

from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row, tuple_row

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_model_runtime_contracts import (
    ModelModality, ModelRouteRevision, ModelRuntimeLifecycle, RegisteredModelRevision, RouteStrategy,
)
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore, ModelRuntimeConflict, canonical_hash, evaluation_candidate_ref,
)
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('org-org', 'dev-project')
NOW = datetime(2026, 10, 23, tzinfo=UTC)


def ref(kind, name, digest='a' * 64, revision=1):
    return VersionedAssetRef(assetType=kind, assetId=name, revision=revision, contentHash=digest)


def rehash(item):
    body = item.model_dump(mode='json', by_alias=True)
    return item.model_copy(update={'content_hash': canonical_hash(
        {k: v for k, v in body.items() if k not in AipModelRuntimeStore._META_FIELDS})})


def route(strategy=RouteStrategy.FAILOVER, lifecycle='validated', gate=False):
    weighted = strategy is RouteStrategy.WEIGHTED
    return rehash(ModelRouteRevision(tenant={'orgId': 'org-org', 'projectId': 'dev-project'},
        routeId='synthetic-route', revision=1, contentHash='0' * 64,
        taskTypes=['synthetic.read'], requiredInputModality='text', requiredOutputModality='text',
        requiredCapabilities=['text'], candidates=[
            {'model': ref('RegisteredModelRevision', 'model-a'), 'weight': 50 if weighted else 100},
            {'model': ref('RegisteredModelRevision', 'model-b', 'b' * 64), 'weight': 50 if weighted else 100}],
        strategy=strategy, runtimePolicyRef=ref('RuntimePolicyRevision', 'policy'),
        evalGateRef=ref('EvalGateDecision', 'old-gate') if gate else None,
        lifecycle=lifecycle, createdBy='synthetic-source-author', createdAt=NOW))


def model():
    return rehash(RegisteredModelRevision(tenant={'orgId': 'org-org', 'projectId': 'dev-project'},
        registeredModelId='synthetic-model', revision=1, contentHash='0' * 64,
        provider=ref('ProviderInstanceRevision', 'provider'), providerModelId='synthetic-model',
        inputModalities=['text'], outputModalities=['text'], capabilities=['text'], contextWindow=1024,
        quotaPolicyRef=ref('QuotaPolicyRevision', 'quota'), budgetPolicyRef=ref('BudgetPolicyRevision', 'budget'),
        priceSnapshotRef=ref('ModelPriceSnapshotRevision', 'price'), lifecycle='validated',
        createdBy='synthetic-source-author', createdAt=NOW))


def case(item=None):
    item = item if item is not None else route()
    is_route = type(item) is ModelRouteRevision
    source = evaluation_candidate_ref(item).model_copy(update={'content_hash': item.content_hash})
    target = evaluation_candidate_ref(item.model_copy(update={
        'revision': item.revision + 1, 'lifecycle': ModelRuntimeLifecycle.ACTIVE, 'eval_gate_ref': None}))
    row = dict(kind='model_route' if is_route else 'registered_model', version=7,
        asset_id=item.route_id if is_route else item.registered_model_id, revision=item.revision,
        content_hash=item.content_hash, lifecycle=item.lifecycle.value,
        payload=item.model_dump(mode='json', by_alias=True))
    return source, target, row


class Result:
    def __init__(self, row=None, rows=None): self.row, self.rows = row, rows
    def fetchone(self): return self.row
    def fetchall(self): return self.rows


class FakeConnection:
    def __init__(self, row):
        self.row = row
        self.rows = []
        self.queries = []
        self.autocommit = False
        self.info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        self.row_factory = dict_row
        self.context = dict(role='aos_runtime', org_id=SCOPE.org_id,
                            project_id=SCOPE.project_id, isolation='serializable')
        self.commits = self.rollbacks = self.closes = 0

    def execute(self, query, params=None):
        self.queries.append((query, params))
        if 'current_user AS role' in query:
            return Result(row=self.context)
        if 'UNION ALL' in query:
            return Result(rows=self.rows)
        if 'FOR UPDATE OF h' in query and ('aip_model_route_head' in query or 'aip_registered_model_head' in query):
            return Result(row=self.row)
        raise AssertionError('unexpected SQL in pure fixture')

    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def close(self): self.closes += 1


class RouteCurrentCandidateTests(unittest.TestCase):
    def setUp(self):
        self.fallback_calls = []
        def forbidden(*args, **kwargs):
            self.fallback_calls.append(True)
            raise AssertionError('new connection forbidden')
        self.store = AipModelRuntimeStore(connect_factory=forbidden)

    def read(self, source=None, target=None, conn=None, expected=7, scope=SCOPE):
        s, t, row = case()
        return self.store.require_current_route_eval_candidate_for_update(
            conn if conn is not None else FakeConnection(row), scope,
            source if source is not None else s, target if target is not None else t,
            expected_head_version=expected)

    def test_01_all_original_strategies_and_weights(self):
        self.assertEqual(len(RouteStrategy), 4)
        for strategy in RouteStrategy:
            with self.subTest(strategy=strategy):
                s, t, row = case(route(strategy))
                result = self.read(s, t, FakeConnection(row))
                self.assertEqual(result.source_ref, s)
                self.assertEqual(result.target_ref, t)
                self.assertIs(result.execution_allowed, False)

    def test_02_draft_and_validated_are_nonexecuting(self):
        for lifecycle in ('draft', 'validated'):
            s, t, row = case(route(lifecycle=lifecycle))
            result = self.read(s, t, FakeConnection(row))
            self.assertEqual(result.source_lifecycle, lifecycle)
            self.assertEqual(result.expected_head_version, 7)
            self.assertIs(result.execution_allowed, False)

    def test_03_missing_stale_and_invalid_head_rows(self):
        s, t, row = case()
        changes = [None, {'version': 8}, {'version': True}, {'version': '7'},
                   {'revision': True}, {'revision': '1'}, {'revision': 2},
                   {'lifecycle': 'active'}, {'lifecycle': 'revoked'}, {'kind': 'other'}]
        for change in changes:
            value = None if change is None else row | change
            with self.subTest(change=change), self.assertRaises(ModelRuntimeConflict):
                self.read(s, t, FakeConnection(value))

    def test_04_payload_hash_and_column_lifecycle_must_agree(self):
        s, t, row = case()
        for key, value in [('taskTypes', ['changed']), ('contentHash', 'f' * 64),
                           ('routeId', 'other'), ('revision', 2), ('lifecycle', 'draft')]:
            altered = deepcopy(row)
            altered['payload'][key] = value
            with self.subTest(key=key), self.assertRaises(ModelRuntimeConflict):
                self.read(s, t, FakeConnection(altered))

    def test_05_target_is_original_next_active_candidate(self):
        for gate in (False, True):
            s, t, row = case(route(gate=gate))
            result = self.read(s, t, FakeConnection(row))
            self.assertEqual(result.target_ref, t)
            with self.assertRaises(ModelRuntimeConflict):
                self.read(s, t.model_copy(update={'content_hash': 'f' * 64}), FakeConnection(row))
        self.assertEqual(case(route(gate=False))[1], case(route(gate=True))[1])
        self.assertNotEqual(case(route(gate=False))[0], case(route(gate=True))[0])

    def test_06_bad_input_shape_is_rejected_before_sql(self):
        s, t, row = case()
        for source, target, head, scope in [
            (s.model_copy(update={'asset_type': 'RegisteredModelRevision'}), t, 7, SCOPE),
            (s, t.model_copy(update={'asset_id': 'other'}), 7, SCOPE),
            (s, t.model_copy(update={'revision': 3}), 7, SCOPE),
            (s, t, True, SCOPE), (s, t, 0, SCOPE), (s, t, '7', SCOPE), (s, t, 7, object())]:
            c = FakeConnection(row)
            with self.subTest(head=head), self.assertRaises(ModelRuntimeConflict):
                self.read(source, target, c, expected=head, scope=scope)
            self.assertEqual(c.queries, [])

    def test_07_constructed_invalid_refs_do_not_bypass_validation(self):
        s, t, row = case()
        for change in ({'revision': True}, {'revision': 0}, {'content_hash': 'bad'},
                       {'content_hash': None}, {'asset_id': ''}):
            bad = s.model_copy(update=change)
            c = FakeConnection(row)
            with self.subTest(change=change), self.assertRaises(ModelRuntimeConflict):
                self.read(bad, t, c)
            self.assertEqual(c.queries, [])

    def test_08_exact_caller_context_before_head_lock(self):
        s, t, row = case()
        for change in ({'role': 'postgres'}, {'org_id': 'dev-org'},
                       {'project_id': 'other'}, {'isolation': 'read committed'}):
            c = FakeConnection(row)
            c.context.update(change)
            with self.subTest(change=change), self.assertRaises(ModelRuntimeConflict):
                self.read(s, t, c)
            self.assertEqual(len(c.queries), 1)
            self.assertNotIn('FOR UPDATE', c.queries[0][0])

    def test_09_caller_must_own_existing_transaction_and_dict_rows(self):
        s, t, row = case()
        for field, value in [('autocommit', True), ('autocommit', 0),
                             ('info', SimpleNamespace(transaction_status=TransactionStatus.IDLE)),
                             ('row_factory', tuple_row), ('row_factory', None)]:
            c = FakeConnection(row)
            setattr(c, field, value)
            with self.subTest(field=field, value=value), self.assertRaises(ModelRuntimeConflict):
                self.read(s, t, c)
            self.assertEqual(c.queries, [])

    def test_10_no_fallback_or_caller_transaction_ending(self):
        s, t, row = case()
        c = FakeConnection(row)
        self.read(s, t, c)
        self.assertEqual(self.fallback_calls, [])
        self.assertEqual((c.commits, c.rollbacks, c.closes), (0, 0, 0))
        self.assertEqual(len(c.queries), 2)
        self.assertIn('aip_model_route_head', c.queries[1][0])
        self.assertIn('FOR UPDATE OF h', c.queries[1][0])
        self.assertEqual(c.queries[1][1], (*SCOPE.key, s.asset_id, s.revision))
        self.assertTrue(all(q.lstrip().startswith('SELECT ') for q, _ in c.queries))

    def test_11_order_weights_policy_and_required_semantics_are_hash_bound(self):
        item = route(RouteStrategy.WEIGHTED)
        s, old_target, _ = case(item)
        changes = [dict(candidates=list(reversed(item.candidates))),
                   dict(candidates=[item.candidates[0].model_copy(update={'weight': 60}),
                                    item.candidates[1].model_copy(update={'weight': 40})]),
                   dict(runtime_policy_ref=ref('RuntimePolicyRevision', 'other-policy')),
                   dict(task_types=['other.task']), dict(required_capabilities=['other']),
                   dict(required_input_modality=ModelModality.IMAGE)]
        for change in changes:
            updated = rehash(ModelRouteRevision.model_validate(
                item.model_copy(update=change).model_dump(mode='json', by_alias=True)))
            source, target, row = case(updated)
            with self.subTest(change=list(change)):
                self.assertNotEqual(target, old_target)
                with self.assertRaises(ModelRuntimeConflict):
                    self.read(source, old_target, FakeConnection(row))
                self.assertEqual(self.read(source, target, FakeConnection(row)).target_ref, target)

    def test_12_old_model_lock_and_both_list_kinds_keep_original_contract(self):
        source, target, row = case(model())
        c = FakeConnection(row)
        del c.autocommit, c.info, c.row_factory
        result = self.store.require_current_model_eval_candidate_for_update(
            c, SCOPE, source, target, expected_head_version=7)
        self.assertEqual((result.source_ref, result.target_ref), (source, target))
        self.assertEqual(len(c.queries), 1)
        self.assertIn('aip_registered_model_head', c.queries[0][0])
        rs, rt, rr = case()
        c.rows = [rr, row]
        @contextmanager
        def connect(scope):
            self.assertEqual(scope, SCOPE)
            yield c
        listed = AipModelRuntimeStore(connect_factory=connect).list_eval_candidates(SCOPE)
        self.assertEqual([x.source_ref.asset_type for x in listed], ['ModelRouteRevision', 'RegisteredModelRevision'])
        self.assertEqual([(x.source_ref, x.target_ref) for x in listed], [(rs, rt), (source, target)])

    def test_13_old_model_negative_errors_are_preserved(self):
        s, t, row = case(model())
        for altered, target, message in [(None, t, 'current Model Eval head or source drifted'),
            (row | {'version': 8}, t, 'current Model Eval head or source drifted'),
            (row, t.model_copy(update={'content_hash': 'f' * 64}), 'current Model Eval target drifted')]:
            with self.subTest(message=message), self.assertRaisesRegex(ModelRuntimeConflict, '^' + message + '$'):
                self.store.require_current_model_eval_candidate_for_update(
                    FakeConnection(altered), SCOPE, s, target, expected_head_version=7)

    def test_14_returned_refs_do_not_alias_caller_inputs(self):
        s, t, row = case()
        result = self.read(s, t, FakeConnection(row))
        old_s, old_t = result.source_ref.content_hash, result.target_ref.content_hash
        self.assertIsNot(result.source_ref, s)
        self.assertIsNot(result.target_ref, t)
        s.__dict__['content_hash'] = 'f' * 64
        t.__dict__['content_hash'] = 'e' * 64
        self.assertEqual((result.source_ref.content_hash, result.target_ref.content_hash), (old_s, old_t))

    def test_15_json_payload_reader_and_non_dict_refusal(self):
        s, t, row = case()
        self.assertEqual(self.read(s, t, FakeConnection(row | {'payload': json.dumps(row['payload'])})).source_ref, s)
        for payload in (None, [], 'not-json', route()):
            with self.subTest(payload_type=type(payload).__name__), self.assertRaises(ModelRuntimeConflict):
                self.read(s, t, FakeConnection(row | {'payload': payload}))

    def test_16_cross_tenant_payload_and_row_identity_refused(self):
        s, t, row = case()
        for change in ({'asset_id': 'other'}, {'content_hash': 'f' * 64}):
            with self.subTest(change=change), self.assertRaises(ModelRuntimeConflict):
                self.read(s, t, FakeConnection(row | change))
        altered = deepcopy(row)
        altered['payload']['tenant']['orgId'] = 'dev-org'
        with self.assertRaises(ModelRuntimeConflict):
            self.read(s, t, FakeConnection(altered))


if __name__ == '__main__': unittest.main()

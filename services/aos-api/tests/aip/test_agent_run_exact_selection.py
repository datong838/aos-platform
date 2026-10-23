"""Pure identity-pinning tests; synthetic gates are not execution authority."""
from datetime import timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from aos_api.aip_llm_adapter import LLMAdapter, LLMRuntimeBlocked
from aos_api.aip_model_runtime_contracts import (
    ModelRouteCandidate, ModelRuntimeLifecycle, ModelRuntimeReadiness, RouteStrategy,
)
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import ModelRuntimeNotFound
from aos_api.tenant_scope import TenantScope
from test_aip_model_runtime_resolver import NOW, SCOPE, ReadyRuntimeStore, ref
import test_aip_agent_run_executor as original_executor


class ExactSelectionTests(unittest.TestCase):
    def setUp(self):
        self.gate = self.enterContext(patch.object(AipModelRuntimeResolver, '_gate_passed', return_value=True))
        self.enterContext(patch.object(AipModelRuntimeResolver, '_health_is_fresh', return_value=True))
        self.store = ReadyRuntimeStore()
        self.resolver = AipModelRuntimeResolver(self.store)
        self.saved = self.resolver.resolve(SCOPE, 'route-copy', now=NOW)

    def checked(self, selection=None, now=NOW):
        return self.resolver.revalidate_selection(SCOPE, self.saved if selection is None else selection, now=now)

    def assert_blocked(self, result):
        self.assertEqual(result.readiness, ModelRuntimeReadiness.BLOCKED)
        self.assertIsNone(result.selected_model)
        self.assertTrue(result.blocker_codes)

    def test_01_revalidates_without_resolve_or_mutating_saved_selection(self):
        before = self.saved.model_dump(mode='json')
        with patch.object(self.resolver, 'resolve', side_effect=AssertionError('reselection')):
            result = self.checked(now=NOW + timedelta(seconds=1))
        self.assertEqual(result.selected_model, self.saved.selected_model)
        self.assertIsNot(result.selected_model, self.saved.selected_model)
        self.assertEqual(result.resolved_at, NOW + timedelta(seconds=1))
        self.assertEqual(self.saved.model_dump(mode='json'), before)

    def test_02_wrong_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            self.resolver.revalidate_selection(TenantScope('dev-org', 'dev-project'), self.saved, now=NOW)

    def test_03_wrong_input_and_unready_snapshot_are_rejected(self):
        with self.assertRaises(ValueError):
            self.checked({'not': 'a selection'})
        bad = self.saved.model_copy(update={'readiness': ModelRuntimeReadiness.BLOCKED})
        with self.assertRaises(ValueError):
            self.checked(bad)
        with self.assertRaises(ValueError):
            self.checked(self.saved.model_copy(update={'tenant': None}))

    def test_04_naive_or_future_clock_is_rejected(self):
        for saved, now in [(self.saved, NOW.replace(tzinfo=None)),
                           (self.saved, False), (self.saved, 0), (self.saved, 'clock'),
                           (self.saved.model_copy(update={'resolved_at': NOW.replace(tzinfo=None)}), NOW),
                           (self.saved, NOW - timedelta(seconds=1))]:
            with self.subTest(now=now), self.assertRaises(ValueError):
                self.checked(saved, now=now)

    def test_05_route_head_or_hash_drift_refuses(self):
        old = self.store.get_route(SCOPE, 'route-copy')
        for changes in [{'revision': 2}, {'content_hash': 'f' * 64}]:
            with self.subTest(changes=changes), patch.object(self.store, 'get_route', return_value=old.model_copy(update=changes)):
                self.assert_blocked(self.checked())

    def test_06_route_suspension_refuses(self):
        route = self.store.get_route(SCOPE, 'route-copy').model_copy(update={'lifecycle': ModelRuntimeLifecycle.SUSPENDED})
        with patch.object(self.store, 'get_route', return_value=route):
            self.assert_blocked(self.checked())

    def test_07_policy_drift_kill_and_revoke_refuse(self):
        old = self.store.get_policy(SCOPE, 'policy', 1)
        for changes in [{'revision': 2}, {'content_hash': 'e' * 64}, {'kill_switch_enabled': True},
                        {'lifecycle': ModelRuntimeLifecycle.REVOKED}]:
            with self.subTest(changes=changes), patch.object(self.store, 'get_policy', return_value=old.model_copy(update=changes)):
                self.assert_blocked(self.checked())

    def test_08_absent_candidate_does_not_choose_another(self):
        route = self.store.get_route(SCOPE, 'route-copy').model_copy(update={
            'candidates': [ModelRouteCandidate(model=ref('RegisteredModelRevision', 'other', 'd' * 64))]})
        with patch.object(self.store, 'get_route', return_value=route), patch.object(self.resolver, '_candidate', side_effect=AssertionError('alternative')):
            self.assert_blocked(self.checked())

    def test_09_zero_weight_candidate_refuses(self):
        route = self.store.get_route(SCOPE, 'route-copy').model_copy(update={
            'strategy': RouteStrategy.WEIGHTED,
            'candidates': [ModelRouteCandidate(model=self.saved.selected_model, weight=0),
                           ModelRouteCandidate(model=ref('RegisteredModelRevision', 'other', 'd' * 64), weight=100)]})
        with patch.object(self.store, 'get_route', return_value=route):
            self.assert_blocked(self.checked())

    def test_10_original_eval_denial_is_not_bypassed(self):
        self.gate.return_value = False
        result = self.checked()
        self.assert_blocked(result)
        self.assertIn('route_eval_gate_not_passed', result.blocker_codes)

    def test_11_pinned_failure_never_falls_back(self):
        route = self.store.get_route(SCOPE, 'route-copy')
        route = route.model_copy(update={'candidates': [*route.candidates,
            ModelRouteCandidate(model=ref('RegisteredModelRevision', 'other', 'd' * 64))]})
        with patch.object(self.store, 'get_route', return_value=route), patch.object(self.store, 'get_model', side_effect=ModelRuntimeNotFound('missing')) as read:
            self.assert_blocked(self.checked())
        self.assertEqual(read.call_count, 1)
        self.assertEqual(read.call_args.args[1], 'model')

    def test_12_provider_ref_mismatch_refuses(self):
        model = self.store.get_model(SCOPE, 'model', 1).model_copy(update={
            'provider': ref('ProviderInstanceRevision', 'different', 'a' * 64)})
        with patch.object(self.store, 'get_model', return_value=model):
            self.assert_blocked(self.checked())

    def test_13_price_ref_mismatch_refuses(self):
        model = self.store.get_model(SCOPE, 'model', 1).model_copy(update={
            'price_snapshot_ref': ref('ModelPriceSnapshotRevision', 'different', 'b' * 64)})
        with patch.object(self.store, 'get_model', return_value=model):
            self.assert_blocked(self.checked())

    def test_14_bool_revision_forgery_is_rejected(self):
        altered = self.saved.model_copy(deep=True)
        altered.selected_model.revision = True
        with self.assertRaises(ValueError):
            self.checked(altered)

    def adapter(self, resolver):
        effects = []
        def invoke(resolution, prompt, classification):
            effects.append(('invoke', resolution))
            return {'answer': 'fixture', 'provider': 'fixture-provider', 'route': 'exact', 'tokens': 1}
        def record(scope, lineage, resolution, response):
            effects.append(('usage', resolution))
            return ['fixture-usage']
        return LLMAdapter(resolver=resolver, provider_invoker=invoke, usage_bridge=SimpleNamespace(record=record)), effects

    def chat(self, adapter, selection=None, route='route-copy'):
        return adapter.chat_exact(SCOPE, route, 'public fixture', lineage_id='fixture-lineage',
            data_classification='public_catalog', expected_selection=self.saved if selection is None else selection)

    def test_15_adapter_uses_one_revalidated_object_for_invoker_and_usage(self):
        checked = self.saved.model_copy(deep=True)
        resolver = SimpleNamespace(revalidate_selection=lambda scope, selection: checked,
                                   resolve=lambda *_: self.fail('reselection'))
        adapter, effects = self.adapter(resolver)
        self.chat(adapter)
        self.assertEqual([e[0] for e in effects], ['invoke', 'usage'])
        self.assertIs(effects[0][1], checked)
        self.assertIs(effects[1][1], checked)

    def test_16_blocked_pin_has_zero_invoker_or_usage_calls(self):
        blocked = self.saved.model_copy(update={'readiness': ModelRuntimeReadiness.BLOCKED,
            'selected_model': None, 'selected_provider': None, 'selected_price_snapshot': None,
            'blocker_codes': ['fixture_revoked']})
        adapter, effects = self.adapter(SimpleNamespace(revalidate_selection=lambda *_: blocked))
        with self.assertRaises(LLMRuntimeBlocked):
            self.chat(adapter)
        self.assertEqual(effects, [])
        with self.assertRaises(LLMRuntimeBlocked):
            self.chat(adapter, selection=self.saved.model_copy(update={'route': None}))

    def test_17_adapter_route_argument_mismatch_refuses_before_revalidation(self):
        adapter, effects = self.adapter(SimpleNamespace(revalidate_selection=lambda *_: self.fail('wrong route')))
        with self.assertRaises(LLMRuntimeBlocked):
            self.chat(adapter, route='other')
        self.assertEqual(effects, [])

    def test_18_missing_revalidator_does_not_fall_back(self):
        adapter, effects = self.adapter(SimpleNamespace(resolve=lambda *_: self.fail('fallback')))
        with self.assertRaises((AttributeError, LLMRuntimeBlocked)):
            self.chat(adapter)
        self.assertEqual(effects, [])

    def test_19_executor_forwards_persisted_attempt_refs(self):
        service, _, attempts, llm, _ = original_executor.executor()
        service.execute(original_executor.SCOPE, 'run-1', original_executor.execute_request(),
            idempotency_key='idem-1', actor='pytest', occurred_at=original_executor.NOW)
        pin = llm.kwargs['expected_selection']
        for a, b in [('route', 'route_ref'), ('policy', 'policy_ref'), ('selected_model', 'model_ref'),
                     ('selected_provider', 'provider_ref'), ('selected_price_snapshot', 'price_snapshot_ref')]:
            self.assertEqual(getattr(pin, a), getattr(attempts.value, b))
        self.assertEqual(pin.resolved_at, attempts.value.prepared_at)

    def test_20_incompatible_adapter_stays_unknown_without_retry(self):
        class OldAdapter:
            calls = 0
            def chat_exact(self, scope, route_id, query, *, lineage_id, system_prompt, data_classification):
                self.calls += 1
                raise AssertionError('must reject new signature before invoking old adapter')
        adapter = OldAdapter()
        service, _, _, _, _ = original_executor.executor(llm=adapter)
        request = original_executor.execute_request()
        first = service.execute(original_executor.SCOPE, 'run-1', request,
            idempotency_key='idem-1', actor='pytest', occurred_at=original_executor.NOW)
        self.assertEqual(first.attempt.status.value, 'unknown')
        self.assertEqual(adapter.calls, 0)
        second = service.execute(original_executor.SCOPE, 'run-1', request,
            idempotency_key='idem-1', actor='pytest', occurred_at=original_executor.NOW)
        self.assertTrue(second.replayed)
        self.assertEqual(second.attempt.status.value, 'unknown')

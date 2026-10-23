"""Numerical fixtures only: no source, approval or execution authority."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from collections import Counter
import ast
import inspect
import unittest
from unittest.mock import patch

from aos_api.aip_model_route_selection import (
    CandidateFacts, CostBasis, LatencySample, RouteSelectionUnavailable,
    calculate_route_selection,
)
from aos_api.aip_model_runtime_contracts import ModelRouteCandidate, ModelRuntimeLifecycle, RouteStrategy
from aos_api.aip_eval_contracts import EvidenceQuality
from aos_api.aip_contracts import TenantContext
from aos_api.aip_development_cost_authorization import DevelopmentCostAuthorization
from test_aip_model_runtime_resolver import NOW, SCOPE, ReadyRuntimeStore, ref


class FourStrategyTests(unittest.TestCase):
    def setUp(self):
        store = ReadyRuntimeStore()
        self.policy = store.get_policy(SCOPE, 'policy', 1)
        base = store.get_route(SCOPE, 'route')
        self.refs = tuple(ref('RegisteredModelRevision', f'fixture-model-{i}', str(i + 2) * 64) for i in range(3))
        self.route = base.model_copy(update={'candidates': [ModelRouteCandidate(model=x) for x in self.refs]})
        price = store.get_price_snapshot(SCOPE, 'price', 1)
        self.facts = tuple(CandidateFacts(
            model=self.refs[i], provider=ref('ProviderInstanceRevision', f'fixture-provider-{i}', 'a' * 64),
            price_ref=ref('ModelPriceSnapshotRevision', f'fixture-price-{i}', 'b' * 64),
            price=price.model_copy(update={'price_snapshot_id': f'fixture-price-{i}',
                'input_token_price': float(i + 1), 'output_token_price': float(2 * i + 2), 'token_unit': 1}),
        ) for i in range(3))
        self.basis = CostBasis('CNY', 1, 0, 0)

    def route_for(self, strategy, weights=(60, 30, 10)):
        return self.route.model_copy(update={'strategy': strategy, 'candidates': [
            ModelRouteCandidate(model=x, weight=weights[i] if strategy is RouteStrategy.WEIGHTED else 100)
            for i, x in enumerate(self.refs)]})

    def choose(self, strategy=RouteStrategy.FAILOVER, facts=None, policy=None, **kwargs):
        return calculate_route_selection(self.route_for(strategy), self.policy if policy is None else policy,
            self.facts if facts is None else facts, now=NOW, **kwargs)

    def sample(self, i, duration, *, end=NOW, key=None):
        return LatencySample(tenant_key=SCOPE.key, model=self.refs[i], provider=self.facts[i].provider,
            sample_id=key or f'fixture-{i}-{duration}', ended_at=end, duration_ns=duration,
            quality=EvidenceQuality.MEASURED, measurement_kind='client_transport_elapsed_ns')

    def groups(self, *groups):
        return tuple(replace(f, latency_samples=tuple(groups[i]) if i < len(groups)
            else (self.sample(i, 100000),)) for i, f in enumerate(self.facts))

    def price(self, i, **fields):
        facts = list(self.facts)
        facts[i] = replace(facts[i], price=facts[i].price.model_copy(update=fields))
        return tuple(facts)

    def test_01_failover_keeps_original_order(self):
        result = self.choose()
        self.assertEqual(result.selected_index, 0)
        self.assertEqual(result.eligible_indices, (0, 1, 2))

    def test_02_only_explicit_health_exclusion_is_allowed(self):
        facts = (replace(self.facts[0], blocker_codes=('provider_health_unavailable_or_stale',)), *self.facts[1:])
        with self.assertRaises(RouteSelectionUnavailable): self.choose(facts=facts)
        policy = self.policy.model_copy(update={'allowed_fallback_reasons': ['provider_health_unavailable_or_stale']})
        result = self.choose(facts=facts, policy=policy)
        self.assertEqual((result.selected_index, result.skipped_indices), (1, (0,)))
        all_blocked = tuple(replace(f, blocker_codes=('provider_health_unavailable_or_stale',)) for f in self.facts)
        with self.assertRaises(RouteSelectionUnavailable) as error:
            self.choose(facts=all_blocked, policy=policy)
        self.assertEqual(error.exception.code, 'route_selection_no_candidate')

    def test_03_unknown_and_security_blockers_never_fall_back(self):
        for code in ['new_unknown_reason', 'model_eval_gate_not_passed', 'model_capability_mismatch',
                     'budget_unavailable', 'provider_unavailable', 'provider_timeout']:
            with self.subTest(code=code):
                policy = self.policy.model_copy(update={'allowed_fallback_reasons': [code]})
                facts = (replace(self.facts[0], blocker_codes=(code,)), *self.facts[1:])
                with self.assertRaises(RouteSelectionUnavailable): self.choose(facts=facts, policy=policy)

    def test_04_zero_weight_does_not_hide_hard_denial(self):
        route = self.route_for(RouteStrategy.WEIGHTED, (0, 50, 50))
        facts = (replace(self.facts[0], blocker_codes=('model_eval_gate_not_passed',)), *self.facts[1:])
        with self.assertRaises(RouteSelectionUnavailable):
            calculate_route_selection(route, self.policy, facts, now=NOW, weighted_ticket=0)

    def test_05_weighted_all_hundred_integer_tickets(self):
        counts = Counter(self.choose(RouteStrategy.WEIGHTED, weighted_ticket=x).selected_index for x in range(100))
        self.assertEqual(counts, {0: 60, 1: 30, 2: 10})

    def test_06_weighted_zero_and_health_exclusions_use_original_intervals(self):
        route = self.route_for(RouteStrategy.WEIGHTED, (0, 30, 70))
        counts = Counter(calculate_route_selection(route, self.policy, self.facts, now=NOW, weighted_ticket=x).selected_index for x in range(100))
        self.assertEqual(counts, {1: 30, 2: 70})
        facts = (replace(self.facts[0], blocker_codes=('provider_health_unavailable_or_stale',)), *self.facts[1:])
        policy = self.policy.model_copy(update={'allowed_fallback_reasons': ['provider_health_unavailable_or_stale']})
        counts = Counter(self.choose(RouteStrategy.WEIGHTED, facts=facts, policy=policy, weighted_ticket=x).selected_index for x in range(40))
        self.assertEqual(counts, {1: 30, 2: 10})

    def test_07_weighted_ticket_has_no_implicit_default_or_coercion(self):
        for ticket in [None, True, -1, 100, 1.0, '1']:
            with self.subTest(ticket=ticket), self.assertRaises(RouteSelectionUnavailable):
                self.choose(RouteStrategy.WEIGHTED, weighted_ticket=ticket)

    def test_08_same_inputs_are_deterministic_without_rng(self):
        with patch('random.random', side_effect=AssertionError('rng')), patch('secrets.randbelow', side_effect=AssertionError('rng')):
            one = self.choose(RouteStrategy.WEIGHTED, weighted_ticket=61)
            two = self.choose(RouteStrategy.WEIGHTED, weighted_ticket=61)
        self.assertEqual(one, two)

    def test_09_nearest_rank_p99_for_100_and_101(self):
        for n, expected in [(100, '98'), (101, '99')]:
            samples = [self.sample(0, i) for i in range(n)]
            result = self.choose(RouteStrategy.LOWEST_LATENCY, facts=self.groups(samples), minimum_latency_samples=1)
            self.assertEqual((result.selected_index, result.comparison_value), (0, expected))

    def test_10_five_minute_window_has_exact_open_left_closed_right_edges(self):
        samples = [self.sample(0, 99999, end=NOW-timedelta(minutes=5), key='old'),
                   self.sample(0, 7, end=NOW-timedelta(minutes=5)+timedelta(microseconds=1), key='in'),
                   self.sample(0, 9, key='now')]
        facts = self.groups(samples,
            [self.sample(1, 100000, key='other-1a'), self.sample(1, 100001, key='other-1b')],
            [self.sample(2, 100000, key='other-2a'), self.sample(2, 100001, key='other-2b')])
        result = self.choose(RouteStrategy.LOWEST_LATENCY, facts=facts, minimum_latency_samples=2)
        self.assertEqual(result.comparison_value, '9')

    def test_11_minimum_sample_count_is_explicit_positive_actual_int(self):
        facts = self.groups([self.sample(0, 1)])
        for minimum in [None, True, 0, -1, 1.0, 2]:
            with self.subTest(minimum=minimum), self.assertRaises(RouteSelectionUnavailable):
                self.choose(RouteStrategy.LOWEST_LATENCY, facts=facts, minimum_latency_samples=minimum)

    def test_12_missing_metric_is_not_zero_or_infinity(self):
        for samples in [[], [self.sample(0, 1, end=NOW-timedelta(minutes=6))]]:
            with self.assertRaises(RouteSelectionUnavailable):
                self.choose(RouteStrategy.LOWEST_LATENCY, facts=self.groups(samples), minimum_latency_samples=1)

    def test_13_future_or_naive_samples_refuse(self):
        for end in [NOW+timedelta(microseconds=1), NOW.replace(tzinfo=None)]:
            with self.assertRaises(RouteSelectionUnavailable):
                self.choose(RouteStrategy.LOWEST_LATENCY, facts=self.groups([self.sample(0, 1, end=end)]), minimum_latency_samples=1)

    def test_14_samples_require_exact_tenant_model_provider(self):
        sample = self.sample(0, 1)
        for changes in [{'tenant_key': ('dev-org', 'dev-project')}, {'model': self.refs[1]},
                        {'provider': self.facts[1].provider}]:
            with self.subTest(changes=list(changes)), self.assertRaises(RouteSelectionUnavailable):
                self.choose(RouteStrategy.LOWEST_LATENCY, facts=self.groups([replace(sample, **changes)]), minimum_latency_samples=1)

    def test_15_duplicate_sample_identity_is_not_counted_twice(self):
        sample = self.sample(0, 1)
        with self.assertRaises(RouteSelectionUnavailable):
            self.choose(RouteStrategy.LOWEST_LATENCY, facts=self.groups([sample, sample]), minimum_latency_samples=1)

    def test_16_duration_requires_nonnegative_actual_integer(self):
        for duration in [-1, True, 1.5, None]:
            with self.subTest(duration=duration), self.assertRaises(RouteSelectionUnavailable):
                self.choose(RouteStrategy.LOWEST_LATENCY, facts=self.groups([self.sample(0, duration)]), minimum_latency_samples=1)

    def test_17_only_measured_single_client_transport_samples(self):
        signature = inspect.signature(LatencySample)
        self.assertIs(signature.parameters['quality'].default, inspect.Parameter.empty)
        self.assertIs(signature.parameters['measurement_kind'].default, inspect.Parameter.empty)
        sample = self.sample(0, 1)
        for changes in [{'quality': EvidenceQuality.ESTIMATED}, {'quality': EvidenceQuality.UNKNOWN},
                        {'quality': 'measured'}, {'measurement_kind': 'p50_latency_ms'},
                        {'measurement_kind': 'server_processing_ns'}, {'quality': None}]:
            with self.subTest(changes=changes), self.assertRaises(RouteSelectionUnavailable):
                self.choose(RouteStrategy.LOWEST_LATENCY, facts=self.groups([replace(sample, **changes)]), minimum_latency_samples=1)

    def test_18_sample_budget_never_silently_downsamples(self):
        samples = [self.sample(0, 1, key=f's-{i}') for i in range(4097)]
        with self.assertRaises(RouteSelectionUnavailable):
            self.choose(RouteStrategy.LOWEST_LATENCY, facts=self.groups(samples), minimum_latency_samples=1)

    def test_19_explicit_directional_workload_changes_unit_quote(self):
        facts = list(self.facts)
        facts[0] = replace(facts[0], price=facts[0].price.model_copy(update={'input_token_price': 1., 'output_token_price': 10.}))
        facts[1] = replace(facts[1], price=facts[1].price.model_copy(update={'input_token_price': 2., 'output_token_price': 1.}))
        self.assertEqual(self.choose(RouteStrategy.LOWEST_COST, facts=tuple(facts), cost_basis=self.basis).selected_index, 0)
        self.assertEqual(self.choose(RouteStrategy.LOWEST_COST, facts=tuple(facts), cost_basis=CostBasis('CNY', 1, 0, 2)).selected_index, 1)

    def test_20_token_units_and_rational_ties_are_exact(self):
        facts = list(self.facts)
        facts[0] = replace(facts[0], price=facts[0].price.model_copy(update={'input_token_price': 1., 'token_unit': 3}))
        facts[1] = replace(facts[1], price=facts[1].price.model_copy(update={'input_token_price': 333., 'token_unit': 999}))
        result = self.choose(RouteStrategy.LOWEST_COST, facts=tuple(facts), cost_basis=self.basis)
        self.assertEqual((result.selected_index, result.comparison_value), (0, '1/3'))

    def test_21_currencies_cannot_be_compared_without_fx_authority(self):
        with self.assertRaises(RouteSelectionUnavailable):
            self.choose(RouteStrategy.LOWEST_COST, facts=self.price(1, currency='USD'), cost_basis=self.basis)

    def test_22_unknown_and_deferred_price_are_not_zero(self):
        with self.assertRaises(RouteSelectionUnavailable):
            self.choose(RouteStrategy.LOWEST_COST, facts=self.price(0, input_token_price=None), cost_basis=self.basis)
        # A synthetic original DTO is not an issued approval; never persisted/used for execution.
        authorization = DevelopmentCostAuthorization(tenant=self.facts[0].price.tenant,
            provider=self.facts[0].provider, provider_model_id='fixture', approval_ref='synthetic-not-authority',
            effective_from=NOW, effective_until=NOW+timedelta(hours=1))
        facts = self.price(0, input_token_price=None, output_token_price=None,
            development_cost_authorization=authorization, effective_until=NOW+timedelta(hours=1))
        with self.assertRaises(RouteSelectionUnavailable):
            self.choose(RouteStrategy.LOWEST_COST, facts=facts, cost_basis=self.basis)

    def test_23_cache_is_disjoint_and_unused_missing_direction_is_not_guessed(self):
        with self.assertRaises(RouteSelectionUnavailable):
            self.choose(RouteStrategy.LOWEST_COST, facts=self.price(0, cached_token_price=.5),
                cost_basis=CostBasis('CNY', 0, 2, 0))
        facts = tuple(replace(f, price=f.price.model_copy(update={
            'input_token_price': None, 'cached_token_price': .5+i})) for i, f in enumerate(self.facts))
        result = self.choose(RouteStrategy.LOWEST_COST, facts=facts, cost_basis=CostBasis('CNY', 0, 2, 0))
        self.assertEqual((result.selected_index, result.comparison_value), (0, '1'))

    def test_24_price_identity_and_tenant_must_match(self):
        for fields in [{'price_snapshot_id': 'other'}, {'content_hash': 'e'*64},
                       {'tenant': TenantContext(org_id='dev-org', project_id='dev-project')}]:
            with self.subTest(fields=list(fields)), self.assertRaises(RouteSelectionUnavailable):
                self.choose(RouteStrategy.LOWEST_COST, facts=self.price(0, **fields), cost_basis=self.basis)

    def test_25_price_must_be_active_and_effective(self):
        for fields in [{'lifecycle': ModelRuntimeLifecycle.REVOKED}, {'effective_from': NOW+timedelta(seconds=1)},
                       {'effective_until': NOW}, {'effective_from': NOW.replace(tzinfo=None)}]:
            with self.subTest(fields=list(fields)), self.assertRaises(RouteSelectionUnavailable):
                self.choose(RouteStrategy.LOWEST_COST, facts=self.price(0, **fields), cost_basis=self.basis)

    def test_26_finite_prices_and_explicit_positive_integer_cost_basis(self):
        for value in [float('nan'), float('inf'), -1., True]:
            with self.subTest(value=value), self.assertRaises(RouteSelectionUnavailable):
                self.choose(RouteStrategy.LOWEST_COST, facts=self.price(0, input_token_price=value), cost_basis=self.basis)
        for basis in [None, CostBasis('CNY', True, 0, 0), CostBasis('CNY', 0, 0, 0), CostBasis('CNY', -1, 0, 0)]:
            with self.assertRaises(RouteSelectionUnavailable): self.choose(RouteStrategy.LOWEST_COST, cost_basis=basis)

    def test_27_equal_scores_keep_original_order(self):
        facts = tuple(replace(f, price=f.price.model_copy(update={'input_token_price': 1.}),
            latency_samples=(self.sample(i, 5),)) for i, f in enumerate(self.facts))
        self.assertEqual(self.choose(RouteStrategy.LOWEST_COST, facts=facts, cost_basis=self.basis).selected_index, 0)
        self.assertEqual(self.choose(RouteStrategy.LOWEST_LATENCY, facts=facts, minimum_latency_samples=1).selected_index, 0)

    def test_28_facts_must_match_original_exact_order_and_kinds(self):
        for facts in [self.facts[::-1], self.facts[:2], list(self.facts),
                      (replace(self.facts[0], provider=self.refs[0]), *self.facts[1:])]:
            with self.assertRaises(RouteSelectionUnavailable): self.choose(facts=facts)
        forged = self.facts[0].model.model_copy(update={'revision': True})
        with self.assertRaises(RouteSelectionUnavailable):
            self.choose(facts=(replace(self.facts[0], model=forged), *self.facts[1:]))

    def test_29_policy_identity_scope_and_kill_switch(self):
        for policy in [self.policy.model_copy(update={'content_hash': 'e'*64}),
                       self.policy.model_copy(update={'kill_switch_enabled': True}),
                       self.policy.model_copy(update={'tenant': TenantContext(org_id='dev-org', project_id='dev-project')})]:
            with self.assertRaises(RouteSelectionUnavailable): self.choose(policy=policy)

    def test_30_bad_clock_and_forged_input_types_are_not_coerced(self):
        for now in [None, False, 0, NOW.replace(tzinfo=None)]:
            with self.assertRaises(RouteSelectionUnavailable):
                calculate_route_selection(self.route, self.policy, self.facts, now=now)
        for facts in [(replace(self.facts[0], blocker_codes=['wrong']), *self.facts[1:]),
                      (replace(self.facts[0], blocker_codes=('',)), *self.facts[1:])]:
            with self.assertRaises(RouteSelectionUnavailable): self.choose(facts=facts)

    def test_31_caller_snapshots_unchanged_and_return_never_authorizes(self):
        before = self.route.model_dump(mode='json')
        result = self.choose()
        self.assertEqual(before, self.route.model_dump(mode='json'))
        self.assertIs(result.execution_allowed, False)
        with self.assertRaises(FrozenInstanceError): result.selected_index = 2
        draft = self.route.model_copy(update={'lifecycle': ModelRuntimeLifecycle.DRAFT, 'eval_gate_ref': None})
        preview = calculate_route_selection(draft, self.policy, self.facts, now=NOW)
        self.assertIs(preview.execution_allowed, False)

    def test_32_stable_errors_and_no_implicit_effect_primitives(self):
        facts = (replace(self.facts[0], blocker_codes=('private_fixture_marker',)), *self.facts[1:])
        with self.assertRaises(RouteSelectionUnavailable) as raised: self.choose(facts=facts)
        self.assertNotIn('private_fixture_marker', str(raised.exception))
        self.assertEqual(str(raised.exception), raised.exception.code)
        import aos_api.aip_model_route_selection as module
        calls = [node for node in ast.walk(ast.parse(inspect.getsource(module))) if isinstance(node, ast.Call)]
        names = {node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
                 for node in calls if isinstance(node.func, (ast.Name, ast.Attribute))}
        self.assertFalse(names & {'connect', 'open', 'Popen', 'randbelow', 'random', 'now', 'time'})

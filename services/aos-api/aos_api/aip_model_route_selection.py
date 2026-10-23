"""Deterministic Route calculations, never readiness or execution authority.

Native current-fact readers and the immutable per-call decision owner must
verify and bind inputs before a runtime may use a calculation. This module
does not read those authorities, sample entropy, call providers or retry.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction
import re

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_eval_contracts import EvidenceQuality
from aos_api.aip_model_runtime_contracts import (
    ModelPriceSnapshotRevision, ModelRouteRevision, ModelRuntimeLifecycle,
    RouteStrategy, RuntimePolicyRevision,
)


_SAFE_AVAILABILITY = frozenset({'provider_health_unavailable_or_stale'})
_MAX_SAMPLES = 4096


class RouteSelectionUnavailable(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class LatencySample:
    tenant_key: tuple[str, str]
    model: VersionedAssetRef
    provider: VersionedAssetRef
    sample_id: str
    ended_at: datetime
    duration_ns: int
    quality: EvidenceQuality
    measurement_kind: str


@dataclass(frozen=True)
class CandidateFacts:
    model: VersionedAssetRef
    provider: VersionedAssetRef
    price_ref: VersionedAssetRef
    blocker_codes: tuple[str, ...] = ()
    price: ModelPriceSnapshotRevision | None = None
    latency_samples: tuple[LatencySample, ...] = ()


@dataclass(frozen=True)
class CostBasis:
    currency: str
    uncached_input_tokens: int
    cached_input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class SelectionCalculation:
    strategy: RouteStrategy
    selected_index: int
    eligible_indices: tuple[int, ...]
    skipped_indices: tuple[int, ...]
    comparison_value: str | None

    @property
    def execution_allowed(self) -> bool:
        return False


def _ref(value: VersionedAssetRef, kind: str) -> VersionedAssetRef:
    if (type(value) is not VersionedAssetRef or value.asset_type != kind
        or type(value.revision) is not int or value.revision < 1):
        raise RouteSelectionUnavailable('route_selection_inputs_invalid')
    return VersionedAssetRef.model_validate(value.model_dump(mode='json', by_alias=True))


def _aware(value) -> bool:
    return isinstance(value, datetime) and value.utcoffset() is not None


def _p99(fact, scope, now, seen, minimum):
    if type(fact.latency_samples) is not tuple or len(fact.latency_samples) > _MAX_SAMPLES:
        raise RouteSelectionUnavailable('route_selection_latency_unavailable')
    durations = []
    for sample in fact.latency_samples:
        if (type(sample) is not LatencySample
            or type(sample.tenant_key) is not tuple or sample.tenant_key != scope
            or _ref(sample.model, 'RegisteredModelRevision') != fact.model
            or _ref(sample.provider, 'ProviderInstanceRevision') != fact.provider
            or type(sample.sample_id) is not str or not sample.sample_id.strip()
            or len(sample.sample_id) > 240 or sample.sample_id in seen
            or not _aware(sample.ended_at) or sample.ended_at > now
            or type(sample.duration_ns) is not int or sample.duration_ns < 0
            or sample.quality is not EvidenceQuality.MEASURED
            or sample.measurement_kind != 'client_transport_elapsed_ns'):
            raise RouteSelectionUnavailable('route_selection_latency_unavailable')
        seen.add(sample.sample_id)
        if now - timedelta(minutes=5) < sample.ended_at <= now:
            durations.append(sample.duration_ns)
    if minimum is None:
        return None
    if len(durations) < minimum:
        raise RouteSelectionUnavailable('route_selection_latency_unavailable')
    durations.sort()
    return durations[(99 * len(durations) + 99) // 100 - 1]


def _quote(fact, scope, now, basis):
    price = fact.price
    if type(price) is not ModelPriceSnapshotRevision:
        raise RouteSelectionUnavailable('route_selection_cost_unavailable')
    # Check numerical values before DTO copying could coerce a forged bool.
    quantities = (basis.uncached_input_tokens, basis.cached_input_tokens, basis.output_tokens)
    rates = (price.input_token_price, price.cached_token_price, price.output_token_price)
    for quantity, rate in zip(quantities, rates):
        if quantity and (type(rate) not in (int, float) or not Decimal(str(rate)).is_finite() or rate < 0):
            raise RouteSelectionUnavailable('route_selection_cost_unavailable')
    if type(price.revision) is not int or type(price.token_unit) is not int:
        raise RouteSelectionUnavailable('route_selection_cost_unavailable')
    price = ModelPriceSnapshotRevision.model_validate(price.model_dump(mode='json', by_alias=True))
    if ((price.tenant.org_id, price.tenant.project_id) != scope
        or (price.price_snapshot_id, price.revision, price.content_hash) != (
            fact.price_ref.asset_id, fact.price_ref.revision, fact.price_ref.content_hash)
        or price.lifecycle is not ModelRuntimeLifecycle.ACTIVE
        or price.currency != basis.currency
        or not _aware(price.effective_from) or price.effective_from > now
        or (price.effective_until is not None and (
            not _aware(price.effective_until) or price.effective_until <= now))):
        raise RouteSelectionUnavailable('route_selection_cost_unavailable')
    rates = (price.input_token_price, price.cached_token_price, price.output_token_price)
    return sum((quantity * Fraction(Decimal(str(rate))) / price.token_unit
                for quantity, rate in zip(quantities, rates) if quantity), Fraction(0))


def calculate_route_selection(
    route: ModelRouteRevision,
    policy: RuntimePolicyRevision,
    facts: tuple[CandidateFacts, ...],
    *,
    now: datetime,
    weighted_ticket: int | None = None,
    minimum_latency_samples: int | None = None,
    cost_basis: CostBasis | None = None,
) -> SelectionCalculation:
    """Calculate one index from explicit inputs; do not authorize that index.

    Draft simulation is permitted. Real source/currentness, permissions,
    signed quality, budget and a committed per-call decision are separate
    mandatory runtime responsibilities, not satisfied by these dataclasses.
    """
    try:
        return _calculate(route, policy, facts, now, weighted_ticket,
                          minimum_latency_samples, cost_basis)
    except RouteSelectionUnavailable:
        raise
    except (ValueError, TypeError, AttributeError, ArithmeticError):
        raise RouteSelectionUnavailable('route_selection_inputs_invalid') from None


def _calculate(route, policy, facts, now, ticket, minimum, basis):
    if (type(route) is not ModelRouteRevision or type(policy) is not RuntimePolicyRevision
        or type(facts) is not tuple or not _aware(now)
        or type(route.revision) is not int or type(policy.revision) is not int):
        raise RouteSelectionUnavailable('route_selection_inputs_invalid')
    for candidate in route.candidates:
        _ref(candidate.model, 'RegisteredModelRevision')
        if type(candidate.weight) is not int:
            raise RouteSelectionUnavailable('route_selection_inputs_invalid')
    _ref(route.runtime_policy_ref, 'RuntimePolicyRevision')
    route = ModelRouteRevision.model_validate(route.model_dump(mode='json', by_alias=True))
    policy = RuntimePolicyRevision.model_validate(policy.model_dump(mode='json', by_alias=True))
    scope = (route.tenant.org_id, route.tenant.project_id)
    if (scope != (policy.tenant.org_id, policy.tenant.project_id)
        or (policy.policy_id, policy.revision, policy.content_hash) != (
            route.runtime_policy_ref.asset_id, route.runtime_policy_ref.revision,
            route.runtime_policy_ref.content_hash)
        or len(facts) != len(route.candidates)):
        raise RouteSelectionUnavailable('route_selection_inputs_invalid')
    if policy.kill_switch_enabled:
        raise RouteSelectionUnavailable('route_selection_blocked')
    copied = []
    eligible = []
    skipped = []
    for index, (fact, candidate) in enumerate(zip(facts, route.candidates)):
        if type(fact) is not CandidateFacts or type(fact.blocker_codes) is not tuple:
            raise RouteSelectionUnavailable('route_selection_inputs_invalid')
        if (any(type(code) is not str or not code.strip() or code != code.strip()
                for code in fact.blocker_codes)
            or len(set(fact.blocker_codes)) != len(fact.blocker_codes)):
            raise RouteSelectionUnavailable('route_selection_inputs_invalid')
        model = _ref(fact.model, 'RegisteredModelRevision')
        provider = _ref(fact.provider, 'ProviderInstanceRevision')
        price_ref = _ref(fact.price_ref, 'ModelPriceSnapshotRevision')
        if model != candidate.model:
            raise RouteSelectionUnavailable('route_selection_inputs_invalid')
        if any(code not in _SAFE_AVAILABILITY or code not in policy.allowed_fallback_reasons
               for code in fact.blocker_codes):
            raise RouteSelectionUnavailable('route_selection_blocked')
        copied.append(CandidateFacts(model, provider, price_ref, fact.blocker_codes,
            fact.price.model_copy(deep=True) if type(fact.price) is ModelPriceSnapshotRevision else fact.price,
            fact.latency_samples))
        if fact.blocker_codes or (route.strategy is RouteStrategy.WEIGHTED and candidate.weight == 0):
            skipped.append(index)
        else:
            eligible.append(index)
    if not eligible:
        raise RouteSelectionUnavailable('route_selection_no_candidate')
    value = None
    if route.strategy is RouteStrategy.FAILOVER:
        selected = eligible[0]
    elif route.strategy is RouteStrategy.WEIGHTED:
        total = sum(route.candidates[i].weight for i in eligible)
        if type(ticket) is not int or not 0 <= ticket < total:
            raise RouteSelectionUnavailable('route_selection_ticket_required')
        boundary = 0
        for index in eligible:
            boundary += route.candidates[index].weight
            if ticket < boundary:
                selected = index
                break
        value = f'{ticket}/{total}'
    elif route.strategy is RouteStrategy.LOWEST_LATENCY:
        if type(minimum) is not int or minimum < 1:
            raise RouteSelectionUnavailable('route_selection_latency_unavailable')
        seen = set()
        scores = {i: _p99(fact, scope, now, seen, minimum if i in eligible else None)
                  for i, fact in enumerate(copied)}
        selected = min(eligible, key=lambda i: scores[i])
        value = str(scores[selected])
    elif route.strategy is RouteStrategy.LOWEST_COST:
        if (type(basis) is not CostBasis or type(basis.currency) is not str
            or re.fullmatch(r'[A-Z]{3}', basis.currency) is None):
            raise RouteSelectionUnavailable('route_selection_cost_unavailable')
        quantities = (basis.uncached_input_tokens, basis.cached_input_tokens, basis.output_tokens)
        if any(type(q) is not int or q < 0 for q in quantities) or not sum(quantities):
            raise RouteSelectionUnavailable('route_selection_cost_unavailable')
        scores = {i: _quote(copied[i], scope, now, basis) for i in eligible}
        selected = min(eligible, key=lambda i: scores[i])
        value = str(scores[selected])
    else:
        raise RouteSelectionUnavailable('route_selection_inputs_invalid')
    return SelectionCalculation(route.strategy, selected, tuple(eligible), tuple(skipped), value)

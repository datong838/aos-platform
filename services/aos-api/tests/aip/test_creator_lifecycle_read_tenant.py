"""Serialized tenant must agree with scoped SQL; fixtures open no database."""
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from aos_api.ecommerce_workshop_creator_lifecycle import (
    CreatorBatchStartDecisionRevision, CreatorContractRevision,
    CreatorDeliveryObservation, CreatorLaneObservation, CreatorLifecycleBlocked,
    CreatorRelationshipRevision,
)
from aos_api.ecommerce_workshop_creator_lifecycle_store import EcommerceWorkshopCreatorLifecycleStore
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('org-org', 'dev-project')
NOW = datetime(2026, 10, 14, tzinfo=UTC)
HASH = 'a' * 64
MODELS = {
    'latest_start_for_tenant_or_none': CreatorBatchStartDecisionRevision,
    'list_lane_observations': CreatorLaneObservation,
    'list_contracts': CreatorContractRevision,
    'list_deliveries': CreatorDeliveryObservation,
    'list_relationships': CreatorRelationshipRevision,
}


def ref(kind):
    return dict(resourceType=kind, resourceId='fixture-ref', revision=1, contentHash=HASH)


def item(method, scope=SCOPE):
    common = dict(tenant=dict(orgId=scope.org_id, projectId=scope.project_id), contentHash=HASH)
    payloads = {
        'latest_start_for_tenant_or_none': dict(
            decisionId='fixture-start', lifecycle='governance_prepared',
            batchRef=ref('CreatorBatchPreparationRevision'), batchItemHashes=[], lanes=[],
            ledger=dict(eligibleItems=0, lanes=0, prepared=0, accepted=0, applied=0,
                        failed=0, unknown=0, disputed=0, completed=0),
            operationalBlockers=[], startedBy='fixture-not-human-approval', startedAt=NOW),
        'list_lane_observations': dict(
            observationId='fixture-lane', startDecisionRef=ref('CreatorBatchStartDecisionRevision'),
            laneId='fixture-lane', actionReceiptRef=ref('ActionReceiptRevision'),
            outcome='prepared', observedAt=NOW),
        'list_contracts': dict(
            collaborationId='fixture-contract', revision=1, candidateRef=ref('CreatorCandidateRevision'),
            startDecisionRef=ref('CreatorBatchStartDecisionRevision'), termsHash=HASH,
            monetaryTermsRef=ref('MonetaryTermsRevision'), lifecycle='draft',
            createdBy='fixture-not-human-approval', createdAt=NOW),
        'list_deliveries': dict(
            observationId='fixture-delivery', collaborationId='fixture-contract',
            contractRef=ref('CreatorContractRevision'), deliveryRef=ref('DeliveryRevision'),
            evidenceBundleRef=ref('EvidenceBundleRevision'), sequence=1, status='expected', observedAt=NOW),
        'list_relationships': dict(
            relationshipId='fixture-relationship', revision=1, collaborationId='fixture-contract',
            contractRef=ref('CreatorContractRevision'), deliveryObservationRefs=[],
            maturityPolicyRef=ref('RelationshipMaturityPolicyRevision'),
            maturityWindowEndsAt=NOW, status='preliminary', createdAt=NOW),
    }
    return MODELS[method](**common, **payloads[method])


def store_with_rows(rows):
    calls = []
    class Connection:
        def execute(self, sql, params):
            assert sql.startswith('SELECT ')
            assert tuple(params[:2]) == SCOPE.key
            calls.append((sql, params))
            return self
        def fetchone(self):
            return rows[0] if rows else None
        def fetchall(self):
            return rows
        def commit(self):
            pytest.fail('view reader must not commit a write')
    @contextmanager
    def read(scope):
        assert scope == SCOPE
        yield Connection()
    def writer(_scope):
        pytest.fail('view must use read connection, not write connection')
    return EcommerceWorkshopCreatorLifecycleStore(writer, read_connect_factory=read), calls


def invoke(store, method):
    args = (SCOPE, 'fixture-start') if method == 'list_lane_observations' else (SCOPE,)
    return getattr(store, method)(*args)


@pytest.mark.parametrize('method', MODELS)
@pytest.mark.parametrize('foreign', [TenantScope('dev-org', 'dev-project'), TenantScope('org-org', 'other')])
def test_foreign_serialized_tenant_is_rejected_even_under_correct_sql(method, foreign):
    valid = dict(authority_data=item(method).model_dump(mode='json', by_alias=True))
    bad = dict(authority_data=item(method, foreign).model_dump(mode='json', by_alias=True))
    rows = [bad] if method.startswith('latest_') else [valid, bad]
    store, calls = store_with_rows(rows)
    with pytest.raises(CreatorLifecycleBlocked, match='CREATOR_LIFECYCLE_TENANT_DRIFT'):
        invoke(store, method)
    assert len(calls) == 1


@pytest.mark.parametrize('method', MODELS)
def test_valid_serialized_tenant_preserves_complete_item(method):
    expected = item(method)
    store, calls = store_with_rows([dict(authority_data=expected.model_dump(mode='json', by_alias=True))])
    actual = invoke(store, method)
    assert actual == (expected if method.startswith('latest_') else [expected])
    assert len(calls) == 1


@pytest.mark.parametrize('method', MODELS)
def test_empty_reader_retains_existing_none_or_empty_semantics(method):
    store, calls = store_with_rows([])
    assert invoke(store, method) == (None if method.startswith('latest_') else [])
    assert len(calls) == 1

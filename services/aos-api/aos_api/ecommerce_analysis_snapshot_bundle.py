"""Current complete observations through the original EvidenceBundle authority."""
from datetime import datetime

from aos_api.aip_business_investigation_evidence import (
    BusinessInvestigationEvidenceBuilder, BusinessInvestigationEvidenceBuildRequest,
)
from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
from aos_api.aip_production_contracts import BuildEvidenceBundleRequest, Coverage, Freshness, ExactRevisionRef
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
from aos_api.ecommerce_analysis_snapshot_brief import AnalysisSnapshotBrief, AnalysisSnapshotBriefSpec
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory

_POLICY = 'snapshot-current-observation/v1'
_LICENSE = {'status': 'pending-policy-review', 'authority': 'business-investigation-evidence-adapter'}


def _exact(reference):
    return ExactRevisionRef(resource_type=reference.resource_type, resource_id=reference.resource_id,
                            revision=reference.revision, content_hash=reference.content_hash[7:])


def _ref(bundle):
    return InvestigationExactRef(resource_type='EvidenceBundleRevision', resource_id=bundle.bundle_id,
                                 revision=bundle.revision, content_hash='sha256:' + bundle.content_hash)


class _CurrentSnapshotStore(AipProductionContractStore):
    """Only instantiated inside the original brief/current-business guards."""

    def __init__(self, factory, scope, expected, observation):
        super().__init__(factory)
        self._scope = scope
        self._expected = expected.model_copy(deep=True)
        self._observation = dict(observation)

    def _compute_evidence_bundle_coverage(self, conn, scope, body):
        if scope != self._scope or body != self._expected:
            raise ValueError('snapshot bundle request differs from current authority')
        coverage, missing, conflicts, uncertainties, _ = super()._compute_evidence_bundle_coverage(conn, scope, body)
        # Current source age is checked before AND after this call by the quality
        # owner. Keep the actual oldest read time, never rewrite it to cutoff.
        uncertainties = [*uncertainties, self._observation]
        freshness = Freshness.BLOCKED if coverage is Coverage.BLOCKED else Freshness.FRESH
        return coverage, missing, conflicts, uncertainties, freshness


class AnalysisSnapshotBundle:
    def __init__(self, brief):
        if type(brief) is not AnalysisSnapshotBrief:
            raise TypeError('original current snapshot Brief owner required')
        self.brief = brief
        self.scope = brief.scope

    def _during(self, conn, business_ref, brief_ref, execute):
        evidence = InvestigationExactRef.model_validate(business_ref)
        brief_ref = InvestigationExactRef.model_validate(brief_ref)

        def consume(tx, original_store, brief_request, actor):
            self.brief._read(tx, original_store, brief_request, actor, brief_ref)
            spec = AnalysisSnapshotBriefSpec.model_validate(brief_request.spec)
            business = self.brief.business._record(conn, evidence)
            source = self.brief.business.source._record(conn, business['selection']['evidenceRef'])
            requirement = DataRequirementRevisionRecord.model_validate(source['fieldContext']['requirement'])
            body = BuildEvidenceBundleRequest(brief_ref=_exact(brief_ref), item_refs=[_exact(evidence)],
                required_fact_ids=requirement.required_facts, cutoff_at=requirement.cutoff_at,
                marking=requirement.markings, license_summary=_LICENSE)
            observation = dict(code='SNAPSHOT_OBSERVATION_NOT_SOURCE_TRANSACTION_TIME', policy=_POLICY,
                               freshnessAt=business['freshnessAt'], observedAt=business['observedAt'])
            store = _CurrentSnapshotStore(TransactionBoundConnectFactory(tx, self.scope), self.scope, body, observation)
            result = execute(tx, store, body, spec, business, actor)
            self.brief._read(tx, original_store, brief_request, actor, brief_ref)
            return result
        return self.brief._during(conn, evidence, consume)

    def prepare_current(self, conn, *, business_ref):
        with conn.transaction():
            brief_ref = self.brief.prepare_current(conn, business_ref=business_ref)

            def build(tx, store, body, spec, business, actor):
                key = 'snapshot-bundle-' + canonical_hash(dict(scope=self.scope.key, policy=_POLICY,
                                                              request=body.model_dump(mode='json', by_alias=True)))
                tx.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (key,))
                request = BusinessInvestigationEvidenceBuildRequest(idempotency_key=key, brief_ref=body.brief_ref,
                    required_fact_ids=body.required_fact_ids, supporting_evidence_refs=body.item_refs,
                    cutoff_at=body.cutoff_at, marking=body.marking)
                response = BusinessInvestigationEvidenceBuilder(store).build(self.scope, spec.runtime, request, actor,
                    created_at=datetime.fromisoformat(business['createdAt']))
                reference = _ref(response.bundle)
                self._read(tx, store, body, actor, reference)
                return reference
            return self._during(conn, business_ref, brief_ref, build)

    def read_current(self, conn, *, business_ref, bundle_ref):
        reference = InvestigationExactRef.model_validate(bundle_ref)
        if (reference.resource_type != 'EvidenceBundleRevision' or type(reference.revision) is not int
                or reference.revision != 1 or reference.receipt_id is not None):
            raise ValueError('exact snapshot bundle reference required')
        with conn.transaction():
            # This preliminary lookup only selects the brief; all authority is
            # subsequently checked under the original current guards.
            row = conn.execute('SELECT brief_ref FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s '
                               'AND bundle_id=%s AND revision=%s', (*self.scope.key, reference.resource_id, reference.revision)).fetchone()
            if row is None:
                raise LookupError('snapshot bundle unavailable')
            raw = row['brief_ref']
            brief_ref = InvestigationExactRef(resource_type=raw['resourceType'], resource_id=raw['resourceId'],
                revision=raw['revision'], content_hash='sha256:' + raw['contentHash'])
            return self._during(conn, business_ref, brief_ref,
                lambda tx, store, body, spec, business, actor: self._read(tx, store, body, actor, reference))

    def _read(self, tx, store, body, actor, reference):
        bundle = store.get_evidence_bundle(self.scope, reference.resource_id, reference.revision)
        coverage, missing, conflicts, uncertainties, freshness = store._compute_evidence_bundle_coverage(tx, self.scope, body)
        payload = dict(**body.model_dump(mode='json', by_alias=True), coverage=coverage.value, missing=missing,
                       conflicts=conflicts, uncertainties=uncertainties, freshness=freshness.value)
        if (_ref(bundle) != reference or bundle.revoked or bundle.lifecycle.value != 'frozen'
                or bundle.created_by != actor or bundle.brief_ref != body.brief_ref or bundle.item_refs != body.item_refs
                or bundle.subject_refs != body.subject_refs or bundle.cutoff_at != body.cutoff_at
                or bundle.marking != body.marking or bundle.license_summary != body.license_summary
                or (bundle.coverage, bundle.missing, bundle.conflicts, bundle.uncertainties, bundle.freshness)
                   != (coverage, missing, conflicts, uncertainties, freshness)
                or bundle.content_hash != canonical_hash(payload)):
            raise ValueError('snapshot bundle authority differs')
        return bundle

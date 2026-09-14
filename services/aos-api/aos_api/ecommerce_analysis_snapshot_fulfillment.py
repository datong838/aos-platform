"""Deliver current snapshot bundles through the original fulfillment authority."""
from aos_api.aip_production_contract_store import canonical_hash
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord, DataFulfillmentReceiptRecord
from aos_api.data_requirement_store import DataRequirementStore
from aos_api.data_fulfillment_store import DataFulfillmentStore, canonical_fulfillment_content_hash
from aos_api.ecommerce_analysis_snapshot_bundle import AnalysisSnapshotBundle
from aos_api.ecommerce_analysis_snapshot_readiness import AnalysisSnapshotReadiness, _require_unexpired
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef


class AnalysisSnapshotFulfillment:
    def __init__(self, bundle, readiness):
        if type(bundle) is not AnalysisSnapshotBundle or type(readiness) is not AnalysisSnapshotReadiness:
            raise TypeError('original snapshot bundle and readiness owners required')
        if bundle.brief.business is not readiness.context.business:
            raise ValueError('snapshot owners must share the original business context')
        self.bundle, self.readiness = bundle, readiness
        self.business, self.source = bundle.brief.business, readiness.context.source
        self.scope = bundle.scope

    @staticmethod
    def reference(record):
        return InvestigationExactRef(resource_type='DataFulfillmentReceipt', resource_id=record.receipt_id,
            revision=1, content_hash=record.content_hash, receipt_id=record.receipt_id)

    def _during(self, conn, *, business_ref, bundle_ref, readiness_ref, policy_ref, reference=None, save=False):
        with conn.transaction():
            # Selection only: the outer projection and inner owners revalidate
            # every original dependency before and after consuming these records.
            business = self.business._record(conn, business_ref)
            source = self.source._record(conn, business['selection']['evidenceRef'])
            original = DataRequirementRevisionRecord.model_validate(source['fieldContext']['requirement'])
            actor = self.source.analysis.source.actor
            factory = TransactionBoundConnectFactory(HostTransaction(conn), self.scope)
            requirements, store = DataRequirementStore(factory), DataFulfillmentStore(factory)
            deadline = None

            def current():
                req = requirements.get_current(self.scope, original.requirement_id)
                if (req != original
                        or req.status.value not in {'requested', 'accepted', 'planned'}
                        or req.blockers or req.requested_outputs != ['EvidenceBundleRevision']):
                    raise ValueError('current requirement does not permit snapshot bundle fulfillment')
                bundle = self.bundle.read_current(conn, business_ref=business_ref, bundle_ref=bundle_ref)
                ready = self.readiness.read_current(conn, reference=readiness_ref,
                    business_ref=business_ref, policy_ref=policy_ref)
                if (bundle.coverage.value != 'complete' or bundle.freshness.value != 'fresh'
                        or bundle.missing or bundle.conflicts or ready.status.value != 'ready'
                        or ready.investigation is None or ready.investigation.status.value != 'ready'
                        or ready.investigation.unmet_facts or ready.investigation.coverage_ratio != 1
                        or len(ready.sources) != 12):
                    raise ValueError('snapshot fulfillment requires complete current evidence')
                now = HostTransaction(conn).execute('SELECT clock_timestamp() AS now').fetchone()['now']
                if now >= req.expires_at:
                    raise ValueError('snapshot requirement expired')
                _require_unexpired(ready, now)
                return req, bundle, ready

            def consume(projection):
                nonlocal deadline
                if projection.payload != source['projection']:
                    raise ValueError('snapshot projection differs from original source evidence')
                req, bundle, ready = before = current()
                deadline = min(req.expires_at, *(s.freshness_expires_at for s in ready.sources))
                req_ref = InvestigationExactRef(resource_type='DataRequirementRevision', resource_id=req.requirement_id,
                    revision=req.revision, content_hash=req.content_hash)
                artifact = InvestigationExactRef.model_validate(bundle_ref)
                ready_ref = InvestigationExactRef(resource_type='SourceReadinessEnvelope',
                    resource_id=ready.receipt_ref.resource_id, revision=1,
                    content_hash='sha256:' + ready.receipt_ref.content_hash, receipt_id=ready.receipt_ref.resource_id)
                identity = canonical_hash(dict(mode='snapshot-bundle-fulfillment/v1', tenant=self.scope.key, actor=actor,
                    requirement=req_ref.model_dump(mode='json'), bundle=artifact.model_dump(mode='json'),
                    readiness=ready_ref.model_dump(mode='json')))
                receipt_id = 'snapshot-fulfillment-receipt-' + identity
                key = 'snapshot-fulfillment-' + identity
                tx = HostTransaction(conn)
                tx.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (key,))
                row = tx.execute('SELECT content_hash FROM data_fulfillment_receipt '
                    'WHERE org_id=%s AND project_id=%s AND receipt_id=%s', (*self.scope.key, receipt_id)).fetchone()
                existing = None
                if row is not None:
                    ref = InvestigationExactRef(resource_type='DataFulfillmentReceipt', resource_id=receipt_id,
                        revision=1, content_hash='sha256:' + str(row['content_hash']).strip(), receipt_id=receipt_id)
                    existing = store.read_exact(self.scope, ref)
                    if existing is None:
                        raise ValueError('original fulfillment disappeared')
                if not save and existing is None:
                    raise LookupError('snapshot fulfillment unavailable')
                now = tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                fulfilled_at = existing.fulfilled_at if existing else now
                if fulfilled_at > now:
                    raise ValueError('original fulfillment is dated in the future')
                item = DataFulfillmentReceiptRecord(tenant=req.tenant, fulfillment_id=key, receipt_id=receipt_id,
                    requirement_ref=req_ref, status='fulfilled', artifact_refs=[artifact], source_readiness_ref=ready_ref,
                    cutoff_at=req.cutoff_at, fulfilled_at=fulfilled_at, content_hash='sha256:' + '0'*64, created_by=actor)
                item = item.model_copy(update={'content_hash': canonical_fulfillment_content_hash(item)})
                if existing is not None and existing != item:
                    raise ValueError('original fulfillment differs from current snapshot identity')
                exact = self.reference(item)
                if not save and InvestigationExactRef.model_validate(reference) != exact:
                    raise ValueError('fulfillment reference differs from current snapshot identity')
                if save:
                    result = store.bind(self.scope, actor, key, item)
                    if (result.receipt_id, result.etag) != (receipt_id, item.content_hash):
                        raise ValueError('original fulfillment binding differs')
                if store.read_exact(self.scope, exact) != item or current() != before:
                    raise ValueError('snapshot fulfillment authority changed during consumption')
                return item

            result = self.source._projections.run_current(conn, scope=self.scope,
                group_id=source['projection']['groupId'], actor=actor,
                bindings=tuple((PipelineExactRef.model_validate(m['controlRef']), m['runId'])
                    for m in source['projection']['members']), execute=consume)
            if deadline is None or HostTransaction(conn).execute('SELECT clock_timestamp() AS now').fetchone()['now'] >= deadline:
                raise ValueError('snapshot fulfillment expired before transaction completion')
            return result

    def put_current(self, conn, *, business_ref, bundle_ref, readiness_ref, policy_ref):
        return self._during(conn, business_ref=business_ref, bundle_ref=bundle_ref,
            readiness_ref=readiness_ref, policy_ref=policy_ref, save=True)

    def read_current(self, conn, *, reference, business_ref, bundle_ref, readiness_ref, policy_ref):
        return self._during(conn, business_ref=business_ref, bundle_ref=bundle_ref,
            readiness_ref=readiness_ref, policy_ref=policy_ref, reference=reference)

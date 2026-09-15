"""Current installed six-policy set over a real PostgreSQL snapshot group."""
import hashlib
import json
from types import SimpleNamespace as NS

import pytest

from test_analysis_snapshot_native_projection_pg import (
    native_projection_case, private_database, stored, native_input_case,
    native_claims_case, host_case, control_governed, governed, service_case,
    pair, body,
)
from aos_api.ecommerce_analysis_snapshot_policy_set import AnalysisSnapshotPolicySetOwner
from aos_api.pipeline_snapshot_business_cohort import compile_business_cohort_policy
from aos_api.pipeline_snapshot_fact_quality import compile_fact_quality_policy
from aos_api.pipeline_snapshot_relationship_quality import compile_relationship_quality_policy
from aos_api.pipeline_snapshot_relationships import compile_relationship_policy
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES


def _raw(value):
    return json.dumps(value, separators=(',', ':')).encode()


@pytest.fixture
def policy_set_case(native_projection_case):
    executor, conn, args, state = native_projection_case
    controls = executor._claims._controls
    kinds = [item.object_type for item in CANONICAL_QYH_SOURCES]
    relationship_doc = dict(schemaVersion='aos.snapshot-relationships/v2', objectTypes=kinds,
        rules=[dict(linkType='Shop.hasWeapp', rowType='Weapp', parentType='Shop',
            referenceProperty='siteId', direction='parent-to-row', encoding='positive-id', allowUnset=False)],
        retirement=dict(mode='present-rows-only', requireCompleteReferences=True,
            rejectNewerThanObservation=True, allowMissingRowDeletion=False))
    relationship = compile_relationship_policy(relationship_doc)
    quality_doc = dict(schemaVersion='aos.snapshot-relationship-quality/v1',
        relationshipPolicyHash=relationship.content_hash,
        purposes=[dict(purposeCode='initial_store_analysis',
            rules=[dict(linkType='Shop.hasWeapp', requirement='required')])])
    quality = compile_relationship_quality_policy(quality_doc, relationship_policy=relationship)
    cohort_doc = dict(schemaVersion='aos.snapshot-business-cohort/v1',
        relationshipPolicyHash=relationship.content_hash, purposeCode='initial_store_analysis',
        windowBoundary='start-inclusive-end-exclusive',
        rules=[dict(objectType=kind, basis='snapshot', statusFilter=None) for kind in kinds])
    cohort = compile_business_cohort_policy(cohort_doc, relationship_policy=relationship)
    field_doc = dict(schemaVersion='aos.snapshot-fact-quality/v1',
        cohortPolicyHash=cohort.content_hash, relationshipQualityPolicyHash=quality.content_hash,
        purposeCode='initial_store_analysis',
        facts=[dict(objectType=kind, fields=[dict(property='name', kind='nonblank-string')]) for kind in kinds])
    fields = compile_fact_quality_policy(field_doc, relationship_policy=relationship,
        cohort_policy=cohort, quality_policy=quality)
    business_doc = dict(schemaVersion='aos.snapshot-business-facts/v1',
        fieldPolicyHash=fields.content_hash, purposeCode='initial_store_analysis',
        facts=[dict(objectType=kind, mode='records', fields=['name']) for kind in kinds])
    readiness_doc = dict(schemaVersion='aos.snapshot-readiness-policy/v1',
        fieldPolicyHash=fields.content_hash, relationshipQualityPolicyHash=quality.content_hash,
        purposeCode='initial_store_analysis', freshnessMode='requirement-oldest-observation',
        reconciliationMode='current-original-base-and-derived', queryBindingId='query-twelve',
        sources=[dict(pipelineId=item.pipeline_id, objectType=item.object_type)
            for item in CANONICAL_QYH_SOURCES])
    names = AnalysisSnapshotPolicySetOwner.POLICIES
    documents = {path: _raw(document) for (_, path), document in zip(names, (
        relationship_doc, quality_doc, cohort_doc, field_doc, business_doc, readiness_doc))}
    artifacts = [dict(relativePath=path, digest='sha256:' + hashlib.sha256(raw).hexdigest(),
        size=len(raw), mediaType='application/json') for path, raw in documents.items()]
    selections = controls._selections
    old_record = selections._artifacts.load_record
    selections._artifacts.load_record = lambda selected: NS(
        manifest=old_record(selected).manifest, artifacts=artifacts)
    selections._artifacts.read_artifact = lambda selected, path, limit: documents[path]
    conn.execute('SET ROLE aos_runtime')
    conn.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)", args['scope'].key)
    return AnalysisSnapshotPolicySetOwner(controls=controls), conn, dict(scope=args['scope'],
        refs=tuple(ref for ref, _ in args['bindings']), actor=args['actor']), state, documents, artifacts, selections


def test_current_installation_resolves_and_compiles_six_exact_policies(policy_set_case):
    owner, conn, args, _, _, _, _ = policy_set_case
    seen = []
    with conn.transaction():
        result = owner.run_current(conn, **args, execute=lambda current: seen.append(current) or 'ok')
    assert result == 'ok' and len(seen) == 1
    current = seen[0]
    assert tuple((ref.resource_type, ref.resource_id) for ref in current.refs) == owner.POLICIES
    assert len({ref.revision for ref in current.refs}) == 1
    assert current.business.field_policy_hash == current.fields.content_hash
    assert current.readiness.field_policy_hash == current.fields.content_hash
    assert current.readiness.relationship_quality_policy_hash == current.quality.content_hash


@pytest.mark.parametrize('fault', ['missing', 'digest', 'export', 'installation', 'release', 'changed'])
def test_incomplete_or_changed_installed_policy_set_never_escapes(policy_set_case, fault):
    owner, conn, args, state, documents, artifacts, selections = policy_set_case
    if fault == 'missing':
        artifacts.pop()
    elif fault == 'digest':
        artifacts[0]['digest'] = 'sha256:' + '0' * 64
    elif fault == 'export':
        record = selections._artifacts.load_record
        selections._artifacts.load_record = lambda selected: NS(
            manifest=NS(spec=NS(exports=NS(policies=[]))), artifacts=record(selected).artifacts)
    elif fault == 'installation':
        selections._store = NS(load_active_baseline_in_transaction=lambda *a, **k:
            NS(lock=NS(payload=NS(resolved=[]))))
    elif fault == 'release':
        state['denied'] = True
    def consume(current):
        if fault == 'changed':
            documents[current.refs[-1].resource_id] += b' '
        return 'uncommitted'
    with pytest.raises((ValueError, PermissionError, KeyError)):
        with conn.transaction():
            owner.run_current(conn, **args, execute=consume)

"""Original PG cohort/control proofs; source and signed package are explicit fixtures."""
import hashlib
import json
import pytest
from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from test_snapshot_group_assessment_owner_pg import assessment_case
from aos_api.pipeline_snapshot_relationships import compile_relationship_policy
from aos_api.pipeline_snapshot_group_quality_owner import PipelineSnapshotGroupQualityOwner


@pytest.fixture
def quality_case(assessment_case):
    executor, conn, args, state, _, ref = assessment_case
    relation = compile_relationship_policy(json.loads(state['policy_raw']))
    document = dict(schemaVersion='aos.snapshot-relationship-quality/v1', relationshipPolicyHash=relation.content_hash,
        purposes=[dict(purposeCode='initial_store_analysis', rules=[dict(linkType='Shop.hasWeapp', requirement='required')])])
    state['quality_raw'] = json.dumps(document).encode()
    quality_ref = ref.model_copy(update={'resource_type':'SnapshotRelationshipQualityPolicy',
        'resource_id':'content/policies/quality.json', 'content_hash':'sha256:'+hashlib.sha256(state['quality_raw']).hexdigest()})
    assets = executor._claims._controls._selections._artifacts
    assets.read_artifact = lambda selected, path, limit: state['quality_raw'] if path == quality_ref.resource_id else state['policy_raw']
    return executor, conn, args | {'policy_ref':ref, 'quality_ref':quality_ref}, state, PipelineSnapshotGroupQualityOwner(claims=executor._claims)


@pytest.mark.parametrize('empty', [False, True])
def test_current_quality_is_bound_and_source_not_reread(quality_case, empty):
    executor, conn, args, state, owner = quality_case
    state['empty'] = empty
    prepared = executor.prepare(**{k:v for k,v in args.items() if k not in ('policy_ref','quality_ref')})
    with conn.transaction(): first = owner.run_current(conn, **args, execute=lambda c:c)
    with conn.transaction(): again = owner.run_current(conn, **args, execute=lambda c:c)
    assert first == again and first.content_hash.startswith('sha256:')
    assert first.assessment.input.manifest_hash == prepared.manifest_hash
    assert first.measurement.counts['Shop.hasWeapp']['completeRows'] == (0 if empty else 1)
    assert first.quality_ref == args['quality_ref'] and state['calls'] == 1


def test_missing_input_never_reads_source(quality_case):
    _, conn, args, state, owner = quality_case
    with pytest.raises((LookupError, RuntimeError)), conn.transaction():
        owner.run_current(conn, **args, execute=lambda c:pytest.fail('input unavailable'))
    assert state['calls'] == 0


@pytest.mark.parametrize('fault', ['version','hash','export','type','tenant'])
def test_exact_quality_reference_and_tenant_required(quality_case, fault):
    executor, conn, args, state, owner = quality_case
    executor.prepare(**{k:v for k,v in args.items() if k not in ('policy_ref','quality_ref')})
    ref = args['quality_ref']
    changes = dict(version={'revision':'999'}, hash={'content_hash':'sha256:'+'0'*64},
        export={'resource_id':'private/quality.json'}, type={'resource_type':'SnapshotRelationshipPolicy'})
    if fault == 'tenant':
        from aos_api.tenant_scope import TenantScope
        args = args | {'scope':TenantScope(org_id='dev-org', project_id='dev-project')}
    else: args = args | {'quality_ref':ref.model_copy(update=changes[fault])}
    with pytest.raises((ValueError, RuntimeError, PermissionError, LookupError)), conn.transaction():
        owner.run_current(conn, **args, execute=lambda c:pytest.fail('invalid authority'))
    assert state['calls'] == 1


@pytest.mark.parametrize('fault', ['counts','purposes','input','policy','release'])
def test_mutation_or_revocation_during_callback_rejected(quality_case, fault):
    executor, conn, args, state, owner = quality_case
    executor.prepare(**{k:v for k,v in args.items() if k not in ('policy_ref','quality_ref')})
    def consume(current):
        if fault == 'counts': current.measurement.counts['Shop.hasWeapp']['completeRows'] = 99
        elif fault == 'purposes': current.measurement.purposes.clear()
        elif fault == 'input': current.assessment.input.parents[0]['outputRows'].clear()
        elif fault == 'policy': state['quality_raw'] += b' '
        else: state['policy_denied'] = True
    with pytest.raises((ValueError, RuntimeError, PermissionError)), conn.transaction():
        owner.run_current(conn, **args, execute=consume)
    assert state['calls'] == 1


@pytest.mark.parametrize('fault', ['other_relationship', 'duplicate_json'])
def test_valid_artifact_hash_does_not_override_policy_semantics(quality_case, fault):
    executor, conn, args, state, owner = quality_case
    executor.prepare(**{k:v for k,v in args.items() if k not in ('policy_ref','quality_ref')})
    if fault == 'other_relationship':
        document = json.loads(state['quality_raw'])
        document['relationshipPolicyHash'] = 'sha256:'+'0'*64
        state['quality_raw'] = json.dumps(document).encode()
    else:
        state['quality_raw'] = state['quality_raw'].replace(b'{', b'{"purposes":[],', 1)
    ref = args['quality_ref'].model_copy(update={'content_hash':'sha256:'+hashlib.sha256(state['quality_raw']).hexdigest()})
    with pytest.raises(ValueError), conn.transaction():
        owner.run_current(conn, **(args | {'quality_ref':ref}), execute=lambda c:pytest.fail('invalid semantics'))
    assert state['calls'] == 1

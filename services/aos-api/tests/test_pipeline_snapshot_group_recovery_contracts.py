"""Renewal changes execution windows, never original input or business scope."""
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4
import pytest

from tests.test_pipeline_runtime_control_contracts import payload
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef,PipelineRuntimeControlDraft
from aos_api.pipeline_runtime_control_owner import RuntimeControlRecord,build_control_payload
from aos_api.source_readiness_contracts import CANONICAL_QYH_PIPELINE_IDS
from aos_api.pipeline_snapshot_group_recovery_contracts import validate_saved_group_control_renewal


def record(draft,*,identity=None,revision=1,previous=None,actor='test-executor'):
    draft=PipelineRuntimeControlDraft.model_validate(draft)
    identity=identity or str(uuid4())
    content=build_control_payload(draft=draft,control_id=identity,revision=revision,previous_hash=previous,actor=actor)
    ref=PipelineExactRef(resource_type='PipelineRuntimeControlRevision',resource_id='pipeline-control-'+identity,
        revision=revision,content_hash=canonical_sha256(content))
    return RuntimeControlRecord(ref,draft,actor,previous)


def successor(old,**changes):
    draft=old.draft.model_copy(update=changes)
    return record(draft,identity=old.ref.resource_id.removeprefix('pipeline-control-'),
        revision=old.ref.revision+1,previous=old.ref.content_hash,actor=old.actor)


@pytest.fixture
def controls():
    old=[];new=[]
    for pipeline in CANONICAL_QYH_PIPELINE_IDS:
        body=payload();body.update(orgId='org-org',projectId='dev-project',pipelineId=pipeline)
        body['sourceSelectionRef']['resourceId']='source-selection-'+str(uuid4())
        original=record(PipelineRuntimeControlDraft.model_validate(body))
        selection=original.draft.source_selection_ref.model_copy(update={'revision':2,'content_hash':'sha256:'+'f'*64})
        current=successor(original,expires_at=original.draft.expires_at+timedelta(hours=1),source_selection_ref=selection)
        old.append(original);new.append(current)
    return tuple(old),tuple(new)


def test_only_window_renewal_is_valid_in_any_member_order(controls):
    old,new=controls
    assert validate_saved_group_control_renewal(old,tuple(reversed(new))) is None


def test_next_day_execution_window_does_not_rewrite_original_window(controls):
    old,new=controls
    later=tuple(successor(o,source_selection_ref=n.draft.source_selection_ref,
        not_before=o.draft.not_before+timedelta(days=2),expires_at=o.draft.expires_at+timedelta(days=2)) for o,n in zip(old,new))
    assert validate_saved_group_control_renewal(old,later) is None
    assert old[0].draft.not_before<later[0].draft.not_before


@pytest.mark.parametrize('fault',['missing','duplicate','list','tenant','actor','control-family','selection-family',
    'control-revision','selection-revision','same-expiry','short-expiry','earlier-start','no-common-window','hash'])
def test_group_identity_and_window_drift_is_rejected(controls,fault):
    old,new=controls
    changed=list(new);first=new[0];original=old[0]
    if fault=='missing':changed.pop()
    elif fault=='duplicate':changed[-1]=changed[0]
    elif fault=='list':
        with pytest.raises((ValueError,TypeError)):validate_saved_group_control_renewal(old,changed)
        return
    elif fault=='tenant':changed[0]=successor(original,**dict(first.draft.model_dump(),org_id='dev-org'))
    elif fault=='actor':changed[0]=record(first.draft,identity=first.ref.resource_id.removeprefix('pipeline-control-'),revision=2,previous=original.ref.content_hash,actor='another')
    elif fault=='control-family':changed[0]=record(first.draft,revision=2,previous=original.ref.content_hash)
    elif fault=='control-revision':changed[0]=record(first.draft,identity=original.ref.resource_id.removeprefix('pipeline-control-'))
    elif fault=='selection-family':changed[0]=successor(original,expires_at=first.draft.expires_at,
        source_selection_ref=first.draft.source_selection_ref.model_copy(update={'resource_id':'source-selection-'+str(uuid4())}))
    elif fault=='selection-revision':changed[0]=successor(original,expires_at=first.draft.expires_at)
    elif fault in {'same-expiry','short-expiry'}:
        changed[0]=successor(original,source_selection_ref=first.draft.source_selection_ref,
            expires_at=original.draft.expires_at-timedelta(minutes=0 if fault=='same-expiry' else 1))
    elif fault=='earlier-start':changed[0]=successor(original,**dict(first.draft.model_dump(),not_before=original.draft.not_before-timedelta(seconds=1)))
    elif fault=='no-common-window':changed[0]=successor(original,source_selection_ref=first.draft.source_selection_ref,
        not_before=original.draft.not_before+timedelta(days=2),expires_at=original.draft.expires_at+timedelta(days=2))
    else:changed[0]=replace(first,ref=first.ref.model_copy(update={'content_hash':'sha256:'+'0'*64}))
    with pytest.raises((ValueError,TypeError)):validate_saved_group_control_renewal(old,tuple(changed))


@pytest.mark.parametrize('field,value',[
    ('max_source_calls',2),('row_limit',99),('timeout_seconds',29),('graph_revision',2),
    ('graph_hash','c'*64),('source_id','other-source'),('execution_epoch',2),
    ('generation','77777777-7777-4777-8777-777777777777'),
])
def test_business_and_budget_fields_cannot_change(controls,field,value):
    old,new=controls
    changed=successor(old[0],**dict(new[0].draft.model_dump(),**{field:value}))
    with pytest.raises(ValueError):validate_saved_group_control_renewal(old,(changed,)+new[1:])


@pytest.mark.parametrize('field',['configuration_ref','mapping_ref','schema_ref','masking_policy_ref','package_ref','source_configuration_ref','installation_ref'])
def test_nested_authority_cannot_change(controls,field):
    old,new=controls
    original=new[0].draft
    nested=getattr(original,field)
    key='lock_hash' if field=='installation_ref' else 'hash' if field=='configuration_ref' else 'content_hash'
    changed=successor(old[0],**dict(original.model_dump(),**{field:nested.model_copy(update={key:'sha256:'+'0'*64})}))
    with pytest.raises(ValueError):validate_saved_group_control_renewal(old,(changed,)+new[1:])


def test_unvalidated_copy_cannot_extend_window_beyond_twenty_four_hours(controls):
    old,new=controls
    bad=replace(new[0],draft=new[0].draft.model_copy(update={
        'expires_at':new[0].draft.not_before+timedelta(days=1,seconds=1)}))
    with pytest.raises(ValueError,match='24 hours'):
        validate_saved_group_control_renewal(old,(bad,)+new[1:])


def test_immediate_successor_must_reference_original_control_hash(controls):
    old,new=controls
    bad=record(new[0].draft,identity=old[0].ref.resource_id.removeprefix('pipeline-control-'),
        revision=2,previous='sha256:'+'0'*64)
    with pytest.raises(ValueError,match='predecessor'):
        validate_saved_group_control_renewal(old,(bad,)+new[1:])

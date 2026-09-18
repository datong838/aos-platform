"""Saved-input renewal differences only: validation never grants execution."""
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef,PipelineRuntimeControlDraft
from aos_api.pipeline_runtime_control_owner import RuntimeControlRecord,build_control_payload,_ref_identity
from aos_api.source_readiness_contracts import CANONICAL_QYH_PIPELINE_IDS


def _records(values):
    if type(values) is not tuple or len(values)!=12:
        raise ValueError('exact twelve renewal controls required')
    checked={};controls=set();selections=set()
    for value in values:
        if type(value) is not RuntimeControlRecord:raise TypeError('original control records required')
        draft=PipelineRuntimeControlDraft.model_validate(value.draft)
        ref=PipelineExactRef.model_validate(value.ref)
        identity=_ref_identity(ref,'PipelineRuntimeControlRevision','pipeline-control-')
        selection=_ref_identity(draft.source_selection_ref,'SourceSelectionRevision','source-selection-')
        content=build_control_payload(draft=draft,control_id=identity,revision=ref.revision,
            previous_hash=value.previous_hash,actor=value.actor)
        if canonical_sha256(content)!=ref.content_hash:
            raise ValueError('renewal control content differs')
        if draft.pipeline_id in checked or identity in controls or selection in selections:
            raise ValueError('unique renewal pipelines and authorities required')
        checked[draft.pipeline_id]=RuntimeControlRecord(ref,draft,value.actor,value.previous_hash)
        controls.add(identity);selections.add(selection)
    if set(checked)!=set(CANONICAL_QYH_PIPELINE_IDS):
        raise ValueError('complete canonical renewal group required')
    first=next(iter(checked.values()))
    common=('org_id','project_id','installation_ref','generation','execution_epoch','configuration_ref',
        'package_ref','source_id','source_configuration_ref','schema_ref','masking_policy_ref')
    if any(item.actor!=first.actor or any(getattr(item.draft,f)!=getattr(first.draft,f) for f in common)
           for item in checked.values()):
        raise ValueError('renewal group common authority differs')
    if max(item.draft.not_before for item in checked.values())>=min(item.draft.expires_at for item in checked.values()):
        raise ValueError('renewal group has no common window')
    return checked


def validate_saved_group_control_renewal(original,current):
    """Call only alongside authoritative ledger/input/current-permission checks.

    The original observation window and renewed execution window are distinct.
    This function neither checks the current time nor permits source reads.
    """
    old,new=_records(original),_records(current)
    excluded={'not_before','expires_at','source_selection_ref'}
    for pipeline in CANONICAL_QYH_PIPELINE_IDS:
        before,after=old[pipeline],new[pipeline]
        first,next_=before.draft,after.draft
        if (before.actor!=after.actor or before.ref.resource_id!=after.ref.resource_id
                or after.ref.revision<=before.ref.revision
                or first.source_selection_ref.resource_id!=next_.source_selection_ref.resource_id
                or next_.source_selection_ref.revision<=first.source_selection_ref.revision):
            raise ValueError('renewal must retain original actor and authority families')
        if after.ref.revision==before.ref.revision+1 and after.previous_hash!=before.ref.content_hash:
            raise ValueError('renewal immediate predecessor differs')
        if (next_.not_before<first.not_before or next_.expires_at<=first.expires_at
                or first.model_dump(mode='json',exclude=excluded)!=next_.model_dump(mode='json',exclude=excluded)):
            raise ValueError('renewal may only advance execution window and selection')


def validate_saved_group_successor_transfer(original,current):
    """Require the replacement controls to preserve the saved read semantics.

    Runtime identity and immutable control families necessarily change when a
    failed installation is replaced.  They are resolved by the current Owners;
    this comparison only permits those replacement fields and the fresh window.
    """
    old,new=_records(original),_records(current)
    excluded={'not_before','expires_at','source_selection_ref','installation_ref',
        'generation','execution_epoch','configuration_ref','package_ref'}
    for pipeline in CANONICAL_QYH_PIPELINE_IDS:
        before,after=old[pipeline],new[pipeline]
        if before.actor!=after.actor:
            raise ValueError('successor recovery actor differs')
        if (before.draft.model_dump(mode='json',exclude=excluded)
                !=after.draft.model_dump(mode='json',exclude=excluded)):
            raise ValueError('successor recovery read semantics differ')


def exact_saved_recovery_transfer_request(request,*,scope,current,group_id,recovery_ref,actor):
    """Match the complete immutable definition request; reading it grants nothing."""
    expected=dict(orgId=scope.org_id,projectId=scope.project_id,
        definitionId=current['definitionId'],actor=actor,intent='transfer_saved_recovery',
        expectedRef=current['priorRef'],settings=None,
        transfer=dict(groupId=group_id,expectedRecoveryRef=recovery_ref))
    return type(request) is dict and request==expected

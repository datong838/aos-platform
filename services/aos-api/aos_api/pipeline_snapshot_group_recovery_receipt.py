"""Immutable recovery history decoding. Reading a receipt is not permission."""
from copy import deepcopy
from datetime import timezone
from uuid import UUID
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.control_policy import validate_idempotency_key
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner


def _ref(kind,prefix,identity,revision,digest):
    return dict(resourceType=kind,resourceId=prefix+str(identity),revision=revision,contentHash=digest)


def recovery_body(row):
    """Canonical serialization only; callers still need original locked Owners."""
    group=str(row['group_id']);definition=str(row['definition_id'])
    previous=None if row['previous_revision'] is None else _ref('SnapshotGroupRecoveryRevision',
        'snapshot-recovery-',group,row['previous_revision'],row['previous_hash'])
    return dict(schemaVersion='aos.snapshot-group-recovery/v1',mode='saved-input-only',
        orgId=row['org_id'],projectId=row['project_id'],groupId=group,revision=row['revision'],priorRef=previous,
        originalDefinitionRef=_ref('SnapshotScheduleDefinitionRevision','snapshot-schedule-',definition,
            row['original_definition_revision'],row['original_definition_hash']),
        currentDefinitionRef=_ref('SnapshotScheduleDefinitionRevision','snapshot-schedule-',definition,
            row['current_definition_revision'],row['current_definition_hash']),
        originalScheduleClaimHash=row['original_schedule_hash'],originalSourceClaimHash=row['original_source_hash'],
        inputManifestHash=row['input_manifest_hash'],actor=row['actor'],executor=row['executor'],
        policyRef=deepcopy(row['policy_ref']),requestHash=row['request_hash'],createdAt=row['created_at'].astimezone(timezone.utc).isoformat())


def decode_recovery_receipt(row):
    expected=recovery_body(row)
    if (row['body']!=expected or row['content_hash']!=canonical_sha256(expected)
            or row['request_hash']!=canonical_sha256(row['request'])):
        raise ValueError('snapshot recovery history content differs')
    return dict(ref=_ref('SnapshotGroupRecoveryRevision','snapshot-recovery-',row['group_id'],
        row['revision'],row['content_hash']),body=expected,request=deepcopy(row['request']),
        requestHash=row['request_hash'],idempotencyKey=row['idempotency_key'])


def read_recovery_receipt(conn,*,scope,group_id,revision=None,idempotency_key=None):
    PipelineScheduleControlOwner._identity(conn,scope)
    if type(group_id) is not str or str(UUID(group_id))!=group_id:
        raise ValueError('canonical recovery group required')
    if revision is not None and (type(revision) is not int or revision<1):
        raise ValueError('positive recovery revision required')
    if revision is not None and idempotency_key is not None:
        raise ValueError('one recovery history selector required')
    where='';params=[*scope.key,group_id]
    if revision is not None:where=' AND revision=%s';params.append(revision)
    if idempotency_key is not None:
        where=' AND idempotency_key=%s';params.append(validate_idempotency_key(idempotency_key))
    row=conn.execute('''SELECT * FROM public.pipeline_snapshot_group_recovery_receipt
        WHERE org_id=%s AND project_id=%s AND group_id=%s'''+where+' ORDER BY revision DESC LIMIT 1',params).fetchone()
    return decode_recovery_receipt(row) if row else None

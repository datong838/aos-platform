"""Current management may inspect original input; these facts grant no execution."""
from dataclasses import dataclass
from datetime import datetime
import re

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ec_ingress_journal import IngressJournal,IngressJournalConflict,_digest
from aos_api.pipeline_runtime_control_owner import decode_control_row
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
from aos_api.pipeline_snapshot_group_recovery_contracts import _records
from aos_api.pipeline_snapshot_schedule_claim import PipelineSnapshotScheduleClaimOwner,_group_id
from aos_api.pipeline_snapshot_schedule_definition import PipelineSnapshotScheduleDefinitionOwner
from aos_api.pipeline_source_claim_owner import _decode,_text
from aos_api.pipeline_source_selection_owner import _now


@dataclass(frozen=True)
class HistoricalSnapshotInput:
    definition: dict
    schedule_claim: dict
    source_claim_hash: str
    controls: tuple
    manifest_hash: str
    manifest: dict
    read_started_at: datetime
    read_completed_at: datetime
    parents: tuple


def _require(condition,message):
    if not condition:raise IngressJournalConflict(message)


class SnapshotSavedFactsReader:
    def __init__(self,*,definitions,claims):
        if type(definitions) is not PipelineSnapshotScheduleDefinitionOwner or type(claims) is not PipelineSnapshotScheduleClaimOwner:
            raise TypeError('original definition and schedule claim Owners required')
        self._definitions,self._claims=definitions,claims

    def read(self,conn,*,scope,group_id,actor,expected_manifest_hash):
        PipelineScheduleControlOwner._identity(conn,scope)
        group_id,actor=_group_id(group_id),_text(actor,240)
        if type(expected_manifest_hash) is not str or re.fullmatch('sha256:[0-9a-f]{64}',expected_manifest_hash) is None:
            raise ValueError('exact original manifest hash required')
        schedule=self._claims.read(conn,scope=scope,group_id=group_id)
        _require(schedule is not None and schedule['schemaVersion']=='aos.snapshot-schedule-claim/v2',
            'SAVED_ORIGINAL_DEFINED_CLAIM_REQUIRED')
        identifier,ref=self._claims._definition_ref(schedule['request']['definitionRef'])
        row=conn.execute('''SELECT * FROM public.pipeline_snapshot_schedule_definition_revision
            WHERE org_id=%s AND project_id=%s AND definition_id=%s AND revision=%s''',
            (*scope.key,identifier,ref['revision'])).fetchone()
        _require(row is not None,'SAVED_ORIGINAL_DEFINITION_REQUIRED')
        definition=self._definitions._decode(row,scope,identifier)
        body=definition['body']
        if self._definitions._permission(conn,org_id=scope.org_id,project_id=scope.project_id,
                installation_id=body['installationId'],generation=body['generation'],actor=actor) is not True:
            raise PermissionError('current saved-input management permission required')
        installation=conn.execute('''SELECT generation FROM public.extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s''',
            (*scope.key,body['installationId'],body['generation'])).fetchone()
        _require(installation is not None and str(installation['generation'])==body['generation'],
            'SAVED_ORIGINAL_INSTALLATION_GENERATION_DIFFERS')
        _require(definition['ref']==ref and body['state']=='enabled' and body['executor']==schedule['request']['actor']
            and body['members']==schedule['request']['members'],'SAVED_ORIGINAL_DEFINITION_DIFFERS')
        bindings=self._definitions._saved_bindings(conn,scope,body)
        controls=[]
        for binding in bindings:
            old=conn.execute('''SELECT * FROM public.pipeline_runtime_control_revision
                WHERE org_id=%s AND project_id=%s AND control_id=%s AND revision=%s''',
                (*scope.key,binding.control_ref.resource_id.removeprefix('pipeline-control-'),binding.control_ref.revision)).fetchone()
            _require(old is not None,'SAVED_ORIGINAL_CONTROL_REQUIRED')
            control=decode_control_row(old)
            _require(control.ref==binding.control_ref and control.actor==body['executor']
                and (binding.installation_id,binding.generation)==(body['installationId'],body['generation'])
                and (control.draft.org_id,control.draft.project_id)==scope.key
                and (control.draft.installation_ref.installation_id,control.draft.generation)==(body['installationId'],body['generation']),
                'SAVED_ORIGINAL_CONTROL_DIFFERS')
            controls.append(control)
        _records(tuple(controls))
        controls=tuple(sorted(controls,key=lambda c:c.ref.resource_id))
        by_control={m['controlRef']['resourceId']:m for m in schedule['members']}
        _require(len(by_control)==12,'SAVED_ORIGINAL_CONTROLS_NOT_UNIQUE')
        expected=[]
        for control in controls:
            member=by_control.get(control.ref.resource_id)
            _require(member is not None and member['pipelineId']==control.draft.pipeline_id
                and member['controlRef']==control.ref.model_dump(mode='json',by_alias=True,exclude_none=True),'SAVED_ORIGINAL_MEMBER_DIFFERS')
            expected.append(dict(runId=member['runId'],controlRef=control.ref.model_dump(mode='json',by_alias=True),draft=control.draft.model_dump(mode='json',by_alias=True)))
        source=conn.execute('''SELECT * FROM public.pipeline_snapshot_group_claim
            WHERE org_id=%s AND project_id=%s AND group_id=%s''',(*scope.key,group_id)).fetchone()
        expected_body=dict(schemaVersion='aos.snapshot-group-claim/v1',orgId=scope.org_id,projectId=scope.project_id,
            groupId=group_id,actor=body['executor'],members=expected)
        _require(source is not None and source['binding']==expected_body and source['request_hash']==canonical_sha256(expected_body)
            and source['member_count']==12 and source['actor']==body['executor'],'SAVED_ORIGINAL_SOURCE_GROUP_DIFFERS')
        members=conn.execute('''SELECT ordinal,run_id FROM public.pipeline_snapshot_group_member
            WHERE org_id=%s AND project_id=%s AND group_id=%s ORDER BY ordinal''',(*scope.key,group_id)).fetchall()
        _require([(m['ordinal'],m['run_id']) for m in members]==[(i,m['runId']) for i,m in enumerate(expected,1)],
            'SAVED_ORIGINAL_SOURCE_MEMBERS_DIFFER')
        saved=conn.execute('''SELECT * FROM public.pipeline_snapshot_group_input
            WHERE org_id=%s AND project_id=%s AND group_id=%s''',(*scope.key,group_id)).fetchone()
        _require(saved is not None,'GROUP_ORIGINAL_INPUT_REQUIRED')
        manifest=saved['manifest'];start=saved['read_started_at'];end=saved['read_completed_at']
        _require(saved['request_hash']==source['request_hash'] and type(manifest) is dict and set(manifest)=={'members'}
            and saved['manifest_hash']==expected_manifest_hash==canonical_sha256(manifest)
            and type(manifest['members']) is list and len(manifest['members'])==12
            and saved['snapshot_basis']=='innodb-repeatable-read'
            and max(c.draft.not_before for c in controls)<=start<=end<min(c.draft.expires_at for c in controls)
            and end<=_now(conn),'GROUP_ORIGINAL_INPUT_BINDING_DRIFT')
        parents=[];journal=IngressJournal()
        for control,item,leaf in zip(controls,expected,manifest['members']):
            draft=control.draft;run_id=item['runId'];member=by_control[control.ref.resource_id]
            claim=conn.execute('''SELECT * FROM public.pipeline_controlled_source_claim
                WHERE org_id=%s AND project_id=%s AND run_id=%s''',(*scope.key,run_id)).fetchone()
            _require(claim is not None,'SAVED_ORIGINAL_SOURCE_CLAIM_REQUIRED')
            claim=_decode(claim)
            _require((claim.scope,claim.run_id,claim.actor,claim.control_ref,claim.pipeline_id,claim.installation_id,claim.generation)==
                (scope,run_id,body['executor'],control.ref,draft.pipeline_id,body['installationId'],body['generation'])
                and claim.call_ordinal<=draft.max_source_calls,'SAVED_ORIGINAL_SOURCE_CLAIM_DIFFERS')
            run=conn.execute('''SELECT schedule_id FROM public.meta_schedule_run
                WHERE org_id=%s AND project_id=%s AND id=%s''',(*scope.key,run_id)).fetchone()
            _require(run is not None and run['schedule_id']==member['scheduleId'],'SAVED_ORIGINAL_RUN_DIFFERS')
            parent=journal.read(conn,scope,run_id)
            _require(parent is not None,'INGRESS_PARENT_REQUIRED')
            _require((parent['runId'],parent['pipelineId'],parent['sourceId'],parent['sourceRevision'],parent['pipelineHash'])==
                (run_id,draft.pipeline_id,draft.source_id,draft.source_configuration_ref.resource_id.removeprefix('source-config-'),draft.graph_hash),
                'SAVED_ORIGINAL_PARENT_BINDING_DIFFERS')
            rows=parent.get('outputRows')
            _require(type(leaf) is dict and set(leaf)=={'runId','envelopeHash','rowsHash','rowCount'}
                and leaf['runId']==run_id and leaf['envelopeHash']==_digest(parent)
                and type(leaf['rowCount']) is int and 0<=leaf['rowCount']<min(c.draft.row_limit for c in controls)
                and type(leaf['rowsHash']) is str and re.fullmatch('sha256:[0-9a-f]{64}',leaf['rowsHash']) is not None
                and type(rows) is list and len(rows)==leaf['rowCount']
                and all(type(r) is dict and 'link_type' not in r for r in rows),'SAVED_ORIGINAL_INPUT_MEMBER_DIFFERS')
            parents.append(parent)
        return HistoricalSnapshotInput(definition,schedule,source['request_hash'],controls,saved['manifest_hash'],manifest,start,end,tuple(parents))

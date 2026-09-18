"""Fixed receipt, current synchronous recovery binding; never a source-read grant."""
from dataclasses import dataclass
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_runtime_control_owner import _ref_identity,decode_control_row
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
from aos_api.pipeline_snapshot_group_policy_owner import CurrentSnapshotGroupPolicy
from aos_api.pipeline_snapshot_group_recovery_contracts import validate_saved_group_control_renewal
from aos_api.pipeline_snapshot_group_recovery_receipt import read_recovery_receipt
from aos_api.pipeline_snapshot_group_saved_facts import SnapshotSavedFactsReader,HistoricalSnapshotInput
from aos_api.pipeline_source_claim_owner import _text
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES


@dataclass(frozen=True)
class CurrentSavedGroupRecovery:
    receipt: dict
    facts: HistoricalSnapshotInput
    execution: CurrentSnapshotGroupPolicy


class SnapshotGroupRecoveryAuthority:
    def __init__(self,*,definitions,claims,ref):
        self._facts=SnapshotSavedFactsReader(definitions=definitions,claims=claims)
        if definitions._groups is None or definitions._groups._groups._controls is not claims._groups._controls:
            raise TypeError('shared original current controls required')
        self._definitions,self._claims=definitions,claims
        self._ref=PipelineExactRef.model_validate(ref)
        self._group_id=_ref_identity(self._ref,'SnapshotGroupRecoveryRevision','snapshot-recovery-')

    def run_current(self,conn,*,scope,actor,bindings,execute):
        PipelineScheduleControlOwner._identity(conn,scope)
        actor=_text(actor,240)
        if not callable(execute) or type(bindings) is not tuple or len(bindings)!=12:
            raise ValueError('complete synchronous recovery consumer required')
        pairs=[]
        for item in bindings:
            if type(item) is not tuple or len(item)!=2:raise ValueError('exact recovery control/run pair required')
            ref=PipelineExactRef.model_validate(item[0])
            _ref_identity(ref,'PipelineRuntimeControlRevision','pipeline-control-')
            pairs.append((ref,_text(item[1],200)))
        if len({r for _,r in pairs})!=12 or len({ref.resource_id for ref,_ in pairs})!=12:
            raise ValueError('unique recovery members required')
        with conn.transaction(), self._definitions._permission.reuse_locked_transaction(conn):
            before=self._load(conn,scope,actor,tuple(pairs))
            receipt,facts,definition,current_bindings=before
            def consume(execution):
                controls=[]
                for ref,draft,_ in execution.group.members:
                    row=conn.execute('''SELECT * FROM public.pipeline_runtime_control_revision
                        WHERE org_id=%s AND project_id=%s AND control_id=%s AND revision=%s''',
                        (*scope.key,ref.resource_id.removeprefix('pipeline-control-'),ref.revision)).fetchone()
                    if row is None:raise ValueError('recovery current control unavailable')
                    record=decode_control_row(row)
                    if record.ref!=ref or record.draft!=draft:raise ValueError('recovery execution control differs')
                    controls.append(record)
                validate_saved_group_control_renewal(facts.controls,tuple(controls))
                types={d.pipeline_id:m.read_spec.object_type for _,d,m in execution.group.members}
                if types!={s.pipeline_id:s.object_type for s in CANONICAL_QYH_SOURCES}:
                    raise ValueError('canonical recovery mappings required')
                if any(row.get('ot')!=types[parent['pipelineId']] for parent in facts.parents for row in parent['outputRows']):
                    raise ValueError('saved recovery mapping differs')
                result=execute(CurrentSavedGroupRecovery(receipt,facts,execution))
                _reject_deferred(result)
                if self._load(conn,scope,actor,tuple(pairs))!=before:
                    raise ValueError('current recovery facts changed during consumption')
                return result
            return self._definitions._groups.run_current(conn,scope=scope,actor=actor,
                refs=tuple(b.control_ref for b in current_bindings),
                policy_ref=PipelineExactRef.model_validate(receipt['body']['policyRef']),execute=consume)

    def _load(self,conn,scope,actor,pairs):
        receipt=read_recovery_receipt(conn,scope=scope,group_id=self._group_id)
        if receipt is None:raise LookupError('snapshot recovery receipt unavailable')
        if receipt['ref']!=self._ref.model_dump(mode='json',by_alias=True,exclude_none=True):
            raise ValueError('snapshot recovery receipt is not current')
        body=receipt['body']
        if actor!=body['executor']:raise PermissionError('original recovery executor required')
        facts=self._facts.read(conn,scope=scope,group_id=self._group_id,actor=body['actor'],
            expected_manifest_hash=body['inputManifestHash'])
        if (facts.definition['ref']!=body['originalDefinitionRef'] or facts.source_claim_hash!=body['originalSourceClaimHash']
                or canonical_sha256(facts.schedule_claim)!=body['originalScheduleClaimHash']
                or facts.definition['body']['executor']!=actor):
            raise ValueError('recovery original authority differs')
        identifier=facts.definition['body']['definitionId']
        if self._definitions._permission(conn,org_id=scope.org_id,project_id=scope.project_id,
                installation_id=facts.definition['body']['installationId'],generation=facts.definition['body']['generation'],actor=actor) is not True:
            raise PermissionError('current recovery executor permission required')
        conn.execute('''SELECT revision FROM public.pipeline_snapshot_schedule_definition_head
            WHERE org_id=%s AND project_id=%s AND definition_id=%s FOR UPDATE''',(*scope.key,identifier))
        definition=self._definitions.read(conn,scope=scope,definition_id=identifier)
        if definition is None or definition['ref']!=body['currentDefinitionRef'] or definition['body']['state']!='enabled':
            raise ValueError('recovery definition is not current enabled authority')
        row=conn.execute('''SELECT request FROM public.pipeline_snapshot_schedule_definition_revision
            WHERE org_id=%s AND project_id=%s AND definition_id=%s AND revision=%s''',
            (*scope.key,identifier,definition['ref']['revision'])).fetchone()
        if row is None or row['request'].get('intent')!='renew_saved_group':
            raise ValueError('saved-only recovery definition required')
        if definition['body']['executor']!=actor or definition['body']['policyRef']!=body['policyRef']:
            raise ValueError('recovery definition actor or policy differs')
        bindings=self._definitions._saved_bindings(conn,scope,definition['body'])
        latest=PipelineScheduleControlOwner.read_latest_many(conn,scope=scope,schedule_ids=tuple(b.schedule_id for b in bindings))
        runs={m['scheduleId']:m['runId'] for m in facts.schedule_claim['members']}
        if latest!=bindings or {b.schedule_id for b in bindings}!=set(runs):
            raise ValueError('recovery bindings are not current')
        if set(pairs)!={(b.control_ref,runs[b.schedule_id]) for b in bindings}:
            raise ValueError('recovery requires complete exact current control and original run pairs')
        schedules=conn.execute('''SELECT id,pipeline_id,enabled,ingest FROM public.meta_schedule
            WHERE org_id=%s AND project_id=%s AND id=ANY(%s) ORDER BY id COLLATE "C" FOR UPDATE''',
            (*scope.key,list(runs))).fetchall()
        indexed={r['id']:r for r in schedules}
        members=conn.execute('''SELECT schedule_id,definition_id,revision FROM public.pipeline_snapshot_schedule_current_member
            WHERE org_id=%s AND project_id=%s AND schedule_id=ANY(%s)''',(*scope.key,list(runs))).fetchall()
        member_by_id={m['schedule_id']:m for m in members}
        for b in bindings:
            schedule=indexed.get(b.schedule_id);member=member_by_id.get(b.schedule_id)
            if (b.actor!=actor or schedule is None or member is None or schedule['enabled'] is not True
                    or (str(member['definition_id']),member['revision'])!=(identifier,definition['ref']['revision'])
                    or schedule['pipeline_id']!=b.pipeline_id or type(schedule['ingest']) is not dict
                    or schedule['ingest'].get('kind')!='pipeline-live-v1' or schedule['ingest'].get('pipelineId')!=b.pipeline_id):
                raise ValueError('recovery current schedule membership differs')
        return receipt,facts,definition,bindings

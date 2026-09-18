"""Atomic saved-input renewal. No source call, run creation, or execution grant."""
from copy import deepcopy
from datetime import datetime,timezone
from uuid import UUID
from psycopg import sql
from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.control_policy import validate_idempotency_key
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef,PipelineRuntimeControlDraft,PipelineSourceSelectionDraft
from aos_api.pipeline_runtime_control_owner import decode_control_row
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
from aos_api.pipeline_snapshot_group_completion import PipelineSnapshotGroupCompletion
from aos_api.pipeline_snapshot_group_recovery_contracts import (exact_saved_recovery_transfer_request,
    validate_saved_group_control_renewal,validate_saved_group_successor_transfer)
from aos_api.pipeline_snapshot_group_recovery_receipt import read_recovery_receipt,recovery_body,decode_recovery_receipt
from aos_api.pipeline_snapshot_group_saved_facts import SnapshotSavedFactsReader
from aos_api.pipeline_snapshot_schedule_claim import _group_id,_member
from aos_api.pipeline_snapshot_schedule_definition import _CONSTRAINTS,_wire
from aos_api.pipeline_source_claim_owner import _text
from aos_api.pipeline_source_selection_owner import _now
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES


class PipelineSnapshotGroupRecoveryOwner:
    def __init__(self,*,definitions,claims):
        self._facts=SnapshotSavedFactsReader(definitions=definitions,claims=claims)
        if definitions._groups is None:raise TypeError('current controls required for renewal')
        self._definitions,self._claims=definitions,claims
        self._controls=definitions._groups._groups._controls
        if self._controls is not claims._groups._controls:
            raise TypeError('shared original controls required')

    def renew(self,conn,*,scope,group_id,actor,expected_definition_ref,expected_recovery_ref,
              input_manifest_hash,not_before,expires_at,idempotency_key):
        PipelineScheduleControlOwner._identity(conn,scope)
        group_id,actor=_group_id(group_id),_text(actor,240)
        key=validate_idempotency_key(idempotency_key)
        identifier,expected=self._claims._definition_ref(expected_definition_ref)
        recovery=None if expected_recovery_ref is None else _wire(expected_recovery_ref)
        if recovery is not None and (recovery['resourceType'],recovery['resourceId'])!=('SnapshotGroupRecoveryRevision','snapshot-recovery-'+group_id):
            raise ValueError('exact recovery predecessor required')
        if any(type(t) is not datetime or t.utcoffset() is None for t in (not_before,expires_at)):
            raise ValueError('aware recovery window required')
        start,end=not_before.astimezone(timezone.utc),expires_at.astimezone(timezone.utc)
        request=dict(schemaVersion='aos.snapshot-group-recovery-request/v1',orgId=scope.org_id,projectId=scope.project_id,
            groupId=group_id,actor=actor,expectedDefinitionRef=expected,expectedRecoveryRef=recovery,
            inputManifestHash=input_manifest_hash,notBefore=start.isoformat(),expiresAt=end.isoformat())
        with conn.transaction():
            locked=conn.execute('SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS locked',
                (PipelineSnapshotGroupCompletion._lock_key(scope,group_id),)).fetchone()['locked']
            if locked is not True:raise IngressJournalConflict('GROUP_COMPLETION_BUSY')
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                ('snapshot-definition:'+canonical_sha256([*scope.key,identifier]),))
            facts=self._facts.read(conn,scope=scope,group_id=group_id,actor=actor,expected_manifest_hash=input_manifest_hash)
            original=facts.definition['body']
            if original['definitionId']!=identifier:raise ValueError('recovery definition family differs')
            replay=read_recovery_receipt(conn,scope=scope,group_id=group_id,idempotency_key=key)
            if replay is not None:
                if replay['request']!=request:raise ValueError('recovery idempotency request differs')
                return replay
            conn.execute('''SELECT revision FROM public.pipeline_snapshot_schedule_definition_head
                WHERE org_id=%s AND project_id=%s AND definition_id=%s FOR UPDATE''',(*scope.key,identifier))
            current=self._definitions.read(conn,scope=scope,definition_id=identifier)
            prior=read_recovery_receipt(conn,scope=scope,group_id=group_id)
            if current is None or current['ref']!=expected or (prior['ref'] if prior else None)!=recovery:
                raise ValueError('recovery predecessor is not current')
            body=current['body']
            transferred=(body['installationId'],body['generation'])!=(original['installationId'],original['generation'])
            transfer_authority=False
            if transferred:
                row=conn.execute('''SELECT request FROM public.pipeline_snapshot_schedule_definition_revision
                    WHERE org_id=%s AND project_id=%s AND definition_id=%s AND revision=%s''',
                    (*scope.key,identifier,body['revision'])).fetchone()
                transfer_authority=(row is not None and exact_saved_recovery_transfer_request(row['request'],scope=scope,
                    current=body,group_id=group_id,recovery_ref=recovery,actor=actor))
            if (body['state']=='retired' or any(body[k]!=original[k] for k in
                    ('executor','cron','timezone','policyRef')) or (transferred and not transfer_authority)):
                raise ValueError('recovery definition business scope differs')
            executor=original['executor']
            if self._definitions._permission(conn,org_id=scope.org_id,project_id=scope.project_id,
                    installation_id=body['installationId'],generation=body['generation'],actor=executor) is not True:
                raise PermissionError('current original executor permission required')
            if not start<=_now(conn)<end or not 0<(end-start).total_seconds()<=86400:
                raise ValueError('recovery window must be current and bounded')
            bindings=self._definitions._saved_bindings(conn,scope,body)
            original_members={m['scheduleId']:m for m in original['members']}
            if {b.schedule_id for b in bindings}!=set(original_members):raise ValueError('recovery schedule members differ')
            latest=PipelineScheduleControlOwner.read_latest_many(conn,scope=scope,schedule_ids=tuple(b.schedule_id for b in bindings))
            if latest!=bindings:raise ValueError('recovery bindings are not current')
            predecessors=[]
            for b in bindings:
                member=original_members[b.schedule_id]
                if (b.pipeline_id!=member['pipelineId'] or
                        (not transferred and b.control_ref.resource_id!=member['controlRef']['resourceId'])):
                    raise ValueError('recovery control family differs')
                row=conn.execute('''SELECT * FROM public.pipeline_runtime_control_revision
                    WHERE org_id=%s AND project_id=%s AND control_id=%s AND revision=%s''',
                    (*scope.key,b.control_ref.resource_id.removeprefix('pipeline-control-'),b.control_ref.revision)).fetchone()
                if row is None:raise ValueError('recovery current control missing')
                control=decode_control_row(row)
                if control.ref!=b.control_ref:raise ValueError('recovery control hash differs')
                predecessors.append(control)
            if transferred:
                validate_saved_group_successor_transfer(facts.controls,tuple(predecessors))
            elif {c.ref for c in predecessors}!={c.ref for c in facts.controls}:
                validate_saved_group_control_renewal(facts.controls,tuple(predecessors))
            if start<max(c.draft.not_before for c in predecessors) or end<=max(c.draft.expires_at for c in predecessors):
                raise ValueError('recovery window must advance its predecessor')
            self._lock_runs(conn,scope,identifier,body['revision'],bindings,facts.schedule_claim)
            def internal_key(stage,pipeline):
                return 'snapshot-recovery:'+canonical_sha256([*scope.key,group_id,key,request,stage,pipeline]).removeprefix('sha256:')
            renewed=[];new_controls=[]
            for binding,previous in zip(bindings,predecessors):
                data=previous.draft.model_dump(exclude={'schema_version','source_selection_ref'})
                data.update(not_before=start,expires_at=end)
                selection=self._controls._selections.append(conn,draft=PipelineSourceSelectionDraft.model_validate(data),actor=executor,
                    previous_ref=previous.draft.source_selection_ref,idempotency_key=internal_key('selection',binding.pipeline_id))
                draft=PipelineRuntimeControlDraft.model_validate(dict(data,source_selection_ref=selection))
                ref=self._controls.append(conn,draft=draft,actor=executor,previous_ref=previous.ref,
                    idempotency_key=internal_key('control',binding.pipeline_id))
                new_controls.append(decode_control_row(conn.execute('''SELECT * FROM public.pipeline_runtime_control_revision
                    WHERE org_id=%s AND project_id=%s AND control_id=%s AND revision=%s''',
                    (*scope.key,ref.resource_id.removeprefix('pipeline-control-'),ref.revision)).fetchone()))
                renewed.append(PipelineScheduleControlOwner(controls=self._controls).bind(conn,scope=scope,
                    schedule_id=binding.schedule_id,actor=executor,control_ref=ref,previous_ref=binding.ref,
                    expected_pipeline_id=binding.pipeline_id,idempotency_key=internal_key('binding',binding.pipeline_id)))
            validate_saved_group_control_renewal(tuple(predecessors),tuple(new_controls))
            conn.execute('SET CONSTRAINTS '+_CONSTRAINTS+',snapshot_recovery_complete DEFERRED')
            def save(current_group):
                object_types={d.pipeline_id:m.read_spec.object_type for _,d,m in current_group.group.members}
                if object_types!={s.pipeline_id:s.object_type for s in CANONICAL_QYH_SOURCES}:
                    raise ValueError('canonical recovery mappings required')
                if any(row.get('ot')!=object_types[parent['pipelineId']] for parent in facts.parents for row in parent['outputRows']):
                    raise ValueError('saved input object type differs from current exact mapping')
                new_body=deepcopy(body)
                new_body.update(revision=body['revision']+1,priorRef=current['ref'],state='enabled',actor=actor,
                    createdAt=_now(conn).isoformat(),members=[_member(b) for b in renewed])
                new=self._definitions._save(conn,scope,new_body,tuple(renewed),
                    dict(intent='renew_saved_group',recoveryRequest=request),internal_key('definition','all'),[b.schedule_id for b in bindings])
                row=dict(org_id=scope.org_id,project_id=scope.project_id,group_id=UUID(group_id),
                    revision=1 if prior is None else prior['ref']['revision']+1,
                    previous_revision=None if prior is None else prior['ref']['revision'],previous_hash=None if prior is None else prior['ref']['contentHash'],
                    definition_id=UUID(identifier),original_definition_revision=facts.definition['ref']['revision'],
                    original_definition_hash=facts.definition['ref']['contentHash'],current_definition_revision=new['ref']['revision'],
                    current_definition_hash=new['ref']['contentHash'],original_schedule_hash=canonical_sha256(facts.schedule_claim),
                    original_source_hash=facts.source_claim_hash,input_manifest_hash=facts.manifest_hash,
                    actor=actor,executor=executor,policy_ref=body['policyRef'],idempotency_key=key,
                    request=request,request_hash=canonical_sha256(request),created_at=_now(conn))
                row['body']=recovery_body(row);row['content_hash']=canonical_sha256(row['body'])
                conn.execute(sql.SQL('INSERT INTO public.pipeline_snapshot_group_recovery_receipt ({}) VALUES ({})').format(
                    sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row)),
                    tuple(Jsonb(v) if isinstance(v,dict) else v for v in row.values()))
                return decode_recovery_receipt(row)
            result=self._definitions._groups.run_current(conn,scope=scope,refs=tuple(b.control_ref for b in renewed),
                actor=executor,policy_ref=PipelineExactRef.model_validate(body['policyRef']),execute=save)
            conn.execute('SET CONSTRAINTS '+_CONSTRAINTS+',snapshot_recovery_complete IMMEDIATE')
            return result

    @staticmethod
    def _lock_runs(conn,scope,identifier,revision,bindings,schedule_claim):
        runs={m['runId'] for m in schedule_claim['members']}
        for b in bindings:
            conn.execute('SELECT id FROM public.meta_schedule WHERE org_id=%s AND project_id=%s AND id=%s FOR UPDATE',(*scope.key,b.schedule_id))
            occupied=conn.execute('''SELECT definition_id,revision FROM public.pipeline_snapshot_schedule_current_member
                WHERE org_id=%s AND project_id=%s AND schedule_id=%s''',(*scope.key,b.schedule_id)).fetchone()
            if occupied is None or (str(occupied['definition_id']),occupied['revision'])!=(identifier,revision):
                raise ValueError('recovery current membership differs')
            others=conn.execute('''SELECT id FROM public.meta_schedule_run WHERE org_id=%s AND project_id=%s AND schedule_id=%s
                AND NOT(id=ANY(%s)) AND (status='running' OR executor_stopped IS NOT TRUE) LIMIT 1''',(*scope.key,b.schedule_id,sorted(runs))).fetchone()
            if others is not None:raise ValueError('another active or unknown schedule run prevents recovery')
        rows=conn.execute('''SELECT id,status,executor_id,executor_stopped,finished_at FROM public.meta_schedule_run
            WHERE org_id=%s AND project_id=%s AND id=ANY(%s) ORDER BY id COLLATE "C" FOR UPDATE''',(*scope.key,sorted(runs))).fetchall()
        if len(rows)!=12 or {r['id'] for r in rows}!=runs:
            raise ValueError('original recovery runs differ')
        # Original ScheduleClaim leaves executor fields unset until completion.
        # Full saved input plus the original completion lock is required above.
        running=all(r['status']=='running' and r['executor_stopped'] is not True and r['finished_at'] is None for r in rows)
        failed=all(r['status']=='failed' and r['executor_stopped'] is True and r['finished_at'] is not None for r in rows)
        if not (running or failed):raise ValueError('original group has mixed, completed or unknown run states')

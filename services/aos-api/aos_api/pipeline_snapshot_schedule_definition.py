"""Installed schedule definitions; configuration is never permission to read a source."""
from copy import deepcopy
from datetime import datetime
import re
from uuid import UUID

from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.control_policy import validate_idempotency_key
from aos_api.extension_runtime.configuration_authorization import CurrentConfigurationPermission
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_runtime_control_owner import PipelineRuntimeControlOwner
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner, ScheduleControlBinding, decode_binding
from aos_api.pipeline_snapshot_group_policy_owner import PipelineSnapshotGroupPolicyOwner
from aos_api.pipeline_snapshot_schedule_claim import _group_id, _member
from aos_api.pipeline_source_claim_owner import _text
from aos_api.scheduling_engine import parse_cron_field
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES

_KIND='SnapshotScheduleDefinitionRevision'
_PREFIX='snapshot-schedule-'
_CONSTRAINTS=('snapshot_definition_revision_complete,snapshot_definition_history_member_complete,'
    'snapshot_definition_head_complete,snapshot_definition_member_complete,snapshot_definition_current_head_fk')


def _wire(ref):
    return PipelineExactRef.model_validate(ref).model_dump(mode='json',by_alias=True,exclude_none=True)


def _cron(value):
    if type(value) is not str or value != ' '.join(value.split()) or len(value)>120:
        raise ValueError('canonical five-part cron required')
    fields=value.split(' ')
    if len(fields)!=5:
        raise ValueError('canonical five-part cron required')
    for field,bounds in zip(fields,((0,59),(0,23),(1,31),(1,12),(0,6))):
        for part in field.split(','):
            if not re.fullmatch(r'(?:\*|[0-9]{1,2})(?:/[0-9]{1,2})?|[0-9]{1,2}-[0-9]{1,2}',part):
                raise ValueError('unsupported cron field')
            base, slash, step=part.partition('/')
            if slash and not 1<=int(step)<=bounds[1]-bounds[0]+1:
                raise ValueError('cron step out of bounds')
            if base!='*':
                values=[int(v) for v in base.split('-')]
                if any(not bounds[0]<=v<=bounds[1] for v in values) or values!=sorted(values):
                    raise ValueError('cron value out of bounds')
        if not parse_cron_field(field,*bounds):
            raise ValueError('cron field has no valid values')
    return value


def _reference(body):
    return dict(resourceType=_KIND,resourceId=_PREFIX+body['definitionId'],
        revision=body['revision'],contentHash=canonical_sha256(body))


class PipelineSnapshotScheduleDefinitionOwner:
    def __init__(self,*,controls,installation_store):
        if type(controls) is not PipelineRuntimeControlOwner:
            raise TypeError('original runtime control Owner required')
        self._groups=PipelineSnapshotGroupPolicyOwner(controls=controls)
        self._permission=CurrentConfigurationPermission(installation_store=installation_store)

    def read(self,conn,*,scope,definition_id):
        PipelineScheduleControlOwner._identity(conn,scope)
        definition_id=_group_id(definition_id)
        row=conn.execute('''SELECT r.* FROM public.pipeline_snapshot_schedule_definition_head h
            JOIN public.pipeline_snapshot_schedule_definition_revision r
            ON (r.org_id,r.project_id,r.definition_id,r.revision,r.content_hash)=
                (h.org_id,h.project_id,h.definition_id,h.revision,h.content_hash)
            WHERE h.org_id=%s AND h.project_id=%s AND h.definition_id=%s''',(*scope.key,definition_id)).fetchone()
        return self._decode(row,scope,definition_id) if row else None

    @staticmethod
    def _decode(row,scope,definition_id):
        body=row['body']
        fields={'schemaVersion','orgId','projectId','definitionId','revision','priorRef','installationId','generation',
            'state','cron','timezone','policyRef','members','executor','actor','createdAt'}
        if (type(body) is not dict or set(body)!=fields or body['schemaVersion']!='aos.snapshot-schedule-definition/v1'
                or (body['orgId'],body['projectId'],body['definitionId'])!=(*scope.key,definition_id)
                or canonical_sha256(body)!=row['content_hash'] or canonical_sha256(row['request'])!=row['request_hash']
                or body['revision']!=row['revision'] or body['state']!=row['state']
                or body['state'] not in {'disabled','enabled','retired'} or body['timezone']!='Asia/Shanghai'
                or len(body['members'])!=12 or datetime.fromisoformat(body['createdAt']).utcoffset() is None):
            raise ValueError('snapshot definition authority differs')
        _cron(body['cron'])
        return dict(ref=_reference(body),body=deepcopy(body))

    @staticmethod
    def _bindings(bindings,scope):
        if type(bindings) is not tuple or len(bindings)!=12 or any(type(b) is not ScheduleControlBinding for b in bindings):
            raise ValueError('twelve exact schedule bindings required')
        bindings=tuple(sorted(bindings,key=lambda b:b.schedule_id))
        first=bindings[0]
        if (len({b.schedule_id for b in bindings})!=12 or
                any((b.scope,b.installation_id,b.generation,b.actor)!=(scope,first.installation_id,first.generation,first.actor) for b in bindings)):
            raise ValueError('definition binding scope, installation or executor differs')
        return bindings

    @staticmethod
    def _saved_bindings(conn,scope,body):
        values=[]
        for member in body['members']:
            ref=PipelineExactRef.model_validate(member['bindingRef'])
            row=conn.execute('''SELECT * FROM public.pipeline_schedule_control_binding WHERE org_id=%s AND project_id=%s
                AND schedule_id=%s AND binding_id=%s AND revision=%s AND content_hash=%s''',
                (*scope.key,member['scheduleId'],ref.resource_id.removeprefix('schedule-control-'),ref.revision,ref.content_hash)).fetchone()
            if row is None or _member(value:=decode_binding(row))!=member:
                raise ValueError('saved definition member differs')
            values.append(value)
        return tuple(values)

    def configure(self,conn,*,scope,definition_id,actor,cron,policy_ref,bindings,expected_ref,idempotency_key):
        bindings=self._bindings(bindings,scope)
        settings=dict(cron=_cron(cron),policyRef=_wire(policy_ref),members=[_member(b) for b in bindings])
        return self._operate(conn,scope=scope,definition_id=definition_id,actor=actor,intent='configure',
            settings=settings,bindings=bindings,expected_ref=expected_ref,idempotency_key=idempotency_key)

    def transition(self,conn,*,scope,definition_id,actor,intent,expected_ref,idempotency_key):
        if intent not in {'enable','disable','retire'}:
            raise ValueError('unsupported snapshot definition transition')
        return self._operate(conn,scope=scope,definition_id=definition_id,actor=actor,intent=intent,
            settings=None,bindings=None,expected_ref=expected_ref,idempotency_key=idempotency_key)

    def _operate(self,conn,*,scope,definition_id,actor,intent,settings,bindings,expected_ref,idempotency_key):
        PipelineScheduleControlOwner._identity(conn,scope)
        definition_id,actor=_group_id(definition_id),_text(actor,240)
        key=validate_idempotency_key(idempotency_key)
        expected=None if expected_ref is None else _wire(expected_ref)
        if expected is not None and (expected['resourceType'],expected['resourceId'])!=(_KIND,_PREFIX+definition_id):
            raise ValueError('exact definition predecessor required')
        request=dict(orgId=scope.org_id,projectId=scope.project_id,definitionId=definition_id,actor=actor,
            intent=intent,expectedRef=expected,settings=settings)
        with conn.transaction():
            conn.execute('SET CONSTRAINTS '+_CONSTRAINTS+' DEFERRED')
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                ('snapshot-definition:'+canonical_sha256([*scope.key,definition_id]),))
            # Installation permission always precedes the definition/control/schedule locks.
            target=conn.execute('''SELECT installation_id,generation FROM public.pipeline_snapshot_schedule_definition_head
                WHERE org_id=%s AND project_id=%s AND definition_id=%s''',(*scope.key,definition_id)).fetchone()
            if target is None:
                if intent!='configure' or bindings is None:
                    raise LookupError('snapshot definition unavailable')
                installation,generation=bindings[0].installation_id,bindings[0].generation
            else:
                installation,generation=str(target['installation_id']),str(target['generation'])
            if self._permission(conn,org_id=scope.org_id,project_id=scope.project_id,
                    installation_id=installation,generation=generation,actor=actor) is not True:
                raise PermissionError('current installation control permission required')
            conn.execute('''SELECT revision FROM public.pipeline_snapshot_schedule_definition_head
                WHERE org_id=%s AND project_id=%s AND definition_id=%s FOR UPDATE''',(*scope.key,definition_id))
            old=self.read(conn,scope=scope,definition_id=definition_id)
            replay=conn.execute('''SELECT * FROM public.pipeline_snapshot_schedule_definition_revision
                WHERE org_id=%s AND project_id=%s AND definition_id=%s AND idempotency_key=%s''',(*scope.key,definition_id,key)).fetchone()
            if replay is not None:
                if replay['request_hash']!=canonical_sha256(request) or replay['request']!=request:
                    raise ValueError('definition idempotency request differs')
                result=self._decode(replay,scope,definition_id)
                conn.execute('SET CONSTRAINTS '+_CONSTRAINTS+' IMMEDIATE')
                return result
            if (old['ref'] if old else None)!=expected:
                raise ValueError('definition predecessor is not current')
            prior=old['body'] if old else None
            if prior and (prior['state']=='retired' or (intent in {'configure','retire'} and prior['state']!='disabled')):
                raise ValueError('definition state does not allow this transition')
            if intent!='configure':
                bindings=self._saved_bindings(conn,scope,prior)
                settings={name:deepcopy(prior[name]) for name in ('cron','policyRef','members')}
            if (bindings[0].installation_id,bindings[0].generation)!=(installation,generation):
                raise ValueError('configuration cannot transfer installation authority')
            def save(_current=None):
                all_ids=sorted({b.schedule_id for b in bindings}|{m['scheduleId'] for m in prior['members']} if prior else {b.schedule_id for b in bindings})
                for schedule_id in all_ids:
                    row=conn.execute('''SELECT pipeline_id,ingest FROM public.meta_schedule
                        WHERE org_id=%s AND project_id=%s AND id=%s FOR UPDATE''',(*scope.key,schedule_id)).fetchone()
                    if row is None:
                        raise ValueError('definition member schedule missing')
                    occupied=conn.execute('''SELECT definition_id FROM public.pipeline_snapshot_schedule_current_member
                        WHERE org_id=%s AND project_id=%s AND schedule_id=%s''',(*scope.key,schedule_id)).fetchone()
                    if occupied and str(occupied['definition_id'])!=definition_id:
                        raise ValueError('schedule already belongs to another definition')
                    if intent in {'configure','retire'} and conn.execute('''SELECT 1 FROM public.meta_schedule_run
                        WHERE org_id=%s AND project_id=%s AND schedule_id=%s AND (status='running' OR executor_stopped IS NOT TRUE) LIMIT 1''',
                        (*scope.key,schedule_id)).fetchone():
                        raise ValueError('definition has active or unknown executions')
                if intent in {'configure','enable'}:
                    for b in bindings:
                        if PipelineScheduleControlOwner.read_latest(conn,scope=scope,schedule_id=b.schedule_id)!=b:
                            raise ValueError('definition schedule binding is not current')
                        row=conn.execute('SELECT pipeline_id,ingest FROM public.meta_schedule WHERE org_id=%s AND project_id=%s AND id=%s',(*scope.key,b.schedule_id)).fetchone()
                        if row['pipeline_id']!=b.pipeline_id or row['ingest'].get('kind')!='pipeline-live-v1' or row['ingest'].get('pipelineId')!=b.pipeline_id:
                            raise ValueError('definition member pipeline differs')
                revision=1 if old is None else prior['revision']+1
                state={'configure':'disabled','enable':'enabled','disable':'disabled','retire':'retired'}[intent]
                body=dict(schemaVersion='aos.snapshot-schedule-definition/v1',orgId=scope.org_id,projectId=scope.project_id,
                    definitionId=definition_id,revision=revision,priorRef=expected,installationId=installation,generation=generation,
                    state=state,timezone='Asia/Shanghai',executor=bindings[0].actor,actor=actor,
                    createdAt=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'].isoformat(),**settings)
                return self._save(conn,scope,body,bindings,request,key,all_ids)
            if intent in {'configure','enable'}:
                def qualified(current):
                    actual={d.pipeline_id:m.read_spec.object_type for _,d,m in current.group.members}
                    if actual!={s.pipeline_id:s.object_type for s in CANONICAL_QYH_SOURCES}:
                        raise ValueError('complete canonical source group required')
                    return save(current)
                result=self._groups.run_current(conn,scope=scope,refs=tuple(b.control_ref for b in bindings),
                    actor=bindings[0].actor,policy_ref=PipelineExactRef.model_validate(settings['policyRef']),execute=qualified)
            else:
                result=save()
            conn.execute('SET CONSTRAINTS '+_CONSTRAINTS+' IMMEDIATE')
            return result

    @staticmethod
    def _save(conn,scope,body,bindings,request,key,all_ids):
        definition_id,revision=body['definitionId'],body['revision']
        ref=_reference(body)
        previous=body['priorRef']
        conn.execute('''INSERT INTO public.pipeline_snapshot_schedule_definition_revision
            (org_id,project_id,definition_id,revision,previous_revision,previous_hash,installation_id,generation,
             state,actor,idempotency_key,request_hash,request,content_hash,body)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (*scope.key,definition_id,revision,previous['revision'] if previous else None,previous['contentHash'] if previous else None,
             body['installationId'],body['generation'],body['state'],body['actor'],key,canonical_sha256(request),Jsonb(request),ref['contentHash'],Jsonb(body)))
        for ordinal,b in enumerate(bindings,1):
            conn.execute('''INSERT INTO public.pipeline_snapshot_schedule_definition_member
                (org_id,project_id,definition_id,revision,ordinal,schedule_id,binding_id,binding_revision,binding_hash)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',(*scope.key,definition_id,revision,ordinal,b.schedule_id,
                b.ref.resource_id.removeprefix('schedule-control-'),b.ref.revision,b.ref.content_hash))
        if previous is None:
            conn.execute('''INSERT INTO public.pipeline_snapshot_schedule_definition_head
                (org_id,project_id,definition_id,revision,content_hash,state,installation_id,generation)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)''',(*scope.key,definition_id,revision,ref['contentHash'],body['state'],body['installationId'],body['generation']))
        elif conn.execute('''UPDATE public.pipeline_snapshot_schedule_definition_head SET revision=%s,content_hash=%s,state=%s
            WHERE org_id=%s AND project_id=%s AND definition_id=%s AND revision=%s AND content_hash=%s''',
            (revision,ref['contentHash'],body['state'],*scope.key,definition_id,previous['revision'],previous['contentHash'])).rowcount!=1:
            raise ValueError('definition CAS failed')
        conn.execute('DELETE FROM public.pipeline_snapshot_schedule_current_member WHERE org_id=%s AND project_id=%s AND definition_id=%s',(*scope.key,definition_id))
        if body['state']!='retired':
            for b in bindings:
                conn.execute('''INSERT INTO public.pipeline_snapshot_schedule_current_member
                    (org_id,project_id,schedule_id,definition_id,revision) VALUES(%s,%s,%s,%s,%s)''',(*scope.key,b.schedule_id,definition_id,revision))
        conn.execute('UPDATE public.meta_schedule SET enabled=%s,updated_at=clock_timestamp() WHERE org_id=%s AND project_id=%s AND id=ANY(%s)',
            (body['state']=='enabled',*scope.key,all_ids))
        return dict(ref=ref,body=deepcopy(body))

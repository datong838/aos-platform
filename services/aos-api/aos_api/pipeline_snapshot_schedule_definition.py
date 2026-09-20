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
        if controls is not None and type(controls) is not PipelineRuntimeControlOwner:
            raise TypeError('original runtime control Owner required')
        self._groups=PipelineSnapshotGroupPolicyOwner(controls=controls) if controls is not None else None
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

    def transfer_saved_recovery(self,conn,*,scope,definition_id,group_id,actor,bindings,
                                expected_ref,expected_recovery_ref,idempotency_key):
        """Transfer one disabled definition to its exact live replacement.

        This is deliberately narrower than configure: it preserves the schedule
        and policy, requires one already-saved unfinished group, and never grants
        execution or creates another group.
        """
        bindings=self._bindings(bindings,scope)
        transfer=dict(groupId=_group_id(group_id),expectedRecoveryRef=_wire(expected_recovery_ref))
        return self._operate(conn,scope=scope,definition_id=definition_id,actor=actor,
            intent='transfer_saved_recovery',settings=None,bindings=bindings,
            expected_ref=expected_ref,idempotency_key=idempotency_key,transfer=transfer)

    def _current_transfer_policy(self,conn,*,scope,bindings,prior):
        """Resolve the predecessor policy path from the target release under its group guard."""
        previous=PipelineExactRef.model_validate(prior['policyRef'])
        def resolve(group):
            return self._groups._resolve_exported_ref(conn,scope,group,
                resource_type='SnapshotRelationshipPolicy',path=previous.resource_id)
        return self._groups._groups.run_current(conn,scope=scope,
            refs=tuple(b.control_ref for b in bindings),actor=bindings[0].actor,execute=resolve)

    @staticmethod
    def _released_retirement_allowed(conn, *, scope, installation_id, actor):
        """Allow an admin to retire disabled configuration left by an uninstalled package."""
        released=conn.execute('''SELECT r.state FROM public.bundle_installation i
            JOIN public.bundle_installation_revision r
              ON (r.org_id,r.project_id,r.installation_pk,r.revision)=
                 (i.org_id,i.project_id,i.installation_pk,i.current_revision)
            WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s''',
            (*scope.key,installation_id)).fetchone()
        membership=conn.execute('''SELECT role FROM public.meta_membership
            WHERE org_id=%s AND project_id=%s AND subject=%s''',(*scope.key,actor)).fetchone()
        return released is not None and released['state']=='uninstalled' and membership is not None and membership['role']=='admin'

    @staticmethod
    def _disabled_head(conn, *, scope, definition_id):
        row=conn.execute('''SELECT state FROM public.pipeline_snapshot_schedule_definition_head
            WHERE org_id=%s AND project_id=%s AND definition_id=%s''',(*scope.key,definition_id)).fetchone()
        return row is not None and row['state']=='disabled'

    def transition(self,conn,*,scope,definition_id,actor,intent,expected_ref,idempotency_key):
        if intent not in {'enable','disable','retire'}:
            raise ValueError('unsupported snapshot definition transition')
        return self._operate(conn,scope=scope,definition_id=definition_id,actor=actor,intent=intent,
            settings=None,bindings=None,expected_ref=expected_ref,idempotency_key=idempotency_key)

    def _operate(self,conn,*,scope,definition_id,actor,intent,settings,bindings,expected_ref,idempotency_key,
                 transfer=None):
        if intent in {'configure','enable','transfer_saved_recovery'} and self._groups is None:
            raise PermissionError('source controls unavailable in stop-only mode')
        PipelineScheduleControlOwner._identity(conn,scope)
        definition_id,actor=_group_id(definition_id),_text(actor,240)
        key=validate_idempotency_key(idempotency_key)
        expected=None if expected_ref is None else _wire(expected_ref)
        if expected is not None and (expected['resourceType'],expected['resourceId'])!=(_KIND,_PREFIX+definition_id):
            raise ValueError('exact definition predecessor required')
        request=dict(orgId=scope.org_id,projectId=scope.project_id,definitionId=definition_id,actor=actor,
            intent=intent,expectedRef=expected,settings=settings)
        if transfer is not None:
            request['transfer']=transfer
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
            elif intent=='transfer_saved_recovery':
                installation,generation=bindings[0].installation_id,bindings[0].generation
            else:
                installation,generation=str(target['installation_id']),str(target['generation'])
            released_retirement=(intent=='retire' and self._disabled_head(conn,scope=scope,definition_id=definition_id)
                and self._released_retirement_allowed(conn,scope=scope,installation_id=installation,actor=actor))
            if not released_retirement and self._permission(conn,org_id=scope.org_id,project_id=scope.project_id,
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
            if prior and (prior['state']=='retired' or (intent in {'configure','retire','transfer_saved_recovery'} and prior['state']!='disabled')):
                raise ValueError('definition state does not allow this transition')
            if intent!='configure':
                if intent!='transfer_saved_recovery':
                    bindings=self._saved_bindings(conn,scope,prior)
                settings={name:deepcopy(prior[name]) for name in ('cron','policyRef','members')}
                if intent=='transfer_saved_recovery':
                    settings['members']=[_member(b) for b in bindings]
                    self._require_saved_recovery_transfer(conn,scope=scope,prior=prior,bindings=bindings,
                        group_id=transfer['groupId'],expected_recovery_ref=transfer['expectedRecoveryRef'])
                    settings['policyRef']=_wire(self._current_transfer_policy(
                        conn,scope=scope,bindings=bindings,prior=prior))
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
                if intent in {'configure','enable','transfer_saved_recovery'}:
                    for b in bindings:
                        if PipelineScheduleControlOwner.read_latest(conn,scope=scope,schedule_id=b.schedule_id)!=b:
                            raise ValueError('definition schedule binding is not current')
                        row=conn.execute('SELECT pipeline_id,ingest FROM public.meta_schedule WHERE org_id=%s AND project_id=%s AND id=%s',(*scope.key,b.schedule_id)).fetchone()
                        if row['pipeline_id']!=b.pipeline_id or row['ingest'].get('kind')!='pipeline-live-v1' or row['ingest'].get('pipelineId')!=b.pipeline_id:
                            raise ValueError('definition member pipeline differs')
                revision=1 if old is None else prior['revision']+1
                state={'configure':'disabled','enable':'enabled','disable':'disabled','retire':'retired',
                    'transfer_saved_recovery':'disabled'}[intent]
                body=dict(schemaVersion='aos.snapshot-schedule-definition/v1',orgId=scope.org_id,projectId=scope.project_id,
                    definitionId=definition_id,revision=revision,priorRef=expected,installationId=installation,generation=generation,
                    state=state,timezone='Asia/Shanghai',executor=bindings[0].actor,actor=actor,
                    createdAt=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'].isoformat(),**settings)
                return self._save(conn,scope,body,bindings,request,key,all_ids)
            if intent in {'configure','enable','transfer_saved_recovery'}:
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

    def _require_saved_recovery_transfer(self,conn,*,scope,prior,bindings,group_id,expected_recovery_ref):
        """Fail closed unless the old authority is drained and target is its exact live child."""
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
            ('snapshot-recovery:'+canonical_sha256([*scope.key,group_id]),))
        if {m['scheduleId'] for m in prior['members']}!={b.schedule_id for b in bindings}:
            raise ValueError('saved recovery schedule set differs')
        recovery=conn.execute('''SELECT revision,content_hash,definition_id,current_definition_revision,
            current_definition_hash,input_manifest_hash FROM public.pipeline_snapshot_group_recovery_receipt
            WHERE org_id=%s AND project_id=%s AND group_id=%s ORDER BY revision DESC LIMIT 1''',
            (*scope.key,group_id)).fetchone()
        expected=expected_recovery_ref
        if (recovery is None or expected!={'resourceType':'SnapshotGroupRecoveryRevision',
                'resourceId':'snapshot-recovery-'+group_id,'revision':recovery['revision'],
                'contentHash':recovery['content_hash']}
                or str(recovery['definition_id'])!=prior['definitionId']
                or not self._saved_recovery_anchor(conn,scope=scope,prior=prior,
                    group_id=group_id,recovery_ref=expected,
                    recovery_revision=recovery['current_definition_revision'],
                    recovery_hash=recovery['current_definition_hash'])):
            raise ValueError('exact saved recovery predecessor required')
        saved=conn.execute('''SELECT c.request,i.manifest_hash,
              (SELECT count(*) FROM public.pipeline_snapshot_schedule_member m
               WHERE m.org_id=c.org_id AND m.project_id=c.project_id AND m.group_id=c.group_id) AS members,
              (SELECT count(*) FROM public.meta_schedule_run r JOIN public.pipeline_snapshot_schedule_member m
               ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
               WHERE m.org_id=c.org_id AND m.project_id=c.project_id AND m.group_id=c.group_id
                 AND r.status='running' AND r.executor_stopped IS FALSE) AS resumable
            FROM public.pipeline_snapshot_schedule_claim c JOIN public.pipeline_snapshot_group_input i
              ON (i.org_id,i.project_id,i.group_id)=(c.org_id,c.project_id,c.group_id)
            WHERE c.org_id=%s AND c.project_id=%s AND c.group_id=%s''',
            (*scope.key,group_id)).fetchone()
        definition_resource='snapshot-schedule-'+prior['definitionId']
        other=conn.execute('''SELECT count(*) AS n FROM public.pipeline_snapshot_schedule_claim c
            JOIN public.pipeline_snapshot_group_input i ON (i.org_id,i.project_id,i.group_id)=(c.org_id,c.project_id,c.group_id)
            WHERE c.org_id=%s AND c.project_id=%s
              AND c.request->'definitionRef'->>'resourceId'=%s''',(*scope.key,definition_resource)).fetchone()
        if (saved is None or saved['manifest_hash']!=recovery['input_manifest_hash']
                or saved['request'].get('definitionRef',{}).get('resourceId')!=definition_resource
                or (saved['members'],saved['resumable'],other['n'])!=(12,12,1)):
            raise ValueError('one exact resumable saved group required')
        old_installation,old_generation=prior['installationId'],prior['generation']
        new_installation,new_generation=bindings[0].installation_id,bindings[0].generation
        lineage=self._exact_active_replacement_lineage(conn,scope=scope,
            old_installation=old_installation,new_installation=new_installation)
        retired_installations=lineage[:-1]
        runtimes=conn.execute('''SELECT installation_id,generation,enabled,operation_fence,desired_state,observed_state
            FROM public.extension_runtime_binding WHERE org_id=%s AND project_id=%s
              AND installation_id=ANY(%s) FOR SHARE''',(*scope.key,lineage)).fetchall()
        by_id={str(row['installation_id']):row for row in runtimes}
        before,after=by_id.get(old_installation),by_id.get(new_installation)
        if (before is None or str(before['generation'])!=old_generation or before['enabled'] is not False
                or before['operation_fence'] is not True or before['desired_state']!='disabled'
                or before['observed_state']!='unknown' or after is None or str(after['generation'])!=new_generation
                or after['enabled'] is not True or after['operation_fence'] is not False
                or after['desired_state']!='enabled' or after['observed_state']!='ready'):
            raise ValueError('exact drained predecessor and ready successor required')
        if (len(by_id)!=len(lineage) or any(
                by_id[installation]['enabled'] is not False
                or by_id[installation]['operation_fence'] is not True
                or by_id[installation]['desired_state']!='disabled'
                or by_id[installation]['observed_state']!='unknown'
                for installation in retired_installations)):
            raise ValueError('exact drained replacement chain required')
        for installation in retired_installations:
            generation=str(by_id[installation]['generation'])
            resources=conn.execute('''SELECT count(*) AS total,
                  count(*) FILTER(WHERE l.cleanup_state='released' AND l.observed_release IS TRUE) AS released
                FROM public.extension_runtime_resource_lease l JOIN public.extension_runtime_operation o
                  ON (o.org_id,o.project_id,o.operation_id)=(l.org_id,l.project_id,l.operation_id)
                WHERE o.org_id=%s AND o.project_id=%s AND o.installation_id=%s AND l.generation=%s''',
                (*scope.key,installation,generation)).fetchone()
            detached=conn.execute('''SELECT count(*) AS n FROM public.extension_dispatch_lifecycle_operation d
                JOIN public.extension_runtime_operation o ON (o.org_id,o.project_id,o.operation_id)=
                  (d.org_id,d.project_id,d.runtime_operation_id)
                WHERE d.org_id=%s AND d.project_id=%s AND o.installation_id=%s
                  AND o.kind='disable' AND o.status='succeeded' AND d.status='detached'
                  AND (SELECT count(*) FROM public.extension_dispatch_lifecycle_receipt x
                       WHERE x.org_id=d.org_id AND x.project_id=d.project_id
                         AND x.runtime_operation_id=d.runtime_operation_id AND x.phase IN ('fence','detach'))=2''',
                (*scope.key,installation)).fetchone()
            if (resources['total'],resources['released'],detached['n'])!=(3,3,1):
                raise ValueError('replacement cleanup or dispatch evidence incomplete')
        routes=conn.execute('''SELECT count(*) AS n FROM public.extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND handler_kind='extension' AND installation_id=%s
              AND generation=%s AND operation_fence IS FALSE''',(*scope.key,new_installation,new_generation)).fetchone()
        if routes['n']!=9:
            raise ValueError('replacement cleanup or dispatch evidence incomplete')

    @staticmethod
    def _exact_active_replacement_lineage(conn,*,scope,old_installation,new_installation):
        """Return an exact finite direct-successor chain from old to new."""
        current=new_installation
        expected=None
        reverse=[]
        seen=set()
        for _ in range(32):
            if current in seen:
                raise ValueError('exact active replacement lineage required')
            seen.add(current)
            row=conn.execute('''SELECT i.current_revision,r.state,r.lock_hash,r.overlay_revision,l.lock_payload
                FROM public.bundle_installation i JOIN public.bundle_installation_revision r
                  ON (r.org_id,r.project_id,r.installation_pk,r.revision)=
                     (i.org_id,i.project_id,i.installation_pk,i.current_revision)
                JOIN public.bundle_composition_lock l ON (l.org_id,l.project_id,l.composition_pk,l.revision)=
                  (r.org_id,r.project_id,r.composition_pk,r.lock_revision)
                WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s''',
                (*scope.key,current)).fetchone()
            actual=None if row is None else {'installationId':current,'revision':row['current_revision'],
                'lockHash':row['lock_hash'],'overlayRevision':row['overlay_revision']}
            if row is None or row['state']!='active' or (expected is not None and actual!=expected):
                raise ValueError('exact active replacement lineage required')
            reverse.append(current)
            if current==old_installation:
                return list(reversed(reverse))
            predecessor=row['lock_payload'].get('currentInstallationRef')
            if (type(predecessor) is not dict or type(predecessor.get('installationId')) is not str
                    or predecessor['installationId']==current):
                raise ValueError('exact active replacement lineage required')
            expected=predecessor
            current=predecessor['installationId']
        raise ValueError('exact active replacement lineage required')

    @classmethod
    def _saved_recovery_anchor(cls,conn,*,scope,prior,group_id,recovery_ref,
                               recovery_revision,recovery_hash):
        """Follow only exact saved-recovery transfers back to the receipt anchor."""
        from aos_api.pipeline_snapshot_group_recovery_contracts import exact_saved_recovery_transfer_request

        current=prior
        visited=set()
        while True:
            previous=current.get('priorRef')
            if (type(previous) is dict
                    and (previous.get('revision'),previous.get('contentHash'))
                       ==(recovery_revision,recovery_hash)):
                return True
            revision=current.get('revision')
            if (type(revision) is not int or revision in visited or revision<=recovery_revision+1
                    or type(previous) is not dict or previous.get('revision')!=revision-1):
                return False
            visited.add(revision)
            row=conn.execute('''SELECT * FROM public.pipeline_snapshot_schedule_definition_revision
                WHERE org_id=%s AND project_id=%s AND definition_id=%s AND revision=%s''',
                (*scope.key,current['definitionId'],revision)).fetchone()
            if row is None:
                return False
            decoded=cls._decode(row,scope,current['definitionId'])
            if decoded['body']!=current or not exact_saved_recovery_transfer_request(
                    row['request'],scope=scope,current=current,group_id=group_id,
                    recovery_ref=recovery_ref,actor=current['actor']):
                return False
            predecessor=conn.execute('''SELECT * FROM public.pipeline_snapshot_schedule_definition_revision
                WHERE org_id=%s AND project_id=%s AND definition_id=%s
                  AND revision=%s AND content_hash=%s''',
                (*scope.key,current['definitionId'],previous['revision'],previous['contentHash'])).fetchone()
            if predecessor is None:
                return False
            current=cls._decode(predecessor,scope,current['definitionId'])['body']

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
        elif conn.execute('''UPDATE public.pipeline_snapshot_schedule_definition_head SET revision=%s,content_hash=%s,state=%s,
                installation_id=%s,generation=%s
            WHERE org_id=%s AND project_id=%s AND definition_id=%s AND revision=%s AND content_hash=%s''',
            (revision,ref['contentHash'],body['state'],body['installationId'],body['generation'],
             *scope.key,definition_id,previous['revision'],previous['contentHash'])).rowcount!=1:
            raise ValueError('definition CAS failed')
        conn.execute('DELETE FROM public.pipeline_snapshot_schedule_current_member WHERE org_id=%s AND project_id=%s AND definition_id=%s',(*scope.key,definition_id))
        if body['state']!='retired':
            for b in bindings:
                conn.execute('''INSERT INTO public.pipeline_snapshot_schedule_current_member
                    (org_id,project_id,schedule_id,definition_id,revision) VALUES(%s,%s,%s,%s,%s)''',(*scope.key,b.schedule_id,definition_id,revision))
        conn.execute('UPDATE public.meta_schedule SET enabled=%s,updated_at=clock_timestamp() WHERE org_id=%s AND project_id=%s AND id=ANY(%s)',
            (body['state']=='enabled',*scope.key,all_ids))
        return dict(ref=ref,body=deepcopy(body))

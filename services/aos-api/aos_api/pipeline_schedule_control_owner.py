"""Immutable schedule approval associations; reading one never grants execution."""
from dataclasses import dataclass
from uuid import UUID,uuid4

from psycopg import sql
from psycopg.rows import dict_row
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.control_policy import validate_idempotency_key
from aos_api.extension_runtime.lifecycle_store import _require_transaction,_values,RuntimeConflict,RuntimeRevisionConflict
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_runtime_control_owner import PipelineRuntimeControlOwner,_ref_identity
from aos_api.pipeline_source_claim_owner import _text
from aos_api.tenant_scope import TenantScope

_KIND='PipelineScheduleControlBinding'
_PREFIX='schedule-control-'
_FIELDS=('org_id','project_id','schedule_id','binding_id','revision','installation_id','generation',
    'pipeline_id','control_id','control_revision','control_hash','actor','previous_revision','previous_hash',
    'request_hash','idempotency_key')


def _request_hash(scope,schedule_id,control_ref,actor,previous_ref):
    return canonical_sha256(dict(orgId=scope.org_id,projectId=scope.project_id,scheduleId=schedule_id,
        controlRef=control_ref.model_dump(mode='json',by_alias=True),actor=actor,
        previousRef=previous_ref.model_dump(mode='json',by_alias=True) if previous_ref else None))


def _content(row):
    body={name:row[name] for name in _FIELDS}
    for name in ('binding_id','installation_id','generation','control_id'):
        body[name]=str(UUID(str(body[name])))
    return dict(schemaVersion='aos.pipeline-schedule-control-binding/v1',**body)


@dataclass(frozen=True)
class ScheduleControlBinding:
    ref: PipelineExactRef
    scope: TenantScope
    schedule_id: str
    pipeline_id: str
    installation_id: str
    generation: str
    control_ref: PipelineExactRef
    actor: str


def decode_binding(row):
    scope=TenantScope(row['org_id'],row['project_id'])
    schedule_id,actor=_text(row['schedule_id'],200),_text(row['actor'],240)
    identity=str(UUID(str(row['binding_id'])))
    revision=row['revision']
    if type(revision) is not int or revision<1:
        raise ValueError('binding revision invalid')
    previous=None if revision==1 else PipelineExactRef(resource_type=_KIND,resource_id=_PREFIX+identity,
        revision=revision-1,content_hash=row['previous_hash'])
    control=PipelineExactRef(resource_type='PipelineRuntimeControlRevision',resource_id='pipeline-control-'+str(row['control_id']),
        revision=row['control_revision'],content_hash=row['control_hash'])
    _ref_identity(control,'PipelineRuntimeControlRevision','pipeline-control-')
    if (row['previous_revision']!=(revision-1 if revision>1 else None)
            or (revision==1 and row['previous_hash'] is not None)
            or row['request_hash']!=_request_hash(scope,schedule_id,control,actor,previous)
            or row['content_hash']!=canonical_sha256(_content(row))):
        raise ValueError('schedule control history differs')
    return ScheduleControlBinding(PipelineExactRef(resource_type=_KIND,resource_id=_PREFIX+identity,
        revision=revision,content_hash=row['content_hash']),scope,schedule_id,_text(row['pipeline_id'],200),
        str(row['installation_id']),str(row['generation']),control,actor)


class PipelineScheduleControlOwner:
    def __init__(self,*,controls):
        if type(controls) is not PipelineRuntimeControlOwner:
            raise TypeError('exact current control Owner required')
        self._controls=controls

    def _identity(self,conn,scope):
        _require_transaction(conn)
        if type(scope) is not TenantScope:raise TypeError('exact tenant required')
        row=conn.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,current_setting('aos.project_id',true) AS project_id").fetchone()
        if _values(row,('role','org_id','project_id'))!=('aos_runtime',*scope.key):
            raise PermissionError('current runtime identity and tenant required')

    def read_latest(self,conn,*,scope,schedule_id):
        self._identity(conn,scope)
        schedule_id=_text(schedule_id,200)
        with conn.cursor(row_factory=dict_row) as cursor:
            row=cursor.execute('''SELECT * FROM pipeline_schedule_control_binding
                WHERE org_id=%s AND project_id=%s AND schedule_id=%s ORDER BY revision DESC LIMIT 1''',
                (*scope.key,schedule_id)).fetchone()
        return decode_binding(row) if row else None

    def bind(self,conn,*,scope,schedule_id,control_ref,actor,idempotency_key,previous_ref=None,expected_pipeline_id=None):
        self._identity(conn,scope)
        schedule_id,actor=_text(schedule_id,200),_text(actor,240)
        if expected_pipeline_id is not None:expected_pipeline_id=_text(expected_pipeline_id,200)
        control_ref=PipelineExactRef.model_validate(control_ref)
        control_id=_ref_identity(control_ref,'PipelineRuntimeControlRevision','pipeline-control-')
        key=validate_idempotency_key(idempotency_key)
        identity,revision=str(uuid4()),1
        if previous_ref is not None:
            previous_ref=PipelineExactRef.model_validate(previous_ref)
            identity=_ref_identity(previous_ref,_KIND,_PREFIX)
            revision=previous_ref.revision+1
        request_hash=_request_hash(scope,schedule_id,control_ref,actor,previous_ref)
        def persist(draft,spec):
            if expected_pipeline_id is not None and draft.pipeline_id!=expected_pipeline_id:
                raise ValueError('request pipeline differs')
            with conn.cursor(row_factory=dict_row) as cursor:
                schedule=cursor.execute('''SELECT pipeline_id,ingest FROM meta_schedule
                    WHERE org_id=%s AND project_id=%s AND id=%s FOR UPDATE''',(*scope.key,schedule_id)).fetchone()
                if schedule is None:raise LookupError('schedule unavailable')
                ingest=schedule['ingest'] or {}
                if (schedule['pipeline_id']!=draft.pipeline_id or type(ingest) is not dict
                        or ingest.get('kind')!='pipeline-live-v1' or ingest.get('pipelineId')!=draft.pipeline_id):
                    raise RuntimeConflict('schedule live pipeline differs')
                existing=cursor.execute('''SELECT * FROM pipeline_schedule_control_binding
                    WHERE org_id=%s AND project_id=%s AND schedule_id=%s AND idempotency_key=%s''',
                    (*scope.key,schedule_id,key)).fetchone()
                if existing is not None:
                    saved=decode_binding(existing)
                    if existing['request_hash']!=request_hash:raise RuntimeConflict('schedule binding idempotency differs')
                    return saved
                latest=self.read_latest(conn,scope=scope,schedule_id=schedule_id)
                if (latest.ref if latest else None)!=previous_ref:
                    raise RuntimeRevisionConflict('schedule binding predecessor is not current')
                row=dict(org_id=scope.org_id,project_id=scope.project_id,schedule_id=schedule_id,
                    binding_id=identity,revision=revision,installation_id=draft.installation_ref.installation_id,generation=draft.generation,
                    pipeline_id=draft.pipeline_id,control_id=control_id,control_revision=control_ref.revision,
                    control_hash=control_ref.content_hash,actor=actor,previous_revision=revision-1 if revision>1 else None,
                    previous_hash=previous_ref.content_hash if previous_ref else None,request_hash=request_hash,idempotency_key=key)
                row['content_hash']=canonical_sha256(_content(row))
                saved=cursor.execute(sql.SQL('INSERT INTO pipeline_schedule_control_binding ({}) VALUES ({}) RETURNING *').format(
                    sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row)),tuple(row.values())).fetchone()
                return decode_binding(saved)
        return self._controls.run_current(conn,scope=scope,ref=control_ref,actor=actor,execute=persist)

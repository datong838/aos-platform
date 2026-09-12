"""Persistent controls whose every use consumes the current source selection."""
from dataclasses import dataclass
import json
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.control_policy import validate_idempotency_key
from aos_api.extension_runtime.lifecycle_store import _require_transaction, _values, RuntimeConflict, RuntimeRevisionConflict
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef, PipelineRuntimeControlDraft, PipelineSourceSelectionDraft
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.tenant_scope import TenantScope


def verify_control_selection(control, selection):
    control=PipelineRuntimeControlDraft.model_validate(control)
    selection=PipelineSourceSelectionDraft.model_validate(selection)
    if (control.model_dump(mode='json',by_alias=True,exclude={'schema_version','source_selection_ref'})
            != selection.model_dump(mode='json',by_alias=True,exclude={'schema_version'})):
        raise ValueError('control context differs from approved selection')


def _identity(control_id, revision, previous_hash, actor):
    if type(control_id) is not str or str(UUID(control_id))!=control_id:
        raise ValueError('canonical control identity required')
    if type(revision) is not int or not 1<=revision<2**63:
        raise ValueError('positive control revision required')
    if type(actor) is not str or not 1<=len(actor)<=240 or actor!=actor.strip() or not actor.isprintable():
        raise ValueError('canonical actor required')
    if revision==1:
        if previous_hash is not None:raise ValueError('first control cannot have predecessor')
        return None
    return PipelineExactRef(resource_type='PipelineRuntimeControlRevision',resource_id='pipeline-control-'+control_id,
        revision=revision-1,content_hash=previous_hash)


def _ref_identity(ref,kind,prefix):
    ref=PipelineExactRef.model_validate(ref)
    identity=ref.resource_id.removeprefix(prefix)
    if ref.resource_type!=kind or type(ref.revision) is not int or ref.resource_id!=prefix+str(UUID(identity)):
        raise ValueError('exact control authority reference required')
    return identity


def control_request_hash(*,draft,control_id,revision,previous_hash,actor):
    draft=PipelineRuntimeControlDraft.model_validate(draft)
    previous=_identity(control_id,revision,previous_hash,actor)
    return canonical_sha256(dict(actor=actor,draft=draft.model_dump(mode='json',by_alias=True),
        previousRef=previous.model_dump(mode='json',by_alias=True) if previous else None))


def build_control_payload(*,draft,control_id,revision,previous_hash,actor):
    draft=PipelineRuntimeControlDraft.model_validate(draft)
    _identity(control_id,revision,previous_hash,actor)
    selection_id=_ref_identity(draft.source_selection_ref,'SourceSelectionRevision','source-selection-')
    return dict(schemaVersion='aos.pipeline-runtime-control-revision/v1',orgId=draft.org_id,projectId=draft.project_id,
        installationId=draft.installation_ref.installation_id,generation=draft.generation,pipelineId=draft.pipeline_id,
        controlId=control_id,revision=revision,selectionId=selection_id,selectionRevision=draft.source_selection_ref.revision,
        selectionHash=draft.source_selection_ref.content_hash,actor=actor,previousHash=previous_hash,
        draft=draft.model_dump(mode='json',by_alias=True))


@dataclass(frozen=True)
class RuntimeControlRecord:
    ref: PipelineExactRef
    draft: PipelineRuntimeControlDraft
    actor: str
    previous_hash: str | None


def decode_control_row(row):
    try:
        draft=PipelineRuntimeControlDraft.model_validate_json(json.dumps(row['payload']['draft'],allow_nan=False))
        args=dict(draft=draft,control_id=str(row['control_id']),revision=row['revision'],previous_hash=row['previous_hash'],actor=row['actor'])
        expected=build_control_payload(**args)
        names={'org_id':'orgId','project_id':'projectId','installation_id':'installationId','generation':'generation',
            'pipeline_id':'pipelineId','selection_id':'selectionId','selection_hash':'selectionHash'}
        if (canonical_sha256(row['payload'])!=canonical_sha256(expected) or canonical_sha256(expected)!=row['content_hash']
                or control_request_hash(**args)!=row['request_hash']
                or any(str(row[key])!=expected[name] for key,name in names.items())
                or type(row['selection_revision']) is not int or row['selection_revision']!=expected['selectionRevision']
                or row['previous_revision']!=(None if row['revision']==1 else row['revision']-1)
                or (row['revision']>1 and type(row['previous_revision']) is not int)):
            raise ValueError('control row differs')
        return RuntimeControlRecord(PipelineExactRef(resource_type='PipelineRuntimeControlRevision',
            resource_id='pipeline-control-'+args['control_id'],revision=row['revision'],content_hash=row['content_hash']),
            draft,row['actor'],row['previous_hash'])
    except (ValueError,KeyError,TypeError):
        raise ValueError('invalid runtime control record') from None


class PipelineRuntimeControlOwner:
    def __init__(self,*,selections):
        if type(selections) is not PipelineSourceSelectionOwner:
            raise TypeError('current source selection Owner required')
        self._selections=selections

    def append(self,conn,*,draft,actor,idempotency_key,previous_ref=None):
        _require_transaction(conn)
        draft=PipelineRuntimeControlDraft.model_validate(draft)
        key=validate_idempotency_key(idempotency_key)
        identity,revision,previous_hash=str(uuid4()),1,None
        if previous_ref is not None:
            previous_ref=PipelineExactRef.model_validate(previous_ref)
            identity=_ref_identity(previous_ref,'PipelineRuntimeControlRevision','pipeline-control-')
            revision,previous_hash=previous_ref.revision+1,previous_ref.content_hash
        args=dict(draft=draft,control_id=identity,revision=revision,previous_hash=previous_hash,actor=actor)
        request_hash=control_request_hash(**args)
        scope=TenantScope(draft.org_id,draft.project_id)
        target=(*scope.key,UUID(draft.installation_ref.installation_id),UUID(draft.generation))
        def persist(selection,spec):
            verify_control_selection(draft,selection)
            with conn.cursor(row_factory=dict_row) as cursor:
                row=cursor.execute('''SELECT * FROM pipeline_runtime_control_revision
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND idempotency_key=%s''',(*target,key)).fetchone()
                if row is not None:
                    saved=decode_control_row(row)
                    if row['request_hash']!=request_hash:raise RuntimeConflict('control idempotency request differs')
                    return saved.ref
                latest=cursor.execute('''SELECT * FROM pipeline_runtime_control_revision
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND pipeline_id=%s
                    ORDER BY revision DESC LIMIT 1''',(*target,draft.pipeline_id)).fetchone()
                if (latest is None and previous_ref is not None) or (latest is not None and decode_control_row(latest).ref!=previous_ref):
                    raise RuntimeRevisionConflict('control predecessor is not current')
                body=build_control_payload(**args)
                row=cursor.execute('''INSERT INTO pipeline_runtime_control_revision
                    (org_id,project_id,installation_id,generation,pipeline_id,control_id,revision,selection_id,selection_revision,
                     selection_hash,payload,content_hash,previous_revision,previous_hash,request_hash,idempotency_key,actor)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                    (*target,draft.pipeline_id,UUID(identity),revision,UUID(body['selectionId']),body['selectionRevision'],
                     body['selectionHash'],Jsonb(body),canonical_sha256(body),None if revision==1 else revision-1,
                     previous_hash,request_hash,key,actor)).fetchone()
                return decode_control_row(row).ref
        return self._selections.run_current(conn,scope=scope,ref=draft.source_selection_ref,actor=actor,execute=persist)

    def run_current_snapshot(self,conn,*,scope,ref,actor,execute):
        """Use the current control with the mapping compiled by asset authority."""
        return self._run_current(conn,scope=scope,ref=ref,actor=actor,execute=execute,snapshot=True)

    def run_current(self,conn,*,scope,ref,actor,execute):
        return self._run_current(conn,scope=scope,ref=ref,actor=actor,execute=execute,snapshot=False)

    def _run_current(self,conn,*,scope,ref,actor,execute,snapshot):
        _require_transaction(conn)
        if type(scope) is not TenantScope or not callable(execute):raise TypeError('exact current control consumer required')
        current=conn.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,current_setting('aos.project_id',true) AS project_id").fetchone()
        if _values(current,('role','org_id','project_id'))!=('aos_runtime',*scope.key):
            raise PermissionError('current runtime identity and tenant required')
        ref=PipelineExactRef.model_validate(ref)
        identity=_ref_identity(ref,'PipelineRuntimeControlRevision','pipeline-control-')
        with conn.cursor(row_factory=dict_row) as cursor:
            row=cursor.execute('''SELECT * FROM pipeline_runtime_control_revision
                WHERE org_id=%s AND project_id=%s AND control_id=%s AND revision=%s''',(*scope.key,UUID(identity),ref.revision)).fetchone()
            if row is None:raise LookupError('runtime control unavailable')
            saved=decode_control_row(row)
            if saved.ref!=ref:raise RuntimeConflict('runtime control reference differs')
        def consume(selection,spec):
            # SourceSelectionOwner now holds the installation lock used by all appends.
            with conn.cursor(row_factory=dict_row) as cursor:
                latest=cursor.execute('''SELECT * FROM pipeline_runtime_control_revision
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND pipeline_id=%s
                    ORDER BY revision DESC LIMIT 1''',(*scope.key,row['installation_id'],row['generation'],row['pipeline_id'])).fetchone()
            if latest is None or decode_control_row(latest).ref!=ref:
                raise RuntimeRevisionConflict('runtime control was superseded')
            verify_control_selection(saved.draft,selection)
            result=execute(saved.draft,spec)
            _reject_deferred(result)
            return result
        consume_selection=self._selections.run_current_snapshot if snapshot else self._selections.run_current
        return consume_selection(conn,scope=scope,ref=saved.draft.source_selection_ref,actor=actor,execute=consume)

"""Current, transaction-owned source call reservations; never a read permission token."""
from dataclasses import dataclass
from uuid import UUID

from psycopg.rows import dict_row

from aos_api.ec_ingress_journal import IngressJournal
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.pipeline_control_errors import SourceCallBudgetExhausted
from aos_api.pipeline_runtime_control_contracts import (PipelineExactRef,
    validate_digest_identical_alias_ref)
from aos_api.pipeline_runtime_control_owner import PipelineRuntimeControlOwner, _ref_identity, decode_control_row
from aos_api.tenant_scope import TenantScope


def _text(value, limit):
    if type(value) is not str or not 1 <= len(value) <= limit or value != value.strip() or not value.isprintable():
        raise ValueError('canonical claim identity required')
    return value


@dataclass(frozen=True)
class SourceClaimRecord:
    scope: TenantScope
    run_id: str
    installation_id: str
    generation: str
    pipeline_id: str
    control_ref: PipelineExactRef
    actor: str
    call_ordinal: int


@dataclass(frozen=True)
class SourceClaimReservation:
    record: SourceClaimRecord
    created: bool


@dataclass(frozen=True)
class _SavedRecoveryAdmission:
    original_controls: tuple
    successor: bool


def _validate_saved_recovery_context(admission,record,ref,draft,original):
    alias_refs=set()
    if (original.ref!=record.control_ref or original.actor!=record.actor
            or (record.installation_id,record.generation,record.pipeline_id)!=(
                original.draft.installation_ref.installation_id,original.draft.generation,
                original.draft.pipeline_id)):
        raise RuntimeConflict('saved recovery context differs')
    if record.control_ref.resource_id==ref.resource_id:
        if ref.revision<=record.control_ref.revision:
            raise RuntimeConflict('saved recovery control family differs')
        excluded={'not_before','expires_at','source_selection_ref'}
    else:
        if type(admission) is not _SavedRecoveryAdmission or admission.successor is not True:
            raise RuntimeConflict('saved recovery control family differs')
        facts=[value for value in admission.original_controls if value.ref==record.control_ref]
        if len(facts)!=1 or facts[0]!=original:
            raise RuntimeConflict('saved recovery context differs')
        excluded={'not_before','expires_at','source_selection_ref','installation_ref',
            'generation','execution_epoch','configuration_ref','package_ref'}
        alias_refs={'mapping_ref','schema_ref','masking_policy_ref'}
        excluded|=alias_refs
    if original.draft.model_dump(mode='json',exclude=excluded)!=draft.model_dump(mode='json',exclude=excluded):
        raise RuntimeConflict('saved recovery context differs')
    try:
        for field in alias_refs:
            validate_digest_identical_alias_ref(
                getattr(original.draft,field),getattr(draft,field))
    except ValueError as error:
        raise RuntimeConflict('saved recovery context differs') from error


def _decode(row):
    ref = PipelineExactRef(resource_type='PipelineRuntimeControlRevision',
        resource_id='pipeline-control-'+str(row['control_id']),revision=row['control_revision'],content_hash=row['control_hash'])
    _ref_identity(ref,'PipelineRuntimeControlRevision','pipeline-control-')
    ordinal = row['call_ordinal']
    if type(ordinal) is not int or not 1 <= ordinal <= 32:
        raise ValueError('invalid claim ordinal')
    return SourceClaimRecord(TenantScope(row['org_id'],row['project_id']),_text(row['run_id'],200),
        str(UUID(str(row['installation_id']))),str(UUID(str(row['generation']))),_text(row['pipeline_id'],200),
        ref,_text(row['actor'],240),ordinal)


class PipelineSourceClaimOwner:
    def __init__(self, *, controls, recovery=None, recovery_bindings=()):
        if type(controls) is not PipelineRuntimeControlOwner:
            raise TypeError('exact current runtime control Owner required')
        self._controls = controls
        self._journal = IngressJournal()
        self._recovery=recovery
        self._recovery_bindings=()
        if recovery is not None:
            from aos_api.pipeline_snapshot_group_recovery_authority import SnapshotGroupRecoveryAuthority
            if type(recovery) is not SnapshotGroupRecoveryAuthority or recovery._definitions._groups._groups._controls is not controls:
                raise TypeError('exact shared recovery authority required')
            if type(recovery_bindings) is not tuple or len(recovery_bindings)!=12:
                raise ValueError('complete fixed recovery bindings required')
            normalized=[]
            for item in recovery_bindings:
                if type(item) is not tuple or len(item)!=2:raise ValueError('exact recovery control/run pair required')
                ref=PipelineExactRef.model_validate(item[0])
                _ref_identity(ref,'PipelineRuntimeControlRevision','pipeline-control-')
                normalized.append((ref,_text(item[1],200)))
            if len({ref.resource_id for ref,_ in normalized})!=12 or len({run for _,run in normalized})!=12:
                raise ValueError('unique fixed recovery members required')
            self._recovery_bindings=tuple(normalized)
        elif recovery_bindings!=():
            raise ValueError('recovery bindings require fixed authority')

    def reserve(self, conn, *, scope, run_id, control_ref, actor):
        """Caller must confirm COMMIT before any separately reauthorized source call.

        created=False or an uncertain commit must never initiate a new source call.
        This method never commits, reads the source, or changes run status.
        """
        return self._operate(conn,scope=scope,run_id=run_id,control_ref=control_ref,actor=actor,create=True)

    def read_current(self, conn, *, scope, run_id, control_ref, actor):
        return self._operate(conn,scope=scope,run_id=run_id,control_ref=control_ref,actor=actor,create=False).record

    def read_saved_current(self, conn, *, scope, run_id, control_ref, actor):
        """Authorize only saved input under an exact current renewal or successor.

        The original claim remains unchanged. This path cannot reserve or grant
        another source call, including when the original outcome is unknown.
        """
        return self._operate(conn,scope=scope,run_id=run_id,control_ref=control_ref,
            actor=actor,create=False,saved_recovery=True).record

    def read_completed_current(self,conn,*,scope,run_id,control_ref,actor):
        """Current authorization over a completed immutable input, never a source call."""
        return self._operate(conn,scope=scope,run_id=run_id,control_ref=control_ref,actor=actor,
            create=False,saved_recovery=True,completed_read=True).record

    def _guard_group(self,conn,*,scope,group_id,actor,bindings):
        if self._recovery is not None:raise PermissionError('saved recovery requires original input path, never a new group claim')
        from aos_api.pipeline_snapshot_schedule_guard import guard_snapshot_schedule_group
        return guard_snapshot_schedule_group(conn,scope=scope,group_id=group_id,actor=actor,
            bindings=bindings,controls=self._controls)

    def _guard_single_prepare(self,conn,*,scope,run_id):
        if self._recovery is not None:raise PermissionError('saved recovery cannot prepare a new source read')
        from aos_api.pipeline_snapshot_schedule_guard import guard_single_snapshot_prepare
        guard_single_snapshot_prepare(conn,scope=scope,run_id=run_id)

    def _guard_schedule(self,conn,*,scope,run_id,control_ref,actor):
        if self._recovery is not None:
            if (PipelineExactRef.model_validate(control_ref),run_id) not in self._recovery_bindings:
                raise PermissionError('saved recovery fixed member differs')
            def admit(value):
                original=value.facts.controls[0].draft
                current=value.execution.group.members[0][1]
                successor=(original.installation_ref,original.generation)!=(current.installation_ref,current.generation)
                return _SavedRecoveryAdmission(value.facts.controls,successor)
            return self._recovery.run_current(conn,scope=scope,actor=actor,
                bindings=self._recovery_bindings,execute=admit)
        # Lazy import avoids the existing schedule/control Owner dependency cycle.
        from aos_api.pipeline_snapshot_schedule_guard import guard_snapshot_schedule_run
        guard_snapshot_schedule_run(conn,scope=scope,run_id=run_id,actor=actor,
            control_ref=control_ref,controls=self._controls)

    def _operate(self, conn, *, scope, run_id, control_ref, actor, create, saved_recovery=False, completed_read=False):
        if completed_read and create:raise ValueError('completed input cannot reserve source calls')
        if self._recovery is not None:
            if create:raise PermissionError('saved recovery cannot reserve another source call')
            saved_recovery=True
        run_id,actor = _text(run_id,200),_text(actor,240)
        ref = PipelineExactRef.model_validate(control_ref)
        identity = UUID(_ref_identity(ref,'PipelineRuntimeControlRevision','pipeline-control-'))
        if self._recovery is not None and (ref,run_id) not in self._recovery_bindings:
            raise PermissionError('saved recovery fixed member differs')
        from aos_api.pipeline_snapshot_claim_context import _check_source_claim_loop
        _check_source_claim_loop(conn,scope=scope,actor=actor,run_id=run_id,control_ref=ref)

        def current(draft, spec):
            # Global lock order: current installation first, then immutable run.
            recovery_admission=self._guard_schedule(conn,scope=scope,run_id=run_id,control_ref=ref,actor=actor)
            self._journal.lock_run(conn,scope,run_id)
            verify=self._journal.verify_completed_schedule_binding if completed_read else self._journal.verify_schedule_binding
            verify(conn,scope,run_id=run_id,pipeline_id=draft.pipeline_id,
                source_id=draft.source_id,source_revision=draft.source_configuration_ref.resource_id.removeprefix('source-config-'),
                pipeline_hash=draft.graph_hash,graph_revision=draft.graph_revision)
            with conn.cursor(row_factory=dict_row) as cursor:
                def read():
                    return cursor.execute('SELECT * FROM pipeline_controlled_source_claim WHERE org_id=%s AND project_id=%s AND run_id=%s',
                        (*scope.key,run_id)).fetchone()
                row = read()
                created = False
                if row is None:
                    if not create:
                        raise LookupError('source call claim unavailable')
                    if self._journal.read(conn,scope,run_id) is not None:
                        raise RuntimeConflict('uncontrolled ingress already exists')
                    count = cursor.execute('''SELECT count(*) AS count,max(call_ordinal) AS last
                        FROM pipeline_controlled_source_claim WHERE org_id=%s AND project_id=%s AND control_id=%s AND control_revision=%s''',
                        (*scope.key,identity,ref.revision)).fetchone()
                    if count['count'] != (count['last'] or 0):
                        raise RuntimeConflict('source claim ordinal history differs')
                    if count['count'] >= draft.max_source_calls:
                        raise SourceCallBudgetExhausted('source call budget exhausted')
                    cursor.execute('''INSERT INTO pipeline_controlled_source_claim
                        (org_id,project_id,run_id,installation_id,generation,pipeline_id,control_id,control_revision,control_hash,call_ordinal,actor)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                        (*scope.key,run_id,UUID(draft.installation_ref.installation_id),UUID(draft.generation),draft.pipeline_id,
                         identity,ref.revision,ref.content_hash,count['count']+1,actor))
                    row,created = read(),True
                record = _decode(row)
                if saved_recovery:
                    if self._journal.read(conn,scope,run_id) is None:
                        raise RuntimeConflict('saved recovery requires original input')
                    if record.control_ref != ref:
                        original_identity=UUID(_ref_identity(record.control_ref,
                            'PipelineRuntimeControlRevision','pipeline-control-'))
                        original_row=cursor.execute('''SELECT * FROM pipeline_runtime_control_revision
                            WHERE org_id=%s AND project_id=%s AND control_id=%s AND revision=%s''',
                            (*scope.key,original_identity,record.control_ref.revision)).fetchone()
                        if original_row is None:
                            raise RuntimeConflict('original control unavailable')
                        original=decode_control_row(original_row)
                        _validate_saved_recovery_context(recovery_admission,record,ref,draft,original)
                successor=(type(recovery_admission) is _SavedRecoveryAdmission and recovery_admission.successor is True)
                if (record.scope != scope or record.run_id != run_id
                    or ((record.installation_id,record.generation)!=(draft.installation_ref.installation_id,draft.generation)
                        and not (saved_recovery and successor)) or record.pipeline_id != draft.pipeline_id
                    or (record.control_ref != ref and not saved_recovery)
                    or record.actor != actor or record.call_ordinal > draft.max_source_calls):
                    raise RuntimeConflict('source claim current binding differs')
                return SourceClaimReservation(record,created)

        return self._controls.run_current(conn,scope=scope,ref=ref,actor=actor,execute=current)

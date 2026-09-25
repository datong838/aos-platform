"""Complete one original snapshot group; never accept a client success claim."""
from time import monotonic
from uuid import UUID,NAMESPACE_URL,uuid5
from contextlib import contextmanager
from aos_api.asset_registry.canonical_json import canonical_sha256

from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ingress_recovery import _check_active
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_projection_owner import PipelineSnapshotGroupProjectionOwner
from aos_api.pipeline_snapshot_group_retirement_executor import ControlledSnapshotGroupRetirementExecutor
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.qyh_cron_scheduler import _persist_schedule_result
from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.recoverable_store_attempt import RecoverableStoreAttemptOwner
from aos_api.extension_runtime.host_lease import OptInHostLease


class PipelineSnapshotGroupCompletion:
    """Trusted host composition for Store recovery and atomic schedule closure."""

    def __init__(self, *, claims, store, connect, eng, host_lease=None):
        if type(claims) is not PipelineSourceClaimOwner or type(store) is not EcomConsistencyStore:
            raise TypeError('exact original snapshot Owners required')
        if not callable(connect):
            raise TypeError('trusted connection factory required')
        if host_lease is not None and type(host_lease) is not OptInHostLease:
            raise TypeError('exact snapshot Completion Host lease required')
        self._claims, self._store, self._connect = claims, store, connect
        self._host_lease = host_lease
        self._retirement = ControlledSnapshotGroupRetirementExecutor(
            claims=claims, store=store, connect=connect, eng=eng,
        )
        self._projection = PipelineSnapshotGroupProjectionOwner(claims=claims, store=store)
        self._attempts = RecoverableStoreAttemptOwner(connect=connect,host_lease=host_lease)

    @staticmethod
    def _lock_key(scope, group_id):
        if type(scope) is not TenantScope or type(group_id) is not str or str(UUID(group_id)) != group_id:
            raise ValueError('canonical snapshot group scope required')
        return f'aos:snapshot-group-completion:{scope.org_id}:{scope.project_id}:{group_id}'

    @contextmanager
    def _transaction(self, scope):
        with self._retirement._transaction(scope) as conn:
            if self._host_lease is not None:
                self._host_lease.fence_in_transaction(
                    conn,dict(org_id=scope.org_id,project_id=scope.project_id))
            yield conn

    @staticmethod
    def _normalize_bindings(bindings):
        if type(bindings) is not tuple or not 1 <= len(bindings) <= 12:
            raise ValueError('bounded exact group bindings required')
        normalized = tuple((PipelineExactRef.model_validate(ref), run) for ref, run in bindings)
        if any(type(run) is not str or not run or run != run.strip() for _, run in normalized):
            raise ValueError('canonical group run required')
        if len({run for _, run in normalized}) != len(normalized):
            raise ValueError('unique group runs required')
        return normalized

    def _rows(self, conn, scope, bindings, *, lock=False):
        run_ids = [run for _, run in bindings]
        suffix = ' FOR UPDATE OF r,s' if lock else ''
        rows = conn.execute(
            """SELECT r.id,r.schedule_id,r.trigger,r.status,r.executor_id,r.executor_stopped,
                      r.finished_at,s.pipeline_id,s.enabled,s.ingest,s.last_run
                 FROM meta_schedule_run r JOIN meta_schedule s
                   ON s.org_id=r.org_id AND s.project_id=r.project_id AND s.id=r.schedule_id
                WHERE r.org_id=%s AND r.project_id=%s AND r.id=ANY(%s)""" + suffix,
            (*scope.key, run_ids),
        ).fetchall()
        indexed = {row['id']: row for row in rows}
        if len(indexed) != len(bindings) or set(indexed) != set(run_ids):
            raise IngressJournalConflict('GROUP_RUN_BINDING_MISSING')
        return indexed

    @staticmethod
    def _route(rows):
        values = tuple(rows.values())
        running = all(row['status'] == 'running' and row['executor_stopped'] is not True
                      and row['finished_at'] is None for row in values)
        completed = all(row['status'] == 'succeeded' and row['executor_id'] == 'ec-live-v1'
                        and row['executor_stopped'] is True and row['finished_at'] is not None
                        for row in values)
        if running:
            return 'running'
        if completed:
            return 'completed'
        raise IngressJournalConflict('GROUP_RUN_STATE_MIXED')

    def _route_with_recovery(self,rows):
        values=tuple(rows.values())
        if (self._claims._recovery is not None and len(values)==12
                and all(r['status']=='failed' and r['executor_stopped'] is True and r['finished_at'] is not None for r in values)):
            return 'stopped_failed'
        return self._route(rows)

    def _recover_stopped_group(self,conn,args,*,deadline,cancel_event):
        """Called only inside complete's original session lock and outer transaction."""
        from aos_api.ec_ingress_claim import claim_failed_run
        from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
        authority=self._claims._recovery
        if authority is None or authority._group_id!=args['group_id']:
            raise PermissionError('fixed original recovery group required')
        scope=args['scope']
        @contextmanager
        def shared(requested):
            if requested!=scope:raise PermissionError('shared recovery transaction scope differs')
            yield conn
        def reopen(current):
            if PipelineExactRef.model_validate(args['policy_ref'])!=current.execution.policy_ref:
                raise ValueError('recovery completion policy differs')
            rows=self._rows(conn,scope,args['bindings'],lock=True)
            if self._route_with_recovery(rows)!='stopped_failed':
                raise IngressJournalConflict('GROUP_STOPPED_FAILED_REQUIRED')
            for ref,run in sorted(args['bindings'],key=lambda pair:pair[1]):
                _check_active(deadline,cancel_event)
                identity=canonical_sha256(dict(tenant=list(scope.key),groupId=args['group_id'],
                    recoveryRef=current.receipt['ref'],runId=run))
                claim_id=str(uuid5(NAMESPACE_URL,identity))
                journal=ControlledIngressJournal(claims=self._claims,scope=scope,run_id=run,
                    control_ref=ref,actor=args['actor'],saved_recovery=True)
                claimed=claim_failed_run(shared,scope,run,claim_id,journal=journal,expected_schedule_id=rows[run]['schedule_id'])
                if claimed is not True:
                    raise IngressJournalConflict('GROUP_RECOVERY_APPROVAL_ALREADY_CONSUMED')
            if self._route(self._rows(conn,scope,args['bindings']))!='running':
                raise IngressJournalConflict('GROUP_RECOVERY_NOT_ATOMIC')
            _check_active(deadline,cancel_event)
        authority.run_current(conn,scope=scope,actor=args['actor'],bindings=args['bindings'],execute=reopen)

    @staticmethod
    def _validate_schedules(current, rows):
        source = current.input if hasattr(current, 'input') else current
        expected = {parent['runId']: draft.pipeline_id
                    for (_, draft, _), parent in zip(source.group.members, source.parents)}
        if set(expected) != set(rows):
            raise IngressJournalConflict('GROUP_RUN_BINDING_CHANGED')
        for run_id, pipeline_id in expected.items():
            row = rows[run_id]
            ingest = row['ingest']
            if (row['pipeline_id'] != pipeline_id or row['enabled'] is not True
                    or type(ingest) is not dict or ingest.get('kind') != 'pipeline-live-v1'
                    or ingest.get('pipelineId') != pipeline_id):
                raise IngressJournalConflict('GROUP_SCHEDULE_BINDING_CHANGED')

    def _read_completed(self, conn, args, rows):
        def verify_projection(projection):
            self._validate_schedules(projection.input, rows)
            return projection
        projection = self._projection.run_current(
            conn,
            scope=args['scope'], group_id=args['group_id'], actor=args['actor'],
            bindings=args['bindings'], execute=verify_projection,
        )
        retirement = self._retirement._retirement.read_completed_current(conn, **args)
        audit = self._retirement._retirement._audit.read_completed_current(conn, **args)
        for row in rows.values():
            last = row['last_run']
            if (type(last) is not dict or last.get('id') != row['id'] or last.get('status') != 'succeeded'):
                raise IngressJournalConflict('GROUP_SCHEDULE_RESULT_MISSING')
        return projection, retirement, audit

    def _recovery_attempt_target(self, conn, args):
        """Bind a short current-authority transaction before expensive assessment."""
        authority = self._claims._recovery
        if authority is None:
            raise PermissionError('fixed original recovery group required')
        current = authority.attempt_target_current(
            conn, scope=args['scope'], actor=args['actor'], bindings=args['bindings'],
        )
        receipt = current.receipt
        if receipt['body']['policyRef'] != PipelineExactRef.model_validate(
                args['policy_ref']).model_dump(mode='json', by_alias=True, exclude_none=True):
            raise ValueError('recovery completion policy differs')
        target = (current.installation_id, current.generation, current.execution_epoch)
        request_hash = self._attempt_request_hash(
            scope=args['scope'], group_id=args['group_id'], actor=args['actor'],
            source_claim_hash=receipt['body']['originalSourceClaimHash'],
            manifest_hash=receipt['body']['inputManifestHash'],
            policy_content_hash=PipelineExactRef.model_validate(receipt['body']['policyRef']).content_hash,
            runs=(run for _, run in args['bindings']),
        )
        return target, request_hash

    @staticmethod
    def _attempt_request_hash(*, scope, group_id, actor, source_claim_hash,
                              manifest_hash, policy_content_hash, runs):
        return canonical_sha256(dict(
            schemaVersion='aos.recoverable-store-attempt-request/v2',
            tenant={'orgId': scope.org_id, 'projectId': scope.project_id},
            groupId=group_id, actor=actor, originalSourceClaimHash=source_claim_hash,
            inputManifestHash=manifest_hash, policyContentHash=policy_content_hash,
            runIds=sorted(runs),
        ))

    def _finish(self, args, execution, duration_ms, *, deadline, cancel_event):
        scope, bindings = args['scope'], args['bindings']
        assessment = self._retirement._retirement._commands._relationships
        with self._transaction(scope) as conn:
            current = assessment.run_current(conn, **args, execute=lambda value: value)
            rows = self._rows(conn, scope, bindings, lock=True)
            if self._route(rows) != 'running':
                raise IngressJournalConflict('GROUP_RUN_STATE_CHANGED')
            self._validate_schedules(current, rows)
            members = {item['run_id']: item for item in execution['links']['objects']['members']}
            if set(members) != set(rows):
                raise IngressJournalConflict('GROUP_EXECUTION_MEMBERS_DIFFER')
            persisted = []
            for run_id in sorted(rows):
                _check_active(deadline, cancel_event)
                row, member = rows[run_id], members[run_id]
                last = _persist_schedule_result(
                    conn, scope, schedule_id=row['schedule_id'], run_id=run_id,
                    trigger=row['trigger'], duration_ms=duration_ms,
                    result={'ok': True, 'rows_written': member['rows_written'],
                            'executor_stopped': True, 'error_code': '', 'error_message': ''},
                    expected_status='running',
                )
                persisted.append(last)
            completed_rows = self._rows(conn, scope, bindings, lock=False)
            projection, retirement, audit = self._read_completed(conn, args, completed_rows)
            if (retirement.preparation_hash != execution['preparation_hash']
                    or retirement.audit_hash != execution['relationship_audit_hash']
                    or audit.content_hash != execution['relationship_audit_hash']):
                raise IngressJournalConflict('GROUP_COMPLETION_RECEIPT_CHANGED')
        return persisted, projection, retirement

    def complete(self, *, scope, group_id, actor, bindings, policy_ref, deadline=None, cancel_event=None):
        _check_active(deadline, cancel_event)
        bindings = self._normalize_bindings(bindings)
        args = dict(scope=scope, group_id=group_id, actor=actor,
                    bindings=bindings, policy_ref=policy_ref)
        lock_key = self._lock_key(scope, group_id)
        with self._connect() as lock_conn:
            locked = lock_conn.execute(
                'SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS locked', (lock_key,),
            ).fetchone()['locked']
            if locked is not True:
                raise IngressJournalConflict('GROUP_COMPLETION_BUSY')
            try:
                attempt = None
                recover_stopped = False
                with self._transaction(scope) as conn:
                    rows = self._rows(conn, scope, bindings, lock=False)
                    route = self._route_with_recovery(rows)
                    if route == 'completed':
                        projection, retirement, audit = self._read_completed(conn, args, rows)
                        attention = any(counts[key] for counts in audit.counts.values()
                                        for key in ('missingExpected', 'extraActive', 'uncertainReferences'))
                        _check_active(deadline, cancel_event)
                        return dict(status='succeeded', replayed=True, group_id=group_id,
                                    runs=sorted(rows), projection_hash=projection.content_hash,
                                    preparation_hash=retirement.preparation_hash,
                                    reconciliation_status=('requires_attention' if attention else 'complete'))
                    recover_stopped = route == 'stopped_failed'
                    if self._claims._recovery is not None:
                        target, request_hash = self._recovery_attempt_target(conn, args)
                        installation_id, generation, execution_epoch = target
                    else:
                        current = self._retirement._retirement._commands._relationships._assessments.run_current(
                            conn, **args, execute=lambda value: value,
                        )
                        drafts = tuple(item[1] for item in current.input.group.members)
                        targets = {
                            (draft.installation_ref.installation_id, draft.generation, draft.execution_epoch)
                            for draft in drafts
                        }
                        if len(drafts) != len(bindings) or len(targets) != 1:
                            raise IngressJournalConflict('GROUP_RUNTIME_TARGET_DIFFERS')
                        installation_id, generation, execution_epoch = targets.pop()
                        request_hash = self._attempt_request_hash(
                            scope=scope, group_id=group_id, actor=actor,
                            source_claim_hash=current.input.claim.request_hash,
                            manifest_hash=current.input.manifest_hash,
                            policy_content_hash=current.policy_ref.content_hash,
                            runs=(run for _, run in bindings),
                        )
                    attempt = self._attempts.claim(
                        conn, scope=scope, installation_id=installation_id,
                        generation=generation, execution_epoch=execution_epoch,
                        operation_key='snapshot-group-completion:'+group_id,
                        idempotency_key='snapshot-group:'+group_id,
                        request_hash=request_hash,
                    )
                with attempt:
                    cancel_event = attempt.cancellation(cancel_event)
                    if recover_stopped:
                        with self._transaction(scope) as conn:
                            rows=self._rows(conn,scope,bindings,lock=False)
                            if self._route_with_recovery(rows)!='stopped_failed':
                                raise IngressJournalConflict('GROUP_RUN_STATE_CHANGED')
                            self._recover_stopped_group(
                                conn,args,deadline=deadline,cancel_event=cancel_event)
                            if self._route(self._rows(conn,scope,bindings,lock=False))!='running':
                                raise IngressJournalConflict('GROUP_RUN_STATE_CHANGED')
                            _check_active(deadline,cancel_event)
                    started = monotonic()
                    execution = self._retirement.execute(
                        **args, deadline=deadline, cancel_event=cancel_event,
                    )
                    _check_active(deadline, cancel_event)
                    duration_ms = max(1, int((monotonic() - started) * 1000))
                    runs, projection, retirement = self._finish(
                        args, execution, duration_ms, deadline=deadline, cancel_event=cancel_event,
                    )
                return dict(status='succeeded', replayed=False, group_id=group_id,
                            runs=runs, projection_hash=projection.content_hash,
                            preparation_hash=retirement.preparation_hash,
                            reconciliation_status=execution['reconciliation_status'])
            finally:
                lock_conn.execute(
                    'SELECT pg_advisory_unlock(hashtextextended(%s,0))', (lock_key,),
                )

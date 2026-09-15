"""Dedicated gate: canonical start followed by initial pause in the original transaction."""
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_store import AipActionStore
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.aip_production_contract_store import canonical_hash, ProductionContractIdempotencyConflict
from aos_api.aip_production_contracts import ProductionStartDecisionStatus
from aos_api.aip_production_start_service import AipProductionStartService
from aos_api.ecommerce_analysis_bootstrap_action import _BootstrapActionGuard
from aos_api.ecommerce_analysis_bootstrap_authority import require_current_bootstrap_review_identity
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory


class _BootstrapProductionStartService(AipProductionStartService):
    def __init__(self, guard):
        if type(guard) is not _BootstrapActionGuard:
            raise TypeError('exact current bootstrap guard required')
        self._guard = guard
        factory = TransactionBoundConnectFactory(HostTransaction(guard.conn), guard.current.analysis.scope)
        super().__init__(connect_factory=factory, action_store=AipActionStore(factory, bootstrap_guard=guard))

    def start(self, scope, actor, idempotency_key, body):
        guard, conn = self._guard, self._guard.conn
        analysis = guard.current.analysis
        if scope != analysis.scope or actor != analysis.source.actor:
            raise PermissionError('bootstrap original executor required')
        receipt = guard.intent.compilation_receipt
        profile = guard.intent.compilation_binding.request.profile
        if (body.task_id != receipt.task_id or body.plan_ref != receipt.plan_ref
                or body.preview_ref != guard.preview_ref or body.production_context_ref != profile.production_context_ref
                or (body.logic_graph_id, body.logic_revision, body.logic_graph_hash) != (
                    receipt.logic_ref.resource_id, receipt.logic_ref.revision, receipt.logic_ref.content_hash)):
            raise ValueError('bootstrap start request exact lineage differs')
        request_hash = canonical_hash(body.model_dump(mode='json', by_alias=True))
        def current(snapshot, _request, _dispatch):
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                (f'aip-w2d-start:{scope.org_id}:{scope.project_id}:{idempotency_key}',))
            old = conn.execute('SELECT * FROM aip_production_start_decision WHERE org_id=%s AND project_id=%s AND idempotency_key=%s',
                               (*scope.key, idempotency_key)).fetchone()
            approved = self._initialization_authority(conn, scope, body)
            if old is not None:
                if old['request_hash'] != request_hash:
                    raise ProductionContractIdempotencyConflict('bootstrap idempotency payload drift')
                decision = self._decision(scope, old)
                if decision.status != ProductionStartDecisionStatus.STARTED or not decision.task_run_ref:
                    raise ValueError('bootstrap prior decision did not initialize a runtime')
                run_id = decision.task_run_ref.resource_id
            else:
                guard.current._read(conn, snapshot, guard.intent, guard.preview_ref)
                decision = super(_BootstrapProductionStartService, self).start(scope, actor, idempotency_key, body)
                if decision.status != ProductionStartDecisionStatus.STARTED or not decision.task_run_ref:
                    raise ValueError('bootstrap original start gate blocked: ' + ','.join(b.code for b in decision.blockers))
                run_id = decision.task_run_ref.resource_id
                run = self._tasks.get_run(scope, run_id)
                task = conn.execute('SELECT version FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s',
                                    (*scope.key, body.task_id)).fetchone()
                started = self._tasks.start_run(scope, run_id, expected_run_version=run.version,
                    expected_task_version=task['version'], actor=actor, idempotency_key=idempotency_key+'-start')
                self._tasks.pause_run(scope, run_id, expected_run_version=started.run.version,
                    expected_task_version=started.task.version, actor=actor, idempotency_key=idempotency_key+'-pause',
                    reason='analysis initialization: first input not executed', checkpoint_before_first_step=True)
            guard.current._read(conn, snapshot, guard.intent, guard.preview_ref, initialized_run_id=run_id)
            run = self._tasks.get_run(scope, run_id)
            timeline = self._tasks.timeline(scope, run_id)
            if (run.status.value != 'paused' or not run.last_checkpoint_id or timeline.steps or timeline.artifacts
                    or len(timeline.checkpoints) != 1
                    or timeline.checkpoints[0]['checkpoint_id'] != run.last_checkpoint_id
                    or timeline.checkpoints[0]['state_snapshot_ref'].get('kind') != 'initial-input'
                    or timeline.checkpoints[0]['state_snapshot_ref'].get('status') != 'not-started'):
                raise ValueError('bootstrap requires untouched first-input pause')
            if conn.execute('SELECT 1 FROM aip_agent_run WHERE org_id=%s AND project_id=%s AND task_run_id=%s LIMIT 1',
                            (*scope.key, run_id)).fetchone() is not None:
                raise ValueError('bootstrap cannot execute an agent')
            if self._initialization_authority(conn, scope, body) != approved:
                raise ValueError('bootstrap authority changed during initialization')
            self._record_authority(conn, scope, approved)
            return dict(decision=decision, run=run)
        with conn.transaction():
            return analysis._phase(conn, guard.claimed, current)

    def _check_action(self, conn, scope, body, preview, snapshot, blockers):
        super()._check_action(conn, scope, body, preview, snapshot, blockers)
        authority = self._initialization_authority(conn, scope, body)
        waived = {'ANALYSIS_BOOTSTRAP_SPECIALIZED_GATE_REQUIRED'}
        if authority['kind'] == 'current-event-control-initialization':
            waived.update({'ACTION_PROPOSAL_NOT_APPROVED', 'ACTION_APPROVAL_QUORUM_LOST'})
        snapshot.append(self._record_authority(conn, scope, authority))
        blockers[:] = [item for item in blockers if item.code not in waived]

    def _initialization_authority(self, conn, scope, body):
        guard = self._guard
        row = conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR UPDATE',
                           (*scope.key, body.action_proposal_ref.proposal_id)).fetchone()
        if (row is None or row['action_type_id'] != 'ecommerce_analysis_bootstrap'
                or row['created_by'] != guard.current.analysis.source.actor or row['status'] not in {'drafted', 'approved'}
                or row['version'] != body.action_proposal_ref.version or row['proposal_hash'] != body.action_proposal_ref.proposal_hash
                or row['payload'] != {'bootstrapIntent': guard.intent.model_dump(mode='json', by_alias=True)}
                or row['task_id'] != body.task_id or row['run_id'] is not None
                or (row['impact_preview_id'], row['impact_preview_revision'], row['impact_preview_hash']) != (
                    body.preview_ref.resource_id, body.preview_ref.revision, body.preview_ref.content_hash)):
            raise ValueError('bootstrap exact approved proposal required')
        require_current_bootstrap_review_identity(transaction=HostTransaction(guard.conn), scope=scope,
            actor=guard.current.analysis.source.actor, maker=row['created_by'],
            action_snapshot=row['action_type_snapshot'], checker=False)
        risk = classify_action_risk(row['action_type_id'], row['action_type_snapshot'], row['payload'], ActionRiskLevel(row['risk_level']))
        policy = dict(floor=risk.floor.value, reasons=list(risk.reasons), **risk.approval_policy)
        if (risk.level != ActionRiskLevel.R1 or row['policy_snapshot'] != policy
                or row['approval_policy_hash'] != canonical_hash(policy) or policy['draftOnly'] is not False
                or policy['makerChecker'] is not True or policy['executionAllowed'] is not True):
            raise ValueError('bootstrap current initialization policy required')
        draft = conn.execute('SELECT snapshot FROM aip_action_draft WHERE org_id=%s AND project_id=%s AND proposal_id=%s ORDER BY proposal_version DESC LIMIT 1',
                             (*scope.key, row['proposal_id'])).fetchone()
        if (draft is None or canonical_hash(draft['snapshot']) != row['proposal_hash']
                or draft['snapshot'].get('payload') != row['payload'] or draft['snapshot'].get('policy') != policy
                or draft['snapshot'].get('actionBindingHash') != row['action_binding_hash']):
            raise ValueError('bootstrap approved draft snapshot differs')
        now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if row['status'] == 'drafted':
            if policy.get('controlledSourceInitialization') is not True or row['expires_at'] <= now:
                raise ValueError('bootstrap current source derivation policy required')
            if conn.execute('SELECT 1 FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s LIMIT 1',
                            (*scope.key, row['proposal_id'])).fetchone() is not None:
                raise ValueError('bootstrap source derivation cannot bypass an existing review')
            proof = self._source_derivation(conn, scope, body)
            return dict(kind=proof['kind'], proposal=dict(row), approvals=[], proof=proof)
        events = conn.execute("SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s AND decision='approved' ORDER BY approval_event_id FOR SHARE",
                              (*scope.key, row['proposal_id'])).fetchall()
        if row['expires_at'] <= now or len(events) < policy['minimumApprovals'] or len({e['actor_id'] for e in events}) != len(events):
            raise ValueError('bootstrap current independent approval required')
        for event in events:
            roles = require_current_bootstrap_review_identity(transaction=HostTransaction(guard.conn), scope=scope,
                actor=event['actor_id'], maker=row['created_by'], action_snapshot=row['action_type_snapshot'], checker=True)
            expected = canonical_hash(dict(tenant=dict(orgId=scope.org_id, projectId=scope.project_id),
                actorId=event['actor_id'], roles=sorted(role.lower() for role in roles), slotId=event['slot_id'],
                approvalPolicyHash=row['approval_policy_hash']))
            if (event['expires_at'] is None or not event['created_at'] <= now < event['expires_at']
                    or event['proposal_hash'] != row['proposal_hash'] or not 1 <= event['proposal_version'] < row['version']
                    or event['action_binding_hash'] != row['action_binding_hash']
                    or event['approval_policy_hash'] != row['approval_policy_hash'] or event['eligibility_snapshot_hash'] != expected):
                raise ValueError('bootstrap current approval event differs')
        ended = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if row['expires_at'] <= ended or any(event['expires_at'] <= ended for event in events):
            raise ValueError('bootstrap approval expired during current checks')
        proof = dict(kind='current-independent-bootstrap-review', actor=guard.current.analysis.source.actor,
            intentHash=guard.intent.content_hash, proposalRef=body.action_proposal_ref.model_dump(mode='json', by_alias=True),
            previewRef=body.preview_ref.model_dump(mode='json', by_alias=True),
            approvalEvents=[dict(eventId=e['approval_event_id'], actor=e['actor_id'],
                proposalVersion=e['proposal_version'], policyHash=e['approval_policy_hash']) for e in events])
        return dict(kind=proof['kind'], proposal=dict(row), approvals=[dict(e) for e in events], proof=proof)


    def _source_derivation(self, conn, scope, body):
        from aos_api.business_investigation_shared_contracts import InvestigationExactRef
        guard = self._guard
        identity = 'SELECT pg_backend_pid() AS pid,txid_current() AS xid'
        if (scope != guard.current.analysis.scope
                or conn.execute(identity).fetchone() != guard.conn.execute(identity).fetchone()):
            raise PermissionError('bootstrap source derivation transaction differs')
        intent = guard.intent.checked()
        def current(snapshot, request, _dispatch):
            if (intent.source_control_receipt_ref != InvestigationExactRef.model_validate(snapshot['source']['controlReceipt']['receiptRef'])
                    or intent.occurrence_ref != InvestigationExactRef.model_validate(request['occurrenceRef'])):
                raise ValueError('bootstrap source derivation no longer matches original control')
            return dict(kind='current-event-control-initialization', actor=guard.current.analysis.source.actor,
                intentHash=intent.content_hash, proposalRef=body.action_proposal_ref.model_dump(mode='json', by_alias=True),
                previewRef=body.preview_ref.model_dump(mode='json', by_alias=True),
                sourceControlReceiptRef=intent.source_control_receipt_ref.model_dump(mode='json', by_alias=True),
                occurrenceRef=intent.occurrence_ref.model_dump(mode='json', by_alias=True),
                businessExecutionAuthorized=False, externalEffectAuthorized=False)
        return guard.current.analysis._phase(guard.conn, guard.claimed, current)

    def _record_authority(self, conn, scope, authority):
        from psycopg.types.json import Jsonb
        proof = authority['proof']
        identity = 'evidence-initialization-authority-' + canonical_hash([*scope.key, self._guard.intent.content_hash])
        subject = self._guard.intent.compilation_receipt.run_ref.model_dump(mode='json', by_alias=True)
        existing = conn.execute('SELECT observed_at FROM aip_evidence WHERE org_id=%s AND project_id=%s AND evidence_id=%s',
                                (*scope.key, identity)).fetchone()
        observed = existing['observed_at'] if existing else conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        payload = dict(schemaVersion='aos.ecommerce.initialization-authority/v1', proof=proof, validatedAt=observed.isoformat())
        digest = canonical_hash(payload)
        actor = self._guard.current.analysis.source.actor
        conn.execute("""INSERT INTO aip_evidence(org_id,project_id,evidence_id,run_id,evidence_type,subject_ref,
            source_type,source_ref,observed_at,freshness_at,content_hash,redaction,payload,created_by,created_at)
            VALUES(%s,%s,%s,NULL,'analysis-initialization-authority',%s,%s,%s,%s,%s,%s,'{}',%s,%s,clock_timestamp())
            ON CONFLICT(org_id,project_id,evidence_id) DO NOTHING""",
            (*scope.key,identity,Jsonb(subject),authority['kind'],self._guard.intent.content_hash,
             observed,observed,digest,Jsonb(payload),actor))
        row = conn.execute("""SELECT e.*,EXISTS(SELECT 1 FROM aip_evidence_revoke_event r
            WHERE r.org_id=e.org_id AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id
              AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked FROM aip_evidence e
            WHERE e.org_id=%s AND e.project_id=%s AND e.evidence_id=%s""",(*scope.key,identity)).fetchone()
        expected = dict(run_id=None,evidence_type='analysis-initialization-authority',subject_ref=subject,
            source_type=authority['kind'],source_ref=self._guard.intent.content_hash,observed_at=observed,
            freshness_at=observed,content_hash=digest,redaction={},payload=payload,created_by=actor)
        if (row is None or row['revoked'] or any(row[k] != v for k,v in expected.items()) or row['created_at'] < observed
                or observed > conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']):
            raise ValueError('bootstrap initialization authority Evidence differs')
        return dict(resourceType='Evidence', resourceId=identity, revision=1, contentHash='sha256:'+digest,
                    authorityKind=authority['kind'])

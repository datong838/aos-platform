"""Necessary independent checker source facts, not Judge-call approval.

The original Action routing remains closed until formal Judge rules and their
exact implementation/template authority are wired and verified separately.
"""
from aos_api.aip_model_eval_action import ModelEvalActionGuard
from aos_api.aip_model_eval_judge_request_store import (
    ModelJudgeCallRequestStore, ModelJudgeRequestRejected,
)
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope


class ModelJudgeCallSourceGuard:
    def require_pending_for_checker(self,conn,principal: Principal,
                                    request_id: str,request_hash: str) -> dict:
        if type(principal) is not Principal or principal.token_kind!='oidc':
            raise ModelJudgeRequestRejected('JUDGE_OIDC_CHECKER_REQUIRED')
        scope=TenantScope(principal.org_id,principal.project_id)
        request=ModelJudgeCallRequestStore().require_current(conn,scope,request_id,request_hash)
        if principal.subject==request['created_by']:
            raise ModelJudgeRequestRejected('JUDGE_INDEPENDENT_CHECKER_REQUIRED')
        try:
            ModelEvalActionGuard._role(conn,scope,principal.subject)
        except (TypeError,ValueError,RuntimeError) as exc:
            raise ModelJudgeRequestRejected('JUDGE_CURRENT_CHECKER_OWNER_REQUIRED') from exc
        # Membership can wait. Recheck all original sources and deadlines after
        # that wait, without persisting or treating these facts as permission.
        current=ModelJudgeCallRequestStore().require_current(conn,scope,request_id,request_hash)
        return {'requestId':current['request_id'],'requestHash':current['request_hash'],
                'maker':current['created_by'],'checker':principal.subject,
                'necessaryFactsOnly':True,'approvalAllowed':False,'executionAllowed':False}


    def require_rule_pending_for_checker(self,conn,principal,request_id,request_hash,*,release_policy,artifact_bytes):
        if type(principal) is not Principal or principal.token_kind!='oidc':
            raise ModelJudgeRequestRejected('JUDGE_OIDC_CHECKER_REQUIRED')
        scope=TenantScope(principal.org_id,principal.project_id)
        store=ModelJudgeCallRequestStore()
        current=store.require_current_with_rule(conn,scope,request_id,request_hash,release_policy=release_policy,artifact_bytes=artifact_bytes)
        if principal.subject==current['created_by']:
            raise ModelJudgeRequestRejected('JUDGE_INDEPENDENT_CHECKER_REQUIRED')
        try:
            ModelEvalActionGuard._role(conn,scope,principal.subject)
        except (TypeError,ValueError,RuntimeError) as exc:
            raise ModelJudgeRequestRejected('JUDGE_CURRENT_CHECKER_OWNER_REQUIRED') from exc
        current=store.require_current_with_rule(conn,scope,request_id,request_hash,release_policy=release_policy,artifact_bytes=artifact_bytes)
        return {'requestId':current['request_id'],'requestHash':current['request_hash'],
            'maker':current['created_by'],'checker':principal.subject,'ruleHash':current['request_json']['ruleFacts']['ruleHash'],
            'necessaryFactsOnly':True,'approvalAllowed':False,'executionAllowed':False}


ACTION_ID='aip_request_model_judge_call'
OBJECT_ID='ModelJudgeCallRequest'
_OBJECT={'id':OBJECT_ID,'name':'模型判读调用申请','description':'仅供独立审批的不可执行申请','published':True,'properties':[],'required_markings':[]}
_ACTION={'id':ACTION_ID,'name':'申请模型判读调用','objectType':OBJECT_ID,'parameters':[],'requiredMarkings':[],'submissionCriteria':[]}


class ModelJudgeCallActionGuard:
    """Server-only signed rule dependency; original Action writes decisions."""
    def __init__(self,*,release_policy,artifact_bytes):
        from aos_api.asset_registry.release_policy import ReleasePolicy
        if type(release_policy) is not ReleasePolicy or type(artifact_bytes) is not dict:
            raise TypeError('exact internal Judge release policy and bytes required')
        self._release_policy=release_policy
        self._artifact_bytes=dict(artifact_bytes)

    @staticmethod
    def read_metadata(conn):
        from aos_api.aip_action_store import canonical_hash,AipActionTransitionBlocked
        obj=conn.execute('SELECT id,name,description,published,properties,required_markings FROM meta_object_type WHERE id=%s FOR SHARE',(OBJECT_ID,)).fetchone()
        row=conn.execute('SELECT id,name,object_type,parameters,required_markings,submission_criteria FROM meta_action_type WHERE id=%s FOR SHARE',(ACTION_ID,)).fetchone()
        if obj is None or dict(obj)!=_OBJECT or row is None:
            raise AipActionTransitionBlocked('JUDGE_ACTION_METADATA_REQUIRED')
        action={'id':row['id'],'name':row['name'],'objectType':row['object_type'],'parameters':row['parameters'],'requiredMarkings':row['required_markings'],'submissionCriteria':row['submission_criteria']}
        if action!=_ACTION:raise AipActionTransitionBlocked('JUDGE_ACTION_METADATA_DRIFTED')
        return {**action,'revisionHash':canonical_hash(action)}

    def _current(self,conn,scope,request_id,request_hash):
        from aos_api.aip_action_store import AipActionTransitionBlocked
        try:
            return ModelJudgeCallRequestStore().require_current_with_rule(conn,scope,request_id,request_hash,
                release_policy=self._release_policy,artifact_bytes=self._artifact_bytes)
        except (TypeError,ValueError,RuntimeError) as exc:
            raise AipActionTransitionBlocked('JUDGE_ACTION_CURRENT_RULE_SOURCE_REQUIRED') from exc

    @staticmethod
    def _proposal_fingerprint(row):
        return (row['proposal_id'],row['version'],row['proposal_hash'],row['payload'],
            row['action_type_snapshot'],row['created_by'],row['expires_at'])

    def prelock_decision(self,conn,scope,proposal_id):
        from aos_api.aip_action_store import AipActionTransitionBlocked
        row=conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*scope.key,proposal_id)).fetchone()
        if row is None or row['action_type_id']!=ACTION_ID or row['action_type_snapshot'].get('id')!=ACTION_ID or set(row['payload'])!={'requestId','requestHash'}:
            raise AipActionTransitionBlocked('JUDGE_DEDICATED_PROPOSAL_REQUIRED')
        self._current(conn,scope,row['payload']['requestId'],row['payload']['requestHash'])
        return self._proposal_fingerprint(row)

    def assert_prelocked_proposal(self,row,fingerprint):
        from aos_api.aip_action_store import AipActionTransitionBlocked
        if self._proposal_fingerprint(row)!=fingerprint:
            raise AipActionTransitionBlocked('JUDGE_PRELOCK_PROPOSAL_DRIFTED')

    def check_request(self,conn,scope,actor,body,action_snapshot,risk):
        from aos_api.aip_action_store import AipActionTransitionBlocked,canonical_hash
        from aos_api.aip_action_policy import classify_action_risk
        from aos_api.aip_contracts import ActionRiskLevel
        from aos_api.openfga import openfga_api_url
        if (body.action_type_id!=ACTION_ID or action_snapshot.get('id')!=ACTION_ID
            or body.purpose!='model-judge-call' or body.task_id is not None or body.run_id is not None
            or body.object_ref is not None or body.impact_preview_ref is not None or body.diff or body.evidence_refs
            or body.risk_hint is not None or openfga_api_url() or set(body.payload)!={'requestId','requestHash'}):
            raise AipActionTransitionBlocked('JUDGE_ACTION_PROPOSAL_SHAPE_REQUIRED')
        current=self._current(conn,scope,body.payload['requestId'],body.payload['requestHash'])
        if action_snapshot!=self.read_metadata(conn):raise AipActionTransitionBlocked('JUDGE_ACTION_METADATA_DRIFTED')
        expected=classify_action_risk(ACTION_ID,action_snapshot,body.payload,None)
        if (risk!=expected or risk.level is not ActionRiskLevel.R2 or risk.approval_policy.get('makerChecker') is not True
            or risk.approval_policy.get('executionAllowed') is not False or risk.approval_policy.get('draftOnly') is not False):
            raise AipActionTransitionBlocked('JUDGE_ACTION_INDEPENDENT_POLICY_REQUIRED')
        if actor!=current['created_by'] or body.effective_expiry()>current['expires_at']:
            raise AipActionTransitionBlocked('JUDGE_ACTION_MAKER_OR_EXPIRY_DRIFTED')
        ModelEvalActionGuard._role(conn,scope,actor)
        self._current(conn,scope,body.payload['requestId'],body.payload['requestHash'])
        return canonical_hash({'requestId':body.payload['requestId'],'requestHash':body.payload['requestHash'],
            'actionTypeRevisionHash':action_snapshot['revisionHash']})

    def check_proposal(self,conn,scope,actor,row,*,checker):
        from aos_api.aip_action_store import AipActionTransitionBlocked,canonical_hash
        from aos_api.aip_action_models import CreateActionProposalRequest
        from aos_api.aip_action_policy import classify_action_risk
        if (row['action_type_id']!=ACTION_ID or row['action_type_snapshot'].get('id')!=ACTION_ID
            or row['task_id'] is not None or row['run_id'] is not None or row['object_ref'] is not None
            or row['impact_preview_id'] is not None or row['diff']!={} or row['evidence_refs']!=[] or row['client_risk_hint'] is not None):
            raise AipActionTransitionBlocked('JUDGE_ACTION_PROPOSAL_DRIFTED')
        body=CreateActionProposalRequest(actionTypeId=ACTION_ID,purpose=row['purpose'],payload=row['payload'],expiresAt=row['expires_at'])
        risk=classify_action_risk(ACTION_ID,row['action_type_snapshot'],row['payload'],None)
        policy={'floor':risk.floor.value,'reasons':list(risk.reasons),**risk.approval_policy}
        binding=self.check_request(conn,scope,row['created_by'],body,row['action_type_snapshot'],risk)
        if row['risk_level']!=risk.level.value or row['policy_snapshot']!=policy or row['approval_policy_hash']!=canonical_hash(policy) or row['action_binding_hash']!=binding:
            raise AipActionTransitionBlocked('JUDGE_ACTION_BINDING_DRIFTED')
        draft=conn.execute('SELECT snapshot FROM aip_action_draft WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*scope.key,row['proposal_id'])).fetchone()
        stable=draft['snapshot'] if draft else None
        if (not isinstance(stable,dict) or canonical_hash(stable)!=row['proposal_hash'] or stable.get('actionBindingHash')!=binding
            or stable.get('actionType')!=row['action_type_snapshot'] or stable.get('payload')!=row['payload'] or stable.get('policy')!=policy):
            raise AipActionTransitionBlocked('JUDGE_ACTION_DRAFT_DRIFTED')
        if not checker:
            if actor!=row['created_by']:raise AipActionTransitionBlocked('JUDGE_REPLAY_MAKER_REQUIRED')
            return None
        if actor==row['created_by']:raise AipActionTransitionBlocked('JUDGE_INDEPENDENT_CHECKER_REQUIRED')
        roles=(ModelEvalActionGuard._role(conn,scope,actor),)
        self._current(conn,scope,row['payload']['requestId'],row['payload']['requestHash'])
        return roles

    def require_current_approval(self,conn,scope,request_id,request_hash,approval_event_id):
        """Current original new-purpose approval facts on the budget caller.

        Reacquire Registry/source locks before the new proposal row. This
        creates no hold or Intent and cannot authorize transport or survive a
        caller transaction boundary as a current admission certificate.
        """
        import psycopg
        from psycopg.pq import TransactionStatus
        from psycopg.rows import dict_row
        from aos_api.aip_action_store import AipActionTransitionBlocked,canonical_hash
        from aos_api.aip_budget_reservation_store import canonical_hash as budget_hash
        if (type(conn) is not psycopg.Connection or type(scope) is not TenantScope
            or scope.key!=('org-org','dev-project')
            or conn.info.transaction_status!=TransactionStatus.INTRANS
            or conn.row_factory is not dict_row):
            raise AipActionTransitionBlocked('JUDGE_APPROVAL_NATIVE_CALLER_REQUIRED')
        identity=conn.execute("""SELECT current_user AS role,
            current_setting('aos.org_id',true) AS org,
            current_setting('aos.project_id',true) AS project,
            current_setting('transaction_isolation') AS isolation,
            pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid""").fetchone()
        if (identity['role'],identity['org'],identity['project'],identity['isolation'])!=('aos_runtime',*scope.key,'serializable'):
            raise AipActionTransitionBlocked('JUDGE_APPROVAL_NATIVE_CALLER_REQUIRED')
        if (any(type(v) is not str or not 1<=len(v)<=200 or v.strip()!=v for v in (request_id,approval_event_id))
            or type(request_hash) is not str or len(request_hash)!=64
            or any(c not in '0123456789abcdef' for c in request_hash)):
            raise AipActionTransitionBlocked('JUDGE_APPROVAL_EXACT_IDENTITY_REQUIRED')
        approval=conn.execute('SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
            (*scope.key,approval_event_id)).fetchone()
        if approval is None or approval['decision']!='approved':
            raise AipActionTransitionBlocked('JUDGE_DEDICATED_APPROVAL_REQUIRED')
        fingerprint=self.prelock_decision(conn,scope,approval['proposal_id'])
        row=conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE',
            (*scope.key,approval['proposal_id'])).fetchone()
        if row is None:raise AipActionTransitionBlocked('JUDGE_DEDICATED_APPROVAL_REQUIRED')
        self.assert_prelocked_proposal(row,fingerprint)
        if (row['status']!='approved' or row['purpose']!='model-judge-call'
            or row['payload']!={'requestId':request_id,'requestHash':request_hash}
            or approval['proposal_hash']!=row['proposal_hash']
            or approval['proposal_version']!=row['version']-1
            or approval['action_binding_hash']!=row['action_binding_hash']
            or approval['approval_policy_hash']!=row['approval_policy_hash']
            or approval['slot_id']!='checker.1'):
            raise AipActionTransitionBlocked('JUDGE_APPROVAL_BINDING_DRIFTED')
        roles=self.check_proposal(conn,scope,approval['actor_id'],row,checker=True)
        eligibility={'tenant':{'orgId':scope.org_id,'projectId':scope.project_id},
            'actorId':approval['actor_id'],'roles':sorted(r.lower() for r in roles),
            'slotId':approval['slot_id'],'approvalPolicyHash':row['approval_policy_hash']}
        if approval['eligibility_snapshot_hash']!=canonical_hash(eligibility):
            raise AipActionTransitionBlocked('JUDGE_APPROVAL_ELIGIBILITY_DRIFTED')
        events=conn.execute("SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s AND decision='approved'",
            (*scope.key,row['proposal_id'])).fetchall()
        if len(events)!=1 or dict(events[0])!=dict(approval):
            raise AipActionTransitionBlocked('JUDGE_UNIQUE_APPROVAL_REQUIRED')
        current=self._current(conn,scope,request_id,request_hash)
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if (approval['expires_at'] is None or approval['expires_at']<=now
            or row['expires_at']<=now or current['expires_at']<=now):
            raise AipActionTransitionBlocked('JUDGE_CURRENT_APPROVAL_REQUIRED')
        # Preserve the original Model parent approval reference projection.
        # Policy/binding/eligibility are additionally verified and recorded.
        projection={key:approval[key] for key in ('approval_event_id','proposal_id','proposal_version','proposal_hash',
            'decision','actor_id','reason','expires_at','created_at','action_binding_hash')}
        payload=current['request_json'];judge=payload['judgeGovernanceApplication']['request']
        facts={'schemaVersion':'aos.model-judge-approved-source-facts/v1',
            'tenant':payload['tenant'],'purpose':'model-judge-call',
            'requestId':request_id,'requestHash':request_hash,
            'request':payload,'approvalEventId':approval_event_id,
            'approvalRef':{'resourceType':'ActionApprovalEvent','resourceId':approval_event_id,
                'revision':approval['proposal_version'],'contentHash':budget_hash(projection,prefixed=True)},
            'proposalId':row['proposal_id'],'proposalHash':row['proposal_hash'],
            'actionBindingHash':row['action_binding_hash'],'approvalPolicyHash':row['approval_policy_hash'],
            'eligibilitySnapshotHash':approval['eligibility_snapshot_hash'],
            'maker':row['created_by'],'checker':approval['actor_id'],
            'providerRef':judge['providerRef'],'modelRef':judge['sourceRef'],
            'priceRef':judge['priceRef'],'quotaPolicyRef':judge['quotaPolicyRef'],'budgetPolicyRef':judge['budgetPolicyRef'],
            'upperBoundMinor':payload['upperBoundMinor'],'currency':payload['currency'],
            'approvalExpiresAt':approval['expires_at'].isoformat(),'checkedAt':now.isoformat(),
            'callerXid':identity['xid'],'callerPid':identity['pid'],
            'approvalVerified':True,'executionAllowed':False,'budgetHoldCreated':False}
        return {**facts,'sourceFactsHash':canonical_hash(facts)}


def _judge_action_identity(principal,key):
    from aos_api.aip_action_store import AipActionTransitionBlocked
    if type(principal) is not Principal or principal.token_kind!='oidc' or type(key) is not str or not key or key.strip()!=key or len(key)>200:
        raise AipActionTransitionBlocked('JUDGE_OIDC_ACTION_IDENTITY_REQUIRED')
    return TenantScope(principal.org_id,principal.project_id)


def propose_model_judge_request(principal,request_id,idempotency_key,expires_at,*,release_policy,artifact_bytes,connect_factory=None):
    from datetime import datetime
    from aos_api.db import connect_serializable
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
    from aos_api.aip_action_models import CreateActionProposalRequest
    from aos_api.aip_action_policy import classify_action_risk
    scope=_judge_action_identity(principal,idempotency_key)
    if type(request_id) is not str or not request_id or request_id.strip()!=request_id or type(expires_at) is not datetime or expires_at.utcoffset() is None:
        raise AipActionTransitionBlocked('JUDGE_ACTION_INPUT_REQUIRED')
    guard=ModelJudgeCallActionGuard(release_policy=release_policy,artifact_bytes=artifact_bytes);factory=connect_factory or connect_serializable
    with factory(scope) as conn:
        row=conn.execute('SELECT request_hash FROM aip_model_eval_judge_request WHERE org_id=%s AND project_id=%s AND request_id=%s',(*scope.key,request_id)).fetchone()
        if row is None:raise AipActionTransitionBlocked('JUDGE_CURRENT_REQUEST_REQUIRED')
        guard._current(conn,scope,request_id,row['request_hash'])
        snapshot=guard.read_metadata(conn)
    payload={'requestId':request_id,'requestHash':row['request_hash']}
    body=CreateActionProposalRequest(actionTypeId=ACTION_ID,purpose='model-judge-call',payload=payload,expiresAt=expires_at)
    return AipActionStore(factory,model_judge_guard=guard).create_proposal(scope,principal.subject,idempotency_key,body,snapshot,classify_action_risk(ACTION_ID,snapshot,payload,None))


def decide_model_judge_request(principal,proposal_id,idempotency_key,body,*,release_policy,artifact_bytes,connect_factory=None):
    from aos_api.db import connect_serializable
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
    from aos_api.aip_action_models import DecideActionProposalRequest
    scope=_judge_action_identity(principal,idempotency_key)
    if type(proposal_id) is not str or not proposal_id or proposal_id.strip()!=proposal_id or type(body) is not DecideActionProposalRequest:
        raise AipActionTransitionBlocked('JUDGE_DECISION_INPUT_REQUIRED')
    guard=ModelJudgeCallActionGuard(release_policy=release_policy,artifact_bytes=artifact_bytes)
    return AipActionStore(connect_factory or connect_serializable,model_judge_guard=guard).decide(scope,principal.subject,proposal_id,idempotency_key,body)

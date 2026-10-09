def test_exact_signed_rule_new_original_suite(
    caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path,
    *, source_provider=None,whole_caller_factory=None,source_prefix=None,source_probe=None,
    source_finish=None,source_native_only=False,
):
    import os
    from aos_api.db import connect,connect_serializable,get_dsn
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.asset_registry.signature import FrozenTrustRootProvider
    from aos_api.aip_action_store import canonical_hash
    from aos_api.aip_eval_contracts import JudgeRevisionRef,AssetRevisionRef,AssetType
    from aos_api.aip_model_eval_judge_request_store import ModelJudgeCallRequestStore
    repo=Path(__file__).resolve().parents[4];base,evidence=_judge_fixture_evidence_paths()
    for name in ('legal_model_prefix_for_application_r4','legal_eval_application_fixture_r4'):
        spec=importlib.util.spec_from_file_location(name,base/(name+'.py'))
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    create=sys.modules['legal_eval_application_fixture_r4'].create_application
    scope=TenantScope('org-org','dev-project');judge_path=tmp_path/'governance';judge_path.mkdir()
    create(caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,judge_path,source_provider=source_provider)
    judge=json.loads((base/'legal-eval-application-result-r4.json').read_text())
    with connect(scope) as conn:
        request=conn.execute('SELECT request_json FROM aip_model_eval_request WHERE request_id=%s',(judge['request_id'],)).fetchone()['request_json']
    source,files,rule,root,service,scope,publisher,bundle_id=_publish_original_signed_judge_rule(tmp_path/'rules',request['sourceRef'],root_lifetime=timedelta(minutes=3))
    policy=ReleasePolicy(trust_roots=FrozenTrustRootProvider({(root.publisher,root.key_id):root}))
    with connect_serializable(scope) as conn:
        facts=ModelJudgeCallRequestStore().read_published_rule(conn,scope,source,release_policy=policy,artifact_bytes=files)
    exact=request['sourceRef']
    route=AssetRevisionRef(asset_type=AssetType.REGISTERED_MODEL,asset_id=exact['assetId'],revision=str(exact['revision']),content_hash=exact['contentHash'])
    ref=JudgeRevisionRef(judge_id=rule['judgeId'],revision=rule['revision'],content_hash=facts['ruleHash'],model_route=route)
    model=AipModelRuntimeStore().get_model(scope,judge['model_id'])
    provider=AipModelRuntimeStore().get_provider(scope,model.provider.asset_id,model.provider.revision)
    target_path=tmp_path/'target';target_path.mkdir()
    # Actual signed publish and approved Judge Model precede fixture RED.
    create(caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,target_path,
           source_provider=provider,suite_case_copies=2,judge_model_ref=exact,judge_rule_ref=ref.model_dump(mode='json',by_alias=True))
    target=json.loads((base/'legal-eval-application-result-r4.json').read_text())
    with connect(scope) as conn:
        target_request=conn.execute('SELECT request_json,request_hash FROM aip_model_eval_request WHERE request_id=%s',(target['request_id'],)).fetchone()
        sr=target_request['request_json']['suiteRef']
        suite=conn.execute('SELECT * FROM aip_eval_suite_revision WHERE suite_id=%s AND revision=%s',(sr['assetId'],sr['revision'])).fetchone()
        assert suite['judge_ref']==ref.model_dump(mode='json',by_alias=True)
        assert len(suite['cases'])==2
        assert canonical_hash(target_request['request_json'])==target_request['request_hash']==target['request_hash']
        approval=conn.execute("SELECT * FROM aip_action_approval_event WHERE proposal_id=%s AND decision='approved'",(target['proposal_id'],)).fetchone()
        assert approval['actor_id']!=target['maker']
    # Original signed rule, new full Suite and both immutable approvals precede
    # the mandatory-source producer RED. No old request is upgraded in place.
    with connect(scope) as conn:
        ids=[conn.execute("SELECT approval_event_id FROM aip_action_approval_event WHERE proposal_id=%s AND decision='approved'",(app['proposal_id'],)).fetchone()['approval_event_id'] for app in (target,judge)]
    from aos_api.aip_model_eval_judge_authorization import ModelJudgeCallRuleRequestInput
    from aos_api.aip_model_eval_judge_authority import judge_request_statements
    from aos_api.auth import resolve_principal
    from aos_api.aip_model_eval_judge_action import ModelJudgeCallSourceGuard
    from aos_api.aip_model_eval_judge_request_store import ModelJudgeRequestRejected
    with psycopg.connect(get_dsn()) as install:
        if install.execute("SELECT to_regclass('public.aip_model_eval_judge_request')").fetchone()[0] is None:
            for statement in judge_request_statements():install.execute(statement)
    maker=resolve_principal(token=https_signer[0](target['maker']),header_org=scope.org_id,header_project=scope.project_id)
    checker=resolve_principal(token=https_signer[0](target['checker']),header_org=scope.org_id,header_project=scope.project_id)
    body=ModelJudgeCallRuleRequestInput(targetRequestId=target['request_id'],targetRequestHash=target['request_hash'],
        targetApprovalEventId=ids[0],judgeRequestId=judge['request_id'],judgeRequestHash=judge['request_hash'],
        judgeApprovalEventId=ids[1],ruleSource=source,upperBoundMinor=20,expiresAt=datetime.now(UTC)+timedelta(minutes=2))
    from uuid import uuid4
    attempt_suffix=uuid4().hex
    request_key='exact-rule-v2-'+attempt_suffix
    proposal_key='judge-call-proposal-v2-'+attempt_suffix
    decision_key='judge-call-checker-v2-'+attempt_suffix
    store=ModelJudgeCallRequestStore()
    with connect_serializable(scope) as conn:
        pending=store.create_with_rule(conn,maker,request_key,body,release_policy=policy,artifact_bytes=files)
        assert store.create_with_rule(conn,maker,request_key,body,release_policy=policy,artifact_bytes=files)==pending
    with connect_serializable(scope) as conn:
        checked=ModelJudgeCallSourceGuard().require_rule_pending_for_checker(conn,checker,pending['request_id'],pending['request_hash'],release_policy=policy,artifact_bytes=files)
        assert checked['ruleHash']==facts['ruleHash'] and checked['approvalAllowed'] is False and checked['executionAllowed'] is False
        for wrong_bytes in ({**files,'template.txt':b'changed'}, {**files,'extra.txt':b'extra'}):
            with pytest.raises(ModelJudgeRequestRejected):
                store.require_current_with_rule(conn,scope,pending['request_id'],pending['request_hash'],release_policy=policy,artifact_bytes=wrong_bytes)
        with pytest.raises(ModelJudgeRequestRejected,match='INDEPENDENT'):
            ModelJudgeCallSourceGuard().require_rule_pending_for_checker(conn,maker,pending['request_id'],pending['request_hash'],release_policy=policy,artifact_bytes=files)
        forged=dict(pending['request_json']);forged['cases']=forged['cases'][:1];forged['caseSetHash']=canonical_hash(forged['cases'])
        with conn.transaction(force_rollback=True):
            fake=conn.execute("""INSERT INTO aip_model_eval_judge_request(org_id,project_id,request_id,idempotency_key,request_hash,request_json,created_by,expires_at)
                VALUES(%s,%s,'forged-v2','forged-v2',%s,%s::jsonb,%s,%s) RETURNING request_id,request_hash""",(*scope.key,canonical_hash(forged),json.dumps(forged),pending['created_by'],pending['expires_at'])).fetchone()
            with pytest.raises(ModelJudgeRequestRejected,match='REDERIVATION'):
                store.require_current_with_rule(conn,scope,fake['request_id'],fake['request_hash'],release_policy=policy,artifact_bytes=files)
    # A separately genuine signed/published rule is not this Suite's rule.
    other_source,other_files,_,other_root,_,_,_,_=_publish_original_signed_judge_rule(tmp_path/'other-rule',exact)
    other_policy=ReleasePolicy(trust_roots=FrozenTrustRootProvider({(other_root.publisher,other_root.key_id):other_root}))
    with connect_serializable(scope) as conn:
        with pytest.raises(ModelJudgeRequestRejected,match='RULE_SUITE_MODEL_BINDING'):
            store.create_with_rule(conn,maker,'unrelated-rule-v2',body.model_copy(update={'rule_source':other_source}),release_policy=other_policy,artifact_bytes=other_files)
    from dataclasses import replace
    with connect_serializable(scope) as conn:
        with pytest.raises(ModelJudgeRequestRejected,match='RULE_REQUEST_WINDOW'):
            store.create_with_rule(conn,maker,'extended-window-v2',body.model_copy(update={'expires_at':datetime.now(UTC)+timedelta(minutes=4)}),release_policy=policy,artifact_bytes=files)
    revoked_policy=ReleasePolicy(trust_roots=FrozenTrustRootProvider({(root.publisher,root.key_id):replace(root,revoked_at=datetime.now(UTC))}))
    with connect_serializable(scope) as conn:
        with pytest.raises(ModelJudgeRequestRejected,match='PUBLISHED_RULE_AUTHORITY'):
            store.require_current_with_rule(conn,scope,pending['request_id'],pending['request_hash'],release_policy=revoked_policy,artifact_bytes=files)
        with pytest.raises(ModelJudgeRequestRejected,match='IDEMPOTENCY'):
            store.create_with_rule(conn,maker,request_key,body.model_copy(update={'upper_bound_minor':21}),release_policy=policy,artifact_bytes=files)
    with connect_serializable(scope) as conn:
        for drift in [source.model_copy(update={'content_hash':'sha256:'+'f'*64}), source.model_copy(update={'version':'9.0.0'})]:
            with pytest.raises(ModelJudgeRequestRejected):
                store.create_with_rule(conn,maker,'drift-v2',body.model_copy(update={'rule_source':drift}),release_policy=policy,artifact_bytes=files)
    with connect_serializable(TenantScope('dev-org','dev-project')) as conn:
        with pytest.raises(ModelJudgeRequestRejected,match='CALLER'):
            store.require_current_with_rule(conn,TenantScope('dev-org','dev-project'),pending['request_id'],pending['request_hash'],release_policy=policy,artifact_bytes=files)
    # Independent new-purpose approval, not either original quality approval.
    from aos_api.aip_model_eval_judge_authority import judge_action_metadata_statements
    from aos_api.aip_model_eval_judge_action import propose_model_judge_request,decide_model_judge_request
    from aos_api.aip_action_models import DecideActionProposalRequest,CreateActionProposalRequest
    from aos_api.aip_action_policy import classify_action_risk
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
    with psycopg.connect(get_dsn()) as install:
        for statement in judge_action_metadata_statements():install.execute(statement)
    expires=datetime.now(UTC)+timedelta(seconds=110)
    proposed=propose_model_judge_request(maker,pending['request_id'],proposal_key,expires,
        release_policy=policy,artifact_bytes=files,connect_factory=connect_serializable)
    with connect(scope) as read:
        proposed_row=read.execute('SELECT * FROM aip_action_proposal WHERE proposal_id=%s',(proposed.proposal.id,)).fetchone()
    decision=DecideActionProposalRequest(decision='approved',expectedProposalVersion=proposed_row['version'],expectedProposalHash=proposed_row['proposal_hash'])
    with pytest.raises(AipActionTransitionBlocked):
        decide_model_judge_request(maker,proposed_row['proposal_id'],'judge-call-self',decision,release_policy=policy,artifact_bytes=files,connect_factory=connect_serializable)
    from contextlib import contextmanager
    approval_started=threading.Event();approval_identity={};approval_results=[]
    @contextmanager
    def observed_approval_factory(tenant):
        with connect_serializable(tenant) as approval_conn:
            approval_identity.update(approval_conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone())
            approval_started.set()
            yield approval_conn
    def approve_after_registry_wait():
        try:
            approval_results.append(decide_model_judge_request(checker,proposed_row['proposal_id'],decision_key,decision,
                release_policy=policy,artifact_bytes=files,connect_factory=observed_approval_factory))
        except BaseException as exc:
            approval_results.append(exc)
    observed_approval_wait=None;proposal_free_before_registry=False
    approval_thread=threading.Thread(target=approve_after_registry_wait)
    try:
        with psycopg.connect(get_dsn()) as blocker:
            blocker.execute('SELECT pg_advisory_xact_lock(228,1)')
            approval_thread.start()
            assert approval_started.wait(5)
            for _ in range(100):
                blocker.execute('SELECT pg_stat_clear_snapshot()')
                observed_approval_wait=blocker.execute("SELECT pid,wait_event_type,wait_event FROM pg_stat_activity WHERE pid=%s AND wait_event_type='Lock' AND query LIKE '%%pg_advisory_xact_lock(228,1)%%'",(approval_identity['pid'],)).fetchone()
                if observed_approval_wait:break
                time.sleep(.02)
            assert observed_approval_wait, approval_results
            with connect(scope) as probe:
                unlocked=probe.execute('SELECT proposal_id FROM aip_action_proposal WHERE proposal_id=%s FOR UPDATE NOWAIT',(proposed_row['proposal_id'],)).fetchone()
                proposal_free_before_registry=unlocked['proposal_id']==proposed_row['proposal_id']
                probe.rollback()
            blocker.commit()
    finally:
        if approval_thread.ident is not None:approval_thread.join(15)
    assert not approval_thread.is_alive() and proposal_free_before_registry
    assert len(approval_results)==1 and not isinstance(approval_results[0],BaseException), approval_results
    approved=approval_results[0]
    replay=decide_model_judge_request(checker,proposed_row['proposal_id'],decision_key,decision,
        release_policy=policy,artifact_bytes=files,connect_factory=connect_serializable)
    assert approved.proposal.status==replay.proposal.status
    other_checker=resolve_principal(token=https_signer[0](judge['checker']),header_org=scope.org_id,header_project=scope.project_id)
    with pytest.raises(AipActionTransitionBlocked,match='REPLAY'):
        decide_model_judge_request(other_checker,proposed_row['proposal_id'],decision_key,decision,
            release_policy=policy,artifact_bytes=files,connect_factory=connect_serializable)
    with pytest.raises(AipActionTransitionBlocked):
        decide_model_judge_request(checker,proposed_row['proposal_id'],'revoked-checker-v2',decision,
            release_policy=revoked_policy,artifact_bytes=files,connect_factory=connect_serializable)
    with connect(scope) as read:
        action_row=read.execute('SELECT * FROM aip_action_proposal WHERE proposal_id=%s',(proposed_row['proposal_id'],)).fetchone()
        new_approval=read.execute("SELECT * FROM aip_action_approval_event WHERE proposal_id=%s AND decision='approved'",(proposed_row['proposal_id'],)).fetchone()
        assert action_row['purpose']=='model-judge-call' and action_row['policy_snapshot']['executionAllowed'] is False
        assert new_approval['actor_id']==checker.subject!=action_row['created_by']
        assert new_approval['approval_event_id'] not in ids
        assert new_approval['action_binding_hash']==action_row['action_binding_hash']
        assert read.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=ANY(%s)',([target['request_id'],judge['request_id']],)).fetchone()['n']==0
    from aos_api.aip_model_eval_judge_action import ModelJudgeCallActionGuard
    action_guard=ModelJudgeCallActionGuard(release_policy=policy,artifact_bytes=files)
    # Fee policy still requires its original exact ten-minor per-call risk.
    # Preserve the twenty-minor approval as a negative, create a distinct
    # ten-minor new-purpose application and independently approve it.
    from aos_api.aip_model_eval_judge_budget import ModelJudgeBudgetStore
    from aos_api.aip_budget_cost_runtime import shared_risk_totals
    from aos_api.aip_budget_reservation_store import BudgetReservationBlocked
    judge_budget=ModelJudgeBudgetStore(release_policy=policy,artifact_bytes=files)
    with connect_serializable(scope) as denied_hold:
        with pytest.raises(BudgetReservationBlocked,match="CURRENT_RISK"):
            judge_budget.hold(denied_hold,scope,pending['request_id'],pending['request_hash'],new_approval['approval_event_id'])
        denied_hold.rollback()
    budget_body=ModelJudgeCallRuleRequestInput.model_validate({**body.model_dump(mode='json',by_alias=True),'upperBoundMinor':10})
    with connect_serializable(scope) as budget_create:
        budget_pending=store.create_with_rule(budget_create,maker,'judge-budget-request-'+attempt_suffix,budget_body,release_policy=policy,artifact_bytes=files)
    budget_proposal=propose_model_judge_request(maker,budget_pending['request_id'],'judge-budget-proposal-'+attempt_suffix,expires,
        release_policy=policy,artifact_bytes=files,connect_factory=connect_serializable)
    with connect(scope) as read:
        bp=read.execute('SELECT * FROM aip_action_proposal WHERE proposal_id=%s',(budget_proposal.proposal.id,)).fetchone()
    decide_model_judge_request(checker,bp['proposal_id'],'judge-budget-checker-'+attempt_suffix,
        DecideActionProposalRequest(decision='approved',expectedProposalVersion=bp['version'],expectedProposalHash=bp['proposal_hash']),
        release_policy=policy,artifact_bytes=files,connect_factory=connect_serializable)
    with connect(scope) as read:
        be=read.execute("SELECT * FROM aip_action_approval_event WHERE proposal_id=%s AND decision='approved'",(bp['proposal_id'],)).fetchone()
    from aos_api.aip_model_eval_execution_owner import ModelEvalExecutionOwner, ModelEvalOwnerRejected
    assert hasattr(ModelEvalExecutionOwner, '_prepare_dual_purpose_bucket_fences'), 'global Target/newJudge original bucket prefix missing'
    assert hasattr(ModelEvalExecutionOwner, 'validate_original_target_judge_manifest'), 'whole new-purpose Manifest original native consumer missing'
    with (whole_caller_factory or connect_serializable)(scope) as hold_conn:
        hold_rollback_identity=hold_conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        native_owner=ModelEvalExecutionOwner()
        spec=importlib.util.spec_from_file_location('whole_native_plan_missing_1602',base/'build_whole_native_plan_1602.py')
        missing_builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(missing_builder)
        missing_plan=missing_builder.missing_parent_description(budget_pending,be['approval_event_id'])
        before_missing_buckets=hold_conn.execute('SELECT count(*) AS n FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']
        with hold_conn.transaction(force_rollback=True):
            with pytest.raises(ModelEvalOwnerRejected):
                native_owner.validate_original_target_judge_manifest(hold_conn,scope,missing_plan,release_policy=policy,artifact_bytes=files)
            after_missing_buckets=hold_conn.execute('SELECT count(*) AS n FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s',scope.key).fetchone()['n']
            assert after_missing_buckets==before_missing_buckets,'whole reader must reject absent parents before preparing any bucket'
        if source_prefix is not None:source_prefix(hold_conn)
        native_owner._prepare_dual_purpose_bucket_fences(hold_conn,scope,budget_pending['request_id'],be['approval_event_id'],release_policy=policy,artifact_bytes=files)
        from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore
        native_target_hold=AipModelEvalBudgetReservationStore().hold(hold_conn,scope,target['request_id'],ids[0])
        held=judge_budget.hold(hold_conn,scope,budget_pending['request_id'],budget_pending['request_hash'],be['approval_event_id'])
        replayed_hold=judge_budget.hold(hold_conn,scope,budget_pending['request_id'],budget_pending['request_hash'],be['approval_event_id'])
        assert str(held['reservation_id'])==str(replayed_hold['reservation_id'])
        assert held['purpose']=='model-judge-call' and held['upper_bound_minor']==10
        buckets=hold_conn.execute('SELECT * FROM aip_model_judge_budget_reservation_bucket WHERE org_id=%s AND project_id=%s AND reservation_id=%s',(*scope.key,held['reservation_id'])).fetchall()
        assert len(buckets)==3 and all(b['reserved_minor']==10 for b in buckets)
        assert next(b for b in buckets if b['bucket_kind']=='task')['account_id']=='model-judge/'+budget_pending['request_id']
        native_target=native_owner.prepare_model_application(hold_conn,scope,target['request_id'],ids[0])
        native_judge=native_owner.prepare_judge_application(hold_conn,scope,budget_pending['request_id'],be['approval_event_id'],release_policy=policy,artifact_bytes=files)
        spec=importlib.util.spec_from_file_location('whole_native_plan_1602',base/'build_whole_native_plan_1602.py')
        whole_builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(whole_builder)
        native_body=whole_builder.build(native_target,native_judge)
        source_trial=None if source_probe is None else source_probe(hold_conn,native_body,native_target,native_judge)
        assert native_owner.validate_original_target_judge_manifest(hold_conn,scope,native_body,release_policy=policy,artifact_bytes=files) is None
        if os.environ.get('AOS_JUDGE_EXPECTED_BYTES_PROBE') == '1':
            import hashlib
            assert hasattr(native_owner, 'validate_original_judge_expected_bytes'), 'original Judge expected byte gate missing'
            raw = '  原Judge期望🙂\n保留空白  '.encode('utf-8')
            expected = tuple((case['caseId'], raw if case['expectedHash'] is not None else None)
                             for case in native_body['cases'])
            assert all(case['expectedHash'] is None or case['expectedHash'] == hashlib.sha256(raw).hexdigest()
                       for case in native_body['cases'])
            native_owner.validate_original_judge_expected_bytes(hold_conn, scope, native_body,
                expected=expected, release_policy=policy, artifact_bytes=files)
            faults = {'cropped': expected[:1], 'duplicate': (expected[0], expected[0]),
                'reordered': tuple(reversed(expected)), 'list': list(expected),
                'missing': ((expected[0][0], None if expected[0][1] is not None else b''), expected[1]),
                'mutable': ((expected[0][0], bytearray(raw)), expected[1]),
                'wrong': ((expected[0][0], b'wrong'), expected[1]),
                'trailing': ((expected[0][0], raw + b' '), expected[1]),
                'oversized': ((expected[0][0], b'x' * 1048577), expected[1]),
                'extra': expected + (('extra-case', raw),)}
            for fault, value in faults.items():
                with pytest.raises(ModelEvalOwnerRejected):
                    native_owner.validate_original_judge_expected_bytes(hold_conn, scope, native_body,
                        expected=value, release_policy=policy, artifact_bytes=files)
            (evidence/(os.environ['AOS_JUDGE_NATIVE_EVIDENCE_LABEL']+'-expected-bytes.json')).write_text(json.dumps({
                'caller':hold_rollback_identity,'cases':[{'caseId':k,'sha256':None if v is None else hashlib.sha256(v).hexdigest(),
                    'bytesLength':None if v is None else len(v)} for k,v in expected],
                'faults_rejected':list(faults),'execution_allowed':False},indent=2))
        native_negatives=[]
        for fault in ('request_body','judge_parent_hash','target_parent_hash','revoked_rule','canary'):
            wrong=json.loads(json.dumps(native_body))
            if fault=='request_body':
                wrong['judgeRequest']['createdBy']+='-forged'
                wrong['judgeRequestHash']=canonical_hash(wrong['judgeRequest'])
                wrong['judgeParentBudget']['requestHash']=wrong['judgeRequestHash']
            elif fault in ('judge_parent_hash','target_parent_hash'):
                purpose='judge' if fault.startswith('judge') else 'target'
                key=purpose+'ParentBudget';wrong[key]['parentHoldRef']['contentHash']='sha256:'+'0'*64
                for c in wrong['cases']:c[purpose]['budgetHoldRef']['contentHash']='sha256:'+'0'*64
            with hold_conn.transaction(force_rollback=True):
                with pytest.raises(ModelEvalOwnerRejected):
                    native_owner.validate_original_target_judge_manifest(hold_conn,
                        TenantScope('dev-org','dev-project') if fault=='canary' else scope,wrong,
                        release_policy=revoked_policy if fault=='revoked_rule' else policy,artifact_bytes=files)
            native_negatives.append(fault)
        native_final=hold_conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid,clock_timestamp() AS now').fetchone()
        assert (native_final['xid'],native_final['pid'])==(hold_rollback_identity['xid'],hold_rollback_identity['pid'])
        assert native_target.parent_row_xmin==native_judge.parent_row_xmin==native_final['xid']
        native_whole_proof={'caller':hold_rollback_identity,'checkedAt':native_final['now'].isoformat(),
            'target_parent_xmin':native_target.parent_row_xmin,'judge_parent_xmin':native_judge.parent_row_xmin,
            'target_parent_id':str(native_target_hold['reservation_id']),'judge_parent_id':str(held['reservation_id']),
            'manifest':native_body,'negative_cases':native_negatives,'execution_allowed':False,
            'missing_parent_denied_no_bucket_write':after_missing_buckets==before_missing_buckets,
            'limitations':'necessary original rows only; Source/account/allocation/Intent/joint/executor refs remain descriptive'}
        if source_trial is not None:
            native_whole_proof['source_newjudge_allocation']=source_trial
            native_whole_proof['limitations']='actual Source/account refs and prepared newJudge debit; full four-leg allocation/Intent/joint/executor refs remain descriptive'
        counted=shared_risk_totals(hold_conn,scope,held['budget_revision_ref']['resourceId'])
        assert counted==(1,10)
        if source_finish is not None:native_whole_proof['source_commit_denial']=source_finish(hold_conn)
        hold_conn.rollback()
    with connect(scope) as rollback_read:
        assert rollback_read.execute('SELECT count(*) AS n FROM aip_model_judge_budget_reservation WHERE request_id=%s',(budget_pending['request_id'],)).fetchone()['n']==0
        assert rollback_read.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=%s',(target['request_id'],)).fetchone()['n']==0
        native_whole_proof['dual_parent_rollback_zero']=True
    with psycopg.connect(get_dsn()) as native_independent:
        native_independent.execute('SET TRANSACTION READ ONLY')
        assert native_independent.execute('SELECT pg_xact_status(%s::xid8)',(hold_rollback_identity['xid'],)).fetchone()[0]=='aborted'
        native_whole_proof['independent_xact_status']='aborted'
    native_label=os.environ.get('AOS_JUDGE_NATIVE_EVIDENCE_LABEL','whole-manifest-native-current')
    (evidence/(native_label+'-whole-plan-proof.json')).write_text(json.dumps(native_whole_proof,default=str,indent=2)+'\n')
    if source_native_only:
        assert source_trial is not None and source_finish is not None
        return
    # The returned hold is not proof of COMMIT: independently read it after
    # the actual caller context commits, then keep it as an open obligation.
    with connect_serializable(scope) as committing_hold:
        committed_hold=judge_budget.hold(committing_hold,scope,budget_pending['request_id'],budget_pending['request_hash'],be['approval_event_id'])
        hold_identity=committing_hold.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
    with connect(scope) as independent_hold_read:
        readback_hold=independent_hold_read.execute('SELECT * FROM aip_model_judge_budget_reservation WHERE org_id=%s AND project_id=%s AND reservation_id=%s',(*scope.key,committed_hold['reservation_id'])).fetchone()
        assert readback_hold['content_hash']==committed_hold['content_hash']
        assert judge_budget._immutable(readback_hold)==judge_budget._immutable(committed_hold)
        assert shared_risk_totals(independent_hold_read,scope,committed_hold['budget_revision_ref']['resourceId'])==(1,10)
        for forbidden_sql in ('UPDATE aip_model_judge_budget_reservation SET upper_bound_minor=11 WHERE reservation_id=%s',
                              'DELETE FROM aip_model_judge_budget_reservation WHERE reservation_id=%s'):
            with independent_hold_read.transaction(force_rollback=True):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    independent_hold_read.execute(forbidden_sql,(committed_hold['reservation_id'],))
    from aos_api.aip_model_eval_execution_contracts import ModelJudgeParentBudgetLimit
    from aos_api.aip_model_eval_execution_reader import validate_judge_parent_hold, ModelExecutionPlanRejected
    parent_body=dict(schemaVersion='aos.model-judge-parent-budget/v1',purpose='model-judge-call',
        tenant={'orgId':scope.org_id,'projectId':scope.project_id},
        parentHoldRef={'resourceType':'ModelJudgeBudgetReservation','resourceId':str(committed_hold['reservation_id']),
                       'revision':1,'contentHash':committed_hold['content_hash']},
        requestId=budget_pending['request_id'],requestHash=budget_pending['request_hash'],
        approvalRef=committed_hold['approval_ref'],budgetPolicyRef=committed_hold['budget_policy_ref'],
        priceRef={'assetType':'ModelPriceSnapshotRevision','assetId':committed_hold['price_ref']['resourceId'],'revision':committed_hold['price_ref']['revision'],'contentHash':committed_hold['price_ref']['contentHash'].removeprefix('sha256:')},currency='CNY',upperBoundMinor=10,executionAllowed=False)
    parent=ModelJudgeParentBudgetLimit.model_validate(parent_body)
    from aos_api.aip_model_eval_execution_owner import ModelEvalExecutionOwner, ModelEvalOwnerRejected
    judge_owner=ModelEvalExecutionOwner()
    reader_negative_cases=[]
    with connect_serializable(scope) as parent_caller:
        parent_caller_identity=parent_caller.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        validate_judge_parent_hold(parent_caller,expected_tenant=parent.tenant,parent_limit=parent,
                                  release_policy=policy,artifact_bytes=files)
        for fault in ('hold_hash','request_hash','approval','policy','price','amount'):
            wrong=json.loads(json.dumps(parent_body))
            if fault=='hold_hash':wrong['parentHoldRef']['contentHash']='sha256:'+'0'*64
            elif fault=='request_hash':wrong['requestHash']='0'*64
            elif fault=='approval':wrong['approvalRef']['resourceId']=new_approval['approval_event_id']
            elif fault=='policy':wrong['budgetPolicyRef']['contentHash']='0'*64
            elif fault=='price':wrong['priceRef']['contentHash']='0'*64
            elif fault=='amount':wrong['upperBoundMinor']=9
            with parent_caller.transaction(force_rollback=True):
                with pytest.raises(ModelExecutionPlanRejected):
                    validate_judge_parent_hold(parent_caller,expected_tenant=parent.tenant,parent_limit=wrong,
                                              release_policy=policy,artifact_bytes=files)
            reader_negative_cases.append(fault)
        judge_owner.prepare_dual_purpose_fee_fences(parent_caller,scope,budget_pending['request_id'],be['approval_event_id'],release_policy=policy,artifact_bytes=files)
        owner_preparation=judge_owner.prepare_judge_application(parent_caller,scope,
            budget_pending['request_id'],be['approval_event_id'],release_policy=policy,artifact_bytes=files)
        judge_owner._prepare_dual_purpose_bucket_fences(parent_caller,scope,budget_pending['request_id'],be['approval_event_id'],release_policy=policy,artifact_bytes=files)
        AipModelEvalBudgetReservationStore().hold(parent_caller,scope,target['request_id'],ids[0])
        parent_target=judge_owner.prepare_model_application(parent_caller,scope,target['request_id'],ids[0])
        stale_body=whole_builder.build(parent_target,owner_preparation)
        with parent_caller.transaction(force_rollback=True):
            with pytest.raises(ModelEvalOwnerRejected,match='fresh dual parent rows'):
                judge_owner.validate_original_target_judge_manifest(parent_caller,scope,stale_body,release_policy=policy,artifact_bytes=files)
        assert owner_preparation.parent_limit==parent
        assert (owner_preparation.caller_xid,owner_preparation.caller_pid)==(parent_caller_identity['xid'],parent_caller_identity['pid'])
        assert owner_preparation.request==budget_pending['request_json'] and owner_preparation.execution_allowed is False
        case_inputs=tuple(dict(caseId=c['caseId'],inputHash=c['inputArtifact']['contentHash'],
            expectedHash=c['expectedArtifact']['contentHash'] if c.get('expectedArtifact') is not None else None)
            for c in budget_pending['request_json']['cases'])
        judge_owner.validate_judge_application_case_set(parent_caller,scope,
            budget_pending['request_id'],be['approval_event_id'],
            target_request_id=target['request_id'],target_request_hash=target_request['request_hash'],
            cases=case_inputs,case_set_hash=canonical_hash(list(case_inputs)),
            release_policy=policy,artifact_bytes=files)
        case_faults={
            'cropped':case_inputs[:1], 'duplicate':(case_inputs[0],case_inputs[0]),
            'reordered':tuple(reversed(case_inputs)),
            'input':(dict(case_inputs[0],inputHash='0'*64),case_inputs[1]),
            'expected':(dict(case_inputs[0],expectedHash='0'*64),case_inputs[1]),
            'extra-permit':(dict(case_inputs[0],executionAllowed=True),case_inputs[1]),
            'list':list(case_inputs), 'empty':(),
        }
        from aos_api.aip_model_eval_execution_contracts import ModelEvalCaseInputBinding
        copied_case=ModelEvalCaseInputBinding.model_validate(case_inputs[0]).model_copy(update={'permit':True})
        case_faults['unchecked-copy']=(copied_case,case_inputs[1])
        case_binding_negatives=[]
        for fault,bad_cases in case_faults.items():
            with parent_caller.transaction(force_rollback=True):
                with pytest.raises(ModelEvalOwnerRejected):
                    judge_owner.validate_judge_application_case_set(parent_caller,scope,
                        budget_pending['request_id'],be['approval_event_id'],
                        target_request_id=target['request_id'],target_request_hash=target_request['request_hash'],
                        cases=bad_cases,case_set_hash=canonical_hash(list(bad_cases)) if fault!='unchecked-copy' else canonical_hash(list(case_inputs)),
                        release_policy=policy,artifact_bytes=files)
            case_binding_negatives.append(fault)
        for fault,rid,rhash,chash in (
            ('wrong-target',judge['request_id'],target_request['request_hash'],canonical_hash(list(case_inputs))),
            ('target-hash',target['request_id'],'0'*64,canonical_hash(list(case_inputs))),
            ('case-hash',target['request_id'],target_request['request_hash'],'0'*64)):
            with parent_caller.transaction(force_rollback=True):
                with pytest.raises(ModelEvalOwnerRejected):
                    judge_owner.validate_judge_application_case_set(parent_caller,scope,
                        budget_pending['request_id'],be['approval_event_id'],target_request_id=rid,
                        target_request_hash=rhash,cases=case_inputs,case_set_hash=chash,
                        release_policy=policy,artifact_bytes=files)
            case_binding_negatives.append(fault)
        for rid,aid in ((target['request_id'],ids[0]),(budget_pending['request_id'],new_approval['approval_event_id']),
                        (' ',be['approval_event_id']),(budget_pending['request_id'],' ')):
            with parent_caller.transaction(force_rollback=True):
                with pytest.raises(ModelEvalOwnerRejected):
                    judge_owner.prepare_judge_application(parent_caller,scope,rid,aid,
                        release_policy=policy,artifact_bytes=files)
        from aos_api.aip_model_eval_execution_owner import ModelJudgeApplicationPreparation
        from pydantic import ValidationError
        for field,value in (('execution_allowed',True),('request_hash','0'*64),
                            ('parent_limit',parent.model_copy(update={'purpose':'quality-eval'}))):
            with pytest.raises(ValidationError):
                ModelJudgeApplicationPreparation.model_validate(owner_preparation.model_copy(update={field:value}))
        parent_caller.rollback()
    with pytest.raises(ModelEvalOwnerRejected):
        judge_owner.prepare_judge_application(object(),scope,budget_pending['request_id'],be['approval_event_id'],
            release_policy=policy,artifact_bytes=files)
    with pytest.raises(ModelEvalOwnerRejected,match='exact native whole newJudge caller'):
        native_owner.validate_original_target_judge_manifest(object(),scope,native_body,release_policy=policy,artifact_bytes=files)
    with connect(scope) as wrong_isolation:
        with pytest.raises(ModelExecutionPlanRejected):
            validate_judge_parent_hold(wrong_isolation,expected_tenant=parent.tenant,parent_limit=parent,
                                      release_policy=policy,artifact_bytes=files)
        with pytest.raises(ModelEvalOwnerRejected):
            judge_owner.prepare_judge_application(wrong_isolation,scope,budget_pending['request_id'],be['approval_event_id'],
                release_policy=policy,artifact_bytes=files)
        with pytest.raises(ModelEvalOwnerRejected,match='original runtime SERIAL whole caller'):
            native_owner.validate_original_target_judge_manifest(wrong_isolation,scope,native_body,release_policy=policy,artifact_bytes=files)
        wrong_isolation.rollback()
    with connect(TenantScope('dev-org','dev-project')) as wrong_tenant:
        with pytest.raises(ModelExecutionPlanRejected):
            validate_judge_parent_hold(wrong_tenant,expected_tenant=parent.tenant,parent_limit=parent,
                                      release_policy=policy,artifact_bytes=files)
        with pytest.raises(ModelEvalOwnerRejected):
            judge_owner.prepare_judge_application(wrong_tenant,TenantScope('dev-org','dev-project'),budget_pending['request_id'],be['approval_event_id'],
                release_policy=policy,artifact_bytes=files)
        with pytest.raises(ModelEvalOwnerRejected,match='exact native whole newJudge caller'):
            native_owner.validate_original_target_judge_manifest(wrong_tenant,TenantScope('dev-org','dev-project'),native_body,release_policy=policy,artifact_bytes=files)
        wrong_tenant.rollback()
    with psycopg.connect(get_dsn(),row_factory=__import__('psycopg.rows',fromlist=['dict_row']).dict_row) as wrong_admin:
        wrong_admin.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
        with pytest.raises(ModelEvalOwnerRejected,match='original runtime SERIAL whole caller'):
            native_owner.validate_original_target_judge_manifest(wrong_admin,scope,native_body,release_policy=policy,artifact_bytes=files)
        with pytest.raises(ModelEvalOwnerRejected):
            judge_owner.prepare_judge_application(wrong_admin,scope,budget_pending['request_id'],be['approval_event_id'],
                release_policy=policy,artifact_bytes=files)
        wrong_admin.rollback()
    with connect(TenantScope('dev-org','dev-project')) as isolated_read:
        assert isolated_read.execute('SELECT count(*) AS n FROM aip_model_judge_budget_reservation').fetchone()['n']==0
    # Actual new Owner must take both fee fences before its Judge buckets.
    policy_ids=[budget_pending['request_json'][k]['request']['budgetPolicyRef']['assetId']
                for k in ('targetApplication','judgeGovernanceApplication')]
    with connect(scope) as fee_read:
        fee_keys=fee_read.execute("SELECT r.payload->'budgetRevisionRef'->>'assetId' AS budget_id,(r.payload->'budgetRevisionRef'->>'revision')::integer AS revision FROM aip_model_governance_policy_revision r JOIN aip_model_governance_policy_head h USING(org_id,project_id,policy_kind,policy_id) WHERE r.org_id=%s AND r.project_id=%s AND r.policy_kind='budget' AND r.policy_id=ANY(%s) AND r.revision=h.current_revision ORDER BY budget_id,revision",(*scope.key,policy_ids)).fetchall()
    assert len(fee_keys)==2 and fee_keys[0]['budget_id']!=fee_keys[1]['budget_id']
    dual_fee_identity={};dual_fee_started=threading.Event();dual_fee_results=[]
    def dual_fee_owner_waiter():
        try:
            with connect_serializable(scope) as dual_conn:
                dual_fee_identity.update(dual_conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone())
                dual_fee_started.set()
                result=judge_owner.prepare_judge_application(dual_conn,scope,budget_pending['request_id'],be['approval_event_id'],release_policy=policy,artifact_bytes=files)
                assert (result.caller_xid,result.caller_pid)==(dual_fee_identity['xid'],dual_fee_identity['pid'])
                dual_conn.rollback()
            dual_fee_results.append('rolled-back')
        except BaseException as exc:
            dual_fee_results.append(type(exc).__name__+':'+str(exc))
    dual_fee_thread=threading.Thread(target=dual_fee_owner_waiter)
    dual_fee_observed=None;dual_bucket_free=False;first_fee_locked=False
    try:
        with psycopg.connect(get_dsn()) as second_fee_blocker:
            last=fee_keys[-1]
            assert second_fee_blocker.execute('SELECT budget_id FROM aip_budget_cost_runtime_fence WHERE org_id=%s AND project_id=%s AND budget_id=%s AND revision=%s FOR UPDATE',(*scope.key,last['budget_id'],last['revision'])).fetchone()
            dual_fee_thread.start();assert dual_fee_started.wait(5)
            for _ in range(100):
                second_fee_blocker.execute('SELECT pg_stat_clear_snapshot()')
                dual_fee_observed=second_fee_blocker.execute("SELECT pid,wait_event_type,wait_event FROM pg_stat_activity WHERE pid=%s AND wait_event_type='Lock' AND query LIKE '%%aip_budget_cost_runtime_fence%%'",(dual_fee_identity['pid'],)).fetchone()
                if dual_fee_observed:break
                time.sleep(.02)
            assert dual_fee_observed,dual_fee_results
            first=fee_keys[0]
            try:
                with connect(scope) as first_probe:
                    first_probe.execute('SELECT budget_id FROM aip_budget_cost_runtime_fence WHERE org_id=%s AND project_id=%s AND budget_id=%s AND revision=%s FOR UPDATE NOWAIT',(*scope.key,first['budget_id'],first['revision']))
            except psycopg.errors.LockNotAvailable:
                first_fee_locked=True
            with connect(scope) as bucket_probe:
                dual_bucket_free=bucket_probe.execute("SELECT account_id FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s AND bucket_kind='task' AND account_id=%s FOR UPDATE NOWAIT",(*scope.key,'model-judge/'+budget_pending['request_id'])).fetchone() is not None
                bucket_probe.rollback()
            assert first_fee_locked and dual_bucket_free
            second_fee_blocker.rollback()
    finally:
        if dual_fee_thread.ident is not None:dual_fee_thread.join(15)
    assert not dual_fee_thread.is_alive() and dual_fee_results==['rolled-back'],dual_fee_results
    # The two original purposes need one ordered bucket union, not two
    # independently ordered triples. No new parent is created by this prefix.
    bucket_accounts = ['model-eval/' + target['request_id'],
                       'model-judge/' + budget_pending['request_id']]
    bucket_accounts += [k['budget_id'] + suffix for k in fee_keys for suffix in (':daily', ':pilot')]
    with connect_serializable(scope) as prefix_conn:
        prefix_identity = prefix_conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        prefix_holds = prefix_conn.execute('SELECT count(*) AS n FROM aip_model_judge_budget_reservation').fetchone()['n']
        assert judge_owner._prepare_dual_purpose_bucket_fences(prefix_conn, scope,
            budget_pending['request_id'], be['approval_event_id'], release_policy=policy, artifact_bytes=files) is None
        ordered_buckets = prefix_conn.execute('''SELECT bucket_kind,account_id,period_start,currency,period_end,limit_minor,held_minor
            FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s AND account_id=ANY(%s)''',
            (*scope.key, bucket_accounts)).fetchall()
        ordered_buckets.sort(key=lambda b: (b['bucket_kind'], b['account_id'], b['period_start'], b['currency']))
        assert len(ordered_buckets) == 6
        assert prefix_conn.execute('SELECT count(*) AS n FROM aip_model_judge_budget_reservation').fetchone()['n'] == prefix_holds
        assert prefix_conn.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=%s',
            (target['request_id'],)).fetchone()['n'] == 0
    bucket_wait_identity = {}; bucket_wait_started = threading.Event(); bucket_wait_results = []
    def bucket_prefix_waiter():
        try:
            with connect_serializable(scope) as waiter:
                bucket_wait_identity.update(waiter.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone())
                bucket_wait_started.set()
                judge_owner._prepare_dual_purpose_bucket_fences(waiter, scope,
                    budget_pending['request_id'], be['approval_event_id'], release_policy=policy, artifact_bytes=files)
                waiter.rollback()
            bucket_wait_results.append('rolled-back')
        except BaseException as exc:
            bucket_wait_results.append(type(exc).__name__ + ':' + str(exc))
    bucket_thread = threading.Thread(target=bucket_prefix_waiter)
    bucket_wait_observed = None; preceding_locked = []; prefix_fees_locked = []
    lock_sql = '''SELECT account_id FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s
        AND bucket_kind=%s AND account_id=%s AND period_start=%s AND currency=%s FOR UPDATE'''
    def bucket_params(bucket):
        return (*scope.key, bucket['bucket_kind'], bucket['account_id'], bucket['period_start'], bucket['currency'])
    try:
        # The original isolated admin observer can read another session's
        # pg_stat_activity query; the restricted runtime cannot attest it.
        with psycopg.connect(get_dsn(), row_factory=__import__('psycopg.rows', fromlist=['dict_row']).dict_row) as last_bucket_blocker:
            assert last_bucket_blocker.execute(lock_sql, bucket_params(ordered_buckets[-1])).fetchone()
            bucket_thread.start(); assert bucket_wait_started.wait(5)
            for _ in range(100):
                last_bucket_blocker.execute('SELECT pg_stat_clear_snapshot()')
                bucket_wait_observed = last_bucket_blocker.execute('''SELECT pid,wait_event_type,wait_event
                    FROM pg_stat_activity WHERE pid=%s AND wait_event_type='Lock'
                      AND query LIKE '%%aip_budget_bucket%%' ''', (bucket_wait_identity['pid'],)).fetchone()
                if bucket_wait_observed: break
                time.sleep(.02)
            assert bucket_wait_observed, bucket_wait_results
            for bucket in ordered_buckets[:-1]:
                with connect(scope) as probe:
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        probe.execute(lock_sql + ' NOWAIT', bucket_params(bucket))
                    probe.rollback()
                preceding_locked.append(bucket['account_id'])
            for fee_key in fee_keys:
                with connect(scope) as probe:
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        probe.execute('''SELECT budget_id FROM aip_budget_cost_runtime_fence
                            WHERE org_id=%s AND project_id=%s AND budget_id=%s AND revision=%s FOR UPDATE NOWAIT''',
                            (*scope.key, fee_key['budget_id'], fee_key['revision']))
                    probe.rollback()
                prefix_fees_locked.append(fee_key['budget_id'])
            last_bucket_blocker.rollback()
    finally:
        if bucket_thread.ident is not None: bucket_thread.join(15)
    assert not bucket_thread.is_alive() and bucket_wait_results == ['rolled-back'], bucket_wait_results
    with connect_serializable(scope) as drift_conn:
        assert judge_owner._prepare_dual_purpose_bucket_fences(drift_conn, scope,
            budget_pending['request_id'], be['approval_event_id'], release_policy=policy, artifact_bytes=files) is None
        with drift_conn.transaction(force_rollback=True):
            # The original immutable-definition guard rejects this mutation
            # before our reader can see it; never disable it to manufacture a
            # downstream drift. Keep the actual producer boundary as evidence.
            with pytest.raises(psycopg.errors.RaiseException, match='budget bucket authority drifted'):
                drift_conn.execute('''UPDATE aip_budget_bucket SET limit_minor=limit_minor+1
                    WHERE org_id=%s AND project_id=%s AND bucket_kind=%s AND account_id=%s AND period_start=%s AND currency=%s''',
                    bucket_params(ordered_buckets[0]))
        assert judge_owner._prepare_dual_purpose_bucket_fences(drift_conn, scope,
            budget_pending['request_id'], be['approval_event_id'], release_policy=policy, artifact_bytes=files) is None
        after_buckets = drift_conn.execute('''SELECT bucket_kind,account_id,period_start,currency,period_end,limit_minor,held_minor
            FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s AND account_id=ANY(%s)''',
            (*scope.key, bucket_accounts)).fetchall()
        after_buckets.sort(key=lambda b: (b['bucket_kind'], b['account_id'], b['period_start'], b['currency']))
        assert after_buckets == ordered_buckets
        drift_conn.rollback()
    # Same original BudgetRevision, existing Model caller: while fee fence
    # is held elsewhere it must not own the common budget bucket first.
    from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore
    old_hold_started=threading.Event();old_hold_identity={};old_hold_results=[]
    def original_model_hold_waiter():
        try:
            with connect_serializable(scope) as old_hold_conn:
                old_hold_identity.update(old_hold_conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone())
                old_hold_started.set()
                AipModelEvalBudgetReservationStore().hold(old_hold_conn,scope,judge['request_id'],ids[1])
                old_hold_conn.rollback()
            old_hold_results.append('rolled-back')
        except BaseException as exc:
            old_hold_results.append(type(exc).__name__+':'+str(exc))
    old_hold_thread=threading.Thread(target=original_model_hold_waiter);old_hold_observed=None;shared_bucket_free=False
    try:
        with psycopg.connect(get_dsn()) as fee_blocker:
            fee_blocker.execute('SELECT budget_id FROM aip_budget_cost_runtime_fence WHERE org_id=%s AND project_id=%s AND budget_id=%s AND revision=%s FOR UPDATE',
                (*scope.key,committed_hold['budget_revision_ref']['resourceId'],committed_hold['budget_revision_ref']['revision']))
            old_hold_thread.start();assert old_hold_started.wait(5)
            for _ in range(100):
                fee_blocker.execute('SELECT pg_stat_clear_snapshot()')
                old_hold_observed=fee_blocker.execute("SELECT pid,wait_event_type,wait_event FROM pg_stat_activity WHERE pid=%s AND wait_event_type='Lock' AND query LIKE '%%aip_budget_cost_runtime_fence%%'",(old_hold_identity['pid'],)).fetchone()
                if old_hold_observed:break
                time.sleep(.02)
            assert old_hold_observed,old_hold_results
            try:
                with connect(scope) as bucket_probe:
                    shared_bucket_free=bucket_probe.execute("SELECT account_id FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s AND bucket_kind='daily' AND account_id=%s FOR UPDATE NOWAIT",
                        (*scope.key,committed_hold['budget_revision_ref']['resourceId']+':daily')).fetchone() is not None
                    bucket_probe.rollback()
            except psycopg.errors.LockNotAvailable:
                shared_bucket_free=False
            fee_blocker.commit()
    finally:
        if old_hold_thread.ident is not None:old_hold_thread.join(15)
    assert not old_hold_thread.is_alive() and old_hold_results==['rolled-back'],old_hold_results
    assert shared_bucket_free,'original Model held shared bucket before waiting for fee fence'
    # Replay cannot smuggle another current approval into an existing hold.
    budget_short_expiry=datetime.now(UTC)+timedelta(seconds=4)
    budget_short=propose_model_judge_request(maker,budget_pending['request_id'],'judge-budget-short-'+attempt_suffix,budget_short_expiry,
        release_policy=policy,artifact_bytes=files,connect_factory=connect_serializable)
    with connect(scope) as read:
        bs=read.execute('SELECT * FROM aip_action_proposal WHERE proposal_id=%s',(budget_short.proposal.id,)).fetchone()
    decide_model_judge_request(checker,bs['proposal_id'],'judge-budget-short-checker-'+attempt_suffix,
        DecideActionProposalRequest(decision='approved',expectedProposalVersion=bs['version'],expectedProposalHash=bs['proposal_hash']),
        release_policy=policy,artifact_bytes=files,connect_factory=connect_serializable)
    with connect_serializable(scope) as valid_budget_short:
        bse=valid_budget_short.execute("SELECT * FROM aip_action_approval_event WHERE proposal_id=%s AND decision='approved'",(bs['proposal_id'],)).fetchone()
        budget_prewait=action_guard.require_current_approval(valid_budget_short,scope,budget_pending['request_id'],budget_pending['request_hash'],bse['approval_event_id'])
        with pytest.raises(BudgetReservationBlocked,match='REPLAY_DRIFTED'):
            judge_budget.hold(valid_budget_short,scope,budget_pending['request_id'],budget_pending['request_hash'],bse['approval_event_id'])
        valid_budget_short.rollback()
    budget_wait_identity={};budget_wait_started=threading.Event();budget_wait_outcomes=[]
    def blocked_budget_replay():
        try:
            with connect_serializable(scope) as budget_waiter:
                budget_wait_identity.update(budget_waiter.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone())
                budget_wait_started.set()
                judge_budget.hold(budget_waiter,scope,budget_pending['request_id'],budget_pending['request_hash'],bse['approval_event_id'])
            budget_wait_outcomes.append('unexpected-success')
        except BaseException as exc:
            budget_wait_outcomes.append(str(exc))
    budget_wait_thread=threading.Thread(target=blocked_budget_replay);budget_observed=None
    try:
        with psycopg.connect(get_dsn()) as bucket_blocker:
            bucket_blocker.execute("SELECT account_id FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s AND bucket_kind='task' AND account_id=%s FOR UPDATE",(*scope.key,'model-judge/'+budget_pending['request_id']))
            budget_wait_thread.start();assert budget_wait_started.wait(5)
            for _ in range(100):
                bucket_blocker.execute('SELECT pg_stat_clear_snapshot()')
                budget_observed=bucket_blocker.execute("SELECT pid,wait_event_type,wait_event FROM pg_stat_activity WHERE pid=%s AND wait_event_type='Lock' AND query LIKE '%%aip_budget_bucket%%'",(budget_wait_identity['pid'],)).fetchone()
                if budget_observed:break
                time.sleep(.02)
            assert budget_observed,budget_wait_outcomes
            time.sleep(max(0,(bse['expires_at']-datetime.now(UTC)).total_seconds())+.05)
            bucket_blocker.commit()
    finally:
        if budget_wait_thread.ident is not None:budget_wait_thread.join(15)
    assert not budget_wait_thread.is_alive() and budget_wait_outcomes==['JUDGE_CURRENT_APPROVAL_REQUIRED'],budget_wait_outcomes
    with connect(scope) as hold_after_wait:
        assert hold_after_wait.execute('SELECT content_hash FROM aip_model_judge_budget_reservation WHERE reservation_id=%s',(committed_hold['reservation_id'],)).fetchone()['content_hash']==committed_hold['content_hash']
        assert shared_risk_totals(hold_after_wait,scope,committed_hold['budget_revision_ref']['resourceId'])==(1,10)
    with connect_serializable(scope) as source_conn:
        approval_facts=action_guard.require_current_approval(source_conn,scope,pending['request_id'],pending['request_hash'],new_approval['approval_event_id'])
        assert approval_facts['requestId']==pending['request_id'] and approval_facts['requestHash']==pending['request_hash']
        assert approval_facts['approvalEventId']==new_approval['approval_event_id']
        assert approval_facts['checker']==checker.subject and approval_facts['maker']==maker.subject
        assert approval_facts['upperBoundMinor']==20 and approval_facts['approvalVerified'] is True
        assert approval_facts['executionAllowed'] is False and approval_facts['budgetHoldCreated'] is False
        identity=source_conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        assert approval_facts['callerXid']==identity['xid'] and approval_facts['callerPid']==identity['pid']
        for wrong_event in (ids[0],ids[1],'missing-judge-event'):
            with pytest.raises(AipActionTransitionBlocked):
                action_guard.require_current_approval(source_conn,scope,pending['request_id'],pending['request_hash'],wrong_event)
        with pytest.raises(AipActionTransitionBlocked):
            action_guard.require_current_approval(source_conn,scope,pending['request_id'],'f'*64,new_approval['approval_event_id'])
    with connect(scope) as nonserial:
        with pytest.raises(AipActionTransitionBlocked,match='CALLER'):
            action_guard.require_current_approval(nonserial,scope,pending['request_id'],pending['request_hash'],new_approval['approval_event_id'])
    with connect_serializable(TenantScope('dev-org','dev-project')) as canary:
        with pytest.raises(AipActionTransitionBlocked,match='CALLER'):
            action_guard.require_current_approval(canary,TenantScope('dev-org','dev-project'),pending['request_id'],pending['request_hash'],new_approval['approval_event_id'])
    with connect_serializable(scope) as probe:
        with probe.transaction(force_rollback=True):
            probe.execute("UPDATE meta_action_type SET name='changed-by-isolated-negative-test' WHERE id='aip_request_model_judge_call'")
            with pytest.raises(AipActionTransitionBlocked,match='METADATA_DRIFTED'):
                action_guard.read_metadata(probe)
        assert action_guard.read_metadata(probe)==action_row['action_type_snapshot']
        with probe.transaction(force_rollback=True):
            probe.execute('UPDATE aip_action_draft SET snapshot=jsonb_set(snapshot,%s,%s::jsonb) WHERE proposal_id=%s',(['payload','requestHash'],json.dumps('f'*64),proposed_row['proposal_id']))
            with pytest.raises(AipActionTransitionBlocked,match='DRAFT_DRIFTED'):
                action_guard.check_proposal(probe,scope,checker.subject,action_row,checker=True)
        assert action_guard.check_proposal(probe,scope,checker.subject,action_row,checker=True)
    generic_body=CreateActionProposalRequest(actionTypeId='aip_request_model_judge_call',purpose='model-judge-call',payload=action_row['payload'],expiresAt=expires)
    with pytest.raises(AipActionTransitionBlocked,match='MODEL_JUDGE_ACTION_PRODUCER_REQUIRED'):
        AipActionStore(connect_serializable).create_proposal(scope,maker.subject,'generic-judge-v2',generic_body,action_row['action_type_snapshot'],classify_action_risk('aip_request_model_judge_call',action_row['action_type_snapshot'],action_row['payload'],None))
    # The original signed/source window stays valid while only the new
    # proposal/approval expires during a real Registry advisory-lock wait.
    short_proposed=propose_model_judge_request(maker,pending['request_id'],proposal_key+'-short',datetime.now(UTC)+timedelta(seconds=4),
        release_policy=policy,artifact_bytes=files,connect_factory=connect_serializable)
    with connect(scope) as read:
        short_row=read.execute('SELECT * FROM aip_action_proposal WHERE proposal_id=%s',(short_proposed.proposal.id,)).fetchone()
    short_decision=DecideActionProposalRequest(decision='approved',expectedProposalVersion=short_row['version'],expectedProposalHash=short_row['proposal_hash'])
    decide_model_judge_request(checker,short_row['proposal_id'],decision_key+'-short',short_decision,
        release_policy=policy,artifact_bytes=files,connect_factory=connect_serializable)
    with connect_serializable(scope) as prewait:
        short_event=prewait.execute("SELECT * FROM aip_action_approval_event WHERE proposal_id=%s AND decision='approved'",(short_row['proposal_id'],)).fetchone()
        before_approval_wait=action_guard.require_current_approval(prewait,scope,pending['request_id'],pending['request_hash'],short_event['approval_event_id'])
        assert before_approval_wait['approvalVerified'] is True
    read_started=threading.Event();read_identity={};read_outcomes=[]
    def approval_source_waiter():
        try:
            with connect_serializable(scope) as waiting:
                read_identity.update(waiting.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone())
                read_started.set()
                action_guard.require_current_approval(waiting,scope,pending['request_id'],pending['request_hash'],short_event['approval_event_id'])
            read_outcomes.append('unexpected-success')
        except AipActionTransitionBlocked as exc:
            read_outcomes.append(str(exc))
        except BaseException as exc:
            read_outcomes.append(type(exc).__name__+':'+str(exc))
    read_thread=threading.Thread(target=approval_source_waiter);observed_read_wait=None
    try:
        with psycopg.connect(get_dsn()) as blocker:
            blocker.execute('SELECT pg_advisory_xact_lock(228,1)')
            read_thread.start();assert read_started.wait(5)
            for _ in range(100):
                blocker.execute('SELECT pg_stat_clear_snapshot()')
                observed_read_wait=blocker.execute("SELECT pid,wait_event_type,wait_event FROM pg_stat_activity WHERE pid=%s AND wait_event_type='Lock' AND query LIKE '%%pg_advisory_xact_lock(228,1)%%'",(read_identity['pid'],)).fetchone()
                if observed_read_wait:break
                time.sleep(.02)
            assert observed_read_wait,read_outcomes
            time.sleep(max(0,(short_event['expires_at']-datetime.now(UTC)).total_seconds())+.05)
            blocker.commit()
    finally:
        if read_thread.ident is not None:read_thread.join(15)
    assert not read_thread.is_alive() and read_outcomes==['JUDGE_CURRENT_APPROVAL_REQUIRED'],read_outcomes
    with connect_serializable(scope) as proof_conn:
        # Rejection is specifically the short new approval, not the pending
        # request or its original signed Rule/source becoming invalid.
        current_after_approval_wait=store.require_current_with_rule(proof_conn,scope,pending['request_id'],pending['request_hash'],release_policy=policy,artifact_bytes=files)
        assert current_after_approval_wait['request_hash']==pending['request_hash']
        assert proof_conn.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=ANY(%s)',([target['request_id'],judge['request_id']],)).fetchone()['n']==0
    # Exact original hold approval is valid before waiting and expires only
    # while the parent reader is blocked on an existing original budget row.
    with connect_serializable(scope) as parent_prewait_conn:
        parent_prewait=action_guard.require_current_approval(parent_prewait_conn,scope,
            budget_pending['request_id'],budget_pending['request_hash'],be['approval_event_id'])
        validate_judge_parent_hold(parent_prewait_conn,expected_tenant=parent.tenant,parent_limit=parent,
                                  release_policy=policy,artifact_bytes=files)
        parent_prewait_conn.rollback()
    parent_wait_identity={};parent_wait_started=threading.Event();parent_wait_outcomes=[]
    def parent_bucket_waiter():
        try:
            with connect_serializable(scope) as parent_wait_conn:
                parent_wait_identity.update(parent_wait_conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone())
                parent_wait_started.set()
                judge_owner.validate_judge_application_case_set(parent_wait_conn,scope,budget_pending['request_id'],be['approval_event_id'],
                    target_request_id=target['request_id'],target_request_hash=target_request['request_hash'],
                    cases=case_inputs,case_set_hash=canonical_hash(list(case_inputs)),
                    release_policy=policy,artifact_bytes=files)
            parent_wait_outcomes.append('unexpected-success')
        except (ModelExecutionPlanRejected,ModelEvalOwnerRejected) as exc:
            cause=exc
            while cause.__cause__ is not None:cause=cause.__cause__
            parent_wait_outcomes.append(str(cause))
        except BaseException as exc:
            parent_wait_outcomes.append(type(exc).__name__+':'+str(exc))
    parent_wait_thread=threading.Thread(target=parent_bucket_waiter);parent_wait_observed=None
    try:
        with psycopg.connect(get_dsn()) as parent_blocker:
            parent_blocker.execute("SELECT account_id FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s AND bucket_kind='task' AND account_id=%s FOR UPDATE",(*scope.key,'model-judge/'+budget_pending['request_id']))
            parent_wait_thread.start();assert parent_wait_started.wait(5)
            for _ in range(100):
                parent_blocker.execute('SELECT pg_stat_clear_snapshot()')
                parent_wait_observed=parent_blocker.execute("SELECT pid,wait_event_type,wait_event FROM pg_stat_activity WHERE pid=%s AND wait_event_type='Lock' AND query LIKE '%%aip_budget_bucket%%'",(parent_wait_identity['pid'],)).fetchone()
                if parent_wait_observed:break
                time.sleep(.02)
            assert parent_wait_observed,parent_wait_outcomes
            time.sleep(max(0,(be['expires_at']-datetime.now(UTC)).total_seconds())+.05)
            parent_blocker.commit()
    finally:
        if parent_wait_thread.ident is not None:parent_wait_thread.join(15)
    assert not parent_wait_thread.is_alive() and parent_wait_outcomes==['JUDGE_CURRENT_APPROVAL_REQUIRED'],parent_wait_outcomes
    with connect(scope) as parent_postread:
        after_parent=parent_postread.execute('SELECT * FROM aip_model_judge_budget_reservation WHERE reservation_id=%s',(committed_hold['reservation_id'],)).fetchone()
        assert judge_budget._immutable(after_parent)==judge_budget._immutable(readback_hold)
        assert after_parent['content_hash']==committed_hold['content_hash']
        assert parent_postread.execute('SELECT count(*) AS n FROM aip_model_judge_budget_reservation WHERE request_id=%s',(budget_pending['request_id'],)).fetchone()['n']==1
        assert parent_postread.execute('SELECT count(*) AS n FROM aip_model_judge_budget_reservation_bucket WHERE reservation_id=%s',(committed_hold['reservation_id'],)).fetchone()['n']==3
        assert shared_risk_totals(parent_postread,scope,committed_hold['budget_revision_ref']['resourceId'])==(1,10)
    # Fresh dual parents inherit their original locks. Verify DB-clock expiry
    # on the actual whole reader without claiming a synthetic lock competition.
    with connect_serializable(scope) as deadline_create:
        deadline_pending=store.create_with_rule(deadline_create,maker,'whole-deadline-request-'+attempt_suffix,
            budget_body,release_policy=policy,artifact_bytes=files)
    deadline_proposal=propose_model_judge_request(maker,deadline_pending['request_id'],
        'whole-deadline-proposal-'+attempt_suffix,datetime.now(UTC)+timedelta(seconds=5),
        release_policy=policy,artifact_bytes=files,connect_factory=connect_serializable)
    with connect(scope) as deadline_read:
        dp=deadline_read.execute('SELECT * FROM aip_action_proposal WHERE proposal_id=%s',
            (deadline_proposal.proposal.id,)).fetchone()
    decide_model_judge_request(checker,dp['proposal_id'],'whole-deadline-checker-'+attempt_suffix,
        DecideActionProposalRequest(decision='approved',expectedProposalVersion=dp['version'],expectedProposalHash=dp['proposal_hash']),
        release_policy=policy,artifact_bytes=files,connect_factory=connect_serializable)
    with connect(scope) as deadline_read:
        de=deadline_read.execute("SELECT * FROM aip_action_approval_event WHERE proposal_id=%s AND decision='approved'",
            (dp['proposal_id'],)).fetchone()
    with connect_serializable(scope) as deadline_conn:
        deadline_identity=deadline_conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        native_owner._prepare_dual_purpose_bucket_fences(deadline_conn,scope,deadline_pending['request_id'],
            de['approval_event_id'],release_policy=policy,artifact_bytes=files)
        AipModelEvalBudgetReservationStore().hold(deadline_conn,scope,target['request_id'],ids[0])
        judge_budget.hold(deadline_conn,scope,deadline_pending['request_id'],deadline_pending['request_hash'],de['approval_event_id'])
        dt=native_owner.prepare_model_application(deadline_conn,scope,target['request_id'],ids[0])
        dj=native_owner.prepare_judge_application(deadline_conn,scope,deadline_pending['request_id'],
            de['approval_event_id'],release_policy=policy,artifact_bytes=files)
        deadline_manifest=whole_builder.build(dt,dj)
        assert native_owner.validate_original_target_judge_manifest(deadline_conn,scope,deadline_manifest,
            release_policy=policy,artifact_bytes=files) is None
        before_deadline=deadline_conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        assert before_deadline < de['expires_at']
        # The database clock determines the wait; no expiry field is rewritten.
        deadline_conn.execute('SELECT pg_sleep(greatest(0,extract(epoch FROM (%s::timestamptz-clock_timestamp())))+0.1)',
            (de['expires_at'],))
        after_deadline=deadline_conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        assert after_deadline > de['expires_at']
        with pytest.raises(ModelEvalOwnerRejected):
            native_owner.validate_original_target_judge_manifest(deadline_conn,scope,deadline_manifest,
                release_policy=policy,artifact_bytes=files)
        deadline_conn.rollback()
    with psycopg.connect(get_dsn()) as deadline_audit:
        deadline_audit.execute('SET TRANSACTION READ ONLY')
        assert deadline_audit.execute('SELECT pg_xact_status(%s::xid8)',(deadline_identity['xid'],)).fetchone()[0]=='aborted'
        for table,parent_id in [('aip_model_eval_budget_reservation',dt.parent_limit.parent_hold_ref.resource_id),
                               ('aip_model_judge_budget_reservation',dj.parent_limit.parent_hold_ref.resource_id)]:
            assert deadline_audit.execute('SELECT count(*) FROM '+table+' WHERE reservation_id=%s',(parent_id,)).fetchone()[0]==0
    native_whole_proof['reader_database_clock_deadline']={'caller':deadline_identity,
        'before':before_deadline.isoformat(),'approval_deadline':de['expires_at'].isoformat(),
        'after':after_deadline.isoformat(),'before_accepted':True,'after_rejected':True,
        'independent_xact_status':'aborted','dual_parent_rows':0,'actual_budget_lock_wait_claimed':False}
    (evidence/(native_label+'-whole-plan-proof.json')).write_text(json.dumps(native_whole_proof,default=str,indent=2)+'\n')
    from psycopg.conninfo import conninfo_to_dict
    out=evidence/(os.environ['AOS_JUDGE_NATIVE_EVIDENCE_LABEL']+'-full-proof.json' if 'AOS_JUDGE_NATIVE_EVIDENCE_LABEL' in os.environ else 'exact-signed-rule-suite-native-r1.json')
    out.write_text(json.dumps({'database':conninfo_to_dict(get_dsn())['dbname'],'judge_application':judge,
        'target_application':target,'source':source.model_dump(mode='json',by_alias=True),'rule_facts':facts,
        'new_suite':dict(suite),'target_request':dict(target_request),'target_approval':dict(approval),
        'rule_pending':pending,'rule_checker_facts':checked,'canonical_v2_forgery_rejected':True,
        'new_judge_proposal':dict(action_row),'new_judge_approval':dict(new_approval),
        'approval_registry_lock_order':{'caller':approval_identity,'observed_wait':list(observed_approval_wait),'proposal_free_before_registry':proposal_free_before_registry,'thread_terminal':not approval_thread.is_alive()},
        'metadata_and_draft_sql_drift_rejected_and_rolled_back':True,
        'current_approval_source_facts':approval_facts,
        'judge_case_set':{'cases':list(case_inputs),'case_set_hash':canonical_hash(list(case_inputs)),'negative_cases':case_binding_negatives,'expiry_wait_via_case_set':True,'target_request_id':target['request_id'],'target_request_hash':target_request['request_hash'],'execution_allowed':False},
        'judge_owner_preparation':{'preparation':owner_preparation.model_dump(mode='json',by_alias=True),'negative_cases':['old-quality-request','wrong-new-approval','empty-request','empty-approval','non-native','nonSER','canary','admin'],'copied_preparation_rejected':True,'expiry_wait_via_owner':True},
        'judge_parent_reader':{'declaration':parent_body,'positive_caller':parent_caller_identity,'negative_cases':reader_negative_cases+['canary','nonSER'],'hold_unchanged':True,'prewait':parent_prewait,'wait_caller':parent_wait_identity,'observed':list(parent_wait_observed),'outcomes':parent_wait_outcomes,'thread_terminal':not parent_wait_thread.is_alive()},
        'dual_fee_lock_order':{'fee_keys':fee_keys,'caller':dual_fee_identity,'observed':list(dual_fee_observed),'first_fee_locked':first_fee_locked,'judge_bucket_free_before_second_fee':dual_bucket_free,'outcomes':dual_fee_results,'thread_terminal':not dual_fee_thread.is_alive()},
        'dual_bucket_lock_order':{'buckets':ordered_buckets,'metadata_caller':prefix_identity,'caller':bucket_wait_identity,
            'observed':dict(bucket_wait_observed),'five_preceding_locked':preceding_locked,'two_fees_locked':prefix_fees_locked,
            'outcomes':bucket_wait_results,'thread_terminal':not bucket_thread.is_alive(),'held_counters_unchanged':True,
            'new_parent_not_created':True,'row_limit_mutation_rejected_by_original_guard':True,'physical_source_joint_not_proven':True},
        'shared_fee_lock_order':{'caller':old_hold_identity,'observed':list(old_hold_observed),'shared_bucket_free_before_fee':shared_bucket_free,'outcomes':old_hold_results,'thread_terminal':not old_hold_thread.is_alive()},
        'judge_budget':{'pending':budget_pending,'approval':dict(be),'hold':committed_hold,'readback':dict(readback_hold),'caller':hold_identity,'rollback_caller':hold_rollback_identity,'rollback_verified':True,'shared_risk_totals':[1,10],'canary_zero':True,'update_delete_denied':True,'old_twenty_minor_risk_denied':True,
            'expiry_wait':{'prewait':budget_prewait,'approval':dict(bse),'caller':budget_wait_identity,'observed':list(budget_observed),'outcomes':budget_wait_outcomes,'thread_terminal':not budget_wait_thread.is_alive(),'original_hold_retained':True}},
        'approval_expiry_wait':{'prewait_facts':before_approval_wait,'deadline':short_event['expires_at'].isoformat(),'event_id':short_event['approval_event_id'],
            'caller':read_identity,'observed':list(observed_read_wait),'outcome':read_outcomes,'thread_terminal':not read_thread.is_alive(),'original_rule_and_pending_current_after_wait':True},
        'execution_allowed':False,'limitations':['isolated test Root and governance only','isolated new Judge-purpose approval only; no formal run/Model quality permission','no Model quality or Provider or expected read permission']},default=str,indent=2)+'\n')

"""Full Model Owner integration begins with original published authority.

This test does not treat the legal application/hold as joint execution authority.
Source/physical/unique Intent/finalizer and Target/Judge quality remain required.
"""
import importlib.util
import json
import sys
import os
import pytest
from pathlib import Path

from tests.aip.test_budget_cost_consumer_pg import caller
from tests.aip.test_budget_cost_issuer_pg import issuer_factory
from tests.aip._runtime_guard_history_fixture import https_signer, guard_issuer_factory, guard_consumer_factory


def _model_owner_fixture_base(*, whole=False):
    """An explicit fresh attempt may reuse exact helpers, never old outputs."""
    original = Path(__file__).resolve().parents[4]/'.evidence/gt-atomic-model-admission-20261008'
    override = os.environ.get('AOS_MODEL_OWNER_FIXTURE_EVIDENCE_ROOT')
    if override is None:
        return original
    selected = Path(override).resolve()
    if (selected == original or not selected.is_relative_to(original)
            or not selected.is_dir()):
        raise ValueError('isolated Model evidence directory required')
    helpers = ('legal_model_prefix_for_application_r4.py', 'legal_eval_application_fixture_r4.py')
    if whole:
        helpers += ('original_plan_certificate_fixture_r1.py',)
    for filename in helpers:
        copy = selected/filename
        if (not copy.is_file() or copy.is_symlink()
                or copy.read_bytes() != (original/filename).read_bytes()):
            raise ValueError('isolated Model evidence requires exact registered helpers')
    if any((selected/filename).exists() for filename in (
            'legal-model-prefix-application-r4.json', 'legal-eval-application-result-r4.json')):
        raise ValueError('isolated Model evidence must not overwrite an earlier attempt')
    return selected


def test_model_owner_from_original_published_approved_application(
    caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path,
):
    from aos_api.db import connect_serializable
    from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore
    from aos_api.tenant_scope import TenantScope
    base=_model_owner_fixture_base()
    for name in ('legal_model_prefix_for_application_r4','legal_eval_application_fixture_r4'):
        spec=importlib.util.spec_from_file_location(name,base/(name+'.py'))
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    sys.modules['legal_eval_application_fixture_r4'].create_application(
        caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path)
    app=json.loads((base/'legal-eval-application-result-r4.json').read_text())
    label=os.environ.get('AOS_MODEL_OWNER_EVIDENCE_LABEL','model-owner-current')
    scope=TenantScope('org-org','dev-project')
    with connect_serializable(scope) as conn:
        approval=conn.execute('''SELECT approval_event_id FROM aip_action_approval_event
            WHERE org_id=%s AND project_id=%s AND proposal_id=%s AND decision='approved' ''',
            (*scope.key,app['proposal_id'])).fetchone()['approval_event_id']
        original=AipModelEvalBudgetReservationStore().hold(conn,scope,app['request_id'],approval)
        assert conn.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=%s',
            (app['request_id'],)).fetchone()['n']==1
        # The original full application is durable; this caller's new budget
        # fact exists only in this transaction until the real Owner finalizes.
        identity=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        before=dict(application=app,approval_event_id=approval,caller=identity,hold={k:str(v) for k,v in original.items()},
                    scope='actual original legal publication, independent signed approval, same-caller budget; Source/Intent/full finalizer pending')
        (base/(label+'-input.json')).write_text(json.dumps(before,indent=2)+'\n')
        from aos_api.aip_model_eval_execution_owner import ModelEvalExecutionOwner,ModelEvalOwnerRejected,ModelEvalApplicationPreparation
        owner=ModelEvalExecutionOwner()
        # prepare must derive the original nonexecuting application command;
        # it cannot dispatch or fabricate Source/physical/Intent from a request.
        command=owner.prepare_model_application(conn,scope,app['request_id'],approval)
        assert command.request_id==app['request_id'] and command.request_hash==app['request_hash']
        assert command.execution_allowed is False
        assert conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()==identity

        stored=conn.execute('SELECT xmin::text AS xmin FROM aip_model_eval_budget_reservation WHERE request_id=%s',(app['request_id'],)).fetchone()
        assert command.parent_row_xmin==stored['xmin']
        assert command.caller_xid==identity['xid'] and command.caller_pid==identity['pid']
        assert command.parent_limit.request_hash==app['request_hash']
        assert command.request.source_ref.asset_id==app['model_id']
        assert ModelEvalApplicationPreparation.model_validate(command).execution_allowed is False
        for rid,aid in [(app['request_id']+' ','x'),('missing-request',approval),(app['request_id'],'unrelated-approval')]:
            with pytest.raises(ModelEvalOwnerRejected):owner.prepare_model_application(conn,scope,rid,aid)
        for forbidden in (True,0,'false'):
            with pytest.raises(ValueError):ModelEvalApplicationPreparation.model_validate(command.model_copy(update={'execution_allowed':forbidden}))
        assert not hasattr(owner,'dispatch') and not hasattr(owner,'admit')
        with pytest.raises(ModelEvalOwnerRejected,match='caller'):
            owner.prepare_model_application(object(),scope,app['request_id'],approval)
        (base/(label+'-preparation.json')).write_text(json.dumps(command.model_dump(mode='json',by_alias=True),indent=2)+'\n')
    # Original legacy budget hold committed as a fixture, not a joint admission.
    # Wrong caller role and isolation are rejected before accessing that hold.
    import psycopg
    from aos_api.db import get_dsn,connect
    with psycopg.connect(get_dsn()) as admin:
        with pytest.raises(ModelEvalOwnerRejected,match='caller'):
            owner.prepare_model_application(admin,scope,app['request_id'],approval)
    with connect(scope) as conn:
        with pytest.raises(ModelEvalOwnerRejected,match='SERIAL'):
            owner.prepare_model_application(conn,scope,app['request_id'],approval)
    with connect_serializable(TenantScope('dev-org','dev-project')) as conn:
        with pytest.raises(ModelEvalOwnerRejected,match='caller'):
            owner.prepare_model_application(conn,TenantScope('dev-org','dev-project'),app['request_id'],approval)


@pytest.mark.parametrize('tail_mode',['rollback','head-wait','contract-wait','judge-binding','judge-mismatch'])
def test_whole_model_plan_binds_each_original_approved_application(
    caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path,tail_mode,
):
    from aos_api.db import connect_serializable,connect,get_dsn
    from aos_api.aip_model_eval_execution_owner import ModelEvalExecutionOwner
    from aos_api.aip_model_eval_budget_reservation import AipModelEvalBudgetReservationStore
    from aos_api.aip_model_eval_execution_contracts import ModelEvalExecutionManifest
    from aos_api.tenant_scope import TenantScope
    from tests.aip.test_model_eval_execution_contracts import _plan_body
    import psycopg
    from datetime import timedelta
    base=_model_owner_fixture_base(whole=True)
    for name in ('legal_model_prefix_for_application_r4','legal_eval_application_fixture_r4'):
        spec=importlib.util.spec_from_file_location(name,base/(name+'.py'))
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    model_judge=tail_mode in ('judge-binding','judge-mismatch')
    original_tail_mode=tail_mode
    if model_judge:tail_mode='rollback'
    apps=[];judge_model_ref=None
    for index in ([1,0] if model_judge else range(2)):
        leg_path=tmp_path/str(index);leg_path.mkdir()
        selected_judge=judge_model_ref
        if original_tail_mode=='judge-mismatch' and index==0:selected_judge=dict(judge_model_ref,contentHash='f'*64)
        sys.modules['legal_eval_application_fixture_r4'].create_application(
            caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,leg_path,
            expires_after=timedelta(seconds=6) if tail_mode!='rollback' and index==1 else None,
            suite_case_copies=2 if index==0 and os.environ.get('AOS_MODEL_PROMPT_FORMAT_PROBE')!='1' else 1,
            judge_model_ref=selected_judge if index==0 else None)
        application=json.loads((base/'legal-eval-application-result-r4.json').read_text())
        if model_judge and index==1:
            with connect(TenantScope('org-org','dev-project')) as read:
                judge_model_ref=read.execute('SELECT request_json FROM aip_model_eval_request WHERE request_id=%s',(application['request_id'],)).fetchone()['request_json']['sourceRef']
        if model_judge:apps.insert(0,application)
        else:apps.append(application)
    scope=TenantScope('org-org','dev-project');owner=ModelEvalExecutionOwner();commands=[]
    label=os.environ.get('AOS_WHOLE_MODEL_OWNER_EVIDENCE_LABEL',
                         os.environ.get('AOS_MODEL_OWNER_EVIDENCE_LABEL','whole-original-plan'))+'-'+original_tail_mode
    with connect_serializable(scope) as conn:
        for app in apps:
            approval=conn.execute("SELECT approval_event_id FROM aip_action_approval_event WHERE proposal_id=%s AND decision='approved'",(app['proposal_id'],)).fetchone()['approval_event_id']
            AipModelEvalBudgetReservationStore().hold(conn,scope,app['request_id'],approval)
            commands.append(owner.prepare_model_application(conn,scope,app['request_id'],approval))
        body=_plan_body();body.update(requestId=commands[0].request_id,requestHash=commands[0].request_hash,
            request=commands[0].request.model_dump(mode='json',by_alias=True),
            parentBudgetLimits=[c.parent_limit.model_dump(mode='json',by_alias=True) for c in commands])
        for purpose,command in zip(('target','judge'),commands):
            leg=body['cases'][0][purpose];request=command.request;parent=command.parent_limit
            for field in ('provider_ref','price_ref','quota_policy_ref','budget_policy_ref'):
                alias=type(request).model_fields[field].alias
                leg[alias]=getattr(request,field).model_dump(mode='json',by_alias=True)
            leg['modelRef']=request.source_ref.model_dump(mode='json',by_alias=True)
            leg['approvalRef']=parent.approval_ref.model_dump(mode='json',by_alias=True)
            leg['budgetHoldRef']=parent.parent_hold_ref.model_dump(mode='json',by_alias=True)
        plan=ModelEvalExecutionManifest.model_validate(body)
        identity=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
        (base/(label+'-input.json')).write_text(json.dumps(dict(applications=apps,manifest=plan.model_dump(mode='json',by_alias=True),caller=identity,limitations='Source/input/Intent/joint refs descriptive only; no execution grant'),indent=2)+'\n')
        assert hasattr(owner,'validate_original_model_plan_requests'), 'whole original Target/Judge application bridge missing'
        assert owner.validate_original_model_plan_requests(conn,scope,plan) is None
        from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
        from aos_api.aip_budget_reservation_store import canonical_hash
        suite_ref=commands[0].request.suite_ref
        suite_row=conn.execute('SELECT * FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s',
            (*scope.key,suite_ref.asset_id,suite_ref.revision)).fetchone()
        suite=AipEvalPackRegistry._suite_from_row(suite_row)
        suite_body=json.loads(json.dumps(body));suite_body['cases']=[]
        for index,original_case in enumerate(suite.cases):
            case=json.loads(json.dumps(body['cases'][0]))
            case.update(caseId=original_case.case_id,inputHash=original_case.input_artifact.content_hash,
                expectedHash=original_case.expected_artifact.content_hash if original_case.expected_artifact else None)
            for purpose in ('target','judge'):
                for field in ('intentRef','budgetAllocationRef'):
                    case[purpose][field]['resourceId']+=f'-suite-{index}'
            suite_body['cases'].append(case)
        def refresh_case_set(value):
            value['caseSetHash']=canonical_hash([{k:c[k] for k in ('caseId','inputHash','expectedHash')} for c in value['cases']])
            return ModelEvalExecutionManifest.model_validate(value)
        suite_plan=refresh_case_set(suite_body)
        (base/(label+'-suite-input.json')).write_text(json.dumps(dict(manifest=suite_plan.model_dump(mode='json',by_alias=True),suite=suite.model_dump(mode='json',by_alias=True)),indent=2)+'\n')
        assert hasattr(owner,'validate_original_model_plan_suite'), 'complete original Suite case bridge missing'
        assert owner.validate_original_model_plan_suite(conn,scope,suite_plan) is None
        if os.environ.get('AOS_MODEL_PROMPT_FORMAT_PROBE') == '1':
            import hashlib
            from aos_api.aip_model_eval_execution_owner import ModelEvalOwnerRejected
            variant = os.environ['AOS_MODEL_PROMPT_VARIANT']
            fixture = sys.modules['registered_model_prompt_fixture_1654']
            raw = fixture.raw_json(fixture.TEST_VALUE)
            inputs = tuple((case.case_id, raw) for case in suite_plan.cases)
            assert all(hashlib.sha256(raw).hexdigest() == case.input_hash for case in suite_plan.cases)
            assert hasattr(owner, 'prepare_original_model_plan_prompt_bytes'), 'original approved Model prompt producer missing'
            if variant == 'valid':
                prepared = owner.prepare_original_model_plan_prompt_bytes(conn, scope, suite_plan, inputs=inputs)
                expected = tuple((case.case_id, fixture.TEST_VALUE['prompt'].encode('utf-8')) for case in suite_plan.cases)
                assert prepared == expected
            else:
                with pytest.raises(ModelEvalOwnerRejected, match='Model prompt (format|input)'):
                    owner.prepare_original_model_plan_prompt_bytes(conn, scope, suite_plan, inputs=inputs)
                prepared = ()
            assert conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone() == identity
            (base/(label+'-prompt-format.json')).write_text(json.dumps(dict(caller=identity, variant=variant,
                input_hash=hashlib.sha256(raw).hexdigest(), prompts=[dict(caseId=cid, sha256=hashlib.sha256(p).hexdigest(), bytesLength=len(p)) for cid,p in prepared],
                rejected=variant!='valid', execution_allowed=False, tokenizer_certified=False),indent=2)+'\n')
        if os.environ.get('AOS_MODEL_INPUT_BYTES_PROBE') == '1':
            from aos_api.ecommerce_content_pre_review_pack import build_content_pre_review_eval_packs
            from aos_api.aip_eval_contracts import AssetRevisionRef
            original_pack = conn.execute('''SELECT target_ref FROM aip_eval_suite_revision
                WHERE org_id=%s AND project_id=%s AND dataset_ref=%s::jsonb
                  AND target_ref->>'assetType'='logic_graph' ORDER BY suite_id LIMIT 1''',
                (*scope.key, json.dumps(suite.dataset.model_dump(mode='json', by_alias=True)))).fetchone()
            assert original_pack is not None
            _, input_pack = build_content_pre_review_eval_packs(AssetRevisionRef.model_validate(original_pack['target_ref']))
            encoded_inputs = tuple((case.case_id, json.dumps(
                input_pack.artifacts[(case.input_artifact.artifact_id, case.input_artifact.revision)],
                ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8'))
                for case in suite.cases)
            import hashlib
            assert [hashlib.sha256(raw).hexdigest() for _, raw in encoded_inputs] == [case.input_hash for case in suite_plan.cases]
            assert hasattr(owner, 'validate_original_model_plan_input_bytes'), 'original Model input bytes consumer missing'
            assert owner.validate_original_model_plan_input_bytes(conn, scope, suite_plan, inputs=encoded_inputs) is None
            first_id, first_raw = encoded_inputs[0]
            invalid_sets = [list(encoded_inputs), encoded_inputs[:-1], encoded_inputs + (('extra', first_raw),),
                (encoded_inputs[0], encoded_inputs[0]), tuple(reversed(encoded_inputs)),
                ((first_id, first_raw+b' '),)+encoded_inputs[1:],
                ((first_id, first_raw.decode()),)+encoded_inputs[1:],
                ((first_id, b'x'*1048577),)+encoded_inputs[1:],
                ((first_id, b'{"x":1,"x":2}'),)+encoded_inputs[1:],
                ((first_id, b'NaN'),)+encoded_inputs[1:],
                ((first_id, b'Infinity'),)+encoded_inputs[1:],
                ((first_id, b'\xff'),)+encoded_inputs[1:],
                ((first_id, b'1e9999'),)+encoded_inputs[1:],
                ((first_id, b'{"outer":{"x":1,"x":2}}'),)+encoded_inputs[1:]]
            for index, invalid in enumerate(invalid_sets):
                with pytest.raises(ValueError, match='strict original Model input UTF8 JSON' if index >= 8 else None):
                    owner.validate_original_model_plan_input_bytes(conn, scope, suite_plan, inputs=invalid)
            with pytest.raises(ValueError, match='caller'):
                owner.validate_original_model_plan_input_bytes(object(), scope, suite_plan, inputs=encoded_inputs)
            assert owner.validate_original_model_plan_input_bytes(conn, scope, suite_plan, inputs=encoded_inputs) is None
            assert conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone() == identity
            (base/(label+'-original-input-bytes.json')).write_text(json.dumps(dict(
                caller=identity, case_hashes=[dict(caseId=case_id, sha256=hashlib.sha256(raw).hexdigest(), bytesLength=len(raw)) for case_id,raw in encoded_inputs],
                rejected_sets=len(invalid_sets), execution_allowed=False, tokenizer_used=False,
                limitations='Original content governance input bytes only; not Model prompt/schema/quality or transport.'),indent=2)+'\n')
        assert hasattr(owner,'validate_original_model_judge_binding'),'original Suite-to-Model Judge binding missing'
        if original_tail_mode=='judge-mismatch':
            with pytest.raises(ValueError,match='original Suite Model Judge differs'):
                owner.validate_original_model_judge_binding(conn,scope,suite_plan)
            (base/(label+'-judge-mismatch.json')).write_text(json.dumps(dict(caller=identity,suite=suite.model_dump(mode='json',by_alias=True),manifest=suite_plan.model_dump(mode='json',by_alias=True),rejected=True,execution_allowed=False),indent=2)+'\n')
        elif model_judge:
            assert owner.validate_original_model_judge_binding(conn,scope,suite_plan) is None
            (base/(label+'-judge-binding.json')).write_text(json.dumps(dict(caller=identity,suite=suite.model_dump(mode='json',by_alias=True),manifest=suite_plan.model_dump(mode='json',by_alias=True),approved_judge_model=commands[1].request.source_ref.model_dump(mode='json',by_alias=True),necessary_binding=True,execution_allowed=False),indent=2)+'\n')
        else:
            with pytest.raises(ValueError,match='original Suite Model Judge'):
                owner.validate_original_model_judge_binding(conn,scope,suite_plan)
        if tail_mode=='rollback':
            currentness=[]
            for purpose,app in zip(('target','judge'),apps):
                conn.execute('SAVEPOINT original_checker_currentness')
                conn.execute('RESET ROLE')
                deleted=conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s RETURNING role',(*scope.key,app['checker'])).fetchall()
                assert deleted,'original independent checker membership must actually exist'
                conn.execute('SET LOCAL ROLE aos_runtime')
                from aos_api.aip_model_eval_execution_owner import ModelEvalOwnerRejected
                with pytest.raises(ModelEvalOwnerRejected,match='original Model checker authority'):
                    owner.validate_original_model_plan_suite(conn,scope,suite_plan)
                conn.execute('ROLLBACK TO SAVEPOINT original_checker_currentness')
                assert owner.validate_original_model_plan_suite(conn,scope,suite_plan) is None
                currentness.append(dict(purpose=purpose,checker=app['checker'],deleted_roles=[r['role'] for r in deleted],restored_positive=True))
            (base/(label+'-checker-currentness.json')).write_text(json.dumps(dict(caller=identity,applications=apps,checks=currentness,execution_allowed=False),indent=2)+'\n')
            spec=importlib.util.spec_from_file_location('original_plan_certificate_fixture_r1',base/'original_plan_certificate_fixture_r1.py')
            cert_fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(cert_fixture)
            cert_fixture.verify_original_certificate_set(conn,suite_plan,base,label)
        for field in ('caseId','inputHash','expectedHash'):
            changed=json.loads(json.dumps(suite_body));changed['cases'][0][field]='wrong-case' if field=='caseId' else 'f'*64
            with pytest.raises(ValueError,match='original Suite cases'):
                owner.validate_original_model_plan_suite(conn,scope,refresh_case_set(changed))
        extra=json.loads(json.dumps(suite_body));additional=json.loads(json.dumps(extra['cases'][0]));additional['caseId']='extra-original-case'
        for purpose in ('target','judge'):
            for field in ('intentRef','budgetAllocationRef'):additional[purpose][field]['resourceId']+='-extra'
        extra['cases'].append(additional)
        with pytest.raises(ValueError,match='original Suite cases'):
            owner.validate_original_model_plan_suite(conn,scope,refresh_case_set(extra))
        if len(suite_body['cases'])>1:
            missing=json.loads(json.dumps(suite_body));missing['cases'].pop()
            with pytest.raises(ValueError,match='original Suite cases'):
                owner.validate_original_model_plan_suite(conn,scope,refresh_case_set(missing))
        for field in ('modelRef','providerRef','quotaPolicyRef'):
            bad=json.loads(json.dumps(body));bad['cases'][0]['judge'][field]['assetId']+='-wrong-original'
            # Still a valid descriptive plan; the original database must deny.
            typed=ModelEvalExecutionManifest.model_validate(bad)
            with pytest.raises(ValueError,match='original leg governance'):
                owner.validate_original_model_plan_requests(conn,scope,typed)
            with pytest.raises(ValueError,match='original leg governance'):
                owner.validate_original_model_judge_binding(conn,scope,typed)
        bad=json.loads(json.dumps(body));bad['parentBudgetLimits'][1]['requestHash']='f'*64
        with pytest.raises(ValueError):owner.validate_original_model_plan_requests(conn,scope,ModelEvalExecutionManifest.model_validate(bad))
        with pytest.raises(ValueError):owner.validate_original_model_plan_requests(conn,scope,plan.model_copy(update={'execution_allowed':True}))
        model=commands[1].request.source_ref.asset_id
        conn.execute('SAVEPOINT changed_head')
        conn.execute('UPDATE aip_registered_model_head SET version=version+1 WHERE registered_model_id=%s',(model,))
        with pytest.raises(ValueError,match='current original Model head'):
            owner.validate_original_model_plan_requests(conn,scope,plan)
        conn.execute('ROLLBACK TO SAVEPOINT changed_head')
        assert owner.validate_original_model_plan_requests(conn,scope,plan) is None
        assert conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()==identity
        if tail_mode=='rollback':conn.rollback()
        # The wait case commits only original legacy budget fixture holds.
        # It creates no prepared physical debit/Intent or joint admission.
    if tail_mode!='rollback':
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        import time
        ready=Event();reader_identity={}
        with connect(scope) as writer,psycopg.connect(get_dsn()) as observer:
            if tail_mode=='head-wait':
                writer.execute('SELECT registered_model_id FROM aip_registered_model_head WHERE registered_model_id=%s FOR UPDATE',(model,)).fetchone()
            else:
                writer.execute('SELECT contract_id FROM aip_eval_contract_head WHERE contract_id=%s FOR UPDATE',(commands[0].request.eval_contract_ref.asset_id,)).fetchone()
            writer_pid=writer.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            def read_after_wait():
                with connect_serializable(scope) as reader:
                    reader.execute("SET LOCAL statement_timeout='15s'")
                    reader_identity.update(reader.execute('SELECT pg_backend_pid() AS pid').fetchone());ready.set()
                    if tail_mode=='head-wait':
                        with pytest.raises(ValueError,match='must remain current after locks'):
                            owner.validate_original_model_plan_requests(reader,scope,plan)
                    else:
                        with pytest.raises(ValueError,match='current immutable parent request|exact current parent approval|must remain current after locks'):
                            owner.validate_original_model_plan_suite(reader,scope,suite_plan)
                    reader.rollback()
                return True
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(read_after_wait)
                try:
                    assert ready.wait(3)
                    end=time.monotonic()+3
                    while time.monotonic()<end:
                        blocked=observer.execute('SELECT %s=ANY(pg_blocking_pids(%s)) AS blocked',(writer_pid,reader_identity['pid'])).fetchone()[0]
                        if blocked:break
                        time.sleep(.02)
                    assert blocked and not future.done()
                    expiry=commands[1].request.expires_at
                    observer.execute('SELECT pg_sleep(GREATEST(0,EXTRACT(EPOCH FROM (%s::timestamptz-clock_timestamp())))+.1)',(expiry,))
                finally:writer.rollback()
                assert future.result(timeout=20) is True
        (base/(label+'-head-wait.json')).write_text(json.dumps(dict(wait_kind=tail_mode,writer_pid=writer_pid,reader_pid=reader_identity['pid'],native_block_observed=True,reader_rejected_after_approval_expiry=True,execution_allowed=False),indent=2)+'\n')
        return
    with connect(scope) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE request_id=ANY(%s)',([a['request_id'] for a in apps],)).fetchone()['n']==0
        assert conn.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation_bucket WHERE reservation_id=ANY(%s::uuid[])',
            ([c.parent_limit.parent_hold_ref.resource_id for c in commands],)).fetchone()['n']==0
    with psycopg.connect(get_dsn()) as conn:
        conn.execute('SELECT 1')
        with pytest.raises(ValueError,match='runtime SERIAL'):
            owner.validate_original_model_plan_requests(conn,scope,plan)
    with connect(scope) as conn:
        with pytest.raises(ValueError,match='runtime SERIAL'):
            owner.validate_original_model_plan_requests(conn,scope,plan)
    with connect_serializable(TenantScope('dev-org','dev-project')) as conn:
        with pytest.raises(ValueError,match='caller'):
            owner.validate_original_model_plan_requests(conn,TenantScope('dev-org','dev-project'),plan)
    (base/(label+'-result.json')).write_text(json.dumps(dict(request_ids=[a['request_id'] for a in apps],caller=identity,actual_rollback=True,execution_allowed=False),indent=2)+'\n')


@pytest.mark.skipif(os.environ.get('AOS_MODEL_PROMPT_FORMAT_PROBE') != '1', reason='explicit isolated Model prompt probe only')
def test_model_owner_new_original_prompt_format(
    caller, issuer_factory, https_signer, guard_issuer_factory, guard_consumer_factory, tmp_path, monkeypatch,
):
    base = _model_owner_fixture_base(whole=True)
    filename = 'registered_model_prompt_fixture_1654.py'
    original = Path(__file__).resolve().parents[4]/'.evidence/gt-atomic-model-admission-20261008'/filename
    copied = base/filename
    assert copied.is_file() and not copied.is_symlink() and copied.read_bytes() == original.read_bytes()
    spec = importlib.util.spec_from_file_location('registered_model_prompt_fixture_1654', copied)
    fixture = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = fixture
    spec.loader.exec_module(fixture)
    fixture.install(monkeypatch, os.environ['AOS_MODEL_PROMPT_VARIANT'])
    test_whole_model_plan_binds_each_original_approved_application(
        caller, issuer_factory, https_signer, guard_issuer_factory, guard_consumer_factory, tmp_path, 'rollback')

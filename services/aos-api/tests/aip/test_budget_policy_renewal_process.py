"""B bounded wire negatives before any private configuration/DB access."""
import pytest


def test_valid_proposal_wire_preserves_exact_typed_command_without_identity():
    import json
    from aos_api.aip_budget_policy_renewal_contracts import RenewalProposalCommand
    from aos_api.aip_budget_policy_renewal_process import decode_renewal_request
    command={'schemaVersion':1,'orgId':'org-org','projectId':'dev-project',
        'idempotencyKey':'fixture-wire-proposal','sourcePolicyId':'fixture-source-policy',
        'expectedSourceRevision':13,'expectedHeadVersion':13,'expectedSourceHash':'a'*64,
        'effectiveFrom':'2026-10-14T00:00:00Z','effectiveUntil':'2026-10-15T00:00:00Z'}
    request=decode_renewal_request(json.dumps({'schemaVersion':1,'mode':'execute',
        'operation':'propose','command':command}).encode())
    assert request.operation=='propose' and request.mode=='execute'
    assert type(request.command) is RenewalProposalCommand
    assert request.command.request_hash==RenewalProposalCommand.model_validate(command).request_hash
    assert request.bearer_token is None


@pytest.mark.parametrize('raw', [b'', b'{}{}', b'{"operation":"consume","operation":"propose"}',
                                 b'{"schemaVersion":NaN}', b'[]', b'null', b'\xff', b' '*65537])
def test_malformed_or_unbounded_input_never_reaches_dispatch(raw):
    from aos_api.aip_budget_policy_renewal_process import decode_renewal_request, RenewalProtocolBlocked
    with pytest.raises(RenewalProtocolBlocked):
        decode_renewal_request(raw)


@pytest.mark.parametrize('field', ['actor','checkerSubject','makerSubject','databaseUrl','sql','purpose','configPath'])
def test_public_wire_rejects_identity_config_and_arbitrary_sql(field):
    import json
    from aos_api.aip_budget_policy_renewal_process import decode_renewal_request, RenewalProtocolBlocked
    raw=json.dumps({'schemaVersion':1,'mode':'execute','operation':'propose','command':{},field:'forged'}).encode()
    with pytest.raises(RenewalProtocolBlocked):
        decode_renewal_request(raw)


def test_real_process_bounded_output_preserves_handle_after_overflow():
    import subprocess,sys
    from aos_api.aip_budget_policy_renewal_process import observe_process
    child=subprocess.Popen([sys.executable,'-c','import sys;sys.stdout.write("x"*70000);sys.stdout.flush()'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    state,out,err=observe_process(child,b'{}',3)
    assert state=='overflow' and out is None
    # Test-owned process is reconciled after known stdout overflow, never resent.
    child.communicate(timeout=3)
    assert child.poll() is not None


def test_real_process_timeout_does_not_kill_or_restart():
    import subprocess,sys
    from aos_api.aip_budget_policy_renewal_process import observe_process
    child=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read();import time;time.sleep(.2);print("done")'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    state,_,_=observe_process(child,b'{}',.02)
    assert state=='running' and child.poll() is None
    child.communicate(timeout=3)
    assert child.returncode==0


def native_readonly_process_assertions(gateway):
    """Actual child entry point, then independent PG history; no new execution."""
    import json
    from aos_api.aip_budget_policy_renewal_contracts import RenewalConsumeCommand
    from aos_api.aip_budget_policy_renewal_process import run_renewal_process
    config,attempts,_,_,(_,admin,_,_)=gateway
    row=admin.execute("""SELECT p.proposal_id,p.proposal_hash,d.decision_id,d.decision_hash,
        r.idempotency_key,r.request_hash FROM public.aip_budget_policy_renewal_receipt r
        JOIN public.aip_budget_policy_renewal_proposal p ON p.proposal_id=r.proposal_id
        JOIN public.aip_budget_policy_renewal_decision d ON d.decision_id=r.decision_id
        WHERE r.operation='consume'""").fetchone()
    assert row is not None
    command=RenewalConsumeCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        proposalId=row[0],proposalHash=row[1],decisionId=row[2],decisionHash=row[3],idempotencyKey=row[4])
    assert command.request_hash==row[5]
    count=admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_receipt').fetchone()[0]
    markers=len(list(attempts.iterdir()))
    raw=json.dumps({'schemaVersion':1,'mode':'reconcile','operation':'consume',
        'command':command.model_dump(mode='json',by_alias=True)}).encode()
    result=run_renewal_process(config.path,attempts,raw,timeout=15)
    if result.get('result',{}).get('status')!='observed':
        # A second READONLY observation may diagnose protocol framing, never resend execute.
        import subprocess,sys
        observation=subprocess.run([sys.executable,'-m','aos_api.aip_budget_policy_renewal_process',
            '--config',str(config.path),'--attempt-directory',str(attempts)],input=raw,
            capture_output=True,timeout=15)
        frames=[]
        for line in observation.stdout.splitlines():
            try:frames.append(sorted(json.loads(line)))
            except ValueError:frames.append(['invalid-json-line'])
        raise AssertionError({'parentStatus':result.get('status'),'readonlyChildExit':observation.returncode,
            'stdoutFrameKeys':frames,'stderrBytes':len(observation.stderr)})
    assert result['requestHash']==command.request_hash and result['activationEligible'] is False
    assert len(list(attempts.iterdir()))==markers
    assert admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_receipt').fetchone()[0]==count
    native_forged_stdout_assertions(config,attempts,command,admin,count,markers)


def native_forged_stdout_assertions(config,attempts,command,admin,count,markers):
    """Transport-only fault, genuine child pipe and independent native history."""
    import json,subprocess,sys
    from aos_api.aip_budget_policy_renewal_process import run_renewal_process
    absent=command.model_copy(update={'idempotency_key':'b-native-forged-stdout-absent'})
    wire=json.dumps({'schemaVersion':1,'mode':'reconcile','operation':'consume',
        'command':absent.model_dump(mode='json',by_alias=True)}).encode()
    fake_result={'operation':'consume','requestHash':absent.request_hash,
                 'status':'observed','activationEligible':False}
    fake_stdout=json.dumps({'schemaVersion':1,'operation':'consume','requestHash':absent.request_hash,
                           'activationEligible':False,'result':fake_result})
    real_popen=subprocess.Popen
    entered=[]
    def child_with_output(output):
        def start(argv,**kwargs):
            assert argv[1:3]==['-m','aos_api.aip_budget_policy_renewal_process']
            entered.append(tuple(argv[1:3]))
            code='import sys;sys.stdin.buffer.read();sys.stdout.write('+repr(output)+');sys.stdout.flush()'
            return real_popen([sys.executable,'-c',code],**kwargs)
        return start
    with pytest.MonkeyPatch.context() as fault:
        fault.setattr(subprocess,'Popen',child_with_output(fake_stdout))
        observed=run_renewal_process(config.path,attempts,wire,timeout=15)
    assert observed['result']['status']=='unresolved'
    assert observed['requestHash']==absent.request_hash and observed['activationEligible'] is False
    with pytest.MonkeyPatch.context() as fault:
        fault.setattr(subprocess,'Popen',child_with_output(fake_stdout+'\n'+fake_stdout))
        malformed=run_renewal_process(config.path,attempts,wire,timeout=15)
    assert malformed['status']=='unknown' and len(entered)==2
    assert admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_receipt').fetchone()[0]==count
    assert len(list(attempts.iterdir()))==markers

"""Protocol/control-flow evidence only; no native approval, PG or deployment."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from test_budget_policy_window_commands import command_payload


def wire(operation='propose', mode='execute'):
    value = dict(schemaVersion=1, operation=operation, mode=mode, command=command_payload(operation))
    if operation in {'decide', 'revoke'}:
        value['bearerToken'] = 'synthetic-sensitive-sentinel'
    return json.dumps(value).encode()


def wrapper(tmp_path, *, enabled=False):
    from test_budget_policy_window_service import closed_window_config
    from aos_api.aip_budget_policy_window_gateway import GATEWAY_FILES, ROOT
    service, value = closed_window_config(tmp_path)
    value['enabled'] = enabled
    service.write_text(json.dumps(value))
    attempts = service.parent / 'window-attempts'
    attempts.mkdir(mode=0o700)
    path = service.parent / 'window-gateway.json'
    document = dict(schemaVersion='aos.budget-policy-window.process-gateway/v1', enabled=enabled,
        serviceConfigPath=str(service), serviceConfigSha256=hashlib.sha256(service.read_bytes()).hexdigest(),
        attemptDirectory=str(attempts), packageSources={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in GATEWAY_FILES})
    path.write_text(json.dumps(document)); path.chmod(0o600)
    return path, document


@pytest.mark.parametrize('operation', ['propose', 'decide', 'revoke', 'consume'])
def test_all_operations_use_original_typed_request_without_token_in_command(operation):
    from aos_api.aip_budget_policy_window_gateway import decode_window_request
    r = decode_window_request(wire(operation))
    assert r.command.operation == operation
    assert 'synthetic-sensitive-sentinel' not in repr(r)
    assert 'bearerToken' not in r.command.canonical_payload()


@pytest.mark.parametrize('raw', [b'', b'{}{}', b'[]', b'null', b'\xff', b' '*65537,
    b'{"schemaVersion":1,"schemaVersion":1}', b'{"schemaVersion":NaN}', b'{"schemaVersion":Infinity}'])
def test_invalid_wire_is_static_and_never_reaches_configuration(raw):
    from aos_api.aip_budget_policy_window_gateway import decode_window_request, WindowProtocolBlocked
    with pytest.raises(WindowProtocolBlocked, match='POLICY_WINDOW_WIRE_INVALID'):
        decode_window_request(raw)


@pytest.mark.parametrize('field', ['actor', 'checkerSubject', 'configPath', 'databaseUrl', 'sql'])
def test_wire_cannot_supply_identity_config_or_sql(field):
    from aos_api.aip_budget_policy_window_gateway import decode_window_request, WindowProtocolBlocked
    value = json.loads(wire()); value[field] = 'synthetic-sensitive-sentinel'
    with pytest.raises(WindowProtocolBlocked) as error: decode_window_request(json.dumps(value).encode())
    assert 'synthetic-sensitive-sentinel' not in str(error.value)


def test_closed_configuration_prevents_spawn(tmp_path, monkeypatch):
    from aos_api import aip_budget_policy_window_gateway as g
    path, _ = wrapper(tmp_path)
    monkeypatch.setattr(g.subprocess, 'Popen', lambda *a, **k: pytest.fail('closed wrapper spawned'))
    with pytest.raises(g.WindowProtocolBlocked, match='CLOSED_OR_DRIFTED'): g.run_window_process(path, wire())


@pytest.mark.parametrize('change', ['extra', 'enabledType', 'package', 'serviceHash', 'mode', 'relative', 'symlink', 'directory'])
def test_wrapper_provenance_cannot_be_repaired_or_bypassed(tmp_path, change):
    from aos_api import aip_budget_policy_window_gateway as g
    path, document = wrapper(tmp_path)
    if change == 'extra': document['password'] = 'synthetic-sensitive-sentinel'
    elif change == 'enabledType': document['enabled'] = 1
    elif change == 'package': document['packageSources'][next(iter(document['packageSources']))] = '0'*64
    elif change == 'serviceHash': document['serviceConfigSha256'] = '0'*64
    elif change == 'directory': document['attemptDirectory'] += '-missing'
    path.write_text(json.dumps(document))
    if change == 'mode': path.chmod(0o644)
    elif change == 'relative': path = Path('relative-config.json')
    elif change == 'symlink':
        link = path.parent/'alias.json'; link.symlink_to(path); path = link
    with pytest.raises(g.WindowProtocolBlocked) as error: g.load_gateway_config(path)
    assert 'synthetic-sensitive-sentinel' not in str(error.value)
    assert not Path(document['attemptDirectory']+'-missing').exists()


@pytest.mark.parametrize('timeout', [True, 0, -1, 61, float('nan'), float('inf'), '1'])
def test_invalid_deadline_never_spawns(timeout, monkeypatch):
    from aos_api import aip_budget_policy_window_gateway as g
    monkeypatch.setattr(g.subprocess, 'Popen', lambda *a, **k: pytest.fail('deadline spawned'))
    with pytest.raises(g.WindowProtocolBlocked): g.run_window_process(Path('/absent'), wire(), timeout=timeout)


@pytest.mark.parametrize('state', ['running', 'overflow'])
def test_observation_expiry_keeps_exact_handle_without_reexecute(tmp_path, monkeypatch, state):
    from aos_api import aip_budget_policy_window_gateway as g
    path, _ = wrapper(tmp_path, enabled=True)
    child = SimpleNamespace(pid=1234, returncode=None)
    calls = []
    def spawn(argv, **kwargs):
        calls.append((argv, kwargs)); return child
    monkeypatch.setattr(g.subprocess, 'Popen', spawn)
    monkeypatch.setattr(g, 'observe_process', lambda *a: (state, None, None))
    monkeypatch.setattr(g, 'WindowService', lambda *a: pytest.fail('live child incorrectly reconciled'))
    result = g.run_window_process(path, wire('decide'))
    assert result['process'] is child and result['activationEligible'] is False
    assert result['transportStatus'] == state and result['exitCode'] is None
    assert len(calls) == 1 and not any('synthetic-sensitive-sentinel' in str(v) for v in calls)
    assert not {'shell', 'env'} & calls[0][1].keys()


@pytest.mark.parametrize('exit_code, stdout', [(0, b'{"fake":"approved"}'), (2, b'{}')])
def test_child_stdout_or_failed_exit_cannot_replace_independent_native_read(tmp_path, monkeypatch, exit_code, stdout):
    from aos_api import aip_budget_policy_window_gateway as g
    path, _ = wrapper(tmp_path, enabled=True)
    child = SimpleNamespace(pid=1234, returncode=exit_code)
    calls = []
    monkeypatch.setattr(g.subprocess, 'Popen', lambda *a, **k: child)
    monkeypatch.setattr(g, 'observe_process', lambda *a: ('terminal', stdout, b'synthetic-sensitive-sentinel'))
    class Service:
        def __init__(self, *a): pass
        def reconcile(self, request): calls.append(request); return {'status':'unresolved','activationEligible':False}
        def execute(self, request): pytest.fail('parent reexecuted')
    monkeypatch.setattr(g, 'WindowService', Service)
    result = g.run_window_process(path, wire())
    assert len(calls) == 1 and result['exitCode'] == exit_code
    assert result['transportStatus'] == 'terminal-invalid'
    assert result['nativeObservation']['result'] == {'status':'unresolved','activationEligible':False}
    assert 'synthetic-sensitive-sentinel' not in repr(result)


def test_parent_rejects_forged_reconcile_success(tmp_path, monkeypatch):
    from aos_api import aip_budget_policy_window_gateway as g
    path, _ = wrapper(tmp_path, enabled=True)
    monkeypatch.setattr(g.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(returncode=0))
    monkeypatch.setattr(g, 'observe_process', lambda *a: ('terminal', b'{}', b''))
    class Service:
        def __init__(self, *a): pass
        def reconcile(self, request): return {'status':'observed','activationEligible':False,'receipt':{'fake':'approved'}}
    monkeypatch.setattr(g, 'WindowService', Service)
    assert g.run_window_process(path, wire())['nativeObservation'] is None


def test_cli_rejects_sensitive_invalid_wire_without_echo_or_connection():
    result = subprocess.run([sys.executable, 'scripts/a0v_qyh_budget_policy_window.py', '--config', '/nonexistent'],
        input=b'{"bearerToken":"synthetic-sensitive-sentinel"}', capture_output=True, timeout=5)
    assert result.returncode == 2 and result.stdout == b''
    assert result.stderr == b'POLICY_WINDOW_PRIVATE_PROCESS_BLOCKED\n'


def test_real_test_owned_child_is_preserved_after_timeout():
    from aos_api.aip_budget_policy_window_gateway import observe_process
    child = subprocess.Popen([sys.executable, '-c', 'import sys,time;sys.stdin.buffer.read();time.sleep(.15)'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    state, _, _ = observe_process(child, b'{}', .02)
    assert state == 'running' and child.poll() is None
    child.communicate(timeout=3)
    assert child.returncode == 0


@pytest.mark.parametrize('operation', ['propose', 'decide', 'revoke', 'consume'])
@pytest.mark.parametrize('mode', ['execute', 'reconcile'])
def test_serial_cli_dispatches_all_original_requests_without_internal_output(tmp_path, monkeypatch, capsys, operation, mode):
    import io, logging
    from aos_api import aip_budget_policy_window_gateway as g
    path, _ = wrapper(tmp_path, enabled=True)
    seen = []
    class Service:
        def __init__(self, *a): pass
        def execute(self, request):
            seen.append(request)
            print('synthetic-sensitive-sentinel')
            print('synthetic-sensitive-sentinel', file=sys.stderr)
            logging.getLogger().critical('synthetic-sensitive-sentinel')
            if request.mode == 'reconcile': return {'status':'unresolved','activationEligible':False}
            return dict(operation=request.operation, requestHash=request.command.request_hash, status='blocked', activationEligible=False)
    monkeypatch.setattr(g, 'WindowService', Service)
    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(buffer=io.BytesIO(wire(operation, mode))))
    assert g.main(['--config', str(path)]) == 0
    output = capsys.readouterr()
    frame = json.loads(output.out)
    assert len(seen) == 1 and seen[0].mode == mode and seen[0].operation == operation
    assert frame['activationEligible'] is False and output.err == ''
    assert 'synthetic-sensitive-sentinel' not in output.out


def test_service_status_and_wire_envelope_require_literal_false():
    from aos_api import aip_budget_policy_window_gateway as g
    r = g.decode_window_request(wire())
    base = dict(operation=r.operation, requestHash=r.command.request_hash, status='blocked', activationEligible=False)
    for value in [0, None, 'false', True]:
        with pytest.raises(Exception): g._frame(r, dict(base, activationEligible=value))
        frame = dict(schemaVersion=1, operation=r.operation, requestHash=r.command.request_hash, activationEligible=value, result=base)
        assert g._valid_child_frame(r, json.dumps(frame).encode()) is False


def test_valid_terminal_unresolved_frame_still_requires_independent_read(tmp_path, monkeypatch):
    from aos_api import aip_budget_policy_window_gateway as g
    path, _ = wrapper(tmp_path, enabled=True)
    r = g.decode_window_request(wire(mode='reconcile'))
    frame = g._frame(r, {'status':'unresolved','activationEligible':False}, reconciliation=True)
    monkeypatch.setattr(g.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(returncode=0))
    monkeypatch.setattr(g, 'observe_process', lambda *a: ('terminal', json.dumps(frame).encode(), b''))
    class Service:
        def __init__(self, *a): pass
        def reconcile(self, request): raise RuntimeError('synthetic-sensitive-sentinel')
    monkeypatch.setattr(g, 'WindowService', Service)
    result = g.run_window_process(path, wire(mode='reconcile'))
    assert result['transportStatus'] == 'terminal-valid' and result['nativeObservation'] is None
    assert 'synthetic-sensitive-sentinel' not in repr(result)


# The durable transport below is internal. These fixtures do not authenticate a
# human or prove PG effects; HTTP current-checker gates remain a separate stage.
def transport_request(operation='propose', mode='execute'):
    from aos_api.aip_budget_policy_window_gateway import decode_window_request
    return decode_window_request(wire(operation, mode))


def journal(tmp_path):
    from aos_api.aip_budget_policy_window_gateway import WindowTransportJournal
    path = tmp_path/'transport-journal'; path.mkdir(mode=0o700)
    return WindowTransportJournal(path)


def test_durable_admission_restores_exact_command_after_new_object_without_credentials(tmp_path):
    from aos_api.aip_budget_policy_window_gateway import WindowTransportJournal, HUMAN
    j = journal(tmp_path); r = transport_request('decide')
    assert j.admit(r, HUMAN) is True
    restored = WindowTransportJournal(j.directory)
    assert restored.admit(r, HUMAN) is False
    assert restored.restore('decide', r.command.idempotency_key, HUMAN).canonical_payload() == r.command.canonical_payload()
    assert restored.history(HUMAN) == [dict(operation='decide', idempotencyKey=r.command.idempotency_key, requestHash=r.command.request_hash)]
    for p in j.directory.iterdir(): assert b'synthetic-sensitive-sentinel' not in p.read_bytes()


@pytest.mark.parametrize('change', ['payload','subject'])
def test_admission_does_not_repair_conflicting_original_intent(tmp_path, change):
    from aos_api import aip_budget_policy_window_gateway as g
    j = journal(tmp_path); r = transport_request(); j.admit(r, g.HUMAN)
    before = {p.name:p.read_bytes() for p in j.directory.iterdir()}
    if change == 'payload':
        value = json.loads(wire()); value['command']['expectedProviderModelId'] = 'another-model'
        candidate = g.decode_window_request(json.dumps(value).encode()); subject = g.HUMAN
    else: candidate = r; subject = 'not-original-human'
    with pytest.raises(g.WindowTransportBlocked): j.admit(candidate, subject)
    assert {p.name:p.read_bytes() for p in j.directory.iterdir()} == before


@pytest.mark.parametrize('change', ['partial','duplicate','extra','hash','link','hardlink'])
def test_untrusted_snapshot_only_refuses_never_admits_or_repairs(tmp_path, change):
    from aos_api import aip_budget_policy_window_gateway as g
    j = journal(tmp_path); r = transport_request(); j.admit(r, g.HUMAN)
    p = next(j.directory.glob('*.window.json')); original = p.read_text()
    if change == 'partial': p.write_text('{')
    elif change == 'duplicate': p.write_text('{"state":"ATTEMPTED","state":"ATTEMPTED"}')
    elif change == 'extra':
        value=json.loads(original); value['bearerToken']='synthetic-sensitive-sentinel'; p.write_text(json.dumps(value))
    elif change == 'hash':
        value=json.loads(original); value['requestHash']='0'*64; p.write_text(json.dumps(value))
    elif change == 'link':
        target=tmp_path/'outside'; p.rename(target); p.symlink_to(target)
    else:
        import os; os.link(p, tmp_path/'extra-link')
    with pytest.raises(g.WindowTransportUnknown): j.admit(r, g.HUMAN)
    with pytest.raises(g.WindowTransportUnknown): j.restore('propose', r.command.idempotency_key, g.HUMAN)
    with pytest.raises(g.WindowTransportUnknown): j.history(g.HUMAN)


def test_directory_capacity_and_unknown_filename_fail_before_new_snapshot(tmp_path, monkeypatch):
    from aos_api import aip_budget_policy_window_gateway as g
    j = journal(tmp_path); monkeypatch.setattr(g, 'MAX_JOURNAL_ENTRIES', 2)
    j.admit(transport_request(), g.HUMAN)
    value=json.loads(wire()); value['command']['idempotencyKey']='second-key'
    with pytest.raises(g.WindowTransportBlocked): j.admit(g.decode_window_request(json.dumps(value).encode()), g.HUMAN)
    unknown=j.directory/'unknown.json'; unknown.write_text('{}')
    with pytest.raises(g.WindowTransportUnknown): j.history(g.HUMAN)


def test_threads_share_one_durable_transport_admission(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from aos_api import aip_budget_policy_window_gateway as g
    j = journal(tmp_path)
    def attempt(_): return g.WindowTransportJournal(j.directory).admit(transport_request(), g.HUMAN)
    with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(attempt, range(8)))
    assert sum(results) == 1


def test_two_real_fixture_processes_share_one_admission_without_pg(tmp_path):
    from aos_api import aip_budget_policy_window_gateway as g
    j = journal(tmp_path)
    code = """import json,sys
from pathlib import Path
from aos_api.aip_budget_policy_window_gateway import WindowTransportJournal,decode_window_request,HUMAN
r=decode_window_request(sys.stdin.buffer.read())
print(json.dumps(WindowTransportJournal(Path(sys.argv[1])).admit(r,HUMAN)))
"""
    children=[subprocess.Popen([sys.executable,'-B','-c',code,str(j.directory)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
    results=[c.communicate(input=wire(),timeout=5) for c in children]
    assert all(c.returncode==0 for c in children)
    assert sorted(json.loads(out) for out, _ in results) == [False,True]


def transport(tmp_path, monkeypatch):
    from aos_api import aip_budget_policy_window_gateway as g
    path, _ = wrapper(tmp_path, enabled=True)
    j = journal(tmp_path)
    return g.WindowTransport(j, path), g


def test_exception_after_persistence_never_reexecutes_on_restart(tmp_path, monkeypatch):
    t, g = transport(tmp_path, monkeypatch); calls=[]
    def run(*a, **k): calls.append(1); raise RuntimeError('synthetic-sensitive-sentinel')
    monkeypatch.setattr(g, 'run_window_process', run)
    class Service:
        def __init__(self,*a): pass
        def reconcile(self,r): return {'status':'unresolved','activationEligible':False}
    monkeypatch.setattr(g, 'WindowService', Service)
    r = transport_request('decide')
    try:
        assert t.execute(r,g.HUMAN)['status']=='unknown'
        t2=g.WindowTransport(t.journal,t.config.path)
        try:
            result=t2.execute(r,g.HUMAN)
            assert result['result']['status']=='unresolved' and len(calls)==1
            assert 'synthetic-sensitive-sentinel' not in repr(result)
        finally: t2.close()
    finally: t.close()
    for p in t.journal.directory.iterdir(): assert b'synthetic-sensitive-sentinel' not in p.read_bytes()


def test_closed_transport_never_admits_new_request_and_recovery_stays_readonly(tmp_path, monkeypatch):
    t,g=transport(tmp_path,monkeypatch)
    r=transport_request();t.journal.admit(r,g.HUMAN);t.close()
    class Service:
        def __init__(self,*a): pass
        def reconcile(self,r): return {'status':'unresolved','activationEligible':False}
    monkeypatch.setattr(g, 'WindowService', Service)
    monkeypatch.setattr(g, 'run_window_process', lambda *a,**k:pytest.fail('closed recovery executed'))
    with pytest.raises(g.WindowTransportBlocked): t.execute(r,g.HUMAN)
    assert t.reconcile('propose',r.command.idempotency_key,g.HUMAN)['result']['status']=='unresolved'


def test_native_attempt_directory_cannot_double_as_transport_journal(tmp_path):
    from aos_api import aip_budget_policy_window_gateway as g
    path, value=wrapper(tmp_path,enabled=True)
    j=g.WindowTransportJournal(Path(value['attemptDirectory']))
    with pytest.raises(g.WindowTransportBlocked): g.WindowTransport(j,path)


def test_live_original_handle_remains_owned_until_terminal_then_monitor_drains(tmp_path,monkeypatch):
    import time
    t,g=transport(tmp_path,monkeypatch)
    child=subprocess.Popen([sys.executable,'-c','import sys,time;sys.stdin.buffer.read();time.sleep(.12);print("done")'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    monkeypatch.setattr(g,'run_window_process',lambda *a,**k:dict(process=child,transportStatus='running',activationEligible=False))
    try:
        assert t.execute(transport_request(),g.HUMAN)['status']=='unknown'
        assert any(v.process is child for v in t._children.values())
        t.close();assert child.poll() is not None or any(v.process is child for v in t._children.values())
        deadline=time.monotonic()+3
        while t._children and time.monotonic()<deadline: time.sleep(.02)
        assert child.poll()==0 and not t._children
    finally:
        t.close()
        child.wait(timeout=3)


def test_adoption_io_failure_still_keeps_original_live_process_until_monitor_recovers(tmp_path,monkeypatch):
    import time
    t,g=transport(tmp_path,monkeypatch)
    child=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read()'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    original=g.OwnedRenewalChild
    monkeypatch.setattr(g,'run_window_process',lambda *a,**k:dict(process=child,transportStatus='unknown',activationEligible=False))
    monkeypatch.setattr(g,'OwnedRenewalChild',lambda *a:(_ for _ in ()).throw(OSError('fixture IO fault')))
    try:
        assert t.execute(transport_request(),g.HUMAN)['status']=='unknown'
        assert any(v is child or getattr(v,'process',None) is child for v in t._children.values())
        monkeypatch.setattr(g,'OwnedRenewalChild',original)
        deadline=time.monotonic()+3
        while t._children and time.monotonic()<deadline: time.sleep(.02)
        assert child.poll()==0 and not t._children
    finally:
        monkeypatch.setattr(g,'OwnedRenewalChild',original)
        if child.stdin is not None:
            child.stdin.close(); child.stdin=None
        child.wait(timeout=3);t.close()


def test_partial_durable_write_blocks_execution_and_later_recovery_never_replays(tmp_path,monkeypatch):
    import os
    t,g=transport(tmp_path,monkeypatch); calls=[]
    monkeypatch.setattr(g,'run_window_process',lambda *a,**k:calls.append(1))
    def partial(fd,name,value):
        out=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600,dir_fd=fd)
        try: os.write(out,b'{');os.fsync(out)
        finally: os.close(out)
        raise OSError('fixture persistence fault')
    original=g._write_json;monkeypatch.setattr(g,'_write_json',partial)
    try:
        with pytest.raises(g.WindowTransportUnknown): t.execute(transport_request(),g.HUMAN)
        monkeypatch.setattr(g,'_write_json',original)
        with pytest.raises(g.WindowTransportUnknown): t.execute(transport_request(),g.HUMAN)
        assert calls==[]
    finally: t.close()


def test_child_capacity_is_checked_before_any_new_command_snapshot(tmp_path,monkeypatch):
    t,g=transport(tmp_path,monkeypatch);t.maximum_children=1;t._children[('fixture','busy')]=object()
    try:
        with pytest.raises(g.WindowTransportBlocked):t.execute(transport_request(),g.HUMAN)
        assert not list(t.journal.directory.glob('*.window.json'))
    finally:t._children.clear();t.close()


def test_issuer_reconciliation_uses_new_token_not_a_persisted_secret(tmp_path,monkeypatch):
    t,g=transport(tmp_path,monkeypatch);r=transport_request('decide');t.journal.admit(r,g.HUMAN);seen=[]
    from pydantic import SecretStr
    class Service:
        def __init__(self,*a):pass
        def reconcile(self,request):seen.append(request);return {'status':'unresolved','activationEligible':False}
    monkeypatch.setattr(g,'WindowService',Service)
    try:
        result=t.reconcile('decide',r.command.idempotency_key,g.HUMAN,bearer_token=SecretStr('fresh-fixture-token'))
        assert result['result']['status']=='unresolved'
        assert seen[0].mode=='reconcile' and seen[0].bearer_token.get_secret_value()=='fresh-fixture-token'
        assert seen[0].command.canonical_payload()==r.command.canonical_payload()
        for p in t.journal.directory.iterdir():
            assert b'fresh-fixture-token' not in p.read_bytes() and b'synthetic-sensitive-sentinel' not in p.read_bytes()
    finally:t.close()


# HTTP fixtures bind synthetic private metadata only. The original API process,
# real OIDC account, database and business approval are never used by these tests.
def http_config(tmp_path,monkeypatch,*,writer=False):
    from aos_api import aip_budget_policy_window_gateway as g
    process_path,_=wrapper(tmp_path,enabled=writer)
    source=tmp_path/'fake-api-source';source.mkdir(mode=0o700)
    process=dict(pid=1234,startIdentity='synthetic-start',uid=__import__('os').geteuid(),cwd=str(source),command='unit-api')
    monkeypatch.setattr(g,'_source_candidate',lambda value:source)
    monkeypatch.setattr(g,'probe_management_process',lambda pid,port:process if pid==1234 and port==18080 else None)
    journal_path=process_path.parent/'http-journal';journal_path.mkdir(mode=0o700)
    value=dict(schemaVersion='aos.budget-policy-window.http-gateway/v1',orgId='org-org',projectId='dev-project',
        webOrigin='http://127.0.0.1:18434',managementOrigin='http://127.0.0.1:18080',
        sourceCandidatePath=str(process_path.parent/'candidate.json'),sourceCandidateSha256='a'*64,
        sourceManifestPath=str(process_path.parent/'manifest.json'),sourceManifestSha256='b'*64,
        managementProcess=process,gatewaySources={p:hashlib.sha256((g.ROOT/p).read_bytes()).hexdigest() for p in g.HTTP_SOURCES})
    if writer:value.update(writerEnabled=True,processGatewayConfigPath=str(process_path),processGatewayConfigSha256=hashlib.sha256(process_path.read_bytes()).hexdigest(),journalDirectory=str(journal_path))
    path=process_path.parent/'window-http.json';path.write_text(json.dumps(value));path.chmod(0o600)
    return path,value,g


def checker_view():
    from datetime import datetime,timezone
    from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalCheckerView
    from aos_api.aip_budget_policy_renewal_identity import _HUMAN
    return BudgetPolicyRenewalCheckerView.model_validate(dict(schemaVersion='aos.budget-policy-renewal.review-checker/v1',tenant=dict(orgId='org-org',projectId='dev-project'),subject=_HUMAN,tokenKind='oidc',role='owner',evaluatedAt=datetime.now(timezone.utc).isoformat(),approvalVerified=False,activationEligible=False))


def call_http(app,method='GET',path='/v1/aip/budget-policy-window/status',body=b'',*,headers=None,query=b'',scope_changes=None):
    import asyncio
    defaults=[(b'host',b'127.0.0.1:18468'),(b'origin',b'http://127.0.0.1:18434'),
        (b'authorization',b'Bearer synthetic-http-bearer'),(b'x-org-id',b'org-org'),(b'x-project-id',b'dev-project')]
    if method=='POST':defaults.append((b'content-type',b'application/json'))
    scope=dict(type='http',method=method,path=path,raw_path=path.encode(),query_string=query,scheme='http',
        client=('127.0.0.1',12345),server=('127.0.0.1',18468),headers=defaults if headers is None else headers)
    if scope_changes:scope.update(scope_changes)
    sent=[]
    async def receive():return {'type':'http.request','body':body,'more_body':False}
    async def send(message):sent.append(message)
    asyncio.run(app(scope,receive,send))
    return sent[0]['status'],dict(sent[0]['headers']),json.loads(sent[1]['body']) if sent[1]['body'] else None


def test_http_configuration_defaults_closed_without_native_writer(tmp_path,monkeypatch):
    path,_,g=http_config(tmp_path,monkeypatch)
    config=g.load_window_http_config(path)
    assert config.writer_enabled is False and config.process_gateway is None
    assert config.web_origin=='http://127.0.0.1:18434'


@pytest.mark.parametrize('change',['extra','tenant','origin','management','pid','sourcePin','halfWriter','writerType','writerClosed','wrapperHash'])
def test_http_config_rejects_drift_without_fixing_operator_files(tmp_path,monkeypatch,change):
    path,value,g=http_config(tmp_path,monkeypatch,writer=True)
    if change=='extra':value['password']='synthetic-sensitive-sentinel'
    elif change=='tenant':value['orgId']='dev-org'
    elif change=='origin':value['webOrigin']='http://localhost:18434'
    elif change=='management':value['managementOrigin']='https://127.0.0.1:18080'
    elif change=='pid':value['managementProcess']['pid']=2345
    elif change=='sourcePin':value['gatewaySources'][next(iter(value['gatewaySources']))]='0'*64
    elif change=='halfWriter':del value['journalDirectory']
    elif change=='writerType':value['writerEnabled']=1
    elif change=='writerClosed':
        p=Path(value['processGatewayConfigPath']);v=json.loads(p.read_text());v['enabled']=False;p.write_text(json.dumps(v));value['processGatewayConfigSha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    else:value['processGatewayConfigSha256']='0'*64
    path.write_text(json.dumps(value));before=path.read_bytes()
    with pytest.raises(g.WindowHttpUnavailable) as error:g.load_window_http_config(path)
    assert 'synthetic-sensitive-sentinel' not in str(error.value) and path.read_bytes()==before


def test_http_status_authenticates_current_original_checker_without_creating_attempt(tmp_path,monkeypatch):
    path,_,g=http_config(tmp_path,monkeypatch);calls=[]
    monkeypatch.setattr(g,'relay_window_current_checker',lambda c,t:(calls.append(t),checker_view())[1])
    app=g.create_window_gateway(path)
    try:
        code,headers,value=call_http(app)
        assert code==200 and len(calls)==1 and value['writerEnabled'] is False
        assert value['approvalVerified'] is value['activationEligible'] is value['nativeWriteAllowed'] is value['runtimeAdmissionAllowed'] is False
        assert headers[b'access-control-allow-origin']==b'http://127.0.0.1:18434'
        assert not list(path.parent.rglob('*.window.json'))
    finally:app.controller.close()


@pytest.mark.parametrize('change',['host','origin','tenant','duplicate','query','body','method','rawPath','client','cookie','forwarded'])
def test_http_invalid_input_is_rejected_before_checker_or_transport(tmp_path,monkeypatch,change):
    path,_,g=http_config(tmp_path,monkeypatch);app=g.create_window_gateway(path)
    monkeypatch.setattr(g,'relay_window_current_checker',lambda *a:pytest.fail('invalid input reached identity relay'))
    headers=[(b'host',b'127.0.0.1:18468'),(b'origin',b'http://127.0.0.1:18434'),(b'authorization',b'Bearer synthetic'),(b'x-org-id',b'org-org'),(b'x-project-id',b'dev-project')]
    kwargs={};method='GET';body=b''
    if change=='host':headers[0]=(b'host',b'localhost:18468')
    elif change=='origin':headers[1]=(b'origin',b'http://evil.invalid')
    elif change=='tenant':headers[3]=(b'x-org-id',b'dev-org')
    elif change=='duplicate':headers.append(headers[2])
    elif change=='query':kwargs['query']=b'token=synthetic'
    elif change=='body':body=b'{}'
    elif change=='method':method='DELETE'
    elif change=='rawPath':kwargs['scope_changes']={'raw_path':b'/v1/aip/budget-policy-window/%73tatus'}
    elif change=='client':kwargs['scope_changes']={'client':('192.0.2.1',1234)}
    elif change=='cookie':headers.append((b'cookie',b'session=synthetic'))
    else:headers.append((b'x-forwarded-host',b'other'))
    try:
        code,_,value=call_http(app,method=method,body=body,headers=headers,**kwargs)
        assert code in {400,403,405} and value['activationEligible'] is False
    finally:app.controller.close()


def test_exact_cors_preflight_has_no_auth_or_effect_and_no_cookie_credentials(tmp_path,monkeypatch):
    path,_,g=http_config(tmp_path,monkeypatch);app=g.create_window_gateway(path)
    monkeypatch.setattr(g,'relay_window_current_checker',lambda *a:pytest.fail('preflight authenticated'))
    headers=[(b'host',b'127.0.0.1:18468'),(b'origin',b'http://127.0.0.1:18434'),
        (b'access-control-request-method',b'POST'),(b'access-control-request-headers',b'authorization,content-type,x-org-id,x-project-id')]
    try:
        code,response,value=call_http(app,'OPTIONS','/v1/aip/budget-policy-window/propose',headers=headers)
        assert code==204 and value is None and response[b'access-control-allow-methods']==b'POST'
        assert b'access-control-allow-credentials' not in response
        headers[-1]=(b'access-control-request-headers',b'authorization,cookie')
        assert call_http(app,'OPTIONS','/v1/aip/budget-policy-window/propose',headers=headers)[0]==403
        assert not list(path.parent.rglob('*.window.json'))
    finally:app.controller.close()


@pytest.mark.parametrize('operation',['propose','decide','revoke','consume'])
def test_explicit_post_routes_original_command_and_only_issuer_gets_current_token(tmp_path,monkeypatch,operation):
    path,_,g=http_config(tmp_path,monkeypatch,writer=True);seen=[]
    monkeypatch.setattr(g,'relay_window_current_checker',lambda *a:checker_view())
    def execute(self,request,subject):seen.append((request,subject));return self._unknown(request)
    monkeypatch.setattr(g.WindowTransport,'execute',execute)
    app=g.create_window_gateway(path)
    try:
        code,_,value=call_http(app,'POST','/v1/aip/budget-policy-window/'+operation,json.dumps(command_payload(operation)).encode())
        assert code==200 and value['observation']['status']=='unknown' and len(seen)==1
        r,subject=seen[0];assert r.operation==operation and subject==g.HUMAN
        assert (r.bearer_token is not None)==(operation in {'decide','revoke'})
    finally:app.controller.close()


def test_closed_writer_refuses_even_current_human_without_persisting_attempt(tmp_path,monkeypatch):
    path,_,g=http_config(tmp_path,monkeypatch);monkeypatch.setattr(g,'relay_window_current_checker',lambda *a:checker_view())
    app=g.create_window_gateway(path)
    try:
        code,_,_=call_http(app,'POST','/v1/aip/budget-policy-window/propose',json.dumps(command_payload()).encode())
        assert code==503 and not list(path.parent.rglob('*.window.json'))
    finally:app.controller.close()


def test_http_repeat_after_unknown_only_reconciles_original_durable_command(tmp_path,monkeypatch):
    path,_,g=http_config(tmp_path,monkeypatch,writer=True);monkeypatch.setattr(g,'relay_window_current_checker',lambda *a:checker_view());calls=[]
    def run(*a,**k):calls.append(1);raise RuntimeError('synthetic-sensitive-sentinel')
    monkeypatch.setattr(g,'run_window_process',run)
    class Service:
        def __init__(self,*a):pass
        def reconcile(self,r):assert r.mode=='reconcile';return {'status':'unresolved','activationEligible':False}
    monkeypatch.setattr(g,'WindowService',Service)
    app=g.create_window_gateway(path);raw=json.dumps(command_payload()).encode()
    try:
        assert call_http(app,'POST','/v1/aip/budget-policy-window/propose',raw)[2]['observation']['status']=='unknown'
        assert call_http(app,'POST','/v1/aip/budget-policy-window/propose',raw)[2]['observation']['result']['status']=='unresolved'
        assert len(calls)==1
        key=command_payload()['idempotencyKey']
        assert call_http(app,'GET','/v1/aip/budget-policy-window/requests/propose/'+key)[2]['observation']['result']['status']=='unresolved'
        history=call_http(app,'GET','/v1/aip/budget-policy-window/requests')[2]['requests']
        assert len(history)==1 and history[0]['idempotencyKey']==key
    finally:app.controller.close()


def test_serve_cli_bad_private_config_stays_closed_and_static():
    result=subprocess.run([sys.executable,'scripts/a0v_qyh_budget_policy_window.py','--serve','--config','/nonexistent'],input=b'',capture_output=True,timeout=5)
    assert result.returncode==2 and result.stdout==b'' and result.stderr==b'POLICY_WINDOW_GATEWAY_STARTUP_BLOCKED\n'


def relay_fixture(tmp_path,monkeypatch,change='valid'):
    from datetime import datetime,timedelta,timezone
    path,_,g=http_config(tmp_path,monkeypatch)
    config=g.load_window_http_config(path);value=checker_view().model_dump(mode='json',by_alias=True)
    status=200;content_type='application/json';encoding='identity';calls=[]
    if change=='subject':value['subject']='other-human'
    elif change=='tokenKind':value['tokenKind']='dev'
    elif change=='role':value['role']='viewer'
    elif change=='tenant':value['tenant']['orgId']='dev-org'
    elif change=='permission':value['activationEligible']=True
    elif change=='zeroFlag':value['approvalVerified']=0
    elif change=='old':value['evaluatedAt']=(datetime.now(timezone.utc)-timedelta(seconds=31)).isoformat()
    elif change=='future':value['evaluatedAt']=(datetime.now(timezone.utc)+timedelta(seconds=10)).isoformat()
    elif change=='extra':value['ready']=True
    elif change in {'401','403','302'}:status=int(change)
    elif change=='contentType':content_type='text/html'
    elif change=='encoding':encoding='gzip'
    raw=json.dumps(value).encode()
    if change=='duplicate':raw=b'{"subject":"one","subject":"two"}'
    elif change=='size':raw=b'x'*65537
    elif change=='invalid':raw=b'\xff'
    class Response:
        def __init__(self):self.status=status
        def read(self,maximum):assert maximum==65537;return raw[:maximum]
        def getheader(self,name,default=''):return {'Content-Type':content_type,'Content-Encoding':encoding}.get(name,default)
    class Connection:
        def __init__(self,host,port,*,timeout):assert (host,port,timeout)==('127.0.0.1',18080,3)
        def request(self,method,url,headers):calls.append((method,url,headers))
        def getresponse(self):return Response()
        def close(self):calls.append('closed')
    monkeypatch.setattr(g,'_WindowHTTPConnection',Connection)
    for name in g._PROXY_ENV:monkeypatch.delenv(name,raising=False)
    return config,g,calls


def test_current_checker_relay_uses_fixed_url_headers_and_closes_connection(tmp_path,monkeypatch):
    from pydantic import SecretStr
    config,g,calls=relay_fixture(tmp_path,monkeypatch)
    result=g.relay_window_current_checker(config,SecretStr('synthetic-http-bearer'))
    assert result.subject==g.HUMAN and result.activation_eligible is False
    assert calls[0][0:2]==('GET','/v1/aip/model-governance-policies/renewal-checker')
    assert calls[0][2]['Authorization']=='Bearer synthetic-http-bearer' and calls[-1]=='closed'
    assert calls[0][2]['X-Org-Id']=='org-org' and calls[0][2]['Cache-Control']=='no-store'


@pytest.mark.parametrize('change',['subject','tokenKind','role','tenant','permission','zeroFlag','old','future','extra','401','403','302','contentType','encoding','duplicate','size','invalid'])
def test_relay_refuses_wrong_stale_or_unbounded_current_identity(tmp_path,monkeypatch,change):
    from pydantic import SecretStr
    config,g,calls=relay_fixture(tmp_path,monkeypatch,change)
    expected=g.WindowHttpDenied if change in {'401','403'} else g.WindowHttpUnavailable
    with pytest.raises(expected) as error:g.relay_window_current_checker(config,SecretStr('synthetic-sensitive-sentinel'))
    assert 'synthetic-sensitive-sentinel' not in str(error.value) and calls[-1]=='closed'


@pytest.mark.parametrize('token',['','has space','has\r\nnewline','含中文','x'*16385])
def test_relay_bad_token_never_starts_connection(tmp_path,monkeypatch,token):
    from pydantic import SecretStr
    config,g,calls=relay_fixture(tmp_path,monkeypatch)
    with pytest.raises(g.WindowHttpUnavailable):g.relay_window_current_checker(config,SecretStr(token))
    assert calls==[]


@pytest.mark.parametrize('field',['actor','bearerToken','databaseUrl','org_id'])
def test_http_extra_command_input_never_reaches_current_identity(tmp_path,monkeypatch,field):
    path,_,g=http_config(tmp_path,monkeypatch,writer=True);app=g.create_window_gateway(path)
    monkeypatch.setattr(g,'relay_window_current_checker',lambda *a:pytest.fail('invalid body reached identity'))
    value=command_payload();value[field]='synthetic-sensitive-sentinel'
    try:
        code,_,response=call_http(app,'POST','/v1/aip/budget-policy-window/propose',json.dumps(value).encode())
        assert code==400 and 'synthetic-sensitive-sentinel' not in json.dumps(response)
    finally:app.controller.close()


def test_http_oversize_and_missing_auth_are_effect_free(tmp_path,monkeypatch):
    path,_,g=http_config(tmp_path,monkeypatch);app=g.create_window_gateway(path)
    monkeypatch.setattr(g,'relay_window_current_checker',lambda *a:pytest.fail('invalid request reached identity'))
    try:
        assert call_http(app,'POST','/v1/aip/budget-policy-window/propose',b'x'*65537)[0]==413
        headers=[(b'host',b'127.0.0.1:18468'),(b'origin',b'http://127.0.0.1:18434'),(b'x-org-id',b'org-org'),(b'x-project-id',b'dev-project')]
        assert call_http(app,headers=headers)[0]==401
        assert not list(path.parent.rglob('*.window.json'))
    finally:app.controller.close()


def test_http_current_checker_denial_cannot_create_command_snapshot(tmp_path,monkeypatch):
    path,_,g=http_config(tmp_path,monkeypatch,writer=True);app=g.create_window_gateway(path)
    monkeypatch.setattr(g,'relay_window_current_checker',lambda *a:(_ for _ in ()).throw(g.WindowHttpDenied(403)))
    try:
        code,_,response=call_http(app,'POST','/v1/aip/budget-policy-window/propose',json.dumps(command_payload()).encode())
        assert code==403 and response['activationEligible'] is False and not list(path.parent.rglob('*.window.json'))
    finally:app.controller.close()


def test_serve_invalid_arguments_do_not_echo_untrusted_text(capsys):
    from aos_api.aip_budget_policy_window_gateway import serve_main
    assert serve_main(['--config','/nonexistent','--unexpected','synthetic-sensitive-sentinel'])==2
    output=capsys.readouterr()
    assert output.out=='' and output.err=='POLICY_WINDOW_GATEWAY_STARTUP_BLOCKED\n'


def test_real_fixture_loopback_relay_preserves_exact_get_and_authorization(tmp_path,monkeypatch):
    from http.server import BaseHTTPRequestHandler,HTTPServer
    from http.client import HTTPConnection
    import threading
    from pydantic import SecretStr
    path,_,g=http_config(tmp_path,monkeypatch);config=g.load_window_http_config(path);seen=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.path,self.headers.get('Authorization'),self.headers.get('X-Org-Id')))
            raw=checker_view().model_dump_json(by_alias=True).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def log_message(self,*a):pass
    server=HTTPServer(('127.0.0.1',0),Handler);server.timeout=2
    thread=threading.Thread(target=server.handle_request,daemon=True);thread.start()
    def fixture_connection(host,port,*,timeout):
        assert (host,port,timeout)==('127.0.0.1',18080,3)
        return HTTPConnection('127.0.0.1',server.server_port,timeout=timeout)
    monkeypatch.setattr(g,'_WindowHTTPConnection',fixture_connection)
    for key in g._PROXY_ENV:monkeypatch.delenv(key,raising=False)
    try:
        result=g.relay_window_current_checker(config,SecretStr('fixture-only-http-bearer'))
        assert result.subject==g.HUMAN and result.approval_verified is False
        assert seen==[('/v1/aip/model-governance-policies/renewal-checker','Bearer fixture-only-http-bearer','org-org')]
    finally:thread.join(timeout=3);server.server_close()
    assert not thread.is_alive()


@pytest.mark.parametrize('operation',['propose','decide','revoke','consume'])
def test_durable_original_request_cannot_be_replayed_by_changing_key(tmp_path,operation):
    from aos_api import aip_budget_policy_window_gateway as g
    j=journal(tmp_path);first=transport_request(operation);assert j.admit(first,g.HUMAN)
    value=json.loads(wire(operation));value['command']['idempotencyKey']='different-key'
    with pytest.raises(g.WindowTransportConflict):j.admit(g.decode_window_request(json.dumps(value).encode()),g.HUMAN)
    assert len(list(j.directory.glob('*.window.json')))==1
    assert j.admit(first,g.HUMAN) is False


@pytest.mark.parametrize('operation,field,value',[('decide','decision','rejected'),('revoke','reason','a revised withdrawal reason'),('consume','decisionHash','a'*64),('decide','proposalHash','a'*64)])
def test_same_immutable_proposal_operation_cannot_escape_old_attempt_with_new_payload(tmp_path,operation,field,value):
    from aos_api import aip_budget_policy_window_gateway as g
    j=journal(tmp_path);j.admit(transport_request(operation),g.HUMAN)
    body=json.loads(wire(operation));body['command'].update(idempotencyKey='changed-payload-key');body['command'][field]=value
    with pytest.raises(g.WindowTransportConflict):j.admit(g.decode_window_request(json.dumps(body).encode()),g.HUMAN)
    assert len(list(j.directory.glob('*.window.json')))==1


def test_distinct_window_or_proposal_or_operation_is_still_independent(tmp_path):
    from aos_api import aip_budget_policy_window_gateway as g
    j=journal(tmp_path);j.admit(transport_request(),g.HUMAN)
    body=json.loads(wire());body['command'].update(idempotencyKey='different-window',effectiveUntil='2026-10-16T00:00:00Z')
    assert j.admit(g.decode_window_request(json.dumps(body).encode()),g.HUMAN)
    assert j.admit(transport_request('decide'),g.HUMAN)
    body=json.loads(wire('decide'));body['command'].update(idempotencyKey='different-proposal',proposalId='different-immutable-proposal')
    assert j.admit(g.decode_window_request(json.dumps(body).encode()),g.HUMAN)
    assert j.admit(transport_request('consume'),g.HUMAN)


def test_new_key_cannot_escape_an_untrusted_prior_snapshot(tmp_path):
    from aos_api import aip_budget_policy_window_gateway as g
    j=journal(tmp_path);j.admit(transport_request(),g.HUMAN)
    next(j.directory.glob('*.window.json')).write_text('{')
    body=json.loads(wire());body['command']['idempotencyKey']='fresh-key'
    with pytest.raises(g.WindowTransportUnknown):j.admit(g.decode_window_request(json.dumps(body).encode()),g.HUMAN)
    assert len(list(j.directory.glob('*.window.json')))==1


@pytest.mark.parametrize('operation',['propose','decide','revoke','consume'])
def test_http_unknown_replay_new_key_is_409_and_original_get_stays_readonly(tmp_path,monkeypatch,operation):
    path,_,g=http_config(tmp_path,monkeypatch,writer=True);monkeypatch.setattr(g,'relay_window_current_checker',lambda *a:checker_view());calls=[]
    def run(*a,**k):calls.append(1);raise RuntimeError('fixture unknown transport')
    monkeypatch.setattr(g,'run_window_process',run)
    class Service:
        def __init__(self,*a):pass
        def reconcile(self,r):assert r.mode=='reconcile';return {'status':'unresolved','activationEligible':False}
    monkeypatch.setattr(g,'WindowService',Service);app=g.create_window_gateway(path)
    try:
        original=command_payload(operation);route='/v1/aip/budget-policy-window/'+operation
        assert call_http(app,'POST',route,json.dumps(original).encode())[2]['observation']['status']=='unknown'
        changed=dict(original,idempotencyKey='replay-new-key')
        status,_,error=call_http(app,'POST',route,json.dumps(changed).encode())
        assert status==409 and error['code']=='POLICY_WINDOW_HTTP_INTENT_CONFLICT' and error['activationEligible'] is False
        assert len(calls)==1
        original_route='/v1/aip/budget-policy-window/requests/'+operation+'/'+original['idempotencyKey']
        assert call_http(app,'GET',original_route)[2]['observation']['result']['status']=='unresolved'
        assert len(list(app.controller.transport.journal.directory.glob('*.window.json')))==1
    finally:app.controller.close()

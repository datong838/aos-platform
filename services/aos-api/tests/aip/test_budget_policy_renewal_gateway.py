"""Transport unit boundaries; no production identity, PG result or consent."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import SecretStr

from aos_api.aip_budget_policy_renewal_contracts import RenewalProposalCommand

SUBJECT = "6f31cfdc-a26c-4f1f-ad6b-95a8559cc657"


def command(key="unit-key", *, head=1, until="2026-12-01T00:00:00Z"):
    return RenewalProposalCommand(
        schemaVersion=1, orgId="org-org", projectId="dev-project", idempotencyKey=key,
        sourcePolicyId="unit-policy", expectedSourceRevision=13, expectedHeadVersion=head,
        expectedSourceHash="a" * 64, effectiveFrom="2026-11-01T00:00:00Z", effectiveUntil=until,
    )


def journal(tmp_path):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportJournal
    directory = tmp_path / "transport"
    directory.mkdir(mode=0o700)
    return RenewalTransportJournal(directory)


def test_transport_journal_exact_original_key_is_never_admitted_twice(tmp_path):
    ledger = journal(tmp_path)
    assert ledger.admit("propose", command(), SUBJECT) is True
    assert ledger.admit("propose", command(), SUBJECT) is False
    restored = ledger.restore("propose", "unit-key", SUBJECT)
    assert restored == command()
    files = list((tmp_path / "transport").iterdir())
    assert all(os.stat(f).st_mode & 0o777 == 0o600 for f in files)
    assert all("bearer" not in f.read_text().lower() for f in files if f.suffix == ".json")


def test_transport_changed_body_same_key_is_conflict(tmp_path):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportConflict
    ledger = journal(tmp_path)
    ledger.admit("propose", command(), SUBJECT)
    with pytest.raises(RenewalTransportConflict):
        ledger.admit("propose", command(until="2026-12-02T00:00:00Z"), SUBJECT)


@pytest.mark.parametrize("head", [1, 2])
def test_unresolved_resource_cannot_be_bypassed_with_new_key_or_epoch(tmp_path, head):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportUnknown
    ledger = journal(tmp_path)
    ledger.admit("propose", command(), SUBJECT)
    with pytest.raises(RenewalTransportUnknown):
        ledger.admit("propose", command("replacement-key", head=head), SUBJECT)


@pytest.mark.parametrize("defect", ["snapshot-missing", "marker-missing", "partial", "symlink"])
def test_partial_or_orphan_transport_records_never_allow_another_write(tmp_path, defect):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportUnknown
    ledger = journal(tmp_path)
    ledger.admit("propose", command(), SUBJECT)
    directory = tmp_path / "transport"
    snapshot, = directory.glob("*.snapshot.json")
    marker, = [p for p in directory.glob("*.json") if not p.name.endswith(".snapshot.json")]
    if defect == "snapshot-missing":
        snapshot.unlink()
    elif defect == "marker-missing":
        marker.unlink()
    elif defect == "partial":
        snapshot.write_text('{"schemaVersion":')
    else:
        snapshot.unlink()
        snapshot.symlink_to(marker)
    with pytest.raises(RenewalTransportUnknown):
        ledger.admit("propose", command("new-key"), SUBJECT)


def test_journal_rejects_public_subject_and_unsafe_directory(tmp_path):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportBlocked
    ledger = journal(tmp_path)
    with pytest.raises(RenewalTransportBlocked):
        ledger.admit("propose", command(), "invented-admin")
    (tmp_path / "transport").chmod(0o755)
    with pytest.raises(RenewalTransportBlocked):
        ledger.admit("propose", command(), SUBJECT)


def test_transport_restart_restores_command_without_execution(tmp_path):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportJournal
    ledger = journal(tmp_path)
    ledger.admit("propose", command(), SUBJECT)
    another = RenewalTransportJournal(tmp_path / "transport")
    assert another.restore("propose", "unit-key", SUBJECT) == command()
    assert another.admit("propose", command(), SUBJECT) is False


def test_missing_marker_does_not_prevent_readonly_original_request_restore(tmp_path):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportUnknown
    ledger = journal(tmp_path)
    ledger.admit("propose", command(), SUBJECT)
    directory = tmp_path / "transport"
    marker, = [p for p in directory.glob("*.json") if not p.name.endswith(".snapshot.json")]
    marker.unlink()
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    assert ledger.restore("propose", "unit-key", SUBJECT) == command()
    assert before == {p.name: p.read_bytes() for p in directory.iterdir()}
    with pytest.raises(RenewalTransportUnknown):
        ledger.admit("propose", command(), SUBJECT)


def test_two_journal_instances_serialize_real_private_filesystem_admission(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportJournal
    first = journal(tmp_path)
    second = RenewalTransportJournal(tmp_path / "transport")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda ledger: ledger.admit("propose", command(), SUBJECT), [first, second]))
    assert sorted(results) == [False, True]


def test_lock_creation_race_opens_only_the_existing_trusted_lock(tmp_path, monkeypatch):
    import errno
    from aos_api import aip_budget_policy_renewal_gateway as module
    ledger = journal(tmp_path)
    real_open = module.os.open
    raced = False

    def concurrent_creator(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal raced
        if path == '.gateway.lock' and flags & os.O_CREAT and not raced:
            raced = True
            fd = real_open(path, flags | os.O_EXCL, mode, dir_fd=dir_fd)
            os.close(fd)
            raise FileNotFoundError(errno.ENOENT, 'observed creation race', path)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(module.os, 'open', concurrent_creator)
    assert ledger.admit('propose', command(), SUBJECT) is True
    assert ledger.admit('propose', command(), SUBJECT) is False
    assert raced


def test_lock_creation_enoent_without_existing_lock_remains_closed(tmp_path, monkeypatch):
    import errno
    from aos_api import aip_budget_policy_renewal_gateway as module
    ledger = journal(tmp_path)
    real_open = module.os.open

    def missing_creator(path, flags, mode=0o777, *, dir_fd=None):
        if path == '.gateway.lock' and flags & os.O_CREAT:
            raise FileNotFoundError(errno.ENOENT, 'unit missing lock', path)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(module.os, 'open', missing_creator)
    with pytest.raises(module.RenewalTransportBlocked):
        ledger.admit('propose', command(), SUBJECT)
    assert list((tmp_path / 'transport').iterdir()) == []


def test_observed_receipt_never_allows_same_source_epoch_with_different_key(tmp_path):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportConflict
    ledger = journal(tmp_path)
    ledger.admit("propose", command(), SUBJECT)
    # Explicit local journal unit input, not a genuine native receipt proof.
    ledger.record_observation("propose", command(), SUBJECT, {
        "operation": "propose", "status": "observed", "requestHash": command().request_hash,
        "activationEligible": False,
    })
    with pytest.raises(RenewalTransportConflict):
        ledger.admit("propose", command("new-key"), SUBJECT)
    assert ledger.admit("propose", command("new-head-key", head=2), SUBJECT) is True


@pytest.mark.parametrize("field,value", [("status", "unresolved"), ("activationEligible", 0),
                                         ("requestHash", "b" * 64)])
def test_unknown_or_mismatched_native_observation_cannot_release_resource(tmp_path, field, value):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportUnknown
    ledger = journal(tmp_path)
    ledger.admit("propose", command(), SUBJECT)
    observation = {"operation": "propose", "status": "observed",
                   "requestHash": command().request_hash, "activationEligible": False}
    observation[field] = value
    ledger.record_observation("propose", command(), SUBJECT, observation)
    with pytest.raises(RenewalTransportUnknown):
        ledger.admit("propose", command("new-head-key", head=2), SUBJECT)


@pytest.mark.parametrize("operation", ["decide", "revoke", "consume"])
def test_other_operations_cannot_replace_an_unresolved_proposal_key(tmp_path, operation):
    from aos_api.aip_budget_policy_renewal_contracts import (
        RenewalDecisionCommand, RenewalConsumeCommand, RenewalRevocationCommand,
    )
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportUnknown
    body = {"schemaVersion": 1, "orgId": "org-org", "projectId": "dev-project",
            "idempotencyKey": "unit-key", "proposalId": "unit-proposal", "proposalHash": "a" * 64}
    if operation == "decide":
        body.update(targetActiveHash="b" * 64, decision="approved")
        model = RenewalDecisionCommand
    else:
        body.update(decisionId="unit-decision", decisionHash="c" * 64)
        model = RenewalRevocationCommand if operation == "revoke" else RenewalConsumeCommand
        if operation == "revoke":
            body["reasonCode"] = "approval_withdrawn"
    ledger = journal(tmp_path)
    ledger.admit(operation, model.model_validate(body), SUBJECT)
    body["idempotencyKey"] = "replacement-key"
    with pytest.raises(RenewalTransportUnknown):
        ledger.admit(operation, model.model_validate(body), SUBJECT)


def test_process_observation_keeps_real_handle_and_never_replays_stdin(tmp_path):
    from aos_api.aip_budget_policy_renewal_gateway import OwnedRenewalChild
    # A real local child, exclusively a lifecycle fixture. No DB or budget call.
    child = subprocess.Popen([sys.executable, "-c",
        "import sys; data=sys.stdin.buffer.read();sys.stdout.buffer.write(b'x'*131072);sys.stdout.flush()"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    child.stdin.write(b"partial-unit-frame")
    child.stdin.flush()
    owned = OwnedRenewalChild(child)
    assert owned.process is child
    owned.finish_incomplete_input()
    assert child.stdin is None
    import time
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not owned.drain():
        time.sleep(.01)
    assert child.poll() == 0
    assert owned.discarded_bytes >= 131072
    assert owned.process is child


def test_failure_only_runner_is_called_once_and_repeat_is_native_reconcile_only(tmp_path, monkeypatch):
    from aos_api import aip_budget_policy_renewal_gateway as module
    ledger = journal(tmp_path)
    calls = []

    def failed_runner(config, attempts, raw, **kwargs):
        calls.append(json.loads(raw))
        return {"status": "unknown", "requestHash": command().request_hash, "activationEligible": False}

    monkeypatch.setattr(module, "run_renewal_process", failed_runner)
    transport = module.RenewalTransport(ledger, Path("/unit/config"), Path("/unit/attempts"))
    observed = []
    monkeypatch.setattr(transport, "_reconcile", lambda request: observed.append(request.mode) or {
        "status": "unknown", "requestHash": request.command.request_hash, "activationEligible": False,
    })
    try:
        assert transport.execute("propose", command(), SUBJECT)["status"] == "unknown"
        assert transport.execute("propose", command(), SUBJECT)["status"] == "unknown"
        assert len(calls) == 1 and observed == ["reconcile"]
        assert "bearerToken" not in calls[0]
    finally:
        transport.close()


def test_issuer_token_is_memory_only_on_failure_and_recovery(tmp_path, monkeypatch):
    from pydantic import SecretStr
    from aos_api import aip_budget_policy_renewal_gateway as module
    from aos_api.aip_budget_policy_renewal_contracts import RenewalDecisionCommand
    ledger = journal(tmp_path)
    token = "unit-noncredential-token-must-not-be-persisted"
    decision = RenewalDecisionCommand(schemaVersion=1, orgId="org-org", projectId="dev-project",
        idempotencyKey="unit-decide", proposalId="unit-proposal", proposalHash="a" * 64,
        targetActiveHash="b" * 64, decision="rejected")
    received = []

    def failure(config, attempts, raw):
        received.append(json.loads(raw))
        return {"status": "unknown", "requestHash": decision.request_hash, "activationEligible": False}

    monkeypatch.setattr(module, "run_renewal_process", failure)
    transport = module.RenewalTransport(ledger, Path("/unit/config"), Path("/unit/attempts"))
    monkeypatch.setattr(transport, "_reconcile", lambda request: {
        "status": "unknown", "requestHash": request.command.request_hash, "activationEligible": False,
    })
    try:
        transport.execute("decide", decision, SUBJECT, bearer_token=SecretStr(token))
        transport.reconcile("decide", "unit-decide", SUBJECT, bearer_token=SecretStr(token))
        assert len(received) == 1 and received[0]["bearerToken"] == token
        assert all(token.encode() not in f.read_bytes() for f in (tmp_path / "transport").iterdir())
        assert all("bearerToken" not in f.read_text() for f in (tmp_path / "transport").glob("*.json"))
    finally:
        transport.close()


# The following real local transport fixtures are NOT signed identity or
# native current-member proof. Those remain in the full isolated C gate.
@pytest.fixture
def checker_relay_fixture(tmp_path, monkeypatch):
    import hashlib
    import threading
    from datetime import datetime, timezone
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from aos_api import aip_budget_policy_renewal_gateway as module

    for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
        monkeypatch.delenv(key, raising=False)
    home = tmp_path / 'private-relay'
    home.mkdir(mode=0o700)
    source = home / 'source'
    source.mkdir(mode=0o700)
    required = ('scripts/a0v_qyh_restored_http.py', 'scripts/a0v_current_preview_http.py',
                'services/aos-api/aos_api/main.py', 'services/aos-api/aos_api/auth.py',
                'services/aos-api/aos_api/aip_budget_policy_renewal_review.py',
                'services/aos-api/aos_api/routers/aip_model_governance_policies.py')
    manifest = {}
    for name in required:
        p = source / name
        p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        p.write_text('# Non-executed provenance fixture; not production source.\n')
        p.chmod(0o600)
        manifest[name] = hashlib.sha256(p.read_bytes()).hexdigest()

    def private_json(name, value):
        p = home / name
        p.write_text(json.dumps(value))
        p.chmod(0o600)
        return p

    for directory in source.rglob('*'):
        if directory.is_dir():
            directory.chmod(0o700)

    manifest_path = private_json('manifest.json', manifest)
    report = {'head': '8d250879612c05622471751cfaca368898c2d1fc', 'source': str(source),
              'fileCount': len(manifest), 'manifestSha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              'outcome': 'CURRENT_M1_API_SOURCE_CANDIDATE_FROZEN_NO_START'}
    report_path = private_json('source.json', report)
    calls = []
    state = {'status':200, 'headers':{'Content-Type':'application/json'}, 'raw':None,
             'response':{'schemaVersion':'aos.budget-policy-renewal.review-checker/v1',
                'tenant':{'orgId':'org-org','projectId':'dev-project'}, 'subject':SUBJECT,
                'tokenKind':'oidc', 'role':'owner', 'evaluatedAt':datetime.now(timezone.utc).isoformat(),
                'approvalVerified':False,'activationEligible':False}}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append({'path':self.path,'headers':dict(self.headers)})
            raw = state['raw'] if state['raw'] is not None else json.dumps(state['response']).encode()
            self.send_response(state['status'])
            for k,v in state['headers'].items():
                self.send_header(k,v)
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass
        def log_message(self,*args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    port = server.server_port
    # Filesystem+HTTP transport tests deliberately inject the observed process
    # binding, while separate tests below probe a real owned child process.
    process = {'pid':os.getpid(),'startIdentity':'fixture-start','uid':os.geteuid(),
               'cwd':str(source),'command':'fixture-only-command'}
    monkeypatch.setattr(module,'probe_management_process',lambda pid,port:dict(process))
    package_root = tmp_path / 'gateway-package'
    package_root.mkdir(mode=0o700)
    package_files = ('scripts/a0v_qyh_budget_policy_renewal.py',
                     'services/aos-api/aos_api/aip_budget_policy_renewal_gateway.py',
                     'services/aos-api/aos_api/aip_budget_policy_renewal_review.py',
                     'services/aos-api/aos_api/routers/aip_model_governance_policies.py')
    packages = {}
    for name in package_files:
        p = package_root/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text('# non-executed package fixture\n')
        packages[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    monkeypatch.setattr(module,'GATEWAY_ROOT',package_root)
    value = {'schemaVersion':'aos.budget-policy-renewal.gateway/v1',
        'orgId':'org-org','projectId':'dev-project','webOrigin':'http://127.0.0.1:18434',
        'managementOrigin':f'http://127.0.0.1:{port}',
        'sourceCandidatePath':str(report_path),
        'sourceCandidateSha256':hashlib.sha256(report_path.read_bytes()).hexdigest(),
        'sourceManifestPath':str(manifest_path),
        'sourceManifestSha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'managementProcess':dict(process),'gatewaySources':packages}
    config_path = private_json('gateway.json',value)
    def write_config():
        config_path.write_text(json.dumps(value))
        config_path.chmod(0o600)
    try:
        yield module,config_path,value,state,calls,source,process,write_config
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
        assert not thread.is_alive()


def test_protected_gateway_config_defaults_closed_without_opening_database(checker_relay_fixture):
    module,path,value,state,calls,source,process,write = checker_relay_fixture
    config = module.load_gateway_config(path)
    assert config.writer_enabled is False
    assert config.renewal_config is None
    assert config.source_root == source
    assert calls == []


@pytest.mark.parametrize('field,value',[
    ('writerEnabled',True),('writerEnabled',0),('writerEnabled','false'),
    ('orgId','dev-org'),('projectId','other'),('extra','forbidden'),
    ('managementOrigin','http://localhost:18080'),
    ('managementOrigin','http://127.0.0.1:18080/'),
    ('managementOrigin','http://user@127.0.0.1:18080'),
    ('managementOrigin','http://127.0.0.1:18080?url=http://evil.invalid'),
    ('webOrigin','https://evil.invalid'),('gatewaySources',{}),
    ('protectedRenewalConfigPath','/tmp/no-implicit-config'),
])
def test_protected_gateway_config_rejects_unsafe_fields(checker_relay_fixture,field,value):
    module,path,body,state,calls,source,process,write = checker_relay_fixture
    body[field]=value;write()
    with pytest.raises(module.RenewalTransportBlocked):
        module.load_gateway_config(path)
    assert calls == []


@pytest.mark.parametrize('defect',['config-mode','config-hardlink','config-duplicate',
    'source-drift','source-extra','source-link','source-mode','manifest-drift',
    'candidate-drift','package-drift','process-drift','listener-drift'])
def test_gateway_source_and_process_drift_close_before_bearer(checker_relay_fixture,defect,monkeypatch):
    module,path,body,state,calls,source,process,write = checker_relay_fixture
    config = module.load_gateway_config(path)
    target=source/'services/aos-api/aos_api/main.py'
    if defect=='config-mode':path.chmod(0o644)
    elif defect=='config-hardlink':os.link(path,path.parent/'hardlink.json')
    elif defect=='config-duplicate':path.write_text('{"orgId":"org-org","orgId":"org-org"}')
    elif defect=='source-drift':target.write_text('changed')
    elif defect=='source-extra':
        extra=source/'added.py';extra.write_text('added');extra.chmod(0o600)
    elif defect=='source-link':
        target.unlink();target.symlink_to(source/'services/aos-api/aos_api/auth.py')
    elif defect=='source-mode':target.chmod(0o644)
    elif defect=='manifest-drift':Path(body['sourceManifestPath']).write_text('{}')
    elif defect=='candidate-drift':Path(body['sourceCandidatePath']).write_text('{}')
    elif defect=='package-drift':(module.GATEWAY_ROOT/next(iter(body['gatewaySources']))).write_text('changed')
    elif defect=='process-drift':process['startIdentity']='different-start'
    else:
        def gone(*args):raise OSError('listener unavailable')
        monkeypatch.setattr(module,'probe_management_process',gone)
    with pytest.raises(module.RenewalTransportBlocked):
        module.relay_current_checker(config,SecretStr('unit-transport-token'))
    assert calls == []


def test_checker_relay_fixed_get_and_strict_observation(checker_relay_fixture):
    module,path,body,state,calls,source,process,write = checker_relay_fixture
    result=module.relay_current_checker(module.load_gateway_config(path),SecretStr('unit-transport-token'))
    assert result.subject==SUBJECT and result.approval_verified is False
    assert len(calls)==1
    assert calls[0]['path']=='/v1/aip/model-governance-policies/renewal-checker'
    assert calls[0]['headers']['Authorization']=='Bearer unit-transport-token'
    assert calls[0]['headers']['X-Org-Id']=='org-org'
    assert calls[0]['headers']['X-Project-Id']=='dev-project'
    assert 'Cookie' not in calls[0]['headers']


@pytest.mark.parametrize('defect',['tenant','role','subject','kind','approval','activation',
    'extra','old','future','duplicate','oversize','redirect','content-type','unauthenticated','forbidden'])
def test_checker_relay_rejects_untrusted_response(checker_relay_fixture,defect):
    from datetime import datetime,timedelta,timezone
    module,path,body,state,calls,source,process,write = checker_relay_fixture
    response=state['response']
    if defect=='tenant':response['tenant']['orgId']='dev-org'
    elif defect=='role':response['role']='member'
    elif defect=='subject':response['subject']='another-human'
    elif defect=='kind':response['tokenKind']='dev'
    elif defect=='approval':response['approvalVerified']=True
    elif defect=='activation':response['activationEligible']=0
    elif defect=='extra':response['bearerToken']='must-not-be-reflected'
    elif defect in {'old','future'}:
        response['evaluatedAt']=(datetime.now(timezone.utc)+timedelta(seconds=90 if defect=='future' else -90)).isoformat()
    elif defect=='duplicate':state['raw']=b'{"role":"owner","role":"owner"}'
    elif defect=='oversize':state['raw']=b'x'*65537
    elif defect=='redirect':state['status']=302;state['headers']['Location']='http://evil.invalid'
    elif defect=='content-type':state['headers']['Content-Type']='text/html'
    elif defect=='unauthenticated':state['status']=401
    else:state['status']=403
    with pytest.raises(module.RenewalTransportBlocked) as error:
        module.relay_current_checker(module.load_gateway_config(path),SecretStr('unit-transport-token'))
    assert 'unit-transport-token' not in str(error.value)
    assert len(calls)==1


def test_checker_relay_rechecks_source_after_response(checker_relay_fixture,monkeypatch):
    module,path,body,state,calls,source,process,write = checker_relay_fixture
    config=module.load_gateway_config(path)
    real_probe=module.probe_management_process
    count=0
    def drift(pid,port):
        nonlocal count
        count+=1
        result=real_probe(pid,port)
        if count>=2:result['startIdentity']='replaced-after-send'
        return result
    monkeypatch.setattr(module,'probe_management_process',drift)
    with pytest.raises(module.RenewalTransportBlocked):
        module.relay_current_checker(config,SecretStr('unit-transport-token'))
    assert len(calls)==1


@pytest.mark.parametrize('defect',['proxy','empty','newline','not-secret'])
def test_checker_relay_refuses_unsafe_token_or_proxy_before_network(checker_relay_fixture,monkeypatch,defect):
    module,path,body,state,calls,source,process,write = checker_relay_fixture
    config=module.load_gateway_config(path)
    token=SecretStr('unit-transport-token')
    if defect=='proxy':monkeypatch.setenv('HTTPS_PROXY','http://127.0.0.1:9')
    elif defect=='empty':token=SecretStr('')
    elif defect=='newline':token=SecretStr('bad\r\ntoken')
    else:token='public-raw-token'
    with pytest.raises(module.RenewalTransportBlocked):
        module.relay_current_checker(config,token)
    assert calls==[]


def test_process_provenance_real_owned_listener_and_terminal(tmp_path):
    import socket,time
    from aos_api import aip_budget_policy_renewal_gateway as module
    child=subprocess.Popen([sys.executable,'-u','-c',
        "import socket,sys; s=socket.socket(); s.bind(('127.0.0.1',0)); s.listen(); "
        "print(s.getsockname()[1],flush=True); sys.stdin.buffer.read()"],
        cwd=tmp_path,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        port=int(child.stdout.readline())
        first=module.probe_management_process(child.pid,port)
        second=module.probe_management_process(child.pid,port)
        assert first==second
        assert first['pid']==child.pid and first['uid']==os.geteuid()
        assert Path(first['cwd']).resolve()==tmp_path.resolve()
        assert first['startIdentity'] and '-c' in first['command']
        with pytest.raises(module.RenewalTransportBlocked):
            module.probe_management_process(os.getpid(),port)
    finally:
        child.stdin.close();child.wait(timeout=5)
        child.stdout.close();child.stderr.close()
    assert child.returncode==0
    with pytest.raises(module.RenewalTransportBlocked):
        module.probe_management_process(child.pid,port)


def full_gateway_writer_fixture(relay, tmp_path, *, enabled=True):
    """Real original B file parser inputs, no live role/DB or human approval."""
    import hashlib
    from tests.aip.test_budget_policy_renewal_connection import closed_config
    module,path,body,state,calls,source,process,write=relay
    b_path,b_value=closed_config(tmp_path)
    b_value['enabled']=enabled
    b_path.write_text(json.dumps(b_value))
    body.update(writerEnabled=True,protectedRenewalConfigPath=str(b_path),
                protectedRenewalConfigSha256=hashlib.sha256(b_path.read_bytes()).hexdigest())
    for field,name in [('journalDirectory','journal'),('attemptDirectory','attempts')]:
        directory=path.parent/name;directory.mkdir(mode=0o700);body[field]=str(directory)
    write()
    return b_path,b_value


def test_full_gateway_writer_loads_original_protected_b_without_database(checker_relay_fixture,tmp_path,monkeypatch):
    import hashlib
    import psycopg
    from aos_api.aip_budget_policy_renewal_connection import ProtectedRenewalConfig,_CALLERS
    module,path,body,state,calls,source,process,write=checker_relay_fixture
    b_path,b_value=full_gateway_writer_fixture(checker_relay_fixture,tmp_path)
    def never_connect(*args,**kwargs):
        pytest.fail('configuration load must not contact PostgreSQL')
    monkeypatch.setattr(psycopg,'connect',never_connect)
    config=module.load_gateway_config(path)
    assert config.writer_enabled is True
    assert type(config.renewal_config) is ProtectedRenewalConfig
    assert config.renewal_config.path==b_path
    assert config.renewal_config.content_sha256==hashlib.sha256(b_path.read_bytes()).hexdigest()
    assert config.renewal_config.enabled is True
    assert config.renewal_config.binding.subject==SUBJECT
    assert {p.purpose:p.user for p in config.renewal_config.profiles}==_CALLERS
    assert config.journal_directory==Path(body['journalDirectory'])
    assert config.attempt_directory==Path(body['attemptDirectory'])
    assert calls==[]
    # Accepting byte-only deployment inputs is not a budget operation.
    assert list(config.journal_directory.iterdir())==[]
    assert list(config.attempt_directory.iterdir())==[]


@pytest.mark.parametrize('defect',['b-disabled','b-hash','b-package','b-identity','b-caller',
    'b-passfile','journal-mode','attempt-mode','journal-symlink','same-directory',
    'partial-fields'])
def test_full_gateway_writer_rejects_original_b_and_private_directory_drift(checker_relay_fixture,tmp_path,monkeypatch,defect):
    import hashlib
    import psycopg
    module,path,body,state,calls,source,process,write=checker_relay_fixture
    b_path,b_value=full_gateway_writer_fixture(checker_relay_fixture,tmp_path)
    def never_connect(*args,**kwargs):
        pytest.fail('invalid configuration must not contact PostgreSQL')
    monkeypatch.setattr(psycopg,'connect',never_connect)
    if defect=='b-disabled':b_value['enabled']=False
    elif defect=='b-package':b_value['packageSources'][next(iter(b_value['packageSources']))]='b'*64
    elif defect=='b-identity':b_value['identityConfigSha256']='b'*64
    elif defect=='b-caller':b_value['profiles']['maker']['user']='aos_app'
    elif defect=='b-passfile':b_value['profiles']['consumer']['passfileSha256']='b'*64
    elif defect=='journal-mode':Path(body['journalDirectory']).chmod(0o755)
    elif defect=='attempt-mode':Path(body['attemptDirectory']).chmod(0o755)
    elif defect=='journal-symlink':
        directory=Path(body['journalDirectory']);directory.rmdir();directory.symlink_to(Path(body['attemptDirectory']),target_is_directory=True)
    elif defect=='same-directory':body['attemptDirectory']=body['journalDirectory']
    elif defect=='partial-fields':body.pop('attemptDirectory')
    b_path.write_text(json.dumps(b_value))
    body['protectedRenewalConfigSha256']=hashlib.sha256(b_path.read_bytes()).hexdigest()
    if defect=='b-hash':body['protectedRenewalConfigSha256']='b'*64
    write()
    with pytest.raises(module.RenewalTransportBlocked):module.load_gateway_config(path)
    assert calls==[]


def test_full_writer_config_credential_drift_closes_before_checker_network(checker_relay_fixture,tmp_path):
    module,path,body,state,calls,source,process,write=checker_relay_fixture
    b_path,b_value=full_gateway_writer_fixture(checker_relay_fixture,tmp_path)
    config=module.load_gateway_config(path)
    # Modify only synthetic private fixture input, never a real credential.
    Path(b_value['profiles']['issuer']['passfile']).write_text('invalid-fixture')
    with pytest.raises(module.RenewalTransportBlocked):
        module.relay_current_checker(config,SecretStr('unit-transport-token'))
    assert calls==[]


@pytest.mark.parametrize('status',[301,302,303,307,308])
def test_checker_redirect_never_contacts_second_real_loopback_server(checker_relay_fixture,status):
    import threading
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    module,path,body,state,calls,source,process,write=checker_relay_fixture
    redirected=[]
    class Target(BaseHTTPRequestHandler):
        def do_GET(self):
            redirected.append(self.path)
            self.send_response(200);self.end_headers()
        def log_message(self,*args):pass
    target=ThreadingHTTPServer(('127.0.0.1',0),Target)
    worker=threading.Thread(target=target.serve_forever,daemon=True);worker.start()
    try:
        state['status']=status
        state['headers']['Location']=f'http://127.0.0.1:{target.server_port}/must-not-be-contacted'
        with pytest.raises(module.RenewalTransportBlocked):
            module.relay_current_checker(module.load_gateway_config(path),SecretStr('unit-transport-token'))
        assert len(calls)==1
        assert calls[0]['path']=='/v1/aip/model-governance-policies/renewal-checker'
        assert redirected==[]
    finally:
        target.shutdown();target.server_close();worker.join(timeout=3)
        assert not worker.is_alive()


def approved_decision(key='decision-key', *, proposal='unit-proposal'):
    from aos_api.aip_budget_policy_renewal_contracts import RenewalDecisionCommand
    return RenewalDecisionCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey=key,proposalId=proposal,proposalHash='a'*64,
        targetActiveHash='b'*64,decision='approved')


def test_chain_intent_is_immutable_exact_and_not_an_approval(tmp_path):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportConflict
    ledger=journal(tmp_path);decision=approved_decision()
    assert ledger.reserve_chain(decision,'consume-key',SUBJECT) is True
    assert ledger.reserve_chain(decision,'consume-key',SUBJECT) is False
    saved,key=ledger.read_chain(decision.proposal_id,SUBJECT)
    assert saved==decision and key=='consume-key'
    assert ledger.command_state('decide',decision,SUBJECT)=='not-attempted'
    with pytest.raises(RenewalTransportConflict):ledger.reserve_chain(decision,'other-consume-key',SUBJECT)
    assert all('bearer' not in p.read_text().lower() for p in (tmp_path/'transport').glob('*.json'))
    assert ledger.admit('decide',decision,SUBJECT) is True
    assert ledger.command_state('decide',decision,SUBJECT)=='attempted'
    assert ledger.reserve_chain(decision,'consume-key',SUBJECT) is False


@pytest.mark.parametrize('defect',['rejected','same-key','wrong-subject','unknown-field'])
def test_chain_never_accepts_nonexplicit_or_wrong_identity_intent(tmp_path,defect):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportBlocked
    ledger=journal(tmp_path);decision=approved_decision();key='consume-key';subject=SUBJECT
    if defect=='rejected':decision=decision.model_copy(update={'decision':'rejected'})
    elif defect=='same-key':key=decision.idempotency_key
    elif defect=='wrong-subject':subject='other-human'
    else:decision=decision.model_copy(update={'proposal_hash':'invalid'})
    with pytest.raises(RenewalTransportBlocked):ledger.reserve_chain(decision,key,subject)


def test_chain_cannot_attach_to_prior_unknown_or_rebind_consumer_key(tmp_path):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportConflict
    ledger=journal(tmp_path);decision=approved_decision()
    ledger.admit('decide',decision,SUBJECT)
    with pytest.raises(RenewalTransportConflict):ledger.reserve_chain(decision,'consume-key',SUBJECT)
    # Different clean namespace for a genuinely new local intent.
    second=tmp_path/'another';second.mkdir(mode=0o700)
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportJournal
    other=RenewalTransportJournal(second)
    other.reserve_chain(decision,'consume-key',SUBJECT)
    with pytest.raises(RenewalTransportConflict):
        other.reserve_chain(approved_decision('another-decision',proposal='another-proposal'),'consume-key',SUBJECT)
    with pytest.raises(RenewalTransportConflict):
        other.admit('decide',approved_decision('changed-key'),SUBJECT)


@pytest.mark.parametrize('defect',['partial','symlink','mode','hash','orphan'])
def test_partial_chain_keeps_all_new_admissions_closed(tmp_path,defect):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportBlocked
    ledger=journal(tmp_path);decision=approved_decision();ledger.reserve_chain(decision,'consume-key',SUBJECT)
    path,=(tmp_path/'transport').glob('*.chain.json')
    if defect=='partial':path.write_text('{')
    elif defect=='symlink':
        target=tmp_path/'untrusted';target.write_text('{}');path.unlink();path.symlink_to(target)
    elif defect=='mode':path.chmod(0o644)
    elif defect=='hash':
        value=json.loads(path.read_text());value['decisionRequestHash']='b'*64;path.write_text(json.dumps(value))
    else:
        extra=path.parent/'unrecognized.json';extra.write_text('{}');extra.chmod(0o600)
    with pytest.raises(RenewalTransportBlocked):ledger.admit('propose',command(),SUBJECT)
    with pytest.raises(RenewalTransportBlocked):ledger.command_state('decide',decision,SUBJECT)


def test_chain_partial_decision_marker_is_unknown_not_unattempted(tmp_path):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportUnknown
    ledger=journal(tmp_path);decision=approved_decision();ledger.reserve_chain(decision,'consume-key',SUBJECT)
    ledger.admit('decide',decision,SUBJECT)
    snapshot,=(tmp_path/'transport').glob('*.snapshot.json');snapshot.unlink()
    with pytest.raises(RenewalTransportUnknown):ledger.command_state('decide',decision,SUBJECT)
    with pytest.raises(RenewalTransportUnknown):ledger.admit('decide',decision,SUBJECT)


def test_chain_real_independent_instances_reserve_only_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportJournal
    first=journal(tmp_path);second=RenewalTransportJournal(first.directory)
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(lambda ledger:ledger.reserve_chain(approved_decision(),'consume-key',SUBJECT),[first,second]))
    assert sorted(result)==[False,True]


@pytest.fixture
def closed_gateway_http(checker_relay_fixture):
    from starlette.testclient import TestClient
    module,path,body,state,calls,source,process,write=checker_relay_fixture
    # Same explicit unsigned local response fixture as transport tests. This
    # tests closed-state HTTP grammar, NOT real login/native budget admission.
    app=module.create_renewal_gateway(path)
    headers={'Authorization':'Bearer unit-transport-token','X-Org-Id':'org-org',
             'X-Project-Id':'dev-project','Origin':'http://127.0.0.1:18434'}
    with TestClient(app,base_url='http://127.0.0.1:18462',headers=headers) as client:
        yield module,client,checker_relay_fixture


PREFIX='/v1/aip/budget-policy-renewal'


def test_http_closed_status_truthful_no_budget_permission(closed_gateway_http):
    module,client,relay=closed_gateway_http
    response=client.get(PREFIX+'/status')
    assert response.status_code==200
    value=response.json()
    assert value['writerEnabled'] is False and value['activationEligible'] is False
    assert value['approvalVerified'] is False and value['state']=='closed'
    assert response.headers['Cache-Control']=='no-store'
    assert not any('access-control-allow' in k for k in response.headers)


@pytest.mark.parametrize('method,path,headers,raw,status',[
    ('GET','/status',{'Host':'evil.invalid'},None,400),
    ('GET','/status',{'Origin':'http://evil.invalid'},None,403),
    ('GET','/status',{'X-Org-Id':'dev-org'},None,403),
    ('GET','/status',{'X-Project-Id':'other'},None,403),
    ('GET','/status',{'Authorization':''},None,401),
    ('GET','/status',{'Forwarded':'host=evil.invalid'},None,400),
    ('GET','/status?url=anything',{},None,400),
    ('POST','/status',{},b'{}',405),
    ('GET','/nonexistent',{},None,404),
    ('OPTIONS','/status',{},None,405),
    ('GET','/status',{},b'{}',400),
    ('POST','/propose',{'Origin':''},b'{}',403),
    ('POST','/propose',{'Content-Type':'text/plain'},b'{}',415),
    ('POST','/propose',{'Content-Type':'application/json','Content-Encoding':'gzip'},b'{}',415),
    ('POST','/propose',{'Content-Type':'application/json'},b'{"orgId":"org-org","orgId":"org-org"}',400),
    ('POST','/propose',{'Content-Type':'application/json'},b'[]',400),
    ('POST','/propose',{'Content-Type':'application/json'},b'x'*65537,413),
], ids=[f'envelope-{i}' for i in range(17)])
def test_http_rejects_invalid_envelope_before_business(closed_gateway_http,method,path,headers,raw,status):
    module,client,relay=closed_gateway_http
    response=client.request(method,PREFIX+path,headers=headers,content=raw)
    assert response.status_code==status
    assert response.json()['activationEligible'] is False
    assert 'unit-transport-token' not in response.text


def test_http_duplicate_headers_rejected(closed_gateway_http):
    module,client,relay=closed_gateway_http
    response=client.get(PREFIX+'/status',headers=[('Host','127.0.0.1:18462'),('Host','127.0.0.1:18462')])
    assert response.status_code==400


def test_closed_writer_never_starts_proposal(closed_gateway_http):
    module,client,relay=closed_gateway_http
    response=client.post(PREFIX+'/propose',json=command().canonical_payload())
    assert response.status_code==503
    assert response.json()['activationEligible'] is False
    assert len(relay[4])==1


@pytest.mark.parametrize('field',['actorSubject','bearerToken','targetBody','configPath'])
def test_http_actor_free_command_rejects_extra_fields(closed_gateway_http,field):
    module,client,relay=closed_gateway_http
    body=command().canonical_payload();body[field]='forbidden-unit-field'
    response=client.post(PREFIX+'/propose',json=body)
    assert response.status_code==400


def test_http_missing_journal_has_no_fabricated_history(closed_gateway_http):
    module,client,relay=closed_gateway_http
    response=client.get(PREFIX+'/requests')
    assert response.status_code==503
    assert 'items' not in response.json()


def test_cli_help_and_invalid_config_never_start_main(tmp_path):
    import importlib.util
    root=Path(__file__).resolve().parents[4]
    cli=root/'scripts/a0v_qyh_budget_policy_renewal.py'
    assert cli.is_file()
    help_run=subprocess.run([sys.executable,str(cli),'--help'],capture_output=True,text=True,timeout=10)
    assert help_run.returncode==0 and '--config' in help_run.stdout
    rejected=subprocess.run([sys.executable,str(cli),'--config',str(tmp_path/'missing.json')],
                            capture_output=True,text=True,timeout=10)
    assert rejected.returncode==2
    assert rejected.stderr.strip()=='RENEWAL_GATEWAY_STARTUP_BLOCKED'
    assert 'Traceback' not in rejected.stderr


def test_chain_history_lists_only_original_requests_not_intent_as_approval(tmp_path):
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportBlocked
    ledger=journal(tmp_path);decision=approved_decision()
    ledger.reserve_chain(decision,'consume-key',SUBJECT)
    assert ledger.list_requests(SUBJECT)==[]
    ledger.admit('decide',decision,SUBJECT)
    assert ledger.list_requests(SUBJECT)==[('decide',decision)]
    with pytest.raises(RenewalTransportBlocked):ledger.list_requests('another-subject')


def test_chain_consumer_key_cannot_be_replaced_by_standalone_operation(tmp_path):
    from aos_api.aip_budget_policy_renewal_contracts import RenewalConsumeCommand
    from aos_api.aip_budget_policy_renewal_gateway import RenewalTransportConflict
    ledger=journal(tmp_path);decision=approved_decision();ledger.reserve_chain(decision,'consume-key',SUBJECT)
    payload={'schemaVersion':1,'orgId':'org-org','projectId':'dev-project','idempotencyKey':'wrong-key',
             'proposalId':decision.proposal_id,'proposalHash':decision.proposal_hash,
             'decisionId':'unit-not-native-decision','decisionHash':'c'*64}
    with pytest.raises(RenewalTransportConflict):
        ledger.admit('consume',RenewalConsumeCommand.model_validate(payload),SUBJECT)
    # Local transport admission only; never passed to a runner/native service.
    payload['idempotencyKey']='consume-key'
    assert ledger.admit('consume',RenewalConsumeCommand.model_validate(payload),SUBJECT) is True
    assert ledger.list_requests(SUBJECT)[0][0]=='consume'


@pytest.mark.parametrize('reason,expected',[
 ('RENEWAL_GATEWAY_CONFIG_CLOSED_OR_DRIFTED','RENEWAL_HTTP_CONFIG_UNAVAILABLE'),
 ('RENEWAL_GATEWAY_CONFIG_DRIFTED','RENEWAL_HTTP_CONFIG_UNAVAILABLE'),
 ('RENEWAL_GATEWAY_MANAGEMENT_PROCESS_UNTRUSTED','RENEWAL_HTTP_MANAGEMENT_UNAVAILABLE'),
 ('RENEWAL_GATEWAY_CHECKER_UNAVAILABLE_OR_DRIFTED','RENEWAL_HTTP_CHECKER_UNAVAILABLE'),
 ('private-token-and-dsn-must-not-leak','RENEWAL_HTTP_UNAVAILABLE'),
])
def test_http_unavailable_exposes_only_known_coarse_category(closed_gateway_http,monkeypatch,reason,expected):
 module,client,relay=closed_gateway_http
 def fail(*args,**kwargs):raise module.RenewalTransportBlocked(reason)
 monkeypatch.setattr(module.RenewalGatewayController,'dispatch',fail)
 response=client.get(PREFIX+'/status')
 assert response.status_code==503 and response.json()['code']==expected
 assert set(response.json())=={'schemaVersion','code','activationEligible','approvalVerified'}
 assert response.json()['activationEligible'] is False and response.json()['approvalVerified'] is False
 assert response.headers['Cache-Control']=='no-store'
 assert 'private-token-and-dsn' not in response.text


@pytest.mark.parametrize('kind',['unexpected','non-string','multiple-args','denied','conflict','unknown'])
def test_http_unavailable_preserves_existing_error_boundaries(closed_gateway_http,monkeypatch,kind):
 module,client,relay=closed_gateway_http
 class SensitiveError(module.RenewalTransportBlocked):
  def __str__(self):raise AssertionError('Never stringify an arbitrary error')
 errors={'unexpected':RuntimeError('private-secret'), 'non-string':SensitiveError({'secret':'private-secret'}),
  'multiple-args':SensitiveError('RENEWAL_GATEWAY_CONFIG_DRIFTED','private-secret'),
  'denied':module.RenewalCheckerDenied(403),'conflict':module.RenewalTransportConflict('private-secret'),
  'unknown':module.RenewalTransportUnknown('private-secret')}
 def fail(*args,**kwargs):raise errors[kind]
 monkeypatch.setattr(module.RenewalGatewayController,'dispatch',fail)
 response=client.get(PREFIX+'/status')
 expected={'denied':(403,'RENEWAL_HTTP_CHECKER_DENIED'),'conflict':(409,'RENEWAL_HTTP_EXACT_INTENT_CONFLICT'),
  'unknown':(409,'RENEWAL_HTTP_OUTCOME_UNKNOWN_READONLY_RECONCILE')}.get(kind,(503,'RENEWAL_HTTP_UNAVAILABLE'))
 assert (response.status_code,response.json()['code'])==expected
 assert 'private-secret' not in response.text


@pytest.fixture
def fake_linux_proc(tmp_path,monkeypatch):
 import os
 import aos_api.aip_budget_policy_renewal_gateway as module
 root=tmp_path/'proc';root.mkdir();cwd=tmp_path/'source';cwd.mkdir();uid=os.geteuid()
 def task(pid,state='S',threads=1,start='100',owner=None):
  folder=root/str(pid);folder.mkdir(exist_ok=True)
  fields=['0']*50;fields[0]=state;fields[19]=start
  (folder/'stat').write_text(str(pid)+' (python worker) '+' '.join(fields))
  effective=uid if owner is None else owner
  (folder/'status').write_text(f'Uid:\t{effective}\t{effective}\t{effective}\t{effective}\nThreads:\t{threads}\n')
  (folder/'cmdline').write_bytes(b'python\0-B\0api.py\0')
  (folder/'cwd').symlink_to(cwd)
  (folder/'fd').mkdir();(folder/'task').mkdir();thread=folder/'task'/str(pid);thread.mkdir()
  (thread/'stat').write_text((folder/'stat').read_text())
  return folder
 api=task(11);(api/'net').mkdir()
 row=['0:','0100007F:46A0','00000000:0000','0A','0','0','0',str(uid),'0','55']
 (api/'net/tcp').write_text('header\n'+' '.join(row)+'\n');(api/'net/tcp6').write_text('header\n')
 (api/'fd/4').symlink_to('socket:[55]')
 boot=root/'sys/kernel/random';boot.mkdir(parents=True);(boot/'boot_id').write_text('unit-boot')
 real_path=Path;real_iterdir=real_path.iterdir;real_stat=real_path.stat
 blocked=set();hidden_owner=set()
 def iterate(path):
  if path in blocked:raise PermissionError('unit inaccessible live/terminal fd table')
  return real_iterdir(path)
 def stat_path(path,*args,**kwargs):
  value=real_stat(path,*args,**kwargs)
  if path in hidden_owner:
   values=list(value);values[4]=0;return os.stat_result(values)
  return value
 monkeypatch.setattr(real_path,'iterdir',iterate);monkeypatch.setattr(real_path,'stat',stat_path)
 monkeypatch.setattr(module,'Path',lambda value:root/str(value).removeprefix('/proc').lstrip('/') if str(value).startswith('/proc') else real_path(value))
 return module,task,blocked,hidden_owner,api


def test_linux_probe_excludes_only_wholly_terminated_single_thread_group(fake_linux_proc):
 module,task,blocked,hidden,api=fake_linux_proc
 zombie=task(22,state='Z');blocked.add(zombie/'fd')
 result=module._linux_process(11,18080)
 assert result['pid']==11 and result['startIdentity']=='linux:unit-boot:100'


def test_linux_probe_live_unreadable_same_uid_stays_closed_even_if_proc_owner_hidden(fake_linux_proc):
 module,task,blocked,hidden,api=fake_linux_proc
 live=task(33);blocked.add(live/'fd');hidden.add(live)
 with pytest.raises(PermissionError):module._linux_process(11,18080)


def test_linux_probe_zombie_leader_with_threads_is_not_ignored(fake_linux_proc):
 module,task,blocked,hidden,api=fake_linux_proc
 zombie=task(22,state='Z',threads=2);blocked.add(zombie/'fd')
 with pytest.raises((ValueError,PermissionError)):module._linux_process(11,18080)


def test_linux_probe_live_inherited_holder_remains_rejected(fake_linux_proc):
 module,task,blocked,hidden,api=fake_linux_proc
 inherited=task(33);(inherited/'fd/4').symlink_to('socket:[55]')
 with pytest.raises(ValueError):module._linux_process(11,18080)


def test_linux_probe_dead_target_stays_rejected(fake_linux_proc):
 module,task,blocked,hidden,api=fake_linux_proc
 (api/'stat').write_text((api/'stat').read_text().replace(') S ',') Z '))
 with pytest.raises(ValueError):module._linux_process(11,18080)

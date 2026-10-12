import importlib.util
from pathlib import Path

import pytest

from aos_api.extension_runtime.runtime_identity import RuntimeDatabaseIdentity


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_current_runtime_host_preflight.py"


def restored_arguments():
    return dict(identity_file=Path('/protected/restored.json'),
                installation_id='ab2fd72f-d81c-400d-bbbc-e1589a159d6b',
                bundle_root=Path('/signed/restored'),
                trust_roots_file=Path('/signed/roots.json'),
                credential_file=Path('/protected/planes.json'), preparation_only=True)


def test_restored_preflight_never_admits_full_mode(gate):
    args = restored_arguments()
    args['preparation_only'] = False
    with pytest.raises(gate.HostPreflightBlocked, match='RESTORED_PREPARATION_ONLY_REQUIRED'):
        gate.preflight_restored(**args)


@pytest.mark.parametrize('field', ['identity_file', 'bundle_root', 'trust_roots_file', 'credential_file'])
def test_restored_preflight_requires_absolute_inputs(gate, field):
    args = restored_arguments()
    args[field] = Path('relative.json')
    with pytest.raises(gate.HostPreflightBlocked, match='RESTORED_PREFLIGHT_INPUT_INVALID'):
        gate.preflight_restored(**args)


def test_restored_preflight_reuses_exact_selector_and_shared_identity_gate(gate, monkeypatch, tmp_path):
    args = restored_arguments()
    args['bundle_root'] = tmp_path / 'signed'
    args['bundle_root'].mkdir()
    args['trust_roots_file'] = tmp_path / 'roots.json'
    args['trust_roots_file'].write_text('{}')
    calls = []
    class Restored:
        @staticmethod
        def select_current_installation(**kwargs):
            calls.append(kwargs)
            return {'identity': {'database': 'aos_meta_head'},
                    'currentInstallation': {'installationId': args['installation_id'],
                        'authorization': 'CURRENT_INSTALLATION_EVIDENCE_ONLY_NO_START',
                        'runtimeHostEnabled': False, 'apiStartAuthorized': False}}
        @staticmethod
        def _identity_parameters(path):
            assert path == args['identity_file']
            return {'host': '127.0.0.1', 'port': 18446, 'dbname': 'aos_meta_head',
                    'user': 'limited', 'pgpassFile': '/protected/passfile'}
    monkeypatch.setattr(gate, '_load_restored_preflight', lambda: Restored)
    def identities(**kwargs):
        assert kwargs['parameters']['passfile'] == '/protected/passfile'
        assert 'pgpassFile' not in kwargs['parameters']
        assert kwargs['signed'] == {'database': 'aos_meta_head',
            'installationId': args['installation_id'], 'signedRoot': str(args['bundle_root']),
            'trustRoots': str(args['trust_roots_file'])}
        assert kwargs['credential_file'] == args['credential_file']
        assert kwargs['preparation_only'] is True
        return {'outcome': 'CURRENT_SIGNED_HOST_READONLY_PREFLIGHT_GREEN'}
    monkeypatch.setattr(gate, '_preflight_identities', identities)
    assert gate.preflight_restored(**args)['outcome'] == 'CURRENT_SIGNED_HOST_READONLY_PREFLIGHT_GREEN'
    assert calls == [{k: args[k] for k in ('identity_file', 'installation_id', 'bundle_root', 'trust_roots_file')}]


def test_restored_selector_failure_has_no_legacy_fallback_or_identity_probe(gate, monkeypatch):
    class Restored:
        @staticmethod
        def select_current_installation(**_):
            raise ValueError('sensitive failure details')
    monkeypatch.setattr(gate, '_load_restored_preflight', lambda: Restored)
    monkeypatch.setattr(gate, 'signed_preflight', lambda **_: pytest.fail('legacy fallback'))
    monkeypatch.setattr(gate, '_runtime_file_dsns', lambda *_a, **_k: pytest.fail('identity probe'))
    with pytest.raises(gate.HostPreflightBlocked, match='RESTORED_INSTALLATION_INVALID') as exc:
        gate.preflight_restored(**restored_arguments())
    assert 'sensitive' not in str(exc.value)


@pytest.mark.parametrize('change', ['database', 'installation', 'authorization', 'start'])
def test_restored_rejects_altered_reader_authority_before_identity_probe(gate, monkeypatch, change):
    args = restored_arguments()
    class Restored:
        @staticmethod
        def select_current_installation(**_):
            result = {'identity': {'database': 'aos_meta_head'},
                'currentInstallation': {'installationId': args['installation_id'],
                    'authorization': 'CURRENT_INSTALLATION_EVIDENCE_ONLY_NO_START',
                    'runtimeHostEnabled': False, 'apiStartAuthorized': False}}
            if change == 'database': result['identity']['database'] = 'other_database'
            if change == 'installation': result['currentInstallation']['installationId'] = 'other'
            if change == 'authorization': result['currentInstallation']['authorization'] = 'START'
            if change == 'start': result['currentInstallation']['runtimeHostEnabled'] = True
            return result
    monkeypatch.setattr(gate, '_load_restored_preflight', lambda: Restored)
    monkeypatch.setattr(gate, '_runtime_file_dsns', lambda *_a, **_k: pytest.fail('identity probe'))
    with pytest.raises(gate.HostPreflightBlocked, match='RESTORED_INSTALLATION_INVALID'):
        gate.preflight_restored(**args)


@pytest.mark.parametrize('argv', [
    ['--restored-api-identity', '/protected/restored.json'],
    ['--signed-receipt', '/signed/receipt', '--restored-api-identity', '/protected/restored.json'],
    ['--restored-api-identity', '/protected/restored.json', '--restored-installation', 'current',
     '--bundle-root', '/signed/root', '--trust-roots-file', '/signed/roots',
     '--credential-file', '/protected/planes'],
])
def test_cli_rejects_partial_mixed_or_nonpreparation_restored_route(gate, monkeypatch, argv):
    import sys
    monkeypatch.setattr(sys, 'argv', ['gate', *argv])
    monkeypatch.setattr(gate, 'preflight', lambda **_: pytest.fail('legacy fallback'))
    monkeypatch.setattr(gate, 'preflight_restored', lambda **_: pytest.fail('restored called'))
    with pytest.raises(SystemExit) as exc:
        gate.main()
    assert exc.value.code == 2


@pytest.fixture
def gate():
    spec = importlib.util.spec_from_file_location("a0v_current_runtime_host_preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def identity(role, oid, *, database="aos_current_preview_20260927", directory=False,
             runtime=False, privileged=False):
    return RuntimeDatabaseIdentity(
        authority=("172.0.0.2", 5432, database), session_user=role, role_oid=oid,
        directory_member=directory, runtime_member=runtime, privileged=privileged,
        owns_protected_relation=False,
    )


def test_missing_credentials_fail_before_signed_or_database_access(gate, monkeypatch):
    monkeypatch.setattr(gate, "signed_preflight", lambda **_: pytest.fail("signed preflight ran"))
    with pytest.raises(gate.HostPreflightBlocked, match="CREDENTIAL_FILE_REQUIRED"):
        gate.preflight(signed_receipt=Path("/unused"), credential_file=None)


def test_old_database_dsn_rejected_before_connection(gate):
    dsns = {plane: f"host=localhost dbname=aos_meta_head user={plane}"
            for plane in ("directory", "runtime", "web")}
    with pytest.raises(gate.HostPreflightBlocked, match="CREDENTIAL_DATABASE_DRIFT"):
        gate.require_current_dsn_targets(dsns, "aos_current_preview_20260927")


def test_signed_receipt_failure_rejected_before_credential_read(gate, monkeypatch):
    monkeypatch.setattr(gate, "signed_preflight", lambda **_: (_ for _ in ()).throw(ValueError("bad")))
    monkeypatch.setattr(gate, "_runtime_file_dsns", lambda *_: pytest.fail("credential file read"))
    with pytest.raises(gate.HostPreflightBlocked, match="SIGNED_INSTALLATION_INVALID"):
        gate.preflight(signed_receipt=Path("/invalid"), credential_file=Path("/protected/current.json"))


def test_old_database_credential_rejected_before_identity_connection(gate, monkeypatch):
    monkeypatch.setattr(gate, "signed_preflight", lambda **_: (
        {"dbname": "aos_current_preview_20260927"},
        {"database": "aos_current_preview_20260927"}))
    monkeypatch.setattr(gate, "_runtime_file_dsns", lambda *_a, **_k: ({
        plane: f"host=localhost dbname=aos_meta_head user={plane}"
        for plane in ("directory", "runtime", "web")}, [1, 2, 3, 4, 5]))
    monkeypatch.setattr(gate.psycopg, "connect", lambda *_a, **_k: pytest.fail("database connected"))
    with pytest.raises(gate.HostPreflightBlocked, match="CREDENTIAL_DATABASE_DRIFT"):
        gate.preflight(signed_receipt=Path("/signed"), credential_file=Path("/protected/old.json"))


@pytest.mark.parametrize("bad", [
    identity("web", 3, database="aos_meta_head"),
    identity("runtime", 2),
    identity("web", 3, privileged=True),
])
def test_mixed_same_role_or_privileged_identity_rejected(gate, bad):
    with pytest.raises(gate.HostPreflightBlocked, match="RUNTIME_IDENTITY_INVALID"):
        gate.require_current_identities(
            directory=identity("directory", 1, directory=True),
            runtime=identity("runtime", 2, runtime=True), web=bad,
            authority=("172.0.0.2", 5432, "aos_current_preview_20260927"),
        )


class ReadConn:
    read_only = True

    def __init__(self, assignment=None, candidates=None, enabled_bindings=0):
        self.assignment = assignment
        self.candidates = candidates
        self.enabled_bindings = enabled_bindings
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        if "extension_runtime_binding" in self.calls[-1][0]:
            return {"enabled_bindings": self.enabled_bindings}
        return self.assignment


def test_exact_host_assignment_and_identity_required(gate, monkeypatch):
    monkeypatch.setattr(gate, "read_candidates", lambda *_: pytest.fail("candidates read too early"))
    conn = ReadConn()
    with pytest.raises(gate.HostPreflightBlocked, match="HOST_ASSIGNMENT_MISSING"):
        gate.require_current_host_and_candidates(conn, identity("directory", 1, directory=True))
    assert conn.calls[0][1] == ("org-org", "dev-project")


def test_host_identity_must_match_directory_role_and_oid(gate, monkeypatch):
    monkeypatch.setattr(gate, "read_candidates", lambda *_: pytest.fail("candidates read too early"))
    conn = ReadConn({"state": "assigned", "host_id": "host-1", "database_role": "old-dir",
                     "database_role_oid": 99, "enabled": True})
    with pytest.raises(gate.HostPreflightBlocked, match="HOST_IDENTITY_MISMATCH"):
        gate.require_current_host_and_candidates(conn, identity("directory", 1, directory=True))


def test_missing_configuration_candidates_fail_closed(gate, monkeypatch):
    from aos_api.extension_runtime.runtime_configuration_candidates import RuntimeConfigurationCandidates
    monkeypatch.setattr(gate, "read_candidates", lambda *_: RuntimeConfigurationCandidates(
        {"budgets": 0}, ("budgets",), False))
    conn = ReadConn({"state": "assigned", "host_id": "host-1", "database_role": "directory",
                     "database_role_oid": 1, "enabled": True})
    with pytest.raises(gate.HostPreflightBlocked, match="CONFIGURATION_CANDIDATES_MISSING"):
        gate.require_current_host_and_candidates(conn, identity("directory", 1, directory=True))


def test_explicit_preparation_only_keeps_identity_gate_and_reports_missing_candidates(gate, monkeypatch):
    from aos_api.extension_runtime.runtime_configuration_candidates import RuntimeConfigurationCandidates
    monkeypatch.setattr(gate, "read_candidates", lambda *_: RuntimeConfigurationCandidates(
        {"budgets": 0}, ("budgets",), False))
    conn = ReadConn({"state": "assigned", "host_id": "host-1", "database_role": "directory",
                     "database_role_oid": 1, "enabled": True})
    result = gate.require_current_host_and_candidates(
        conn, identity("directory", 1, directory=True), preparation_only=True)
    assert result == {"hostId": "host-1", "candidateCounts": {"budgets": 0},
                      "admissionMode": "PREPARATION_ONLY"}
    assert conn.calls[0][1] == ("org-org", "dev-project")


def test_preparation_only_rejects_existing_enabled_binding(gate, monkeypatch):
    from aos_api.extension_runtime.runtime_configuration_candidates import RuntimeConfigurationCandidates
    monkeypatch.setattr(gate, "read_candidates", lambda *_: RuntimeConfigurationCandidates(
        {"budgets": 0}, ("budgets",), False))
    conn = ReadConn({"state": "assigned", "host_id": "host-1", "database_role": "directory",
                     "database_role_oid": 1, "enabled": True}, enabled_bindings=1)
    with pytest.raises(gate.HostPreflightBlocked, match="ACTIVE_BINDING_REQUIRES_FULL_HOST"):
        gate.require_current_host_and_candidates(
            conn, identity("directory", 1, directory=True), preparation_only=True)


def test_green_report_carries_exact_physical_authority_and_signed_paths(gate, monkeypatch):
    signed = {"database": "aos_current_preview_20260927", "installationId": "current-install",
              "signedRoot": "/signed/current", "trustRoots": "/signed/trust-roots.json"}
    monkeypatch.setattr(gate, "signed_preflight", lambda **_: ({"dbname": signed["database"]}, signed))
    monkeypatch.setattr(gate, "_runtime_file_dsns", lambda *_a, **_k: ({
        plane: f"dbname={signed['database']} user={plane}"
        for plane in ("directory", "runtime", "web")}, [1, 2, 3, 4, 5]))

    class Conn:
        read_only = False
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def execute(self, _query):
            assert self.read_only is True
            return self
        def fetchone(self):
            return {"server_addr": "172.0.0.2", "server_port": 5432,
                    "database_name": signed["database"]}

    monkeypatch.setattr(gate.psycopg, "connect", lambda *_a, **_k: Conn())
    roles = {"directory": identity("directory", 1, directory=True),
             "runtime": identity("runtime", 2, runtime=True),
             "web": identity("web", 3)}
    monkeypatch.setattr(gate, "probe_runtime_database_identity",
                        lambda conn, **kw: roles.pop(next(iter(roles))))
    monkeypatch.setattr(gate, "require_current_host_and_candidates",
                        lambda *_, **__: {"hostId": "host-1", "candidateCounts": {"budgets": 1},
                                          "admissionMode": "FULL"})
    report = gate.preflight(signed_receipt=Path("/signed/receipt.json"),
                            credential_file=Path("/protected/identities.json"))
    assert report["databaseAuthority"] == ["172.0.0.2", 5432, signed["database"]]
    assert report["signedRoot"] == signed["signedRoot"]
    assert report["trustRoots"] == signed["trustRoots"]
    assert report["credentialFileGeneration"] == [1, 2, 3, 4, 5]
    assert report["authorization"] == "PREFLIGHT_ONLY_NO_RUNTIME_START"
    generations = iter(([1, 2, 3, 4, 5], [1, 2, 3, 4, 6]))
    monkeypatch.setattr(gate, "_runtime_file_dsns", lambda *_a, **_k: ({
        plane: f"dbname={signed['database']} user={plane}"
        for plane in ("directory", "runtime", "web")}, next(generations)))
    roles = {"directory": identity("directory", 1, directory=True),
             "runtime": identity("runtime", 2, runtime=True),
             "web": identity("web", 3)}
    monkeypatch.setattr(gate, "probe_runtime_database_identity",
                        lambda conn, **kw: roles.pop(next(iter(roles))))
    with pytest.raises(gate.HostPreflightBlocked, match="CREDENTIAL_FILE_CHANGED"):
        gate.preflight(signed_receipt=Path("/signed/receipt.json"),
                       credential_file=Path("/protected/identities.json"))

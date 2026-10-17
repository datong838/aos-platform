"""Protected service schema/config gates; no mocked native acceptance."""
import hashlib
import json
from pathlib import Path

from pydantic import ValidationError
import pytest
from test_budget_policy_window_commands import command_payload


def closed_window_config(tmp_path):
    from tests.aip.test_budget_policy_renewal_connection import closed_config
    from aos_api.aip_budget_policy_window_service import PACKAGE_FILES, ROOT
    path, value = closed_config(tmp_path)
    value['schemaVersion'] = 'aos.budget-policy-window.private/v1'
    value['nativeManifestSha256'] = 'a'*64
    value['legacyManifestSha256'] = 'b'*64
    value['profiles']['consumer']['user'] = 'aos_budget_consumer_call'
    for profile in value['profiles'].values():
        profile.pop('manifestSha256')
        p = Path(profile['passfile'])
        p.write_text(f"{profile['host']}:{profile['port']}:{profile['database']}:{profile['user']}:fixture-only\n")
        profile['passfileSha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
    value['packageSources'] = {f: hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in PACKAGE_FILES}
    path.write_text(json.dumps(value))
    return path, value


@pytest.mark.parametrize('operation', ['propose', 'decide', 'revoke', 'consume'])
def test_exact_private_request_keeps_token_out_of_command(operation):
    from aos_api.aip_budget_policy_window_service import WindowRequest
    value = dict(schemaVersion=1, mode='execute', operation=operation, command=command_payload(operation))
    if operation in {'decide', 'revoke'}: value['bearerToken'] = 'synthetic-not-real-jwt'
    request = WindowRequest.model_validate(value).revalidated()
    assert request.command.operation == operation
    assert 'bearerToken' not in request.command.canonical_payload()
    assert 'synthetic-not-real-jwt' not in repr(request)


@pytest.mark.parametrize('operation', ['propose', 'consume'])
def test_machine_request_never_accepts_token_field(operation):
    from aos_api.aip_budget_policy_window_service import WindowRequest
    for token in (None, '', 'synthetic'):
        with pytest.raises(ValidationError):
            WindowRequest.model_validate(dict(schemaVersion=1, mode='execute', operation=operation,
                command=command_payload(operation), bearerToken=token))


@pytest.mark.parametrize('operation', ['decide', 'revoke'])
def test_issuer_missing_token_is_rejected(operation):
    from aos_api.aip_budget_policy_window_service import WindowRequest
    with pytest.raises(ValidationError):
        WindowRequest.model_validate(dict(schemaVersion=1, mode='execute', operation=operation,
            command=command_payload(operation)))


def test_closed_config_has_no_database_fallback(tmp_path, monkeypatch):
    from aos_api.aip_budget_policy_window_service import load_protected_config, open_purpose_connection, WindowServiceBlocked
    monkeypatch.setenv('AOS_DATABASE_URL', 'postgresql://unused@127.0.0.1:1/unused')
    path, _ = closed_window_config(tmp_path)
    config = load_protected_config(path)
    assert config.enabled is False
    with pytest.raises(WindowServiceBlocked, match='CLOSED_OR_DRIFTED'):
        with open_purpose_connection(config, 'maker', False): pytest.fail('closed config connected')


@pytest.mark.parametrize('change', ['identity', 'source', 'consumer', 'database', 'extraPassword', 'legacyPin', 'nativePin'])
def test_private_provenance_rejects_drift(tmp_path, change):
    from aos_api.aip_budget_policy_window_service import load_protected_config, WindowServiceBlocked
    path, value = closed_window_config(tmp_path)
    if change == 'identity': value['identityConfigSha256'] = '0'*64
    elif change == 'source': value['packageSources'][next(iter(value['packageSources']))] = '0'*64
    elif change == 'consumer': value['profiles']['consumer']['user'] = 'aos_budget_renewal_consumer_call'
    elif change == 'database': value['profiles']['consumer']['database'] = 'another'
    elif change == 'extraPassword': value['password'] = 'synthetic-sensitive-sentinel'
    elif change == 'legacyPin': value['legacyManifestSha256'] = 'bad'
    else: value['nativeManifestSha256'] = 'bad'
    path.write_text(json.dumps(value))
    with pytest.raises(WindowServiceBlocked) as error: load_protected_config(path)
    assert 'synthetic-sensitive-sentinel' not in str(error.value)


@pytest.mark.parametrize('kind', ['missing', 'relative', 'symlink', 'mode', 'duplicate'])
def test_private_file_boundary(tmp_path, kind):
    from aos_api.aip_budget_policy_window_service import load_protected_config, WindowServiceBlocked
    path, _ = closed_window_config(tmp_path)
    if kind == 'missing': path = path.parent/'absent.json'
    elif kind == 'relative': path = Path('private/absent.json')
    elif kind == 'symlink':
        link = path.parent/'alias.json'; link.symlink_to(path); path = link
    elif kind == 'mode': path.chmod(0o644)
    else: path.write_text('{"schemaVersion":1,"schemaVersion":2}')
    with pytest.raises(WindowServiceBlocked): load_protected_config(path)


def test_mutated_private_request_is_revalidated():
    from aos_api.aip_budget_policy_window_service import WindowRequest
    request = WindowRequest(schemaVersion=1, mode='execute', operation='consume', command=command_payload('consume'))
    with pytest.raises(ValidationError): request.model_copy(update={'operation': 'decide'}).revalidated()


def test_private_validation_error_does_not_echo_token():
    from aos_api.aip_budget_policy_window_service import WindowRequest
    secret = 'synthetic-private-jwt-sentinel'
    with pytest.raises(ValidationError) as error:
        WindowRequest.model_validate(dict(schemaVersion=1, mode='execute', operation='decide',
            command=command_payload('decide'), bearerToken=secret, actor='untrusted'))
    assert secret not in str(error.value)

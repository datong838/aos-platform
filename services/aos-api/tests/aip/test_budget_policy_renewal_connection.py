"""B protected connection boundary; fixture files, never live credentials."""
from pathlib import Path

import pytest


def private_file(tmp_path, text, *, mode=0o600):
    directory = tmp_path / 'private'
    directory.mkdir(mode=0o700)
    path = directory / 'renewal.json'
    path.write_text(text)
    path.chmod(mode)
    return path


def test_missing_private_config_never_uses_shared_api_dsn(tmp_path, monkeypatch):
    from aos_api.aip_budget_policy_renewal_connection import load_protected_config, RenewalConnectionBlocked
    monkeypatch.setenv('AOS_DATABASE_URL', 'postgresql://shared@127.0.0.1:1/unused')
    with pytest.raises(RenewalConnectionBlocked, match='PRIVATE_CONFIG'):
        load_protected_config(tmp_path / 'absent.json')


@pytest.mark.parametrize('file_mode,parent_mode', [(0o644,0o700),(0o600,0o755)])
def test_broad_file_or_directory_permissions_are_rejected(tmp_path,file_mode,parent_mode):
    from aos_api.aip_budget_policy_renewal_connection import load_protected_config, RenewalConnectionBlocked
    path=private_file(tmp_path,'{}',mode=file_mode)
    path.parent.chmod(parent_mode)
    with pytest.raises(RenewalConnectionBlocked, match='PRIVATE_CONFIG'):
        load_protected_config(path)


def test_symlink_private_configuration_is_not_followed(tmp_path):
    from aos_api.aip_budget_policy_renewal_connection import load_protected_config, RenewalConnectionBlocked
    path=private_file(tmp_path,'{}')
    link=path.parent/'alias.json'
    link.symlink_to(path)
    with pytest.raises(RenewalConnectionBlocked, match='PRIVATE_CONFIG'):
        load_protected_config(link)


def test_ancestor_symlink_cannot_hide_inside_private_directory(tmp_path):
    from aos_api.aip_budget_policy_renewal_connection import _private_bytes, RenewalConnectionBlocked
    path=private_file(tmp_path,'fixture-sensitive-sentinel')
    alias=tmp_path/'ancestor-alias'
    alias.symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(RenewalConnectionBlocked,match='PRIVATE_CONFIG'):
        _private_bytes(alias/'private'/'renewal.json')


def test_duplicate_json_keys_and_embedded_password_are_rejected_without_echo(tmp_path):
    from aos_api.aip_budget_policy_renewal_connection import load_protected_config, RenewalConnectionBlocked
    path=private_file(tmp_path,'{"schemaVersion":1,"schemaVersion":2,"password":"fixture-sensitive-sentinel"}')
    with pytest.raises(RenewalConnectionBlocked) as error:
        load_protected_config(path)
    assert 'fixture-sensitive-sentinel' not in str(error.value)


def test_relative_configuration_path_is_not_resolved_from_working_directory():
    from aos_api.aip_budget_policy_renewal_connection import load_protected_config, RenewalConnectionBlocked
    with pytest.raises(RenewalConnectionBlocked, match='PRIVATE_CONFIG'):
        load_protected_config(Path('private/renewal.json'))


def closed_config(tmp_path):
    import json,hashlib
    from aos_api.aip_budget_policy_renewal_connection import ROOT,PACKAGE_FILES,_CALLERS
    directory=tmp_path/'private'
    directory.mkdir(mode=0o700)
    issuer='http://127.0.0.1:18448/realms/qyh-local'
    oidc={'schemaVersion':'aos.local-management-oidc/v1','issuer':issuer,'audience':'aos-api',
          'clientId':'aos-api','jwksUrl':issuer+'/protocol/openid-connect/certs',
          'tokenUrl':issuer+'/protocol/openid-connect/token','clockSkewSeconds':0}
    identity=directory/'oidc.json';identity.write_text(json.dumps(oidc));identity.chmod(0o600)
    profiles={}
    for purpose,user in _CALLERS.items():
        password=directory/(purpose+'.pgpass')
        password.write_text(f'127.0.0.1:1:unused:{user}:fixture-only\n');password.chmod(0o600)
        profiles[purpose]={'host':'127.0.0.1','port':1,'database':'unused','user':user,
            'passfile':str(password),'passfileSha256':hashlib.sha256(password.read_bytes()).hexdigest(),
            'manifestSha256':'a'*64}
    value={'schemaVersion':'aos.budget-policy-renewal.private/v1','orgId':'org-org',
        'projectId':'dev-project','enabled':False,'identityConfigPath':str(identity),
        'identityConfigSha256':hashlib.sha256(identity.read_bytes()).hexdigest(),'profiles':profiles,
        'packageSources':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in PACKAGE_FILES}}
    path=directory/'renewal.json';path.write_text(json.dumps(value));path.chmod(0o600)
    return path,value


def test_complete_closed_provenance_loads_without_contacting_any_database(tmp_path):
    from aos_api.aip_budget_policy_renewal_connection import load_protected_config,open_purpose_connection,RenewalConnectionBlocked
    path,_=closed_config(tmp_path)
    config=load_protected_config(path)
    assert config.enabled is False
    assert config.binding.subject=='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
    assert len(config.profiles)==3
    with pytest.raises(RenewalConnectionBlocked,match='CLOSED_OR_DRIFTED'):
        with open_purpose_connection(config,'maker',False):
            pytest.fail('closed config yielded connection')


@pytest.mark.parametrize('drift',['identityHash','sourceHash','caller','wildcardCredential','differentDatabase'])
def test_complete_provenance_rejects_drift_before_connect(tmp_path,drift):
    import json
    from aos_api.aip_budget_policy_renewal_connection import load_protected_config,RenewalConnectionBlocked
    path,value=closed_config(tmp_path)
    if drift=='identityHash':value['identityConfigSha256']='b'*64
    elif drift=='sourceHash':value['packageSources'][next(iter(value['packageSources']))]='b'*64
    elif drift=='caller':value['profiles']['maker']['user']='aos_app'
    elif drift=='differentDatabase':value['profiles']['consumer']['database']='other'
    else:
        password=Path(value['profiles']['maker']['passfile'])
        password.write_text('*:*:*:*:fixture-only\n')
        import hashlib
        value['profiles']['maker']['passfileSha256']=hashlib.sha256(password.read_bytes()).hexdigest()
    path.write_text(json.dumps(value))
    with pytest.raises(RenewalConnectionBlocked):load_protected_config(path)

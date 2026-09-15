import importlib.util
from pathlib import Path
from unittest.mock import Mock
import pytest


@pytest.fixture
def launcher(monkeypatch):
    root=Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(root/'scripts'))
    spec=importlib.util.spec_from_file_location('controlled_api_launcher_test',root/'scripts/a0v_controlled_api.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_api_flags_do_not_start_other_writers(launcher,monkeypatch):
    monkeypatch.setattr(launcher,'require_leases',lambda:None)
    configure=Mock()
    monkeypatch.setattr(launcher,'_configure_environment',configure)
    for key in launcher.API_FLAGS:
        monkeypatch.setenv(key,'test-original')
    launcher.configure_environment()
    configure.assert_called_once()
    import os
    for key,value in launcher.API_FLAGS.items():assert os.environ[key]==value
    assert os.environ['AOS_EXTENSION_RUNTIME_HOST_ENABLED']=='0'
    assert os.environ['AOS_QYH_CRON_ENABLED']=='false'
    assert os.environ['AOS_JDBC_SSH_PREBUILD_ENABLED']=='false'
    assert os.environ['AOS_DB_MIGRATION_MODE']=='disabled'


def test_product_profile_uses_niushop_1_23_current_signed_root(monkeypatch):
    root=Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(root/'scripts'))
    import a0v_product_controlled_api as product
    launcher=product.load_launcher()
    assert launcher.BUNDLE_ROOT==(root.parent/
        '.aos-recovery-20260915/state/niushop-1.23-current-package/registry/signed-bundles-niushop-1.23-current')
    assert launcher.API_FLAGS['AOS_EXTENSION_RUNTIME_HOST_ENABLED']=='0'
    assert launcher.API_FLAGS['AOS_QYH_CRON_ENABLED']=='false'
    assert launcher.API_FLAGS['AOS_JDBC_SSH_PREBUILD_ENABLED']=='false'
    assert launcher.API_FLAGS['AOS_DB_MIGRATION_MODE']=='disabled'


def test_invalid_lease_blocks_before_environment(launcher,monkeypatch):
    configure=Mock()
    monkeypatch.setattr(launcher,'_configure_environment',configure)
    def deny():raise ValueError('lease unavailable')
    monkeypatch.setattr(launcher,'require_leases',deny)
    with pytest.raises(ValueError,match='lease unavailable'):launcher.configure_environment()
    configure.assert_not_called()


def test_product_identity_requires_matching_main_deployment(tmp_path,monkeypatch):
    import json
    root=Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(root/'scripts'))
    import a0v_product_controlled_api as product
    repo=tmp_path/'repo'
    assert product.registration_identity_reference(repo) is None
    state=tmp_path/'.aos-recovery-20260913/state/registration-deployment';state.mkdir(parents=True)
    (state/'registration-main-identity.json').write_text('private-reference-fixture')
    with pytest.raises(ValueError):product.registration_identity_reference(repo)
    proof=dict(outcome='REGISTRATION_IDENTITY_READ_VERIFIED',database='aos_meta_head',role='aos_ecommerce_registration_control',defaultActorDenied=True,negativeTenantDenied=True)
    (state/'identity-main.json').write_text(json.dumps(proof))
    assert product.registration_identity_reference(repo)==str(state/'registration-main-identity.json')
    proof['database']='clone'
    (state/'identity-main.json').write_text(json.dumps(proof))
    with pytest.raises(ValueError):product.registration_identity_reference(repo)


@pytest.fixture
def ui_profile(tmp_path,monkeypatch):
    import json,hashlib
    root=Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(root/'scripts'))
    import a0v_product_controlled_api as product
    repo=tmp_path/'repo'
    state=tmp_path/'.aos-recovery-20260913/state/ui-read-deployment';state.mkdir(parents=True)
    identity=state/'ui-read-main-identity.json'
    identity.write_text(json.dumps(dict(schemaVersion='aos.runtime-ui-api-identity/v1',role='aos_ui_read_transport_20260913',dsn='dbname=fixture user=aos_ui_read_transport_20260913')))
    identity.chmod(0o600)
    proof=dict(outcome='UI_READ_TRANSPORT_IDENTITY_VERIFIED',database='aos_meta_head',role='aos_ui_read_transport_20260913',reachableRole='aos_ui_read_api',positiveSubjectVerified=True,absentRequestReturnedNull=True,denials=['subject-mismatch','negative-tenant','direct-table','host-function'],identityFileHash='sha256:'+hashlib.sha256(identity.read_bytes()).hexdigest())
    evidence=state/'ui-identity-main-proof.json';evidence.write_text(json.dumps(proof))
    return product,repo,identity,evidence,proof


def test_ui_identity_accepts_private_proof_and_restores_environment(ui_profile,monkeypatch):
    import os
    product,repo,identity,_,_=ui_profile
    monkeypatch.setenv(product.UI_ENV,'previous-path')
    assert product.ui_identity_reference(repo)==str(identity)
    assert os.environ[product.UI_ENV]=='previous-path'


@pytest.mark.parametrize('change',['digest','database','denial','mode','missing-proof','missing-identity'])
def test_ui_identity_rejects_invalid_proof_or_private_file(ui_profile,change):
    import json
    product,repo,identity,evidence,proof=ui_profile
    if change=='digest':proof['identityFileHash']='sha256:wrong'
    elif change=='database':proof['database']='clone'
    elif change=='denial':proof['denials']=[]
    elif change=='mode':identity.chmod(0o644)
    elif change=='missing-proof':evidence.unlink()
    elif change=='missing-identity':identity.unlink()
    if change!='missing-proof':evidence.write_text(json.dumps(proof))
    with pytest.raises((ValueError,RuntimeError)):product.ui_identity_reference(repo)


def test_absent_ui_identity_cleans_inherited_configuration(ui_profile,monkeypatch):
    import os
    product,repo,identity,evidence,_=ui_profile
    identity.unlink();evidence.unlink()
    module=product.load_launcher()
    monkeypatch.setattr(module,'ROOT',repo)
    monkeypatch.setattr(module,'require_leases',lambda:None)
    monkeypatch.setattr(module,'_configure_environment',lambda *a,**kw:None)
    for key in (product.UI_ENV,*product.UI_ORIGINS):monkeypatch.setenv(key,'stale')
    module.configure_environment()
    assert all(key not in os.environ for key in (product.UI_ENV,*product.UI_ORIGINS))
    assert os.environ['AOS_EXTENSION_RUNTIME_HOST_ENABLED']=='0'
    assert os.environ['AOS_DB_MIGRATION_MODE']=='disabled'

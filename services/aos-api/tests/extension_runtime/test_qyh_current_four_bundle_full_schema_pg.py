"""Exact current signed four-pack protocol on a disposable full-schema database.

Fixture identities are not formal publishers/Owners; no Host or business runs.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from psycopg.conninfo import conninfo_to_dict

from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.signature import FileTrustRootProvider, FrozenTrustRootProvider
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.aip_responsibility_template_authority import ApprovedBIPreparationResolver, ActiveBIBusinessResolver
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

ROOT=Path(__file__).resolve().parents[4]
SCOPE=TenantScope('org-org','dev-project')
CASES=(('domain.ecommerce.core','1.4.3'),('platform.ecommerce.niushop','1.23.2'),
       ('solution.ecommerce.growth','1.13.0'),('solution.ecommerce.operations-base','1.2.2'))


def files_hash(root):
    rows={}
    for path in sorted(root.rglob('*')):
        assert not path.is_symlink()
        if path.is_file():rows[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
    return rows


def test_current_four_signed_packs_original_installation_stores_on_full161(tmp_path):
    parts=conninfo_to_dict(os.environ['AOS_DATABASE_URL'])
    assert (parts['host'],parts['port'])==('127.0.0.1','18431')
    assert parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')
    common=ROOT/'.evidence/qyh-full-system-restoration-20261011'
    bundle_root=common/'selected-public-bundles'
    trust_path=common/'restoration-public-trust-roots.json'
    before=files_hash(bundle_root)
    trust=FileTrustRootProvider(trust_path).snapshot()
    loader=ManifestLoader({'current-qyh':bundle_root},trust_roots=trust)
    registry=RegistryService(store=PostgresRegistryStore(connect),loader=loader,trust_roots=trust)
    with connect(SCOPE) as conn:
        assert conn.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']=='a0v_161'
        assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']=='7695416748450308141'
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','栖月汇 protocol fixture') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','fixture') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_org(id,name) VALUES('org-org','栖月汇 protocol fixture') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES('org-org','dev-project','fixture') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES('org-org','dev-project','fixture-qyh-maker','admin') ON CONFLICT DO NOTHING")
    for bid,version in CASES:
        ref='bundle://current-qyh/'+bid+'/'+version
        loaded=loader.load(ref)
        registry.create_bundle(publisher='aos',bundle_id=bid,kind=loaded.manifest.kind,
            display_name=loaded.manifest.metadata.display_name,actor='fixture-qyh-maker',roles={'developer'},publisher_scopes={'aos'})
        registry.create_version(publisher='aos',bundle_id=bid,source_ref=ref,
            actor='fixture-qyh-maker',roles={'developer'},publisher_scopes={'aos'})
        registry.validate(publisher='aos',bundle_id=bid,version=version,
            actor='fixture-qyh-validator',roles={'developer'},publisher_scopes={'aos'})
        registry.publish(publisher='aos',bundle_id=bid,version=version,
            actor='fixture-qyh-publisher',roles={'asset-publisher'},publisher_scopes={'aos'})
    spec=importlib.util.spec_from_file_location('original_installer',ROOT/'scripts/a0v_canonical_ecommerce_first_install.py')
    original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
    installed=original.create_approved_first_installation(connect_factory=connect,state_dir=tmp_path,
        core_version='1.4.3',adapter_version='1.23.2',growth_version='1.13.0',operations_version='1.2.2',
        trust_path=trust_path,idempotency_prefix='fixture-qyh-current161',overlay_revision='fixture-only-current161',
        display_name='栖月汇 current four-pack protocol fixture',maker_actor='fixture-qyh-maker',checker_actor='fixture-qyh-checker')
    assert installed['installationState']=='approved' and installed['installationEtag']==3
    assert installed['moduleCount']==8 and installed['edgeCount']==3
    assert {(r['bundleId'],r['version']) for r in installed['resolved']}==set(CASES)
    assert installed['transitions']==['submit','approve']
    store=PostgresInstallationStore(connect_factory=connect)
    actual=store.get_installation(org_id=SCOPE.org_id,project_id=SCOPE.project_id,installation_id=installed['installationId'])
    assert actual.state=='approved' and actual.etag_version==3
    lock=PostgresCompositionStore(connect).get_lock(org_id=SCOPE.org_id,project_id=SCOPE.project_id,
        composition_id=installed['compositionId'],revision=installed['lockRevision'])
    assert lock.lock_hash==installed['lockHash']
    resolver=ApprovedBIPreparationResolver(connect_factory=connect,registry_connect_factory=connect,
        release_root=bundle_root,trust_roots=trust,source_alias='current-qyh')
    selected=resolver.select(SCOPE)
    assert selected is not None and selected.installation_id==installed['installationId']
    assert 'solution.ecommerce.growth/1.13.0/' in selected.template_ref.resource_id
    assert resolver.select(TenantScope('dev-org','dev-project')) is None
    assert ApprovedBIPreparationResolver(connect_factory=connect,registry_connect_factory=connect,
        release_root=bundle_root,trust_roots=FrozenTrustRootProvider({}),source_alias='current-qyh').select(SCOPE) is None
    assert ActiveBIBusinessResolver(connect_factory=connect,registry_connect_factory=connect,
        release_root=bundle_root,trust_roots=trust,source_alias='current-qyh').select(SCOPE) is None
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM extension_runtime_binding WHERE org_id='org-org'").fetchone()['n']==0
        assert conn.execute("SELECT count(*) AS n FROM bundle_installation WHERE org_id='dev-org'").fetchone()['n']==0
    assert files_hash(bundle_root)==before

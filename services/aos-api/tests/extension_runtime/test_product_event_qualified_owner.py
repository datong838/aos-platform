"""Named release/source fakes test qualification composition, not real signatures."""
import json
from types import SimpleNamespace
from pathlib import Path
import pytest
from psycopg.pq import TransactionStatus
from tests.test_ecommerce_product_event_policy import case
from test_ecommerce_growth_registration_qualification import selected
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.extension_runtime.runtime_release_artifacts import CurrentRuntimeReleaseArtifacts
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.tenant_scope import TenantScope
import aos_api.ecommerce_product_event_qualified_owner as module


@pytest.fixture
def setup(monkeypatch):
    body,record=case();scope=TenantScope(body['orgId'],body['projectId']);bundle=selected();calls=[]
    lock=SimpleNamespace(payload=SimpleNamespace(resolved=[bundle]),lock_hash='sha256:'+'a'*64)
    store=object.__new__(PostgresInstallationStore)
    store.load_active_baseline_in_transaction=lambda *a,**kw:SimpleNamespace(lock=lock)
    artifacts=object.__new__(CurrentRuntimeReleaseArtifacts);artifacts.scope=scope
    artifacts.load_record=lambda _:SimpleNamespace(manifest=SimpleNamespace(spec=SimpleNamespace(exports=SimpleNamespace(schemas=('content/schemas/',)))))
    def read(*args):calls.append('artifact');return json.dumps(module.EVENT_CONTRACT).encode()
    artifacts.read_artifact=read
    source=object.__new__(PipelineSourceSelectionOwner)
    def current(conn,**kw):calls.append('source');return kw['execute'](record.draft,'compiled-mapping')
    source.run_current_snapshot=current
    def qualified(*a,**kw):
        calls.append('qualification')
        return dict(schemaVersion='aos.ecommerce.registration-release-qualification/v1',lockHash=lock.lock_hash,packageId=bundle.id,version=bundle.version,contentHash=bundle.content_hash,executable=False)
    monkeypatch.setattr(module,'qualify_registration_release',qualified)
    conn=SimpleNamespace(info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS),
        execute=lambda *a,**kw:calls.append('registry-lock'))
    owner=module.ProductEventQualifiedOwner(selections=source,installation_store=store,artifacts=artifacts,release_policy=ReleasePolicy(trust_roots=None))
    return owner,conn,scope,record,calls,artifacts


def run(data,execute=lambda *a:'saved'):
    owner,conn,scope,record,_,_=data
    return owner.run_current_snapshot(conn,scope=scope,ref=record.ref,actor='fixture',execute=execute)


def test_current_qualification_surrounds_work(setup):
    def save(*a):setup[4].append('save');return 'saved'
    assert run(setup,save)=='saved'
    assert setup[4]==['registry-lock','source','qualification','artifact','save','qualification','artifact']


@pytest.mark.parametrize('change',['missing-contract','changed-contract','release-denied','different-tenant'])
def test_old_or_unqualified_release_never_executes(setup,monkeypatch,change):
    if change=='missing-contract':setup[5].read_artifact=lambda *a:(_ for _ in ()).throw(LookupError('old package'))
    elif change=='changed-contract':setup[5].read_artifact=lambda *a:b'{}'
    elif change=='release-denied':monkeypatch.setattr(module,'qualify_registration_release',lambda *a,**kw:(_ for _ in ()).throw(PermissionError('revoked')))
    else:setup[5].scope=TenantScope('other','project')
    with pytest.raises((ValueError,PermissionError,LookupError)):
        run(setup,lambda *a:pytest.fail('must not run'))


def test_exported_contract_matches_host_protocol():
    path=Path(__file__).resolve().parents[4]/'bundles/solutions/ecommerce-growth'/module.CONTRACT_PATH
    assert json.loads(path.read_text())==module.EVENT_CONTRACT


def test_contract_boolean_is_not_an_integer(setup):
    setup[5].read_artifact=lambda *a:json.dumps(dict(module.EVENT_CONTRACT,saveEnabled=0)).encode()
    with pytest.raises(ValueError):run(setup,lambda *a:pytest.fail('must not run'))


def test_qualification_change_after_callback_does_not_return_success(setup):
    def save(*a):
        setup[5].read_artifact=lambda *a:b'{}'
        return 'pending-result'
    with pytest.raises(ValueError):run(setup,save)

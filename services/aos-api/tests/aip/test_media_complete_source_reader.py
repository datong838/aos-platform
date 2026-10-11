"""Wiring doubles test composition only, never real signed Source acceptance."""
import json,hashlib
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from psycopg import Connection,IsolationLevel
from psycopg.pq import TransactionStatus
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.contracts import BundleKind
from aos_api.aip_production_contracts import RegisterMediaGateProfileRequest
from aos_api.aip_production_contract_store import canonical_hash
from aos_api.tenant_scope import TenantScope
from aos_api.aip_media_gate_source_reader import CompleteMediaGateSourceReader
import aos_api.aip_media_gate_source_reader as m

@pytest.fixture
def case(monkeypatch,tmp_path):
    scope=TenantScope('org-org','dev-project');coordinate='aos/solution.fixture@1.0.0'
    specs=[{'testOnly':False,'kind':x} for x in ['fact','brand','copyright','platform']]
    gates=[{'gateId':'media.'+kind,'kind':kind,'returnStage':'review','ruleRef':{'resourceType':'EvalRuleRevision','resourceId':'fixture-rule-'+kind,'revision':1,'contentHash':canonical_hash({'ruleId':'fixture-rule-'+kind,'revision':1,'spec':spec})}} for kind,spec in zip(['fact','brand','copyright','platform'],specs)]
    document={'schema':'aos.ecommerce-media-gate-policy/v1','policyId':'fixture-policy','revision':1,'profileId':'fixture-full','profileRevision':1,'gates':gates};raw=json.dumps(document).encode();digest='sha256:'+hashlib.sha256(raw).hexdigest()
    material=dict(contentHash='sha256:'+'a'*64,signatureFingerprint='sha256:'+'b'*64,releaseEvidenceRevision='sha256:'+'c'*64,publicationSequence=2)
    loaded=SimpleNamespace(content_hash=material['contentHash'],manifest=SimpleNamespace(kind=BundleKind.SOLUTION_PACK),signature=object(),artifacts=[SimpleNamespace(relative_path='content/media-gate-policies/full.json',digest=digest)])
    record=SimpleNamespace(manifest=loaded.manifest,signature=loaded.signature)
    class Loader(ManifestLoader):
        def load(self,_):return loaded
        def read_verified_artifact(self,*a,**k):assert k['expected_digest']==digest;return raw
    loader=Loader({'fixture':tmp_path})
    conn=MagicMock(spec=Connection);conn.read_only=False;conn.isolation_level=IsolationLevel.SERIALIZABLE;conn.info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
    identity=dict(login='aos_contract_source_issuer',role='aos_contract_source_issuer',org='org-org',project='dev-project',runtime_member=False,checked_at=datetime.now(timezone.utc))
    receipts=[]
    for gate,spec in zip(gates,specs):receipts.append(dict(result_ref=gate['ruleRef'],request_hash=gate['ruleRef']['contentHash'],created_by='fixture-actor'))
    def execute(query,params=()):
        if 'session_user' in query:return SimpleNamespace(fetchone=lambda:identity)
        assert 'aip_production_contract_receipt' in query
        ref_id=params[2];return SimpleNamespace(fetchall=lambda:[r for r in receipts if r['result_ref']['resourceId']==ref_id])
    conn.execute.side_effect=execute;conn.commit.side_effect=lambda:pytest.fail('reader must not commit')
    class Store:
        def __init__(self,factory):self.factory=factory
        def get_version(self,*a):
            with self.factory() as c:assert c is conn
            return record
    class Service:
        def __init__(self,**kwargs):pass
        def get_published_reference_material(self,**kwargs):return material
    monkeypatch.setattr(m,'PostgresRegistryStore',Store);monkeypatch.setattr(m,'RegistryService',Service)
    monkeypatch.setattr(m._VersionRecord,'from_store',lambda x:x);monkeypatch.setattr(m,'_source_ref',lambda _: 'bundle://fixture/solution.fixture/1.0.0')
    monkeypatch.setattr(m,'configuration_source_acl_ready',lambda c:True)
    release=SimpleNamespace(publisher='aos',bundle_id='solution.fixture',version='1.0.0',content_hash=material['contentHash'],signature_fingerprint=material['signatureFingerprint'],release_evidence_revision=material['releaseEvidenceRevision'])
    view=SimpleNamespace(scope=scope.key,current_revision=1,active_revision=1,releases=(release,))
    monkeypatch.setattr(m,'_read_unique_active_in_transaction',lambda c,**k:view)
    def rule_read(self,s,ref,*,conn):
        assert s==scope
        return SimpleNamespace(spec=next(spec for g,spec in zip(gates,specs) if g['ruleRef']['resourceId']==ref.resource_id),content_hash=ref.content_hash,created_by='fixture-actor')
    monkeypatch.setattr(m.AipProductionContractStore,'get_review_rule_revision_with_content_integrity',rule_read)
    body=RegisterMediaGateProfileRequest.model_validate(dict(profileId='fixture-full',revision=1,sourceBundleRef=dict(resourceType='BundleManifestRevision',resourceId=coordinate,revision=2,contentHash='a'*64),signatureRef=dict(resourceType='BundleSignatureVerification',resourceId=coordinate,revision=2,contentHash='b'*64),policyRef=dict(resourceType='MediaGatePolicyRevision',resourceId=coordinate+'#fixture-policy',revision=1,contentHash=digest.removeprefix('sha256:')),gates=gates))
    return CompleteMediaGateSourceReader(loader=loader),conn,scope,body,identity,material,view,specs,receipts


def test_composition_same_transaction_no_commit(case):
    reader,conn,scope,body,*_=case
    assert reader(conn,scope,body) is True
    assert not conn.commit.called

@pytest.mark.parametrize('change',['readonly','isolation','role','tenant','runtimeMember','acl','sourceHash','signatureHash','policyHash','profile','installation','mixedRelease','testOnly','missingReceipt'])
def test_incomplete_or_forged_source_never_passes(case,monkeypatch,change):
    reader,conn,scope,body,identity,material,view,specs,receipts=case
    if change=='readonly':conn.read_only=True
    if change=='isolation':conn.isolation_level=IsolationLevel.READ_COMMITTED
    if change=='role':identity['role']='aos_runtime'
    if change=='tenant':identity['org']='dev-org'
    if change=='runtimeMember':identity['runtime_member']=True
    if change=='acl':monkeypatch.setattr(m,'configuration_source_acl_ready',lambda c:False)
    if change=='sourceHash':body=body.model_copy(update={'source_bundle_ref':body.source_bundle_ref.model_copy(update={'content_hash':'d'*64})})
    if change=='signatureHash':body=body.model_copy(update={'signature_ref':body.signature_ref.model_copy(update={'content_hash':'d'*64})})
    if change=='policyHash':body=body.model_copy(update={'policy_ref':body.policy_ref.model_copy(update={'content_hash':'d'*64})})
    if change=='profile':body=body.model_copy(update={'profile_id':'other'})
    if change=='installation':view.scope=('dev-org','dev-project')
    if change=='mixedRelease':view.releases[0].signature_fingerprint='sha256:'+'d'*64
    if change=='testOnly':specs[0]['testOnly']=True
    if change=='missingReceipt':receipts.clear()
    assert reader(conn,scope,body) is False


def test_unclassified_database_error_propagates(case):
    reader,conn,scope,body,*_=case;conn.execute.side_effect=PermissionError('fixture-denied')
    with pytest.raises(PermissionError):reader(conn,scope,body)

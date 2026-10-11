"""Real signature fixtures validate material; never authorize a tenant installation."""
from copy import deepcopy
import pytest
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.errors import AssetRegistryError
from tests.asset_registry.test_release_policy import _record, NOW


def fixture():
    record,roots=_record()
    roots.snapshot=lambda:roots
    snapshot=[x.model_dump(mode='json',by_alias=True,exclude_none=False) for x in record.evidence]
    snapshot.sort(key=lambda x:(x['type'],x['artifactRef']))
    raw=dict(publisher=record.publisher,bundleId=record.manifest.metadata.id,kind=record.manifest.kind.value,displayName=record.manifest.metadata.display_name,version=record.manifest.metadata.version,manifest=record.manifest.model_dump(mode='json',by_alias=True),contentHash=record.content_hash,signature=record.signature.model_dump(mode='json',by_alias=True),status='published',evidence=deepcopy(snapshot),artifacts=record.artifacts,createdBy='fixture-creator',lifecycleEvents=[dict(sequence=n,fromStatus=start,toStatus=end,actor=actor,evidenceRevision=canonical_sha256(snapshot),evidenceSnapshot=deepcopy(snapshot)) for n,start,end,actor in [(1,'draft','validated','fixture-validator'),(2,'validated','published','fixture-publisher')]])
    class Store:
        def get_version(self,*args):return deepcopy(raw)
    return RegistryService(store=Store(),loader=object(),trust_roots=roots,clock=lambda:NOW),raw


def test_native_publication_sequence_not_hash_or_generated_revision():
    service,raw=fixture()
    result=service.get_published_reference_material(bundle_id=raw['bundleId'],version=raw['version'],publisher=raw['publisher'])
    assert result['publicationSequence']==2
    assert result['contentHash']==raw['contentHash']
    assert result['tenantInstallationVerified'] is False and result['mediaPolicyVerified'] is False
    assert not {'actor','reason','evidenceSnapshot','lifecycleEvents'} & set(result)

@pytest.mark.parametrize('mutation',['status','legacy','noSnapshot','snapshotHash','evidenceChanged','creatorPublishes','validatorPublishes','badSignature'])
def test_published_material_refuses_untrusted_or_drifted_publication(mutation):
    service,raw=fixture()
    if mutation=='status':raw['status']='validated'
    if mutation=='legacy':raw['lifecycleEvents'][-1]['evidenceRevision']='sha256:'+'0'*64;raw['lifecycleEvents'][-1]['evidenceSnapshot']=None
    if mutation=='noSnapshot':raw['lifecycleEvents'][-1]['evidenceSnapshot']=None
    if mutation=='snapshotHash':raw['lifecycleEvents'][-1]['evidenceRevision']='sha256:'+'b'*64
    if mutation=='evidenceChanged':raw['evidence'][0]['metadata']={'drift':True}
    if mutation=='creatorPublishes':raw['lifecycleEvents'][-1]['actor']='fixture-creator'
    if mutation=='validatorPublishes':raw['lifecycleEvents'][-1]['actor']='fixture-validator'
    if mutation=='badSignature':raw['signature']['signature']='invalid'
    with pytest.raises(AssetRegistryError):service.get_published_reference_material(bundle_id=raw['bundleId'],version=raw['version'],publisher=raw['publisher'])

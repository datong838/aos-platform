from pathlib import Path
from types import SimpleNamespace as NS
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
from a0v_firstchain_capability_bindings import AUTHORITY, require_license, require_contract


@pytest.mark.parametrize('fault',[None,'foreign_subject','commercial','authorization','unfrozen','coverage'])
def test_license_requires_internal_exact_subjects(fault):
    skills=[NS(skill_id='ecommerce.skill.'+x,revision=2) for x in ('D01','D02','D03')]
    row={'lifecycle':'frozen','coverage':'complete','subject_refs':[{'resourceType':'SkillTemplate','resourceId':s.skill_id,'revision':'2'} for s in skills],
        'license_summary':{'authorizationRef':AUTHORITY,'sourceLicense':'internal','commercialLicenseAsserted':False,'externalPublicationAuthorized':False}}
    if fault=='foreign_subject':row['subject_refs'][0]['resourceId']='foreign'
    if fault=='commercial':row['license_summary']['commercialLicenseAsserted']=True
    if fault=='authorization':row['license_summary']['authorizationRef']='other'
    if fault=='unfrozen':row['lifecycle']='draft'
    if fault=='coverage':row['coverage']='incomplete'
    if fault:
        with pytest.raises(ValueError,match='LICENSE_SCOPE'):require_license(row,skills)
    else:require_license(row,skills)


@pytest.mark.parametrize('fault',[None,'hash','gate','schema','kind','draft'])
def test_contract_retains_exact_skill_gate_lineage(fault):
    skill=NS(skill_id='ecommerce.skill.D01',release_gate_ref=NS(asset_id='gate',content_hash='a'*64))
    row={'lifecycle':'frozen','release_gate_ref':{'resourceType':'ReleaseGateDecision','resourceId':'gate','contentHash':'a'*64},
         'artifact_schema_ref':{'resourceId':'SkillPublicationContract.D01'},'gate_policy':{'evidenceKind':'isolated_skill_contract'}}
    if fault=='hash':row['release_gate_ref']['contentHash']='b'*64
    if fault=='gate':row['release_gate_ref']['resourceId']='other'
    if fault=='schema':row['artifact_schema_ref']['resourceId']='SkillPublicationContract.D02'
    if fault=='kind':row['gate_policy']['evidenceKind']='business_result'
    if fault=='draft':row['lifecycle']='draft'
    if fault:
        with pytest.raises(ValueError,match='CONTRACT_LINEAGE'):require_contract(row,skill)
    else:require_contract(row,skill)

@pytest.mark.parametrize('fault',['missing','future','expired','provider','unhealthy'])
def test_activation_refuses_unusable_health(fault):
    from contextlib import contextmanager
    from datetime import UTC,datetime,timedelta
    import a0v_firstchain_capability_activate as activate
    from a0v_firstchain_capability_bindings import exact
    now=datetime.now(UTC);provider=exact('ProviderInstanceRevision','provider',1,'a'*64)
    row={'status':'healthy','observed_at':now-timedelta(minutes=1),'expires_at':now+timedelta(minutes=1),
        'provider_ref':provider.model_dump(mode='json',by_alias=True)}
    if fault=='missing':row=None
    if fault=='future':row['observed_at']=now+timedelta(minutes=2)
    if fault=='expired':row['expires_at']=now-timedelta(seconds=1)
    if fault=='provider':row['provider_ref']['contentHash']='b'*64
    if fault=='unhealthy':row['status']='unknown'
    @contextmanager
    def connect(scope):yield NS(execute=lambda *a:NS(fetchone=lambda:row))
    with pytest.raises(ValueError,match='EXACT_HEALTH'):activate.latest_health(connect,provider)


def test_blocked_preview_never_creates_binding_service(monkeypatch):
    import a0v_firstchain_capability_activate as activate
    monkeypatch.setattr(activate,'prepare',lambda *_: (None,None,[('D01',None,None,NS(readiness=NS(value='blocked'),reasons=['stale']))]))
    def forbidden(*a,**k):raise AssertionError('write service created')
    monkeypatch.setattr(activate,'AipCapabilityBindingService',forbidden)
    with pytest.raises(ValueError,match='DEPENDENCIES_BLOCKED'):activate.run('aos_meta_head')


def test_successor_binding_namespace_is_explicit_and_legacy_stable():
    from a0v_firstchain_capability_bindings import binding_namespace
    assert binding_namespace(2)=='a0v-firstchain-'
    assert binding_namespace(3)=='a0v-model-successor-r3-'
    with pytest.raises(ValueError):binding_namespace(4)

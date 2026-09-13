from datetime import timedelta
import json
import pytest

from test_a0v_text_eval_evidence import NOW, PROVIDER, NETWORK, records
from a0v_text_eval_profiles import get_profile
from a0v_text_eval_evidence import expected_identity, read_verified_text_evidence, TextEvidenceBlocked
from a0v_exact_text_live_eval import execute_case, run


def read(root, name):
    return read_verified_text_evidence(root, provider=PROVIDER, network=NETWORK,
        provider_model_id='agnes-2.5-flash', approval_ref='approved', checked_at=NOW,
        profile_name=name)


def v2_records(root):
    profile=get_profile('text-readiness-v2')
    for case in profile.cases:
        body={'identity':expected_identity(case,PROVIDER,NETWORK,'agnes-2.5-flash','approved',
                  max_output_tokens=profile.max_output_tokens),
              'status':'completed','result':{'status':'healthy','response_model':'agnes-2.5-flash',
                  'prompt_tokens':10,'completion_tokens':40,'total_tokens':50,'latency_ms':1,
                  'answer_present':True,'response_contract_passed':True,
                  'observed_at':(NOW-timedelta(minutes=1)).isoformat()}}
        (root/(case[0]+'.json')).write_text(json.dumps(body))


def test_profiles_have_distinct_requests_and_bounded_budget():
    old,new=get_profile('legacy-v1'),get_profile('text-readiness-v2')
    assert len(old.cases)==len(new.cases)==3
    assert old.max_output_tokens==32 and new.max_output_tokens==256
    assert not {x[1] for x in old.cases}&{x[1] for x in new.cases}
    assert run(profile_name='text-readiness-v2')['providerCalls']==0
    with pytest.raises(ValueError):get_profile('arbitrary')


def test_v2_evidence_is_not_legacy_and_cannot_mix(tmp_path):
    v2_records(tmp_path)
    result=read(tmp_path,'text-readiness-v2')
    assert result['profile']=='text-readiness-v2'
    assert result['providerCalls']==result['databaseWrites']==0
    with pytest.raises(TextEvidenceBlocked):read(tmp_path,'legacy-v1')
    old=tmp_path/'old';old.mkdir();records(old)
    (tmp_path/'instruction.json').write_bytes((old/'instruction.json').read_bytes())
    with pytest.raises(TextEvidenceBlocked):read(tmp_path,'text-readiness-v2')


def test_legacy_shape_preserved(tmp_path):
    records(tmp_path)
    assert 'profile' not in read(tmp_path,'legacy-v1')


def test_v2_result_still_requires_cap_and_exact_pass(tmp_path):
    v2_records(tmp_path)
    p=tmp_path/'instruction.json';body=json.loads(p.read_text())
    body['result'].update(completion_tokens=257,total_tokens=267)
    p.write_text(json.dumps(body))
    with pytest.raises(TextEvidenceBlocked,match='USAGE'):read(tmp_path,'text-readiness-v2')


def test_v2_cannot_overwrite_or_resend_original_unresolved(tmp_path):
    p=tmp_path/'instruction.json'
    p.write_text(json.dumps(dict(status='submitted',identity={'requestHash':'old'})))
    before=p.read_bytes()
    with pytest.raises(RuntimeError,match='DRIFT'):
        execute_case(p,{'requestHash':'new'},lambda:pytest.fail('must not call'))
    assert p.read_bytes()==before


def test_frozen_renewal_profile_cannot_switch_before_database_access(tmp_path):
    import a0v_formal_text_model as model
    plan={'renewal':True,'evidenceDirectory':str(tmp_path/'evidence'),
          'evidenceProfile':'text-readiness-v2'}
    plan['planHash']=model.canonical_hash(plan)
    (tmp_path/'plan.json').write_text(json.dumps(plan))
    def forbidden(*args):pytest.fail('must not connect')
    with pytest.raises(ValueError,match='PROFILE_DRIFT'):
        model.freeze_plan(forbidden,tmp_path,renew=True,evidence_dir=tmp_path/'evidence')
    assert model.freeze_plan(forbidden,tmp_path,renew=True,evidence_dir=tmp_path/'evidence',
        profile_name='text-readiness-v2')==plan

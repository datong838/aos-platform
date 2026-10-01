"""Envelope isolation tests; no issuer, runtime permission or real Provider proof."""
from copy import deepcopy
import hashlib
import json
import pytest
from pydantic import ValidationError
from aos_api.aip_eval_subject_proof_contracts import (
    SubjectReviewEnvelope, canonical_subject_envelope_bytes, subject_envelope_hash,
    require_subject_bytes,
)


def payload():
    def revision(kind, name):
        return dict(resourceType=kind, resourceId=name, revision=1, contentHash='a'*64)
    def asset(kind, name):
        return dict(assetType=kind, assetId=name, revision='1', contentHash='a'*64)
    attempt=dict(resourceType='StepRunAttempt',runId='task',stepKey='solution-design',stepRunId='step',attempt=1,inputHash='a'*64)
    return dict(tenant=dict(orgId='org-org',projectId='dev-project'), taskRunId='task',
        evalRunId='eval',caseId='case',suiteRef=asset('eval_suite','suite'),
        judgeRef=dict(judgeId='judge',revision=1,contentHash='a'*64),
        ruleInputHash='b'*64,expectedHash='c'*64,
        generationSkillRef=asset('skill_template','ecommerce.skill.D03'),
        generationAttemptRef=attempt,agentRunId='agent',requestHash='d'*64,
        queryRef=dict(resourceType='Artifact',resourceId='query',contentHash='e'*64),
        subjectArtifactRef=dict(resourceType='Artifact',resourceId='output',contentHash='f'*64),
        queryBytesHash=hashlib.sha256(b'query').hexdigest(),
        subjectBytesHash=hashlib.sha256(b'body\n').hexdigest(),
        subjectRef=revision('GrowthPlanRevision','plan'),stage='solution-design',stageAttemptRef=attempt,
        contractRef=revision('EvalContractRevision','contract'),policyRef=revision('EvalContractRevision','policy'),
        cutoff='2026-10-01T08:00:00Z',packageHash='1'*64,generation=1,epoch=1,
        configurationRef=revision('RuntimeConfigurationRevision','config'),commandKey='command')


def test_canonical_is_domain_separated_and_timezone_normalized():
    a=SubjectReviewEnvelope.model_validate(payload())
    p=payload();p['cutoff']='2026-10-01T16:00:00+08:00'
    b=SubjectReviewEnvelope.model_validate_json(json.dumps(dict(reversed(list(p.items())))))
    assert canonical_subject_envelope_bytes(a).startswith(b'AOS-EVAL-SUBJECT-ENVELOPE-v1\n')
    assert subject_envelope_hash(a)==subject_envelope_hash(b)
    require_subject_bytes(a,query=b'query',subject=b'body\n')
    with pytest.raises(ValueError):require_subject_bytes(a,query=b'query',subject=b'body')


@pytest.mark.parametrize('field',['tenant','evalRunId','caseId','suiteRef','judgeRef','ruleInputHash',
    'expectedHash','generationSkillRef','generationAttemptRef','agentRunId','requestHash','queryRef',
    'subjectArtifactRef','queryBytesHash','subjectBytesHash','subjectRef','stageAttemptRef','contractRef',
    'policyRef','cutoff','packageHash','generation','epoch','configurationRef','commandKey'])
def test_each_provenance_component_changes_signed_hash(field):
    p=payload(); original=subject_envelope_hash(SubjectReviewEnvelope.model_validate(p))
    value=deepcopy(p[field])
    if isinstance(value,dict):
        key=next(k for k in ('contentHash','inputHash','orgId') if k in value)
        value[key]='9'*64 if key!='orgId' else 'other-org'
    elif isinstance(value,int):value+=1
    elif field=='cutoff':value='2026-10-01T08:00:01Z'
    elif len(value)==64:value='9'*64
    else:value+='-other'
    p[field]=value
    assert subject_envelope_hash(SubjectReviewEnvelope.model_validate(p))!=original


@pytest.mark.parametrize('fault',['missing','extra','bool','nested_bool','naive','suite','skill','run','blank_tenant','bad_ref_hash'])
def test_invalid_envelope_rejected(fault):
    p=payload()
    if fault=='missing':del p['queryBytesHash']
    elif fault=='extra':p['executionAllowed']=True
    elif fault=='bool':p['epoch']=True
    elif fault=='nested_bool':p['stageAttemptRef']['attempt']=True
    elif fault=='naive':p['cutoff']='2026-10-01T08:00:00'
    elif fault=='suite':p['suiteRef']['assetType']='policy'
    elif fault=='skill':p['generationSkillRef']['assetType']='registered_model'
    elif fault=='run':p['stageAttemptRef']['runId']='other-task'
    elif fault=='blank_tenant':p['tenant']['orgId']=' '
    else:p['subjectRef']['contentHash']='invalid'
    with pytest.raises(ValidationError):SubjectReviewEnvelope.model_validate(p)


def test_unvalidated_model_copy_cannot_be_signed():
    a=SubjectReviewEnvelope.model_validate(payload()).model_copy(update={'epoch':True})
    with pytest.raises(ValueError):canonical_subject_envelope_bytes(a)


@pytest.mark.parametrize('stage', ['portrait', 'diagnosis', 'solution-design'])
def test_original_domain_stage_vocabulary(stage):
    p=payload(); p['stage']=stage
    p['stageAttemptRef']['stepKey']=stage
    assert SubjectReviewEnvelope.model_validate(p).stage==stage


@pytest.mark.parametrize('value', [True, 1.0, '1'])
@pytest.mark.parametrize('field,key', [('judgeRef','revision'),('subjectRef','revision'),
    ('configurationRef','revision'),('contractRef','revision'),('policyRef','revision'),
    ('stageAttemptRef','attempt'),('generationAttemptRef','attempt')])
def test_reference_numbers_are_not_coerced(field,key,value):
    p=payload();p[field][key]=value
    with pytest.raises(ValidationError):SubjectReviewEnvelope.model_validate(p)

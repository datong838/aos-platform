"""Original package dispatch and algorithms; sources are explicit test fixtures."""
from copy import deepcopy
from hashlib import sha256
import importlib
import json

import pytest

from test_analyst_package_proposals import BACKEND, sample
from test_analyst_structure_case import query

OPERATION = 'ecommerce_growth_analysis_advance'


def request(monkeypatch, stage='portrait'):
    text = json.dumps(sample('growth' if stage == 'solution-design' else stage), ensure_ascii=False)
    return dict(kind='evaluate_stage_structure', stage=stage, query=query(monkeypatch, stage),
                subjectArtifactRef=dict(resourceType='Artifact', resourceId='original-text',
                                        contentHash=sha256(text.encode()).hexdigest()),
                subjectText=text)


@pytest.fixture()
def package(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    return importlib.import_module('ecommerce_growth')


@pytest.mark.parametrize('stage', ['portrait', 'diagnosis', 'solution-design'])
def test_dispatch_evaluates_original_text_against_original_query(package, monkeypatch, stage):
    body = request(monkeypatch, stage)
    before = deepcopy(body)
    expected = dict(schemaVersion='aos.analyst-structure-result/v1', stage=stage,
                    structurePassed=True, detailCode='STRUCTURE_VALID')
    assert package.handle(OPERATION, body, object()) == expected
    assert package.handle(OPERATION, body, object()) == expected
    assert body == before
    assert 'subjectText' not in expected and 'gatePassed' not in expected


@pytest.mark.parametrize('stage', ['portrait', 'diagnosis', 'solution-design'])
def test_bad_answer_produces_real_negative_result_without_text(package, monkeypatch, stage):
    body = request(monkeypatch, stage)
    body['subjectText'] = '{"private":"DO_NOT_ECHO","approvedAt":"forged"}'
    body['subjectArtifactRef']['contentHash'] = sha256(body['subjectText'].encode()).hexdigest()
    result = package.handle(OPERATION, body, object())
    assert result == dict(schemaVersion='aos.analyst-structure-result/v1', stage=stage,
                         structurePassed=False, detailCode='ANSWER_STRUCTURE_INVALID')
    assert 'DO_NOT_ECHO' not in json.dumps(result)


@pytest.mark.parametrize('fault', ['extra', 'missing', 'body_hash', 'source_hash',
                                 'manual_case', 'stage', 'subject_scope', 'query_type'])
def test_inexact_or_tampered_message_rejected_without_source_excerpt(package, monkeypatch, fault):
    body = request(monkeypatch)
    if fault == 'extra': body['approved'] = True
    if fault == 'missing': body.pop('subjectArtifactRef')
    if fault == 'body_hash': body['subjectText'] += 'DO_NOT_ECHO'
    if fault == 'source_hash':
        value = json.loads(body['query'])
        value['sources'][0]['items'][0]['payload']['private'] = 'DO_NOT_ECHO'
        body['query'] = json.dumps(value)
    if fault == 'manual_case': body['caseInput'] = {'sourceCount': 1}
    if fault == 'stage': body['stage'] = 'unknown'
    if fault == 'subject_scope': body['subjectArtifactRef']['orgId'] = 'dev-org'
    if fault == 'query_type': body['query'] = {'private': 'DO_NOT_ECHO'}
    with pytest.raises(ValueError) as error:
        package.handle(OPERATION, body, object())
    assert str(error.value) in {'INVALID_STRUCTURE_MESSAGE', 'INVALID_GENERATION_CONTEXT', 'INVALID_STRUCTURE_INPUT'}
    assert 'DO_NOT_ECHO' not in str(error.value)


def test_fixed_message_cannot_be_used_on_review_or_unknown_operation(package, monkeypatch):
    body = request(monkeypatch)
    with pytest.raises(PermissionError):
        package.handle('ecommerce_growth_review_advance', body, object())
    with pytest.raises(ValueError, match='unregistered'):
        package.handle('caller_chosen_operation', body, object())
    body['kind'] = 'caller_chosen_kind'
    with pytest.raises(PermissionError):
        package.handle(OPERATION, body, object())

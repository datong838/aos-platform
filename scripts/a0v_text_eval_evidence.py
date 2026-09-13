"""Read existing trusted local probe evidence; never call or publish a model."""
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path

from a0v_exact_text_live_eval import digest
from a0v_text_eval_profiles import get_profile
from aos_api.aip_r1_bootstrap_probe import R1BootstrapProbeRequest


class TextEvidenceBlocked(ValueError):
    pass


def expected_identity(case, provider, network, provider_model_id, approval_ref, *, max_output_tokens=32):
    case_id, prompt, expected = case
    request = R1BootstrapProbeRequest(
        provider=provider, networkPolicy=network, providerModelId=provider_model_id,
        dataClassification='public_catalog', prompt=prompt,
        expectedResponseBehavior='exact_text', expectedText=expected,
        approvalRef=approval_ref, maxOutputTokens=max_output_tokens,
    )
    return dict(caseId=case_id, requestHash=digest(request.model_dump(mode='json')),
                provider=provider.model_dump(mode='json'), network=network.model_dump(mode='json'))


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise TextEvidenceBlocked('EVAL_EVIDENCE_DUPLICATE_FIELD')
        value[key] = item
    return value


def read_verified_text_evidence(state_dir, *, provider, network, provider_model_id,
                                approval_ref, checked_at, profile_name="legacy-v1"):
    profile = get_profile(profile_name)
    if not isinstance(checked_at, datetime) or checked_at.utcoffset() is None:
        raise TextEvidenceBlocked('EVAL_EVIDENCE_CHECK_TIME_REQUIRED')
    checked_at = checked_at.astimezone(UTC)
    cases = []
    for case in profile.cases:
        path = Path(state_dir) / (case[0] + '.json')
        try:
            if path.is_symlink():
                raise TextEvidenceBlocked('EVAL_EVIDENCE_SYMLINK')
            with path.open('rb') as stream:
                raw = stream.read(16385)
            if len(raw) > 16384:
                raise TextEvidenceBlocked('EVAL_EVIDENCE_TOO_LARGE')
            body = json.loads(raw, object_pairs_hook=_unique_object)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise TextEvidenceBlocked('EVAL_EVIDENCE_UNREADABLE') from None
        identity = expected_identity(case, provider, network, provider_model_id, approval_ref,
                                     max_output_tokens=profile.max_output_tokens)
        if (not isinstance(body, dict) or set(body) != {'identity', 'status', 'result'}
                or body['status'] != 'completed' or digest(body['identity']) != digest(identity)):
            raise TextEvidenceBlocked('EVAL_EVIDENCE_IDENTITY_OR_STATE_DRIFT')
        result = body['result']
        if not isinstance(result, dict) or set(result) != {
            'status', 'response_model', 'prompt_tokens', 'completion_tokens', 'total_tokens',
            'latency_ms', 'answer_present', 'response_contract_passed', 'observed_at',
        }:
            raise TextEvidenceBlocked('EVAL_EVIDENCE_RESULT_SHAPE')
        if (result['status'] != 'healthy' or result['response_model'] != provider_model_id
                or result['answer_present'] is not True or result['response_contract_passed'] is not True):
            raise TextEvidenceBlocked('EVAL_EVIDENCE_CONTRACT_FAILED')
        for key in ('prompt_tokens', 'completion_tokens', 'total_tokens', 'latency_ms'):
            if type(result[key]) is not int or result[key] < 0:
                raise TextEvidenceBlocked('EVAL_EVIDENCE_USAGE_INVALID')
        if (result['total_tokens'] != result['prompt_tokens'] + result['completion_tokens']
                or result['completion_tokens'] > profile.max_output_tokens):
            raise TextEvidenceBlocked('EVAL_EVIDENCE_USAGE_INVALID')
        try:
            observed = datetime.fromisoformat(result['observed_at'])
            if observed.utcoffset() is None:
                raise ValueError('timezone required')
            observed = observed.astimezone(UTC)
        except (ValueError, TypeError):
            raise TextEvidenceBlocked('EVAL_EVIDENCE_TIME_INVALID') from None
        if not observed <= checked_at < observed + timedelta(hours=24):
            raise TextEvidenceBlocked('EVAL_EVIDENCE_OUTSIDE_WINDOW')
        cases.append(dict(caseId=case[0], requestHash=identity['requestHash'],
            evidenceHash=hashlib.sha256(raw).hexdigest(), observedAt=observed.isoformat(),
            promptTokens=result['prompt_tokens'], completionTokens=result['completion_tokens'],
            totalTokens=result['total_tokens'], latencyMs=result['latency_ms']))
    evidence = dict(schemaVersion='a0v.verified-text-evidence/v1',
        provider=provider.model_dump(mode='json'), network=network.model_dump(mode='json'),
        providerModelId=provider_model_id, cases=cases)
    if profile_name != 'legacy-v1':
        evidence['profile'] = profile_name
    return {**evidence, 'sourceHash': digest(evidence), 'checkedAt': checked_at.isoformat(),
            'providerCalls': 0, 'databaseWrites': 0}

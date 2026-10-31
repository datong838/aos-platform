"""Complete original Model/Route subject bytes for a future signed manifest.

This pure binding neither reads current authority nor verifies signatures. Its
bytes cannot authorize execution, publication, or substitute for persisted proof.
"""
from __future__ import annotations

import json

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_model_eval_execution_contracts import _plain_contract_input
from aos_api.aip_model_runtime_contracts import (
    ModelEvalCandidate, ModelRouteRevision, ModelRuntimeLifecycle,
    RegisteredModelRevision, RuntimePolicyRevision,
)
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore, canonical_hash, evaluation_candidate_ref,
)
from aos_api.tenant_scope import TenantScope

_DOMAIN = b'AOS-MODEL-ROUTE-EVAL-SUBJECT-BINDING-v1\n'


def _strict_revisions(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'revision', 'expected_head_version', 'expectedHeadVersion'}:
                if type(item) is not int or item < 1:
                    raise ValueError('native positive integer revisions and head required')
            _strict_revisions(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _strict_revisions(item)


def _fresh(value, expected):
    if type(value) is not expected:
        raise ValueError('exact original subject contract type required')
    plain = _plain_contract_input(value)
    _strict_revisions(plain)
    return expected.model_validate(plain)


def _stored(scope, value):
    if (value.tenant.org_id, value.tenant.project_id) != scope.key:
        raise ValueError('exact dual-tenant subject and dependencies required')
    body = value.model_dump(mode='json', by_alias=True)
    if value.content_hash != canonical_hash({
        k: v for k, v in body.items() if k not in AipModelRuntimeStore._META_FIELDS
    }):
        raise ValueError('original stored revision content hash drifted')
    return body


def canonical_eval_subject_binding_bytes(
    scope: TenantScope,
    candidate: ModelEvalCandidate,
    source: RegisteredModelRevision | ModelRouteRevision,
    *,
    models: tuple[RegisteredModelRevision, ...] | list[RegisteredModelRevision] = (),
    runtime_policy: RuntimePolicyRevision | None = None,
) -> bytes:
    """Bind full supplied snapshots, never assert that their heads are current.

    Route dependencies include even zero-weight candidates, in original Route
    order. No resolver or selection algorithm runs here. The future owner must
    separately lock/recheck current source, approvals, dependencies and identity
    before dispatch and prove signed persisted results before publication.
    """
    if type(scope) is not TenantScope:
        raise ValueError('exact tenant scope required')
    if type(candidate) is not ModelEvalCandidate or type(candidate.execution_allowed) is not bool or candidate.execution_allowed:
        raise ValueError('descriptive candidate with strict executionAllowed false required')
    claim = _fresh(candidate, ModelEvalCandidate)
    if type(source) not in {RegisteredModelRevision, ModelRouteRevision}:
        raise ValueError('original Model or Route source required')
    subject = _fresh(source, type(source))
    body = _stored(scope, subject)
    if subject.lifecycle not in {ModelRuntimeLifecycle.DRAFT, ModelRuntimeLifecycle.VALIDATED}:
        raise ValueError('draft or validated first-Eval source required')
    source_ref = evaluation_candidate_ref(subject).model_copy(update={'content_hash': subject.content_hash})
    target_ref = evaluation_candidate_ref(subject.model_copy(update={
        'revision': subject.revision + 1, 'lifecycle': ModelRuntimeLifecycle.ACTIVE, 'eval_gate_ref': None,
    }))
    if (claim.source_ref != source_ref or claim.target_ref != target_ref
            or claim.source_lifecycle != subject.lifecycle.value):
        raise ValueError('original source and complete next-active target must match candidate')
    if type(models) not in {tuple, list}:
        raise ValueError('explicit complete Model dependencies required')
    ordered_models = []
    policy_body = None
    if type(subject) is RegisteredModelRevision:
        if models or runtime_policy is not None:
            raise ValueError('Model subject cannot carry unrelated Route dependencies')
    else:
        policy = _fresh(runtime_policy, RuntimePolicyRevision)
        policy_body = _stored(scope, policy)
        policy_ref = VersionedAssetRef(
            assetType='RuntimePolicyRevision', assetId=policy.policy_id,
            revision=policy.revision, contentHash=policy.content_hash,
        )
        if (policy_ref != subject.runtime_policy_ref
                or policy.lifecycle is not ModelRuntimeLifecycle.ACTIVE or policy.kill_switch_enabled):
            raise ValueError('exact active Route policy without kill switch required')
        dependencies = {}
        for supplied in models:
            model = _fresh(supplied, RegisteredModelRevision)
            model_body = _stored(scope, model)
            model_ref = VersionedAssetRef(
                assetType='RegisteredModelRevision', assetId=model.registered_model_id,
                revision=model.revision, contentHash=model.content_hash,
            )
            if model.registered_model_id in dependencies:
                raise ValueError('duplicate Route Model dependency')
            if (model.lifecycle is not ModelRuntimeLifecycle.ACTIVE
                    or subject.required_input_modality not in model.input_modalities
                    or subject.required_output_modality not in model.output_modalities
                    or not set(subject.required_capabilities).issubset(model.capabilities)):
                raise ValueError('original Route candidate lifecycle, modality or capability mismatch')
            dependencies[model.registered_model_id] = (model_ref, model_body)
        if set(dependencies) != {c.model.asset_id for c in subject.candidates}:
            raise ValueError('all and only original Route candidates required including zero-weight entries')
        for route_candidate in subject.candidates:
            actual_ref, model_body = dependencies[route_candidate.model.asset_id]
            if actual_ref != route_candidate.model:
                raise ValueError('exact original Route candidate Model reference drifted')
            ordered_models.append(model_body)
    payload = {
        'schemaVersion': 'aos.model-route-eval-subject-binding/v1',
        'tenant': {'orgId': scope.org_id, 'projectId': scope.project_id},
        'candidate': claim.model_dump(mode='json', by_alias=True),
        'source': body, 'models': ordered_models, 'runtimePolicy': policy_body,
        'executionAllowed': False,
    }
    return _DOMAIN + json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False,
    ).encode('utf-8')

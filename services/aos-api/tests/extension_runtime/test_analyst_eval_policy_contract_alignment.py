"""Original API-to-Growth proof type compatibility; no execution authority supplied."""
import importlib

import pytest

from aos_api.aip_eval_contracts import EvalGatePolicyRef as PlatformPolicyRef
from test_analyst_stage_eval_report_proof import package, values


@pytest.mark.parametrize("kind", ["EvalContractRevision", "MediaGatePolicyRevision"])
def test_original_platform_policy_payload_survives_growth_runtime_dispatch(package, kind):
    module, proof, args = values(package)
    policy = PlatformPolicyRef(resourceType=kind, resourceId="original-policy",
                               revision=1, contentHash="a" * 64).model_dump(mode="json", by_alias=True)
    body = proof.model_dump(mode="json", by_alias=True)
    body["gatePolicyRef"] = policy
    runtime = importlib.import_module("ecommerce_growth")
    response = runtime.handle("ecommerce_growth_review_advance", dict(
        kind="validate_eval_proof", proof=body,
        tenant=args["tenant"].model_dump(mode="json", by_alias=True),
        artifactRef=args["artifact_ref"].model_dump(mode="json", by_alias=True),
        stageAttemptRef=args["stage_attempt_ref"].model_dump(mode="json", by_alias=True),
        evalContractRef=args["eval_contract_ref"].model_dump(mode="json", by_alias=True),
        gatePolicyRef=policy, cutoffAt=args["cutoff_at"].isoformat(),
        now=args["now"].isoformat()), object())
    assert response["reportRef"]["resourceId"] == "report"
    assert module.EvalGatePolicyRef.model_validate(policy).resource_type == kind


@pytest.mark.parametrize("kind", ["BudgetRevision", "EvalReportRevision", "MediaGateProfileRevision"])
def test_unrelated_resource_types_remain_rejected(package, kind):
    module = package[2]
    with pytest.raises(ValueError):
        module.EvalGatePolicyRef(resourceType=kind, resourceId="policy", revision=1,
                                contentHash="a" * 64)


@pytest.mark.parametrize("fault", ["type", "hash", "tenant"])
def test_contract_policy_proof_still_rejects_exact_binding_drift(package, fault):
    module, proof, args = values(package)
    payload = proof.model_dump(mode="python", by_alias=True)
    policy = dict(resourceType="EvalContractRevision", resourceId="policy", revision=1,
                  contentHash="a" * 64)
    payload["gatePolicyRef"] = policy
    proof = module.StageEvalReportProof.model_validate(payload)
    args["gate_policy_ref"] = module.EvalGatePolicyRef.model_validate(policy)
    if fault == "type":
        # Identical ID/revision/hash does not make a Media policy the same resource.
        args["gate_policy_ref"] = module.EvalGatePolicyRef.model_validate(
            {**policy, "resourceType": "MediaGatePolicyRevision"})
    elif fault == "hash":
        args["gate_policy_ref"] = module.EvalGatePolicyRef.model_validate(
            {**policy, "contentHash": "b" * 64})
    else:
        args["tenant"] = package[0].TenantContext(orgId="dev-org", projectId="dev-project")
    with pytest.raises(ValueError, match="inputs drifted"):
        module.require_stage_eval_report_inputs(proof=proof, **args)


def test_contract_policy_bool_revision_remains_rejected(package):
    with pytest.raises(ValueError):
        package[2].EvalGatePolicyRef(resourceType="EvalContractRevision", resourceId="policy",
                                    revision=True, contentHash="a" * 64)

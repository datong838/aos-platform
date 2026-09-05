"""Compare signed declarations with observations, without activating anything."""

from aos_api.asset_registry.canonical_json import canonical_json
from aos_api.asset_registry.contracts import contribution_conflict_keys
from aos_api.extension_runtime.contracts import RegistrationDescription


def _index(description: RegistrationDescription) -> dict[tuple[str, ...], bytes]:
    indexed = {}
    for claim in description.contributions:
        body = canonical_json(claim.model_dump(mode="json", by_alias=True))
        for key in contribution_conflict_keys(claim):
            if key in indexed:
                raise ValueError("duplicate registration contribution")
            indexed[key] = body
    return indexed


def validate_registration(declared: RegistrationDescription, observed: RegistrationDescription) -> None:
    """Success means exact description equality only, never install readiness."""
    declared = RegistrationDescription.model_validate(declared)
    observed = RegistrationDescription.model_validate(observed)
    if _index(declared) != _index(observed):
        raise ValueError("registration differs from signed contributions")

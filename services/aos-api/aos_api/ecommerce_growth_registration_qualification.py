"""Current signed backend declarations required for first dispatch registration."""
from types import MappingProxyType

from aos_api.asset_registry.composition_contracts import ResolvedBundle, StoredCompositionLock
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.extension_runtime.contracts import RegistrationDescription
from aos_api.extension_runtime.registration import registration_fingerprint
from aos_api.extension_runtime.release_revalidation import RuntimeReleaseRevalidator


_API_PATHS = MappingProxyType({
    'ecommerce_growth_investigation_describe': '/ecommerce/growth/investigations/describe',
    'ecommerce_growth_case_put': '/ecommerce/growth/investigations/cases',
    'ecommerce_growth_schedule_put': '/ecommerce/growth/investigations/schedules',
    'ecommerce_growth_schedule_trigger': '/ecommerce/growth/investigations/schedules/trigger',
    'ecommerce_growth_data_fulfill': '/ecommerce/growth/investigations/data/fulfill',
    'ecommerce_growth_analysis_advance': '/ecommerce/growth/investigations/analysis/advance',
    'ecommerce_growth_review_advance': '/ecommerce/growth/investigations/review/advance',
    'ecommerce_growth_content_generate': '/ecommerce/growth/content/generate',
    'ecommerce_growth_content_review': '/ecommerce/growth/content/review',
})


def require_growth_registration_claims(selected: ResolvedBundle) -> str:
    """Validate declarations only; this helper is not a signature authority."""
    if type(selected) is not ResolvedBundle:
        raise TypeError('exact selected release required')
    selected = ResolvedBundle.model_validate(selected.model_dump(mode='python', by_alias=True))
    error = 'REGISTRATION_GROWTH_DECLARATIONS_INVALID'
    if selected.id != 'solution.ecommerce.growth' or selected.kind.value != 'SolutionPack':
        raise ValueError(error)
    if set(_API_PATHS) != set(ECOMMERCE_GROWTH_OPERATIONS):
        raise ValueError(error)
    claims = [claim for claim in selected.contributions if claim.kind == 'api']
    if (len(claims) != len(_API_PATHS)
            or {claim.operation_id for claim in claims} != set(_API_PATHS)
            or any(claim.method != 'POST' or claim.mode != 'exclusive'
                   or claim.path != _API_PATHS.get(claim.operation_id) for claim in claims)):
        raise ValueError(error)
    # Same full declaration digest used by the existing runtime release verifier.
    return registration_fingerprint(RegistrationDescription(contributions=selected.contributions))


def qualify_registration_release(conn, *, lock: StoredCompositionLock, release_policy: ReleasePolicy) -> dict:
    """Recheck current signatures under the caller's transaction and Registry lock."""
    if type(release_policy) is not ReleasePolicy:
        raise TypeError('current production release policy required')
    lock = StoredCompositionLock.model_validate(lock)
    selected = [value for value in lock.payload.resolved if value.id == 'solution.ecommerce.growth']
    if len(selected) != 1:
        raise ValueError('REGISTRATION_GROWTH_PACKAGE_REQUIRED')
    selected = selected[0]
    digest = require_growth_registration_claims(selected)
    checked = RuntimeReleaseRevalidator(release_policy=release_policy).revalidate_in_transaction(conn, lock=lock)
    matches = [claim for claim in checked.backend_claim_fingerprints if claim[0] == selected.id]
    if matches != [(selected.id, selected.content_hash, digest)]:
        raise ValueError('REGISTRATION_SIGNED_BACKEND_DECLARATIONS_DIFFER')
    return dict(schemaVersion='aos.ecommerce.registration-release-qualification/v1',
                lockHash=lock.lock_hash, packageId=selected.id, version=selected.version,
                contentHash=selected.content_hash, declarationHash=digest,
                operationCount=len(_API_PATHS), checkedAt=checked.checked_at.isoformat(),
                executable=False)

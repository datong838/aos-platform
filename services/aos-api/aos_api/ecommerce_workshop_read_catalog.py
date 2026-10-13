"""GET admission candidate over a current, signed, explicitly selected installation.

This adapter does not activate HTTP routes or grant runtime readiness. Legacy
admission is preserved; selected installed assets require actual exact scope grants.
"""
from __future__ import annotations

from aos_api.asset_registry.errors import AssetNotFoundError
from aos_api.ecommerce_workshop_contracts import WorkshopDependencyType


class EcommerceWorkshopReadCatalog:
    def __init__(self, *, legacy, installed=None, installed_factory=None) -> None:
        self._legacy = legacy
        self._installed = installed
        self._installed_factory = installed_factory

    def get_readiness(self, **scope):
        try:
            return self._legacy.get_readiness(**scope)
        except AssetNotFoundError:
            # Integrity, signature and availability errors never permit fallback.
            pass
        return self.get_installed_readiness(**scope)

    def get_installed_readiness(self, **scope):
        """Check only the selected installation with the existing exact read gate."""
        installed = (
            self._installed_factory() if self._installed_factory is not None
            else self._installed
        )
        result = installed.get_readiness(**scope)
        item = result.item
        installation = item.installation_ref
        required = set(item.permissions.data_scopes)
        expected_revision = (
            f'installation:{installation.revision}/lock:{installation.lock_revision}'
        )
        granted = {
            ref.resource_id for ref in item.dependency_refs
            if ref.resource_type == 'DataScopeGrant'
            and ref.revision == expected_revision
            and ref.content_hash == installation.lock_hash
            and ref.authority == 'postgres:bundle_composition_lock'
        }
        permitted_gap_types = {
            WorkshopDependencyType.OBJECT,
            WorkshopDependencyType.CAPABILITY,
            WorkshopDependencyType.AIP_FEATURE,
        }
        disallowed = any(
            blocker.dependency_type not in permitted_gap_types
            and not (
                blocker.dependency_type == WorkshopDependencyType.INSTALLATION
                and blocker.reason_code == 'INSTALLED_ASSET_READONLY'
                and blocker.dependency_id == installation.installation_id
            )
            for blocker in item.blockers
        )
        if 'ecommerce.workshop.read' not in required or not required <= granted or disallowed:
            raise AssetNotFoundError('Workshop module is not installed for scoped reading')
        # Keep the original disabled state and every runtime/authority gap intact.
        return result

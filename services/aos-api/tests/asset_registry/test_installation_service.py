"""Concrete Installation service contract gates."""

from __future__ import annotations

import inspect

from aos_api.asset_registry.control_protocols import InstallationControl
from aos_api.asset_registry.installation_service import InstallationService


def test_concrete_action_signatures_match_frozen_protocol() -> None:
    for name in ("submit", "approve", "reject", "apply", "verify", "rollback"):
        concrete = inspect.signature(getattr(InstallationService, name))
        protocol = inspect.signature(getattr(InstallationControl, name))
        assert tuple(concrete.parameters) == tuple(protocol.parameters)
        assert [item.kind for item in concrete.parameters.values()] == [
            item.kind for item in protocol.parameters.values()
        ]
        assert all(
            item.kind is not inspect.Parameter.VAR_KEYWORD
            for item in concrete.parameters.values()
        )
        assert concrete.return_annotation == protocol.return_annotation

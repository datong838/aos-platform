"""Fail-closed runtime wiring for the Route worker customer lifecycle."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aos_api.aip_route_worker_customer_lifecycle import (
    RouteWorkerCustomerLifecycleService,
)
from aos_api.aip_route_worker_identity import RouteWorkerIdentityConfig
from aos_api.aip_route_worker_installation import (
    RouteWorkerIdentityInstallationStore,
)
from aos_api.aip_route_worker_installation_authority import (
    CurrentRouteWorkerInstallationAuthority,
    RouteWorkerSignedInstallationCoordinator,
)
from aos_api.aip_secret_backend import SecretClient, default_secret_client
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.db import connect, connect_read_only

_SCOPE = ("org-org", "dev-project")
_COMPLETE_OPERATION = "route_worker_identity.customer_lifecycle.complete"


class RouteWorkerBusinessEntryFactory:
    """Build one request-scoped lifecycle service without starting the worker."""

    def __init__(
        self,
        *,
        connect_factory: Callable[..., Any] = connect,
        read_connect_factory: Callable[..., Any] = connect_read_only,
        secret_client: SecretClient | None = None,
        authority_factory: Callable[
            [], CurrentRouteWorkerInstallationAuthority
        ] = CurrentRouteWorkerInstallationAuthority.from_runtime,
        config_factory: Callable[
            [], RouteWorkerIdentityConfig
        ] = RouteWorkerIdentityConfig.from_control_env,
        path_factory: Callable[[], Path] | None = None,
    ) -> None:
        if not all(
            callable(item)
            for item in (
                connect_factory,
                read_connect_factory,
                authority_factory,
                config_factory,
            )
        ):
            raise ValueError(
                "complete route worker business entry dependencies required"
            )
        self._connect_factory = connect_factory
        self._read_connect_factory = read_connect_factory
        self._secret_client = secret_client or default_secret_client()
        self._authority_factory = authority_factory
        self._config_factory = config_factory
        self._path_factory = path_factory or self._configured_path

    @staticmethod
    def _configured_path() -> Path:
        raw = os.environ.get("AOS_ROUTE_WORKER_IDENTITY_FILE", "").strip()
        path = Path(raw)
        if not raw or not path.is_absolute():
            raise ValueError("protected route worker configuration path required")
        return path

    def _latest_completion(self) -> dict[str, Any] | None:
        with self._read_connect_factory() as conn:
            apply_asset_transaction_scope(conn, org_id=_SCOPE[0], project_id=_SCOPE[1])
            rows = conn.execute(
                """
                SELECT response_json
                  FROM bundle_installation_command
                 WHERE org_id = %s AND project_id = %s AND operation = %s
                 ORDER BY created_at DESC, idempotency_key DESC
                 LIMIT 2
                """,
                (*_SCOPE, _COMPLETE_OPERATION),
            ).fetchall()
            if not rows:
                return None
            return rows[0]["response_json"]

    def build(self, *, installation_id: str) -> RouteWorkerCustomerLifecycleService:
        path = self._path_factory()
        if not isinstance(path, Path) or not path.is_absolute():
            raise ValueError("protected route worker configuration path required")
        authority = self._authority_factory()
        store = RouteWorkerIdentityInstallationStore(secret_client=self._secret_client)

        def current_reader():
            try:
                path.lstat()
            except FileNotFoundError:
                return None
            return store.load(path)

        return RouteWorkerCustomerLifecycleService(
            receipt_store=PostgresInstallationStore(
                connect_factory=self._connect_factory
            ),
            coordinator=RouteWorkerSignedInstallationCoordinator(
                store=store, authority=authority
            ),
            authority=authority,
            current_reader=current_reader,
            document_factory=lambda: authority.build_document(
                config=self._config_factory(), installation_id=installation_id
            ),
            config_path=path,
            latest_completion_reader=self._latest_completion,
        )

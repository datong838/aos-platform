"""Tenant-scoped exact reference reauthorization for production Handoffs."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import psycopg

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import HandoffResourceRef
from aos_api.db import connect as db_connect
from aos_api.ecommerce_workshop_task_cockpit import (
    EcommerceWorkshopTaskCockpit,
    TaskCockpitPersistenceError,
)
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AipHandoffReferenceAuthority:
    """Resolve only registered governed refs; every unknown shape fails closed."""

    _ARTIFACT_TABLES = {
        "BusinessDossierRevision": "ecommerce_investigation_business_dossier_revision",
        "ProblemMapRevision": "ecommerce_investigation_problem_map_revision",
        "OpportunityMapRevision": "ecommerce_investigation_opportunity_map_revision",
        "SolutionPortfolioRevision": "ecommerce_investigation_solution_portfolio_revision",
    }

    def __init__(self, connect_factory: ConnectFactory | None = None, responsibility_reader=None) -> None:
        self._connect_factory = connect_factory or db_connect
        self._responsibility_reader = responsibility_reader or EcommerceWorkshopTaskCockpit()

    def __call__(
        self,
        scope: TenantScope,
        ref: HandoffResourceRef,
        _receiver_instance: VersionedAssetRef,
    ) -> bool:
        if ref.revision is None or ref.content_hash is None:
            return False
        try:
            with self._connect_factory(scope) as conn:
                if ref.resource_type == "GrowthPlanRevision":
                    return self._growth_plan_exists(conn, scope, ref)
                table = self._ARTIFACT_TABLES.get(ref.resource_type)
                if table is not None:
                    return self._artifact_exists(conn, scope, table, ref)
        except (psycopg.Error, TypeError, ValueError):
            return False
        return False

    def authorize_receiver(self, scope: TenantScope, row, receiver_instance: VersionedAssetRef) -> bool:
        """Re-read the compiled target slot immediately before token consumption."""
        try:
            context = row["context_payload"]
            target_slot_id = context.get("targetSlotId") if isinstance(context, dict) else None
            run_id = row["task_run_id"]
            if not isinstance(target_slot_id, str) or not target_slot_id or not isinstance(run_id, str) or not run_id:
                return False
            projection = self._responsibility_reader.read_responsibility_handoffs(
                org_id=scope.org_id,
                project_id=scope.project_id,
                run_id=run_id,
            )
            slot = next((item for item in projection.slots if item.slot_id == target_slot_id), None)
            if slot is None or target_slot_id not in projection.compiled_required_slot_ids:
                return False
            assignee = slot.assignee
            return (
                assignee.kind == "agent_instance"
                and assignee.operational_readiness == "resolved_at_observation"
                and assignee.resource_id == receiver_instance.asset_id
                and assignee.version == receiver_instance.revision
            )
        except (
            ApiError,
            TaskCockpitPersistenceError,
            AttributeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            return False

    @staticmethod
    def _numeric_revision(ref: HandoffResourceRef) -> int | None:
        value = ref.revision
        if value is None or not value.isdigit() or int(value) < 1:
            return None
        return int(value)

    def _growth_plan_exists(self, conn, scope: TenantScope, ref: HandoffResourceRef) -> bool:
        revision = self._numeric_revision(ref)
        if revision is None:
            return False
        row = conn.execute(
            """SELECT 1
               FROM ecommerce_analyst_growth_plan_head h
               JOIN ecommerce_analyst_growth_plan_revision r
                 ON r.org_id=h.org_id AND r.project_id=h.project_id
                AND r.plan_id=h.plan_id AND r.revision=h.current_revision
              WHERE h.org_id=%s AND h.project_id=%s AND h.plan_id=%s
                AND r.revision=%s AND r.content_hash=%s
                AND r.payload#>>'{lifecycle}'='approved'""",
            (*scope.key, ref.resource_id, revision, ref.content_hash.removeprefix("sha256:")),
        ).fetchone()
        return row is not None

    def _artifact_exists(
        self, conn, scope: TenantScope, table: str, ref: HandoffResourceRef
    ) -> bool:
        revision = self._numeric_revision(ref)
        if revision is None:
            return False
        row = conn.execute(
            f"""SELECT 1 FROM {table}
                 WHERE org_id=%s AND project_id=%s AND artifact_id=%s
                   AND revision=%s AND content_hash=%s""",
            (*scope.key, ref.resource_id, revision, ref.content_hash),
        ).fetchone()
        return row is not None


__all__ = ["AipHandoffReferenceAuthority"]

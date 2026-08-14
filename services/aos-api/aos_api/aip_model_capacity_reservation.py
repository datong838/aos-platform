"""Transactional AIP-7 capacity reservations for exact model-route resolution."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_model_runtime_contracts import ModelRouteResolution
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


class AipModelCapacityReservationGate:
    """Reserve one authority-defined execution quantum under a locked exact pool."""

    def __init__(self, connect_factory=None) -> None:
        self._connect_factory = connect_factory or db_connect

    def reserve(
        self,
        scope: TenantScope,
        resolution: ModelRouteResolution,
        agent_run_id: str,
    ) -> str:
        exact = self._exact_resolution(resolution)
        with self._connect_factory(scope) as conn:
            pool = conn.execute(
                """SELECT h.pool_id,h.current_revision,r.max_concurrency,
                          r.max_token_units,r.token_unit_per_reservation,r.lease_seconds
                   FROM aip_model_capacity_pool_head h
                   JOIN aip_model_capacity_pool_revision r
                     ON r.org_id=h.org_id AND r.project_id=h.project_id
                    AND r.pool_id=h.pool_id AND r.revision=h.current_revision
                   WHERE h.org_id=%s AND h.project_id=%s
                     AND r.route_id=%s AND r.route_revision=%s AND r.route_hash=%s
                     AND r.model_id=%s AND r.model_revision=%s AND r.model_hash=%s
                     AND r.provider_id=%s AND r.provider_revision=%s AND r.provider_hash=%s
                     AND r.lifecycle='active'
                   FOR UPDATE OF h""",
                (*scope.key, *exact),
            ).fetchone()
            if pool is None:
                raise AipAgentRegistryTransitionBlocked("capacity_pool_authority_unavailable")
            request_hash = self._request_hash(
                agent_run_id,
                exact,
                pool["pool_id"],
                pool["current_revision"],
                pool["token_unit_per_reservation"],
            )
            replay = conn.execute(
                """SELECT *,expires_at>NOW() AS is_active FROM aip_model_capacity_reservation
                   WHERE org_id=%s AND project_id=%s AND agent_run_id=%s
                   FOR UPDATE""",
                (*scope.key, agent_run_id),
            ).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise AipAgentRegistryConflict("capacity reservation replay payload drifted")
                if replay["status"] in {"reserved", "consumed"} and replay["is_active"]:
                    return replay["reservation_id"]
            expired = conn.execute(
                """UPDATE aip_model_capacity_reservation
                   SET status='expired',updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND pool_id=%s
                     AND pool_revision=%s AND status IN ('reserved','consumed') AND expires_at<=NOW()
                   RETURNING reservation_id""",
                (*scope.key, pool["pool_id"], pool["current_revision"]),
            ).fetchall()
            for row in expired:
                self._event(conn, scope, row["reservation_id"], "expired")
            usage = conn.execute(
                """SELECT COUNT(*) AS request_units,COALESCE(SUM(token_units),0) AS token_units
                   FROM aip_model_capacity_reservation
                   WHERE org_id=%s AND project_id=%s AND pool_id=%s
                     AND pool_revision=%s AND status IN ('reserved','consumed') AND expires_at>NOW()""",
                (*scope.key, pool["pool_id"], pool["current_revision"]),
            ).fetchone()
            next_requests = int(usage["request_units"]) + 1
            next_tokens = int(usage["token_units"]) + int(pool["token_unit_per_reservation"])
            if next_requests > int(pool["max_concurrency"]):
                raise AipAgentRegistryTransitionBlocked("capacity_concurrency_exhausted")
            if next_tokens > int(pool["max_token_units"]):
                raise AipAgentRegistryTransitionBlocked("capacity_token_units_exhausted")
            if replay is None:
                reservation_id = f"capres-{uuid.uuid4().hex}"
                row = conn.execute(
                    """INSERT INTO aip_model_capacity_reservation
                   (org_id,project_id,reservation_id,pool_id,pool_revision,agent_run_id,
                    request_hash,request_units,token_units,status,expires_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s,'reserved',
                           NOW()+(%s * INTERVAL '1 second'))
                   RETURNING reservation_id""",
                    (
                        *scope.key,
                        reservation_id,
                        pool["pool_id"],
                        pool["current_revision"],
                        agent_run_id,
                        request_hash,
                        pool["token_unit_per_reservation"],
                        pool["lease_seconds"],
                    ),
                ).fetchone()
            else:
                row = conn.execute(
                    """UPDATE aip_model_capacity_reservation
                       SET status='reserved',expires_at=NOW()+(%s * INTERVAL '1 second'),
                           updated_at=NOW()
                       WHERE org_id=%s AND project_id=%s AND reservation_id=%s
                       RETURNING reservation_id""",
                    (pool["lease_seconds"], *scope.key, replay["reservation_id"]),
                ).fetchone()
            self._event(conn, scope, row["reservation_id"], "reserved")
            conn.commit()
            return row["reservation_id"]

    def consume(self, scope: TenantScope, reservation_id: str) -> None:
        self._terminal(scope, reservation_id, "consumed")

    def release(self, scope: TenantScope, reservation_id: str) -> None:
        self._terminal(scope, reservation_id, "released")

    def release_for_run(self, scope: TenantScope, agent_run_id: str) -> None:
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """SELECT reservation_id FROM aip_model_capacity_reservation
                   WHERE org_id=%s AND project_id=%s AND agent_run_id=%s""",
                (*scope.key, agent_run_id),
            ).fetchone()
        if row is not None:
            self.release(scope, row["reservation_id"])

    def _terminal(self, scope: TenantScope, reservation_id: str, target: str) -> None:
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """SELECT status FROM aip_model_capacity_reservation
                   WHERE org_id=%s AND project_id=%s AND reservation_id=%s FOR UPDATE""",
                (*scope.key, reservation_id),
            ).fetchone()
            if row is None:
                return
            if row["status"] == target:
                return
            if row["status"] != "reserved":
                raise AipAgentRegistryConflict(
                    f"capacity reservation cannot become {target} from {row['status']}"
                )
            conn.execute(
                """UPDATE aip_model_capacity_reservation SET status=%s,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND reservation_id=%s""",
                (target, *scope.key, reservation_id),
            )
            self._event(conn, scope, reservation_id, target)
            conn.commit()

    @staticmethod
    def _event(conn, scope: TenantScope, reservation_id: str, event_type: str) -> None:
        conn.execute(
            """INSERT INTO aip_model_capacity_event
               (org_id,project_id,event_id,reservation_id,event_type,occurred_at)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (
                *scope.key,
                f"capevt-{uuid.uuid4().hex}",
                reservation_id,
                event_type,
                datetime.now(UTC),
            ),
        )

    @staticmethod
    def _request_hash(
        agent_run_id: str,
        exact: tuple[object, ...],
        pool_id: str,
        pool_revision: int,
        token_units: int,
    ) -> str:
        raw = json.dumps(
            {
                "agentRunId": agent_run_id,
                "exactResolution": exact,
                "poolId": pool_id,
                "poolRevision": pool_revision,
                "tokenUnits": token_units,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _exact_resolution(resolution: ModelRouteResolution) -> tuple[object, ...]:
        if resolution.selected_model is None or resolution.selected_provider is None:
            raise AipAgentRegistryTransitionBlocked("capacity_exact_resolution_required")
        refs = (resolution.route, resolution.selected_model, resolution.selected_provider)
        return tuple(value for ref in refs for value in (ref.asset_id, ref.revision, ref.content_hash))

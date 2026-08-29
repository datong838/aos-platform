"""Privacy-safe CustomerLite source observation for the Workshop customer view."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from functools import partial
from hashlib import sha256
from typing import Any

import psycopg

from aos_api.db import connect
from aos_api.ecommerce_workshop_customer_contracts import (
    CustomerAxisReadiness,
    CustomerBlocker,
    CustomerExactRef,
    CustomerReadinessAxis,
    CustomerViewId,
)
from aos_api.ecommerce_workshop_customer_reader import (
    CustomerReadError,
    CustomerViewObservation,
)
from aos_api.tenant_scope import TenantScope, apply_transaction_scope


ConnectFactory = Callable[[], AbstractContextManager[Any]]
_SCHEDULE_ID = "sch-P08-customer-lite-qyh"


class EcommerceWorkshopCustomerSourceReader:
    """Read only P08 run/count evidence; never return customer identities or PII."""

    def __init__(self, *, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or partial(connect, inherit_scope=False)

    def read_view(
        self,
        scope: TenantScope,
        *,
        view_id: CustomerViewId,
        cutoff: datetime,
        limit: int,
    ) -> CustomerViewObservation:
        if cutoff.utcoffset() is None:
            raise ValueError("customer source cutoff requires a timezone")
        if limit != 100:
            raise ValueError("customer source reader requires the canonical bound")
        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
                run = conn.execute(
                    """SELECT id,scheduled_for,started_at,finished_at,rows_written
                       FROM meta_schedule_run
                       WHERE org_id=%s AND project_id=%s AND schedule_id=%s
                         AND trigger='cron' AND status='succeeded' AND finished_at<=%s
                       ORDER BY finished_at DESC,id DESC LIMIT 1""",
                    (*scope.key, _SCHEDULE_ID, cutoff),
                ).fetchone()
                if run is None:
                    raise CustomerReadError("P08 successful natural run is unavailable")
                rows = conn.execute(
                    """SELECT payload_hash
                       FROM ecom_object
                       WHERE org_id=%s AND workspace_id=%s AND object_type='CustomerLite'
                         AND deleted_at IS NULL AND source_updated_at<=%s
                       ORDER BY external_id""",
                    (*scope.key, cutoff),
                ).fetchall()
        except CustomerReadError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise CustomerReadError("CustomerLite source observation failed closed") from exc

        source_count = len(rows)
        if source_count != int(run["rows_written"]):
            raise CustomerReadError("P08 run and CustomerLite projection count drift")
        digest = sha256()
        digest.update(str(run["id"]).encode())
        digest.update(str(run["scheduled_for"].isoformat()).encode())
        for row in rows:
            digest.update(str(row["payload_hash"]).encode())
        exact_ref = CustomerExactRef(
            resource_type="CustomerLiteSourceWindow",
            resource_id=_SCHEDULE_ID,
            revision=max(1, int(run["scheduled_for"].timestamp() // 60)),
            content_hash="sha256:" + digest.hexdigest(),
            receipt_id=str(run["id"]),
        )
        axes = []
        for axis in CustomerReadinessAxis:
            if axis is CustomerReadinessAxis.CUSTOMER_LITE:
                axes.append(CustomerAxisReadiness(axis=axis, status="ready", exact_ref=exact_ref))
                continue
            blocker = CustomerBlocker(
                code=f"CUSTOMER_{axis.value.upper()}_AUTHORITY_NOT_AVAILABLE",
                dependency=f"customer.{axis.value}",
                required_action="attach tenant-bound purpose, consent and retention authority before disclosure",
            )
            axes.append(CustomerAxisReadiness(axis=axis, status="blocked", blockers=[blocker]))
        return CustomerViewObservation(
            scope=scope,
            resource_revision=exact_ref.revision,
            data_cutoff=cutoff,
            readiness_axes=tuple(axes),
            authority_refs=(exact_ref,),
            input_count=source_count,
            suppressed_count=source_count,
        )


__all__ = ["EcommerceWorkshopCustomerSourceReader"]

"""Tenant-bound canonical source reader for the media-studio summary slices.

The reader distinguishes an authoritative empty collection from a missing
authority.  It deliberately fails closed once records exist until every record
can be projected with its exact revision, hash and Receipt; the richer media
lifecycle composer remains the canonical non-empty contribution reader.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from aos_api.ecommerce_workshop_media_studio_contracts import (
    MediaAxisReadiness,
    MediaReadinessAxis,
)
from aos_api.ecommerce_workshop_media_studio_reader import (
    MediaStudioReadError,
    MediaStudioSliceObservation,
)
from aos_api.tenant_scope import TenantScope


def _items(value: Any) -> list[Any]:
    items = getattr(value, "items", None)
    if not isinstance(items, list):
        raise MediaStudioReadError("media canonical source returned a non-list collection")
    return items


class EcommerceWorkshopMediaStudioSourceReader:
    """Read bounded media authorities without creating placeholder facts."""

    def __init__(
        self,
        *,
        production_store: Any,
        production_start_service: Any,
        provider_job_store: Any,
        media_finance_store: Any,
        action_store: Any,
    ) -> None:
        self._production = production_store
        self._starts = production_start_service
        self._jobs = provider_job_store
        self._finance = media_finance_store
        self._actions = action_store

    @staticmethod
    def _validate(cutoff: datetime, limit: int) -> None:
        if cutoff.utcoffset() is None:
            raise MediaStudioReadError("media canonical reader cutoff requires timezone")
        if limit != 100:
            raise MediaStudioReadError("media canonical reader limit must equal 100")

    @staticmethod
    def _empty(scope: TenantScope, cutoff: datetime) -> MediaStudioSliceObservation:
        return MediaStudioSliceObservation(
            scope=scope,
            data_cutoff=cutoff,
            readiness_axes=tuple(
                MediaAxisReadiness(axis=axis, status="not_applicable")
                for axis in MediaReadinessAxis
            ),
        )

    @staticmethod
    def _read(label: str, operation: Callable[[], list[Any]]) -> list[Any]:
        try:
            return operation()
        except MediaStudioReadError:
            raise
        except Exception as exc:
            raise MediaStudioReadError(f"media {label} authority read failed closed") from exc

    @staticmethod
    def _require_exact_receipt(label: str, records: list[Any]) -> None:
        if records:
            raise MediaStudioReadError(
                f"media {label} authority has records without an attached exact Receipt projection"
            )

    def read_context(
        self, scope: TenantScope, *, cutoff: datetime, limit: int
    ) -> MediaStudioSliceObservation:
        self._validate(cutoff, limit)
        contexts = self._read(
            "context", lambda: _items(self._production.list_production_contexts(scope))
        )
        visible = [item for item in contexts if item.created_at <= cutoff]
        self._require_exact_receipt("context", visible)
        return self._empty(scope, cutoff)

    def read_execution(
        self, scope: TenantScope, *, cutoff: datetime, limit: int
    ) -> MediaStudioSliceObservation:
        self._validate(cutoff, limit)
        contexts = self._read(
            "execution", lambda: _items(self._production.list_production_contexts(scope))
        )
        context_refs = {
            (item.context_id, item.revision)
            for item in contexts
            if item.created_at <= cutoff
        }
        starts = self._read(
            "execution", lambda: _items(self._starts.list(scope))
        )
        related_starts = [
            item
            for item in starts
            if item.created_at <= cutoff
            and item.production_context_ref is not None
            and (
                item.production_context_ref.resource_id,
                item.production_context_ref.revision,
            )
            in context_refs
        ]
        jobs = self._read(
            "execution", lambda: _items(self._jobs.list_jobs(scope, limit=limit))
        )
        finances = self._read(
            "execution", lambda: _items(self._finance.list(scope, limit=limit))
        )
        visible_jobs = [item for item in jobs if item.created_at <= cutoff]
        visible_finances = [item for item in finances if item.created_at <= cutoff]
        self._require_exact_receipt(
            "execution", related_starts + visible_jobs + visible_finances
        )
        return self._empty(scope, cutoff)

    def read_delivery(
        self, scope: TenantScope, *, cutoff: datetime, limit: int
    ) -> MediaStudioSliceObservation:
        self._validate(cutoff, limit)
        contexts = self._read(
            "delivery", lambda: _items(self._production.list_production_contexts(scope))
        )
        task_ids = {
            item.task_id for item in contexts if item.created_at <= cutoff
        }
        families = self._read(
            "delivery", lambda: _items(self._production.list_artifact_families(scope))
        )
        gates = self._read(
            "delivery", lambda: _items(self._production.list_media_gate_sets(scope))
        )
        issues = self._read(
            "delivery", lambda: _items(self._production.list_review_issues(scope))
        )
        returns = self._read(
            "delivery", lambda: _items(self._production.list_return_decisions(scope))
        )
        proposals = self._read(
            "delivery", lambda: list(self._actions.list_proposals(scope, limit=limit))
        )
        related_proposals = [
            item
            for item in proposals
            if getattr(getattr(item, "proposal", None), "task_id", None) in task_ids
            and getattr(item, "created_at", cutoff) <= cutoff
        ]
        related_delivery = families
        if families:
            related_delivery = families + gates + issues + returns
        self._require_exact_receipt(
            "delivery", related_delivery + related_proposals
        )
        return self._empty(scope, cutoff)


__all__ = ["EcommerceWorkshopMediaStudioSourceReader"]

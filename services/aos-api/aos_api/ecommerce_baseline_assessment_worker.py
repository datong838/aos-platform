"""Natural once-slot scheduler and fail-closed baseline analysis worker."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_logic_automation_scheduler import run_due_schedule_binding
from aos_api.automation_occurrence_store import AutomationOccurrenceStore, ClaimTarget
from aos_api.ecommerce_baseline_assessment_discovery import (
    BaselineAssessmentDiscovery,
    BaselineAssessmentNotApplicable,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_connection import connect_serializable
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.logging_facade import get_logger
from aos_api.pipeline_control_service import PipelineControlServiceFactory
from aos_api.pipeline_controlled_runtime import _authoritative_store


log = get_logger("aos-api.baseline-assessment-worker")


class BaselineAssessmentWorker:
    def __init__(self, factory, directory):
        if type(factory) is not PipelineControlServiceFactory or type(directory) is not LivePreparedJobDirectory:
            raise TypeError("exact lifecycle baseline worker dependencies required")
        self.factory, self.directory = factory, directory
        self._owner = "baseline-assessment-" + uuid4().hex
        self._target_offset = 0
        self._occurrences = AutomationOccurrenceStore(connect_serializable)
        self._discovery = BaselineAssessmentDiscovery()
        self.last_status = dict(targetsChecked=0, bindingsChecked=0, due=0, pending=0,
                                missed=0, accepted=0, reconciled=0, notApplicable=0, failed=0)

    @staticmethod
    def _now(scope):
        with connect_serializable(scope) as conn:
            return conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"].astimezone(UTC).replace(microsecond=0)

    @staticmethod
    def _markings(scope, actor):
        with connect_serializable(scope) as conn:
            roles = conn.execute(
                "SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s",
                (*scope.key, actor),
            ).fetchall()
            if len(roles) != 1:
                raise PermissionError("current baseline worker membership required")
            rows = conn.execute(
                "SELECT object_key FROM authz_tuple WHERE org_id=%s AND project_id=%s "
                "AND user_key=%s AND relation='bearer' AND object_key LIKE %s LIMIT 1001",
                (*scope.key, "user:" + actor, "marking:%"),
            ).fetchall()
        if len(rows) > 1000:
            raise PermissionError("bounded current baseline markings required")
        result = tuple(sorted({row["object_key"].removeprefix("marking:") for row in rows}))
        if any(not item or item != item.strip() or not item.isprintable() for item in result):
            raise PermissionError("current baseline marking identity invalid")
        return result

    def _route(self, scope, claimed, now):
        with connect_serializable(scope) as conn:
            return self._discovery.read(HostTransaction(conn), scope, claimed, observed_at=now)

    @staticmethod
    def _not_applicable_receipt(scope, claimed, reason):
        body = {
            "schemaVersion": "aos.ecommerce.baseline-disposition/v1",
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "occurrenceId": str(claimed.occurrence_id),
            "outcome": "not_applicable",
            "reasonCode": reason,
        }
        digest = canonical_hash(body, prefixed=True)
        return {
            "resourceType": "AutomationDisposition",
            "resourceId": str(claimed.occurrence_id),
            "revision": 1,
            "contentHash": digest,
        }

    async def _dispatch_one(self, target, now):
        scope, installation, generation = target
        self._occurrences.reconcile_expired_claims(scope, now=now)
        claim_target = ClaimTarget("ecommerce_growth_schedule_trigger", installation, generation,
                                   trigger_source="schedule")
        held = self._occurrences.read_needs_attention_target(scope, target=claim_target)
        if held is not None:
            from aos_api.ecommerce_growth_runtime_adapters import _HostAnalysisReceiptStore
            with connect_serializable(scope) as conn:
                root = _HostAnalysisReceiptStore(HostTransaction(conn), scope).read(
                    held["target_idempotency_key"]
                )
            if (
                type(root) is not dict
                or type(root.get("receiptRef")) is not dict
                or root.get("phase") != "PREPARING"
                or root.get("completed") is not False
                or root.get("occurrenceRef", {}).get("resourceId") != str(held["occurrence_id"])
            ):
                return "failed"
            self._occurrences.reconcile_target_receipt(
                scope, occurrence_id=held["occurrence_id"], receipt_ref=root["receiptRef"],
                occurred_at=self._now(scope),
            )
            return "reconciled"
        claimed = self._occurrences.claim_next(
            scope, owner=self._owner, now=now,
            target=claim_target,
        )
        if claimed is None:
            return "idle"
        try:
            route = self._route(scope, claimed, now)
            markings = self._markings(scope, route.source_actor)
            with _authoritative_store() as store:
                service = self.factory.build_scheduled_analysis(
                    scope, actor=route.source_actor, run_id=route.source_run_id,
                    control_ref=route.source_control_ref, installation_id=installation,
                    generation=generation, live_directory=self.directory,
                    markings=markings, store=store,
                )
                receipt = await service.handle_with_data(claimed)
            if type(receipt) is not dict or not receipt:
                raise ValueError("baseline analysis returned no Receipt")
        except BaselineAssessmentNotApplicable as exc:
            receipt = self._not_applicable_receipt(scope, claimed, str(exc))
            self._occurrences.record_not_applicable(
                scope, occurrence_id=claimed.occurrence_id, owner=self._owner,
                receipt_ref=receipt, occurred_at=self._now(scope),
            )
            return "notApplicable"
        except Exception as exc:
            self._occurrences.mark_needs_attention(
                scope, occurrence_id=claimed.occurrence_id, owner=self._owner,
                occurred_at=self._now(scope),
            )
            log.warning("baseline_analysis_held scope=%s occurrence=%s error=%s",
                        scope.key, claimed.occurrence_id, type(exc).__name__)
            return "failed"
        self._occurrences.record_target_receipt(
            scope, occurrence_id=claimed.occurrence_id, owner=self._owner,
            receipt_ref=receipt, occurred_at=self._now(scope),
        )
        return "accepted"

    async def tick(self):
        targets = self.directory.current_targets()
        stats = dict(targetsChecked=0, bindingsChecked=0, due=0, pending=0,
                     missed=0, accepted=0, reconciled=0, notApplicable=0, failed=0)
        if not targets:
            self.last_status = stats
            return stats
        start = self._target_offset % len(targets)
        selected = (targets[start:] + targets[:start])[:4]
        self._target_offset = (start + len(selected)) % len(targets)
        for target in selected:
            scope, installation, generation = target
            stats["targetsChecked"] += 1
            try:
                now = self._now(scope)
                bindings = self._occurrences.list_current_natural_bindings(
                    scope, installation_id=installation, generation=generation,
                )
                for binding, watermark in bindings:
                    stats["bindingsChecked"] += 1
                    result = run_due_schedule_binding(
                        scope, binding, watermark=watermark, now=now, store=self._occurrences,
                    )
                    for key in ("due", "pending", "missed"):
                        stats[key] += result[key]
                outcome = await self._dispatch_one(target, now)
                if outcome in stats:
                    stats[outcome] += 1
            except asyncio.CancelledError:
                raise
            except Exception:
                stats["failed"] += 1
                log.exception("baseline_assessment_tick_failed_closed target=%s", target)
        self.last_status = dict(stats)
        return stats

    async def serve(self, stop, *, host_ready):
        while not stop.is_set() and host_ready():
            try:
                result = await self.tick()
                if any(result[key] for key in ("due", "accepted", "reconciled", "notApplicable", "failed")):
                    log.info("baseline_assessment_tick %s", result)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("baseline_assessment_worker_failed_closed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=15)
            except TimeoutError:
                continue


def build_baseline_assessment_worker(control_plane):
    factory = getattr(control_plane, "pipeline_control_factory", None)
    directory = getattr(control_plane, "live_job_directory", None)
    if factory is None or directory is None:
        return None
    return BaselineAssessmentWorker(factory, directory)


__all__ = ["BaselineAssessmentWorker", "build_baseline_assessment_worker"]

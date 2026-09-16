"""Current schedule occurrence to the existing sealed analysis bootstrap."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC

from aos_api.automation_occurrence_store import AutomationOccurrenceStore, ClaimedOccurrence
from aos_api.ecommerce_baseline_assessment_discovery import BaselineAssessmentDiscovery
from aos_api.ecommerce_growth_canonical_router import IssuedDispatchRef
from aos_api.ecommerce_growth_host_ports import HostTransaction, LockedEcommerceGrowthHostPort
from aos_api.ecommerce_growth_runtime_adapters import _occurrence_payload, _occurrence_ref


class ScheduledBaselinePhaseOwner:
    def __init__(self, discovery: BaselineAssessmentDiscovery | None = None) -> None:
        if discovery is not None and type(discovery) is not BaselineAssessmentDiscovery:
            raise TypeError("exact baseline discovery required")
        self.discovery = discovery or BaselineAssessmentDiscovery()

    def run_current(self, analysis, conn, claimed, execute):
        from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService

        if (
            type(analysis) is not ProductEventAnalysisService
            or type(claimed) is not ClaimedOccurrence
            or claimed.operation_id != "ecommerce_growth_schedule_trigger"
            or not callable(execute)
        ):
            raise ValueError("exact scheduled baseline analysis claim required")
        scope = analysis.scope
        tx = HostTransaction(conn)
        now = tx.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        route = self.discovery.read(tx, scope, claimed, observed_at=now)
        routing = tx.execute(
            """SELECT * FROM extension_operation_dispatch_binding
                WHERE org_id=%s AND project_id=%s
                  AND operation_id='ecommerce_growth_analysis_advance'""",
            scope.key,
        ).fetchone()
        if routing is None:
            raise ValueError("current baseline analysis dispatch missing")
        issued = IssuedDispatchRef(
            org_id=scope.org_id,
            project_id=scope.project_id,
            operation_id="ecommerce_growth_analysis_advance",
            handler_kind=routing["handler_kind"],
            dispatch_revision=routing["revision"],
            installation_id=str(routing["installation_id"]),
            generation=str(routing["generation"]),
            execution_epoch=routing["execution_epoch"],
            cutover_group_id=str(routing["cutover_group_id"]),
            cutover_group_revision=routing["cutover_group_revision"],
        )
        LockedEcommerceGrowthHostPort._lock_and_revalidate(conn, scope, issued)
        if (
            issued.installation_id != str(route.installation_id)
            or issued.generation != str(route.generation)
            or issued.execution_epoch != route.execution_epoch
        ):
            raise ValueError("baseline analysis dispatch differs from occurrence")
        installed = analysis.invoker.read_current_in_transaction(tx)
        occurrence = _occurrence_payload(tx, scope, claimed.occurrence_id)
        group = analysis._source_group(conn)
        journal = analysis.source.reader._journal
        if (
            group is None
            or group.group_id != str(route.source_group_id)
            or group.actor != route.source_actor
            or group.read_completed_at != route.cutoff_at
            or (journal._ref, route.source_run_id) not in group.bindings
            or journal._ref != route.source_control_ref
            or journal._run_id != route.source_run_id
        ):
            raise ValueError("baseline snapshot group differs from governed source")
        approval = tx.execute(
            """SELECT expires_at FROM aip_action_approval_event
                WHERE org_id=%s AND project_id=%s AND approval_event_id=%s FOR SHARE""",
            (*scope.key, route.schedule_control.approval_ref.resource_id),
        ).fetchone()
        if approval is None or approval["expires_at"] is None or approval["expires_at"] <= now:
            raise ValueError("baseline schedule approval expired")

        policy = route.policy.model_dump(mode="json", by_alias=True)
        policy.update(
            sourceSelectionRef=route.source_selection_ref.model_dump(mode="json", by_alias=True),
            maxSourceAgeSeconds=route.max_source_age_seconds,
            effectiveFrom=route.policy.created_at.astimezone(UTC).isoformat(),
            effectiveUntil=approval["expires_at"].astimezone(UTC).isoformat(),
        )
        control = route.schedule_control.model_dump(mode="json", by_alias=True)
        control_receipt = {
            "receiptRef": deepcopy(control["receiptRef"]),
            "authority": {
                "schemaVersion": "aos.ecommerce.schedule-policy-bootstrap-control/v1",
                "command": {"approvalRef": deepcopy(control["approvalRef"])},
                "scheduleControl": control,
            },
        }
        source = {
            "policy": policy,
            "case": route.case.model_dump(mode="json", by_alias=True),
            "bindingRevision": route.policy.revision,
            "controlReceipt": control_receipt,
            "installed": analysis.source.invoker.read_current_in_transaction(tx),
            "events": [],
            "dispatch": {
                "revision": issued.dispatch_revision,
                "groupRevision": issued.cutover_group_revision,
                "groupId": issued.cutover_group_id,
                "installationId": issued.installation_id,
                "generation": issued.generation,
                "executionEpoch": issued.execution_epoch,
            },
        }
        origin = {
            "triggerSource": "schedule",
            "schedulePolicyRef": route.schedule_control.policy_ref.model_dump(mode="json", by_alias=True),
            "runId": route.source_run_id,
            "actor": route.source_actor,
            "sourceGroupId": str(route.source_group_id),
        }
        source_group = {
            "groupId": group.group_id,
            "manifestHash": group.manifest_hash,
            "readStartedAt": group.read_started_at.isoformat(),
            "readCompletedAt": group.read_completed_at.isoformat(),
        }
        case = source["case"]
        request = {
            "kind": "build_analysis_start",
            "occurrenceRef": _occurrence_ref(occurrence),
            "caseRef": {
                "resourceType": "BusinessInvestigationCaseRevision",
                "resourceId": case["caseId"],
                "revision": case["revision"],
                "contentHash": case["contentHash"],
            },
            "profileRef": {key: value for key, value in case["investigationProfileRef"].items() if value is not None},
            "cutoffAt": route.cutoff_at.isoformat(),
            "idempotencyKey": claimed.target_idempotency_key,
        }
        stable = {
            "source": source,
            "growth": installed,
            "occurrence": occurrence,
            "origin": origin,
            "request": request,
            "dispatchRevision": issued.dispatch_revision,
            "groupRevision": issued.cutover_group_revision,
            "sourceGroup": source_group,
        }
        result = execute(stable, request, issued)
        AutomationOccurrenceStore._lock_claim(conn, scope, claimed)
        if analysis.invoker.read_current_in_transaction(tx) != installed:
            raise ValueError("current growth installation changed")
        return result


__all__ = ["ScheduledBaselinePhaseOwner"]

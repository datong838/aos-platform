"""BI-W4-08 rebuildable Workbench View projection tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest
from pydantic import ValidationError

from aos_api.ecommerce_business_investigation_artifact import (
    BusinessInvestigationArtifactBinding,
    BusinessInvestigationArtifactType,
)
from aos_api.ecommerce_business_investigation_projection import (
    BusinessInvestigationProjectionBuilder,
    BusinessInvestigationProjectionError,
    BusinessInvestigationProjectionNotFound,
    BusinessInvestigationProjectionSource,
    BusinessInvestigationRuntimeSource,
    BusinessInvestigationStagePlanSource,
    BusinessInvestigationStageRunSource,
    BusinessInvestigationCheckpointSource,
    BusinessInvestigationWorkbenchView,
    CanonicalBusinessInvestigationProjectionReader,
)
from aos_api.aip_contracts import ResourceRef
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStateRevision
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database
from test_ecommerce_business_investigation_lifecycle import (
    HASH_A,
    draft_case,
    ref,
    requested_run,
)


SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 26, 10, 0, tzinfo=UTC)


def _state(**changes) -> BusinessInvestigationRunStateRevision:
    payload = {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "runId": "run-1",
        "version": 1,
        "lifecycle": "PREPARING",
        "control": "RUNNING",
        "eventSequence": 1,
        "contentHash": HASH_A,
        "createdBy": "owner",
        "createdAt": NOW,
    }
    payload.update(changes)
    return BusinessInvestigationRunStateRevision.model_validate(payload)


def _binding(kind: BusinessInvestigationArtifactType) -> BusinessInvestigationArtifactBinding:
    case = draft_case("case-1")
    run = requested_run(case)
    value = {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "bindingId": f"binding-{kind.value}",
        "bindingHash": HASH_A,
        "artifactRef": ref(kind.value, f"artifact-{kind.value}"),
        "selectedChannelRef": ref("ChannelRevision", "private-mall"),
        "selectedEntityRef": ref("BusinessEntityRevision", "store-1"),
        "caseRef": ref(
            "BusinessInvestigationCaseRevision",
            case.case_id,
            revision=case.revision,
            content_hash=case.content_hash,
        ),
        "runRef": ref(
            "BusinessInvestigationRun",
            run.run_id,
            revision=run.version,
            content_hash=run.content_hash,
        ),
        "selectionRevision": 3,
        "dataCutoff": NOW - timedelta(hours=1),
        "lineageRef": ref("LineageEventRevision", f"lineage-{kind.value}"),
        "boundBy": "owner",
        "boundAt": NOW,
    }
    draft = BusinessInvestigationArtifactBinding.model_validate(value)
    value["bindingHash"] = draft.calculated_binding_hash()
    return BusinessInvestigationArtifactBinding.model_validate(value)


def projection_source(
    *,
    state: BusinessInvestigationRunStateRevision | None = None,
    bindings: tuple[BusinessInvestigationArtifactBinding, ...] = (),
) -> BusinessInvestigationProjectionSource:
    case = draft_case("case-1")
    return BusinessInvestigationProjectionSource(
        case=case,
        run=requested_run(case),
        state=state or _state(),
        bindings=bindings,
    )


class FixedReader:
    def __init__(self, source: BusinessInvestigationProjectionSource) -> None:
        self.source = source
        self.calls: list[tuple[TenantScope, str]] = []

    def read(self, scope: TenantScope, run_id: str) -> BusinessInvestigationProjectionSource:
        self.calls.append((scope, run_id))
        return self.source


def projection_view(*, observed_at: datetime = NOW) -> BusinessInvestigationWorkbenchView:
    return BusinessInvestigationProjectionBuilder(FixedReader(projection_source())).build(
        SCOPE, "run-1", observed_at=observed_at
    )


def test_projection_rebuild_is_deterministic_and_keeps_canonical_four_slots() -> None:
    bindings = (
        _binding(BusinessInvestigationArtifactType.DOSSIER),
        _binding(BusinessInvestigationArtifactType.PROBLEM_MAP),
    )
    first = BusinessInvestigationProjectionBuilder(FixedReader(projection_source(bindings=bindings))).build(
        SCOPE, "run-1", observed_at=NOW
    )
    restarted = BusinessInvestigationProjectionBuilder(
        FixedReader(projection_source(bindings=bindings))
    ).build(SCOPE, "run-1", observed_at=NOW + timedelta(minutes=5))
    assert first.projection_hash == restarted.projection_hash
    assert first.source_watermark == restarted.source_watermark
    assert [item.artifact_type for item in first.artifacts] == list(BusinessInvestigationArtifactType)
    assert [item.status for item in first.artifacts] == ["bound", "bound", "missing", "missing"]
    assert sorted(item.event_type for item in first.timeline) == [
        "artifact_bound", "artifact_bound", "case_revision", "run_created", "state_revision"
    ]
    assert [(item.occurred_at, item.event_id) for item in first.timeline] == sorted(
        (item.occurred_at, item.event_id) for item in first.timeline
    )
    assert all(item.exact_ref.content_hash.startswith("sha256:") for item in first.timeline)
    assert first.timeline == restarted.timeline
    assert first.observed_at != restarted.observed_at
    assert first.schema_version == "aos.ecommerce.business-investigation-workbench-view/v5"
    assert first.command_projection.expected_state_version == first.state_ref.revision
    assert first.command_projection.allowed_commands == ["PAUSE_RUN", "CANCEL_RUN"]
    assert first.command_projection.external_effects_allowed is False


@pytest.mark.parametrize(
    ("control", "expected"),
    [
        ("RUNNING", ["PAUSE_RUN", "CANCEL_RUN"]),
        ("PAUSED", ["RESUME_RUN", "CANCEL_RUN"]),
        ("UNKNOWN", []),
        ("RECONCILING", []),
        ("CANCELLED", []),
    ],
)
def test_projection_server_owns_fail_closed_command_matrix(
    control: str, expected: list[str]
) -> None:
    changes = {}
    if control != "RUNNING":
        changes = {
            "version": 2,
            "eventSequence": 2,
            "priorRef": ref("BusinessInvestigationRunStateRevision", "run-1"),
        }
    if control in {"UNKNOWN", "RECONCILING"}:
        changes["uncertainCommand"] = {
            "commandId": "command-1", "operation": "investigation.fetch", "requestHash": HASH_A,
        }
    state = _state(control=control, **changes)
    view = BusinessInvestigationProjectionBuilder(FixedReader(projection_source(state=state))).build(
        SCOPE, "run-1", observed_at=NOW
    )
    assert view.command_projection.allowed_commands == expected
    payload = view.model_dump(by_alias=True, mode="json")
    assert payload["commandProjection"]["expectedStateVersion"] == state.version
    assert payload["commandProjection"]["externalEffectsAllowed"] is False


def test_projection_preserves_waiting_unknown_and_reconciling_without_success_claim() -> None:
    requirement = ref("DataRequirementRevision", "requirement-1")
    waiting = _state(
        version=2,
        priorRef=ref("BusinessInvestigationRunStateRevision", "run-1"),
        eventSequence=2,
        lifecycle="WAITING_DATA",
        pendingRequirementRef=requirement,
    )
    waiting_view = BusinessInvestigationProjectionBuilder(FixedReader(projection_source(state=waiting))).build(
        SCOPE, "run-1", observed_at=NOW
    )
    assert waiting_view.lifecycle == "WAITING_DATA"
    assert waiting_view.pending_requirement_ref.resource_id == "requirement-1"

    uncertain = {"commandId": "cmd-1", "operation": "investigation.fetch", "requestHash": HASH_A}
    for control in ("UNKNOWN", "RECONCILING"):
        state = _state(
            version=2,
            priorRef=ref("BusinessInvestigationRunStateRevision", "run-1"),
            eventSequence=2,
            control=control,
            uncertainCommand=uncertain,
        )
        view = BusinessInvestigationProjectionBuilder(FixedReader(projection_source(state=state))).build(
            SCOPE, "run-1", observed_at=NOW
        )
        assert view.control == control and view.uncertain_command.command_id == "cmd-1"
        assert "completed" not in view.model_dump(by_alias=True, mode="json")


def test_projection_exposes_server_owned_case_envelope_stage_progress_and_checkpoint() -> None:
    source = projection_source()
    runtime = BusinessInvestigationRuntimeSource(
        task_id="task-1",
        plan_ref=ref("PlanRevision", "plan-1"),
        task_run_id="task-run-1",
        task_run_version=4,
        task_run_status="running",
        plan_stages=(
            BusinessInvestigationStagePlanSource(stage_id="portrait"),
            BusinessInvestigationStagePlanSource(
                stage_id="diagnosis",
                responsibility_slot_ids=("slot-diagnosis",),
                assignee_refs=(ResourceRef(
                    resource_type="AgentInstance", resource_id="data-advisor",
                    revision="7", authority="aip-assignee-directory",
                ),),
                input_refs=(ResourceRef(
                    resource_type="EvidenceBundleRevision", resource_id="evidence-1",
                    revision="3", authority="aip-evidence-authority",
                ),),
            ),
            BusinessInvestigationStagePlanSource(stage_id="solution-design"),
        ),
        stages=(
            BusinessInvestigationStageRunSource(
                stage_id="portrait", step_run_id="step-portrait", attempt=1, status="succeeded"
            ),
            BusinessInvestigationStageRunSource(
                stage_id="diagnosis", step_run_id="step-diagnosis", attempt=2, status="running",
                output_refs=(ResourceRef(
                    resource_type="AnalysisDraft", resource_id="draft-1",
                    revision="1", authority="aip-runtime",
                ),),
            ),
        ),
        checkpoint=BusinessInvestigationCheckpointSource(
            checkpoint_id="checkpoint-2", sequence=2, step_key="diagnosis",
            state_hash="a" * 64, created_at=NOW,
        ),
    )
    view = BusinessInvestigationProjectionBuilder(
        FixedReader(BusinessInvestigationProjectionSource(
            case=source.case, run=source.run, state=source.state, runtime=runtime
        ))
    ).build(SCOPE, "run-1", observed_at=NOW)
    assert view.case_envelope.title == source.case.title
    assert view.runtime.binding_status == "bound"
    assert view.runtime.completed == 1 and view.runtime.total == 3
    assert view.runtime.current_stage_id == "diagnosis"
    assert [item.status for item in view.runtime.stages] == ["completed", "running", "not_started"]
    assert view.runtime.checkpoint is not None and view.runtime.checkpoint.sequence == 2
    assert view.source_watermark.runtime_hash is not None
    assert view.schema_version.endswith("/v5")
    assert view.current_workspace.stage_id == "diagnosis"
    assert view.current_workspace.status == "running"
    assert view.current_workspace.responsibility_slot_ids == ["slot-diagnosis"]
    assert [item.resource_id for item in view.current_workspace.input_refs] == ["evidence-1"]
    assert view.evidence.status == "missing"
    assert [item.resource_id for item in view.evidence.locator_refs] == ["evidence-1"]
    assert view.evidence.exact_refs == []
    assert [item.resource_id for item in view.current_workspace.output_refs] == ["draft-1"]
    assert [item.area for item in view.current_workspace.areas] == [
        "known", "unknown", "assumption", "counter_evidence"
    ]
    assert view.current_workspace.areas[0].status == "reference_only"
    assert view.current_workspace.areas[2].status == "unknown"
    assert all("推理链" not in item.summary for item in view.current_workspace.areas)


def test_projection_runtime_unbound_and_task_pending_are_explicit() -> None:
    unbound = projection_view()
    assert unbound.runtime.binding_status == "unbound"
    assert unbound.runtime.completed == 0 and unbound.runtime.current_stage_id is None
    assert unbound.current_workspace.status == "unbound"
    assert unbound.current_workspace.stage_id is None
    assert unbound.current_workspace.areas[0].status == "unknown"
    source = projection_source()
    pending = BusinessInvestigationProjectionBuilder(FixedReader(
        BusinessInvestigationProjectionSource(
            case=source.case, run=source.run, state=source.state,
            runtime=BusinessInvestigationRuntimeSource(
                task_id="task-1", plan_ref=ref("PlanRevision", "plan-1")
            ),
        )
    )).build(SCOPE, "run-1", observed_at=NOW)
    assert pending.runtime.binding_status == "task_pending"
    assert pending.runtime.task_run_ref is None and pending.runtime.checkpoint is None
    assert pending.current_workspace.stage_id == "portrait"
    assert pending.current_workspace.status == "task_pending"


def test_projection_contract_rejects_tampering_and_stale_missing_slot_data() -> None:
    view = projection_view()
    payload = view.model_dump(by_alias=True, mode="json")
    payload["caseEnvelope"]["title"] = "tampered title"
    with pytest.raises(ValidationError, match="projectionHash"):
        BusinessInvestigationWorkbenchView.model_validate(payload)
    payload = view.model_dump(by_alias=True, mode="json")
    payload["artifacts"][0]["artifactRef"] = ref("BusinessDossierRevision", "stale")
    with pytest.raises(ValidationError, match="missing artifact"):
        BusinessInvestigationWorkbenchView.model_validate(payload)


def test_projection_fails_closed_on_tenant_run_or_duplicate_binding_drift() -> None:
    source = projection_source()
    wrong_tenant = source.case.model_validate(
        {
            **source.case.model_dump(by_alias=True, mode="json"),
            "tenant": {"orgId": OTHER_SCOPE.org_id, "projectId": OTHER_SCOPE.project_id},
        }
    )
    with pytest.raises(BusinessInvestigationProjectionError, match="tenant"):
        BusinessInvestigationProjectionBuilder(
            FixedReader(
                BusinessInvestigationProjectionSource(
                    case=wrong_tenant, run=source.run, state=source.state
                )
            )
        ).build(SCOPE, "run-1", observed_at=NOW)
    duplicate = _binding(BusinessInvestigationArtifactType.DOSSIER)
    with pytest.raises(BusinessInvestigationProjectionError, match="binding"):
        BusinessInvestigationProjectionBuilder(
            FixedReader(projection_source(bindings=(duplicate, duplicate)))
        ).build(SCOPE, "run-1", observed_at=NOW)


def test_canonical_reader_is_tenant_bounded_read_only_and_not_visible_is_distinct() -> None:
    source = projection_source()
    calls: list[tuple[str, tuple]] = []

    class Cursor:
        def __init__(self, rows):
            self.rows = rows

        def fetchone(self):
            return self.rows[0] if self.rows else None

        def fetchall(self):
            return self.rows

    class Connection:
        def execute(self, sql, params):
            normalized = " ".join(sql.split())
            calls.append((normalized, params))
            if "DISTINCT ON" in normalized:
                return Cursor([])
            if "aip_business_investigation_compile_receipt" in normalized:
                return Cursor([])
            if params[:2] == OTHER_SCOPE.key:
                return Cursor([])
            return Cursor(
                [
                    {
                        "case_authority": source.case.model_dump(by_alias=True, mode="json"),
                        "run_authority": source.run.model_dump(by_alias=True, mode="json"),
                        "state_authority": source.state.model_dump(by_alias=True, mode="json"),
                    }
                ]
            )

    @contextmanager
    def connect(_scope):
        yield Connection()

    reader = CanonicalBusinessInvestigationProjectionReader(connect)
    assert reader.read(SCOPE, "run-1").run.run_id == "run-1"
    assert len(calls) == 3 and all(call[0].startswith("SELECT") for call in calls)
    assert calls[0][1] == (*SCOPE.key, "run-1")
    with pytest.raises(BusinessInvestigationProjectionNotFound):
        reader.read(OTHER_SCOPE, "run-1")


def test_disposable_database_projection_rebuild_survives_reader_restart_and_rls() -> None:
    case_r1 = draft_case("case-1")
    case_payload = case_r1.model_dump(by_alias=True, mode="json")
    case_payload.update(
        revision=2,
        version=2,
        lifecycle="ACTIVE",
        priorRef=ref(
            "BusinessInvestigationCaseRevision",
            case_r1.case_id,
            revision=1,
            content_hash=case_r1.content_hash,
        ),
        contentHash=HASH_A,
    )
    case_r2 = case_r1.model_validate(case_payload)
    case_payload["contentHash"] = case_r2.calculated_content_hash()
    case_r2 = case_r1.model_validate(case_payload)
    run = requested_run(case_r2)

    with isolated_aip_migration_database("biw4_projection_rebuild") as (_config, dsn):
        with psycopg.connect(dsn) as conn:
            conn.execute(
                """INSERT INTO twa_workspace(org_id,project_id,name)
                   VALUES(%s,%s,'BI-W4-08') ON CONFLICT DO NOTHING""",
                SCOPE.key,
            )
            conn.execute(
                """INSERT INTO ecommerce_investigation_case_head(
                     org_id,project_id,case_id,current_revision,version,lifecycle,
                     analysis_type,channel_id,business_entity_id)
                   VALUES(%s,%s,%s,2,2,'ACTIVE','initial_store_analysis','private-mall','store-1')""",
                (*SCOPE.key, case_r2.case_id),
            )
            conn.execute(
                """INSERT INTO ecommerce_investigation_case_revision(
                     org_id,project_id,case_id,revision,version,prior_revision,content_hash,
                     lifecycle,analysis_type,channel_id,business_entity_id,entity_channel_binding_id,
                     idempotency_key,request_hash,authority_data,created_by,created_at)
                   VALUES(%s,%s,%s,2,2,1,%s,'ACTIVE','initial_store_analysis','private-mall',
                     'store-1','binding-1','seed-case',%s,%s,'owner',%s)""",
                (
                    *SCOPE.key,
                    case_r2.case_id,
                    case_r2.content_hash,
                    HASH_A,
                    Jsonb(case_r2.model_dump(by_alias=True, mode="json")),
                    NOW,
                ),
            )
            conn.execute(
                """INSERT INTO ecommerce_investigation_run(
                     org_id,project_id,run_id,version,content_hash,case_id,case_revision,
                     lifecycle,control,analysis_type,trigger_kind,trigger_key,current_event_sequence,
                     authority_data,created_by,created_at)
                   VALUES(%s,%s,%s,1,%s,%s,2,'PREPARING','RUNNING','initial_store_analysis',
                     'manual',%s,1,%s,'owner',%s)""",
                (
                    *SCOPE.key,
                    run.run_id,
                    run.content_hash,
                    case_r2.case_id,
                    run.trigger_key,
                    Jsonb(run.model_dump(by_alias=True, mode="json")),
                    NOW,
                ),
            )
            conn.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute(
                    "SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",
                    scope.key,
                )
                yield conn

        first = BusinessInvestigationProjectionBuilder(
            CanonicalBusinessInvestigationProjectionReader(runtime_connect)
        ).build(SCOPE, "run-1", observed_at=NOW)
        restarted = BusinessInvestigationProjectionBuilder(
            CanonicalBusinessInvestigationProjectionReader(runtime_connect)
        ).build(SCOPE, "run-1", observed_at=NOW + timedelta(minutes=1))
        assert first.projection_hash == restarted.projection_hash
        assert first.source_watermark == restarted.source_watermark
        with pytest.raises(BusinessInvestigationProjectionNotFound):
            CanonicalBusinessInvestigationProjectionReader(runtime_connect).read(
                OTHER_SCOPE, "run-1"
            )


def test_projection_observed_at_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="observedAt"):
        projection_view(observed_at=datetime(2026, 8, 26, 10, 0))

"""Claimed DataRequirement Outbox -> original analysis/snapshot route."""
from contextlib import contextmanager
from dataclasses import replace

import pytest
import psycopg
from psycopg.rows import dict_row

pytest_plugins = ("test_analysis_snapshot_resume_chain_pg",)
pytestmark = [
    pytest.mark.parametrize("startup_case", ["defer-host"], indirect=True),
    pytest.mark.parametrize("stored", ["qualified-runtime"], indirect=True),
]

from aos_api.data_requirement_outbox_store import DataRequirementOutboxStore
from aos_api.data_requirement_store import (
    DataRequirementStore,
    canonical_revision_content_hash,
)
from aos_api.business_investigation_shared_contracts import (
    DataRequirementStatus,
    InvestigationExactRef,
)
from aos_api.ecommerce_analysis_data_requirement_route import (
    AnalysisDataRequirementRouteReader,
)


def _runtime_connect(conn):
    dsn = conn.info.dsn

    @contextmanager
    def factory(scope):
        with psycopg.connect(dsn, row_factory=dict_row) as current:
            current.execute("SET ROLE aos_runtime")
            current.execute(
                "SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)",
                scope.key,
            )
            yield current

    return factory


def _claim(scope, connect_factory):
    claim = DataRequirementOutboxStore(connect_factory).claim_next(
        scope,
        topic="data.requirement.request",
        worker_id="analysis-data-route-test",
        lease_token="analysis-data-route-test-token",
        lease_seconds=300,
    )
    assert claim is not None
    return claim


def test_claim_routes_to_exact_original_analysis_and_snapshot_group(chain_case):
    conn, _state, analysis, session, root, requirement = chain_case
    connect_factory = _runtime_connect(conn)
    claim = _claim(analysis.scope, connect_factory)
    route = AnalysisDataRequirementRouteReader(
        claims=analysis.source.reader._journal._claims,
        connect_factory=connect_factory,
    ).read(analysis.scope, claim)

    assert route.requirement == requirement
    assert route.analysis_receipt_ref == root["receiptRef"]
    assert route.occurrence_id == root["occurrenceRef"]["resourceId"]
    assert route.actor == analysis.source.actor
    assert route.source_run_id == analysis.source.reader._journal._run_id
    assert route.source_control_ref == analysis.source.reader._journal._ref
    assert route.group_id
    assert route.installation_id == str(analysis.invoker.installation_id)
    assert route.generation == str(analysis.invoker.generation)
    assert session.command["requirementRef"]["resourceId"] == claim.requirement_id

    outbox = DataRequirementOutboxStore(connect_factory)
    assert outbox.mark_unknown(analysis.scope, claim.outbox_id, claim.lease_token,
        reason_code="COORDINATION_RESULT_UNKNOWN").state == "unknown"
    unknown = outbox.read_unknown_next(analysis.scope, topic="data.requirement.request")
    assert unknown == claim
    assert AnalysisDataRequirementRouteReader(
        claims=analysis.source.reader._journal._claims,
        connect_factory=connect_factory,
    ).read_unknown(analysis.scope, unknown) == route
    with pytest.raises(ValueError, match="no longer current"):
        AnalysisDataRequirementRouteReader(
            claims=analysis.source.reader._journal._claims,
            connect_factory=connect_factory,
        ).read(analysis.scope, unknown)


def test_claim_payload_or_current_head_drift_fails_before_route_is_returned(chain_case):
    conn, _state, analysis, _session, _root, requirement = chain_case
    connect_factory = _runtime_connect(conn)
    claim = _claim(analysis.scope, connect_factory)
    changed = replace(claim, payload={**claim.payload, "revision": claim.requirement_revision + 1})
    with pytest.raises(ValueError, match="Outbox payload"):
        AnalysisDataRequirementRouteReader(
            claims=analysis.source.reader._journal._claims,
            connect_factory=connect_factory,
        ).read(analysis.scope, changed)

    prior = InvestigationExactRef(
        resource_type="DataRequirementRevision",
        resource_id=requirement.requirement_id,
        revision=requirement.revision,
        content_hash=requirement.content_hash,
    )
    with connect_factory(analysis.scope) as current:
        now = current.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    cancelled = requirement.model_copy(
        update={
            "revision": 2,
            "prior_ref": prior,
            "status": DataRequirementStatus.CANCELLED,
            "created_at": now,
            "content_hash": "sha256:" + "0" * 64,
        }
    )
    cancelled = cancelled.model_copy(
        update={"content_hash": canonical_revision_content_hash(cancelled)}
    )
    DataRequirementStore(connect_factory).cancel(
        analysis.scope,
        "ecommerce-growth-data-host",
        "analysis-data-route-cancel",
        cancelled,
        expected_version=1,
    )
    with pytest.raises(ValueError, match="no longer current"):
        AnalysisDataRequirementRouteReader(
            claims=analysis.source.reader._journal._claims,
            connect_factory=connect_factory,
        ).read(analysis.scope, claim)

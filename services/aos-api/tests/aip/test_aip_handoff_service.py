from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import HandoffResourceRef
from aos_api.aip_handoff_reference_authority import AipHandoffReferenceAuthority
from aos_api.routers import aip_handoffs
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
HASH = "a" * 64


class Cursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class Connection:
    def __init__(self, row=None):
        self.row = row
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return Cursor(self.row)


def factory(connection):
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection

    return connect


def receiver() -> VersionedAssetRef:
    return VersionedAssetRef(
        assetType="AgentInstance",
        assetId="receiver-1",
        revision=1,
        contentHash=HASH,
    )


def ref(kind="GrowthPlanRevision", *, revision="1", content_hash=f"sha256:{HASH}"):
    return HandoffResourceRef(
        resourceType=kind,
        resourceId="resource-1",
        revision=revision,
        authority="postgresql",
        contentHash=content_hash,
    )


def test_production_router_uses_fail_closed_reference_authority() -> None:
    service = aip_handoffs.get_handoff_service()
    assert isinstance(service._ref_authorizer, AipHandoffReferenceAuthority)
    assert service._envelope_authorizer == service._ref_authorizer.authorize_receiver


def test_reference_authority_requires_revision_hash_and_registered_type() -> None:
    connection = Connection(row={"exists": 1})
    authority = AipHandoffReferenceAuthority(factory(connection))

    assert not authority(
        SCOPE,
        HandoffResourceRef(
            resourceType="GrowthPlanRevision",
            resourceId="plan-1",
            revision="1",
            authority="postgresql",
        ),
        receiver(),
    )
    assert not authority(SCOPE, ref("UnknownRevision"), receiver())
    assert len(connection.calls) == 0


def test_growth_plan_requires_current_approved_exact_revision_and_tenant_scope() -> None:
    connection = Connection(row={"exists": 1})
    authority = AipHandoffReferenceAuthority(factory(connection))

    assert authority(SCOPE, ref(), receiver())
    sql, params = connection.calls[0]
    assert "ecommerce_analyst_growth_plan_head" in sql
    assert "lifecycle" in sql and "approved" in sql
    assert params == ("org-org", "dev-project", "resource-1", 1, HASH)


def test_governed_artifact_reauthorizes_exact_hash_in_same_tenant() -> None:
    connection = Connection(row={"exists": 1})
    authority = AipHandoffReferenceAuthority(factory(connection))

    assert authority(SCOPE, ref("ProblemMapRevision"), receiver())
    sql, params = connection.calls[0]
    assert "ecommerce_investigation_problem_map_revision" in sql
    assert params == (
        "org-org",
        "dev-project",
        "resource-1",
        1,
        f"sha256:{HASH}",
    )

    missing = AipHandoffReferenceAuthority(factory(Connection(row=None)))
    assert not missing(SCOPE, ref("ProblemMapRevision"), receiver())


class ResponsibilityReader:
    def __init__(self, *, slot_id="target-slot", instance_id="receiver-1", version=1, readiness="resolved_at_observation"):
        self.slot_id = slot_id
        self.instance_id = instance_id
        self.version = version
        self.readiness = readiness
        self.calls = []

    def read_responsibility_handoffs(self, **kwargs):
        self.calls.append(kwargs)
        assignee = SimpleNamespace(kind="agent_instance", resource_id=self.instance_id, version=self.version, operational_readiness=self.readiness)
        slot = SimpleNamespace(slot_id=self.slot_id, assignee=assignee)
        return SimpleNamespace(slots=[slot], compiled_required_slot_ids=[self.slot_id])


def test_receiver_reauthorization_rechecks_exact_target_slot_in_same_tenant() -> None:
    reader = ResponsibilityReader()
    authority = AipHandoffReferenceAuthority(factory(Connection()), reader)
    row = {"context_payload": {"targetSlotId": "target-slot"}, "task_run_id": "task-run-1"}

    assert authority.authorize_receiver(SCOPE, row, receiver())
    assert reader.calls == [{"org_id": "org-org", "project_id": "dev-project", "run_id": "task-run-1"}]
    assert not AipHandoffReferenceAuthority(factory(Connection()), ResponsibilityReader(version=2)).authorize_receiver(SCOPE, row, receiver())
    assert not AipHandoffReferenceAuthority(factory(Connection()), ResponsibilityReader(readiness="unverified")).authorize_receiver(SCOPE, row, receiver())
    assert not authority.authorize_receiver(SCOPE, {"context_payload": {}, "task_run_id": "task-run-1"}, receiver())

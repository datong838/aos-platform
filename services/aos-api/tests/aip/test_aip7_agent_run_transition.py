from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from aos_api.aip_agent_registry_contracts import AgentRunStatus, VersionedAssetRef
from aos_api.aip_agent_registry_store import AipAgentRegistryConflict, AipAgentRegistryTransitionBlocked
from aos_api.aip_agent_run_service import AipAgentRunService, UnavailableCapacityReservationGate
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.tenant_scope import TenantScope

NOW=datetime(2026,8,14,tzinfo=UTC);SCOPE=TenantScope("org-org","dev-project");HASH="a"*64
def ref(kind,value,digest=HASH):return VersionedAssetRef(assetType=kind,assetId=value,revision=1,contentHash=digest)
def resolution(readiness=ModelRuntimeReadiness.READY):return ModelRouteResolution(tenant=TenantContext(orgId="org-org",projectId="dev-project"),route=ref("ModelRouteRevision","route-1"),policy=ref("RuntimePolicyRevision","policy-1"),readiness=readiness,selectedModel=ref("RegisteredModelRevision","model-1") if readiness is ModelRuntimeReadiness.READY else None,selectedProvider=ref("ProviderInstanceRevision","provider-1") if readiness is ModelRuntimeReadiness.READY else None,selectedPriceSnapshot=ref("ModelPriceSnapshotRevision","price-1") if readiness is ModelRuntimeReadiness.READY else None,blockerCodes=[] if readiness is ModelRuntimeReadiness.READY else ["route_eval_gate_not_passed"],resolvedAt=NOW)
class Resolver:
    def __init__(self,result):self.result=result
    def resolve(self,scope,route_id):assert scope==SCOPE and route_id=="route-1";return self.result
class Capacity:
    def __init__(self):self.reserved=[];self.released=[]
    def reserve(self,scope,result,run_id):self.reserved.append(run_id);return "reservation-1"
    def release(self,scope,reservation_id):self.released.append(reservation_id)
    def release_for_run(self,scope,run_id):self.released.append(f"run:{run_id}")
class ReleaseFails(Capacity):
    def release_for_run(self,scope,run_id):raise RuntimeError("release transport failed")
class Conn:
    def __init__(self,row,updated=True,commit_error=False):self.row=row;self.updated=updated;self.committed=False;self.commit_error=commit_error
    def execute(self,query,args):
        if query.lstrip().startswith("SELECT"):return Result(self.row)
        return Result({**self.row,"status":args[0],"version":2} if self.updated else None)
    def commit(self):
        if self.commit_error:raise RuntimeError("commit failed")
        self.committed=True
class Result:
    def __init__(self,row):self.value=row
    def fetchone(self):return self.value
def factory(conn):
    @contextmanager
    def connect(scope):yield conn
    return connect
def row(policy_kind="RuntimePolicyRevision"):
    return {"agent_run_id":"run-1","model_route_ref":ref("ModelRouteRevision","route-1").model_dump(mode="json",by_alias=True),"policy_ref":ref(policy_kind,"policy-1").model_dump(mode="json",by_alias=True)}

def test_running_requires_exact_ready_resolution_and_capacity():
    conn=Conn(row());capacity=Capacity();service=AipAgentRunService(factory(conn),model_resolver=Resolver(resolution()),capacity_gate=capacity)
    service._from_row=lambda scope,value:value
    result=service.transition(SCOPE,"run-1",expected_version=1,from_status=AgentRunStatus.QUEUED,to_status=AgentRunStatus.RUNNING,actor="pytest",occurred_at=NOW)
    assert result["status"]=="running" and capacity.reserved==["run-1"] and conn.committed

@pytest.mark.parametrize(("policy_kind","readiness","message"),[("PolicyRevision",ModelRuntimeReadiness.READY,"runtime_policy_revision_required"),("RuntimePolicyRevision",ModelRuntimeReadiness.BLOCKED,"route_eval_gate_not_passed")])
def test_running_fails_closed_without_exact_ready_authority(policy_kind,readiness,message):
    conn=Conn(row(policy_kind));capacity=Capacity();service=AipAgentRunService(factory(conn),model_resolver=Resolver(resolution(readiness)),capacity_gate=capacity)
    with pytest.raises(AipAgentRegistryTransitionBlocked,match=message):service.transition(SCOPE,"run-1",expected_version=1,from_status=AgentRunStatus.QUEUED,to_status=AgentRunStatus.RUNNING,actor="pytest",occurred_at=NOW)
    assert capacity.reserved==[] and not conn.committed

def test_cas_failure_releases_capacity_reservation():
    conn=Conn(row(),updated=False);capacity=Capacity();service=AipAgentRunService(factory(conn),model_resolver=Resolver(resolution()),capacity_gate=capacity)
    with pytest.raises(AipAgentRegistryConflict):service.transition(SCOPE,"run-1",expected_version=1,from_status=AgentRunStatus.QUEUED,to_status=AgentRunStatus.RUNNING,actor="pytest",occurred_at=NOW)
    assert capacity.released==["reservation-1"]

def test_commit_failure_releases_capacity_reservation():
    conn=Conn(row(),commit_error=True);capacity=Capacity();service=AipAgentRunService(factory(conn),model_resolver=Resolver(resolution()),capacity_gate=capacity)
    with pytest.raises(RuntimeError,match="commit failed"):service.transition(SCOPE,"run-1",expected_version=1,from_status=AgentRunStatus.QUEUED,to_status=AgentRunStatus.RUNNING,actor="pytest",occurred_at=NOW)
    assert capacity.released==["reservation-1"]

def test_leaving_running_releases_capacity_for_agent_run():
    conn=Conn({**row(),"status":"running","version":1});capacity=Capacity();service=AipAgentRunService(factory(conn),model_resolver=Resolver(resolution()),capacity_gate=capacity)
    service._from_row=lambda scope,value:value
    service.transition(SCOPE,"run-1",expected_version=1,from_status=AgentRunStatus.RUNNING,to_status=AgentRunStatus.SUCCEEDED,actor="pytest",occurred_at=NOW)
    assert capacity.released==["run:run-1"]

def test_release_failure_after_committed_terminal_transition_uses_ttl_recovery():
    conn=Conn({**row(),"status":"running","version":1});service=AipAgentRunService(factory(conn),model_resolver=Resolver(resolution()),capacity_gate=ReleaseFails())
    service._from_row=lambda scope,value:value
    result=service.transition(SCOPE,"run-1",expected_version=1,from_status=AgentRunStatus.RUNNING,to_status=AgentRunStatus.SUCCEEDED,actor="pytest",occurred_at=NOW)
    assert result["status"]=="succeeded" and conn.committed

def test_default_capacity_gate_keeps_real_start_blocked():
    service=AipAgentRunService(factory(Conn(row())),model_resolver=Resolver(resolution()),capacity_gate=UnavailableCapacityReservationGate())
    with pytest.raises(AipAgentRegistryTransitionBlocked,match="capacity_reservation_authority_unavailable"):service.transition(SCOPE,"run-1",expected_version=1,from_status=AgentRunStatus.QUEUED,to_status=AgentRunStatus.RUNNING,actor="pytest",occurred_at=NOW)

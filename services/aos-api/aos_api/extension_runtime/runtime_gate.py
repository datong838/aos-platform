"""Trusted synchronous broker seam: never export a reusable admission token."""
import inspect
import asyncio
from uuid import UUID
from pydantic import BaseModel,ConfigDict

from aos_api.asset_registry.composition_contracts import CurrentInstallationRef,ResolvedBundle
from .lifecycle import AdmissionFacts,effective_ready
from .lifecycle_store import _require_transaction,_values


class CurrentPolicy(BaseModel):
    model_config=ConfigDict(strict=True,extra="forbid",frozen=True)
    permissions_valid:bool
    budget_valid:bool
    policy_valid:bool


def _reject_deferred(result):
    if inspect.isawaitable(result) or inspect.isgenerator(result) or inspect.isasyncgen(result):
        if isinstance(result,asyncio.Future):result.cancel()
        if inspect.iscoroutine(result) or inspect.isgenerator(result):result.close()
        raise ValueError("execution must finish within the locked transaction")


def run_guarded(conn,*,installation_store,org_id,project_id,current_ref,generation,
                request_epoch,selected,check_current_policy,execute):
    """Caller owns trusted scope/policy/port implementation and transaction."""
    _require_transaction(conn)
    if type(request_epoch) is not int or request_epoch<1:
        raise ValueError("positive execution epoch required")
    if not callable(check_current_policy) or not callable(execute) or inspect.iscoroutinefunction(execute):
        raise ValueError("trusted synchronous policy and execution callbacks required")
    scope=conn.execute("SELECT current_setting('aos.org_id',true) AS org_id,current_setting('aos.project_id',true) AS project_id").fetchone()
    if not org_id or not project_id or _values(scope,("org_id","project_id"))!=(org_id,project_id):
        raise PermissionError("runtime tenant scope mismatch")
    current_ref=CurrentInstallationRef.model_validate(current_ref)
    selected=ResolvedBundle.model_validate(selected)
    baseline=installation_store.load_active_baseline_in_transaction(conn,org_id=org_id,project_id=project_id,requested_ref=current_ref)
    if selected not in baseline.lock.payload.resolved:
        raise PermissionError("runtime package is not in the active lock")
    row=conn.execute("""SELECT installation_revision,package_lock_ref,observed_state,enabled,
        operation_fence,execution_epoch,desired_state FROM extension_runtime_binding
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s FOR SHARE""",
        (org_id,project_id,UUID(current_ref.installation_id),UUID(str(generation)))).fetchone()
    if row is None:
        raise PermissionError("runtime binding unavailable")
    revision,lock_ref,observed,enabled,fence,epoch,desired=_values(row,
        ("installation_revision","package_lock_ref","observed_state","enabled","operation_fence","execution_epoch","desired_state"))
    if lock_ref.get("lockHash")!=baseline.lock.lock_hash:
        raise PermissionError("runtime binding lock mismatch")
    policy=check_current_policy(conn,baseline)
    _reject_deferred(policy)
    policy=CurrentPolicy.model_validate(policy.model_dump() if isinstance(policy,CurrentPolicy) else policy)
    facts=AdmissionFacts(installation_active=True,installation_revision=baseline.server_ref.revision,
        binding_installation_revision=revision,binding_ready=observed=="ready" and desired=="enabled",
        enabled=enabled,operation_fence=fence,execution_epoch=epoch,request_epoch=request_epoch,
        **policy.model_dump())
    if not effective_ready(facts):
        raise PermissionError("runtime request is not currently admitted")
    result=execute()
    _reject_deferred(result)
    return result

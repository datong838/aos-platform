from types import SimpleNamespace
import asyncio
import uuid
import psycopg
from psycopg import sql
import pytest
from test_lifecycle_pg import database,seed,pytestmark
from test_admission import fixture


def setup_gate(database):
    from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
    conn,_,schema=database
    installation,_=seed(conn)
    generation=uuid.uuid4()
    selected=fixture()[0]["selected"]
    current=CurrentInstallationRef(installationId=str(installation),revision=1,lockHash="sha256:"+"a"*64,overlayRevision="test-overlay")
    conn.execute("""INSERT INTO extension_runtime_binding
        (org_id,project_id,installation_id,generation,installation_revision,package_lock_ref,profile_ref,
         config_ref,desired_state,observed_state,enabled,operation_fence)
        VALUES('org-org','dev-project',%s,%s,1,%s::jsonb,'internal-python-v1','{}','enabled','ready',true,false)""",
        (installation,generation,'{"lockHash":"'+current.lock_hash+'"}'))
    conn.execute("SELECT set_config('aos.org_id','org-org',false),set_config('aos.project_id','dev-project',false)")
    class Store:
        # Only baseline reader is a test seam; binding/fence locks are actual PG.
        def load_active_baseline_in_transaction(self,c,**kwargs):
            c.execute("SELECT installation_id FROM bundle_installation WHERE installation_id=%s FOR SHARE",(installation,))
            return SimpleNamespace(server_ref=current,lock=SimpleNamespace(lock_hash=current.lock_hash,payload=SimpleNamespace(resolved=[selected])))
    return dict(conn=conn,installation_store=Store(),org_id="org-org",project_id="dev-project",
                current_ref=current,generation=generation,request_epoch=1,selected=selected),schema


def test_gate_current_policy_and_epoch_reject_without_execution(database):
    from aos_api.extension_runtime.runtime_gate import run_guarded,CurrentPolicy
    args,_=setup_gate(database)
    conn=args["conn"]
    checks=lambda c,b:CurrentPolicy(permissions_valid=True,budget_valid=True,policy_valid=True)
    with conn.transaction():assert run_guarded(**args,check_current_policy=checks,execute=lambda:"准入成功")=="准入成功"
    for changed in ({"request_epoch":2},{"request_epoch":True}):
        with pytest.raises((PermissionError,ValueError)):
            with conn.transaction():run_guarded(**{**args,**changed},check_current_policy=checks,execute=lambda:pytest.fail("must not execute"))
    for key in ("permissions_valid","budget_valid","policy_valid"):
        policy=CurrentPolicy(**{name:name!=key for name in ("permissions_valid","budget_valid","policy_valid")})
        with pytest.raises(PermissionError):
            with conn.transaction():run_guarded(**args,check_current_policy=lambda c,b:policy,execute=lambda:pytest.fail("must not execute"))


def test_gate_binding_lock_blocks_fence_and_then_rejects_old_epoch(database):
    from aos_api.extension_runtime.runtime_gate import run_guarded,CurrentPolicy
    args,schema=setup_gate(database)
    conn=args["conn"]
    checks=lambda c,b:CurrentPolicy(permissions_valid=True,budget_valid=True,policy_valid=True)
    with psycopg.connect(host="127.0.0.1",port=18432,user="postgres",dbname="postgres",autocommit=True) as other:
        other.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        other.execute("SET lock_timeout='100ms'")
        def during():
            with pytest.raises(psycopg.errors.LockNotAvailable):
                other.execute("UPDATE extension_runtime_binding SET enabled=false,operation_fence=true,execution_epoch=2")
            return "read completed"
        with conn.transaction():assert run_guarded(**args,check_current_policy=checks,execute=during)=="read completed"
        other.execute("UPDATE extension_runtime_binding SET enabled=false,operation_fence=true,execution_epoch=2")
    with pytest.raises(PermissionError):
        with conn.transaction():run_guarded(**args,check_current_policy=checks,execute=lambda:pytest.fail("late request"))


def test_gate_scope_and_lock_membership(database):
    from aos_api.extension_runtime.runtime_gate import run_guarded,CurrentPolicy
    args,_=setup_gate(database)
    conn=args["conn"]
    checks=lambda c,b:CurrentPolicy(permissions_valid=True,budget_valid=True,policy_valid=True)
    for changed in ({"org_id":"dev-org"},{"selected":args["selected"].model_copy(update={"content_hash":"sha256:"+"b"*64})}):
        with pytest.raises(PermissionError):
            with conn.transaction():run_guarded(**{**args,**changed},check_current_policy=checks,execute=lambda:pytest.fail("must not execute"))
    conn.execute("UPDATE extension_runtime_binding SET package_lock_ref='{}'")
    with pytest.raises(PermissionError):
        with conn.transaction():run_guarded(**args,check_current_policy=checks,execute=lambda:pytest.fail("wrong lock"))


@pytest.mark.parametrize('fence', ['disabled', 'operation-fenced'])
def test_independent_reader_cannot_bypass_persisted_installation_fence(database, fence):
    from aos_api.extension_runtime.runtime_gate import run_guarded, CurrentPolicy
    args, _ = setup_gate(database)
    conn = args['conn']
    if fence == 'disabled':
        conn.execute('UPDATE extension_runtime_binding SET enabled=false')
    else:
        conn.execute('UPDATE extension_runtime_binding SET enabled=false,operation_fence=true')
    with pytest.raises(PermissionError), conn.transaction():
        run_guarded(**args,
            check_current_policy=lambda c, b: CurrentPolicy(
                permissions_valid=True, budget_valid=True, policy_valid=True),
            execute=lambda: pytest.fail('fenced installation reached source callback'))


@pytest.mark.parametrize("deferred",["async-function","coroutine-result","generator-result"])
def test_gate_cannot_return_deferred_execution(database,deferred):
    from aos_api.extension_runtime.runtime_gate import run_guarded,CurrentPolicy
    args,_=setup_gate(database)
    checks=lambda c,b:CurrentPolicy(permissions_valid=True,budget_valid=True,policy_valid=True)
    async def later():return "must not escape transaction"
    def generator():yield "must not escape transaction"
    execute={"async-function":later,"coroutine-result":lambda:later(),"generator-result":lambda:generator()}[deferred]
    with pytest.raises(ValueError):
        with args["conn"].transaction():run_guarded(**args,check_current_policy=checks,execute=execute)


def test_gate_cancels_new_task_before_event_loop_can_execute_it(database):
    from aos_api.extension_runtime.runtime_gate import run_guarded,CurrentPolicy
    args,_=setup_gate(database)
    checks=lambda c,b:CurrentPolicy(permissions_valid=True,budget_valid=True,policy_valid=True)
    actions=[]
    async def run():
        async def action():actions.append("escaped")
        with pytest.raises(ValueError):
            with args["conn"].transaction():run_guarded(**args,check_current_policy=checks,execute=lambda:asyncio.create_task(action()))
        await asyncio.sleep(0)
        assert actions==[]
    asyncio.run(run())

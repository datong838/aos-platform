"""Original signed cost revoke waits on its actual implicit fence trigger."""
import hashlib
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event

import pytest

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]


class ProbePlugin:
    @pytest.hookimpl(tryfirst=True)
    def pytest_pyfunc_call(self, pyfuncitem):
        if pyfuncitem.originalname != 'test_real_caller_consumes_once_and_legacy_store_reads':
            return None
        original = pyfuncitem.module
        from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
        from aos_api.db import connect_serializable
        captured = []
        approve = original.approved

        def record_approval(*args, **kwargs):
            result = approve(*args, **kwargs)
            captured.append(result)
            return result

        original.approved = record_approval
        try:
            pyfuncitem.obj(**{name:pyfuncitem.funcargs[name]
                for name in pyfuncitem._fixtureinfo.argnames})
        finally:
            original.approved = approve
        assert len(captured) == 1
        maker, _, proposal, saved, decision = captured[0]
        issuer_factory = pyfuncitem.funcargs['issuer_factory']
        sign = pyfuncitem.funcargs['https_signer'][0]
        command = original.command(sign, maker, saved, operation='revoke', decision=None,
            reason='isolated lock contract observation')
        ready = Event()
        issuer_identity = {}

        @contextmanager
        def observed_issuer(scope, read_only):
            with issuer_factory(scope, read_only) as conn:
                issuer_identity.update(conn.execute('SELECT pg_backend_pid() AS pid, '
                    'session_user AS session,current_database() AS database').fetchone())
                ready.set()
                yield conn

        with original.isolated_owner() as observer, connect_serializable(original.SCOPE) as caller:
            assert observer.info.dbname.startswith('aos_test_')
            assert str(observer.execute('SELECT system_identifier FROM pg_control_system()')
                .fetchone()['system_identifier']) == '7693564235776004128'
            before = observer.execute('SELECT version FROM aip_budget_cost_runtime_fence '
                'WHERE org_id=%s AND project_id=%s AND budget_id=%s AND revision=%s',
                (*original.SCOPE.key,proposal.target.budget_id,proposal.target.revision)).fetchone()
            assert before is not None
            identity = caller.execute("SELECT current_user AS role,current_setting('transaction_isolation') "
                "AS isolation,pg_backend_pid() AS pid,pg_current_xact_id()::text AS xid").fetchone()
            assert identity['role']=='aos_runtime' and identity['isolation']=='serializable'
            locked = caller.execute('SELECT version FROM aip_budget_cost_runtime_fence '
                'WHERE org_id=%s AND project_id=%s AND budget_id=%s AND revision=%s FOR UPDATE',
                (*original.SCOPE.key,proposal.target.budget_id,proposal.target.revision)).fetchone()
            assert locked == before
            # Pure row lock: no new hold, no fictitious Task or direct fence increment.
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(BudgetCostIssuer(observed_issuer).execute, command)
                try:
                    assert ready.wait(timeout=3)
                    assert issuer_identity['session']=='aos_budget_cost_issuer'
                    blockers = []
                    deadline = time.monotonic()+3
                    while identity['pid'] not in blockers:
                        blockers = observer.execute('SELECT pg_blocking_pids(%s) AS pids',
                            (issuer_identity['pid'],)).fetchone()['pids']
                        assert not future.done() and time.monotonic()<deadline
                        time.sleep(.01)
                    assert observer.execute('SELECT count(*) AS n FROM aip_budget_cost_revocation '
                        'WHERE decision_id=%s',(decision['decisionId'],)).fetchone()['n']==0
                finally:
                    caller.rollback()
                result = future.result(timeout=10)
            assert result['decisionId']==decision['decisionId']
            after = observer.execute('SELECT version FROM aip_budget_cost_runtime_fence '
                'WHERE org_id=%s AND project_id=%s AND budget_id=%s AND revision=%s',
                (*original.SCOPE.key,proposal.target.budget_id,proposal.target.revision)).fetchone()
            assert after['version']==before['version']+1
            assert observer.execute('SELECT count(*) AS n FROM aip_budget_cost_revocation '
                'WHERE decision_id=%s',(decision['decisionId'],)).fetchone()['n']==1
            assert observer.execute("SELECT count(*) AS n FROM aip_budget_cost_issuer_receipt "
                "WHERE operation='revoke' AND idempotency_key=%s",(command.idempotency_key,)).fetchone()['n']==1
            for table in ('aip_agent_run','aip_budget_reservation','aip_model_eval_budget_reservation',
                    'aip_model_capacity_reservation'):
                assert observer.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']==0
            assert observer.execute("SELECT count(*) AS n FROM aip_budget_cost_revocation WHERE org_id='dev-org'").fetchone()['n']==0
            record = dict(status='ORIGINAL_SIGNED_REVOKE_NATIVE_FENCE_WAIT_VERIFIED',
                database=observer.info.dbname,cluster='7693564235776004128', caller=identity,
                issuer=issuer_identity,blocked_by=blockers,budget_id=proposal.target.budget_id,
                budget_revision=proposal.target.revision,decision_id=decision['decisionId'],
                revocation_id=result['revocationId'],before_version=before['version'],after_version=after['version'],
                head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
                probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                limitations=['Original fixture Provider history producer; no complete business authorization',
                    'Native runtime row lock is not physical/budget/Intent joint implementation',
                    'No Provider call, new hold, Source attempt replay, or formal effects'])
            (BASE/'cost-revoke-lock-verification.json').write_text(json.dumps(record,indent=2)+'\n')
            print(record['status'],record['database'],'actual issuer waits; revoke COMMIT fence version+1',flush=True)
        return True

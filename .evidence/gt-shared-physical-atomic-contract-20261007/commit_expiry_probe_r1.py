"""Observe the original nonexecuting reader's real post-expiry COMMIT boundary."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

from psycopg.pq import TransactionStatus

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
TARGET = 'test_occupation_source_consumption_uses_actual_business_caller'


def probe(caller, source, command, sign, subject):
    from aos_api.aip_provider_capacity_occupation_source import consume_capacity_source_for_occupation
    from aos_api.aip_provider_capacity_source_consumer import ProviderCapacityConsumptionBlocked
    from aos_api.tenant_scope import apply_transaction_scope
    from tests.aip.test_capacity_occupation_source_pg import SCOPE
    from tests.aip._runtime_guard_history_fixture import isolated_owner

    caller.rollback()
    expiry = int(time.time()) + 4
    expiring = command.model_copy(update={'bearer_token': sign(subject, changes={'exp': expiry})})
    caller.execute("SET LOCAL TimeZone='UTC'")
    apply_transaction_scope(caller, SCOPE)
    identity = caller.execute("SELECT current_database() AS database,session_user AS login,"
        "current_user AS role,pg_backend_pid() AS pid,pg_current_xact_id()::text AS xid,"
        "current_setting('transaction_isolation') AS isolation").fetchone()
    assert caller.pgconn.used_password
    assert identity['login'] == 'aos_provider_capacity_occupation' and identity['role'] == 'aos_runtime'
    assert identity['isolation'] == 'serializable'
    assert consume_capacity_source_for_occupation(caller, expiring) == source
    assert not source.execution_allowed
    readback = caller.execute("SELECT extract(epoch FROM clock_timestamp())::float8 AS clock,"
        "pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid").fetchone()
    assert readback['clock'] < expiry and readback['xid'] == identity['xid'] and readback['pid'] == identity['pid']
    limit = time.monotonic() + 8
    while True:
        before = caller.execute("SELECT extract(epoch FROM clock_timestamp())::float8 AS clock,"
            "pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid").fetchone()
        if before['clock'] >= expiry + 0.1:
            break
        assert time.monotonic() < limit, 'DB clock did not naturally cross the bounded JWT expiry'
        time.sleep(0.025)
    assert before['xid'] == identity['xid'] and before['pid'] == identity['pid']
    # This is exactly one caller COMMIT, with no retry on an unknown outcome.
    caller.commit()
    assert caller.info.transaction_status == TransactionStatus.IDLE
    after = caller.execute('SELECT extract(epoch FROM clock_timestamp())::float8 AS clock').fetchone()
    assert after['clock'] >= before['clock']
    caller.rollback()
    caller.execute("SET LOCAL TimeZone='UTC'")
    apply_transaction_scope(caller, SCOPE)
    try:
        consume_capacity_source_for_occupation(caller, expiring)
    except ProviderCapacityConsumptionBlocked:
        expired_rejected = True
    else:
        raise AssertionError('Expired JWT was accepted by the original fresh reader')
    finally:
        caller.rollback()
    caller.execute("SET LOCAL TimeZone='UTC'")
    apply_transaction_scope(caller, SCOPE)
    assert consume_capacity_source_for_occupation(caller,
        command.model_copy(update={'bearer_token': sign(subject)})) == source
    caller.rollback()
    with isolated_owner() as admin:
        admin.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        cluster = admin.execute("SELECT system_identifier::text AS cluster FROM pg_control_system()").fetchone()['cluster']
        assert cluster == '7693564235776004128'
        counts = {t: admin.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in
            ('aip_agent_run', 'aip_model_capacity_reservation', 'aip_budget_reservation', 'aip_model_eval_budget_hold')}
        assert not any(counts.values())
    result = dict(status='NONEXECUTING_SOURCE_READ_COMMIT_AFTER_JWT_EXPIRY_OBSERVED',
        identity=identity, cluster=cluster, authentication_expiry=expiry,
        read_return=readback, before_commit=before, after_commit=after,
        commit_calls=1, commit_returned_idle=True, expired_fresh_read_rejected=expired_rejected,
        fresh_authentication_restored=True, execution_allowed=False,
        source_ref=command.source_ref.model_dump(mode='json', by_alias=True), product_counts=counts,
        head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        product_sha256={n: hashlib.sha256((REPO/n).read_bytes()).hexdigest() for n in
            ('services/aos-api/aos_api/aip_provider_capacity_occupation_source.py',
             'services/aos-api/aos_api/aip_provider_capacity_source_consumer.py',
             'services/aos-api/tests/aip/test_capacity_occupation_source_pg.py')},
        limitations=['Nonexecuting Source fact read only, no business hold/budget/Intent or send',
            'Original reader promises currentness at return; joint actual-COMMIT deadline gate remains required',
            'Historical timing evidence belongs to this executed probe; retained state alone cannot prove it'])
    (BASE/'commit-expiry-verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result['status'], identity['database'], 'single actual COMMIT; expired fresh read denied; business0', flush=True)


class ProbePlugin:
    module = None
    original = None
    def pytest_runtest_setup(self, item):
        if item.originalname == TARGET:
            self.module = item.module
            self.original = item.module._assert_occupation_epoch_concurrency
            def wrapped(*args):
                probe(*args)
                return self.original(*args)
            item.module._assert_occupation_epoch_concurrency = wrapped
    def pytest_runtest_teardown(self, item, nextitem):
        if self.module is not None:
            self.module._assert_occupation_epoch_concurrency = self.original
            self.module = None
    def pytest_sessionfinish(self, session, exitstatus):
        path = BASE/'commit-expiry-verification.json'
        if path.exists():
            result = json.loads(path.read_text())
            result['original_full_test_exitstatus'] = int(exitstatus)
            result['original_full_test_cleanup_passed'] = int(exitstatus) == 0
            path.write_text(json.dumps(result, indent=2)+'\n')

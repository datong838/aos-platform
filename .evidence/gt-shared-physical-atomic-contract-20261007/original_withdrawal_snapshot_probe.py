"""Actual withdrawal writer precedes the original SCRAM/SER fact reader."""
import hashlib
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
TARGET = 'test_occupation_source_consumption_uses_actual_business_caller'


class ProbePlugin:
    item = None
    passed = False
    executed = False

    def pytest_runtest_setup(self, item):
        if item.originalname == TARGET:
            self.item = item

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        if item is self.item and report.when == 'call':
            self.passed = report.passed

    def pytest_fixture_post_finalizer(self, fixturedef, request):
        if (fixturedef.argname != 'exact_public_source_caller' or not self.passed
                or self.executed or fixturedef.cached_result is None):
            return
        # The original fixture has restored its own harness grants. No new
        # role, grant, function or authority exception is introduced here.
        self.executed = True
        probe(self.item)


def probe(item):
    from fastapi.testclient import TestClient
    from aos_api.main import create_app
    from aos_api.aip_action_models import DecideActionProposalRequest, WithdrawActionProposalRequest
    from aos_api.aip_action_store import canonical_hash
    from aos_api.aip_provider_capacity_source_action import (
        propose_provider_capacity_source, decide_provider_capacity_source)
    from tests.aip import test_capacity_source_publication_transaction_pg as original
    from tests.aip._runtime_guard_history_fixture import isolated_owner
    maker, checker = item.funcargs['approved_command'][:2]
    candidate = item.funcargs['native_signed_source'][3]
    caller, harness, old_args, _ = item.funcargs['native_original_fact_reader']
    sign = item.funcargs['https_signer'][0]
    proposed = propose_provider_capacity_source(maker, candidate,
        'snapshot-proposal-'+uuid4().hex, candidate.valid_until)
    approved = decide_provider_capacity_source(checker, proposed.proposal.id,
        'snapshot-approval-'+uuid4().hex,
        DecideActionProposalRequest(expectedProposalVersion=proposed.proposal.version,
            expectedProposalHash=proposed.proposal.proposal_hash, decision='approved',
            reason='isolated original writer-first snapshot edge', approvalExpiresAt=candidate.valid_until))
    args = (maker.subject,
        dict(assetType='ActionProposal', assetId=approved.proposal.id, revision=2,
            contentHash=approved.proposal.proposal_hash),
        dict(assetType='ActionApprovalEvent', assetId=approved.approvals[0].id, revision=1,
            contentHash=canonical_hash(approved.approvals[0].model_dump(mode='json', by_alias=True))))
    assert approved.proposal.id != old_args[1]['assetId']
    assert not caller.closed and caller.pgconn.used_password
    original._refresh_native_facts_transaction(caller)
    positive = original._call_native_original_facts(caller, harness, args)
    assert positive['source'] == candidate.model_dump(mode='json', by_alias=True)
    original._refresh_native_facts_transaction(caller)
    reader = caller.execute("SELECT pg_backend_pid() AS pid,pg_current_xact_id()::text AS xid,"
        "pg_current_snapshot()::text AS snapshot,session_user AS session,current_user AS role,"
        "current_setting('transaction_isolation') AS isolation").fetchone()
    assert reader['session'] == 'aos_provider_capacity_issuer' and reader['isolation'] == 'serializable'
    key = 'snapshot-withdrawal-'+uuid4().hex
    with isolated_owner() as epoch_holder, isolated_owner() as observer:
        identity = observer.execute("SELECT current_database() AS database,"
            "system_identifier::text AS cluster FROM pg_control_system()").fetchone()
        assert identity['database'].startswith('aos_test_') and identity['cluster'] == '7693564235776004128'
        holder_pid = epoch_holder.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
        assert epoch_holder.execute('SELECT epoch FROM public.aip_capacity_withdrawal_epoch '
            'WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE',
            (*original.SCOPE.key, approved.proposal.id)).fetchone()['epoch'] == 0
        body = WithdrawActionProposalRequest(expectedProposalVersion=approved.proposal.version,
            expectedProposalHash=approved.proposal.proposal_hash, reason='isolated writer-first snapshot edge')
        pending = dict(status='NEW_NATIVE_WITHDRAWAL_INTENT_NO_REPLAY', identity=identity,
            proposal_id=approved.proposal.id, original_proposal_id=old_args[1]['assetId'],
            idempotency_key=key, reader=reader, epoch_holder_pid=holder_pid)
        (BASE / 'original-withdrawal-snapshot-attempt.json').write_text(json.dumps(pending, indent=2)+'\n')
        client = TestClient(create_app())
        with ThreadPoolExecutor(max_workers=2) as pool:
            api_future = pool.submit(client.post, '/v1/aip/action-proposals/'+approved.proposal.id+'/withdraw',
                headers={'Authorization': 'Bearer '+sign(maker.subject), 'Idempotency-Key': key,
                    'X-Org-Id': original.SCOPE.org_id, 'X-Project-Id': original.SCOPE.project_id},
                json=body.model_dump(mode='json', by_alias=True))
            read_future = None
            try:
                deadline = time.monotonic()+4
                while time.monotonic() < deadline:
                    observer.execute('SELECT pg_stat_clear_snapshot()')
                    blocked = observer.execute('SELECT pid FROM pg_stat_activity WHERE datname=%s '
                        'AND %s=ANY(pg_blocking_pids(pid))', (identity['database'], holder_pid)).fetchall()
                    if blocked:
                        assert len(blocked) == 1
                        api_pid = blocked[0]['pid']
                        break
                    assert not api_future.done(), 'Original API completed before writer wait'
                    time.sleep(.01)
                else:
                    raise AssertionError('Original API epoch wait not observed')
                read_future = pool.submit(original._call_native_original_facts, caller, harness, args)
                deadline = time.monotonic()+4
                while time.monotonic() < deadline:
                    reader_blockers = observer.execute('SELECT pg_blocking_pids(%s) AS pids',
                        (reader['pid'],)).fetchone()['pids']
                    if api_pid in reader_blockers:
                        break
                    assert not read_future.done(), 'Reader ended before writer row wait'
                    time.sleep(.01)
                else:
                    raise AssertionError('Native reader did not wait on API proposal lock')
                assert observer.execute('SELECT count(*) AS n FROM aip_action_withdrawal_event '
                    'WHERE idempotency_key=%s', (key,)).fetchone()['n'] == 0
            finally:
                epoch_holder.rollback()
            response = api_future.result(timeout=10)
            assert response.status_code == 200
            assert read_future is not None
            with pytest.raises(psycopg.errors.SerializationFailure) as stale:
                read_future.result(timeout=10)
            assert stale.value.sqlstate == '40001'
            client.close()
        original._refresh_native_facts_transaction(caller)
        with pytest.raises(psycopg.errors.NoDataFound) as fresh:
            original._call_native_original_facts(caller, harness, args)
        assert fresh.value.sqlstate == 'P0002'
        caller.rollback()
        state = observer.execute('SELECT p.status,p.version,e.epoch FROM aip_action_proposal p '
            'JOIN aip_capacity_withdrawal_epoch e USING(org_id,project_id,proposal_id) '
            'WHERE p.proposal_id=%s', (approved.proposal.id,)).fetchone()
        assert state == dict(status='withdrawn', version=3, epoch=1)
        counts = {t: observer.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in
            ('aip_agent_run', 'aip_model_capacity_reservation', 'aip_budget_reservation', 'aip_model_eval_budget_reservation')}
        assert not any(counts.values())
        record = dict(**pending, verdict='ORIGINAL_API_WRITER_FIRST_STALE_40001_FRESH_SOURCE_PREFIX_REJECTED',
            api_pid=api_pid, reader_blockers=reader_blockers, old_snapshot_sqlstate='40001',
            fresh_snapshot_sqlstate='P0002', committed_state=state, product_counts=counts,
            head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
            probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            limitations=['Original fact prefix, not complete signed occupation Source admission',
                'Original test harness restored by its fixture, no new ACL grants',
                'Independent approved proposal not a published Source exact ref',
                'No app lifespan/restart, legal business AgentRun or joint ledger completion'])
        (BASE / 'original-withdrawal-snapshot-verification.json').write_text(json.dumps(record, indent=2)+'\n')
        print(record['verdict'], identity['database'], 'original API COMMIT; actual SCRAM/SER reader40001; fresh prefixP0002', flush=True)

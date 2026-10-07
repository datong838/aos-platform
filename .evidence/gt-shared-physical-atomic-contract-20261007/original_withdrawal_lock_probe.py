"""Original maker-authenticated withdrawal API and its implicit epoch writer."""
import hashlib
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
TARGET = 'test_occupation_source_consumption_uses_actual_business_caller'


class ProbePlugin:
    @pytest.hookimpl(tryfirst=True)
    def pytest_pyfunc_call(self, pyfuncitem):
        if pyfuncitem.originalname != TARGET:
            return None
        original = pyfuncitem.module
        captured = []
        epoch_check = original._assert_occupation_epoch_concurrency

        def capture(caller, source, command, sign, subject):
            captured.append((source, sign, subject))
            return epoch_check(caller, source, command, sign, subject)

        original._assert_occupation_epoch_concurrency = capture
        try:
            pyfuncitem.obj(**{name: pyfuncitem.funcargs[name]
                for name in pyfuncitem._fixtureinfo.argnames})
        finally:
            original._assert_occupation_epoch_concurrency = epoch_check
        assert len(captured) == 1
        source, sign, subject = captured[0]
        from aos_api.aip_provider_capacity_source_action import (
            propose_provider_capacity_source, decide_provider_capacity_source)
        from aos_api.aip_action_models import DecideActionProposalRequest
        maker, checker = pyfuncitem.funcargs['approved_command'][:2]
        candidate = pyfuncitem.funcargs['native_signed_source'][3]
        assert maker.subject == subject
        proposed = propose_provider_capacity_source(maker, candidate,
            'isolated-withdrawal-proposal-'+uuid4().hex, candidate.valid_until)
        approved = decide_provider_capacity_source(checker, proposed.proposal.id,
            'isolated-withdrawal-approval-'+uuid4().hex,
            DecideActionProposalRequest(expectedProposalVersion=proposed.proposal.version,
                expectedProposalHash=proposed.proposal.proposal_hash, decision='approved',
                reason='isolated original withdrawal lock edge', approvalExpiresAt=candidate.valid_until))
        proposal_id = approved.proposal.id
        assert proposal_id != source.source_proposal_ref.asset_id
        from fastapi.testclient import TestClient
        from aos_api.main import create_app
        from aos_api.aip_action_models import WithdrawActionProposalRequest
        key = 'isolated-native-withdrawal-' + uuid4().hex
        with original.isolated_owner() as proposal_holder, original.isolated_owner() as epoch_holder, \
                original.isolated_owner() as observer:
            identity = observer.execute("SELECT current_database() AS database,"
                "system_identifier::text AS cluster FROM pg_control_system()").fetchone()
            assert identity['database'].startswith('aos_test_')
            assert identity['cluster'] == '7693564235776004128'
            proposal_holder.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
            epoch_holder.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
            holder_pids = [c.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
                for c in (proposal_holder, epoch_holder)]
            row = proposal_holder.execute("SELECT proposal_hash,version,created_by,status,"
                "expires_at>clock_timestamp() AS current FROM public.aip_action_proposal "
                "WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE",
                (*original.SCOPE.key, proposal_id)).fetchone()
            assert row and row['created_by'] == subject and row['status'] == 'approved' and row['current']
            before_epoch = epoch_holder.execute('SELECT epoch FROM public.aip_capacity_withdrawal_epoch '
                'WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE',
                (*original.SCOPE.key, proposal_id)).fetchone()['epoch']
            assert before_epoch == 0
            body = WithdrawActionProposalRequest(expected_proposal_version=row['version'],
                expected_proposal_hash=row['proposal_hash'], reason='isolated original writer lock observation')
            headers = {'Authorization': 'Bearer ' + sign(subject), 'Idempotency-Key': key,
                'X-Org-Id': original.SCOPE.org_id, 'X-Project-Id': original.SCOPE.project_id}
            # No conftest client reset or lifespan bootstrap: existing full fixture
            # supplies actual authority. Router, auth, DTO, service and store run normally.
            client = TestClient(create_app())
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(client.post, '/v1/aip/action-proposals/'+proposal_id+'/withdraw',
                    headers=headers, json=body.model_dump(mode='json', by_alias=True))
                def waiting_on(holder, expected_pid=None):
                    deadline = time.monotonic() + 4
                    while time.monotonic() < deadline:
                        observer.execute('SELECT pg_stat_clear_snapshot()')
                        matches = observer.execute('SELECT pid FROM pg_stat_activity WHERE datname=%s '
                            'AND %s=ANY(pg_blocking_pids(pid))', (identity['database'], holder)).fetchall()
                        if matches:
                            assert len(matches) == 1
                            pid = matches[0]['pid']
                            if expected_pid is not None:
                                assert pid == expected_pid
                            return pid
                        if future.done():
                            response = future.result()
                            raise AssertionError('Original API ended before lock observation: HTTP '+str(response.status_code))
                        time.sleep(.01)
                    raise AssertionError('Original API wait was not observed')
                try:
                    api_pid = waiting_on(holder_pids[0])
                    assert observer.execute('SELECT count(*) AS n FROM public.aip_action_withdrawal_event '
                        'WHERE idempotency_key=%s', (key,)).fetchone()['n'] == 0
                    proposal_holder.rollback()
                    assert waiting_on(holder_pids[1], api_pid) == api_pid
                    assert observer.execute('SELECT count(*) AS n FROM public.aip_action_withdrawal_event '
                        'WHERE idempotency_key=%s', (key,)).fetchone()['n'] == 0
                finally:
                    proposal_holder.rollback()
                    epoch_holder.rollback()
                response = future.result(timeout=10)
                client.close()
            assert response.status_code == 200
            result = response.json()
            assert result['proposal']['status'] == 'withdrawn'
            after = observer.execute('SELECT status,version FROM public.aip_action_proposal '
                'WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                (*original.SCOPE.key, proposal_id)).fetchone()
            assert after == dict(status='withdrawn', version=row['version']+1)
            after_epoch = observer.execute('SELECT epoch FROM public.aip_capacity_withdrawal_epoch '
                'WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                (*original.SCOPE.key, proposal_id)).fetchone()['epoch']
            assert after_epoch == before_epoch+1
            assert observer.execute('SELECT count(*) AS n FROM public.aip_action_withdrawal_event '
                'WHERE idempotency_key=%s', (key,)).fetchone()['n'] == 1
            counts = {t: observer.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in
                ('aip_agent_run', 'aip_model_capacity_reservation', 'aip_budget_reservation',
                    'aip_model_eval_budget_reservation')}
            assert not any(counts.values())
            assert observer.execute("SELECT count(*) AS n FROM public.aip_action_withdrawal_event "
                "WHERE org_id='dev-org' AND idempotency_key=%s", (key,)).fetchone()['n'] == 0
            evidence = dict(status='ORIGINAL_MAKER_WITHDRAWAL_API_TWO_NATIVE_WAITS_AND_COMMIT_VERIFIED',
                identity=identity, proposal_id=proposal_id, maker=subject, idempotency_key=key,
                original_source_proposal_id=source.source_proposal_ref.asset_id,
                before_proposal_version=row['version'], after_proposal_version=after['version'],
                before_epoch=before_epoch, after_epoch=after_epoch, api_pid=api_pid,
                holder_pids=holder_pids, product_counts=counts, canary=0,
                head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
                probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                limitations=['Original full fixture Source history, no lawful complete business AgentRun',
                    'Independent isolated admin row locks are primitives, not a joint ledger consumer',
                    'Separate original approved Source proposal is not the published Source exact reference',
                    'Existing fixture app authority; no app lifespan/restart acceptance',
                    'One original API request only; no direct withdrawal INSERT or epoch UPDATE'])
            (BASE / 'original-withdrawal-lock-verification.json').write_text(json.dumps(evidence, indent=2)+'\n')
            print(evidence['status'], identity['database'], 'proposal wait then AFTER epoch wait; original COMMIT', flush=True)
        return True

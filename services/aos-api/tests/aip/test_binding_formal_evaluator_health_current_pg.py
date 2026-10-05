"""Health currentness counterexample; raw rows are fault data, not authority."""
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import errors
from psycopg.rows import dict_row
import pytest

from aos_api.db import get_dsn
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE


def test_existing_health_row_lock_and_serial_snapshot_do_not_fence_new_observation():
    provider = 'b90-health-fault-' + uuid4().hex
    ref = {'assetType': 'ProviderInstanceRevision', 'assetId': provider,
           'revision': 1, 'contentHash': 'a' * 64}
    old_id, new_id = provider + '-healthy', provider + '-unavailable'
    insert = '''INSERT INTO public.aip_provider_health_observation(
        org_id,project_id,observation_id,provider_ref,status,observed_at,expires_at)
        VALUES(%s,%s,%s,%s::jsonb,%s,clock_timestamp()-(%s * interval '1 second'),
               clock_timestamp()+interval '10 minutes')'''
    latest = '''SELECT observation_id,status FROM public.aip_provider_health_observation
        WHERE org_id=%s AND project_id=%s AND provider_ref->>'assetId'=%s
        ORDER BY observed_at DESC LIMIT 1'''
    with isolated_owner() as owner:
        owner.execute(insert, (*SCOPE.key, old_id, json.dumps(ref), 'healthy', 60))
        owner.commit()
        with psycopg.connect(get_dsn(), row_factory=dict_row) as reader:
            reader.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
            row = reader.execute(latest + ' FOR SHARE', (*SCOPE.key, provider)).fetchone()
            assert row == {'observation_id': old_id, 'status': 'healthy'}
            with psycopg.connect(get_dsn(), row_factory=dict_row) as writer:
                writer.execute("SET LOCAL lock_timeout='500ms'")
                writer.execute(insert, (*SCOPE.key, new_id, json.dumps(ref), 'unavailable', 0))
                writer_pid = writer.info.backend_pid
                writer.commit()
            current = owner.execute(latest, (*SCOPE.key, provider)).fetchone()
            stale = reader.execute(latest, (*SCOPE.key, provider)).fetchone()
            assert current == {'observation_id': new_id, 'status': 'unavailable'}
            assert stale == row
            reader_pid = reader.info.backend_pid
            reader.commit()  # Valid serialization before writer; no automatic 40001.
        if target := os.environ.get('AOS_B90_HEALTH_PROBE_EVIDENCE'):
            path = Path(target)
            assert path.is_absolute() and path.name == 'mechanism-probe.json'
            path.write_text(json.dumps({'schema': 'b90-health-current-counterexample/v1',
                'fault_data_only': True, 'reader_pid': reader_pid, 'writer_pid': writer_pid,
                'writer_committed_without_waiting_on_old_row': True,
                'fresh_current': current, 'serial_snapshot': stale,
                'serial_commit_succeeded': True}, indent=2) + '\n', encoding='utf-8')


def test_complete_evaluator_has_current_health_transaction_consumer():
    # Missing module is contract RED only, not evidence of a business rejection.
    from aos_api.aip_binding_formal_evaluator import read_current_provider_health_fact
    assert callable(read_current_provider_health_fact)


def test_health_epoch_fence_rejects_stale_serializable_snapshot():
    """A serializable reader that observed the health epoch before a concurrent
    health write must fail with 40001, never certify a stale latest observation.

    This is the positive counterpart to the b90 counterexample: the epoch fence
    (not the observation row lock alone) is what makes the stale snapshot reject.
    """
    provider = 'b90-health-fence-' + uuid4().hex
    ref = {'assetType': 'ProviderInstanceRevision', 'assetId': provider,
           'revision': 1, 'contentHash': 'a' * 64}
    insert = '''INSERT INTO public.aip_provider_health_observation(
        org_id,project_id,observation_id,provider_ref,status,observed_at,expires_at)
        VALUES(%s,%s,%s,%s::jsonb,%s,clock_timestamp()-(%s * interval '1 second'),
               clock_timestamp()+interval '10 minutes')'''
    with isolated_owner() as owner:
        owner.execute(insert, (*SCOPE.key, 'seed-' + provider, json.dumps(ref), 'healthy', 60))
        owner.commit()
        with psycopg.connect(get_dsn(), row_factory=dict_row) as reader:
            reader.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
            reader.execute("SET LOCAL lock_timeout='500ms'")
            reader.execute("SELECT set_config('aos.org_id',%s,true),"
                           "set_config('aos.project_id',%s,true)", SCOPE.key)
            before = reader.execute(
                "SELECT epoch FROM public.aip_provider_health_epoch "
                "WHERE org_id=%s AND project_id=%s AND provider_ref->>'assetId'=%s",
                (*SCOPE.key, provider)).fetchone()['epoch']
            assert before >= 1  # seed observation already coordinated the epoch
            # Concurrent health write bumps the epoch and commits.
            with psycopg.connect(get_dsn(), row_factory=dict_row) as writer:
                writer.execute(insert, (*SCOPE.key, 'new-' + provider, json.dumps(ref), 'unavailable', 0))
                writer.commit()
            # Re-acquire the shared fence lock on the now-bumped epoch row. The
            # serializable snapshot predates the committed bump, so SSI must reject.
            with pytest.raises(errors.SerializationFailure):
                reader.execute(
                    "SELECT public.aos_provider_health_epoch_lock(%s,%s,%s::jsonb,true)",
                    (*SCOPE.key, json.dumps(ref, sort_keys=True)))
                reader.commit()

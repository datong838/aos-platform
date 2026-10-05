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


def _scope(conn):
    conn.execute("SELECT set_config('aos.org_id',%s,true),"
                 "set_config('aos.project_id',%s,true)", SCOPE.key)


def _insert(conn, provider, *, revision=1):
    ref = {'assetType': 'ProviderInstanceRevision', 'assetId': provider,
           'revision': revision, 'contentHash': 'a' * 64}
    conn.execute('''INSERT INTO public.aip_provider_health_observation(
        org_id,project_id,observation_id,provider_ref,status,observed_at,expires_at)
        VALUES(%s,%s,%s,%s::jsonb,'healthy',clock_timestamp(),
               clock_timestamp()+interval '10 minutes')''',
        (*SCOPE.key, 'fence-' + uuid4().hex, json.dumps(ref)))
    return ref


def test_shared_fence_coordinates_other_revision_and_failed_write_rolls_back():
    provider = 'b90-shared-' + uuid4().hex
    with isolated_owner() as owner:
        _scope(owner)
        ref = _insert(owner, provider)
        owner.commit()
        with psycopg.connect(get_dsn(), row_factory=dict_row) as reader:
            _scope(reader)
            row = reader.execute('SELECT public.aos_provider_health_epoch_lock(%s,%s,%s::jsonb,true) AS epoch',
                                 (*SCOPE.key, json.dumps(ref))).fetchone()
            with psycopg.connect(get_dsn(), row_factory=dict_row) as writer:
                _scope(writer)
                writer.execute("SET LOCAL lock_timeout='150ms'")
                with pytest.raises(errors.LockNotAvailable):
                    _insert(writer, provider, revision=2)
                writer.rollback()
            assert reader.execute('SELECT epoch FROM public.aip_provider_health_epoch '
                'WHERE org_id=%s AND project_id=%s AND provider_id=%s',
                (*SCOPE.key, provider)).fetchone()['epoch'] == row['epoch']
            reader.rollback()


def test_health_truncate_is_rejected():
    with isolated_owner() as owner:
        _scope(owner)
        with pytest.raises(errors.InsufficientPrivilege, match='PROVIDER_HEALTH_TRUNCATE_DENIED'):
            owner.execute('TRUNCATE public.aip_provider_health_observation')
        owner.rollback()


def test_health_fence_owner_and_function_acl_are_bounded():
    with isolated_owner() as owner:
        role = owner.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,"
            "rolreplication,rolbypassrls FROM pg_roles WHERE rolname='aos_provider_health_fence_owner'").fetchone()
        assert role and all(value is False for value in role.values())
        assert owner.execute("SELECT relforcerowsecurity AS forced FROM pg_class "
            "WHERE oid='public.aip_provider_health_epoch'::regclass").fetchone()['forced']
        for function in ('aos_provider_health_epoch_touch()', 'aos_provider_health_epoch_bump()'):
            assert not owner.execute("SELECT has_function_privilege('aos_runtime',%s,'EXECUTE') AS allowed",
                                     ('public.' + function,)).fetchone()['allowed']
        for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
            assert not owner.execute("SELECT has_table_privilege('aos_runtime',"
                "'public.aip_provider_health_epoch',%s) AS allowed", (privilege,)).fetchone()['allowed']


def test_health_write_missing_or_wrong_tenant_is_rejected():
    with isolated_owner() as owner:
        with pytest.raises(errors.InsufficientPrivilege, match='PROVIDER_HEALTH_SCOPE_MISMATCH'):
            _insert(owner, 'b90-noscope-' + uuid4().hex)
        owner.rollback()
        owner.execute("SELECT set_config('aos.org_id','dev-org',true),"
                      "set_config('aos.project_id','dev-project',true)")
        with pytest.raises(errors.InsufficientPrivilege, match='PROVIDER_HEALTH_SCOPE_MISMATCH'):
            _insert(owner, 'b90-canary-' + uuid4().hex)
        owner.rollback()


def test_health_update_coordinates_old_and_new_provider_without_noop_epoch_bump():
    old_id, new_id = 'b90-old-' + uuid4().hex, 'b90-new-' + uuid4().hex
    with isolated_owner() as owner:
        _scope(owner)
        _insert(owner, old_id)
        _insert(owner, new_id)
        owner.commit()
        _scope(owner)
        epoch_sql = ('SELECT provider_id,epoch FROM public.aip_provider_health_epoch '
                     'WHERE org_id=%s AND project_id=%s AND provider_id=ANY(%s) ORDER BY provider_id')
        params = (*SCOPE.key, [old_id, new_id])
        before = owner.execute(epoch_sql, params).fetchall()
        owner.execute("UPDATE public.aip_provider_health_observation SET status=status "
            "WHERE org_id=%s AND project_id=%s AND provider_ref->>'assetId'=%s", (*SCOPE.key, old_id))
        assert owner.execute(epoch_sql, params).fetchall() == before
        owner.execute("UPDATE public.aip_provider_health_observation SET provider_ref="
            "jsonb_set(provider_ref,'{assetId}',to_jsonb(%s::text)) "
            "WHERE org_id=%s AND project_id=%s AND provider_ref->>'assetId'=%s",
            (new_id, *SCOPE.key, old_id))
        after = owner.execute(epoch_sql, params).fetchall()
        assert after == [{**row, 'epoch': row['epoch'] + 1} for row in before]
        owner.rollback()
        _scope(owner)
        assert owner.execute(epoch_sql, params).fetchall() == before


def test_original_health_delete_bumps_coordinator_and_rollback_preserves_history():
    provider = 'b90-delete-' + uuid4().hex
    with isolated_owner() as owner:
        _scope(owner)
        _insert(owner, provider)
        owner.commit()
        _scope(owner)
        query = ('SELECT epoch FROM public.aip_provider_health_epoch '
                 'WHERE org_id=%s AND project_id=%s AND provider_id=%s')
        before = owner.execute(query, (*SCOPE.key, provider)).fetchone()['epoch']
        owner.execute("DELETE FROM public.aip_provider_health_observation WHERE org_id=%s "
            "AND project_id=%s AND provider_ref->>'assetId'=%s", (*SCOPE.key, provider))
        assert owner.execute(query, (*SCOPE.key, provider)).fetchone()['epoch'] == before + 1
        owner.rollback()
        _scope(owner)
        assert owner.execute(query, (*SCOPE.key, provider)).fetchone()['epoch'] == before
        assert owner.execute("SELECT count(*) AS n FROM public.aip_provider_health_observation "
            "WHERE org_id=%s AND project_id=%s AND provider_ref->>'assetId'=%s",
            (*SCOPE.key, provider)).fetchone()['n'] == 1


def test_runtime_reads_shared_neutral_epoch_without_business_write_privileges():
    provider = 'b90-runtime-' + uuid4().hex
    ref = {'assetType': 'ProviderInstanceRevision', 'assetId': provider,
           'revision': 1, 'contentHash': 'a' * 64}
    with isolated_owner() as owner:
        owner.execute('SET LOCAL ROLE aos_runtime')
        _scope(owner)
        epoch = owner.execute('SELECT public.aos_provider_health_epoch_lock(%s,%s,%s::jsonb,true) AS epoch',
                              (*SCOPE.key, json.dumps(ref))).fetchone()['epoch']
        assert epoch == 0  # Neutral initialization invents no health observation.
        assert owner.execute("SELECT count(*) AS n FROM public.aip_provider_health_observation "
            "WHERE org_id=%s AND project_id=%s AND provider_ref->>'assetId'=%s",
            (*SCOPE.key, provider)).fetchone()['n'] == 0
        with pytest.raises(errors.InsufficientPrivilege, match='PROVIDER_HEALTH_READER_SHARED_REQUIRED'):
            owner.execute('SELECT public.aos_provider_health_epoch_lock(%s,%s,%s::jsonb,false)',
                          (*SCOPE.key, json.dumps(ref)))
        owner.rollback()


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
        _scope(owner)
        owner.execute(insert, (*SCOPE.key, old_id, json.dumps(ref), 'healthy', 60))
        owner.commit()
        with psycopg.connect(get_dsn(), row_factory=dict_row) as reader:
            reader.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
            row = reader.execute(latest + ' FOR SHARE', (*SCOPE.key, provider)).fetchone()
            assert row == {'observation_id': old_id, 'status': 'healthy'}
            with psycopg.connect(get_dsn(), row_factory=dict_row) as writer:
                _scope(writer)
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


@pytest.mark.xfail(strict=True, raises=ImportError,
                   reason='完整八依赖命令尚未实现；Health机制通过不构成业务正向')
def test_complete_evaluator_command_remains_an_explicit_pending_contract():
    # An import failure records missing implementation, never a business denial.
    # Once implemented, XPASS forces replacement with real full-command behavior.
    from aos_api.aip_binding_formal_evaluator import evaluate_binding_in_transaction
    assert callable(evaluate_binding_in_transaction)


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
        _scope(owner)
        owner.execute(insert, (*SCOPE.key, 'seed-' + provider, json.dumps(ref), 'healthy', 60))
        owner.commit()
        with psycopg.connect(get_dsn(), row_factory=dict_row) as reader:
            reader.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
            reader.execute("SET LOCAL lock_timeout='500ms'")
            reader.execute("SELECT set_config('aos.org_id',%s,true),"
                           "set_config('aos.project_id',%s,true)", SCOPE.key)
            before = reader.execute(
                "SELECT epoch FROM public.aip_provider_health_epoch "
                "WHERE org_id=%s AND project_id=%s AND provider_id=%s",
                (*SCOPE.key, provider)).fetchone()['epoch']
            assert before >= 1  # seed observation already coordinated the epoch
            # Concurrent health write bumps the epoch and commits.
            with psycopg.connect(get_dsn(), row_factory=dict_row) as writer:
                _scope(writer)
                writer.execute(insert, (*SCOPE.key, 'new-' + provider, json.dumps(ref), 'unavailable', 0))
                writer.commit()
            # Re-acquire the shared fence lock on the now-bumped epoch row. The
            # serializable snapshot predates the committed bump, so SSI must reject.
            with pytest.raises(errors.SerializationFailure):
                reader.execute(
                    "SELECT public.aos_provider_health_epoch_lock(%s,%s,%s::jsonb,true)",
                    (*SCOPE.key, json.dumps(ref, sort_keys=True)))
                reader.commit()

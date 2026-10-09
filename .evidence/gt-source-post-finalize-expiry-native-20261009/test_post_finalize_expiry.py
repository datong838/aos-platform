"""Observe the unresolved issuance-finalize versus caller-COMMIT time boundary."""
import hashlib
import json
import time
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from pydantic import SecretStr
from psycopg.types.json import Jsonb

from aos_api.aip_provider_capacity_publication_contracts import (
    PublishedProviderCapacitySourceV2, parse_signed_capacity_body,
)
from aos_api.aip_provider_capacity_source_issuer import capacity_source_preparation_bytes

pytest_plugins = ('tests.conftest', 'tests.aip.test_capacity_source_publication_transaction_pg')


@pytest.fixture(autouse=True)
def registered_database_isolation(_isolated_postgres_database, monkeypatch):
    """This new node uses the original full-migration bootstrap once per layout."""
    from tests.conftest import _isolated_postgres_database as original_bootstrap
    from aos_api import tenant_catalog, data_os_store
    import os
    assert os.environ['AOS_TEST_RETAIN_DATABASE'] == '1'
    assert os.environ['AOS_TEST_USE_SHARED_DATABASE'] == '0'
    with monkeypatch.context() as local:
        local.setattr(tenant_catalog, '_schema_ready', False)
        local.setattr(data_os_store, '_schema_ready', False)
        database = original_bootstrap.__wrapped__()
        try:
            next(database)
            yield
        finally:
            database.close()


@pytest.mark.parametrize('native_original_fact_reader', ['shared', 'distinct'], indirect=True)
def test_post_finalize_expiry_observes_actual_caller_commit(
        exact_public_source_caller, https_signer, native_original_fact_reader):
    caller, _, material, _ = exact_public_source_caller
    sign, _ = https_signer
    command, _, _ = material['actual_command']()
    maker = json.loads(capacity_source_preparation_bytes(command))['makerSubject']
    exp = int(time.time()) + 20
    command = command.model_copy(update={
        'bearer_token': SecretStr(sign(maker, changes={'exp': exp})),
    })
    packet = capacity_source_preparation_bytes(command)
    assert json.loads(packet)['authentication']['makerSubject'] == maker
    asset = 'post-finalize-expiry-' + uuid4().hex
    identity = caller.execute(
        'SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid,'
        'session_user AS login,current_user AS role').fetchone()
    assert caller.pgconn.used_password and identity['login'] == 'aos_provider_capacity_issuer'
    row = caller.execute(
        'SELECT * FROM public.prepare_capacity_source(%s,%s,%s,%s::jsonb)',
        (packet, command.idempotency_key, asset, Jsonb(material['refs'][-1]))).fetchone()
    raw = bytes(row['source_raw'])
    source = parse_signed_capacity_body(raw, PublishedProviderCapacitySourceV2)
    deadline = source.issuance_context.authentication_expires_at
    assert int(deadline.timestamp()) == exp and source.execution_allowed is False
    signature = material['source_key'].sign(raw)
    finalized = caller.execute('SELECT * FROM public.commit_capacity_source(%s,%s,%s)',
        (command.idempotency_key, raw, signature)).fetchone()
    assert finalized['asset_id'] == asset
    finalized_at = caller.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    assert finalized_at < deadline, 'Fixture did not finalize with a currently valid JWT'
    assert source.valid_until > deadline, 'JWT expiry and Source validity must be distinct'
    observations = []
    stop = time.monotonic() + 30
    while True:
        now = caller.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        observations.append(now.isoformat())
        if now.timestamp() >= deadline.timestamp() + .1:
            break
        assert time.monotonic() < stop, 'Actual database deadline was not crossed'
        time.sleep(min(1, max(.02, deadline.timestamp() + .1 - now.timestamp())))
    before_commit = now
    assert deadline < before_commit < source.valid_until
    result = {'outcome': 'committed'}
    try:
        caller.commit()
    except psycopg.Error as error:
        result = {'outcome': 'rejected', 'sqlstate': error.sqlstate,
                  'message': error.diag.message_primary}
        caller.rollback()
    # No COMMIT replay: an independent retained-DB read will prove the outcome.
    after = caller.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    from aos_api.db import get_dsn
    from psycopg.conninfo import conninfo_to_dict
    report = dict(database=conninfo_to_dict(get_dsn())['dbname'], asset=asset,
        identity=identity, finalized_at=finalized_at.isoformat(),
        authentication_deadline=deadline.isoformat(), before_commit=before_commit.isoformat(),
        after_commit=after.isoformat(), source_valid_until=source.valid_until.isoformat(),
        observed_database_times=observations, source_sha256=hashlib.sha256(raw).hexdigest(),
        result=result, execution_allowed=False, semantic_decision_made=False)
    out = Path(__file__).resolve().parent
    with (out / ('observation-' + asset + '.json')).open('x') as handle:
        json.dump(report, handle, indent=2)
    caller.rollback()

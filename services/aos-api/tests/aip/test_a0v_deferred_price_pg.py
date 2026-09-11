"""Real Price Owner lifecycle in disposable PostgreSQL tables with forced RLS."""
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from test_aip_budget_reservation_pg import PG, runtime_connection
from aos_api.aip_model_runtime_contracts import ModelPriceSnapshotRevision
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore, ModelRuntimeDependencyBlocked, ModelRuntimeNotFound,
    canonical_hash, require_current_development_price,
)
from aos_api.tenant_scope import TenantScope

pytestmark = pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='isolated PG opt-in')


def test_deferred_price_owner_replay_withdrawal_and_tenant_isolation():
    schema = 'a0v_price_' + uuid4().hex
    owner = psycopg.connect(**PG, autocommit=True, row_factory=dict_row)
    owner.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    try:
        owner.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        owner.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_runtime').format(sql.Identifier(schema)))
        for name in ('aip_model_price_snapshot_head', 'aip_model_price_snapshot_revision', 'aip_model_runtime_receipt'):
            table = sql.Identifier(name)
            owner.execute(sql.SQL('CREATE TABLE {} (LIKE public.{} INCLUDING ALL)').format(table, table))
            owner.execute(sql.SQL('GRANT SELECT, INSERT, UPDATE ON {} TO aos_runtime').format(table))
            owner.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(table))
            owner.execute(sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(table))
            owner.execute(sql.SQL("CREATE POLICY tenant_scope ON {} TO aos_runtime USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(table))
        connect = runtime_connection(SimpleNamespace(schema=schema))
        store = AipModelRuntimeStore(connect)
        scope = TenantScope('org-org', 'dev-project')
        canary = TenantScope('dev-org', 'dev-project')
        now = datetime.now(UTC)
        authorization = dict(tenant={'orgId': scope.org_id, 'projectId': scope.project_id},
            provider={'assetType': 'ProviderInstanceRevision', 'assetId': 'test-provider', 'revision': 1, 'contentHash': 'b'*64},
            providerModelId='text-test', approvalRef='test-development',
            effectiveFrom=now, effectiveUntil=now+timedelta(hours=1))
        first = None
        for revision, lifecycle in enumerate(('active', 'suspended', 'revoked'), 1):
            item = ModelPriceSnapshotRevision(tenant=authorization['tenant'], priceSnapshotId='test-price',
                revision=revision, contentHash='0'*64, currency='CNY', lifecycle=lifecycle,
                effectiveFrom=now, effectiveUntil=now+timedelta(hours=1), createdBy='test', createdAt=now,
                developmentCostAuthorization=authorization)
            body = item.model_dump(mode='json', by_alias=True)
            item.content_hash = canonical_hash({k: v for k, v in body.items() if k not in store._META_FIELDS})
            saved = store.publish_price_snapshot(scope, 'test', f'price-{revision}', item, expected_version=revision-1)
            assert saved == item
            assert store.publish_price_snapshot(scope, 'test', f'price-{revision}', item, expected_version=revision-1) == saved
            assert saved.input_token_price is None and saved.output_token_price is None
            if first is None:
                first = saved
                require_current_development_price(store, scope, first)
            else:
                assert store.get_price_snapshot(scope, 'test-price', 1) == first
                with pytest.raises(ModelRuntimeDependencyBlocked, match='current'):
                    require_current_development_price(store, scope, first)
        with pytest.raises(ModelRuntimeNotFound):
            store.get_price_snapshot(canary, 'test-price', 1)
        with connect(canary) as conn:
            assert conn.execute('SELECT count(*) AS n FROM aip_model_price_snapshot_revision').fetchone()['n'] == 0
        assert owner.execute('SELECT count(*) AS n FROM aip_model_runtime_receipt').fetchone()['n'] == 3
    finally:
        owner.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        owner.close()

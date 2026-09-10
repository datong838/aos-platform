from datetime import datetime, timezone
from types import SimpleNamespace
from decimal import Decimal

import pytest
from aos_api.ec_ingress_journal import canonical_output_rows, IngressJournalConflict
from aos_api.ec_ot_writer import _normalize_rows, _build_sync_scope, _build_batch_command, prepare_derived_commands
from aos_api.tenant_scope import TenantScope


def prepared():
    tenant = TenantScope('org-org','dev-project')
    pipeline = SimpleNamespace(id='p12')
    row = dict(ot='Payment',source_pk='1',source_updated_at=datetime(2026,9,11,tzinfo=timezone.utc),
               properties={'orderId':'o-1','outTradeNo':'t-1','payStatus':'1','pay_duration_min':5},
               pay_time=600,_order_create_time=300,raw_unneeded='excluded',ssh_password='excluded')
    store = SimpleNamespace(get_checkpoint=lambda _:None,get_latest_authoritative_revision=lambda _:7,get_derived_revision=lambda *a:0)
    sync = _build_sync_scope(tenant,pipeline)
    objects,links = _normalize_rows([row],sync)
    command = _build_batch_command(sync_scope=sync,objects=objects,links=links,pipeline_id=pipeline.id,store=store)
    return tenant,pipeline,row,command,SimpleNamespace(ecom_consistency_store=store)


def test_snapshot_preserves_exact_derived_preparation_and_excludes_raw_columns():
    tenant,pipeline,row,command,eng = prepared()
    saved = canonical_output_rows(command,[row])
    assert saved[0]['pay_time'] == 600 and saved[0]['_order_create_time'] == 300
    assert 'raw_unneeded' not in saved[0] and 'ssh_password' not in saved[0]
    assert isinstance(saved[0]['source_updated_at'],str)
    assert canonical_output_rows(command,saved) == saved
    # Both paths hash the same fixed timestamps and auxiliary inputs.
    before = prepare_derived_commands(eng,tenant,pipeline,[row])
    after = prepare_derived_commands(eng,tenant,pipeline,saved)
    assert before == after
    saved[0]['properties']['pay_duration_min'] = 6
    assert row['properties']['pay_duration_min'] == 5


def test_base_record_drift_rejected():
    _,_,row,command,_ = prepared()
    row['properties']['orderId'] = 'other'
    with pytest.raises(IngressJournalConflict,match='INGRESS_OUTPUT_BASE_DRIFT'):
        canonical_output_rows(command,[row])


@pytest.mark.parametrize('value',[float('nan'),object()])
def test_invalid_auxiliary_values_rejected(value):
    _,_,row,command,_ = prepared()
    row['pay_time'] = value
    with pytest.raises((ValueError,TypeError)):
        canonical_output_rows(command,[row])

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from aos_api.tenant_scope import TenantScope
from aos_api.ecom_core_models import DerivedMetricCommand


def test_prepare_derived_commands_does_not_write_and_freezes_input():
    from aos_api.ec_ot_writer import prepare_derived_commands
    store = SimpleNamespace(get_latest_authoritative_revision=Mock(return_value=7),
        get_derived_revision=Mock(return_value=2),update_derived_metrics=Mock())
    row = {'ot':'CustomerLite','source_pk':'1','source_updated_at':datetime.now(timezone.utc),
           'properties':{'order_count':2,'last_order_days':3}}
    commands = prepare_derived_commands(SimpleNamespace(ecom_consistency_store=store),
        TenantScope('org-org','dev-project'),SimpleNamespace(id='p08'),[row])
    store.update_derived_metrics.assert_not_called()
    assert len(commands)==1
    original = commands[0]
    restored = DerivedMetricCommand.model_validate_json(original.model_dump_json())
    assert restored.request_hash()==original.request_hash()
    assert restored.input_revision==7 and restored.expected_derived_revision==2
    row['properties']['order_count']=99
    assert original.derived_props['order_count']==2


def test_batch_preparation_uses_receipt_watermark_and_checks_scope():
    import pytest
    from test_ec_ingress_input import prepared
    from aos_api.ec_ot_writer import prepare_derived_commands_for_batch
    tenant,pipeline,row,command,eng = prepared()
    store=eng.ecom_consistency_store
    store.read_committed_batch_revision=Mock(return_value=11)
    store.get_latest_authoritative_revision=Mock(side_effect=AssertionError('global watermark must not be read'))
    commands=prepare_derived_commands_for_batch(eng,tenant,pipeline,command,[row])
    assert commands[0].input_revision == 11
    with pytest.raises(ValueError,match='INGRESS_SCOPE_MISMATCH'):
        prepare_derived_commands_for_batch(eng,TenantScope('dev-org','dev-project'),pipeline,command,[row])


def test_real_store_preparation_ignores_later_batch_watermark():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from aos_api.ecom_consistency_store import EcomConsistencyStore, metadata
    from aos_api.ec_ot_writer import prepare_derived_commands_for_batch, _normalize_rows, _build_batch_command
    from test_ec_ingress_input import prepared
    tenant,pipeline,row,command,_ = prepared()
    engine = create_engine('sqlite+pysqlite:///:memory:',poolclass=StaticPool)
    metadata.create_all(engine)
    store = EcomConsistencyStore(engine)
    eng = SimpleNamespace(ecom_consistency_store=store)
    try:
        store.apply_batch(command)
        original = prepare_derived_commands_for_batch(eng,tenant,pipeline,command,[row])
        other = dict(row,source_pk='2')
        objects,links = _normalize_rows([other],command.scope)
        later = _build_batch_command(sync_scope=command.scope,objects=objects,links=links,pipeline_id=pipeline.id,store=store)
        store.apply_batch(later)
        assert store.get_latest_authoritative_revision(original[0].identity) > original[0].input_revision
        assert prepare_derived_commands_for_batch(eng,tenant,pipeline,command,[row]) == original
        assert store.update_derived_metrics(original[0]).updated
        assert store.update_derived_metrics(original[0]).replayed
    finally:
        engine.dispose()

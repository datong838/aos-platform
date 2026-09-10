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

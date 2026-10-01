"""Original configuration provenance in disposable PG; no Provider invocation."""
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_provider_plugin_authority import ProviderPluginAuthority
from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore
from aos_api.db import connect
from tests.aip.test_budget_cost_issuer_pg import prepared
from tests.aip.test_network_consumer_boundary_pg import SCOPE


def test_budget_provider_has_original_publish_receipt_and_exact_dependencies():
    maker, _, _, proposal, _ = prepared()
    provider = AipModelRuntimeStore().get_provider(SCOPE, proposal.basis.provider.asset_id, 1)
    with connect(SCOPE) as conn:
        rows = conn.execute(
            "SELECT result_ref,created_by FROM aip_model_runtime_receipt "
            "WHERE operation='provider_instance.publish' AND result_ref->>'resourceId'=%s",
            (provider.provider_instance_id,),
        ).fetchall()
    assert len(rows) == 1, 'Provider must come from original publication, not direct INSERT'
    assert rows[0]['created_by'] == maker.subject
    assert rows[0]['result_ref']['contentHash'] == provider.content_hash
    ProviderPluginAuthority().validate_ref(SCOPE, provider.plugin_ref)
    store = AipRuntimeGuardPolicyStore()
    for ref, read in ((provider.egress_policy_ref, store.get_egress),
                      (provider.data_classification_policy_ref, store.get_data_classification)):
        item = read(SCOPE, ref.asset_id, ref.revision)
        assert item.revision == 2 and item.lifecycle.value == 'active'
        assert item.content_hash == ref.content_hash

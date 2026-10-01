"""Real derived price into the content Owner amount gate, not a full Host proof."""
import pytest

from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.db import connect_serializable
from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner
from aos_api.ecommerce_growth_host_ports import HostTransaction
from tests.aip.test_budget_configuration_runtime_pg import configured_pair, withdraw
from tests.aip.test_budget_cost_consumer_pg import caller
from tests.aip.test_budget_cost_issuer_pg import issuer_factory, command
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE


def inputs(pair, conn):
    _, p, _, _, _, budget, price_ref = pair
    price = AipModelRuntimeStore().get_price_snapshot(SCOPE, price_ref.resource_id, price_ref.revision)
    provider = p.basis.provider
    return price, p.basis.per_request_risk_minor, dict(
        transaction=HostTransaction(conn), scope=SCOPE, policy_ref=budget, pricing_ref=price_ref,
        provider_ref=BudgetExactRef(resource_type=provider.asset_type, resource_id=provider.asset_id,
            revision=provider.revision, content_hash="sha256:" + provider.content_hash),
        provider_model_id=p.basis.provider_model_id, max_input_tokens=4000, max_output_tokens=2000)


def test_approved_risk_amount_passes_without_claiming_numeric_price_or_hold(configured_pair):
    with connect_serializable(SCOPE) as conn:
        price, amount, options = inputs(configured_pair, conn)
        before = conn.execute("SELECT count(*) AS n FROM aip_budget_reservation WHERE org_id=%s AND project_id=%s", SCOPE.key).fetchone()
        assert price.input_token_price is None and price.output_token_price is None
        assert ContentBudgetCommandOwner._approved_bound(price, amount, **options) == amount
        assert conn.execute("SELECT count(*) AS n FROM aip_budget_reservation WHERE org_id=%s AND project_id=%s", SCOPE.key).fetchone() == before


@pytest.mark.parametrize("drift", ["amount", "provider", "model", "price", "unconsumed", "tokens", "bool", "context"])
def test_risk_amount_requires_exact_current_context(configured_pair, drift):
    with connect_serializable(SCOPE) as conn:
        price, amount, options = inputs(configured_pair, conn)
        if drift == "amount": amount += 1
        elif drift == "provider": options["provider_ref"] = options["provider_ref"].model_copy(update={"resource_id": "other-provider"})
        elif drift == "model": options["provider_model_id"] = "other-model"
        elif drift == "price": price = price.model_copy(update={"token_unit": price.token_unit + 1})
        elif drift == "unconsumed": options["policy_ref"] = options["policy_ref"].model_copy(update={"resource_id": "no-cost-receipt"})
        elif drift == "tokens": options["max_output_tokens"] = 0
        elif drift == "bool": options["max_input_tokens"] = True
        elif drift == "context": options.pop("transaction")
        with pytest.raises(ValueError):
            ContentBudgetCommandOwner._approved_bound(price, amount, **options)


@pytest.mark.parametrize("drift", ["withdraw", "revoke"])
def test_current_withdrawal_or_revocation_blocks_owner(configured_pair, issuer_factory, https_signer, drift):
    if drift == "withdraw": withdraw(configured_pair)
    else:
        maker, _, saved, _, _, _, _ = configured_pair
        BudgetCostIssuer(issuer_factory).execute(command(https_signer[0], maker, saved,
            operation="revoke", decision=None, reason="withdraw cost allowance"))
    with connect_serializable(SCOPE) as conn:
        price, amount, options = inputs(configured_pair, conn)
        with pytest.raises(ValueError):
            ContentBudgetCommandOwner._approved_bound(price, amount, **options)


def test_stale_transaction_cannot_use_withdrawn_risk_price(configured_pair):
    with connect_serializable(SCOPE) as conn:
        price, amount, options = inputs(configured_pair, conn)
        conn.execute("SELECT current_revision FROM aip_model_price_snapshot_head WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s",
            (*SCOPE.key, price.price_snapshot_id)).fetchone()
        withdraw(configured_pair)
        with pytest.raises(ValueError):
            ContentBudgetCommandOwner._approved_bound(price, amount, **options)

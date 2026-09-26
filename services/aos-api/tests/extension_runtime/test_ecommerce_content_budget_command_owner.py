"""Budget command Owner never substitutes a guessed amount or retries unknown Host commits."""

from types import SimpleNamespace

import pytest


def test_pricing_bound_uses_exact_token_unit_and_requires_approved_cover():
    from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner

    price = SimpleNamespace(input_token_price=0.5, output_token_price=1.0,
                            token_unit=1000, development_cost_authorization=None)
    assert ContentBudgetCommandOwner._minimum_bound_fen(
        price, max_input_tokens=4000, max_output_tokens=2000) == 400
    assert ContentBudgetCommandOwner._approved_bound(
        price, 500, max_input_tokens=4000, max_output_tokens=2000) == 500
    with pytest.raises(ValueError, match="approved upper bound"):
        ContentBudgetCommandOwner._approved_bound(
            price, 399, max_input_tokens=4000, max_output_tokens=2000)
    with pytest.raises(ValueError, match="price"):
        ContentBudgetCommandOwner._minimum_bound_fen(
            SimpleNamespace(input_token_price=None, output_token_price=1.0,
                            token_unit=1000, development_cost_authorization=None),
            max_input_tokens=4000, max_output_tokens=2000)

"""Fail-closed helpers for an exact, approved content budget command."""

from __future__ import annotations

from typing import Any

from aos_api.aip_budget_reservation_contracts import usage_cost_minor


class ContentBudgetCommandOwner:
    """No budget command may infer an approval or silently price an unknown model."""

    @staticmethod
    def _minimum_bound_fen(
        price: Any, *, max_input_tokens: int, max_output_tokens: int
    ) -> int:
        if (
            price.development_cost_authorization is not None
            or price.input_token_price is None
            or price.output_token_price is None
            or type(price.token_unit) is not int
            or price.token_unit <= 0
            or type(max_input_tokens) is not int
            or max_input_tokens <= 0
            or type(max_output_tokens) is not int
            or max_output_tokens <= 0
        ):
            raise ValueError("exact numeric price and positive token limits required")
        return usage_cost_minor(
            quantity=max_input_tokens,
            unit_price_cny=str(price.input_token_price),
            price_unit=price.token_unit,
        ) + usage_cost_minor(
            quantity=max_output_tokens,
            unit_price_cny=str(price.output_token_price),
            price_unit=price.token_unit,
        )

    @classmethod
    def _approved_bound(
        cls, price: Any, approved_fen: int, *, max_input_tokens: int, max_output_tokens: int
    ) -> int:
        minimum = cls._minimum_bound_fen(
            price, max_input_tokens=max_input_tokens, max_output_tokens=max_output_tokens
        )
        if type(approved_fen) is not int or approved_fen <= 0 or approved_fen < minimum:
            raise ValueError("approved upper bound does not cover maximum priced usage")
        return approved_fen

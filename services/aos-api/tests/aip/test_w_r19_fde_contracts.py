from __future__ import annotations

import pytest
from pydantic import ValidationError

from aos_api.aip_fde_contracts import FdeIntakeRequest


def _payload() -> dict[str, object]:
    return {
        "requirement": "接入微商城订单与商品，只生成 S1-S3 计划",
        "platform": "niushop",
        "dataTypes": ["orders", "products"],
        "syncFrequency": "hourly",
        "merchantRef": "merchant://qyh/default",
        "secretRef": "keychain://aos/agnes-api-key",
        "secretVersion": "1",
    }


def test_intake_accepts_only_normalized_opaque_secret_reference() -> None:
    intake = FdeIntakeRequest.model_validate(_payload())

    assert intake.platform == "niushop"
    assert intake.data_types == ["orders", "products"]
    assert intake.secret_ref == "keychain://aos/agnes-api-key"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("secretRef", "plaintext-key", "secretRef must use"),
        ("requirement", "api_key=abcd1234", "secret payload is forbidden"),
        ("dataTypes", ["Orders"], "normalized lowercase"),
        ("dataTypes", ["orders", "orders"], "must be unique"),
    ],
)
def test_intake_fails_closed_for_secret_or_identifier_drift(
    field: str,
    value: object,
    message: str,
) -> None:
    payload = _payload()
    payload[field] = value

    with pytest.raises(ValidationError, match=message):
        FdeIntakeRequest.model_validate(payload)

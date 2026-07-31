"""228-EC frozen platform-neutral public contracts."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aos_api.public_contracts import (
    ContractViolation,
    EC_CAPABILITY_IDS,
    EC_INDEPENDENT_PLATFORM_COUNT,
    EC_PLANNED_ENTRY_COUNT,
    EC_SCHEME_DIRECTORY_COUNT,
    ExchangeRate,
    ExternalIdentityKey,
    ForwardEnumValue,
    Money,
    MoneyBag,
    StableCursor,
    TaskStatus,
    TERMINAL_TASK_STATUSES,
    ZonedInstant,
    normalize_task_status,
    redact_sensitive,
    transition_task_status,
)


def test_task_status_full_main_path_and_legacy_value() -> None:
    assert normalize_task_status("created") is TaskStatus.PENDING
    status = TaskStatus.PENDING
    for target in (
        TaskStatus.PLANNING,
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.APPROVED,
        TaskStatus.EXECUTING,
        TaskStatus.COMPLETED,
        TaskStatus.ROLLED_BACK,
    ):
        status = transition_task_status(status, target)
    assert status in TERMINAL_TASK_STATUSES
    assert transition_task_status(status, status) is status


def test_capability_ids_and_platform_counts_are_unambiguous() -> None:
    assert len(EC_CAPABILITY_IDS) == 8
    assert all(value.startswith("ec.") and not value.startswith("G") for value in EC_CAPABILITY_IDS)
    assert (EC_INDEPENDENT_PLATFORM_COUNT, EC_SCHEME_DIRECTORY_COUNT, EC_PLANNED_ENTRY_COUNT) == (7, 8, 9)


def test_task_status_pause_resume_cancel_and_invalid_transition() -> None:
    assert transition_task_status(TaskStatus.EXECUTING, "paused") is TaskStatus.PAUSED
    assert transition_task_status(TaskStatus.PAUSED, "executing") is TaskStatus.EXECUTING
    assert transition_task_status(TaskStatus.APPROVED, "cancelled") is TaskStatus.CANCELLED
    with pytest.raises(ContractViolation) as exc:
        transition_task_status(TaskStatus.COMPLETED, TaskStatus.EXECUTING)
    assert exc.value.code == "TASK_STATUS_CONFLICT"


def test_external_identity_keeps_org_scope_and_normalizes_platform_only() -> None:
    first = ExternalIdentityKey(
        org_id="org-a", workspace_id="same", platform=" Shopify ",
        shop_or_marketplace_id=" Shop-X ", external_id=" AbC ",
    )
    second = first.model_copy(update={"org_id": "org-b"})
    assert first.platform == "shopify"
    assert first.external_id == "AbC"
    assert first.public_key() == second.public_key()
    assert first.scoped_key() != second.scoped_key()
    with pytest.raises(ValidationError):
        ExternalIdentityKey(org_id="", workspace_id="w", platform="p", shop_or_marketplace_id="s", external_id="e")


def test_money_decimal_scales_rounding_and_bag() -> None:
    cny = Money(amount="0.105", currency="cny")
    usd = Money(amount=Decimal("1.235"), currency="USD")
    jpy = Money(amount="100.5", currency="JPY")
    assert cny.model_dump(mode="json")["amount"] == "0.10"
    assert usd.model_dump(mode="json")["amount"] == "1.24"
    assert jpy.model_dump(mode="json")["amount"] == "100"
    total = Money(amount="0.10", currency="CNY") + Money(amount="0.20", currency="CNY")
    assert total.amount == Decimal("0.30")
    bag = MoneyBag().add(total).add(Money(amount="2", currency="USD"))
    assert set(bag.amounts) == {"CNY", "USD"}
    with pytest.raises(ContractViolation):
        _ = total + Money(amount="1", currency="USD")
    with pytest.raises(ValidationError):
        Money(amount=0.1, currency="CNY")
    with pytest.raises(ValidationError):
        Money(amount="1", currency="ZZZ")


def test_exchange_rate_requires_provenance_time_and_decimal() -> None:
    rate = ExchangeRate(
        source_currency="CNY", target_currency="JPY", rate="20.5",
        source="central-bank", as_of="2026-01-01T00:00:00Z",
    )
    converted = rate.convert(Money(amount="10.00", currency="CNY"))
    assert converted.model_dump(mode="json")["amount"] == "205"
    with pytest.raises(ValidationError):
        ExchangeRate(
            source_currency="CNY", target_currency="USD", rate=0.14,
            source="", as_of="2026-01-01T00:00:00",
        )


def test_time_requires_zone_preserves_offset_and_cursor_tie_breaks() -> None:
    before = ZonedInstant.parse("2026-03-08T01:30:00-05:00")
    after = ZonedInstant.parse("2026-03-08T03:30:00-04:00")
    assert before.source_timezone == "-0500"
    assert after.source_timezone == "-0400"
    assert before.utc < after.utc
    with pytest.raises(ContractViolation):
        ZonedInstant.parse("2026-03-08T01:30:00")
    instant = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = StableCursor(source_updated_at_utc=instant, external_id="a")
    b = StableCursor(source_updated_at_utc=instant, external_id="b")
    assert a.sort_key() < b.sort_key()
    assert a.encode() == '["2026-01-01T00:00:00.000000Z","a"]'
    assert StableCursor.decode(a.encode()) == a


def test_forward_enum_preserves_unknown_raw_value() -> None:
    known = ForwardEnumValue.from_raw("PAID", {"PAID": "paid"})
    unknown = ForwardEnumValue.from_raw("NEW_PLATFORM_VALUE", {"PAID": "paid"})
    assert (known.canonical_value, known.unknown) == ("paid", False)
    assert (unknown.canonical_value, unknown.raw_status, unknown.unknown) == (
        "unknown", "NEW_PLATFORM_VALUE", True,
    )


def test_recursive_redaction_covers_nested_credentials_and_pii() -> None:
    safe = redact_sensitive({
        "authorization": "Bearer top-secret",
        "nested": [{"password": "pw"}, "mail user@example.com phone 13800138000 sk-123456789"],
    })
    rendered = str(safe)
    assert "top-secret" not in rendered
    assert "user@example.com" not in rendered
    assert "13800138000" not in rendered
    assert "sk-123456789" not in rendered

import pytest
from pydantic import ValidationError

from aos_api.extension_runtime.contracts import RegistrationDescription
from aos_api.extension_runtime.registration import validate_registration


def description(*items):
    return RegistrationDescription.model_validate({"contributions": list(items)})


CLAIM = {"kind": "ui", "slot": "main", "id": "example", "mode": "exclusive"}


def test_registration_returns_no_readiness_or_binding():
    assert validate_registration(description(CLAIM), description(CLAIM)) is None


@pytest.mark.parametrize("items", [[], [CLAIM, CLAIM], [{**CLAIM, "mode": "shared"}], [{**CLAIM, "id": "other"}]])
def test_registration_rejects_missing_duplicate_extra_or_drift(items):
    with pytest.raises(ValueError):
        validate_registration(description(CLAIM), description(*items))


def test_duplicate_declaration_is_rejected_even_if_observation_matches():
    with pytest.raises(ValueError):
        validate_registration(description(CLAIM, CLAIM), description(CLAIM, CLAIM))


def test_callable_is_never_executed():
    called = []
    def register():
        called.append(True)
    with pytest.raises(ValidationError):
        description(register)
    assert called == []


def test_registration_bound():
    with pytest.raises(ValidationError):
        description(*[CLAIM] * 257)

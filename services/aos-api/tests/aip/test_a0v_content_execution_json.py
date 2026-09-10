from datetime import UTC, datetime
import json
import pytest
from aos_api.ecommerce_content_execution_journal import _payload


def test_aware_timestamp_normalizes_to_stable_json_hash():
    text,digest=_payload({'time':datetime(2026,9,11,tzinfo=UTC)})
    assert json.loads(text)=={'time':'2026-09-11T00:00:00+00:00'}
    assert _payload(json.loads(text))==(text,digest)


@pytest.mark.parametrize('value',[datetime(2026,9,11),object(),float('nan')])
def test_no_silent_stringification_of_unknown_or_invalid_values(value):
    with pytest.raises((TypeError,ValueError)):
        _payload({'value':value})

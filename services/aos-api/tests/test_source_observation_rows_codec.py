from datetime import datetime, timezone
from decimal import Decimal

import pytest

from aos_api.source_observation_rows_codec import encode_observed_rows,decode_observed_rows
from aos_api.source_read_observation import observed_rows_hash


def test_roundtrip_preserves_original_typed_hash():
    rows=[dict(number=Decimal('12.00'),floating=0.1,integer=2,flag=True,missing=None,text='商品',time=datetime.now(timezone.utc),nested={'a':[1,'2',False]})]
    encoded=encode_observed_rows(rows)
    decoded=decode_observed_rows(encoded)
    assert observed_rows_hash(decoded)==observed_rows_hash(rows)
    assert isinstance(decoded[0]['number'],Decimal) and str(decoded[0]['number'])=='12.00'
    assert type(decoded[0]['integer']) is int and type(decoded[0]['flag']) is bool


@pytest.mark.parametrize('encoded',[
    ['list',[['dict',[['a',['int',True]]]]]],
    ['list',[['dict',[['a',['float','nan']]]]]],
    ['list',[['dict',[['a',['decimal','NaN']]]]]],
    ['list',[['dict',[['a',['datetime','2026-01-01T00:00:00']]]]]],
    ['list',[['dict',[['a',['int',1]],['a',['int',2]]]]]],
    ['list',[['dict',[['z',['int',1]],['a',['int',2]]]]]],
    ['list',[['dict',[['a',['str',2]]]]]],
    ['list',[['dict',[['a',['unknown','x']]]]]],
    ['list',[['dict',[['a',['float','0.1']]]]]],
    ['dict',[]],
])
def test_noncanonical_or_invalid_encoding_is_rejected(encoded):
    with pytest.raises(ValueError): decode_observed_rows(encoded)


@pytest.mark.parametrize('value',[float('nan'),float('inf'),Decimal('Infinity'),b'bytes'])
def test_unsupported_values_are_not_coerced(value):
    with pytest.raises(ValueError): encode_observed_rows([{'value':value}])


def test_size_depth_and_limit_types_fail_closed():
    with pytest.raises(ValueError): encode_observed_rows([{'text':'长'*100}],max_bytes=20)
    with pytest.raises(ValueError): decode_observed_rows(encode_observed_rows([{'text':'长'*100}]),max_bytes=20)
    with pytest.raises(ValueError): encode_observed_rows([],max_bytes=True)
    nested=0
    for _ in range(40): nested=[nested]
    with pytest.raises(ValueError): encode_observed_rows([{'nested':nested}])

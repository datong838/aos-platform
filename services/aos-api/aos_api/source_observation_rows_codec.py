"""Bounded inverse of the existing observation type encoding, without coercion."""
from datetime import datetime
from decimal import Decimal,InvalidOperation
import json

from aos_api.source_read_observation import _typed,observed_rows_hash


def _size(value,max_bytes):
    if type(max_bytes) is not int or not 1<=max_bytes<=2_000_000:
        raise ValueError('explicit bounded observation size required')
    if len(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8'))>max_bytes:
        raise ValueError('complete observation encoding exceeds limit')


def _depth(value,depth=0):
    if depth>32: raise ValueError('observation nesting exceeds limit')
    if isinstance(value,dict):
        for item in value.values(): _depth(item,depth+1)
    elif isinstance(value,(list,tuple)):
        for item in value: _depth(item,depth+1)


def encode_observed_rows(rows,*,max_bytes=2_000_000):
    try:
        _depth(rows)
        observed_rows_hash(rows)
        encoded=_typed(rows)
        _size(encoded,max_bytes)
        return encoded
    except (ValueError,TypeError,RecursionError,OverflowError,InvalidOperation):
        raise ValueError('observation rows encoding invalid or exceeds limit') from None


def _decode(value,depth=0):
    if depth>32 or type(value) is not list or not value or type(value[0]) is not str:
        raise ValueError('invalid observation type encoding')
    tag=value[0]
    if tag=='null' and len(value)==1: return None
    if len(value)!=2: raise ValueError('invalid observation value encoding')
    raw=value[1]
    expected={'str':str,'int':int,'bool':bool}
    if tag in expected:
        if type(raw) is not expected[tag]: raise ValueError('incorrect observation scalar type')
        return raw
    if tag in {'float','decimal','datetime'}:
        if type(raw) is not str: raise ValueError('typed observation string required')
        if tag=='float': return float.fromhex(raw)
        if tag=='decimal': return Decimal(raw)
        return datetime.fromisoformat(raw)
    if type(raw) is not list: raise ValueError('observation container required')
    if tag=='list': return [_decode(item,depth+1) for item in raw]
    if tag=='dict':
        result={}
        for pair in raw:
            if type(pair) is not list or len(pair)!=2 or type(pair[0]) is not str or pair[0] in result:
                raise ValueError('unique observation keys required')
            result[pair[0]]=_decode(pair[1],depth+1)
        return result
    raise ValueError('unsupported observation type')


def decode_observed_rows(encoded,*,max_bytes=2_000_000):
    try:
        _size(encoded,max_bytes)
        rows=_decode(encoded)
        observed_rows_hash(rows)
        if _typed(rows)!=encoded: raise ValueError('noncanonical observation encoding')
        return rows
    except (ValueError,TypeError,RecursionError,OverflowError,InvalidOperation):
        raise ValueError('observation rows encoding invalid or exceeds limit') from None

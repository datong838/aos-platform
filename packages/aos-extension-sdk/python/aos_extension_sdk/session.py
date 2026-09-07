"""Container-only persistent protocol. Business ports remain closed."""
import json
import math
import re
import struct
import sys

from .client import RegistrationContext, _pairs

_FIELDS = {"schemaVersion", "type", "method", "requestId", "parentRequestId", "payload", "sequence"}
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}")
_OPERATION_ID = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,159}")


def _value(value, depth=0):
    if depth > 64:
        raise ValueError("JSON depth exceeded")
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise ValueError("invalid JSON key")
            _value(child, depth+1)
    elif type(value) is list:
        for child in value:
            _value(child, depth+1)
    elif type(value) is float:
        if not math.isfinite(value):
            raise ValueError("nonfinite number")
    elif value is not None and type(value) not in (str, int, bool):
        raise ValueError("invalid JSON value")


def _read(source):
    header = source.read(4)
    if header == b"":
        return None
    if len(header) != 4:
        raise ValueError("truncated header")
    size = struct.unpack(">I", header)[0]
    if not 0 < size <= 1048576:
        raise ValueError("frame limit exceeded")
    raw = source.read(size)
    if len(raw) != size:
        raise ValueError("truncated frame")
    message = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    _value(message)
    if type(message) is not dict or set(message) != _FIELDS:
        raise ValueError("invalid frame fields")
    if (type(message["schemaVersion"]) is not int or message["schemaVersion"] != 1
            or type(message["sequence"]) is not int or not 0 <= message["sequence"] <= 2**53-1
            or message["parentRequestId"] is not None or type(message["payload"]) is not dict
            or any(type(message[k]) is not str or not _ID.fullmatch(message[k]) for k in ("requestId", "method"))):
        raise ValueError("invalid request envelope")
    return message


def serve_session(register, handle, *, source=None, target=None):
    source = source if source is not None else sys.stdin.buffer
    target = target if target is not None else sys.stdout.buffer
    methods, seen = set(), set()
    context = RegistrationContext()
    for sequence in range(1024):
        message = _read(source)
        if message is None:
            if sequence == 0:
                raise ValueError("registration required")
            return
        if message["sequence"] != sequence or message["requestId"] in seen:
            raise ValueError("replayed or out-of-order request")
        seen.add(message["requestId"])
        if sequence == 0:
            if message["type"] != "register" or message["method"] != "register" or message["payload"] != {}:
                raise ValueError("registration required first")
            result = register(context)
            if (type(result) is not dict or set(result) != {"contributions"}
                    or type(result["contributions"]) is not list or len(result["contributions"]) > 256):
                raise ValueError("invalid registration")
            for claim in result["contributions"]:
                if type(claim) is not dict:
                    raise ValueError("invalid contribution")
                if claim.get("kind") == "api":
                    method = claim.get("operationId")
                    if type(method) is not str or not _OPERATION_ID.fullmatch(method) or method in methods:
                        raise ValueError("invalid API operation")
                    methods.add(method)
        elif message['type'] == 'heartbeat':
            nonce = message['payload'].get('nonce')
            if (message['method'] != 'heartbeat' or set(message['payload']) != {'nonce'}
                    or type(nonce) is not str or not re.fullmatch(r'[0-9a-f]{32}', nonce)):
                raise ValueError('invalid heartbeat')
            result = {'nonce': nonce, 'protocol': 'aos-extension/1', 'status': 'alive'}
        else:
            if message["type"] != "invoke" or message["method"] not in methods:
                raise ValueError("unregistered invocation")
            result = handle(message["method"], message["payload"], context)
            if type(result) is not dict:
                raise ValueError("handler result must be an object")
        response = {**message, "type": "result", "payload": result}
        _value(response)
        raw = json.dumps(response, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(raw) > 1048576:
            raise ValueError("response limit exceeded")
        target.write(struct.pack(">I", len(raw))+raw)
        target.flush()
    raise ValueError("session request budget exhausted")

"""Bounded, strict length-prefixed JSON protocol, independent of domain code."""
from __future__ import annotations

import json
import math
import re
import struct

MAX_FRAME_BYTES = 1024 * 1024
_FIELDS = {"schemaVersion", "type", "requestId", "parentRequestId", "method", "payload", "sequence"}
_TYPES = {"register", "result", "invoke", "port_request", "port_result", "cancel", "heartbeat"}
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}")


class ProtocolError(ValueError):
    """Invalid protocol input; callers must close the owning runtime stream."""


def _json_value(value, depth=0):
    if depth > 64:
        raise ProtocolError("JSON nesting limit exceeded")
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ProtocolError("invalid JSON key")
            _json_value(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _json_value(item, depth + 1)
    elif type(value) is float:
        if not math.isfinite(value):
            raise ProtocolError("nonfinite JSON number")
    elif value is not None and type(value) not in (str, int, bool):
        raise ProtocolError("unsupported JSON value")


def _validate(message):
    if type(message) is not dict or set(message) != _FIELDS:
        raise ProtocolError("invalid frame fields")
    if type(message["schemaVersion"]) is not int or message["schemaVersion"] != 1:
        raise ProtocolError("unsupported schema")
    if type(message["type"]) is not str or message["type"] not in _TYPES:
        raise ProtocolError("unknown frame type")
    for key in ("requestId", "method", "parentRequestId"):
        value = message[key]
        if key == "parentRequestId" and value is None:
            continue
        if type(value) is not str or not _IDENTIFIER.fullmatch(value):
            raise ProtocolError("invalid protocol identifier")
    if type(message["sequence"]) is not int or not 0 <= message["sequence"] <= 2**53 - 1:
        raise ProtocolError("invalid sequence")
    if type(message["payload"]) is not dict:
        raise ProtocolError("payload must be an object")
    _json_value(message)
    return message


def encode_frame(message: dict) -> bytes:
    try:
        body = json.dumps(_validate(message), ensure_ascii=False, allow_nan=False,
                          sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (UnicodeError, RecursionError, OverflowError) as exc:
        raise ProtocolError("unencodable frame") from exc
    if not 0 < len(body) <= MAX_FRAME_BYTES:
        raise ProtocolError("frame length exceeded")
    return struct.pack(">I", len(body)) + body


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate JSON key")
        result[key] = value
    return result


def _constant(_):
    raise ProtocolError("nonfinite JSON number")


class FrameSession:
    """One bounded incoming stream; authorization belongs to the broker."""

    def __init__(self, *, allowed_methods: set[str]):
        self._methods = frozenset(allowed_methods)
        self._buffer = bytearray()
        self._next = 0
        self._closed = False

    def feed(self, chunk: bytes) -> list[dict]:
        if self._closed:
            raise ProtocolError("stream is closed")
        try:
            # The pipe reader must deliver bounded chunks. Never buffer arbitrary output.
            if type(chunk) is not bytes or len(chunk) > MAX_FRAME_BYTES + 4:
                raise ProtocolError("unbounded input chunk")
            if len(self._buffer) + len(chunk) > 2 * (MAX_FRAME_BYTES + 4):
                raise ProtocolError("buffer limit exceeded")
            self._buffer.extend(chunk)
            result = []
            while len(self._buffer) >= 4:
                size = struct.unpack(">I", self._buffer[:4])[0]
                if not 0 < size <= MAX_FRAME_BYTES:
                    raise ProtocolError("invalid frame length")
                if len(self._buffer) < size + 4:
                    break
                body = bytes(self._buffer[4:4 + size])
                del self._buffer[:4 + size]
                message = _validate(json.loads(body.decode("utf-8"), object_pairs_hook=_pairs,
                                               parse_constant=_constant))
                if message["method"] not in self._methods or message["sequence"] != self._next:
                    raise ProtocolError("unapproved method or out-of-order frame")
                self._next += 1
                result.append(message)
            return result
        except (ValueError, TypeError, RecursionError, OverflowError) as exc:
            self._closed = True
            self._buffer.clear()
            raise ProtocolError("invalid runtime stream") from exc

    def finish(self) -> None:
        if self._closed or self._buffer:
            self._closed = True
            self._buffer.clear()
            raise ProtocolError("truncated or invalid stream")
        self._closed = True

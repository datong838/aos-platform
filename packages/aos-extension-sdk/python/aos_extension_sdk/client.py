"""Container-side registration protocol; stdlib only, no platform imports."""
import json
import struct
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class RegistrationContext:
    def request(self, method, payload):
        raise PermissionError("registration phase has no business ports")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def serve_registration(register, *, source=None, target=None):
    source = source if source is not None else sys.stdin.buffer
    target = target if target is not None else sys.stdout.buffer
    header = source.read(4)
    if len(header) != 4:
        raise ValueError("truncated frame")
    size = struct.unpack(">I", header)[0]
    if not 0 < size <= 1048576:
        raise ValueError("invalid frame size")
    body = source.read(size)
    if len(body) != size:
        raise ValueError("truncated frame")
    frame = json.loads(body.decode("utf-8"), object_pairs_hook=_pairs)
    if type(frame) is not dict or set(frame) != {"schemaVersion", "type", "method", "requestId", "parentRequestId", "payload", "sequence"}:
        raise ValueError("invalid request")
    if (type(frame["schemaVersion"]) is not int or frame["schemaVersion"] != 1
            or type(frame["sequence"]) is not int or frame["sequence"] != 0
            or frame["type"] != "register" or frame["method"] != "register"
            or frame["parentRequestId"] is not None or frame["payload"] != {}
            or type(frame["requestId"]) is not str or not 0 < len(frame["requestId"]) <= 160):
        raise ValueError("not a registration request")
    description = register(RegistrationContext())
    if type(description) is not dict or set(description) != {"contributions"} or type(description["contributions"]) is not list or len(description["contributions"]) > 256:
        raise ValueError("invalid registration description")
    frame["type"] = "result"
    frame["payload"] = description
    output = json.dumps(frame, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(output) > 1048576:
        raise ValueError("registration description exceeds limit")
    target.write(struct.pack(">I", len(output)) + output)
    target.flush()

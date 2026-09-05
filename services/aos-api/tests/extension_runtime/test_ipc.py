import json
import struct

import pytest

from aos_api.extension_runtime.ipc import FrameSession, ProtocolError, encode_frame


def message(**changes):
    return {"schemaVersion": 1, "type": "register", "requestId": "r1",
            "parentRequestId": None, "method": "register", "payload": {}, "sequence": 0,
            **changes}


def raw(data):
    return struct.pack(">I", len(data)) + data


def test_roundtrip_and_fragmentation():
    session = FrameSession(allowed_methods={"register"})
    frame = encode_frame(message())
    assert session.feed(frame[:3]) == []
    assert session.feed(frame[3:7]) == []
    assert session.feed(frame[7:]) == [message()]
    assert session.feed(encode_frame(message(sequence=1))) == [message(sequence=1)]
    session.finish()


@pytest.mark.parametrize("data", [
    raw(b'{"schemaVersion":1,"schemaVersion":1}'), raw(b'{"x":NaN}'),
    raw(b'[]'), raw(b'\xff'), struct.pack('>I', 1048577), raw(b''),
    raw(json.dumps(message(schemaVersion=True)).encode()),
    raw(json.dumps(message(sequence=True)).encode()),
    raw(json.dumps(message(type="unknown")).encode()),
    raw(json.dumps(message(method="http://x")).encode()),
    raw(json.dumps(message(tenant="org-org")).encode()),
    raw(json.dumps(message(payload=[])).encode()),
    raw(json.dumps(message(requestId="")).encode()),
])
def test_bad_frame_closes_stream(data):
    session = FrameSession(allowed_methods={"register"})
    with pytest.raises(ProtocolError):
        session.feed(data)
    with pytest.raises(ProtocolError):
        session.feed(encode_frame(message()))


def test_repeat_sequence_and_unapproved_method_rejected():
    session = FrameSession(allowed_methods={"register"})
    session.feed(encode_frame(message()))
    with pytest.raises(ProtocolError):
        session.feed(encode_frame(message()))
    with pytest.raises(ProtocolError):
        FrameSession(allowed_methods={"register"}).feed(encode_frame(message(method="authority.read")))


def test_truncation_rejected():
    session = FrameSession(allowed_methods={"register"})
    session.feed(encode_frame(message())[:-1])
    with pytest.raises(ProtocolError):
        session.finish()


def test_nested_payload_bound():
    value = {}
    for _ in range(66):
        value = {"nested": value}
    with pytest.raises(ProtocolError):
        encode_frame(message(payload=value))
    with pytest.raises(ProtocolError):
        FrameSession(allowed_methods={"register"}).feed(raw(json.dumps(message(payload=value)).encode()))


def test_maximum_frame_and_consecutive_frames():
    base = message(payload={"text": ""})
    base["payload"]["text"] = "a" * (1048576 - (len(encode_frame(base)) - 4))
    frame = encode_frame(base)
    assert len(frame) == 1048580
    assert FrameSession(allowed_methods={"register"}).feed(frame) == [base]
    base["payload"]["text"] += "a"
    with pytest.raises(ProtocolError):
        encode_frame(base)
    session = FrameSession(allowed_methods={"register"})
    assert len(session.feed(encode_frame(message()) + encode_frame(message(sequence=1)))) == 2
    session.finish()
    with pytest.raises(ProtocolError):
        session.feed(b"")

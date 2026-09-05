import importlib.util
import io
from pathlib import Path
import sys

from aos_api.extension_runtime.ipc import FrameSession, encode_frame


def test_sdk_host_protocol_and_no_ports():
    path = Path(__file__).resolve().parents[4] / "packages/aos-extension-sdk/python/aos_extension_sdk/client.py"
    spec = importlib.util.spec_from_file_location("aos_sdk_registration_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    frame = {"schemaVersion": 1, "type": "register", "method": "register", "requestId": "test",
             "parentRequestId": None, "payload": {}, "sequence": 0}
    target = io.BytesIO()
    def register(ctx):
        try:
            ctx.request("authority.read", {})
        except PermissionError:
            return {"contributions": []}
        raise AssertionError("ports must be unavailable")
    module.serve_registration(register, source=io.BytesIO(encode_frame(frame)), target=target)
    expected = {**frame, "type": "result", "payload": {"contributions": []}}
    assert target.getvalue() == encode_frame(expected)
    assert FrameSession(allowed_methods={"register"}).feed(target.getvalue()) == [expected]

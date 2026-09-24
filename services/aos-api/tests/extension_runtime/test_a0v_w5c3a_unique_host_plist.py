import plistlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PLIST = ROOT / "deploy/dev/com.aos.a0v-w5c3-runtime-host.plist"


def test_w5c3a_host_is_single_instance_not_auto_restarted():
    value = plistlib.loads(PLIST.read_bytes())
    assert value["Label"] == "com.aos.a0v-w5c3-runtime-host"
    assert value["RunAtLoad"] is True
    assert value["KeepAlive"] is False
    args = value["ProgramArguments"]
    assert args[1].endswith("/scripts/a0v_ecommerce_runtime_host.py")
    assert args[args.index("--interval-seconds") + 1] == "2"
    assert args[args.index("--credential-file") + 1].endswith(
        "/bm-runtime-credentials/runtime-host-identities.json")
    assert args[args.index("--bundle-root") + 1].endswith(
        "/bn-canonical-alias-registry/signed-bundles")
    assert args[args.index("--trust-roots-file") + 1].endswith(
        "/bm-trust-root-rotation/signing/trust-roots.json")
    assert "8080" not in " ".join(args)

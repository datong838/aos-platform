"""Actual isolated-engine registration tests; explicit opt-in, no shared engine."""
import asyncio
import os
import subprocess
import shutil
from pathlib import Path

import pytest

from aos_api.extension_runtime.contracts import RegistrationDescription
from aos_api.extension_runtime.supervisor import register_once
from aos_api.extension_runtime.oci_driver import OciDriver

pytestmark = pytest.mark.skipif(os.getenv("AOS_EXTENSION_OCI_TEST") != "1", reason="explicit isolated OCI environment required")
CONTEXT = "colima-aos-extension"


@pytest.fixture
def image(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.11-alpine\nCOPY runner.py /aos/runner.py\n", encoding="utf-8")
    def build(body):
        (tmp_path / "runner.py").write_text(body, encoding="utf-8")
        result = subprocess.run(["docker", "--context", CONTEXT, "build", "--network=none", "--pull=false", "-q", str(tmp_path)],
                                check=True, capture_output=True, text=True, timeout=60)
        return result.stdout.strip()
    return build


def test_actual_container_registration_and_cleanup(image):
    image_id = image('''import sys,json,struct,os
assert os.getuid()==65534
assert open('/proc/self/uid_map').read().split()[1] != '0'
n=struct.unpack('>I',sys.stdin.buffer.read(4))[0]
request=json.loads(sys.stdin.buffer.read(n))
request['type']='result'
request['payload']={'contributions':[]}
data=json.dumps(request).encode()
sys.stdout.buffer.write(struct.pack('>I',len(data))+data)
''')
    result = asyncio.run(register_once(OciDriver(context=CONTEXT), image_id=image_id,
                                      declared=RegistrationDescription(contributions=[])))
    assert result.contributions == []
    remaining = subprocess.check_output(["docker", "--context", CONTEXT, "ps", "-aq", "--filter", "label=aos.extension.owner"], text=True)
    assert remaining.strip() == ""


@pytest.mark.parametrize("body", [
    "print('not a frame')",
    "import sys;sys.stdout.buffer.write(b'x'*1048581)",
    "import sys;sys.stderr.buffer.write(b'x'*65537)",
])
def test_actual_bad_output_is_rejected_and_cleaned(image, body):
    with pytest.raises(ValueError):
        asyncio.run(register_once(OciDriver(context=CONTEXT), image_id=image(body),
                                  declared=RegistrationDescription(contributions=[])))
    remaining = subprocess.check_output(["docker", "--context", CONTEXT, "ps", "-aq", "--filter", "label=aos.extension.owner"], text=True)
    assert remaining.strip() == ""


def test_actual_sdk_package_relative_import(tmp_path):
    sdk = Path(__file__).resolve().parents[4] / "packages/aos-extension-sdk/python/aos_extension_sdk"
    shutil.copytree(sdk, tmp_path / "aos_extension_sdk")
    package = tmp_path / "bundle/backend/example"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("from .implementation import register\n")
    (package / "implementation.py").write_text("def register(ctx):\n    return {'contributions': []}\n")
    (tmp_path / "runtime.json").write_text('{"entrypoint":"backend/example/__init__.py:register","pythonPackage":"example"}')
    (tmp_path / "runner.py").write_text("from aos_extension_sdk.runner import main\nmain()\n")
    (tmp_path / "Dockerfile").write_text(
        "FROM python:3.11-alpine\n"
        "COPY aos_extension_sdk /usr/local/lib/python3.11/site-packages/aos_extension_sdk\n"
        "COPY bundle /aos/bundle\nCOPY runtime.json runner.py /aos/\n")
    digest = subprocess.check_output(["docker", "--context", CONTEXT, "build", "--network=none", "--pull=false", "-q", str(tmp_path)], text=True, timeout=60).strip()
    result = asyncio.run(register_once(OciDriver(context=CONTEXT), image_id=digest,
                                      declared=RegistrationDescription(contributions=[])))
    assert result.contributions == []


def test_actual_seccomp_denies_syscalls(image):
    digest = image('''import ctypes,errno,os,sys,json,struct
libc=ctypes.CDLL(None,use_errno=True)
for function,args in [(libc.ptrace,(0,0,0,0)),(libc.mount,(b'none',b'/tmp',b'tmpfs',0,None)),(libc.mknod,(b'/tmp/forbidden',0o20600,259))]:
    ctypes.set_errno(0)
    assert function(*args)==-1 and ctypes.get_errno()==errno.EPERM
n=struct.unpack('>I',sys.stdin.buffer.read(4))[0]
r=json.loads(sys.stdin.buffer.read(n));r['type']='result';r['payload']={'contributions':[]}
b=json.dumps(r).encode();sys.stdout.buffer.write(struct.pack('>I',len(b))+b)
''')
    assert asyncio.run(register_once(OciDriver(context=CONTEXT), image_id=digest,
                       declared=RegistrationDescription(contributions=[]))).contributions == []


def test_actual_cancellation_cleans_container(image):
    digest = image("import time; time.sleep(120)")
    async def exercise():
        task = asyncio.create_task(register_once(OciDriver(context=CONTEXT), image_id=digest,
                                   declared=RegistrationDescription(contributions=[])))
        await asyncio.sleep(.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(exercise())
    assert subprocess.check_output(["docker", "--context", CONTEXT, "ps", "-aq", "--filter", "label=aos.extension.owner"], text=True).strip() == ""


def test_actual_registration_timeout_cleans_container(image):
    with pytest.raises(TimeoutError):
        asyncio.run(register_once(OciDriver(context=CONTEXT), image_id=image("import time; time.sleep(120)"),
                                  declared=RegistrationDescription(contributions=[])))
    assert subprocess.check_output(["docker", "--context", CONTEXT, "ps", "-aq", "--filter", "label=aos.extension.owner"], text=True).strip() == ""

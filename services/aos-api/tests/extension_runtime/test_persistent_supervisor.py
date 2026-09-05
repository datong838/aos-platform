import asyncio
import json
from pathlib import Path
import shutil
import subprocess
import uuid
import pytest
from test_supervisor import pytestmark, CONTEXT
from aos_api.extension_runtime.contracts import RegistrationDescription
from aos_api.extension_runtime.oci_driver import OciDriver
from aos_api.extension_runtime.supervisor import ResourceIdentity


def build_session_image(tmp_path):
    sdk=Path(__file__).resolve().parents[4]/"packages/aos-extension-sdk/python/aos_extension_sdk"
    shutil.copytree(sdk,tmp_path/"aos_extension_sdk")
    package=tmp_path/"bundle/backend/example"
    package.mkdir(parents=True)
    claims={"contributions":[{"kind":"api","method":"POST","path":"/example/read",
                              "operationId":"example_read","mode":"exclusive"}]}
    (package/"__init__.py").write_text(
        "def register(ctx):\n    return "+repr(claims)+"\n"
        "def handle(operation,payload,ctx):\n"
        "    if payload.get('bad'): return []\n"
        "    if payload.get('wait'):\n        import time; time.sleep(60)\n"
        "    if payload.get('noisy'):\n"
        "        import threading,time,sys\n"
        "        def noisy():\n            time.sleep(.1); sys.stderr.write('x'*65537); sys.stderr.flush()\n"
        "        threading.Thread(target=noisy,daemon=True).start()\n"
        "    try: ctx.request('storage.query',{})\n"
        "    except PermissionError: return {'value':payload['value']}\n"
        "    raise RuntimeError('ports unexpectedly open')\n")
    (tmp_path/"runtime.json").write_text(json.dumps({"entrypoint":"backend/example/__init__.py:register","pythonPackage":"example"}))
    (tmp_path/"runner.py").write_text("from aos_extension_sdk.runner import main\nmain()\n")
    (tmp_path/"Dockerfile").write_text("FROM python:3.11-alpine\nCOPY aos_extension_sdk /usr/local/lib/python3.11/site-packages/aos_extension_sdk\nCOPY bundle /aos/bundle\nCOPY runtime.json runner.py /aos/\n")
    digest=subprocess.check_output(["docker","--context",CONTEXT,"build","--network=none","--pull=false","-q",str(tmp_path)],text=True,timeout=60).strip()
    return digest,claims


@pytest.mark.parametrize("finish",["normal","error","cancel","double-cancel","idle-stderr"])
def test_real_sdk_persistent_calls_and_exact_cleanup(tmp_path, finish):
    from aos_api.extension_runtime.session_supervisor import open_session
    digest,claims=build_session_image(tmp_path)
    identity=ResourceIdentity(uuid.uuid4().hex)
    async def exercise():
        async with open_session(OciDriver(context=CONTEXT),image_id=digest,
                                declared=RegistrationDescription.model_validate(claims),resource_identity=identity) as session:
            assert await session.check_health() is None
            assert await session.invoke("example_read",{"value":"第一次"})=={"value":"第一次"}
            assert await session.check_health() is None
            assert await session.invoke("example_read",{"value":"第二次"})=={"value":"第二次"}
            if finish=="error":
                with pytest.raises(Exception):
                    await session.invoke("example_read",{"bad":True})
            if finish in {"cancel","double-cancel"}:
                task=asyncio.create_task(session.invoke("example_read",{"wait":True}))
                await asyncio.sleep(.05)
                task.cancel()
                if finish=="double-cancel":
                    asyncio.get_running_loop().call_soon(task.cancel)
                with pytest.raises(asyncio.CancelledError):
                    await task
            if finish=="idle-stderr":
                await session.invoke("example_read",{"value":"已安排异步噪声","noisy":True})
                for _ in range(30):
                    await asyncio.sleep(.05)
                    remaining=subprocess.check_output(["docker","--context",CONTEXT,"ps","-aq","--filter","name="+identity.name],text=True)
                    if not remaining.strip():break
                assert session.failed
            if finish!="normal":
                assert subprocess.check_output(["docker","--context",CONTEXT,"ps","-aq","--filter","name="+identity.name],text=True).strip()==""
                with pytest.raises(ValueError):
                    await session.invoke("example_read",{"value":"禁止续用"})
    asyncio.run(exercise())
    assert subprocess.check_output(["docker","--context",CONTEXT,"ps","-aq","--filter","name="+identity.name],text=True).strip()==""

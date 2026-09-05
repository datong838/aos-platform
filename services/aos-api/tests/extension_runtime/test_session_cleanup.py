import asyncio
import uuid
import pytest
from aos_api.extension_runtime.session_supervisor import open_session, RuntimeSession
from aos_api.extension_runtime.supervisor import ResourceIdentity
from aos_api.extension_runtime.contracts import RegistrationDescription
from aos_api.extension_runtime.oci_driver import CleanupUncertainError


def test_create_uncertain_and_delete_error_preserve_reference():
    identity=ResourceIdentity(uuid.uuid4().hex)
    class Driver:
        context="colima-aos-extension"
        def require_isolation(self):pass
        def create_session(self,image,name,owner):raise CleanupUncertainError(self.context,name,owner)
        def remove_owned(self,*args):raise RuntimeError("engine unavailable")
    async def run():
        async with open_session(Driver(),image_id="sha256:"+"a"*64,
                                declared=RegistrationDescription(contributions=[]),resource_identity=identity):
            raise AssertionError("must not enter")
    with pytest.raises(CleanupUncertainError) as captured:
        asyncio.run(run())
    assert captured.value.cleanup_reference=={"context":"colima-aos-extension","name":identity.name,"owner":identity.owner}


def test_cleanup_uncertainty_survives_cancel_during_communication_drain():
    async def run():
        started=asyncio.Event()
        class Input:
            def write(self,data):pass
            async def drain(self):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    await asyncio.sleep(.01)
        class Process:
            stdin=Input()
        uncertainty=CleanupUncertainError("colima-aos-extension","resource","owner")
        async def close():
            asyncio.get_running_loop().call_soon(asyncio.current_task().cancel)
            raise uncertainty
        stderr=asyncio.create_task(asyncio.Event().wait())
        session=RuntimeSession(Process(),stderr,RegistrationDescription(contributions=[]),close)
        task=asyncio.create_task(session._exchange("register","register",{},15))
        await started.wait()
        task.cancel()
        try:
            with pytest.raises(CleanupUncertainError) as captured:
                await task
            assert captured.value is uncertainty
        finally:
            stderr.cancel()
            await asyncio.gather(stderr,return_exceptions=True)
    asyncio.run(run())

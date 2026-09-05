import asyncio
import threading

import pytest

from aos_api.extension_runtime.contracts import RegistrationDescription
from aos_api.extension_runtime.supervisor import register_once


@pytest.mark.parametrize("uncertain", [False, True])
def test_cancel_during_creation_waits_before_cleanup(uncertain):
    from aos_api.extension_runtime.oci_driver import CleanupUncertainError
    started, release = threading.Event(), threading.Event()
    events = []

    class Driver:
        def require_isolation(self):
            pass

        def create_registration(self, image_id, name, owner):
            started.set()
            assert release.wait(5)
            events.append("created")
            if uncertain:
                raise CleanupUncertainError("colima-aos-extension", name, owner)
            return "a" * 64

        def remove_owned(self, name, owner):
            assert events == ["created"]
            events.append("removed")

    async def exercise():
        task = asyncio.create_task(register_once(Driver(), image_id="unused",
                                   declared=RegistrationDescription(contributions=[])))
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(.01)
        assert not task.done()
        task.cancel()
        await asyncio.sleep(.01)
        task.cancel()
        await asyncio.sleep(.01)
        assert not task.done()
        release.set()
        with pytest.raises(CleanupUncertainError if uncertain else asyncio.CancelledError):
            await task
    asyncio.run(exercise())
    assert events == ["created", "removed"]

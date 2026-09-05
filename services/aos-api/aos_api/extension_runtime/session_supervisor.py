"""Persistent isolated diagnostic sessions; never grants business admission."""
import asyncio
from contextlib import asynccontextmanager
import struct
import uuid

from .contracts import RegistrationDescription
from .ipc import FrameSession, MAX_FRAME_BYTES, ProtocolError, encode_frame
from .registration import validate_registration
from .supervisor import ResourceIdentity, _bounded_read
from .oci_driver import CleanupUncertainError


class RuntimeSession:
    def __init__(self, process, stderr_task, declared, close):
        self.process = process
        self.stderr_task = stderr_task
        self.methods = {claim.operation_id for claim in declared.contributions if claim.kind == "api"}
        self.frames = FrameSession(allowed_methods=self.methods | {"register"})
        self.sequence = 0
        self.failed = False
        self.lock = asyncio.Lock()
        self.close = close

    async def _exchange(self, kind, method, payload, timeout):
        if self.failed:
            raise ProtocolError("session is closed")
        request_id = uuid.uuid4().hex
        request = {"schemaVersion":1,"type":kind,"method":method,"requestId":request_id,
                   "parentRequestId":None,"payload":payload,"sequence":self.sequence}

        async def exchange():
            self.process.stdin.write(encode_frame(request))
            await self.process.stdin.drain()
            header = await self.process.stdout.readexactly(4)
            size = struct.unpack(">I",header)[0]
            if not 0 < size <= MAX_FRAME_BYTES:
                raise ProtocolError("invalid response size")
            body = await self.process.stdout.readexactly(size)
            frames = self.frames.feed(header+body)
            if len(frames)!=1:
                raise ProtocolError("single response required")
            result=frames[0]
            if (result["type"]!="result" or result["requestId"]!=request_id
                    or result["parentRequestId"] is not None or result["method"]!=method):
                raise ProtocolError("response identity mismatch")
            return result["payload"]

        task=asyncio.create_task(exchange())
        try:
            async def monitored():
                done,_=await asyncio.wait({task,self.stderr_task},return_when=asyncio.FIRST_COMPLETED)
                if self.stderr_task in done:
                    self.stderr_task.result()
                return await task
            result=await asyncio.wait_for(monitored(),timeout=timeout)
            self.sequence+=1
            return result
        except BaseException:
            self.failed=True
            task.cancel()
            try:
                await self.close()
            finally:
                drain=asyncio.gather(task,return_exceptions=True)
                while not drain.done():
                    try:
                        await asyncio.shield(drain)
                    except asyncio.CancelledError:
                        # Preserve the pending cleanup error (or original failure).
                        continue
                drain.result()
            raise

    async def invoke(self, method, payload):
        async with self.lock:
            if method not in self.methods:
                raise ProtocolError("undeclared operation")
            return await self._exchange("invoke",method,payload,30)


@asynccontextmanager
async def open_session(driver, *, image_id, declared, resource_identity):
    """Caller must persist and claim identity and verify artifact before entry."""
    if not isinstance(resource_identity,ResourceIdentity):
        raise ValueError("persisted resource identity required")
    declared=RegistrationDescription.model_validate(declared)
    await asyncio.to_thread(driver.require_isolation)
    identity=resource_identity
    creation=asyncio.create_task(asyncio.to_thread(driver.create_session,image_id,identity.name,identity.owner))
    launch=None
    process=None
    stderr_task=None
    watcher=None
    session=None
    cleanup_task=None

    async def cleanup():
        if session is not None:
            session.failed=True
        creation_result=(await asyncio.gather(creation,return_exceptions=True))[0]
        launched=(await asyncio.gather(launch,return_exceptions=True))[0] if launch else None
        if stderr_task:
            stderr_task.cancel()
            await asyncio.gather(stderr_task,return_exceptions=True)
        try:
            await asyncio.to_thread(driver.remove_owned,identity.name,identity.owner)
        except Exception as exc:
            if isinstance(creation_result,CleanupUncertainError):
                raise creation_result from exc
            raise CleanupUncertainError(driver.context,identity.name,identity.owner) from exc
        finally:
            if isinstance(launched,asyncio.subprocess.Process) and launched.returncode is None:
                launched.kill()
                await launched.wait()
        if isinstance(creation_result,CleanupUncertainError):
            raise creation_result

    async def close():
        nonlocal cleanup_task
        if cleanup_task is None:
            cleanup_task=asyncio.create_task(cleanup())
        cancelled=False
        while not cleanup_task.done():
            try:
                await asyncio.shield(cleanup_task)
            except asyncio.CancelledError:
                cancelled=True
        cleanup_task.result()
        if cancelled:
            raise asyncio.CancelledError

    try:
        container_id=await asyncio.shield(creation)
        launch=asyncio.create_task(asyncio.create_subprocess_exec(*driver.start_command(container_id),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE))
        process=await asyncio.shield(launch)
        stderr_task=asyncio.create_task(_bounded_read(process.stderr,65536))
        session=RuntimeSession(process,stderr_task,declared,close)
        async def watch_stderr():
            try:
                await asyncio.shield(stderr_task)
            except asyncio.CancelledError:
                return
            except Exception:
                pass
            # EOF or overrun outside an invoke also invalidates the session.
            await close()
        watcher=asyncio.create_task(watch_stderr())
        result=await session._exchange("register","register",{},15)
        validate_registration(declared,RegistrationDescription.model_validate(result))
        yield session
    finally:
        try:
            await close()
        finally:
            if watcher:
                await asyncio.gather(watcher,return_exceptions=True)

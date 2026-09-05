"""Bounded one-shot registration supervisor; does not activate installations."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from aos_api.extension_runtime.contracts import RegistrationDescription
from aos_api.extension_runtime.ipc import FrameSession, MAX_FRAME_BYTES, ProtocolError, encode_frame
from aos_api.extension_runtime.oci_driver import CleanupUncertainError, OciDriver
from aos_api.extension_runtime.registration import validate_registration


@dataclass(frozen=True)
class ResourceIdentity:
    owner: str

    def __post_init__(self):
        if uuid.UUID(self.owner).hex != self.owner:
            raise ValueError("resource owner must be a canonical generated UUID")

    @property
    def name(self):
        return "aos-ext-" + self.owner


async def _bounded_read(reader, limit):
    output = bytearray()
    while True:
        chunk = await reader.read(min(65536, limit + 1 - len(output)))
        if not chunk:
            return bytes(output)
        output.extend(chunk)
        if len(output) > limit:
            raise ProtocolError("runtime output limit exceeded")


async def register_once(driver: OciDriver, *, image_id: str,
                        declared: RegistrationDescription,
                        resource_identity: ResourceIdentity | None = None) -> RegistrationDescription:
    """Internal entry only: caller must verify signed artifact before invocation."""
    await asyncio.to_thread(driver.require_isolation)
    identity = resource_identity or ResourceIdentity(uuid.uuid4().hex)
    owner, name = identity.owner, identity.name
    request_id = uuid.uuid4().hex
    process = None
    readers = []
    creation = asyncio.create_task(asyncio.to_thread(driver.create_registration, image_id, name, owner))
    try:
        container_id = await asyncio.shield(creation)
        process = await asyncio.create_subprocess_exec(
            *driver.start_command(container_id),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

        async def exchange():
            request = {"schemaVersion": 1, "type": "register", "method": "register",
                       "requestId": request_id, "parentRequestId": None,
                       "payload": {}, "sequence": 0}
            process.stdin.write(encode_frame(request))
            await process.stdin.drain()
            process.stdin.close()
            readers.extend([asyncio.create_task(_bounded_read(process.stdout, MAX_FRAME_BYTES + 4)),
                            asyncio.create_task(_bounded_read(process.stderr, 65536))])
            stdout, _ = await asyncio.gather(*readers)
            if await process.wait() != 0:
                raise ProtocolError("registration process failed")
            session = FrameSession(allowed_methods={"register"})
            frames = session.feed(stdout)
            session.finish()
            if len(frames) != 1:
                raise ProtocolError("expected exactly one registration result")
            response = frames[0]
            if response["type"] != "result" or response["requestId"] != request_id or response["parentRequestId"] is not None:
                raise ProtocolError("registration response does not match request")
            observed = RegistrationDescription.model_validate(response["payload"])
            validate_registration(declared, observed)
            return observed

        return await asyncio.wait_for(exchange(), timeout=15)
    finally:
        # A cancelled caller must not race ahead of a still-running create call.
        async def cleanup():
            creation_result = (await asyncio.gather(creation, return_exceptions=True))[0]
            for task in readers:
                if not task.done():
                    task.cancel()
            if readers:
                await asyncio.gather(*readers, return_exceptions=True)
            try:
                await asyncio.to_thread(driver.remove_owned, name, owner)
            finally:
                if process is not None and process.returncode is None:
                    process.kill()
                    await process.wait()
            if isinstance(creation_result, CleanupUncertainError):
                raise creation_result
        cleanup_task = asyncio.create_task(cleanup())
        cancelled = False
        while not cleanup_task.done():
            try:
                await asyncio.shield(cleanup_task)
            except asyncio.CancelledError:
                cancelled = True
        cleanup_task.result()
        if cancelled:
            raise asyncio.CancelledError

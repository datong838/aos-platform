"""Signed artifact to journal seam; not a public or business admission API."""
import asyncio
from copy import deepcopy
from contextlib import asynccontextmanager

from .admission import admit_runtime_artifact
from .contracts import RegistrationDescription
from .journaled_session import open_journaled_session


@asynccontextmanager
async def open_signed_session(*, driver, connect, org_id, project_id, resource_id,
                              record, selected, policy, checked_at, read_artifact, platform):
    # This work only validates bytes and inspects an existing cached image.
    # Cancellation here creates no resource and grants no journal claim.
    record, selected = deepcopy(record), deepcopy(selected)
    artifact = await asyncio.to_thread(admit_runtime_artifact, record=record, selected=selected,
        policy=policy, checked_at=checked_at, read_artifact=read_artifact, platform=platform, driver=driver)
    declared = RegistrationDescription(contributions=record.manifest.spec.contributions)
    async with open_journaled_session(driver,connect=connect,org_id=org_id,project_id=project_id,
        resource_id=resource_id,image_id=artifact.image_id,declared=declared,
        expected_package=(record.manifest.metadata.id,artifact.package_hash)) as session:
        yield session

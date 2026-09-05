"""Internal journal/session seam; callers still owe signed installation admission."""
import asyncio
from contextlib import asynccontextmanager

from .lifecycle_store import RuntimeConflict
from .oci_driver import CleanupUncertainError
from .reconciler import ResourceJournal
from .session_supervisor import open_session


async def _settle(task):
    cancelled=False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled=True
    return task.result(),cancelled


class _JournalDriver:
    def __init__(self,driver,persist):
        self.driver=driver
        self.persist=persist
        self.created=False
        self.unknown=False
        self.observation_attempted=False

    def __getattr__(self,name):
        return getattr(self.driver,name)

    def observe(self,confirmed):
        self.observation_attempted=True
        self.persist(confirmed)

    def create_session(self,*args):
        try:
            result=self.driver.create_session(*args)
        except CleanupUncertainError:
            self.unknown=True
            raise
        self.created=True
        return result

    def remove_owned(self,*args):
        try:
            removed=self.driver.remove_owned(*args)
        except Exception:
            self.observe(False)
            raise
        # Absence is proof only after a completed create, never an unknown create.
        self.observe(not self.unknown and (removed is True or self.created))
        return removed


@asynccontextmanager
async def open_journaled_session(driver,*,connect,org_id,project_id,resource_id,image_id,declared):
    """connect is a trusted scoped factory, not a request-supplied connection."""
    journal=ResourceJournal()
    def claim():
        with connect() as conn:
            with conn.transaction():
                intent=journal.claim_create(conn,org_id=org_id,project_id=project_id,resource_id=resource_id)
                if intent.engine_context!=driver.context:
                    raise RuntimeConflict("resource engine context mismatch")
                return intent
    intent,cancelled=await _settle(asyncio.create_task(asyncio.to_thread(claim)))
    def persist(confirmed):
        with connect() as conn:
            with conn.transaction():
                journal.record_cleanup(conn,org_id=org_id,project_id=project_id,intent=intent,removed=confirmed)
    wrapped=_JournalDriver(driver,persist)
    try:
        if cancelled:
            raise asyncio.CancelledError
        async with open_session(wrapped,image_id=image_id,declared=declared,resource_identity=intent.identity) as session:
            yield session
    finally:
        if not wrapped.observation_attempted:
            # Claim survived but no reliable cleanup observation was made.
            _,cancelled_during_observation=await _settle(asyncio.create_task(asyncio.to_thread(wrapped.observe,False)))
            if cancelled_during_observation:
                raise asyncio.CancelledError

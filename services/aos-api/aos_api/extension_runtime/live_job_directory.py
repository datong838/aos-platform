"""Process-owned live PreparedJob identities; never grants runtime admission."""

from uuid import UUID

from aos_api.tenant_scope import TenantScope
from .preparation_worker import PreparedJob


class LivePreparedJobDirectory:
    def __init__(self):
        self._jobs = {}

    @staticmethod
    def _job_key(job):
        if not isinstance(job, PreparedJob):
            raise TypeError("live directory requires a PreparedJob")
        if type(job.tenant_scope) is not TenantScope:
            raise TypeError("live PreparedJob requires TenantScope")
        return (
            *job.tenant_scope.key,
            UUID(str(job.plan.installation_id)),
            UUID(str(job.plan.generation)),
        )

    @staticmethod
    def _lookup_key(*, scope, installation_id, generation):
        if type(scope) is not TenantScope:
            raise TypeError("live directory lookup requires TenantScope")
        return (*scope.key, UUID(str(installation_id)), UUID(str(generation)))

    def register(self, job):
        key = self._job_key(job)
        current = self._jobs.get(key)
        if current is not None and current is not job:
            raise RuntimeError("live prepared job is already owned")
        self._jobs[key] = job
        return job

    def resolve(self, *, scope, installation_id, generation):
        key = self._lookup_key(
            scope=scope, installation_id=installation_id, generation=generation
        )
        job = self._jobs.get(key)
        if job is None:
            raise LookupError("live prepared job unavailable")
        return job

    def jobs_for_scope(self, scope):
        if type(scope) is not TenantScope:
            raise TypeError('live directory enumeration requires TenantScope')
        jobs=tuple(job for key,job in sorted(self._jobs.items(),key=lambda pair:tuple(map(str,pair[0])))
                   if key[:2]==scope.key)
        if len(jobs)>1000 or any(self._job_key(job)[:2]!=scope.key for job in jobs):
            raise RuntimeError('bounded current live directory required')
        return jobs

    def unregister(self, job):
        key = self._job_key(job)
        if self._jobs.get(key) is not job:
            return False
        del self._jobs[key]
        return True


__all__ = ["LivePreparedJobDirectory"]

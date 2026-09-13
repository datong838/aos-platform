from types import SimpleNamespace
from uuid import uuid4

import pytest

from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.extension_runtime.preparation_consumer import PreparationConsumer
from aos_api.extension_runtime.preparation_worker import PreparationWorker
from aos_api.extension_runtime.preparation_worker import PreparedJob
from aos_api.tenant_scope import TenantScope


def _job(scope=TenantScope("org-org", "dev-project"), *, installation=None, generation=None):
    job = object.__new__(PreparedJob)
    job._tenant_scope = scope
    job.plan = SimpleNamespace(
        installation_id=installation or uuid4(), generation=generation or uuid4()
    )
    return job


def test_directory_resolves_only_exact_job_owned_identity():
    directory = LivePreparedJobDirectory()
    job = _job()
    assert directory.register(job) is job
    assert directory.register(job) is job
    assert directory.resolve(
        scope=job.tenant_scope,
        installation_id=job.plan.installation_id,
        generation=job.plan.generation,
    ) is job
    for scope, installation, generation in (
        (TenantScope("dev-org", "dev-project"), job.plan.installation_id, job.plan.generation),
        (job.tenant_scope, uuid4(), job.plan.generation),
        (job.tenant_scope, job.plan.installation_id, uuid4()),
    ):
        with pytest.raises(LookupError, match="live prepared job unavailable"):
            directory.resolve(scope=scope, installation_id=installation, generation=generation)


def test_directory_rejects_competing_owner_and_unregister_is_identity_bound():
    directory = LivePreparedJobDirectory()
    job = _job()
    competing = _job(installation=job.plan.installation_id, generation=job.plan.generation)
    directory.register(job)
    with pytest.raises(RuntimeError, match="already owned"):
        directory.register(competing)
    assert directory.unregister(competing) is False
    assert directory.unregister(job) is True
    assert directory.unregister(job) is False
    with pytest.raises(LookupError):
        directory.resolve(scope=job.tenant_scope, installation_id=job.plan.installation_id,
                          generation=job.plan.generation)


@pytest.mark.parametrize("value", [None, object(), SimpleNamespace()])
def test_directory_accepts_only_real_prepared_jobs(value):
    with pytest.raises(TypeError, match="PreparedJob"):
        LivePreparedJobDirectory().register(value)


def test_preparation_consumer_registers_then_unregisters_the_owned_job():
    async def run():
        scope = TenantScope("org-org", "dev-project")
        operation = uuid4()
        job = _job(scope)
        job.plan.operation_id = operation
        stopped = []

        async def stop():
            stopped.append(True)

        job.stop = stop
        worker = object.__new__(PreparationWorker)

        async def start(**kwargs):
            assert kwargs == {
                "org_id": scope.org_id,
                "project_id": scope.project_id,
                "operation_id": operation,
                "expected_revision": 3,
            }
            return job

        worker.start = start
        directory = LivePreparedJobDirectory()
        consumer = object.__new__(PreparationConsumer)
        consumer.tenant_scope = scope
        consumer.scope = {"org_id": scope.org_id, "project_id": scope.project_id}
        consumer.installation = job.plan.installation_id
        consumer.worker = worker
        consumer.live_directory = directory
        consumer._job = None
        consumer._task = None
        owned = await consumer._start_owned(operation, 3)
        assert directory.resolve(scope=scope, installation_id=job.plan.installation_id,
                                 generation=job.plan.generation) is owned
        await consumer._close()
        assert stopped == [True]
        with pytest.raises(LookupError):
            directory.resolve(scope=scope, installation_id=job.plan.installation_id,
                              generation=job.plan.generation)

    import asyncio
    asyncio.run(run())


def test_job_enumeration_is_scoped_and_does_not_admit_other_tenants():
    directory=LivePreparedJobDirectory()
    positive=_job();negative=_job(TenantScope('dev-org','dev-project'))
    directory.register(positive);directory.register(negative)
    assert directory.jobs_for_scope(positive.tenant_scope)==(positive,)
    assert directory.jobs_for_scope(negative.tenant_scope)==(negative,)
    directory.unregister(positive)
    assert directory.jobs_for_scope(positive.tenant_scope)==()


def test_current_targets_are_detached_and_do_not_expose_jobs():
    directory=LivePreparedJobDirectory();first=_job();second=_job(TenantScope('other-org','other-project'))
    directory.register(first);directory.register(second)
    targets=directory.current_targets()
    assert type(targets) is tuple
    assert set(targets)=={(job.tenant_scope,job.plan.installation_id,job.plan.generation) for job in (first,second)}
    directory.unregister(first)
    assert len(targets)==2 and len(directory.current_targets())==1


def test_current_targets_reject_mutated_registered_identity():
    directory=LivePreparedJobDirectory();job=_job();directory.register(job)
    job.plan.generation=uuid4()
    with pytest.raises(RuntimeError,match='identity'):directory.current_targets()


def test_current_targets_are_bounded():
    directory=LivePreparedJobDirectory()
    for _ in range(1001):directory.register(_job())
    with pytest.raises(RuntimeError,match='bounded'):directory.current_targets()

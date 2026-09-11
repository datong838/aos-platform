from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from aos_api.extension_runtime.live_installation_owner import (
    LiveInstallationLifecycleOwner,
)
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.extension_runtime.pending_preparation_directory import (
    LiveInstallationOwnerFactory,
    PendingPreparationDescriptor,
    PostgresPendingPreparationDirectory,
)
from aos_api.extension_runtime.preparation_worker import PreparationWorker
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def test_descriptor_requires_exact_scope_and_uuid():
    with pytest.raises(TypeError):
        PendingPreparationDescriptor(SCOPE, "not-a-uuid")
    with pytest.raises(TypeError):
        PendingPreparationDescriptor(object(), uuid4())


def test_directory_normalizes_dict_and_tuple_rows_in_uuid_order():
    first = UUID("00000000-0000-0000-0000-000000000001")
    second = UUID("00000000-0000-0000-0000-000000000002")
    directory = object.__new__(PostgresPendingPreparationDirectory)
    directory.scope = SCOPE
    directory._read_installations = lambda: (
        {"installation_id": first},
        (second,),
    )
    assert directory.read_descriptors() == (
        PendingPreparationDescriptor(SCOPE, first),
        PendingPreparationDescriptor(SCOPE, second),
    )


@pytest.mark.parametrize(
    "rows,error",
    [
        (({"installation_id": uuid4()},) * 101, "limit"),
        (((UUID(int=2),), (UUID(int=1),)), "ordered"),
        (((UUID(int=1),), (UUID(int=1),)), "duplicate"),
    ],
)
def test_directory_rejects_unbounded_unordered_or_duplicate_rows(rows, error):
    directory = object.__new__(PostgresPendingPreparationDirectory)
    directory.scope = SCOPE
    directory._read_installations = lambda: rows
    with pytest.raises((RuntimeError, ValueError), match=error):
        directory.read_descriptors()


def test_factory_builds_exact_unstarted_owner_and_rejects_cross_scope():
    worker = object.__new__(PreparationWorker)
    live_directory = LivePreparedJobDirectory()
    connect = lambda: None
    factory = LiveInstallationOwnerFactory(
        connect=connect,
        scope=SCOPE,
        worker=worker,
        live_directory=live_directory,
    )
    descriptor = PendingPreparationDescriptor(SCOPE, uuid4())
    owner = factory(descriptor)
    assert type(owner) is LiveInstallationLifecycleOwner
    assert owner.preparation.connect is connect
    assert owner.preparation.worker is worker
    assert owner.preparation.live_directory is live_directory
    assert owner.preparation.installation == descriptor.installation_id
    assert owner.preparation.job is None
    with pytest.raises(ValueError, match="scope mismatch"):
        factory(PendingPreparationDescriptor(TenantScope("other", "project"), uuid4()))


@pytest.mark.parametrize("worker,directory", [(object(), LivePreparedJobDirectory()), (object.__new__(PreparationWorker), object())])
def test_factory_rejects_non_exact_dependencies(worker, directory):
    with pytest.raises(TypeError, match="exact live"):
        LiveInstallationOwnerFactory(
            connect=lambda: None,
            scope=SCOPE,
            worker=worker,
            live_directory=directory,
        )

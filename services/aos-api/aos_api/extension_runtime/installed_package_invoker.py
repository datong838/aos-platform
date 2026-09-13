"""Current installed-package invocation around one transaction-free live IPC."""

from copy import deepcopy
import inspect
from uuid import UUID

from aos_api.asset_registry.canonical_json import canonical_json
from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope
from .live_job_directory import LivePreparedJobDirectory
from .preparation_worker import PreparedJob


class CurrentInstalledPackageInvoker:
    def __init__(self, *, scope, installation_id, generation, package_id, markings,
                 connect_factory, installation_store, live_directory, expected_job=None):
        if type(scope) is not TenantScope:
            raise TypeError("installed invocation requires TenantScope")
        if not callable(connect_factory) or inspect.iscoroutinefunction(connect_factory):
            raise TypeError("trusted synchronous scoped connection factory required")
        if not callable(getattr(installation_store, "load_active_baseline_in_transaction", None)):
            raise TypeError("active Installation baseline reader required")
        if type(live_directory) is not LivePreparedJobDirectory:
            raise TypeError("exact live PreparedJob directory required")
        if type(package_id) is not str or not package_id or package_id != package_id.strip():
            raise ValueError("exact package id required")
        if type(markings) not in (tuple, list) or any(
            type(value) is not str or not value or value != value.strip()
            for value in markings
        ):
            raise ValueError("exact caller markings required")
        self.scope = scope
        self.installation_id = UUID(str(installation_id))
        self.generation = UUID(str(generation))
        self.package_id = package_id
        self.markings = frozenset(markings)
        self.connect = connect_factory
        self.store = installation_store
        self.directory = live_directory
        if expected_job is not None:
            if not isinstance(expected_job,PreparedJob):
                raise TypeError('exact expected PreparedJob required')
            if live_directory.resolve(scope=scope,installation_id=self.installation_id,generation=self.generation) is not expected_job:
                raise PermissionError('expected PreparedJob is not current')
        self.expected_job = expected_job

    def read_current_in_transaction(self, transaction):
        if type(transaction) is not HostTransaction:
            raise TypeError("installed snapshot requires HostTransaction")
        installation = transaction.execute(
                """SELECT i.active_revision,r.lock_hash,r.overlay_revision
                     FROM bundle_installation i
                     JOIN bundle_installation_revision r
                       ON r.org_id=i.org_id AND r.project_id=i.project_id
                      AND r.installation_pk=i.installation_pk
                      AND r.revision=i.active_revision
                    WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s
                    FOR SHARE OF i,r""",
                (*self.scope.key, self.installation_id),
            ).fetchone()
        binding = transaction.execute(
                """SELECT installation_revision,package_lock_ref,profile_ref,config_ref,
                          execution_epoch,desired_state,observed_state,enabled,
                          operation_fence,revision
                     FROM extension_runtime_binding
                    WHERE org_id=%s AND project_id=%s
                      AND installation_id=%s AND generation=%s FOR SHARE""",
                (*self.scope.key, self.installation_id, self.generation),
            ).fetchone()
        if installation is None or binding is None:
            raise PermissionError("current installed runtime unavailable")
        current_ref = CurrentInstallationRef.model_validate({
                "installationId": str(self.installation_id),
                "revision": installation["active_revision"],
                "lockHash": installation["lock_hash"],
                "overlayRevision": installation["overlay_revision"],
            })
        baseline = self.store.load_active_baseline_in_transaction(
            transaction, org_id=self.scope.org_id, project_id=self.scope.project_id,
            requested_ref=current_ref,
        )
        if baseline.server_ref != current_ref or baseline.lock.lock_hash != current_ref.lock_hash:
            raise PermissionError("current Installation baseline drifted")
        lock_ref = binding["package_lock_ref"]
        if (
                binding["installation_revision"] != current_ref.revision
                or type(lock_ref) is not dict
                or lock_ref.get("lockHash") != current_ref.lock_hash
                or binding["desired_state"] != "enabled"
                or binding["observed_state"] != "ready"
                or binding["enabled"] is not True
                or binding["operation_fence"] is not False
        ):
            raise PermissionError("current installed runtime is not admitted")
        target_markings = baseline.lock.payload.permission_diff.target.markings
        if type(target_markings) is not list or any(
                type(value) is not str or not value for value in target_markings
        ) or not set(target_markings).issubset(self.markings):
            raise PermissionError("current installed package markings are not admitted")
        selected = tuple(
                value for value in baseline.lock.payload.resolved
                if value.id == self.package_id
        )
        if len(selected) != 1:
            raise PermissionError("current installed package is not unique")
        package = selected[0]
        snapshot = {
                "scope": {"orgId": self.scope.org_id, "projectId": self.scope.project_id},
                "installationRef": current_ref.model_dump(mode="json", by_alias=True),
                "generation": str(self.generation),
                "binding": {
                    "installationRevision": binding["installation_revision"],
                    "packageLockRef": deepcopy(lock_ref),
                    "profileRef": binding["profile_ref"],
                    "configRef": deepcopy(binding["config_ref"]),
                    "executionEpoch": binding["execution_epoch"],
                    "desiredState": binding["desired_state"],
                    "observedState": binding["observed_state"],
                    "enabled": binding["enabled"],
                    "operationFence": binding["operation_fence"],
                    "revision": binding["revision"],
                },
                "package": package.model_dump(mode="json", by_alias=True),
                "targetMarkings": sorted(set(target_markings)),
        }
        canonical_json(snapshot)
        return snapshot

    def _read_current(self):
        with self.connect(self.scope) as conn:
            return self.read_current_in_transaction(HostTransaction(conn))

    async def __call__(self, operation, payload):
        if type(operation) is not str or not operation or type(payload) is not dict:
            raise ValueError("exact installed invocation required")
        canonical_json(payload)
        before = self._read_current()
        package_hash = before["package"]["contentHash"]
        job = self.directory.resolve(
            scope=self.scope, installation_id=self.installation_id,
            generation=self.generation,
        )
        if self.expected_job is not None and job is not self.expected_job:
            raise PermissionError('expected PreparedJob changed')
        result = await job.invoke_selected_once(
            package_id=self.package_id, package_hash=package_hash,
            operation=operation, payload=payload,
        )
        after = self._read_current()
        if self.expected_job is not None and self.directory.resolve(
                scope=self.scope,installation_id=self.installation_id,generation=self.generation) is not self.expected_job:
            raise PermissionError('expected PreparedJob changed')
        if after != before:
            raise PermissionError("installed invocation authority changed")
        return result


__all__ = ["CurrentInstalledPackageInvoker"]

"""W7-07 governed media Provider Job composition service.

The default service has no scanner or Provider adapter.  It therefore fails
closed before any external call.  Tests and future registered adapters inject
versioned implementations explicitly.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable, Protocol

from aos_api.aip_media_provider_job_contracts import (
    MediaAssetDirection,
    MediaJobStatus,
    MediaProviderBindingSnapshot,
    MediaProviderJob,
    PrepareMediaProviderJobRequest,
    ProviderOperation,
    ProviderOperationResult,
    ServerOwnedMediaScanResult,
)
from aos_api.aip_media_provider_job_store import (
    AipMediaProviderJobStore,
    MediaProviderJobConflict,
    MediaProviderJobDependencyBlocked,
)
from aos_api.aip_model_runtime_contracts import ModelRuntimeReadiness
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeStoreError
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_provider_plugin_authority import (
    ProviderPluginAuthority,
    ProviderPluginAuthorityError,
)
from aos_api.tenant_scope import TenantScope


class MediaAssetScanner(Protocol):
    def scan(
        self,
        scope: TenantScope,
        artifact_ref: ExactRevisionRef,
        direction: MediaAssetDirection,
    ) -> ServerOwnedMediaScanResult: ...


class MediaProviderAdapter(Protocol):
    adapter_ref: ExactRevisionRef

    def submit(self, job: MediaProviderJob) -> ProviderOperationResult: ...
    def status(self, job: MediaProviderJob) -> ProviderOperationResult: ...
    def cancel(self, job: MediaProviderJob) -> ProviderOperationResult: ...
    def reconcile(self, job: MediaProviderJob) -> ProviderOperationResult: ...


ExactRefValidator = Callable[[TenantScope, ExactRevisionRef], bool]


class AipMediaProviderJobService:
    def __init__(
        self,
        *,
        store: AipMediaProviderJobStore | None = None,
        model_resolver: AipModelRuntimeResolver | None = None,
        model_store: AipModelRuntimeStore | None = None,
        plugin_authority: ProviderPluginAuthority | None = None,
        scanner: MediaAssetScanner | None = None,
        adapter: MediaProviderAdapter | None = None,
        capability_validator: ExactRefValidator | None = None,
        binding_validator: ExactRefValidator | None = None,
        license_validator: ExactRefValidator | None = None,
        adapter_validator: ExactRefValidator | None = None,
    ) -> None:
        self._store = store or AipMediaProviderJobStore()
        self._model_store = model_store or AipModelRuntimeStore()
        self._model_resolver = model_resolver or AipModelRuntimeResolver(self._model_store)
        self._plugin_authority = plugin_authority or ProviderPluginAuthority()
        self._scanner = scanner
        self._adapter = adapter
        self._capability_validator = capability_validator
        self._binding_validator = binding_validator
        self._license_validator = license_validator
        self._adapter_validator = adapter_validator

    def prepare(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        body: PrepareMediaProviderJobRequest,
    ) -> MediaProviderJob:
        if self._scanner is None:
            raise MediaProviderJobDependencyBlocked("MEDIA_SCANNER_NOT_REGISTERED")
        self._require_validated(scope, body.capability_ref, self._capability_validator, "MEDIA_CAPABILITY_REF_BLOCKED")
        self._require_validated(scope, body.binding_ref, self._binding_validator, "MEDIA_BINDING_REF_BLOCKED")
        self._require_validated(scope, body.license_ref, self._license_validator, "MEDIA_LICENSE_REF_BLOCKED")
        self._require_validated(scope, body.adapter_ref, self._adapter_validator, "MEDIA_ADAPTER_REF_BLOCKED")
        try:
            resolution = self._model_resolver.resolve(scope, body.model_route_ref.resource_id)
        except Exception as exc:
            raise MediaProviderJobDependencyBlocked("MEDIA_MODEL_ROUTE_UNAVAILABLE") from exc
        if resolution.readiness is not ModelRuntimeReadiness.READY:
            raise MediaProviderJobDependencyBlocked("MEDIA_MODEL_ROUTE_NOT_READY")
        self._same_ref(body.model_route_ref, resolution.route, "MEDIA_MODEL_ROUTE_REF_DRIFTED")
        self._same_ref(body.runtime_policy_ref, resolution.policy, "MEDIA_RUNTIME_POLICY_REF_DRIFTED")
        if (
            resolution.selected_model is None
            or resolution.selected_provider is None
            or resolution.selected_price_snapshot is None
        ):
            raise MediaProviderJobDependencyBlocked("MEDIA_MODEL_ROUTE_SELECTION_INCOMPLETE")
        try:
            model = self._model_store.get_model(
                scope, resolution.selected_model.asset_id, resolution.selected_model.revision
            )
            provider = self._model_store.get_provider(
                scope, resolution.selected_provider.asset_id,
                resolution.selected_provider.revision,
            )
        except ModelRuntimeStoreError as exc:
            raise MediaProviderJobDependencyBlocked("MEDIA_MODEL_PROVIDER_UNAVAILABLE") from exc
        if body.expected_output_modality not in {item.value for item in model.output_modalities}:
            raise MediaProviderJobDependencyBlocked("MEDIA_MODEL_OUTPUT_MODALITY_BLOCKED")
        try:
            plugin = self._plugin_authority.validate_ref(scope, provider.plugin_ref)
        except ProviderPluginAuthorityError as exc:
            raise MediaProviderJobDependencyBlocked("MEDIA_PROVIDER_PLUGIN_BLOCKED") from exc
        binding = MediaProviderBindingSnapshot(
            capabilityRef=body.capability_ref,
            bindingRef=body.binding_ref,
            modelRouteRef=body.model_route_ref,
            modelRef=self._exact_from_versioned(resolution.selected_model),
            providerRef=self._exact_from_versioned(resolution.selected_provider),
            runtimePolicyRef=body.runtime_policy_ref,
            providerPluginRef=ExactRevisionRef(
                resourceType="ProviderPluginRevision",
                resourceId=plugin.provider_plugin_id,
                revision=plugin.revision,
                contentHash=plugin.content_hash,
            ),
            priceSnapshotRef=self._exact_from_versioned(resolution.selected_price_snapshot),
            adapterRef=body.adapter_ref,
            licenseRef=body.license_ref,
            evalGateRef=self._exact_from_versioned(model.eval_gate_ref),
        )
        scans = [
            self._scanner.scan(scope, artifact, MediaAssetDirection.INPUT)
            for artifact in body.input_artifact_refs
        ]
        return self._store.prepare_job(scope, actor, key, body, binding, scans)

    def submit(
        self, scope: TenantScope, actor: str, job_id: str, key: str, *, expected_sequence: int
    ) -> MediaProviderJob:
        return self._invoke(scope, actor, job_id, key, ProviderOperation.SUBMIT, expected_sequence)

    def status(
        self, scope: TenantScope, actor: str, job_id: str, key: str, *, expected_sequence: int
    ) -> MediaProviderJob:
        return self._invoke(scope, actor, job_id, key, ProviderOperation.STATUS, expected_sequence)

    def cancel(
        self, scope: TenantScope, actor: str, job_id: str, key: str, *, expected_sequence: int
    ) -> MediaProviderJob:
        return self._invoke(scope, actor, job_id, key, ProviderOperation.CANCEL, expected_sequence)

    def reconcile(
        self, scope: TenantScope, actor: str, job_id: str, key: str, *, expected_sequence: int
    ) -> MediaProviderJob:
        return self._invoke(scope, actor, job_id, key, ProviderOperation.RECONCILE, expected_sequence)

    def observe_webhook(
        self,
        scope: TenantScope,
        actor: str,
        job_id: str,
        key: str,
        result: ProviderOperationResult,
        *,
        expected_sequence: int,
    ) -> MediaProviderJob:
        job = self._store.get_job(scope, job_id)
        result = self._scan_outputs(scope, actor, job, result)
        return self._store.record_operation(
            scope, actor, job_id, key, ProviderOperation.WEBHOOK, result,
            expected_sequence=expected_sequence,
        )

    def _invoke(
        self,
        scope: TenantScope,
        actor: str,
        job_id: str,
        key: str,
        operation: ProviderOperation,
        expected_sequence: int,
    ) -> MediaProviderJob:
        if self._adapter is None:
            raise MediaProviderJobDependencyBlocked("MEDIA_PROVIDER_ADAPTER_NOT_REGISTERED")
        job = self._store.get_job(scope, job_id)
        self._assert_operation_allowed(job.status, operation)
        if self._adapter.adapter_ref != job.binding.adapter_ref:
            raise MediaProviderJobDependencyBlocked("MEDIA_PROVIDER_ADAPTER_REF_DRIFTED")
        method_name = "status" if operation is ProviderOperation.STATUS else operation.value
        try:
            result = getattr(self._adapter, method_name)(job)
        except Exception:
            result = ProviderOperationResult(
                status=MediaJobStatus.UNKNOWN,
                blockerCodes=["MEDIA_PROVIDER_RESULT_UNKNOWN_RECONCILE_REQUIRED"],
                observedAt=datetime.now(UTC),
            )
        result = self._scan_outputs(scope, actor, job, result)
        return self._store.record_operation(
            scope, actor, job_id, key, operation, result,
            expected_sequence=expected_sequence,
        )

    @staticmethod
    def _assert_operation_allowed(status: MediaJobStatus, operation: ProviderOperation) -> None:
        allowed = {
            ProviderOperation.SUBMIT: {MediaJobStatus.PREPARED},
            ProviderOperation.STATUS: {
                MediaJobStatus.SUBMITTED, MediaJobStatus.RUNNING,
                MediaJobStatus.CANCEL_REQUESTED,
            },
            ProviderOperation.CANCEL: {
                MediaJobStatus.SUBMITTED, MediaJobStatus.RUNNING, MediaJobStatus.UNKNOWN,
            },
            ProviderOperation.RECONCILE: {
                MediaJobStatus.UNKNOWN, MediaJobStatus.CANCEL_REQUESTED,
            },
        }
        if status not in allowed.get(operation, set()):
            raise MediaProviderJobConflict(
                f"MEDIA_JOB_OPERATION_BLOCKED:{status.value}:{operation.value}"
            )

    def _scan_outputs(
        self,
        scope: TenantScope,
        actor: str,
        job: MediaProviderJob,
        result: ProviderOperationResult,
    ) -> ProviderOperationResult:
        if result.status is not MediaJobStatus.SUCCEEDED:
            return result
        if self._scanner is None:
            return result.model_copy(
                update={
                    "status": MediaJobStatus.FAILED,
                    "output_artifact_refs": [],
                    "blocker_codes": ["MEDIA_OUTPUT_SCANNER_NOT_REGISTERED"],
                }
            )
        rejected: list[str] = []
        for artifact in result.output_artifact_refs:
            scan = self._scanner.scan(scope, artifact, MediaAssetDirection.OUTPUT)
            self._store.record_scan_observation(
                scope, actor, artifact, MediaAssetDirection.OUTPUT,
                job.scan_policy_ref, job.scanner_ref, scan,
            )
            if scan.verdict.value != "passed":
                rejected.extend(item.code for item in scan.findings)
        if rejected:
            return result.model_copy(
                update={
                    "status": MediaJobStatus.FAILED,
                    "output_artifact_refs": [],
                    "blocker_codes": list(dict.fromkeys(rejected)),
                }
            )
        return result

    @staticmethod
    def _require_validated(
        scope: TenantScope,
        ref: ExactRevisionRef,
        validator: ExactRefValidator | None,
        code: str,
    ) -> None:
        if validator is None or not validator(scope, ref):
            raise MediaProviderJobDependencyBlocked(code)

    @staticmethod
    def _same_ref(expected: ExactRevisionRef, actual, code: str) -> None:
        if (
            expected.resource_id != actual.asset_id
            or expected.revision != actual.revision
            or expected.content_hash != actual.content_hash
        ):
            raise MediaProviderJobDependencyBlocked(code)

    @staticmethod
    def _exact_from_versioned(ref) -> ExactRevisionRef:
        return ExactRevisionRef(
            resourceType=ref.asset_type,
            resourceId=ref.asset_id,
            revision=ref.revision,
            contentHash=ref.content_hash,
        )


__all__ = ["AipMediaProviderJobService", "MediaAssetScanner", "MediaProviderAdapter"]

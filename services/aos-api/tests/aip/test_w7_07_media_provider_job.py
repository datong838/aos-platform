"""W7-07 governed media Provider Job contract and safety tests."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.aip_media_provider_job_contracts import (
    MediaAssetDirection,
    IssueMediaAccessGrantRequest,
    MediaJobStatus,
    MediaProviderBindingSnapshot,
    MediaProviderJob,
    MediaScanVerdict,
    PrepareMediaProviderJobRequest,
    ProviderOperation,
    ProviderOperationResult,
    ServerOwnedMediaScanResult,
)
from aos_api.aip_media_provider_job_service import AipMediaProviderJobService
from aos_api.aip_media_provider_job_store import (
    AipMediaProviderJobStore,
    MediaProviderJobConflict,
    MediaProviderJobDependencyBlocked,
)
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _ref(kind: str, name: str) -> ExactRevisionRef:
    return ExactRevisionRef(
        resourceType=kind, resourceId=name, revision=1, contentHash=_hash(f"{kind}:{name}")
    )


def _request() -> PrepareMediaProviderJobRequest:
    return PrepareMediaProviderJobRequest(
        taskRunRef=_ref("TaskRun", "task-run"),
        stepRunRef=_ref("StepRunAttempt", "step-run"),
        capabilityRef=_ref("CapabilityRevision", "media-generate"),
        bindingRef=_ref("CapabilityBindingRevision", "content-officer-media"),
        modelRouteRef=_ref("ModelRouteRevision", "image-route"),
        runtimePolicyRef=_ref("RuntimePolicyRevision", "media-policy"),
        adapterRef=_ref("MediaProviderAdapterRevision", "provider-adapter"),
        licenseRef=_ref("MediaLicenseDecision", "license-decision"),
        scanPolicyRef=_ref("MediaAssetScanPolicyRevision", "scan-policy"),
        scannerRef=_ref("MediaAssetScannerRevision", "scanner"),
        inputArtifactRefs=[_ref("Artifact", "input")],
        expectedOutputModality="image",
        purpose="campaign visual generation",
        dataClassification="internal",
    )


def _binding() -> MediaProviderBindingSnapshot:
    body = _request()
    return MediaProviderBindingSnapshot(
        capabilityRef=body.capability_ref,
        bindingRef=body.binding_ref,
        modelRouteRef=body.model_route_ref,
        modelRef=_ref("RegisteredModelRevision", "image-model"),
        providerRef=_ref("ProviderInstanceRevision", "provider"),
        runtimePolicyRef=body.runtime_policy_ref,
        providerPluginRef=_ref("ProviderPluginRevision", "plugin"),
        priceSnapshotRef=_ref("ModelPriceSnapshotRevision", "price"),
        adapterRef=body.adapter_ref,
        licenseRef=body.license_ref,
        evalGateRef=_ref("EvalGateDecision", "eval"),
    )


def _job(status: MediaJobStatus = MediaJobStatus.PREPARED) -> MediaProviderJob:
    body = _request()
    blockers = ["RESULT_UNKNOWN"] if status is MediaJobStatus.UNKNOWN else []
    return MediaProviderJob(
        tenant={"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        jobId="media-job-1",
        taskRunRef=body.task_run_ref,
        stepRunRef=body.step_run_ref,
        binding=_binding(),
        inputArtifactRefs=body.input_artifact_refs,
        inputScanRefs=[_ref("MediaScanObservation", "input-scan")],
        scanPolicyRef=body.scan_policy_ref,
        scannerRef=body.scanner_ref,
        expectedOutputModality="image",
        purpose=body.purpose,
        dataClassification=body.data_classification,
        requestFingerprint=_hash("request"),
        status=status,
        sequence=1,
        blockerCodes=blockers,
        createdBy="test",
        createdAt=NOW,
        updatedAt=NOW,
    )


class _Scanner:
    def __init__(self, verdict: MediaScanVerdict) -> None:
        self.verdict = verdict

    def scan(self, scope, artifact_ref, direction):  # type: ignore[no-untyped-def]
        findings = [] if self.verdict is MediaScanVerdict.PASSED else [{
            "code": "MEDIA_MALWARE_DETECTED",
            "location": f"{direction.value}:payload",
            "evidenceHash": _hash("malware"),
        }]
        return ServerOwnedMediaScanResult(
            detectedMime="image/png",
            byteSize=128,
            contentHash=artifact_ref.content_hash,
            verdict=self.verdict,
            findings=findings,
            scannedAt=NOW,
        )


class _Store:
    def __init__(self, status: MediaJobStatus = MediaJobStatus.PREPARED) -> None:
        self.scans = []
        self.recorded = None
        self.status = status

    def get_job(self, scope, job_id):  # type: ignore[no-untyped-def]
        return _job(self.status)

    def record_scan_observation(self, *args):  # type: ignore[no-untyped-def]
        self.scans.append(args)

    def record_operation(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.recorded = (args, kwargs)
        return _job(MediaJobStatus.UNKNOWN if args[5].status is MediaJobStatus.UNKNOWN else MediaJobStatus.PREPARED)


def test_prepare_contract_forbids_client_owned_scan_or_secret() -> None:
    payload = _request().model_dump(mode="json", by_alias=True)
    payload["scanResult"] = {"verdict": "passed"}
    payload["secretRef"] = "must-not-cross-contract"
    with pytest.raises(ValidationError):
        PrepareMediaProviderJobRequest.model_validate(payload)


def test_prepare_store_rejects_server_scan_hash_drift_before_persistence() -> None:
    scan = _Scanner(MediaScanVerdict.PASSED).scan(
        SCOPE, _ref("Artifact", "different"), MediaAssetDirection.INPUT
    )
    with pytest.raises(MediaProviderJobDependencyBlocked, match="MEDIA_INPUT_SCAN_HASH_DRIFTED"):
        AipMediaProviderJobStore(connect_factory=lambda _: pytest.fail("must not connect")).prepare_job(
            SCOPE, "test", "key", _request(), _binding(), [scan]
        )


def test_prepare_store_rejects_malicious_server_scan_before_persistence() -> None:
    body = _request()
    scan = _Scanner(MediaScanVerdict.REJECTED).scan(
        SCOPE, body.input_artifact_refs[0], MediaAssetDirection.INPUT
    )
    with pytest.raises(MediaProviderJobDependencyBlocked, match="MEDIA_MALWARE_DETECTED"):
        AipMediaProviderJobStore(connect_factory=lambda _: pytest.fail("must not connect")).prepare_job(
            SCOPE, "test", "key", body, _binding(), [scan]
        )


@pytest.mark.parametrize(
    "finding_code",
    [
        "MEDIA_MIME_SPOOFED",
        "MEDIA_SIZE_LIMIT_EXCEEDED",
        "MEDIA_ARCHIVE_BOMB_DETECTED",
        "MEDIA_MALWARE_DETECTED",
        "MEDIA_LICENSE_BLOCKED",
        "MEDIA_PORTRAIT_CONSENT_MISSING",
        "MEDIA_TRADEMARK_REVIEW_REQUIRED",
        "MEDIA_OCR_PROMPT_INJECTION",
        "MEDIA_EXIF_PROMPT_INJECTION",
        "MEDIA_SUBTITLE_PROMPT_INJECTION",
        "MEDIA_SCRIPT_PROMPT_INJECTION",
    ],
)
def test_each_server_owned_input_gate_fails_before_persistence(finding_code: str) -> None:
    body = _request()
    scan = ServerOwnedMediaScanResult(
        detectedMime="application/octet-stream",
        byteSize=1024,
        contentHash=body.input_artifact_refs[0].content_hash,
        verdict="rejected",
        findings=[{
            "code": finding_code,
            "location": "quarantine:input",
            "evidenceHash": _hash(finding_code),
        }],
        scannedAt=NOW,
    )
    with pytest.raises(MediaProviderJobDependencyBlocked, match=finding_code):
        AipMediaProviderJobStore(connect_factory=lambda _: pytest.fail("must not connect")).prepare_job(
            SCOPE, "test", finding_code, body, _binding(), [scan]
        )


def test_unknown_and_terminal_jobs_cannot_be_blindly_submitted() -> None:
    for current in (MediaJobStatus.UNKNOWN, MediaJobStatus.SUCCEEDED, MediaJobStatus.FAILED):
        with pytest.raises(MediaProviderJobConflict):
            AipMediaProviderJobStore._assert_transition(
                current, ProviderOperation.SUBMIT, MediaJobStatus.SUBMITTED
            )


def test_timeout_becomes_unknown_without_implicit_retry() -> None:
    class Adapter:
        adapter_ref = _request().adapter_ref
        calls = 0

        def submit(self, job):  # type: ignore[no-untyped-def]
            self.calls += 1
            raise TimeoutError("provider timeout")

    store = _Store()
    adapter = Adapter()
    result = AipMediaProviderJobService(store=store, adapter=adapter).submit(
        SCOPE, "test", "media-job-1", "submit-1", expected_sequence=1
    )
    assert adapter.calls == 1
    assert result.status is MediaJobStatus.UNKNOWN
    operation = store.recorded[0][5]
    assert operation.status is MediaJobStatus.UNKNOWN
    assert operation.blocker_codes == ["MEDIA_PROVIDER_RESULT_UNKNOWN_RECONCILE_REQUIRED"]


def test_unknown_submit_is_blocked_before_adapter_call() -> None:
    class Adapter:
        adapter_ref = _request().adapter_ref
        calls = 0

        def submit(self, job):  # type: ignore[no-untyped-def]
            self.calls += 1
            raise AssertionError("must not invoke Provider")

    adapter = Adapter()
    with pytest.raises(MediaProviderJobConflict, match="MEDIA_JOB_OPERATION_BLOCKED"):
        AipMediaProviderJobService(
            store=_Store(MediaJobStatus.UNKNOWN), adapter=adapter
        ).submit(SCOPE, "test", "media-job-1", "blind-retry", expected_sequence=1)
    assert adapter.calls == 0


def test_malicious_output_is_failed_and_not_exposed_as_artifact() -> None:
    store = _Store()
    service = AipMediaProviderJobService(
        store=store, scanner=_Scanner(MediaScanVerdict.REJECTED)
    )
    result = service._scan_outputs(
        SCOPE,
        "test",
        _job(),
        ProviderOperationResult(
            status=MediaJobStatus.SUCCEEDED,
            outputArtifactRefs=[_ref("Artifact", "output")],
            observedAt=NOW,
        ),
    )
    assert result.status is MediaJobStatus.FAILED
    assert result.output_artifact_refs == []
    assert result.blocker_codes == ["MEDIA_MALWARE_DETECTED"]
    assert store.scans[0][4] == _request().scan_policy_ref
    assert store.scans[0][5] == _request().scanner_ref


def test_migration_declares_rls_append_only_and_no_secret_columns() -> None:
    migration = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "alembic/versions/w7_005_media_provider_job_adapter.py"
    ).read_text()
    for table in (
        "aip_media_asset_scan_observation",
        "aip_media_provider_job",
        "aip_media_provider_receipt",
        "aip_media_provider_job_event",
        "aip_media_access_grant",
    ):
        assert f"ENABLE ROW LEVEL SECURITY;" in migration
        assert table in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "guard_aip4_append_only" in migration
    assert "secret_value" not in migration
    assert "provider_payload" not in migration


def test_disposable_database_persists_and_isolates_append_only_job_authority() -> None:
    body = _request()
    scan = _Scanner(MediaScanVerdict.PASSED).scan(
        SCOPE, body.input_artifact_refs[0], MediaAssetDirection.INPUT
    )
    store = AipMediaProviderJobStore()
    job = store.prepare_job(SCOPE, "test:w7-07", "db-prepare-w7-07", body, _binding(), [scan])
    assert job.status is MediaJobStatus.PREPARED
    assert job.scan_policy_ref == body.scan_policy_ref
    assert store.list_jobs(TenantScope("dev-org", "dev-project")).count == 0
    submitted = store.record_operation(
        SCOPE,
        "test:w7-07",
        job.job_id,
        "db-submit-w7-07",
        ProviderOperation.SUBMIT,
        ProviderOperationResult(status=MediaJobStatus.SUBMITTED, observedAt=NOW),
        expected_sequence=1,
    )
    webhook = ProviderOperationResult(status=MediaJobStatus.RUNNING, observedAt=NOW)
    observed = store.record_operation(
        SCOPE, "test:w7-07", job.job_id, "db-webhook-w7-07-a",
        ProviderOperation.WEBHOOK, webhook, expected_sequence=submitted.sequence,
    )
    replay = store.record_operation(
        SCOPE, "test:w7-07", job.job_id, "db-webhook-w7-07-b",
        ProviderOperation.WEBHOOK, webhook, expected_sequence=observed.sequence,
    )
    assert replay.sequence == observed.sequence == 3
    with connect(SCOPE) as conn:
        receipt_count = conn.execute(
            "SELECT COUNT(*) AS count FROM aip_media_provider_receipt "
            "WHERE org_id=%s AND project_id=%s AND job_id=%s",
            (*SCOPE.key, job.job_id),
        ).fetchone()["count"]
        assert receipt_count == 2
        with pytest.raises(Exception):
            conn.execute(
                "UPDATE aip_media_provider_job SET purpose='tampered' "
                "WHERE org_id=%s AND project_id=%s AND job_id=%s",
                (*SCOPE.key, job.job_id),
            )
        conn.rollback()


def test_api_default_prepare_fails_closed_without_registered_scanner(
    client, auth_headers
) -> None:
    response = client.post(
        "/v1/aip/media-provider-jobs",
        headers={**auth_headers, "Idempotency-Key": "api-prepare-w7-07"},
        json=_request().model_dump(mode="json", by_alias=True),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "MEDIA_PROVIDER_JOB_DEPENDENCY_BLOCKED"
    assert "MEDIA_SCANNER_NOT_REGISTERED" in response.text
    assert "secret" not in response.text.lower()


def test_purpose_bound_access_grant_persists_hash_only() -> None:
    issued_at = datetime.now(UTC)
    body = IssueMediaAccessGrantRequest(
        artifactRef=_ref("Artifact", "grant-artifact"),
        principalRef="adapter:image-provider",
        purpose="single provider input read",
        marking="internal",
        licenseRef=_ref("MediaLicenseDecision", "grant-license"),
        expiresAt=issued_at.replace(year=issued_at.year + 1),
        accessReceiptRef=_ref("AccessReceipt", "grant-receipt"),
    )
    token_hash = _hash("one-time-token-never-persisted")
    grant = AipMediaProviderJobStore().issue_access_grant(
        SCOPE, body, token_hash=token_hash, now=issued_at
    )
    assert grant.token_hash == token_hash
    assert grant.purpose == body.purpose
    with connect(SCOPE) as conn:
        row = conn.execute(
            "SELECT token_hash,purpose FROM aip_media_access_grant "
            "WHERE org_id=%s AND project_id=%s AND grant_id=%s",
            (*SCOPE.key, grant.grant_id),
        ).fetchone()
    assert row == {"token_hash": token_hash, "purpose": body.purpose}
    assert "one-time-token-never-persisted" not in str(row)

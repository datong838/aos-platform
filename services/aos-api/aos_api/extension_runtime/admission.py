"""Signed release + exact resolution + image bytes. No caller readiness flags."""
from dataclasses import dataclass
import hashlib
import json
import re

from aos_api.asset_registry.composition_contracts import ResolvedBundle
from aos_api.asset_registry.contracts import BundleEvidenceType
from aos_api.extension_runtime.artifact_cache import resolve_image_index, require_cached_image
from aos_api.extension_runtime.ipc import _pairs
from aos_api.asset_registry.runtime_contracts import _path
from aos_api.extension_runtime.query_registry import validate_select_template


@dataclass(frozen=True)
class AdmittedRuntimeArtifact:
    image_id: str
    package_hash: str
    signature_fingerprint: str
    evidence_revision: str


@dataclass(frozen=True)
class AdmittedQuery:
    operation_id: str
    raw: bytes
    expected_hash: str
    table: str
    column_types: tuple[tuple[str, str], ...]
    limit: int
    package_hash: str
    signature_fingerprint: str
    evidence_revision: str


def admit_query_registry(*, record, selected, policy, checked_at, read_artifact):
    """Authenticate immutable query definitions, without granting execution."""
    selected = ResolvedBundle.model_validate(selected)
    metadata = record.manifest.metadata
    if (record.publisher, metadata.id, metadata.version, record.content_hash) != (
            selected.publisher, selected.id, selected.version, selected.content_hash):
        raise ValueError("release does not match exact composition lock")
    approved = policy.evaluate(record, checked_at=checked_at,
        expected_signature_fingerprint=selected.signature_fingerprint,
        expected_evidence_revision=selected.release_evidence_revision)
    runtime = record.manifest.spec.runtime
    if runtime is None or runtime.backend is None:
        raise ValueError("query registry requires backend runtime")
    artifacts = {item["relativePath"]: item for item in record.artifacts}
    if len(artifacts) != len(record.artifacts):
        raise ValueError("duplicate artifact paths")

    def verified(path):
        item = artifacts.get(path)
        if item is None or type(item["size"]) is not int or not 0 < item["size"] <= 65536:
            raise ValueError("registry artifact missing or oversized")
        raw = read_artifact(path, 65536)
        if (not isinstance(raw, bytes) or len(raw) != item["size"]
                or "sha256:"+hashlib.sha256(raw).hexdigest() != item["digest"]):
            raise ValueError("registry artifact differs from signed release")
        return raw, item["digest"]

    raw, _ = verified("artifacts/storage-registry.json")
    document = json.loads(raw, object_pairs_hook=_pairs)
    if (not isinstance(document, dict) or set(document) != {"schemaVersion", "queries"}
            or type(document["schemaVersion"]) is not int or document["schemaVersion"] != 1
            or not isinstance(document["queries"], list) or not 1 <= len(document["queries"]) <= 64):
        raise ValueError("invalid query registry")
    admitted, seen = [], set()
    for entry in document["queries"]:
        if not isinstance(entry, dict) or set(entry) != {"operationId", "sqlPath", "table", "columnTypes", "limit"}:
            raise ValueError("invalid query definition")
        operation = entry["operationId"]
        if (not isinstance(operation, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", operation)
                or operation in seen):
            raise ValueError("invalid or duplicate operation")
        seen.add(operation)
        table = entry["table"]
        prefix = runtime.backend.schema_namespace + "."
        if (not isinstance(table, str) or not table.startswith(prefix)
                or not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", table[len(prefix):])):
            raise ValueError("query outside backend namespace")
        columns = entry["columnTypes"]
        if (not isinstance(columns, dict) or not 1 <= len(columns) <= 64
                or any(not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", name)
                       or kind not in ("int8", "text", "bool") for name, kind in columns.items())
                or type(entry["limit"]) is not int or not 1 <= entry["limit"] <= 500):
            raise ValueError("invalid query type or limit contract")
        path = entry["sqlPath"]
        if not isinstance(path, str):
            raise ValueError("invalid SQL artifact path")
        _path(path, "artifacts", ".sql")
        sql_raw, digest = verified(path)
        validate_select_template(sql_raw, expected_hash=digest,
            tables={table: frozenset(columns)}, parameter_count=1)
        admitted.append(AdmittedQuery(operation, sql_raw, digest, table, tuple(sorted(columns.items())),
            entry["limit"], record.content_hash, approved.signature_fingerprint, approved.release_evidence_revision))
    return tuple(admitted)


def admit_runtime_artifact(*, record, selected: ResolvedBundle, policy, checked_at,
                           read_artifact, platform, driver):
    selected=ResolvedBundle.model_validate(selected)
    metadata=record.manifest.metadata
    if (record.publisher,metadata.id,metadata.version,record.content_hash) != (
            selected.publisher,selected.id,selected.version,selected.content_hash):
        raise ValueError("release does not match exact composition lock")
    approved=policy.evaluate(record,checked_at=checked_at,
        expected_signature_fingerprint=selected.signature_fingerprint,
        expected_evidence_revision=selected.release_evidence_revision)
    runtime=record.manifest.spec.runtime
    if runtime is None or runtime.backend is None:
        raise ValueError("release has no backend runtime")
    artifacts={item["relativePath"]:item for item in record.artifacts}
    if len(artifacts)!=len(record.artifacts):
        raise ValueError("duplicate artifact paths")

    def verified_bytes(path,limit):
        item=artifacts.get(path)
        if item is None or type(item["size"]) is not int or not 0 <= item["size"] <= limit:
            raise ValueError("artifact missing or oversized")
        raw=read_artifact(path,limit)
        if not isinstance(raw,bytes) or len(raw)!=item["size"] or "sha256:"+hashlib.sha256(raw).hexdigest()!=item["digest"]:
            raise ValueError("artifact bytes differ from signed release")
        return raw

    index_path=runtime.backend.image_index
    raw=verified_bytes(index_path,65536)
    image=resolve_image_index(raw,expected_hash=artifacts[index_path]["digest"],platform=platform)
    lock=verified_bytes("artifacts/python-dependencies.lock",1024*1024)
    if "sha256:"+hashlib.sha256(lock).hexdigest()!=image.dependency_lock_hash:
        raise ValueError("Python dependency lock mismatch")
    sbom=verified_bytes(image.sbom_path,1024*1024)
    if not isinstance(json.loads(sbom,object_pairs_hook=_pairs),dict):
        raise ValueError("invalid SBOM object")
    if not any(item.type==BundleEvidenceType.SBOM and item.artifact_hash==artifacts[image.sbom_path]["digest"]
               for item in record.evidence):
        raise ValueError("SBOM evidence does not reference the selected artifact")
    image_id=require_cached_image(driver,image)
    return AdmittedRuntimeArtifact(image_id,record.content_hash,approved.signature_fingerprint,approved.release_evidence_revision)

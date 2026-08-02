"""Fail-closed loader for allowlisted, non-executable asset bundle directories."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import yaml
from pydantic import ValidationError

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.asset_registry.contracts import (
    BUNDLE_ID_PATTERN,
    BundleArtifact,
    BundleEvidence,
    BundleManifest,
    BundleSignature,
    LoadedBundle,
)
from aos_api.asset_registry.errors import ManifestInvalidError
from aos_api.asset_registry.signature import TrustRootProvider, verify_ed25519

MANIFEST_FILENAME: Final = "bundle.yaml"
SIGNATURE_FILENAME: Final = "bundle.signature.json"
SBOM_RELATIVE_PATH: Final = "evidence/sbom.json"
BUNDLE_EVALS_RELATIVE_PATH: Final = "evidence/bundle-evals.json"

_SENSITIVE_FILENAMES: Final = {
    ".env",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}
_SENSITIVE_SUFFIXES: Final = {".key", ".p12", ".pfx", ".pkcs12"}
_PRIVATE_KEY_MARKERS: Final = (
    b"-----begin private key-----",
    b"-----begin encrypted private key-----",
    b"-----begin rsa private key-----",
    b"-----begin ec private key-----",
    b"-----begin openssh private key-----",
)
_DATABASE_URL_MARKERS: Final = (
    b"postgres://",
    b"postgresql://",
    b"mysql://",
    b"mariadb://",
    b"mongodb://",
    b"redis://",
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?:^|[,{;\n]\s*)[\"']?"
    r"(?:password|passwd|token|access[_-]?token|refresh[_-]?token|"
    r"api[_-]?key|private[_-]?key|database[_-]?url|db[_-]?url|secretref)"
    r"[\"']?\s*[:=]\s*(?!null\b|~\s*(?:[,;}\n]|$)|[\"']{2})\S+",
)
_BEARER_ASSIGNMENT = re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+\S+")


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects ambiguous duplicate mapping keys."""

    def construct_mapping(self, node: yaml.nodes.MappingNode, deep: bool = False):
        if not isinstance(node, yaml.nodes.MappingNode):
            raise yaml.constructor.ConstructorError(
                None, None, "expected a mapping node", node.start_mark
            )
        self.flatten_mapping(node)
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found an unhashable key",
                    key_node.start_mark,
                ) from exc
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


class ManifestLoader:
    """Load a bundle from a configured root without executing bundle content."""

    MAX_MANIFEST_BYTES = 256 * 1024
    MAX_SIGNATURE_BYTES = 16 * 1024
    MAX_EVIDENCE_BYTES = 1024 * 1024
    MAX_BUNDLE_FILES = 20_000
    MAX_FILE_BYTES = 64 * 1024 * 1024
    MAX_TOTAL_BYTES = 512 * 1024 * 1024

    def __init__(
        self,
        allowlist_roots: Mapping[str, Path],
        trust_roots: TrustRootProvider | None = None,
    ) -> None:
        roots: dict[str, Path] = {}
        for alias, configured_root in allowlist_roots.items():
            if (
                not isinstance(alias, str)
                or not re.fullmatch(BUNDLE_ID_PATTERN, alias)
                or len(alias) > 120
            ):
                raise ValueError("allowlist alias is invalid")
            if not isinstance(configured_root, Path):
                raise TypeError("allowlist roots must be pathlib.Path values")
            try:
                root = configured_root.resolve(strict=True)
            except OSError as exc:
                raise ValueError("allowlist root does not exist") from exc
            if not root.is_dir():
                raise ValueError("allowlist root must be a directory")
            roots[alias] = root
        self._allowlist_roots = roots
        self._trust_roots = trust_roots

    def load(self, source_ref: str) -> LoadedBundle:
        """Return server-derived manifest, content index, digest and trust evidence."""

        try:
            alias, relative_parts = self._parse_source_ref(source_ref)
            root = self._allowlist_roots.get(alias)
            if root is None:
                raise ManifestInvalidError("bundle source alias is not allowlisted")
            bundle_root = self._resolve_bundle_root(root, relative_parts)
            files = self._enumerate_files(bundle_root)
            by_relative = {relative: path for relative, path, _size in files}
            manifest_path = by_relative.get(MANIFEST_FILENAME)
            if manifest_path is None:
                raise ManifestInvalidError("bundle.yaml is required")

            manifest_bytes = self._read_regular_file(
                manifest_path,
                relative_path=MANIFEST_FILENAME,
                limit=self.MAX_MANIFEST_BYTES,
            )
            self._scan_sensitive_content(MANIFEST_FILENAME, manifest_bytes)
            manifest = self._parse_manifest(manifest_bytes)
            self._validate_manifest_references(bundle_root, manifest)

            artifacts: list[BundleArtifact] = []
            signature_bytes: bytes | None = None
            evidence_documents: dict[str, bytes] = {}
            for relative_path, path, expected_size in files:
                content = self._read_regular_file(
                    path,
                    relative_path=relative_path,
                    limit=(
                        self.MAX_MANIFEST_BYTES
                        if relative_path == MANIFEST_FILENAME
                        else (
                            self.MAX_SIGNATURE_BYTES
                            if relative_path == SIGNATURE_FILENAME
                            else (
                                self.MAX_EVIDENCE_BYTES
                                if relative_path
                                in {SBOM_RELATIVE_PATH, BUNDLE_EVALS_RELATIVE_PATH}
                                else self.MAX_FILE_BYTES
                            )
                        )
                    ),
                )
                if len(content) != expected_size:
                    raise ManifestInvalidError("bundle file changed while loading")
                self._scan_sensitive_content(relative_path, content)
                if relative_path == MANIFEST_FILENAME:
                    if content != manifest_bytes:
                        raise ManifestInvalidError("bundle.yaml changed while loading")
                    continue
                if relative_path == SIGNATURE_FILENAME:
                    signature_bytes = content
                    continue
                artifacts.append(
                    BundleArtifact.model_validate(
                        {
                            "relativePath": relative_path,
                            "artifactRef": f"{source_ref}/{relative_path}",
                            "digest": self._sha256_bytes(content),
                            "size": len(content),
                            "mediaType": self._media_type(relative_path),
                        }
                    )
                )
                if relative_path in {
                    SBOM_RELATIVE_PATH,
                    BUNDLE_EVALS_RELATIVE_PATH,
                }:
                    evidence_documents[relative_path] = content

            artifacts.sort(key=lambda item: item.relative_path)
            manifest_payload = manifest.model_dump(
                mode="json", by_alias=True, exclude_none=False
            )
            content_descriptor = {
                "manifest": manifest_payload,
                "artifacts": [
                    {
                        "relativePath": item.relative_path,
                        "digest": item.digest,
                        "size": item.size,
                        "mediaType": item.media_type,
                    }
                    for item in artifacts
                ],
            }
            signed_payload = canonical_json(content_descriptor)
            content_hash = canonical_sha256(content_descriptor)
            observed_at = datetime.now(UTC)
            evidence = [
                self._evidence(
                    source_ref=source_ref,
                    evidence_type="manifest_validation",
                    relative_path=MANIFEST_FILENAME,
                    artifact_hash=canonical_sha256(manifest_payload),
                    status="valid",
                    observed_at=observed_at,
                    metadata={"apiVersion": manifest.api_version},
                ),
                self._evidence(
                    source_ref=source_ref,
                    evidence_type="content_hash",
                    relative_path=MANIFEST_FILENAME,
                    artifact_hash=content_hash,
                    status="valid",
                    observed_at=observed_at,
                    metadata={"artifactCount": len(artifacts)},
                ),
            ]
            sbom_bytes = evidence_documents.get(SBOM_RELATIVE_PATH)
            if sbom_bytes is not None:
                evidence.append(
                    self._sbom_evidence(source_ref, sbom_bytes, observed_at)
                )
            evals_bytes = evidence_documents.get(BUNDLE_EVALS_RELATIVE_PATH)
            if evals_bytes is not None:
                evidence.append(
                    self._bundle_evals_evidence(
                        source_ref, evals_bytes, observed_at
                    )
                )
            signature, signature_evidence = self._verify_signature(
                source_ref=source_ref,
                signature_bytes=signature_bytes,
                manifest=manifest,
                signed_payload=signed_payload,
                observed_at=observed_at,
            )
            if signature_evidence is not None:
                evidence.append(signature_evidence)
            return LoadedBundle.model_validate(
                {
                    "sourceRef": source_ref,
                    "manifest": manifest,
                    "artifacts": artifacts,
                    "evidence": evidence,
                    "contentHash": content_hash,
                    "signature": signature,
                    "loadedAt": observed_at,
                }
            )
        except ManifestInvalidError:
            raise
        except (OSError, ValueError, TypeError, ValidationError, yaml.YAMLError) as exc:
            raise ManifestInvalidError("bundle source failed safe loading") from exc

    def _parse_source_ref(self, source_ref: str) -> tuple[str, tuple[str, ...]]:
        if (
            not isinstance(source_ref, str)
            or not source_ref
            or source_ref != source_ref.strip()
            or not source_ref.startswith("bundle://")
            or any(marker in source_ref for marker in ("\\", "?", "#", "%", "\x00"))
        ):
            raise ManifestInvalidError("bundle source reference is invalid")
        remainder = source_ref.removeprefix("bundle://")
        if "/" not in remainder:
            raise ManifestInvalidError("bundle source reference requires alias and path")
        alias, relative = remainder.split("/", 1)
        if not alias or not relative or not re.fullmatch(BUNDLE_ID_PATTERN, alias):
            raise ManifestInvalidError("bundle source reference is invalid")
        parts = tuple(relative.split("/"))
        if any(part in {"", ".", ".."} for part in parts):
            raise ManifestInvalidError("bundle source path traversal is forbidden")
        return alias, parts

    @staticmethod
    def _resolve_bundle_root(root: Path, relative_parts: tuple[str, ...]) -> Path:
        cursor = root
        try:
            for part in relative_parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise ManifestInvalidError("symbolic links are forbidden")
            resolved = cursor.resolve(strict=True)
        except ManifestInvalidError:
            raise
        except OSError as exc:
            raise ManifestInvalidError("bundle source was not found") from exc
        if not resolved.is_relative_to(root) or not resolved.is_dir():
            raise ManifestInvalidError("bundle source must remain inside its allowlist")
        return resolved

    def _enumerate_files(self, bundle_root: Path) -> list[tuple[str, Path, int]]:
        files: list[tuple[str, Path, int]] = []
        total_size = 0

        def raise_walk_error(error: OSError) -> None:
            raise error

        try:
            for directory, directory_names, filenames in os.walk(
                bundle_root,
                topdown=True,
                onerror=raise_walk_error,
                followlinks=False,
            ):
                directory_path = Path(directory)
                directory_names.sort()
                filenames.sort()
                for name in directory_names:
                    child = directory_path / name
                    relative_path = child.relative_to(bundle_root).as_posix()
                    self._validate_relative_file_path(relative_path)
                    child_stat = child.lstat()
                    if child.is_symlink():
                        raise ManifestInvalidError("symbolic links are forbidden")
                    if not stat.S_ISDIR(child_stat.st_mode):
                        raise ManifestInvalidError(
                            "bundle contains a non-directory path"
                        )
                    if not child.resolve(strict=True).is_relative_to(bundle_root):
                        raise ManifestInvalidError(
                            "bundle content escaped its allowlisted root"
                        )
                for name in filenames:
                    path = directory_path / name
                    relative_path = path.relative_to(bundle_root).as_posix()
                    self._validate_relative_file_path(relative_path)
                    if path.is_symlink():
                        raise ManifestInvalidError("symbolic links are forbidden")
                    resolved = path.resolve(strict=True)
                    if not resolved.is_relative_to(bundle_root):
                        raise ManifestInvalidError(
                            "bundle content escaped its allowlisted root"
                        )
                    file_stat = path.stat(follow_symlinks=False)
                    if not stat.S_ISREG(file_stat.st_mode):
                        raise ManifestInvalidError(
                            "bundle contains a non-regular file"
                        )
                    if file_stat.st_size > self.MAX_FILE_BYTES:
                        raise ManifestInvalidError(
                            "bundle file exceeds the size limit"
                        )
                    files.append((relative_path, path, file_stat.st_size))
                    if len(files) > self.MAX_BUNDLE_FILES:
                        raise ManifestInvalidError(
                            "bundle exceeds the file-count limit"
                        )
                    total_size += file_stat.st_size
                    if total_size > self.MAX_TOTAL_BYTES:
                        raise ManifestInvalidError(
                            "bundle exceeds the total-size limit"
                        )
        except ManifestInvalidError:
            raise
        except OSError as exc:
            raise ManifestInvalidError("bundle content could not be enumerated") from exc
        files.sort(key=lambda item: item[0])
        return files

    @staticmethod
    def _validate_relative_file_path(relative_path: str) -> None:
        if any(marker in relative_path for marker in ("\\", "?", "#", "%", "\x00")):
            raise ManifestInvalidError("bundle contains an unsafe file path")
        if any(part in {"", ".", ".."} for part in relative_path.split("/")):
            raise ManifestInvalidError("bundle contains an unsafe file path")

    @staticmethod
    def _validate_manifest_references(
        bundle_root: Path, manifest: BundleManifest
    ) -> None:
        export_paths = [
            path
            for values in manifest.spec.exports.model_dump(mode="python").values()
            for path in values
        ]
        references = [
            *export_paths,
            manifest.spec.migrations.plan,
            manifest.spec.preflight,
            manifest.spec.regression,
            manifest.spec.rollback,
        ]
        for reference in references:
            if reference is None:
                continue
            parts = reference.removesuffix("/").split("/")
            cursor = bundle_root
            try:
                for part in parts:
                    cursor = cursor / part
                    if cursor.is_symlink():
                        raise ManifestInvalidError("symbolic links are forbidden")
                resolved = cursor.resolve(strict=True)
            except ManifestInvalidError:
                raise
            except OSError as exc:
                raise ManifestInvalidError(
                    "manifest references missing bundle content"
                ) from exc
            if not resolved.is_relative_to(bundle_root):
                raise ManifestInvalidError(
                    "manifest reference escaped its allowlisted bundle"
                )

    @staticmethod
    def _read_regular_file(path: Path, *, relative_path: str, limit: int) -> bytes:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
            with os.fdopen(descriptor, "rb") as handle:
                file_stat = os.fstat(handle.fileno())
                if not stat.S_ISREG(file_stat.st_mode):
                    raise ManifestInvalidError("bundle contains a non-regular file")
                if file_stat.st_size > limit:
                    raise ManifestInvalidError(
                        f"{relative_path} exceeds the size limit"
                    )
                content = handle.read(limit + 1)
        except ManifestInvalidError:
            raise
        except OSError as exc:
            raise ManifestInvalidError("bundle file could not be read safely") from exc
        if len(content) > limit:
            raise ManifestInvalidError(f"{relative_path} exceeds the size limit")
        return content

    @staticmethod
    def _parse_manifest(manifest_bytes: bytes) -> BundleManifest:
        try:
            text = manifest_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ManifestInvalidError("bundle.yaml must be UTF-8") from exc
        try:
            payload = yaml.load(text, Loader=_UniqueKeySafeLoader)
        except yaml.YAMLError as exc:
            raise ManifestInvalidError("bundle.yaml is not valid safe YAML") from exc
        if not isinstance(payload, dict):
            raise ManifestInvalidError("bundle.yaml must contain an object")
        ManifestLoader._scan_sensitive_value(payload)
        try:
            return BundleManifest.model_validate(payload)
        except ValidationError as exc:
            raise ManifestInvalidError(
                "bundle.yaml failed the canonical manifest contract"
            ) from exc

    def _verify_signature(
        self,
        *,
        source_ref: str,
        signature_bytes: bytes | None,
        manifest: BundleManifest,
        signed_payload: bytes,
        observed_at: datetime,
    ) -> tuple[BundleSignature | None, BundleEvidence | None]:
        if signature_bytes is None:
            return None, None
        artifact_hash = self._sha256_bytes(signature_bytes)
        try:
            signature = BundleSignature.model_validate_json(signature_bytes)
        except (ValidationError, ValueError):
            return None, self._evidence(
                source_ref=source_ref,
                evidence_type="signature_verification",
                relative_path=SIGNATURE_FILENAME,
                artifact_hash=artifact_hash,
                status="invalid",
                observed_at=observed_at,
                metadata={"reason": "malformed_signature_envelope"},
            )
        if self._trust_roots is None:
            status = "invalid"
            reason = "trust_roots_unavailable"
        elif verify_ed25519(
            payload=signed_payload,
            signature_b64=signature.signature,
            publisher=manifest.metadata.publisher,
            key_id=signature.key_id,
            trust_roots=self._trust_roots,
            algorithm=signature.algorithm,
            verified_at=observed_at,
        ):
            status = "valid"
            reason = "verified"
        else:
            status = "invalid"
            reason = "verification_failed"
        return signature, self._evidence(
            source_ref=source_ref,
            evidence_type="signature_verification",
            relative_path=SIGNATURE_FILENAME,
            artifact_hash=artifact_hash,
            status=status,
            observed_at=observed_at,
            metadata={"keyId": signature.key_id, "reason": reason},
        )

    @staticmethod
    def _sbom_evidence(
        source_ref: str, content: bytes, observed_at: datetime
    ) -> BundleEvidence:
        status = "invalid"
        metadata: dict[str, str | int] = {"reason": "invalid_sbom"}
        try:
            payload = ManifestLoader._parse_json_object(content)
            format_name = payload.get("format")
            components = payload.get("components")
            if (
                isinstance(format_name, str)
                and bool(format_name)
                and format_name == format_name.strip()
                and len(format_name) <= 120
                and isinstance(components, list)
                and all(isinstance(component, dict) for component in components)
            ):
                status = "valid"
                metadata = {
                    "format": format_name,
                    "componentCount": len(components),
                }
        except (UnicodeDecodeError, ValueError, TypeError):
            pass
        return ManifestLoader._evidence(
            source_ref=source_ref,
            evidence_type="sbom",
            relative_path=SBOM_RELATIVE_PATH,
            artifact_hash=ManifestLoader._sha256_bytes(content),
            status=status,
            observed_at=observed_at,
            metadata=metadata,
        )

    @staticmethod
    def _bundle_evals_evidence(
        source_ref: str, content: bytes, observed_at: datetime
    ) -> BundleEvidence:
        status = "invalid"
        metadata: dict[str, str | int] = {"reason": "bundle_evals_not_passed"}
        try:
            payload = ManifestLoader._parse_json_object(content)
            report_status = payload.get("status")
            failed = payload.get("failed")
            if report_status == "passed" and type(failed) is int and failed == 0:
                status = "valid"
                metadata = {"status": "passed", "failed": 0}
        except (UnicodeDecodeError, ValueError, TypeError):
            pass
        return ManifestLoader._evidence(
            source_ref=source_ref,
            evidence_type="bundle_evals",
            relative_path=BUNDLE_EVALS_RELATIVE_PATH,
            artifact_hash=ManifestLoader._sha256_bytes(content),
            status=status,
            observed_at=observed_at,
            metadata=metadata,
        )

    @staticmethod
    def _parse_json_object(content: bytes) -> dict:
        def unique_object(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate JSON object key")
                value[key] = item
            return value

        payload = json.loads(content.decode("utf-8"), object_pairs_hook=unique_object)
        if not isinstance(payload, dict):
            raise TypeError("evidence document must be a JSON object")
        return payload

    @staticmethod
    def _scan_sensitive_value(value: object, *, path: str = "$") -> None:
        if isinstance(value, dict):
            for raw_key, item in value.items():
                key = str(raw_key)
                normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
                if normalized_key in {
                    "password",
                    "passwd",
                    "token",
                    "accesstoken",
                    "refreshtoken",
                    "apikey",
                    "privatekey",
                    "databaseurl",
                    "dburl",
                    "secretref",
                } and item is not None and item != "":
                    raise ManifestInvalidError(
                        "bundle manifest contains a forbidden sensitive value",
                        details={"path": f"{path}.{key}"},
                    )
                ManifestLoader._scan_sensitive_value(item, path=f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                ManifestLoader._scan_sensitive_value(item, path=f"{path}[{index}]")
        elif isinstance(value, str):
            lowered = value.lower().encode("utf-8", errors="ignore")
            if any(marker in lowered for marker in _DATABASE_URL_MARKERS):
                raise ManifestInvalidError(
                    "bundle manifest contains a forbidden database URL",
                    details={"path": path},
                )

    @staticmethod
    def _scan_sensitive_content(relative_path: str, content: bytes) -> None:
        lowered_name = Path(relative_path).name.lower()
        if (
            lowered_name in _SENSITIVE_FILENAMES
            or lowered_name.startswith(".env.")
            or Path(lowered_name).suffix in _SENSITIVE_SUFFIXES
        ):
            raise ManifestInvalidError("bundle contains a forbidden sensitive file")
        lowered = content.lower()
        if any(marker in lowered for marker in _PRIVATE_KEY_MARKERS):
            raise ManifestInvalidError("bundle contains private key material")
        if any(marker in lowered for marker in _DATABASE_URL_MARKERS):
            raise ManifestInvalidError("bundle contains a database URL")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return
        if _SECRET_ASSIGNMENT.search(text) or _BEARER_ASSIGNMENT.search(text):
            raise ManifestInvalidError("bundle contains a sensitive value")

    @staticmethod
    def _evidence(
        *,
        source_ref: str,
        evidence_type: str,
        relative_path: str,
        artifact_hash: str,
        status: str,
        observed_at: datetime,
        metadata: dict[str, str | int],
    ) -> BundleEvidence:
        return BundleEvidence.model_validate(
            {
                "type": evidence_type,
                "artifactRef": f"{source_ref}/{relative_path}",
                "artifactHash": artifact_hash,
                "status": status,
                "observedAt": observed_at,
                "expiresAt": None,
                "revokedAt": None,
                "metadata": metadata,
            }
        )

    @staticmethod
    def _sha256_bytes(content: bytes) -> str:
        return f"sha256:{hashlib.sha256(content).hexdigest()}"

    @staticmethod
    def _media_type(relative_path: str) -> str:
        suffix = Path(relative_path).suffix.lower()
        overrides = {
            ".css": "text/css",
            ".csv": "text/csv",
            ".html": "text/html",
            ".js": "text/javascript",
            ".json": "application/json",
            ".md": "text/markdown",
            ".py": "text/x-python",
            ".sql": "application/sql",
            ".svg": "image/svg+xml",
            ".ts": "text/typescript",
            ".tsx": "text/typescript-jsx",
            ".txt": "text/plain",
            ".yaml": "application/yaml",
            ".yml": "application/yaml",
        }
        return overrides.get(suffix, "application/octet-stream")

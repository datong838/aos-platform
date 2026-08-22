"""Fail-closed loader for allowlisted, non-executable asset bundle directories."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
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
    LegacyWorkshopMigrationInput,
    LoadedBundle,
    UiContributionClaim,
    NavigationContributionClaim,
    WorkshopModuleContribution,
)
from aos_api.asset_registry.errors import ManifestInvalidError
from aos_api.asset_registry.signature import (
    TrustRoot,
    TrustRootProvider,
    verify_ed25519,
)

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
    r"[\"']?\s*[:=]\s*(?!null\b|~\s*(?:[,;}\n]|$)|[\"']{2}|\{)\S+",
)
_BEARER_ASSIGNMENT = re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+\S+")

_ANALYST_TEMPLATE_DOCUMENT_FIELDS: Final = {
    "schemaVersion",
    "bundleRef",
    "templates",
}
_ANALYST_TEMPLATE_FIELDS: Final = {
    "templateId",
    "revision",
    "roleId",
    "roleName",
    "queryKind",
    "defaultObjectType",
    "defaultPrompt",
    "requiredObjectTypes",
    "requiredLogicIds",
    "sourceDataTypes",
    "purpose",
    "policy",
}


@dataclass(frozen=True)
class _BundleFile:
    relative_path: str
    size: int
    device: int
    inode: int
    modified_ns: int
    changed_ns: int


class _PinnedTrustRootProvider:
    def __init__(self, root: TrustRoot) -> None:
        self._root = root

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None:
        if (publisher, key_id) == (self._root.publisher, self._root.key_id):
            return self._root
        return None


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
        root_identities: dict[str, tuple[int, int]] = {}
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
            root_stat = root.stat(follow_symlinks=False)
            roots[alias] = root
            root_identities[alias] = (root_stat.st_dev, root_stat.st_ino)
        self._allowlist_roots = roots
        self._allowlist_root_identities = root_identities
        self._trust_roots = trust_roots

    @property
    def trust_roots(self) -> TrustRootProvider | None:
        """Expose the same read-only provider used for load-time verification."""

        return self._trust_roots

    def load(self, source_ref: str) -> LoadedBundle:
        """Return server-derived manifest, content index, digest and trust evidence."""

        try:
            alias, relative_parts = self._parse_source_ref(source_ref)
            root = self._allowlist_roots.get(alias)
            if root is None:
                raise ManifestInvalidError("bundle source alias is not allowlisted")
            root_identity = self._allowlist_root_identities[alias]
            with self._open_bundle_directory(
                root, root_identity, relative_parts
            ) as bundle_descriptor:
                files, available_paths = self._enumerate_files(bundle_descriptor)
                by_relative = {item.relative_path: item for item in files}
                manifest_file = by_relative.get(MANIFEST_FILENAME)
                if manifest_file is None:
                    raise ManifestInvalidError("bundle.yaml is required")

                manifest_bytes = self._read_regular_file(
                    bundle_descriptor,
                    manifest_file,
                    limit=self.MAX_MANIFEST_BYTES,
                )
                self._scan_sensitive_content(MANIFEST_FILENAME, manifest_bytes)
                manifest = self._parse_manifest(manifest_bytes)
                self._validate_manifest_references(available_paths, manifest)

                artifacts: list[BundleArtifact] = []
                signature_bytes: bytes | None = None
                evidence_documents: dict[str, bytes] = {}
                workshop_documents: dict[str, bytes] = {}
                for item in files:
                    relative_path = item.relative_path
                    content = self._read_regular_file(
                        bundle_descriptor,
                        item,
                        limit=(
                            self.MAX_MANIFEST_BYTES
                            if relative_path == MANIFEST_FILENAME
                            else (
                                self.MAX_SIGNATURE_BYTES
                                if relative_path == SIGNATURE_FILENAME
                                else (
                                    self.MAX_EVIDENCE_BYTES
                                    if relative_path
                                    in {
                                        SBOM_RELATIVE_PATH,
                                        BUNDLE_EVALS_RELATIVE_PATH,
                                    }
                                    else self.MAX_FILE_BYTES
                                )
                            )
                        ),
                    )
                    self._scan_sensitive_content(relative_path, content)
                    if relative_path == MANIFEST_FILENAME:
                        if content != manifest_bytes:
                            raise ManifestInvalidError(
                                "bundle.yaml changed while loading"
                            )
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
                    if self._is_exported_path(
                        relative_path, manifest.spec.exports.workshops
                    ):
                        workshop_documents[relative_path] = content
                final_files, final_paths = self._enumerate_files(bundle_descriptor)
                if final_files != files or final_paths != available_paths:
                    raise ManifestInvalidError("bundle content changed while loading")

            workshop_modules, legacy_workshops = self._parse_workshop_assets(
                manifest=manifest,
                available_paths=available_paths,
                documents=workshop_documents,
            )

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
                    self._bundle_evals_evidence(source_ref, evals_bytes, observed_at)
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
                    "workshopModules": workshop_modules,
                    "legacyWorkshops": legacy_workshops,
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

    @staticmethod
    def _is_exported_path(relative_path: str, exports: list[str]) -> bool:
        return any(
            relative_path.startswith(export_path)
            if export_path.endswith("/")
            else relative_path == export_path
            for export_path in exports
        )

    @staticmethod
    def _parse_workshop_assets(
        *,
        manifest: BundleManifest,
        available_paths: frozenset[str],
        documents: Mapping[str, bytes],
    ) -> tuple[
        list[WorkshopModuleContribution],
        list[LegacyWorkshopMigrationInput],
    ]:
        modules: list[WorkshopModuleContribution] = []
        legacy: list[LegacyWorkshopMigrationInput] = []
        for relative_path, content in sorted(documents.items()):
            if not relative_path.endswith(".json"):
                raise ManifestInvalidError("Workshop exports must contain JSON assets")
            try:
                payload = ManifestLoader._parse_json_object(content)
                ManifestLoader._scan_sensitive_value(payload)
                if ManifestLoader._parse_analyst_query_template_asset(
                    manifest=manifest,
                    payload=payload,
                ):
                    continue
                if "schema" in payload:
                    module = WorkshopModuleContribution.model_validate(payload)
                    if Path(relative_path).stem != module.module_id:
                        raise ManifestInvalidError(
                            "Workshop module filename must match moduleId"
                        )
                    ManifestLoader._validate_workshop_module_binding(
                        manifest=manifest,
                        available_paths=available_paths,
                        module=module,
                    )
                    modules.append(module)
                else:
                    legacy.append(
                        ManifestLoader._parse_legacy_workshop(
                            relative_path=relative_path,
                            payload=payload,
                        )
                    )
            except ManifestInvalidError:
                raise
            except (UnicodeDecodeError, ValueError, TypeError, ValidationError) as exc:
                raise ManifestInvalidError(
                    f"Workshop asset {relative_path} failed the canonical contract"
                ) from exc

        module_ids = [item.module_id for item in modules]
        routes = [item.route for item in modules]
        orders = [item.order for item in modules]
        legacy_ids = [item.legacy_id for item in legacy]
        if len(module_ids) != len(set(module_ids)):
            raise ManifestInvalidError("Workshop module ids must be unique")
        if len(routes) != len(set(routes)):
            raise ManifestInvalidError("Workshop module routes must be unique")
        if len(orders) != len(set(orders)):
            raise ManifestInvalidError("Workshop module order values must be unique")
        if len(legacy_ids) != len(set(legacy_ids)):
            raise ManifestInvalidError("legacy Workshop ids must be unique")
        return modules, legacy

    @staticmethod
    def _parse_analyst_query_template_asset(
        *, manifest: BundleManifest, payload: dict
    ) -> bool:
        """Recognize the immutable 1.3.0 Analyst auxiliary asset strictly.

        The historical SolutionPack exported this read-only AIP catalog from its
        Workshop directory.  It is an artifact of the installed bundle, but it
        must never become a Workshop module projection.  Unknown JSON remains
        fail-closed in ``_parse_legacy_workshop``.
        """

        if set(payload) != _ANALYST_TEMPLATE_DOCUMENT_FIELDS:
            return False
        expected_bundle_ref = (
            f"bundle://{manifest.metadata.publisher}/"
            f"{manifest.metadata.id}@{manifest.metadata.version}"
        )
        templates = payload.get("templates")
        if (
            payload.get("schemaVersion") != 1
            or payload.get("bundleRef") != expected_bundle_ref
            or not isinstance(templates, list)
            or not templates
        ):
            raise ManifestInvalidError("Analyst query template document is invalid")

        template_ids: list[str] = []
        role_ids: list[str] = []
        for item in templates:
            if not isinstance(item, dict) or set(item) != _ANALYST_TEMPLATE_FIELDS:
                raise ManifestInvalidError("Analyst query template fields drifted")
            scalar_fields = (
                "templateId",
                "roleId",
                "roleName",
                "queryKind",
                "defaultObjectType",
                "purpose",
                "policy",
            )
            if any(
                not isinstance(item.get(field), str) or not item[field].strip()
                for field in scalar_fields
            ):
                raise ManifestInvalidError("Analyst query template scalar is invalid")
            if not isinstance(item.get("defaultPrompt"), str):
                raise ManifestInvalidError("Analyst query template prompt is invalid")
            revision = item.get("revision")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
                raise ManifestInvalidError("Analyst query template revision is invalid")
            for field in (
                "requiredObjectTypes",
                "requiredLogicIds",
                "sourceDataTypes",
            ):
                values = item.get(field)
                if (
                    not isinstance(values, list)
                    or not values
                    or any(not isinstance(value, str) or not value.strip() for value in values)
                    or len(values) != len(set(values))
                ):
                    raise ManifestInvalidError(
                        f"Analyst query template {field} is invalid"
                    )
            if item["queryKind"] != "semantic" or item["policy"] != "canonical-read-only":
                raise ManifestInvalidError("Analyst query template is not read-only")
            if item["defaultObjectType"] not in item["requiredObjectTypes"]:
                raise ManifestInvalidError(
                    "Analyst query template default Object Type is not required"
                )
            template_ids.append(item["templateId"])
            role_ids.append(item["roleId"])

        if len(template_ids) != len(set(template_ids)) or len(role_ids) != len(set(role_ids)):
            raise ManifestInvalidError("Analyst query template identity is duplicated")
        return True

    @staticmethod
    def _validate_workshop_module_binding(
        *,
        manifest: BundleManifest,
        available_paths: frozenset[str],
        module: WorkshopModuleContribution,
    ) -> None:
        expected_bundle_ref = (
            f"bundle://{manifest.metadata.publisher}/"
            f"{manifest.metadata.id}@{manifest.metadata.version}"
        )
        if module.bundle_ref != expected_bundle_ref:
            raise ManifestInvalidError("Workshop bundleRef does not match its manifest")

        has_route_claim = any(
            isinstance(claim, NavigationContributionClaim)
            and claim.route == module.route
            and claim.mode == "exclusive"
            for claim in manifest.spec.contributions
        )
        has_ui_claim = any(
            isinstance(claim, UiContributionClaim)
            and claim.slot == module.slot
            and claim.id == module.module_id
            and claim.mode == "exclusive"
            for claim in manifest.spec.contributions
        )
        if not has_route_claim or not has_ui_claim:
            raise ManifestInvalidError(
                "Workshop module must bind exclusive navigation and UI claims"
            )

        references = [
            *module.view_refs,
            *module.eval_pack_refs,
            *module.production_contract_refs,
            *module.responsibility_template_refs,
            *module.impact_calculator_refs,
            *module.legacy_asset_refs,
        ]
        if any(reference not in available_paths for reference in references):
            raise ManifestInvalidError("Workshop module references missing bundle content")

    @staticmethod
    def _parse_legacy_workshop(
        *, relative_path: str, payload: dict
    ) -> LegacyWorkshopMigrationInput:
        allowed_top_level = {
            "workshop_id",
            "title",
            "route",
            "widgets",
            "decision_tags",
            "decision_tags_contract",
            "status",
            "note",
        }
        if set(payload).difference(allowed_top_level):
            raise ManifestInvalidError("legacy Workshop contains unknown fields")
        legacy_id = payload.get("workshop_id")
        route = payload.get("route")
        if (
            not isinstance(legacy_id, str)
            or not re.fullmatch(BUNDLE_ID_PATTERN, legacy_id)
            or not isinstance(route, str)
            or not route.startswith("workshop/")
        ):
            raise ManifestInvalidError("unknown unschematized Workshop asset")
        widgets = payload.get("widgets")
        if not isinstance(widgets, list) or not widgets:
            raise ManifestInvalidError("legacy Workshop requires widgets")
        allowed_widget_fields = {
            "id",
            "title",
            "source_ot",
            "aggregator",
            "filter",
            "description",
            "decision_tag_ref",
        }
        widget_ids: list[str] = []
        required_objects: list[str] = []
        for widget in widgets:
            if not isinstance(widget, dict) or set(widget).difference(
                allowed_widget_fields
            ):
                raise ManifestInvalidError("legacy Workshop widget is invalid")
            widget_id = widget.get("id")
            title = widget.get("title")
            source_ot = widget.get("source_ot")
            if not all(
                isinstance(value, str) and value and value == value.strip()
                for value in (widget_id, title, source_ot)
            ):
                raise ManifestInvalidError("legacy Workshop widget is incomplete")
            widget_ids.append(widget_id)
            for object_id in source_ot.split("+"):
                if object_id not in required_objects:
                    required_objects.append(object_id)
        return LegacyWorkshopMigrationInput.model_validate(
            {
                "sourcePath": relative_path,
                "legacyId": legacy_id,
                "title": payload.get("title"),
                "route": f"/{route}",
                "widgetIds": widget_ids,
                "requiredObjects": required_objects,
            }
        )

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
            raise ManifestInvalidError(
                "bundle source reference requires alias and path"
            )
        alias, relative = remainder.split("/", 1)
        if not alias or not relative or not re.fullmatch(BUNDLE_ID_PATTERN, alias):
            raise ManifestInvalidError("bundle source reference is invalid")
        parts = tuple(relative.split("/"))
        if any(part in {"", ".", ".."} for part in parts):
            raise ManifestInvalidError("bundle source path traversal is forbidden")
        return alias, parts

    @staticmethod
    @contextmanager
    def _open_bundle_directory(
        root: Path,
        root_identity: tuple[int, int],
        relative_parts: tuple[str, ...],
    ) -> Iterator[int]:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor: int | None = None
        try:
            descriptor = os.open(root, flags)
            root_stat = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(root_stat.st_mode)
                or (
                    root_stat.st_dev,
                    root_stat.st_ino,
                )
                != root_identity
            ):
                raise ManifestInvalidError("allowlist root changed while loading")
            for part in relative_parts:
                child = os.open(part, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
                child_stat = os.fstat(descriptor)
                if not stat.S_ISDIR(child_stat.st_mode):
                    raise ManifestInvalidError(
                        "bundle source must remain inside its allowlist"
                    )
            yield descriptor
        except ManifestInvalidError:
            raise
        except OSError as exc:
            raise ManifestInvalidError(
                "symbolic links are forbidden or bundle source was not found"
            ) from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def _enumerate_files(
        self, bundle_descriptor: int
    ) -> tuple[list[_BundleFile], frozenset[str]]:
        files: list[_BundleFile] = []
        available_paths: set[str] = set()
        total_size = 0

        try:
            directory_flags = (
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )

            def walk(directory_descriptor: int, prefix: str) -> None:
                nonlocal total_size
                for name in sorted(os.listdir(directory_descriptor)):
                    relative_path = f"{prefix}/{name}" if prefix else name
                    self._validate_relative_file_path(relative_path)
                    child_stat = os.stat(
                        name,
                        dir_fd=directory_descriptor,
                        follow_symlinks=False,
                    )
                    if stat.S_ISLNK(child_stat.st_mode):
                        raise ManifestInvalidError("symbolic links are forbidden")
                    if stat.S_ISDIR(child_stat.st_mode):
                        child_descriptor = os.open(
                            name,
                            directory_flags,
                            dir_fd=directory_descriptor,
                        )
                        try:
                            opened_stat = os.fstat(child_descriptor)
                            if not stat.S_ISDIR(opened_stat.st_mode) or (
                                opened_stat.st_dev,
                                opened_stat.st_ino,
                            ) != (child_stat.st_dev, child_stat.st_ino):
                                raise ManifestInvalidError(
                                    "bundle directory changed while loading"
                                )
                            available_paths.add(relative_path)
                            walk(child_descriptor, relative_path)
                        finally:
                            os.close(child_descriptor)
                        continue
                    if not stat.S_ISREG(child_stat.st_mode):
                        raise ManifestInvalidError("bundle contains a non-regular file")
                    if child_stat.st_size > self.MAX_FILE_BYTES:
                        raise ManifestInvalidError("bundle file exceeds the size limit")
                    files.append(
                        _BundleFile(
                            relative_path=relative_path,
                            size=child_stat.st_size,
                            device=child_stat.st_dev,
                            inode=child_stat.st_ino,
                            modified_ns=child_stat.st_mtime_ns,
                            changed_ns=child_stat.st_ctime_ns,
                        )
                    )
                    available_paths.add(relative_path)
                    if len(files) > self.MAX_BUNDLE_FILES:
                        raise ManifestInvalidError(
                            "bundle exceeds the file-count limit"
                        )
                    total_size += child_stat.st_size
                    if total_size > self.MAX_TOTAL_BYTES:
                        raise ManifestInvalidError(
                            "bundle exceeds the total-size limit"
                        )

            walk(bundle_descriptor, "")
        except ManifestInvalidError:
            raise
        except OSError as exc:
            raise ManifestInvalidError(
                "bundle content could not be enumerated"
            ) from exc
        files.sort(key=lambda item: item.relative_path)
        return files, frozenset(available_paths)

    @staticmethod
    def _validate_relative_file_path(relative_path: str) -> None:
        if any(marker in relative_path for marker in ("\\", "?", "#", "%", "\x00")):
            raise ManifestInvalidError("bundle contains an unsafe file path")
        if any(part in {"", ".", ".."} for part in relative_path.split("/")):
            raise ManifestInvalidError("bundle contains an unsafe file path")
        try:
            relative_path.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ManifestInvalidError("bundle contains an unsafe file path") from exc

    @staticmethod
    def _validate_manifest_references(
        available_paths: frozenset[str], manifest: BundleManifest
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
            if reference.removesuffix("/") not in available_paths:
                raise ManifestInvalidError("manifest references missing bundle content")

    @staticmethod
    def _read_regular_file(
        bundle_descriptor: int,
        item: _BundleFile,
        *,
        limit: int,
    ) -> bytes:
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        file_flags = (
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        parent_descriptor: int | None = None
        file_descriptor: int | None = None
        try:
            parent_descriptor = os.dup(bundle_descriptor)
            parts = item.relative_path.split("/")
            for part in parts[:-1]:
                child_descriptor = os.open(
                    part,
                    directory_flags,
                    dir_fd=parent_descriptor,
                )
                os.close(parent_descriptor)
                parent_descriptor = child_descriptor
            file_descriptor = os.open(
                parts[-1],
                file_flags,
                dir_fd=parent_descriptor,
            )
            with os.fdopen(file_descriptor, "rb") as handle:
                file_descriptor = None
                file_stat = os.fstat(handle.fileno())
                if not stat.S_ISREG(file_stat.st_mode):
                    raise ManifestInvalidError("bundle contains a non-regular file")
                if not ManifestLoader._matches_file_snapshot(file_stat, item):
                    raise ManifestInvalidError("bundle file changed while loading")
                if file_stat.st_size > limit:
                    raise ManifestInvalidError(
                        f"{item.relative_path} exceeds the size limit"
                    )
                content = handle.read(limit + 1)
                final_stat = os.fstat(handle.fileno())
                if not ManifestLoader._matches_file_snapshot(final_stat, item):
                    raise ManifestInvalidError("bundle file changed while loading")
        except ManifestInvalidError:
            raise
        except OSError as exc:
            raise ManifestInvalidError("bundle file could not be read safely") from exc
        finally:
            if file_descriptor is not None:
                os.close(file_descriptor)
            if parent_descriptor is not None:
                os.close(parent_descriptor)
        if len(content) > limit:
            raise ManifestInvalidError(f"{item.relative_path} exceeds the size limit")
        return content

    @staticmethod
    def _matches_file_snapshot(file_stat: os.stat_result, item: _BundleFile) -> bool:
        return (
            stat.S_ISREG(file_stat.st_mode)
            and file_stat.st_dev == item.device
            and file_stat.st_ino == item.inode
            and file_stat.st_size == item.size
            and file_stat.st_mtime_ns == item.modified_ns
            and file_stat.st_ctime_ns == item.changed_ns
        )

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
        artifact_hash = canonical_sha256(
            signature.model_dump(mode="json", by_alias=True, exclude_none=False)
        )
        trust_root: TrustRoot | None = None
        trust_root_unavailable = False
        if self._trust_roots is not None:
            try:
                trust_root = self._trust_roots.get_trust_root(
                    publisher=manifest.metadata.publisher,
                    key_id=signature.key_id,
                )
            except Exception:  # noqa: BLE001 - provider outages fail closed
                trust_root_unavailable = True

        if trust_root_unavailable:
            status = "invalid"
            reason = "trust_root_provider_unavailable"
        elif self._trust_roots is None:
            status = "invalid"
            reason = "trust_roots_unavailable"
        elif trust_root is None:
            status = "invalid"
            reason = "verification_failed"
        elif verify_ed25519(
            payload=signed_payload,
            signature_b64=signature.signature,
            publisher=manifest.metadata.publisher,
            key_id=signature.key_id,
            trust_roots=_PinnedTrustRootProvider(trust_root),
            algorithm=signature.algorithm,
            verified_at=observed_at,
        ):
            status = "valid"
            reason = "verified"
        else:
            status = "invalid"
            reason = "verification_failed"
        metadata = {
            "keyId": signature.key_id,
            "reason": reason,
            "signatureHashProfile": "canonical-envelope-v1",
        }
        if trust_root is not None:
            metadata["trustRootRevision"] = trust_root.revision
        evidence_expiry = None
        if (
            trust_root is not None
            and trust_root.not_after is not None
            and trust_root.not_after.utcoffset() is not None
            and trust_root.not_after > observed_at
        ):
            evidence_expiry = trust_root.not_after
        return signature, self._evidence(
            source_ref=source_ref,
            evidence_type="signature_verification",
            relative_path=SIGNATURE_FILENAME,
            artifact_hash=artifact_hash,
            status=status,
            observed_at=observed_at,
            expires_at=evidence_expiry,
            metadata=metadata,
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
                if (
                    normalized_key
                    in {
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
                    }
                    and item is not None
                    and item != ""
                ):
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
        expires_at: datetime | None = None,
    ) -> BundleEvidence:
        return BundleEvidence.model_validate(
            {
                "type": evidence_type,
                "artifactRef": f"{source_ref}/{relative_path}",
                "artifactHash": artifact_hash,
                "status": status,
                "observedAt": observed_at,
                "expiresAt": expires_at,
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

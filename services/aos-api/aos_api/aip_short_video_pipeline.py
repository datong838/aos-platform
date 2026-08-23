"""Pure, fail-closed planning contracts for AIP short-video MediaJobs.

This module never invokes FFmpeg, TTS, a Provider, or a filesystem writer.  It
only validates exact authorities and returns a shell-free argv plan that a
separately leased executor may use after all operational gates are GREEN.
"""
from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Mapping

from pydantic import Field, model_validator

from aos_api.aip_content_contracts import MediaAssetRef, MediaType
from aos_api.aip_contracts import AipContractModel, ArtifactRef, ResourceRef
from aos_api.aip_production_contracts import ContractReadiness, ExactRevisionRef


class ShortVideoAssetRole(StrEnum):
    PRODUCT_IMAGE = "product_image"
    VOICEOVER = "voiceover"
    SUBTITLE = "subtitle"
    BGM = "bgm"
    FONT = "font"


_ROLE_TYPES = {
    ShortVideoAssetRole.PRODUCT_IMAGE: MediaType.IMAGE,
    ShortVideoAssetRole.VOICEOVER: MediaType.AUDIO,
    ShortVideoAssetRole.SUBTITLE: MediaType.SUBTITLE,
    ShortVideoAssetRole.BGM: MediaType.AUDIO,
    ShortVideoAssetRole.FONT: MediaType.FONT,
}
_REQUIRED_ROLES = {
    ShortVideoAssetRole.PRODUCT_IMAGE,
    ShortVideoAssetRole.VOICEOVER,
    ShortVideoAssetRole.SUBTITLE,
}
_SINGLE_ROLES = {
    ShortVideoAssetRole.PRODUCT_IMAGE,
    ShortVideoAssetRole.VOICEOVER,
    ShortVideoAssetRole.SUBTITLE,
    ShortVideoAssetRole.BGM,
    ShortVideoAssetRole.FONT,
}


class ShortVideoAsset(AipContractModel):
    role: ShortVideoAssetRole
    asset: MediaAssetRef

    @model_validator(mode="after")
    def _role_type(self) -> "ShortVideoAsset":
        if self.asset.media_type is not _ROLE_TYPES[self.role]:
            raise ValueError("asset role media type does not match")
        return self


class SubtitleCue(AipContractModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _positive_interval(self) -> "SubtitleCue":
        if self.end_ms <= self.start_ms:
            raise ValueError("subtitle cue end must be after start")
        return self


class VideoCanvas(AipContractModel):
    width: int = Field(ge=320, le=7680)
    height: int = Field(ge=320, le=7680)
    fps: int = Field(ge=12, le=60)


class ShortVideoManifest(AipContractModel):
    manifest_id: str = Field(min_length=1, max_length=200)
    product_ref: ResourceRef
    script_artifact_ref: ArtifactRef
    duration_ms: int = Field(ge=30_000, le=60_000)
    canvas: VideoCanvas
    assets: list[ShortVideoAsset] = Field(min_length=3, max_length=100)
    subtitle_cues: list[SubtitleCue] = Field(min_length=1, max_length=1000)
    output_schema_ref: ResourceRef

    @model_validator(mode="after")
    def _exact_closed_manifest(self) -> "ShortVideoManifest":
        if self.product_ref.resource_type != "Product" or not self.product_ref.revision:
            raise ValueError("productRef requires Product exact revision")
        if (
            self.script_artifact_ref.artifact_type != "document"
            or not self.script_artifact_ref.revision
            or not self.script_artifact_ref.content_hash
        ):
            raise ValueError("scriptArtifactRef requires exact document artifact")
        if (
            self.output_schema_ref.resource_type != "JsonSchemaRevision"
            or not self.output_schema_ref.revision
        ):
            raise ValueError("outputSchemaRef requires JsonSchemaRevision exact revision")
        roles = [item.role for item in self.assets]
        artifact_ids = [item.asset.artifact_ref.artifact_id for item in self.assets]
        missing = _REQUIRED_ROLES - set(roles)
        if missing:
            raise ValueError("required short-video asset roles are missing")
        if any(roles.count(role) > 1 for role in _SINGLE_ROLES):
            raise ValueError("single asset role must not be duplicated")
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("asset artifacts must be unique across roles")
        previous_end = 0
        for cue in self.subtitle_cues:
            if cue.start_ms < previous_end:
                raise ValueError("subtitle cues must not overlap")
            if cue.end_ms > self.duration_ms:
                raise ValueError("subtitle cue exceeds video duration")
            previous_end = cue.end_ms
        if self.subtitle_cues[0].start_ms != 0 or previous_end != self.duration_ms:
            raise ValueError("subtitle timeline must cover the full video duration")
        return self


class AssetLicenseState(StrEnum):
    ALLOWED = "allowed"
    UNKNOWN = "unknown"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class AssetAuthorityObservation(AipContractModel):
    artifact_ref: ArtifactRef
    provenance_ref: ExactRevisionRef
    license_ref: ExactRevisionRef
    evidence_bundle_ref: ExactRevisionRef
    withdrawal_policy_ref: ExactRevisionRef
    content_available: bool
    license_state: AssetLicenseState


class FFmpegObservation(AipContractModel):
    available: bool
    binary_path: str | None = None
    version: str | None = None

    @model_validator(mode="after")
    def _honest_availability(self) -> "FFmpegObservation":
        if self.available:
            if not self.binary_path or not self.version:
                raise ValueError("available FFmpeg requires binaryPath and version")
            if not Path(self.binary_path).is_absolute():
                raise ValueError("FFmpeg binaryPath must be absolute")
        elif self.binary_path or self.version:
            raise ValueError("unavailable FFmpeg cannot carry path or version")
        return self


class ShortVideoReadinessDecision(AipContractModel):
    readiness: ContractReadiness
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    blocker_codes: list[str]

    @model_validator(mode="after")
    def _honest_state(self) -> "ShortVideoReadinessDecision":
        if self.readiness is ContractReadiness.READY and self.blocker_codes:
            raise ValueError("ready decision cannot contain blockers")
        if self.readiness is not ContractReadiness.READY and not self.blocker_codes:
            raise ValueError("blocked decision requires blockers")
        return self


def _canonical_hash(value) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluate_short_video_readiness(
    manifest: ShortVideoManifest,
    *,
    asset_observations: Mapping[str, AssetAuthorityObservation],
    ffmpeg: FFmpegObservation,
) -> ShortVideoReadinessDecision:
    blockers: set[str] = set()
    for item in manifest.assets:
        identifier = item.asset.artifact_ref.artifact_id
        observed = asset_observations.get(identifier)
        if observed is None:
            blockers.add("ASSET_AUTHORITY_MISSING")
            continue
        expected_refs = (
            (observed.artifact_ref, item.asset.artifact_ref),
            (observed.provenance_ref, item.asset.provenance_ref),
            (observed.license_ref, item.asset.license_ref),
            (observed.evidence_bundle_ref, item.asset.evidence_bundle_ref),
            (observed.withdrawal_policy_ref, item.asset.withdrawal_policy_ref),
        )
        if any(actual != expected for actual, expected in expected_refs):
            blockers.add("ASSET_EXACT_REF_DRIFTED")
        if not observed.content_available:
            blockers.add("ASSET_CONTENT_UNAVAILABLE")
        if observed.license_state is not AssetLicenseState.ALLOWED:
            blockers.add(f"ASSET_LICENSE_{observed.license_state.value.upper()}")
        if item.role is ShortVideoAssetRole.FONT:
            blockers.add("FONT_RENDERING_UNSUPPORTED")
    if not ffmpeg.available:
        blockers.add("FFMPEG_UNAVAILABLE")
    blocker_codes = sorted(blockers)
    return ShortVideoReadinessDecision(
        readiness=(
            ContractReadiness.READY
            if not blocker_codes
            else ContractReadiness.BLOCKED
        ),
        manifestHash=_canonical_hash(
            manifest.model_dump(mode="json", by_alias=True)
        ),
        blockerCodes=blocker_codes,
    )


_ALLOWED_SUFFIXES = {
    ShortVideoAssetRole.PRODUCT_IMAGE: {".png", ".jpg", ".jpeg", ".webp"},
    ShortVideoAssetRole.VOICEOVER: {".wav", ".mp3", ".m4a", ".aac"},
    ShortVideoAssetRole.SUBTITLE: {".srt", ".vtt"},
    ShortVideoAssetRole.BGM: {".wav", ".mp3", ".m4a", ".aac"},
    ShortVideoAssetRole.FONT: {".ttf", ".otf"},
}


def _safe_local_path(path: Path, root: Path, *, role: ShortVideoAssetRole) -> Path:
    raw = str(path)
    if "://" in raw or not path.is_absolute():
        raise ValueError("media input must be an absolute local file")
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("media input must remain inside workspace") from exc
    if not resolved.is_file():
        raise ValueError("media input local file is missing")
    if resolved.suffix.lower() not in _ALLOWED_SUFFIXES[role]:
        raise ValueError("media input suffix is not allowed for role")
    return resolved


def build_ffmpeg_argv(
    manifest: ShortVideoManifest,
    *,
    workspace_root: Path,
    binary_path: Path,
    input_paths: Mapping[ShortVideoAssetRole, Path],
    output_path: Path,
) -> list[str]:
    """Build fixed argv only; caller must never execute it through a shell."""
    if not binary_path.is_absolute():
        raise ValueError("FFmpeg binary path must be absolute")
    root = workspace_root.resolve()
    if not root.is_dir():
        raise ValueError("render workspace is unavailable")
    output = output_path.resolve()
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise ValueError("media output must remain inside workspace") from exc
    if output.exists():
        raise ValueError("media output already exists")
    if output.suffix.lower() != ".mp4":
        raise ValueError("media output must use mp4")

    manifest_roles = {item.role for item in manifest.assets}
    if set(input_paths) != manifest_roles:
        raise ValueError("media input path roles must exactly match manifest roles")
    if ShortVideoAssetRole.FONT in manifest_roles:
        raise ValueError("font rendering is not supported by this argv planner")

    if any(role not in input_paths for role in _REQUIRED_ROLES):
        raise ValueError("required media input path is missing")
    required_paths = {
        role: _safe_local_path(input_paths[role], root, role=role)
        for role in _REQUIRED_ROLES
    }
    bgm = input_paths.get(ShortVideoAssetRole.BGM)
    bgm_path = (
        _safe_local_path(bgm, root, role=ShortVideoAssetRole.BGM)
        if bgm is not None
        else None
    )
    image = required_paths[ShortVideoAssetRole.PRODUCT_IMAGE]
    voice = required_paths[ShortVideoAssetRole.VOICEOVER]
    subtitle = required_paths[ShortVideoAssetRole.SUBTITLE]
    duration = f"{manifest.duration_ms / 1000:.3f}"
    video_filter = (
        f"scale={manifest.canvas.width}:{manifest.canvas.height}:"
        "force_original_aspect_ratio=decrease,"
        f"pad={manifest.canvas.width}:{manifest.canvas.height}:"
        "(ow-iw)/2:(oh-ih)/2"
    )
    argv = [
        str(binary_path),
        "-hide_banner",
        "-nostdin",
        "-n",
        "-loop",
        "1",
        "-i",
        str(image),
        "-i",
        str(voice),
    ]
    if bgm_path is not None:
        argv += [
            "-i",
            str(bgm_path),
            "-i",
            str(subtitle),
            "-filter_complex",
            "[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=0[aout]",
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-map",
            "3:s:0",
        ]
    else:
        argv += [
            "-i",
            str(subtitle),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-map",
            "2:s:0",
        ]
    argv += [
        "-t",
        duration,
        "-r",
        str(manifest.canvas.fps),
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-c:s",
        "mov_text",
        "-movflags",
        "+faststart",
        str(output),
    ]
    return argv


__all__ = [
    "AssetAuthorityObservation",
    "AssetLicenseState",
    "FFmpegObservation",
    "ShortVideoAsset",
    "ShortVideoAssetRole",
    "ShortVideoManifest",
    "ShortVideoReadinessDecision",
    "SubtitleCue",
    "VideoCanvas",
    "build_ffmpeg_argv",
    "evaluate_short_video_readiness",
]

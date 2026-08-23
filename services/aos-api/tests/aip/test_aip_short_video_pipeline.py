from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.aip_short_video_pipeline import (
    AssetAuthorityObservation,
    FFmpegObservation,
    ShortVideoAsset,
    ShortVideoAssetRole,
    ShortVideoManifest,
    build_ffmpeg_argv,
    evaluate_short_video_readiness,
)


HASH = "a" * 64


def exact(resource_type: str, resource_id: str, hash_value: str = HASH):
    return {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": 1,
        "contentHash": hash_value,
    }


def artifact(media_type: str, identifier: str):
    return {
        "artifactId": identifier,
        "artifactType": media_type,
        "revision": "1",
        "contentHash": HASH,
    }


def asset(role: str, media_type: str, identifier: str):
    return {
        "role": role,
        "asset": {
            "artifactRef": artifact(media_type, identifier),
            "mediaType": media_type,
            "usage": "input",
            "provenanceRef": exact("AssetProvenanceRevision", f"prov-{identifier}"),
            "licenseRef": exact("AssetLicenseRevision", f"lic-{identifier}"),
            "evidenceBundleRef": exact("EvidenceBundleRevision", f"ev-{identifier}"),
            "withdrawalPolicyRef": exact(
                "AssetWithdrawalPolicyRevision", f"withdraw-{identifier}"
            ),
        },
    }


def manifest_payload():
    return {
        "manifestId": "qyh-product-59-short-video-v1",
        "productRef": {
            "resourceType": "Product",
            "resourceId": "niushop:1:59",
            "revision": HASH,
            "authority": "ecom_object",
        },
        "scriptArtifactRef": artifact("document", "script-product-59"),
        "durationMs": 45000,
        "canvas": {"width": 1080, "height": 1920, "fps": 25},
        "assets": [
            asset("product_image", "image", "image-product-59"),
            asset("voiceover", "audio", "voice-product-59"),
            asset("subtitle", "subtitle", "subtitle-product-59"),
            asset("bgm", "audio", "bgm-internal-1"),
        ],
        "subtitleCues": [
            {"startMs": 0, "endMs": 15000, "textHash": "b" * 64},
            {"startMs": 15000, "endMs": 30000, "textHash": "c" * 64},
            {"startMs": 30000, "endMs": 45000, "textHash": "d" * 64},
        ],
        "outputSchemaRef": {
            "resourceType": "JsonSchemaRevision",
            "resourceId": "short-video-output-v1",
            "revision": "1",
            "authority": "bundle",
        },
    }


def observations(manifest: ShortVideoManifest, *, license_state="allowed"):
    return {
        item.asset.artifact_ref.artifact_id: AssetAuthorityObservation(
            artifactRef=item.asset.artifact_ref,
            provenanceRef=item.asset.provenance_ref,
            licenseRef=item.asset.license_ref,
            evidenceBundleRef=item.asset.evidence_bundle_ref,
            withdrawalPolicyRef=item.asset.withdrawal_policy_ref,
            contentAvailable=True,
            licenseState=license_state,
        )
        for item in manifest.assets
    }


def test_manifest_requires_30_to_60_seconds_and_exact_product() -> None:
    assert ShortVideoManifest.model_validate(manifest_payload()).duration_ms == 45000
    for duration in (29999, 60001):
        with pytest.raises(ValidationError):
            ShortVideoManifest.model_validate(
                {**manifest_payload(), "durationMs": duration}
            )
    payload = manifest_payload()
    payload["productRef"] = {**payload["productRef"], "revision": None}
    with pytest.raises(ValidationError, match="exact revision"):
        ShortVideoManifest.model_validate(payload)


def test_manifest_requires_unique_roles_matching_media_types_and_timeline() -> None:
    payload = manifest_payload()
    payload["assets"][0] = asset("product_image", "audio", "bad-image")
    with pytest.raises(ValidationError, match="role media type"):
        ShortVideoManifest.model_validate(payload)

    payload = manifest_payload()
    payload["assets"].append(asset("voiceover", "audio", "second-voice"))
    with pytest.raises(ValidationError, match="single asset"):
        ShortVideoManifest.model_validate(payload)

    payload = manifest_payload()
    payload["assets"].append(asset("product_image", "image", "second-image"))
    with pytest.raises(ValidationError, match="single asset"):
        ShortVideoManifest.model_validate(payload)

    payload = manifest_payload()
    payload["subtitleCues"][1]["startMs"] = 14000
    with pytest.raises(ValidationError, match="overlap"):
        ShortVideoManifest.model_validate(payload)

    payload = manifest_payload()
    payload["subtitleCues"][-1]["endMs"] = 44000
    with pytest.raises(ValidationError, match="full video"):
        ShortVideoManifest.model_validate(payload)

    payload = manifest_payload()
    payload["assets"][-1] = asset("bgm", "audio", "voice-product-59")
    with pytest.raises(ValidationError, match="unique"):
        ShortVideoManifest.model_validate(payload)


@pytest.mark.parametrize("license_state", ["unknown", "denied", "withdrawn", "expired"])
def test_readiness_fails_closed_for_non_allowed_license(license_state: str) -> None:
    manifest = ShortVideoManifest.model_validate(manifest_payload())
    decision = evaluate_short_video_readiness(
        manifest,
        asset_observations=observations(manifest, license_state=license_state),
        ffmpeg=FFmpegObservation(available=True, binaryPath="/usr/local/bin/ffmpeg", version="7.1"),
    )
    assert decision.readiness == "blocked"
    assert f"ASSET_LICENSE_{license_state.upper()}" in decision.blocker_codes


def test_readiness_requires_exact_asset_authority_content_and_ffmpeg() -> None:
    manifest = ShortVideoManifest.model_validate(manifest_payload())
    observed = observations(manifest)
    observed["image-product-59"] = observed["image-product-59"].model_copy(
        update={"content_available": False}
    )
    decision = evaluate_short_video_readiness(
        manifest,
        asset_observations=observed,
        ffmpeg=FFmpegObservation(available=False),
    )
    assert decision.readiness == "blocked"
    assert decision.blocker_codes == [
        "ASSET_CONTENT_UNAVAILABLE",
        "FFMPEG_UNAVAILABLE",
    ]

    observed = observations(manifest)
    observed["image-product-59"] = observed["image-product-59"].model_copy(
        update={"artifact_ref": artifact("image", "drifted-image")}
    )
    drifted = evaluate_short_video_readiness(
        manifest,
        asset_observations=observed,
        ffmpeg=FFmpegObservation(
            available=True,
            binaryPath="/usr/local/bin/ffmpeg",
            version="7.1",
        ),
    )
    assert drifted.blocker_codes == ["ASSET_EXACT_REF_DRIFTED"]


def test_ready_manifest_builds_shell_free_argv_inside_workspace(tmp_path: Path) -> None:
    manifest = ShortVideoManifest.model_validate(manifest_payload())
    decision = evaluate_short_video_readiness(
        manifest,
        asset_observations=observations(manifest),
        ffmpeg=FFmpegObservation(available=True, binaryPath="/usr/local/bin/ffmpeg", version="7.1"),
    )
    assert decision.readiness == "ready"
    paths = {}
    for item in manifest.assets:
        suffix = {
            ShortVideoAssetRole.PRODUCT_IMAGE: ".png",
            ShortVideoAssetRole.VOICEOVER: ".wav",
            ShortVideoAssetRole.SUBTITLE: ".srt",
            ShortVideoAssetRole.BGM: ".mp3",
        }[item.role]
        path = tmp_path / f"{item.role.value}{suffix}"
        path.write_bytes(b"x")
        paths[item.role] = path
    output = tmp_path / "output.mp4"
    argv = build_ffmpeg_argv(
        manifest,
        workspace_root=tmp_path,
        binary_path=Path("/usr/local/bin/ffmpeg"),
        input_paths=paths,
        output_path=output,
    )
    assert argv[0] == "/usr/local/bin/ffmpeg"
    assert argv[-1] == str(output)
    assert "shell" not in " ".join(argv).lower()
    assert all("http://" not in part and "https://" not in part for part in argv)


def test_argv_rejects_workspace_escape_network_and_unexpected_suffix(tmp_path: Path) -> None:
    manifest = ShortVideoManifest.model_validate(manifest_payload())
    good = tmp_path / "good.png"
    good.write_bytes(b"x")
    outside = tmp_path.parent / "outside.wav"
    outside.write_bytes(b"x")
    paths = {
        ShortVideoAssetRole.PRODUCT_IMAGE: good,
        ShortVideoAssetRole.VOICEOVER: outside,
        ShortVideoAssetRole.SUBTITLE: tmp_path / "captions.srt",
        ShortVideoAssetRole.BGM: tmp_path / "bgm.mp3",
    }
    (tmp_path / "captions.srt").write_bytes(b"x")
    (tmp_path / "bgm.mp3").write_bytes(b"x")
    with pytest.raises(ValueError, match="workspace"):
        build_ffmpeg_argv(
            manifest,
            workspace_root=tmp_path,
            binary_path=Path("/usr/local/bin/ffmpeg"),
            input_paths=paths,
            output_path=tmp_path / "output.mp4",
        )

    paths[ShortVideoAssetRole.VOICEOVER] = Path("https://example.com/voice.wav")
    with pytest.raises(ValueError, match="local file"):
        build_ffmpeg_argv(
            manifest,
            workspace_root=tmp_path,
            binary_path=Path("/usr/local/bin/ffmpeg"),
            input_paths=paths,
            output_path=tmp_path / "output.mp4",
        )


def test_declared_font_is_explicitly_blocked_until_rendering_support_exists() -> None:
    payload = manifest_payload()
    payload["assets"].append(asset("font", "font", "font-internal-1"))
    manifest = ShortVideoManifest.model_validate(payload)
    decision = evaluate_short_video_readiness(
        manifest,
        asset_observations=observations(manifest),
        ffmpeg=FFmpegObservation(
            available=True,
            binaryPath="/usr/local/bin/ffmpeg",
            version="7.1",
        ),
    )
    assert decision.blocker_codes == ["FONT_RENDERING_UNSUPPORTED"]

"""Hashes captured using unmodified m1@36942b23 loader before AR1-a."""
import hashlib
from pathlib import Path

import pytest

from aos_api.asset_registry.canonical_json import canonical_json
from aos_api.asset_registry.contracts import BundleManifest
from aos_api.asset_registry.manifest_loader import ManifestLoader

ROOT = Path(__file__).resolve().parents[4] / "bundles" / "releases"


@pytest.mark.parametrize("relative,expected", [
    ("ecommerce/solution.ecommerce.growth/1.3.0", "acd2590090a731fd3fa4ed00833ebc09a64832fe88ee7b00855c4cd8c0968bbf"),
    ("ecommerce/solution.ecommerce.operations-base/1.1.0", "bc4a8bcf6105363bae2ec3099947d5951ec7b65ae84214e475c9457f8ab9c04f"),
])
def test_old_release_descriptor_matches_preimplementation_hash(relative, expected):
    loaded = ManifestLoader({"releases": ROOT}).load("bundle://releases/" + relative)
    assert loaded.content_hash == "sha256:" + expected
    data = loaded.manifest.model_dump(mode="json", by_alias=True, exclude_none=False)
    assert "runtime" not in data["spec"]
    data["spec"]["runtime"] = None
    normalized = BundleManifest.model_validate(data).model_dump(mode="json", by_alias=True, exclude_none=False)
    assert "runtime" not in normalized["spec"]
    descriptor = {"manifest": normalized, "artifacts": [
        {"relativePath": a.relative_path, "digest": a.digest, "size": a.size, "mediaType": a.media_type}
        for a in loaded.artifacts]}
    assert hashlib.sha256(canonical_json(descriptor)).hexdigest() == expected
    data["spec"]["runtime"] = {"apiVersion": "aos.dev/bundle-runtime/v1alpha1", "frontend": {
        "manifest": "frontend/manifest.json", "artifactHash": "sha256:" + "a" * 64}}
    descriptor["manifest"] = BundleManifest.model_validate(data).model_dump(mode="json", by_alias=True, exclude_none=False)
    assert hashlib.sha256(canonical_json(descriptor)).hexdigest() != expected

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPOSITORY_ROOT / "scripts/workshop_w1_10_successor_install.py"
RELEASE_ROOT = REPOSITORY_ROOT / "bundles/releases/ecommerce"

RELEASES = (
    (
        "ecommerce-growth",
        "solution.ecommerce.growth",
        "1.3.0",
        7,
        "fa984229dde02fef8953ba80fd52b94262b2f0336fd3d3381926329921143101",
    ),
    (
        "ecommerce-operations-base",
        "solution.ecommerce.operations-base",
        "1.1.0",
        1,
        "7b85053c5959c3d5e6182c5f88cb0d298f3be329fbac144953c8fdeca48f2d49",
    ),
)


def _files(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "bundle.signature.json"
    }


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for relative_path, content in _files(root).items():
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def _load_script():
    spec = importlib.util.spec_from_file_location("workshop_successor", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_snapshots_match_immutable_tree_hashes() -> None:
    for _author_name, bundle_id, version, _module_count, expected_hash in RELEASES:
        release = RELEASE_ROOT / bundle_id / version
        assert release.is_dir()
        assert _tree_hash(release) == expected_hash
        assert not (release / "bundle.signature.json").exists()


def test_successor_spec_has_exact_eight_module_inventory() -> None:
    module = _load_script()
    specs = module.release_specs(REPOSITORY_ROOT)
    assert sum(len(spec.expected_module_ids) for spec in specs) == 8
    assert len({item for spec in specs for item in spec.expected_module_ids}) == 8
    assert len({item for spec in specs for item in spec.expected_routes}) == 8
    assert {
        spec.source_ref for spec in specs
    } == {
        "bundle://d3-catalog/releases/ecommerce/solution.ecommerce.growth/1.3.0",
        "bundle://d3-catalog/releases/ecommerce/solution.ecommerce.operations-base/1.1.0",
    }
    growth_manifest = (RELEASE_ROOT / "solution.ecommerce.growth/1.3.0/bundle.yaml").read_text(encoding="utf-8")
    assert "displayName: 电商增长方案包（D3：W03 客户与私域运营台 + L05 分润异常检测）" in growth_manifest


def test_existing_published_version_drift_fails_closed() -> None:
    module = _load_script()
    expected = {
        "status": "published",
        "sourceRef": "bundle://d3-catalog/releases/ecommerce/example/1.0.0",
        "contentHash": "sha256:" + "1" * 64,
        "manifestHash": "sha256:" + "2" * 64,
        "artifacts": [{"artifactRef": "bundle://d3-catalog/releases/ecommerce/example/1.0.0/content/a.json", "digest": "sha256:" + "3" * 64}],
    }
    module.assert_existing_version_exact(expected, expected)
    drifted = dict(expected, contentHash="sha256:" + "4" * 64)
    try:
        module.assert_existing_version_exact(drifted, expected)
    except module.SuccessorInstallBlocked as exc:
        assert exc.reason_code == "EXISTING_VERSION_DRIFT"
    else:
        raise AssertionError("published version drift must fail closed")


def test_script_requires_explicit_apply_and_has_no_direct_sql_mutation() -> None:
    module = _load_script()
    assert module.parse_args([]).apply is False
    assert module.parse_args(["--apply"]).apply is True
    source = SCRIPT.read_text(encoding="utf-8").lower()
    forbidden = (
        "delete from asset_bundle",
        "update asset_bundle",
        "insert into asset_bundle",
        "session_replication_role",
        "_inlinesnapshotreader",
    )
    assert all(marker not in source for marker in forbidden)

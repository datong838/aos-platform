import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/a0v_current_preview_http.py"


@pytest.fixture
def preview():
    spec = importlib.util.spec_from_file_location("a0v_current_preview_http", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_missing_signed_root_rejected_before_database_access(preview, tmp_path, monkeypatch):
    receipt = tmp_path / "signing-receipt.json"
    receipt.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(preview, "_load", lambda *_: pytest.fail("loaded module before signature check"))
    with pytest.raises(preview.PreviewBlocked, match="SIGNING_RECEIPT_DRIFT"):
        preview.preflight(signed_receipt=receipt)


def test_matching_tree_hash_with_invalid_signatures_blocks_before_database(preview, tmp_path, monkeypatch):
    builder = preview._load(
        preview.ROOT / "scripts/build_ecommerce_current_candidates.py", "test_profile"
    ).load_builder()
    signed_root = tmp_path / "signing-state" / "signed-bundles"
    for relative, _, _, _ in builder.ALL_CASES:
        bundle = signed_root / relative
        bundle.mkdir(parents=True)
        (bundle / "bundle.signature.json").write_text(
            '{"algorithm":"Ed25519","signature":"invalid"}\n', encoding="utf-8"
        )
    (signed_root.parent / "trust-roots.json").write_text(
        '{"trustRoots":[]}\n', encoding="utf-8"
    )
    receipt = tmp_path / "signing-receipt.json"
    receipt.write_text(json.dumps({
        "outcome": "SIGNED_TREE_GREEN",
        "signedTree": str(signed_root),
        "signedTreeHash": builder._tree_hash(signed_root),
    }), encoding="utf-8")
    monkeypatch.setattr(preview, "_load", lambda path, name: (
        SimpleNamespace(load_builder=lambda: builder)
        if path.name == "build_ecommerce_current_candidates.py"
        else pytest.fail("database bootstrap loaded before cryptographic rejection")
    ))
    with pytest.raises(preview.PreviewBlocked, match="SIGNED_BUNDLE_CRYPTO_INVALID"):
        preview.preflight(signed_receipt=receipt)


def test_all_execution_flags_are_explicitly_disabled(preview):
    assert preview.EXPECTED_SCHEMA_HEAD == "a0v_112"
    assert preview.FLAGS["AOS_EXTENSION_RUNTIME_HOST_ENABLED"] == "0"
    assert preview.FLAGS["AOS_QYH_CRON_ENABLED"] == "false"
    assert preview.FLAGS["AOS_DB_MIGRATION_MODE"] == "disabled"
    assert all(value == "false" for key, value in preview.FLAGS.items() if "WORKER_ENABLED" in key)

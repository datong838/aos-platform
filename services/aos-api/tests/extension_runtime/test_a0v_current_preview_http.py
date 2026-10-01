import importlib.util
import json
import os
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
    assert preview.FLAGS["AOS_EXTENSION_RUNTIME_HOST_ENABLED"] == "0"
    assert preview.FLAGS["AOS_QYH_CRON_ENABLED"] == "false"
    assert preview.FLAGS["AOS_DB_MIGRATION_MODE"] == "disabled"
    assert all(value == "false" for key, value in preview.FLAGS.items() if "WORKER_ENABLED" in key)


@pytest.mark.parametrize("rows", [[], [{"version_num": "a0v_118"}],
    [{"version_num": "a0v_130"}, {"version_num": "a0v_118"}]])
def test_schema_must_match_current_code_head(preview, monkeypatch, rows):
    monkeypatch.setattr(preview, "_code_schema_head", lambda: "a0v_130", raising=False)
    with pytest.raises(preview.PreviewBlocked, match="PREVIEW_CODE_SCHEMA_DRIFT"):
        preview._require_current_schema(rows)


def test_current_schema_returns_verified_head(preview, monkeypatch):
    monkeypatch.setattr(preview, "_code_schema_head", lambda: "a0v_130", raising=False)
    assert preview._require_current_schema([{"version_num": "a0v_130"}]) == "a0v_130"


@pytest.mark.parametrize("heads", [[], ["a0v_130", "other_branch"]])
def test_ambiguous_code_head_never_authorizes_start(preview, monkeypatch, heads):
    from alembic.script import ScriptDirectory
    monkeypatch.setattr(ScriptDirectory, "get_heads", lambda self: heads)
    with pytest.raises(preview.PreviewBlocked, match="PREVIEW_CODE_SCHEMA_UNAVAILABLE"):
        preview._code_schema_head()


def test_limited_identity_rejects_weak_mode_and_wrong_target(preview, tmp_path):
    pgpass = tmp_path / "api.pgpass"
    pgpass.write_text("opaque-test-only\n", encoding="utf-8")
    pgpass.chmod(0o600)
    identity = tmp_path / "api.json"
    data = {"host": "127.0.0.1", "port": 18436,
            "dbname": preview.TARGET, "user": "aos_api_testonly", "pgpassFile": str(pgpass)}
    identity.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(preview.PreviewBlocked, match="API_IDENTITY_MODE_INVALID"):
        preview._limited_identity(identity, {"databaseHost": "127.0.0.1", "databasePort": 18436})
    identity.chmod(0o600)
    with pytest.raises(preview.PreviewBlocked, match="API_IDENTITY_TARGET_DRIFT"):
        preview._limited_identity(identity, {"databaseHost": "127.0.0.1", "databasePort": 18435})


def test_limited_service_preflight_runs_in_child_without_owner_loader(preview, tmp_path, monkeypatch):
    monkeypatch.setenv("AOS_OIDC_JWKS_URL", "https://id.example.test/jwks")
    monkeypatch.setenv("AOS_OIDC_ISSUER", "https://id.example.test/realms/qyh")
    monkeypatch.setenv("AOS_OIDC_AUDIENCE", "aos-api")
    identity = tmp_path / "api.json"
    identity.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(preview, "preflight", lambda **_: pytest.fail("owner preflight in service"))
    monkeypatch.setattr(preview, "_port_free", lambda *_: True)
    child = SimpleNamespace(returncode=0, stdout='{"msg":"startup log"}\n' + json.dumps({
        "outcome": "CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN", "database": preview.TARGET,
        "databaseHost": "127.0.0.1", "databasePort": 18436,
        "signedRoot": "/signed", "trustRoots": "/trust"}), stderr="")
    calls = []
    monkeypatch.setattr(preview.subprocess, "run", lambda *a, **kw: calls.append((a, kw)) or child)
    monkeypatch.setattr(preview, "_limited_identity", lambda *_: {
        "host": "127.0.0.1", "port": 18436, "dbname": preview.TARGET,
        "user": "aos_api_testonly", "pgpassFile": "/private/api.pgpass"})
    monkeypatch.setattr(preview, "_verify_limited_login", lambda *_: None)
    monkeypatch.setattr(preview.os, "execve", lambda *a: calls.append(a))
    preview.serve_limited(signed_receipt=Path("/signed/receipt"), identity_file=identity)
    assert calls[0][0][0][1:3] == [str(preview.ROOT / "scripts/a0v_current_preview_http.py"), "--signed-receipt"]
    assert "PGPASSWORD" not in calls[-1][2]
    assert "password=" not in calls[-1][2]["AOS_DATABASE_URL"]
    assert calls[-1][2]["PGPASSFILE"] == "/private/api.pgpass"
    assert calls[-1][2]["AOS_EXTENSION_RUNTIME_HOST_ENABLED"] == "0"
    assert calls[-1][2]["AOS_AUTH_ALLOW_DEV"] == "0"
    assert calls[-1][2]["AOS_AUTH_EXTERNAL_ONLY"] == "1"
    assert calls[-1][2]["AOS_REST_CONNECTOR_MOCK"] == "0"


def test_limited_service_requires_external_identity_before_preflight(preview, tmp_path, monkeypatch):
    monkeypatch.delenv("AOS_OIDC_JWKS_URL", raising=False)
    monkeypatch.delenv("AOS_OIDC_JWKS_URLS", raising=False)
    monkeypatch.delenv("AOS_OIDC_ISSUER", raising=False)
    monkeypatch.delenv("AOS_OIDC_ISSUERS", raising=False)
    monkeypatch.delenv("AOS_OIDC_AUDIENCE", raising=False)
    monkeypatch.setattr(preview, "_port_free", lambda *_: True)
    monkeypatch.setattr(preview.subprocess, "run", lambda *_a, **_k: pytest.fail("preflight ran"))
    with pytest.raises(preview.PreviewBlocked, match="EXTERNAL_OIDC_CONFIG_REQUIRED"):
        preview.serve_limited(signed_receipt=tmp_path / "receipt", identity_file=tmp_path / "identity")


def test_limited_service_rejects_loopback_idp(preview, monkeypatch):
    monkeypatch.setenv("AOS_OIDC_JWKS_URL", "http://127.0.0.1:8080/jwks")
    monkeypatch.setenv("AOS_OIDC_ISSUER", "https://id.example.test/realms/qyh")
    monkeypatch.setenv("AOS_OIDC_AUDIENCE", "aos-api")
    with pytest.raises(preview.PreviewBlocked, match="EXTERNAL_OIDC_CONFIG_INVALID"):
        preview._require_external_oidc()

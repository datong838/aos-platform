#!/usr/bin/env python3
"""Materialize one exact A0-V Agnes text Provider without invoking it."""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"
FIRST_INSTALLER = ROOT / "scripts/a0v_canonical_ecommerce_first_install.py"
ENV_FILE = ROOT / ".env"
RECOVERY_ROOT = ROOT.parent / ".aos-recovery-20260910"
ORG_ID = "org-org"
PROJECT_ID = "dev-project"
CANARY_ORG_ID = "dev-org"
CANARY_PROJECT_ID = "dev-project"
ACTOR = "a0v-real-text-provider-authority"
APPROVAL_REF = "approval:AOS-000573:A0-V-local-readonly"
PROVIDER_ID = "a0v-agnes-text-readonly-dev"
PROVIDER_REVISION = 1
PLUGIN_ID = "agnes-text"
PLUGIN_REVISION = 3
BASE_URL = "https://api.agnes-ai.cn/v1"
PROVIDER_MODEL_ID = "agnes-2.5-flash"
SECRET_SERVICE = "com.aos.llm"
SECRET_VERSION = "a0v-v1"
SECRET_ACCOUNT = (
    f"{PLUGIN_ID}/{ORG_ID}/{PROJECT_ID}/{PROVIDER_ID}/api-key/{SECRET_VERSION}"
)
SECRET_REF = (
    f"keychain://{SECRET_SERVICE}/{PLUGIN_ID}/{ORG_ID}/{PROJECT_ID}/"
    f"{PROVIDER_ID}#api-key"
)
CREATED_AT = datetime(2026, 9, 10, 0, 0, tzinfo=UTC)
POLICY_IDS = {
    "egress": "a0v-ecommerce-egress-v1",
    "data": "a0v-ecommerce-public-catalog-v1",
    "network": "a0v-ecommerce-network-v1",
}


class ProviderAuthorityBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database-name")
    parser.add_argument("--docker-context", default="colima-aos-extension")
    parser.add_argument("--database-container", default="aos-a0v-recovery-pg")
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=RECOVERY_ROOT / "state/a0v-real-text-provider-authority",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def _load_first_installer() -> Any:
    spec = importlib.util.spec_from_file_location("a0v_first_install", FIRST_INSTALLER)
    if spec is None or spec.loader is None:
        raise ProviderAuthorityBlocked("FIRST_INSTALLER_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_env(path: Path) -> dict[str, str]:
    allowed = {"AGNES_API_KEY", "AGNES_BASE_URL", "AGNES_TEXT_MODEL"}
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        raise ProviderAuthorityBlocked("AGNES_ENV_FILE_UNAVAILABLE") from None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in allowed:
            values[key] = value.strip().strip("'").strip('"')
    if not values.get("AGNES_API_KEY"):
        raise ProviderAuthorityBlocked("AGNES_API_KEY_UNAVAILABLE")
    if values.get("AGNES_BASE_URL", "").rstrip("/") != BASE_URL:
        raise ProviderAuthorityBlocked("AGNES_BASE_URL_DRIFTED")
    if values.get("AGNES_TEXT_MODEL") != PROVIDER_MODEL_ID:
        raise ProviderAuthorityBlocked("AGNES_TEXT_MODEL_DRIFTED")
    return values


def _keychain_exists(*, runner: Any = subprocess.run) -> bool:
    try:
        completed = runner(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                SECRET_SERVICE,
                "-a",
                SECRET_ACCOUNT,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            shell=False,
            timeout=5.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ProviderAuthorityBlocked("KEYCHAIN_PROBE_FAILED") from None
    if completed.returncode == 0:
        return True
    if completed.returncode == 44:
        return False
    raise ProviderAuthorityBlocked("KEYCHAIN_PROBE_FAILED")


def _load_security_frameworks() -> tuple[Any, Any]:
    try:
        security = ctypes.CDLL(
            "/System/Library/Frameworks/Security.framework/Security"
        )
        core = ctypes.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
    except OSError:
        raise ProviderAuthorityBlocked("KEYCHAIN_FRAMEWORK_UNAVAILABLE") from None
    return security, core


def _install_keychain_secret(
    secret: str, *, frameworks: tuple[Any, Any] | None = None
) -> None:
    if not secret:
        raise ProviderAuthorityBlocked("AGNES_API_KEY_UNAVAILABLE")
    security, core = frameworks or _load_security_frameworks()
    security.SecKeychainFindGenericPassword.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    security.SecKeychainFindGenericPassword.restype = ctypes.c_int32
    security.SecKeychainItemModifyAttributesAndData.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
    ]
    security.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
    security.SecKeychainAddGenericPassword.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    security.SecKeychainAddGenericPassword.restype = ctypes.c_int32
    core.CFRelease.argtypes = [ctypes.c_void_p]
    core.CFRelease.restype = None
    service = SECRET_SERVICE.encode("utf-8")
    account = SECRET_ACCOUNT.encode("utf-8")
    payload = secret.encode("utf-8")
    item = ctypes.c_void_p()
    try:
        status = security.SecKeychainFindGenericPassword(
            None,
            len(service),
            service,
            len(account),
            account,
            None,
            None,
            ctypes.byref(item),
        )
        if status == 0:
            status = security.SecKeychainItemModifyAttributesAndData(
                item, None, len(payload), payload
            )
        elif status == -25300:
            status = security.SecKeychainAddGenericPassword(
                None,
                len(service),
                service,
                len(account),
                account,
                len(payload),
                payload,
                ctypes.byref(item),
            )
        else:
            raise ProviderAuthorityBlocked("KEYCHAIN_WRITE_FAILED")
    except (AttributeError, OSError):
        raise ProviderAuthorityBlocked("KEYCHAIN_WRITE_FAILED") from None
    finally:
        if item.value:
            try:
                core.CFRelease(item)
            except (AttributeError, OSError):
                pass
    if status != 0:
        raise ProviderAuthorityBlocked("KEYCHAIN_WRITE_FAILED")


def _scoped_factory(connect: Any):
    def scoped(_scope: Any = None):
        return connect()

    return scoped


def _asset_ref(item: Any, resource_type: str, identity: str) -> Any:
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef

    return VersionedAssetRef(
        assetType=resource_type,
        assetId=getattr(item, identity),
        revision=item.revision,
        contentHash=item.content_hash,
    )


def _desired_provider(connect: Any) -> Any:
    from aos_api.aip_contracts import TenantContext
    from aos_api.aip_model_runtime_contracts import (
        ModelRuntimeLifecycle,
        ProviderEndpointProfile,
        ProviderInstanceRevision,
    )
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore, canonical_hash
    from aos_api.aip_network_policy_store import AipNetworkPolicyStore
    from aos_api.aip_provider_plugin_authority import ProviderPluginAuthority
    from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore
    from aos_api.tenant_scope import TenantScope

    scope = TenantScope(ORG_ID, PROJECT_ID)
    factory = _scoped_factory(connect)
    plugin = ProviderPluginAuthority().get(scope, PLUGIN_ID, PLUGIN_REVISION)
    guard = AipRuntimeGuardPolicyStore(factory)
    egress = guard.get_egress(scope, POLICY_IDS["egress"], 1)
    data = guard.get_data_classification(scope, POLICY_IDS["data"], 1)
    network = AipNetworkPolicyStore(factory, guard_policy_store=guard).get(
        scope, POLICY_IDS["network"], 1
    )
    egress_ref = _asset_ref(egress, "EgressPolicyRevision", "policy_id")
    data_ref = _asset_ref(data, "DataClassificationPolicyRevision", "policy_id")
    if (
        egress.allowed_hosts != ["api.agnes-ai.cn"]
        or network.allowed_hosts != ["api.agnes-ai.cn"]
        or network.egress_policy_ref != egress_ref
        or "public_catalog" not in data.allowed_classifications
        or not data.deny_unknown
    ):
        raise ProviderAuthorityBlocked("A0V_PROVIDER_POLICY_DRIFTED")
    payload = {
        "tenant": TenantContext(orgId=ORG_ID, projectId=PROJECT_ID),
        "providerInstanceId": PROVIDER_ID,
        "revision": PROVIDER_REVISION,
        "pluginRef": _asset_ref(plugin, "ProviderPluginRevision", "provider_plugin_id"),
        "endpointProfile": ProviderEndpointProfile(
            baseUrl=BASE_URL,
            region=egress.region,
            timeoutMs=10_000,
            metadata={"authority": "AOS-000573", "mode": "readonly-development"},
        ),
        "secretRef": SECRET_REF,
        "secretVersion": SECRET_VERSION,
        "egressPolicyRef": egress_ref,
        "dataClassificationPolicyRef": data_ref,
        "lifecycle": ModelRuntimeLifecycle.ACTIVE,
        "createdBy": ACTOR,
        "createdAt": CREATED_AT,
    }
    provisional = ProviderInstanceRevision(**payload, contentHash="0" * 64)
    content = {
        key: value
        for key, value in provisional.model_dump(mode="json", by_alias=True).items()
        if key not in AipModelRuntimeStore._META_FIELDS
    }
    return ProviderInstanceRevision(**payload, contentHash=canonical_hash(content))


def _inventory(connect: Any) -> dict[str, int]:
    with connect() as conn:
        identity = conn.execute("SELECT current_database() AS database").fetchone()
        if identity is None or identity["database"] != "aos_meta_head":
            raise ProviderAuthorityBlocked("DATABASE_IDENTITY_MISMATCH")
        positive = conn.execute(
            "SELECT count(*) AS n FROM aip_provider_instance_revision "
            "WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s",
            (ORG_ID, PROJECT_ID, PROVIDER_ID),
        ).fetchone()
        canary_provider = conn.execute(
            "SELECT count(*) AS n FROM aip_provider_instance_revision "
            "WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s",
            (CANARY_ORG_ID, CANARY_PROJECT_ID, PROVIDER_ID),
        ).fetchone()
        canary_health = conn.execute(
            "SELECT count(*) AS n FROM aip_provider_health_observation "
            "WHERE org_id=%s AND project_id=%s",
            (CANARY_ORG_ID, CANARY_PROJECT_ID),
        ).fetchone()
    result = {
        "providerRevisionCount": int(positive["n"]),
        "canaryProviderRevisionCount": int(canary_provider["n"]),
        "canaryHealthObservationCount": int(canary_health["n"]),
    }
    if result["canaryProviderRevisionCount"] or result["canaryHealthObservationCount"]:
        raise ProviderAuthorityBlocked("CANARY_PROVIDER_AUTHORITY_NOT_EMPTY")
    return result


def preflight() -> dict[str, Any]:
    return {
        "outcome": "PREFLIGHT_GREEN",
        "mode": "preflight",
        "scope": {"orgId": ORG_ID, "projectId": PROJECT_ID},
        "provider": {
            "assetId": PROVIDER_ID,
            "revision": PROVIDER_REVISION,
            "pluginId": PLUGIN_ID,
            "pluginRevision": PLUGIN_REVISION,
            "baseUrl": BASE_URL,
            "providerModelId": PROVIDER_MODEL_ID,
            "secretVersion": SECRET_VERSION,
        },
        "effects": {
            "providerInvocationCount": 0,
            "businessMutationCount": 0,
            "externalPublicationCount": 0,
        },
    }


def apply(args: argparse.Namespace) -> dict[str, Any]:
    if args.database_name != "aos_meta_head":
        raise ProviderAuthorityBlocked("EXPLICIT_ISOLATED_DATABASE_REQUIRED")
    settings = _load_env(args.env_file)
    installer = _load_first_installer()
    connect = installer.container_database_connect_factory(
        context=args.docker_context,
        container=args.database_container,
        database_name=args.database_name,
    )
    before = _inventory(connect)
    backup = installer.create_pre_mutation_backup(
        context=args.docker_context,
        container=args.database_container,
        database_name=args.database_name,
        state_dir=args.state_dir,
    )
    sys.path.insert(0, str(API_ROOT))
    try:
        from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeNotFound
        from aos_api.aip_secret_backend import ExactSecretResolver, SecretBackendError
        from aos_api.tenant_scope import TenantScope

        scope = TenantScope(ORG_ID, PROJECT_ID)
        desired = _desired_provider(connect)
        resolver = ExactSecretResolver()
        keychain_before = False
        try:
            resolver.resolve(scope, desired)
            keychain_before = True
        except SecretBackendError as exc:
            code = exc.code
            if code not in {"keychain_item_unavailable", "keychain_empty"}:
                raise ProviderAuthorityBlocked("KEYCHAIN_EXACT_SECRET_UNAVAILABLE") from None
            _install_keychain_secret(settings["AGNES_API_KEY"])
        if not _keychain_exists():
            raise ProviderAuthorityBlocked("KEYCHAIN_ITEM_UNAVAILABLE_AFTER_WRITE")
        try:
            resolved = resolver.resolve(scope, desired)
        except SecretBackendError:
            raise ProviderAuthorityBlocked("KEYCHAIN_EXACT_SECRET_UNAVAILABLE") from None
        if not resolved:
            raise ProviderAuthorityBlocked("KEYCHAIN_EXACT_SECRET_UNAVAILABLE")
        del resolved
        probe = resolver.probe(scope, desired)
        if not probe.exists or probe.secret_version != SECRET_VERSION:
            raise ProviderAuthorityBlocked("KEYCHAIN_EXACT_SECRET_UNAVAILABLE")
        store = AipModelRuntimeStore(_scoped_factory(connect))
        try:
            provider = store.get_provider(scope, PROVIDER_ID)
        except ModelRuntimeNotFound:
            provider = store.publish_provider(
                scope,
                ACTOR,
                "a0v-real-text-provider-v1",
                desired,
                expected_version=0,
            )
        if provider != desired:
            raise ProviderAuthorityBlocked("A0V_PROVIDER_HEAD_DRIFTED")
    finally:
        sys.path.remove(str(API_ROOT))
    after = _inventory(connect)
    mutation_count = after["providerRevisionCount"] - before["providerRevisionCount"]
    return {
        "outcome": "A0V_REAL_TEXT_PROVIDER_AUTHORITY_GREEN",
        "mode": "apply",
        "scope": {"orgId": ORG_ID, "projectId": PROJECT_ID},
        "provider": {
            "assetType": "ProviderInstanceRevision",
            "assetId": provider.provider_instance_id,
            "revision": provider.revision,
            "contentHash": provider.content_hash,
            "lifecycle": provider.lifecycle.value,
            "pluginRef": provider.plugin_ref.model_dump(mode="json", by_alias=True),
            "egressPolicyRef": provider.egress_policy_ref.model_dump(mode="json", by_alias=True),
            "dataClassificationPolicyRef": provider.data_classification_policy_ref.model_dump(mode="json", by_alias=True),
            "baseUrl": str(provider.endpoint_profile.base_url),
            "region": provider.endpoint_profile.region,
            "secretRefFingerprint": probe.ref_fingerprint,
            "secretVersion": probe.secret_version,
        },
        "before": before,
        "after": after,
        "backup": backup,
        "mutationCount": mutation_count,
        "keychainMutationCount": 0 if keychain_before else 1,
        "effects": {
            "providerInvocationCount": 0,
            "businessMutationCount": 0,
            "externalPublicationCount": 0,
        },
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    return apply(args) if args.apply else preflight()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run(args)
        status = 0
    except ProviderAuthorityBlocked as exc:
        result = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.code}
        status = 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return status


if __name__ == "__main__":
    raise SystemExit(main())

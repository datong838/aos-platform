"""d2_6_register_ecommerce_bundle.py — D2.6 子任务 A-2.

注册 domain.ecommerce.core 资产包到 Registry，让 /apollo/assets 页面可见。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
为什么用 import 模式而非 HTTP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  后端 uvicorn 在本地有时假死（进程在但端口不 LISTEN）。
  d2_qiyuehui_init_load.py 已采用 "import 内部模块 + 直连 PG" 模式
  绕过 HTTP，本脚本沿用相同模式。数据写入 PG 后，重启 uvicorn
  即可在前端看到。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
签名（关键 · 不绕过安全检查）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  RegistryService.validate 强制要求 bundle 有签名
  (release_policy.py:153 SignatureInvalidError)。
  本脚本采用 M5 测试同款 "运行时签名" 模式 (m5_bundle_support.py):
    1. 生成临时 Ed25519 密钥
    2. 复制 bundles/domains/ecommerce-core 到临时目录
    3. 用 canonical_json(manifest + artifacts) 作为签名负载
    4. 写 bundle.yaml.sig 文件
    5. 构造 FrozenTrustRootProvider 注入 ManifestLoader
  签名材料不持久化（临时目录用完即删），原始 bundles/ 目录不污染。

注册流程:
  0. cleanup: 删除已有的未签名 version（含子表）
  1. create_bundle
  2. create_version (从签名后的临时目录加载)
  3. validate
  4. publish
"""
from __future__ import annotations

import base64
import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICES_API = REPO_ROOT / "services" / "aos-api"
sys.path.insert(0, str(SERVICES_API))

import psycopg  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256  # noqa: E402
from aos_api.asset_registry.contracts import BundleKind  # noqa: E402
from aos_api.asset_registry.manifest_loader import (  # noqa: E402
    MANIFEST_FILENAME,
    SIGNATURE_FILENAME,
    ManifestLoader,
)
from aos_api.asset_registry.registry_service import RegistryService  # noqa: E402
from aos_api.asset_registry.registry_store import PostgresRegistryStore  # noqa: E402
from aos_api.asset_registry.signature import (  # noqa: E402
    FrozenTrustRootProvider,
    TrustRoot,
)
from aos_api.db import get_dsn  # noqa: E402

# ─────────────────────────────────────────────────────────
# 注册参数（与 bundles/domains/ecommerce-core/bundle.yaml 对齐）
# ─────────────────────────────────────────────────────────
PUBLISHER = "aos"
BUNDLE_ID = "domain.ecommerce.core"
BUNDLE_KIND = BundleKind.DOMAIN_PACK
DISPLAY_NAME = "电商核心本体包"
VERSION = "1.0.0"
BUNDLE_RELATIVE_PATH = "domains/ecommerce-core"
SOURCE_ALIAS = "catalog"  # alias 须匹配 BUNDLE_ID_PATTERN，catalog 符合

ACTOR = "d2-6-registrar"
ROLES = frozenset({"asset-publisher", "asset-registry-admin"})
PUBLISHER_SCOPES = frozenset({PUBLISHER})

# 职责分离（maker-checker）：create/validate/publish 必须是不同 actor
# (registry_service._assert_publish_duty_separation)
CREATOR_ACTOR = "d2-6-creator"
VALIDATOR_ACTOR = "d2-6-validator"
PUBLISHER_ACTOR = "d2-6-publisher"

RUNTIME_KEY_ID = "d2-6-runtime-signer"
# 持久化密钥文件：每次跑复用同一密钥，确保 trust_roots 与已存储签名一致。
# 首次跑自动生成；gitignore 应忽略 *.pem。
RUNTIME_KEY_PATH = REPO_ROOT / "scripts" / ".d2_6_runtime_ed25519.pem"
# 固定时间窗口（与密钥一同持久化在 trust_root revision 里），
# 避免 not_before/not_after 漂移导致续跑验签失败。
TRUST_NOT_BEFORE = datetime(2026, 1, 1, tzinfo=UTC)
TRUST_NOT_AFTER = datetime(2036, 1, 1, tzinfo=UTC)


def _load_or_create_runtime_key() -> Ed25519PrivateKey:
    """加载或生成持久化 Ed25519 密钥。"""
    if RUNTIME_KEY_PATH.exists():
        raw = RUNTIME_KEY_PATH.read_bytes()
        return serialization.load_pem_private_key(raw, password=None)
    RUNTIME_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    RUNTIME_KEY_PATH.write_bytes(pem)
    try:
        RUNTIME_KEY_PATH.chmod(0o600)
    except OSError:
        pass
    return key


def cleanup_existing(dsn: str) -> None:
    """删除已有的 domain.ecommerce.core bundle + version（含子表）。

    幂等：不存在不报错。按 FK 依赖反序删除。
    """
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            # asset_bundle.bundle_pk 是 PK，bundle_id 是业务 ID
            cur.execute(
                "SELECT bundle_pk FROM asset_bundle WHERE bundle_id = %s",
                (BUNDLE_ID,),
            )
            bundle_pk_rows = cur.fetchall()
            bundle_pks = [r["bundle_pk"] for r in bundle_pk_rows]
            version_pks: list = []
            if bundle_pks:
                bp_placeholders = ",".join(["%s"] * len(bundle_pks))
                cur.execute(
                    f"SELECT version_pk FROM asset_bundle_version "
                    f"WHERE bundle_pk IN ({bp_placeholders})",
                    bundle_pks,
                )
                version_pks = [r["version_pk"] for r in cur.fetchall()]
            if version_pks:
                placeholders = ",".join(["%s"] * len(version_pks))
                for child in (
                    "asset_bundle_evidence",
                    "asset_bundle_artifact",
                    "asset_bundle_dependency",
                    "asset_bundle_version_event",
                ):
                    cur.execute(
                        f"DELETE FROM {child} WHERE version_pk IN ({placeholders})",
                        version_pks,
                    )
                cur.execute(
                    f"DELETE FROM asset_bundle_version "
                    f"WHERE bundle_pk IN ({bp_placeholders})",
                    bundle_pks,
                )
            cur.execute(
                "DELETE FROM asset_bundle WHERE bundle_id = %s",
                (BUNDLE_ID,),
            )
        conn.commit()
    if version_pks:
        print(f"[cleanup] removed {len(version_pks)} old version(s) + bundle")


def _canonical_signature_payload(loaded) -> bytes:
    """镜像 m5_bundle_support.canonical_bundle_signature_payload。"""
    return canonical_json(
        {
            "manifest": loaded.manifest.model_dump(
                mode="json", by_alias=True, exclude_none=False
            ),
            "artifacts": [
                {
                    "relativePath": item.relative_path,
                    "digest": item.digest,
                    "size": item.size,
                    "mediaType": item.media_type,
                }
                for item in loaded.artifacts
            ],
        }
    )


def sign_bundle_to_temp(
    *, source_root: Path, relative_path: str, alias: str
) -> tuple[Path, ManifestLoader, FrozenTrustRootProvider]:
    """复制 bundle 到临时目录并运行时签名。

    返回 (temp_root, signed_loader, trust_roots)。
    调用方负责清理 temp_root。
    """
    temp_root = Path(tempfile.mkdtemp(prefix="d2-6-bundle-"))
    try:
        shutil.copytree(source_root / relative_path, temp_root / relative_path)
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise

    unsigned_loader = ManifestLoader({alias: temp_root})
    source_ref = f"bundle://{alias}/{relative_path}"
    unsigned = unsigned_loader.load(source_ref)

    runtime_key = _load_or_create_runtime_key()
    public_key = runtime_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_key_b64 = base64.b64encode(public_key).decode("ascii")
    trust_root = TrustRoot(
        publisher=PUBLISHER,
        key_id=RUNTIME_KEY_ID,
        public_key=public_key,
        revision=canonical_sha256(
            {
                "publisher": PUBLISHER,
                "keyId": RUNTIME_KEY_ID,
                "algorithm": "Ed25519",
                "publicKey": public_key_b64,
            }
        ),
        not_before=TRUST_NOT_BEFORE,
        not_after=TRUST_NOT_AFTER,
    )
    trust_roots = FrozenTrustRootProvider(
        {(trust_root.publisher, trust_root.key_id): trust_root}
    )

    envelope = {
        "algorithm": "Ed25519",
        "keyId": RUNTIME_KEY_ID,
        "signature": base64.b64encode(
            runtime_key.sign(_canonical_signature_payload(unsigned))
        ).decode("ascii"),
        "signedAt": datetime.now(UTC).isoformat(),
    }
    signature_path = temp_root / relative_path / SIGNATURE_FILENAME
    signature_path.write_text(
        json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    signed_loader = ManifestLoader({alias: temp_root}, trust_roots=trust_roots)
    return temp_root, signed_loader, trust_roots


def main() -> int:
    dsn = get_dsn()
    catalog_root = REPO_ROOT / "bundles"

    # 运行时签名（每次都用新临时密钥；签名只在 create_version 时校验内容指纹，
    # 已存在的 version 不会重新加载，因此续跑不会因密钥变化失败）
    temp_root, signed_loader, trust_roots = sign_bundle_to_temp(
        source_root=catalog_root,
        relative_path=BUNDLE_RELATIVE_PATH,
        alias=SOURCE_ALIAS,
    )
    try:
        service = RegistryService(
            store=PostgresRegistryStore(),
            loader=signed_loader,
            trust_roots=trust_roots,
        )
        source_ref = f"bundle://{SOURCE_ALIAS}/{BUNDLE_RELATIVE_PATH}"

        # 步骤 1: create_bundle（已存在则跳过；幂等）
        from aos_api.asset_registry.errors import (
            AssetNotFoundError,
            AssetRegistryError,
        )
        try:
            service.get_bundle(bundle_id=BUNDLE_ID, publisher=PUBLISHER)
            print(f"[skip] bundle {BUNDLE_ID} already exists")
        except AssetNotFoundError:
            print(f"[create_bundle] {BUNDLE_ID} ...")
            service.create_bundle(
                publisher=PUBLISHER,
                bundle_id=BUNDLE_ID,
                kind=BUNDLE_KIND,
                display_name=DISPLAY_NAME,
                actor=CREATOR_ACTOR,
                roles=ROLES,
                publisher_scopes=PUBLISHER_SCOPES,
            )
            print("[ok] bundle created")
        except AssetRegistryError as exc:
            if "not" not in str(exc).lower():
                raise
            print(f"[create_bundle] {BUNDLE_ID} ...")
            service.create_bundle(
                publisher=PUBLISHER,
                bundle_id=BUNDLE_ID,
                kind=BUNDLE_KIND,
                display_name=DISPLAY_NAME,
                actor=CREATOR_ACTOR,
                roles=ROLES,
                publisher_scopes=PUBLISHER_SCOPES,
            )
            print("[ok] bundle created")

        # 步骤 2: create_version（已存在则跳过；幂等）
        try:
            version_detail = service.get_version(
                bundle_id=BUNDLE_ID, version=VERSION, publisher=PUBLISHER
            )
            current_status = version_detail.get("status", "draft")
            print(f"[skip] version {VERSION} exists, status={current_status}")
        except AssetNotFoundError:
            print(f"[create_version] source_ref={source_ref} ...")
            service.create_version(
                bundle_id=BUNDLE_ID,
                source_ref=source_ref,
                actor=CREATOR_ACTOR,
                roles=ROLES,
                publisher=PUBLISHER,
                publisher_scopes=PUBLISHER_SCOPES,
            )
            version_detail = service.get_version(
                bundle_id=BUNDLE_ID, version=VERSION, publisher=PUBLISHER
            )
            current_status = version_detail.get("status", "draft")
            print(f"[ok] version {VERSION} created (signed), status={current_status}")
        except AssetRegistryError as exc:
            if "not" not in str(exc).lower():
                raise
            print(f"[create_version] source_ref={source_ref} ...")
            service.create_version(
                bundle_id=BUNDLE_ID,
                source_ref=source_ref,
                actor=CREATOR_ACTOR,
                roles=ROLES,
                publisher=PUBLISHER,
                publisher_scopes=PUBLISHER_SCOPES,
            )
            version_detail = service.get_version(
                bundle_id=BUNDLE_ID, version=VERSION, publisher=PUBLISHER
            )
            current_status = version_detail.get("status", "draft")
            print(f"[ok] version {VERSION} created (signed), status={current_status}")

        # 步骤 3+4: 状态机续跑（draft→validate→publish / validated→publish / published→skip）
        if current_status == "published":
            print(f"[skip] {BUNDLE_ID}@{VERSION} already published")
        else:
            if current_status == "draft":
                print(f"[validate] {BUNDLE_ID}@{VERSION} ...")
                service.validate(
                    bundle_id=BUNDLE_ID,
                    version=VERSION,
                    actor=VALIDATOR_ACTOR,
                    roles=ROLES,
                    publisher=PUBLISHER,
                    publisher_scopes=PUBLISHER_SCOPES,
                )
                print("[ok] validated")
                current_status = "validated"
            if current_status == "validated":
                print(f"[publish] {BUNDLE_ID}@{VERSION} ...")
                service.publish(
                    bundle_id=BUNDLE_ID,
                    version=VERSION,
                    actor=PUBLISHER_ACTOR,
                    roles=ROLES,
                    publisher=PUBLISHER,
                    publisher_scopes=PUBLISHER_SCOPES,
                )
                print("[ok] published")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    # 验证：list_bundles 应包含 domain.ecommerce.core
    verify_service = RegistryService(
        store=PostgresRegistryStore(),
        loader=signed_loader,
        trust_roots=trust_roots,
    )
    bundles = verify_service.list_bundles()
    found = [b for b in bundles if b.get("bundleId") == BUNDLE_ID]
    if not found:
        print(f"[FAIL] {BUNDLE_ID} not in list_bundles output")
        return 1
    print(f"[verified] {BUNDLE_ID} visible in Registry: {found[0]['displayName']}")

    version_detail = verify_service.get_version(
        bundle_id=BUNDLE_ID, version=VERSION, publisher=PUBLISHER
    )
    print(f"[verified] version status={version_detail.get('status')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

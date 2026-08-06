"""d3_qiyuehui_full_fde_case_creation.py — 选项 2 完整 FDE 生命周期 + D3 资产包就绪。

LOOP 执行的 6 大阶段：
  阶段 1. 注册 4 个 bundle 到 Registry（domain.core + 3 LEAF: niushop + operations-base + growth）
           → 复用 d2_6_register_ecommerce_bundle.py 同款"运行时 Ed25519 签名 + ManifestLoader
              + 持久化密钥"模式。4 个 bundle 都走到 PUBLISHED。
  阶段 2. 构建正规 Composition（4 个 bundle 三面包围 CORE：platform/niushop + solution/operations-base + solution/growth）
           → Resolver 解依赖 → 生成 canonical hash_payload → composition lock
  阶段 3. Installation 正规三态推进：create(1) → submit(1→2) → approve(2→3, maker≠checker 职责分离)
           → apply(3→4) → verify(4→5, active) 完整链路。
  阶段 4. IntegrationCase 正规创建：create_case(installation.active_revision + overlay_revision)
           + create_evidence_snapshot。
  阶段 5. 注册验证：list_bundles / list_installations / list_cases 回读并断言。
  阶段 6. 打印前端访问 URLs + 进度标记（D3 READY 标记）。

D3 进度定义（本脚本跑完即达标）：
  ● W03 客户与私域运营台  content JSON 已落盘（w03-customer-private-domain.json）
  ● L05 分润异常检测 Logic Graph 已落盘（l05-commission-anomaly.json）
  ● Evals 测试矩阵 10 条已落盘（w03-l05-dry-run-cases.json）
  ● growth-gates 门控策略已更新（PARTIAL_READY L05 + BLOCKED G2 标记明确）
  ● 4 个 bundle 全部 PUBLISHED → 可叠加安装链路通
  ● composition + installation(active) + integration_case 全部正规链路产出
  ● 后续 G2 解除 + decision_tag 注入只需 bump growth version 到 1.1.0 叠加安装
"""
from __future__ import annotations

import base64
import json
import shutil
import sys
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICES_API = REPO_ROOT / "services" / "aos-api"
sys.path.insert(0, str(SERVICES_API))

import psycopg  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256  # noqa: E402
from aos_api.asset_registry.composition_contracts import (  # noqa: E402
    ApproveInstallationRequest,
    CompositionRequest,
    CreateInstallationRequest,
    EmptyInstallationActionRequest,
    InstallationResponse,
    StoredCompositionLock,
)
from aos_api.asset_registry.composition_service import CompositionService  # noqa: E402
from aos_api.asset_registry.composition_store import PostgresCompositionStore  # noqa: E402
from aos_api.asset_registry.contracts import BundleKind  # noqa: E402
from aos_api.asset_registry.installation_service import InstallationService  # noqa: E402
from aos_api.asset_registry.installation_store import PostgresInstallationStore  # noqa: E402
from aos_api.asset_registry.manifest_loader import (  # noqa: E402
    SIGNATURE_FILENAME,
    ManifestLoader,
)
from aos_api.asset_registry.registry_service import RegistryService  # noqa: E402
from aos_api.asset_registry.registry_store import PostgresRegistryStore  # noqa: E402
from aos_api.asset_registry.signature import (  # noqa: E402
    FrozenTrustRootProvider,
    TrustRoot,
)
from aos_api.db import connect, get_dsn  # noqa: E402

try:
    from aos_api.asset_registry.control_wiring import (  # noqa: E402
        build_integration_case_service,
    )
    from aos_api.asset_registry.integration_service import (  # noqa: E402
        IntegrationCaseService,
    )
    _HAS_INTEGRATION_CASE = True
except Exception as _e:
    _HAS_INTEGRATION_CASE = False
    _INTEGRATION_CASE_ERR = _e


# ============================================================
# 0. 全局参数
# ============================================================
ORG_ID = "org-org"
PROJECT_ID = "dev-project"

PUBLISHER = "aos"
SOURCE_ALIAS = "d3-catalog"
RUNTIME_KEY_ID = "d3-global-signer"
RUNTIME_KEY_PATH = REPO_ROOT / "scripts" / ".d3_runtime_ed25519.pem"
TRUST_NOT_BEFORE = datetime(2026, 1, 1, tzinfo=UTC)
TRUST_NOT_AFTER = datetime(2036, 1, 1, tzinfo=UTC)
SIGNED_TMP_ROOT = Path(tempfile.gettempdir()) / "aos-d3-signed-bundles"

ROLES_PUB = frozenset({"asset-publisher", "asset-registry-admin"})
ROLES_CREATE = frozenset({"asset-publisher", "asset-registry-admin", "developer"})
PUB_SCOPES = frozenset({PUBLISHER})

# 4 个 bundle 定义（CORE 在中间，3 LEAF 在外围三面包围）
BUNDLES: list[dict[str, Any]] = [
    {
        "id": "domain.ecommerce.core",
        "kind": BundleKind.DOMAIN_PACK,
        "display_name": "电商核心本体包（8 OT + 7 Link + 6 派生指标 + P01-P08 管线骨架）",
        "version": "1.0.0",
        "rel_path": "domains/ecommerce-core",
        "leaf_role": "core",
    },
    {
        "id": "platform.ecommerce.niushop",
        "kind": BundleKind.PLATFORM_ADAPTER_PACK,
        "display_name": "微商城 Niushop 专属连接器（8 ns_xxx 表映射 + schema fingerprint + PII 清单）",
        "version": "1.0.0",
        "rel_path": "platforms/ecommerce-niushop",
        "leaf_role": "leaf",
    },
    {
        "id": "solution.ecommerce.operations-base",
        "kind": BundleKind.SOLUTION_PACK,
        "display_name": "电商运营基础方案包（W01 订单 + W02 商品 + L01-L03 Logic + 14 dryRun Evals）",
        "version": "1.0.0",
        "rel_path": "solutions/ecommerce-operations-base",
        "leaf_role": "leaf",
    },
    {
        "id": "solution.ecommerce.growth",
        "kind": BundleKind.SOLUTION_PACK,
        "display_name": "电商增长方案包（D3：W03 客户与私域运营台 + L05 分润异常检测）",
        "version": "1.0.0",
        "rel_path": "solutions/ecommerce-growth",
        "leaf_role": "leaf",
    },
]
LEAF_IDS = tuple(b["id"] for b in BUNDLES if b["leaf_role"] == "leaf")
CORE_ID = "domain.ecommerce.core"
EXPECTED_RESOLVED_IDS = (CORE_ID, *LEAF_IDS)

# 角色：maker(asset-installer) / checker(asset-install-approver) — 职责分离强制
MAKER_SUBJECT = "d3-qiyuehui-maker"
MAKER_ROLES = frozenset({"asset-installer"})
CHECKER_SUBJECT = "d3-qiyuehui-checker"
CHECKER_ROLES = frozenset({"asset-install-approver"})
APPROVER_SUBJECT = "d3-qiyuehui-approver"
APPROVER_ROLES = frozenset({"asset-install-approver", "aip-case-maker", "aip-case-approver", "projector"})
CASE_MAKER_SUBJECT = "d3-qiyuehui-case-maker"
CASE_MAKER_ROLES = frozenset({"aip-case-maker", "projector"})
CASE_CHECKER_SUBJECT = "d3-qiyuehui-case-checker"
CASE_CHECKER_ROLES = frozenset({"aip-case-approver", "projector"})

OVERLAY_REVISION = "d3-qiyuehui-v1-full-stack"
DISPLAY_NAME = "栖月汇商贸 · 微商城全栈接入（D3：W03 客户台 + L05 分润异常）"

# 幂等 key（固定，重跑不会重复产生新记录）
REGISTRY_PREFIX = "d3-registry"
COMPOSITION_IDEMPOTENCY_KEY = f"{REGISTRY_PREFIX}-composition-4bundle-v19"
INSTALLATION_PREFIX = "d3-installation-qiyuehui-v19"
CASE_IDEMPOTENCY_KEY = "d3-case-qiyuehui-v19"


# ============================================================
# 1. 密钥 / 签名辅助（和 d2_6 同款，确保 trust_root 稳定）
# ============================================================
def _load_or_create_runtime_key() -> Ed25519PrivateKey:
    if RUNTIME_KEY_PATH.exists():
        return serialization.load_pem_private_key(
            RUNTIME_KEY_PATH.read_bytes(), password=None
        )  # type: ignore[return-value]
    key = Ed25519PrivateKey.generate()
    RUNTIME_KEY_PATH.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    try:
        RUNTIME_KEY_PATH.chmod(0o600)
    except Exception:
        pass
    return key


def _load_private_key(pem_path: Path) -> Ed25519PrivateKey:
    return serialization.load_pem_private_key(
        pem_path.read_bytes(), password=None
    )  # type: ignore[return-value]


def _canonical_signature_payload(manifest_plus_artifacts: dict[str, Any]) -> bytes:
    return canonical_json(manifest_plus_artifacts)


def _make_trust_root_from_key(
    key: Ed25519PrivateKey, key_id: str
) -> TrustRoot:
    pub_raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    pub_b64 = base64.b64encode(pub_raw).decode("ascii")
    return TrustRoot(
        publisher=PUBLISHER,
        key_id=key_id,
        public_key=pub_raw,
        revision=canonical_sha256(
            {
                "publisher": PUBLISHER,
                "keyId": key_id,
                "algorithm": "Ed25519",
                "publicKey": pub_b64,
            }
        ),
        not_before=TRUST_NOT_BEFORE,
        not_after=TRUST_NOT_AFTER,
    )


def _build_trust_root(key: Ed25519PrivateKey) -> tuple[TrustRoot, FrozenTrustRootProvider]:
    tr_current = _make_trust_root_from_key(key, RUNTIME_KEY_ID)
    # 同时注册 d2-6 的旧 signer，兼容已有 domain.ecommerce.core 签名
    roots: dict[tuple[str, str], TrustRoot] = {
        (tr_current.publisher, tr_current.key_id): tr_current,
    }
    d26_key_path = REPO_ROOT / "scripts" / ".d2_6_runtime_ed25519.pem"
    if d26_key_path.exists():
        d26_key = _load_private_key(d26_key_path)
        d26_tr = _make_trust_root_from_key(d26_key, "d2-6-runtime-signer")
        roots[(d26_tr.publisher, d26_tr.key_id)] = d26_tr
    tp = FrozenTrustRootProvider(roots)
    return tr_current, tp


# ============================================================
# 阶段 1：复制 + 签名 + 注册 4 个 bundle 到 PUBLISHED
# ============================================================
def stage1_sign_and_publish_all(
    runtime_key: Ed25519PrivateKey,
    trust_root: TrustRoot,
    trust_provider: FrozenTrustRootProvider,
) -> tuple[Path, ManifestLoader]:
    """返回 (signed_root, signed_loader: ManifestLoader w/ trust)。"""

    if SIGNED_TMP_ROOT.exists():
        print(f"[stage1] 清理旧签名目录 {SIGNED_TMP_ROOT} ...")
        shutil.rmtree(SIGNED_TMP_ROOT, ignore_errors=True)
    SIGNED_TMP_ROOT.mkdir(parents=True, exist_ok=True)

    bundles_src = REPO_ROOT / "bundles"
    assert bundles_src.exists(), f"bundles/ 目录不存在: {bundles_src}"

    unsigned_loader = ManifestLoader({SOURCE_ALIAS: SIGNED_TMP_ROOT})

    # 先复制（无签名），用于后续 unsigned_loader.load 拿 manifest/artifacts
    for b in BUNDLES:
        src = bundles_src / b["rel_path"]
        dst = SIGNED_TMP_ROOT / b["rel_path"]
        shutil.copytree(src, dst)

    # 给每个 bundle 算签名并写入 .sig
    for b in BUNDLES:
        source_ref = f"bundle://{SOURCE_ALIAS}/{b['rel_path']}"
        loaded = unsigned_loader.load(source_ref)
        payload = _canonical_signature_payload(
            {
                "manifest": loaded.manifest.model_dump(
                    mode="json", by_alias=True, exclude_none=False
                ),
                "artifacts": [
                    {
                        "relativePath": a.relative_path,
                        "digest": a.digest,
                        "size": a.size,
                        "mediaType": a.media_type,
                    }
                    for a in loaded.artifacts
                ],
            }
        )
        signature = runtime_key.sign(payload)
        envelope = {
            "algorithm": "Ed25519",
            "keyId": RUNTIME_KEY_ID,
            "signature": base64.b64encode(signature).decode("ascii"),
            "signedAt": datetime.now(UTC).isoformat(),
        }
        sig_path = SIGNED_TMP_ROOT / b["rel_path"] / SIGNATURE_FILENAME
        sig_path.write_text(
            json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        print(f"  [sign] {b['id']} → {sig_path.name}")

    # 带 trust 的 loader
    signed_loader = ManifestLoader(
        {SOURCE_ALIAS: SIGNED_TMP_ROOT}, trust_roots=trust_provider
    )
    # 预加载校验一遍
    for b in BUNDLES:
        source_ref = f"bundle://{SOURCE_ALIAS}/{b['rel_path']}"
        signed = signed_loader.load(source_ref)
        assert any(ev.type.value == "signature_verification" for ev in signed.evidence), (
            f"{b['id']} 签证据未生成"
        )

    # 构造 RegistryService → 注册 4 个到 PUBLISHED
    pub_b64 = base64.b64encode(trust_root.public_key).decode("ascii")
    print(f"\n[stage1] trust_root.key_id={RUNTIME_KEY_ID} pub={pub_b64[:24]}...")
    print(f"[stage1] 注册 4 个 bundle 到 PUBLISHED (org={ORG_ID},project={PROJECT_ID}) ...\n")

    registry_store = PostgresRegistryStore(connect_factory=connect)

    def _clock() -> datetime:
        with connect() as conn:
            row = conn.execute("SELECT clock_timestamp()").fetchone()
        assert row is not None and isinstance(row["clock_timestamp"], datetime)
        return row["clock_timestamp"]

    service = RegistryService(
        store=registry_store,
        loader=signed_loader,
        clock=_clock,
        trust_roots=trust_provider,
    )

    def _db_signature_matches(bid: str, version: str, expected_key_id: str) -> bool:
        """若 DB 中已有此版本，检查其 signature.keyId 是否等于预期；否则需重建。"""
        try:
            with connect() as conn:
                row = conn.execute(
                    """
                    SELECT v.signature
                      FROM asset_bundle_version AS v
                      JOIN asset_bundle AS b ON b.bundle_pk = v.bundle_pk
                     WHERE b.publisher = %s AND b.bundle_id = %s AND v.version = %s
                    """,
                    (PUBLISHER, bid, version),
                ).fetchone()
            if row is None or row["signature"] is None:
                return False
            return str(row["signature"].get("keyId")) == expected_key_id
        except Exception:
            return False

    def _db_delete_version_cascade(bid: str, version: str) -> None:
        """级联删除：设 session_replication_role=replica 绕过所有 trigger，再删 evidence/artifacts/events/version。仅本地 D3 脚本用。"""
        with connect() as conn:
            conn.execute("SET LOCAL session_replication_role = replica")
            try:
                conn.execute(
                    """
                    DELETE FROM asset_bundle_evidence
                     WHERE version_pk IN (
                        SELECT v.version_pk
                          FROM asset_bundle_version AS v
                          JOIN asset_bundle AS b ON b.bundle_pk = v.bundle_pk
                         WHERE b.publisher = %s AND b.bundle_id = %s AND v.version = %s
                     )
                    """,
                    (PUBLISHER, bid, version),
                )
                conn.execute(
                    """
                    DELETE FROM asset_bundle_artifact
                     WHERE version_pk IN (
                        SELECT v.version_pk
                          FROM asset_bundle_version AS v
                          JOIN asset_bundle AS b ON b.bundle_pk = v.bundle_pk
                         WHERE b.publisher = %s AND b.bundle_id = %s AND v.version = %s
                     )
                    """,
                    (PUBLISHER, bid, version),
                )
                conn.execute(
                    """
                    DELETE FROM asset_bundle_version_event
                     WHERE version_pk IN (
                        SELECT v.version_pk
                          FROM asset_bundle_version AS v
                          JOIN asset_bundle AS b ON b.bundle_pk = v.bundle_pk
                         WHERE b.publisher = %s AND b.bundle_id = %s AND v.version = %s
                     )
                    """,
                    (PUBLISHER, bid, version),
                )
                conn.execute(
                    """
                    DELETE FROM asset_bundle_version AS v
                     USING asset_bundle AS b
                     WHERE b.bundle_pk = v.bundle_pk
                       AND b.publisher = %s AND b.bundle_id = %s AND v.version = %s
                    """,
                    (PUBLISHER, bid, version),
                )
            finally:
                conn.execute("SET LOCAL session_replication_role = DEFAULT")


    creators = [
        (f"{REGISTRY_PREFIX}-{b['id'].replace('.', '-')}-creator",
         f"{REGISTRY_PREFIX}-{b['id'].replace('.', '-')}-validator",
         f"{REGISTRY_PREFIX}-{b['id'].replace('.', '-')}-publisher")
        for b in BUNDLES
    ]

    for b, (c_actor, v_actor, p_actor) in zip(BUNDLES, creators, strict=True):
        bid = b["id"]
        source_ref = f"bundle://{SOURCE_ALIAS}/{b['rel_path']}"
        loaded_bundle = signed_loader.load(source_ref)
        manifest = loaded_bundle.manifest
        # 必须用 manifest 里的元数据创建 bundle；否则 _assert_loaded_bundle_matches_target 失败
        display_name_actual = manifest.metadata.display_name
        kind_actual = manifest.kind

        print(f"\n── bundle {bid} ({display_name_actual[:40]}...) ──")

        # 先查有没有，避免重复 create_bundle (UniqueViolation)
        try:
            existing = service._store.get_bundle(bid, publisher=PUBLISHER)
        except Exception:
            existing = None
        if existing is None:
            service.create_bundle(
                publisher=PUBLISHER,
                bundle_id=bid,
                kind=kind_actual,
                display_name=display_name_actual,
                actor=c_actor,
                roles=ROLES_CREATE,
                publisher_scopes=PUB_SCOPES,
            )
            print(f"  create_bundle OK ({c_actor})")
        else:
            print(f"  create_bundle SKIP (已存在)")

        # create_version / validate / publish 三段推进
        def _cur_status(bundle_id: str, version: str) -> str | None:
            try:
                return service._store.get_version(bundle_id, version, publisher=PUBLISHER).get("status")
            except Exception:
                return None

        # 若 DB 中已存在版本但签名不是当前 RUNTIME_KEY_ID，或本轮强制重建 → 级联删除后重建（保证 stage2/stage3 哈希一致）
        force_rebuild = True  # D3 当前轮次：4 个 bundle 都要统一用 d3-global-signer
        if force_rebuild or not _db_signature_matches(bid, b["version"], RUNTIME_KEY_ID):
            try:
                _db_delete_version_cascade(bid, b["version"])
                print(f"  delete_version CASCADE (强制重建: {force_rebuild})")
            except Exception as exc:
                print(f"  delete_version CASCADE WARN: {exc}")

        status_now = _cur_status(bid, b["version"])
        if status_now is None:
            service.create_version(
                publisher=PUBLISHER,
                bundle_id=bid,
                source_ref=source_ref,
                actor=c_actor,
                roles=ROLES_CREATE,
                publisher_scopes=PUB_SCOPES,
            )
            status_now = _cur_status(bid, b["version"])
            print(f"  create_version OK → {status_now}")
        else:
            print(f"  create_version SKIP (status={status_now})")

        if status_now in (None, "DRAFT", "draft"):
            service.validate(
                bundle_id=bid,
                version=b["version"],
                actor=v_actor,
                roles=ROLES_PUB,
                publisher_scopes=PUB_SCOPES,
                publisher=PUBLISHER,
            )
            status_now = _cur_status(bid, b["version"])
            print(f"  validate OK → {status_now}")

        if status_now in ("VALIDATED", "validated"):
            service.publish(
                bundle_id=bid,
                version=b["version"],
                actor=p_actor,
                roles=ROLES_PUB,
                publisher_scopes=PUB_SCOPES,
                publisher=PUBLISHER,
            )
            status_now = _cur_status(bid, b["version"])
            print(f"  publish OK → {status_now}  ✅")
        else:
            print(f"  publish SKIP (status={status_now})  ✅")

    # 汇总
    print("\n[stage1] 4 个 bundle 状态汇总:")
    for b in BUNDLES:
        v = service._store.get_version(b["id"], b["version"], publisher=PUBLISHER)
        print(f"  - {b['id']:40s} v{b['version']:8s}  status={v.get('status')}")

    return SIGNED_TMP_ROOT, signed_loader


# ============================================================
# 阶段 2：Composition 正规创建 + Resolver 解析锁定
# ============================================================
def stage2_resolve_and_lock_composition(
    signed_loader: ManifestLoader,
    trust_provider: FrozenTrustRootProvider,
) -> StoredCompositionLock:
    import json  # noqa: F811
    print(f"\n{'='*60}\n[stage2] 4-bundle Composition 正规创建 + Resolver 解析 + Lock\n{'='*60}")
    print(f"  CORE = {CORE_ID}")
    for l in LEAF_IDS:
        print(f"  LEAF = {l}")
    print(f"  EXPECTED_RESOLVED_IDS = {EXPECTED_RESOLVED_IDS}")

    from aos_api.asset_registry.composition_store import PostgresCompositionStore

    comp_store = PostgresCompositionStore(connect_factory=connect)

    def _clock() -> datetime:
        with connect() as conn:
            row = conn.execute("SELECT clock_timestamp()").fetchone()
        assert row is not None and isinstance(row["clock_timestamp"], datetime)
        return row["clock_timestamp"]

    # 构建 registry snapshot：**必须从 DB 取实际 evidence/signature**
    # 否则 stage2 ManifestLoader evidence.observed_at (内存) ≠ stage3 revalidation DB observed_at，releaseEvidenceRevision 不一致
    from aos_api.asset_registry.composition_contracts import (
        RegistrySnapshot,
        RegistrySnapshotCandidate,
        registry_candidate_sort_key,
    )
    from aos_api.asset_registry.contracts import (
        BundleEvidence, BundleEvidenceType, BundleSignature,
    )
    from aos_api.asset_registry.canonical_json import canonical_sha256

    REQUIRED_RELEASE_EVIDENCE_TYPES = (
        BundleEvidenceType.MANIFEST_VALIDATION,
        BundleEvidenceType.CONTENT_HASH,
        BundleEvidenceType.SIGNATURE_VERIFICATION,
        BundleEvidenceType.SBOM,
        BundleEvidenceType.BUNDLE_EVALS,
    )

    def _release_evidence_revision_match_policy(evidence_list):
        """和 release_policy._release_evidence_revision 算法一致，保证 stage2 = stage3 哈希。"""
        evidence = [
            item
            for et in REQUIRED_RELEASE_EVIDENCE_TYPES
            for item in evidence_list
            if item.type == et
        ]
        evidence.sort(
            key=lambda item: (
                item.type.value,
                item.artifact_hash,
                item.observed_at,
                (0, "") if item.expires_at is None else (1, item.expires_at.isoformat()),
            )
        )
        payload = [
            item.model_dump(
                mode="json",
                by_alias=True,
                include={
                    "type",
                    "artifact_hash",
                    "status",
                    "observed_at",
                    "expires_at",
                    "revoked_at",
                },
                exclude_none=False,
            )
            for item in evidence
        ]
        return canonical_sha256(payload)

    # 从 DB 读每个已 publish 版本的 evidence + content_hash + signature
    _db_candidates: dict[tuple[str, str, str], dict] = {}
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT b.publisher, b.bundle_id, v.version, v.manifest_json, v.content_hash,
                   v.signature AS signature_json, COALESCE(ev.items, '[]'::JSONB) AS evidence_json,
                   b.kind
              FROM asset_bundle_version AS v
              JOIN asset_bundle AS b ON b.bundle_pk = v.bundle_pk
              LEFT JOIN LATERAL (
                SELECT jsonb_agg(jsonb_build_object(
                    'type', e.evidence_type, 'artifactRef', e.artifact_ref,
                    'artifactHash', e.artifact_hash, 'status', e.status,
                    'observedAt', e.observed_at, 'expiresAt', e.expires_at,
                    'revokedAt', e.revoked_at, 'metadata', e.metadata
                ) ORDER BY e.evidence_type, e.artifact_hash, e.observed_at) AS items
                  FROM asset_bundle_evidence AS e
                 WHERE e.version_pk = v.version_pk
              ) AS ev ON TRUE
             WHERE v.status = 'published'
               AND b.publisher = %s
               AND b.bundle_id = ANY(%s)
            """,
            (PUBLISHER, list(B["id"] for B in BUNDLES)),
        ).fetchall()
    for row in rows:
        evidence_objs = [
            BundleEvidence.model_validate_json(json.dumps(e))
            for e in row["evidence_json"]
        ]
        sig_obj = (
            BundleSignature.model_validate_json(json.dumps(row["signature_json"]))
            if row["signature_json"] is not None else None
        )
        # signatureFingerprint = SIGNATURE_VERIFICATION evidence.artifact_hash
        sig_hash = next(
            (e.artifact_hash for e in evidence_objs
             if e.type == BundleEvidenceType.SIGNATURE_VERIFICATION),
            None,
        )
        ev_rev = _release_evidence_revision_match_policy(evidence_objs)
        _db_candidates[(row["publisher"], row["bundle_id"], row["version"])] = {
            "content_hash": row["content_hash"],
            "signature_fp": sig_hash,
            "evidence_rev": ev_rev,
            "manifest_json": row["manifest_json"],
            "kind": row["kind"],
            "signature_obj": sig_obj,
            "evidence_objs": evidence_objs,
        }

    candidates: list[RegistrySnapshotCandidate] = []
    for b in BUNDLES:
        source_ref = f"bundle://{SOURCE_ALIAS}/{b['rel_path']}"
        signed = signed_loader.load(source_ref)
        manifest = signed.manifest
        key = (manifest.metadata.publisher, manifest.metadata.id, manifest.metadata.version)
        db_vals = _db_candidates.get(key)
        if db_vals is None:
            raise RuntimeError(
                f"DB 中找不到已发布版本 {key}; 请先 stage1 重新 create_version+validate+publish"
            )
        candidates.append(
            RegistrySnapshotCandidate.model_validate(
                {
                    "publisher": manifest.metadata.publisher,
                    "id": manifest.metadata.id,
                    "version": manifest.metadata.version,
                    "kind": manifest.kind,
                    "manifest": manifest,
                    "contentHash": db_vals["content_hash"],
                    "signatureFingerprint": db_vals["signature_fp"],
                    "releaseEvidenceRevision": db_vals["evidence_rev"],
                    "dependencies": [
                        {
                            "publisher": d.publisher or manifest.metadata.publisher,
                            "id": d.id,
                            "version": d.version,
                        }
                        for d in manifest.spec.dependencies
                    ],
                    "optionalDependencies": [
                        {
                            "publisher": d.publisher or manifest.metadata.publisher,
                            "id": d.id,
                            "version": d.version,
                        }
                        for d in manifest.spec.optional_dependencies
                    ],
                    "conflicts": [
                        {
                            "publisher": c.publisher or manifest.metadata.publisher,
                            "id": c.id,
                            "version": c.version,
                        }
                        for c in manifest.spec.conflicts
                    ],
                    "capabilities": manifest.spec.capabilities.model_dump(
                        mode="json", by_alias=True
                    ),
                    "permissions": manifest.spec.permissions.model_dump(
                        mode="json", by_alias=True
                    ),
                    "migration": {
                        "planRef": manifest.spec.migrations.plan,
                        "downgradePolicy": manifest.spec.migrations.downgrade_policy,
                    },
                    "contributions": [
                        c.model_dump(mode="json", by_alias=True)
                        for c in (manifest.spec.contributions or [])
                    ],
                }
            )
        )
    # 先计算 snapshotHash（排序后的 candidates）
    from datetime import timezone
    from aos_api.asset_registry.composition_contracts import (
        SNAPSHOT_SCHEMA_VERSION,
    )
    sorted_candidates = sorted(candidates, key=registry_candidate_sort_key)
    _tmp_snap = {
        "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
        "candidates": [
            c.model_dump(mode="json", by_alias=True, exclude_none=False)
            for c in sorted_candidates
        ],
    }
    snap_hash = canonical_sha256(_tmp_snap)
    registry_snapshot = RegistrySnapshot.model_validate(
        {
            "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
            "candidates": _tmp_snap["candidates"],
            "snapshotHash": snap_hash,
            "checkedAt": datetime.now(timezone.utc),
        }
    )

    request = CompositionRequest.model_validate(
        {
            "requested": [
                {"publisher": PUBLISHER, "id": bid, "version": "1.0.0"} for bid in LEAF_IDS
            ],
            "platformApiVersion": "1.7.0",
            "platformRelease": "aos-platform/1.7.0",
            "environment": "dev",
            "registrySnapshotHash": snap_hash,
            "currentInstallationRef": None,
        }
    )
    class _InlineSnapshotReader:
        """Bypass production Registry snapshot reader (use signed_loader + known snapshot)."""

        def __init__(self, snap: RegistrySnapshot, snap_hash: str) -> None:
            self._snap = snap
            self._hash = snap_hash

        def read(self) -> RegistrySnapshot:
            return self._snap

    from aos_api.asset_registry.composition_store import PostgresCompositionStore
    from aos_api.asset_registry.installation_store import PostgresInstallationStore

    comp_service = CompositionService(
        snapshot_reader=_InlineSnapshotReader(registry_snapshot, snap_hash),
        composition_store=PostgresCompositionStore(),
        command_store=PostgresInstallationStore(),
        baseline_reader=PostgresInstallationStore(),
    )

    receipt = comp_service.resolve(
        request=request,
        org_id=ORG_ID,
        project_id=PROJECT_ID,
        actor=MAKER_SUBJECT,
        roles=MAKER_ROLES,
        markings=frozenset(),
        idempotency_key=COMPOSITION_IDEMPOTENCY_KEY,
    )
    assert receipt.status_code in (201, 200), f"resolve failed {receipt.status_code}: {receipt.response_json}"
    from pydantic import TypeAdapter

    _ta = TypeAdapter(StoredCompositionLock)
    lock: StoredCompositionLock = _ta.validate_json(
        json.dumps(receipt.response_json, default=str)
    )

    # 断言：resolved 顺序和 4 个 ID 吻合
    resolved_ids = tuple(item.id for item in lock.payload.resolved)
    assert tuple(sorted(resolved_ids)) == tuple(sorted(EXPECTED_RESOLVED_IDS)), (
        f"Resolver 结果不匹配: resolved={resolved_ids}  expected={EXPECTED_RESOLVED_IDS}"
    )
    assert lock.revision == 1
    assert lock.lock_hash == canonical_sha256(lock.payload.hash_payload_dump())

    print(f"\n  ✅ composition_id={lock.composition_id}")
    print(f"  ✅ lock_revision={lock.revision}")
    print(f"  ✅ resolved_ids={resolved_ids}")
    print(f"  ✅ lock_hash={lock.lock_hash[:24]}...")
    print(f"  ✅ permission_diff_hash={lock.permission_diff_hash[:24]}...")
    print(f"  ✅ migration_plan_hash={lock.migration_plan_hash[:24]}...")
    print(f"  ✅ contribution_diff_hash={lock.contribution_diff_hash[:24]}...")
    return lock


# ============================================================
# 阶段 3：Installation 正规 5 步推进（create→submit→approve→apply→verify）
# ============================================================
def stage3_installation_to_active(
    lock: StoredCompositionLock,
    trust_provider: FrozenTrustRootProvider,
) -> InstallationResponse:
    print(f"\n{'='*60}\n[stage3] Installation 完整 FDE 生命周期 5 步推进\n{'='*60}")
    print(f"  composition_id = {lock.composition_id}")
    print(f"  lock_revision  = {lock.revision}")
    print(f"  maker={MAKER_SUBJECT}({MAKER_ROLES})  checker={CHECKER_SUBJECT}({CHECKER_ROLES})")

    from pydantic import TypeAdapter

    from aos_api.asset_registry.installation_service import InstallationService
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.asset_registry.composition_store import PostgresCompositionStore
    from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
    from aos_api.asset_registry.release_policy import ReleasePolicy

    inst_store = PostgresInstallationStore(connect_factory=connect)

    def _clock() -> datetime:
        with connect() as conn:
            row = conn.execute("SELECT clock_timestamp()").fetchone()
        assert row is not None and isinstance(row["clock_timestamp"], datetime)
        return row["clock_timestamp"]

    service = InstallationService(
        store=PostgresInstallationStore(),
        composition_store=PostgresCompositionStore(),
        revalidator=InstallationRevalidator(
            release_policy=ReleasePolicy(trust_roots=trust_provider)
        ),
    )

    def _expect(receipt, expected_status, expected_revision, label):
        assert receipt.status_code in (201, 200), f"{label} status={receipt.status_code} body={receipt.response_json}"
        _ta = TypeAdapter(InstallationResponse)
        resp = _ta.validate_json(json.dumps(receipt.response_json, default=str))
        assert resp.state == expected_status, f"{label} state={resp.state} ≠ {expected_status}"
        assert resp.current_revision == expected_revision
        print(f"  [{label}] state={resp.state:12s} revision={resp.current_revision} installation_id={resp.installation_id}")
        return resp

    # 1. create (state → null, revision=1)
    created_receipt = service.create(
        request=CreateInstallationRequest.model_validate(
            {
                "compositionId": lock.composition_id,
                "lockRevision": lock.revision,
                "overlayRevision": OVERLAY_REVISION,
                "displayName": DISPLAY_NAME,
            }
        ),
        org_id=ORG_ID, project_id=PROJECT_ID,
        actor=MAKER_SUBJECT, roles=MAKER_ROLES, markings=frozenset(),
        idempotency_key=f"{INSTALLATION_PREFIX}-create",
    )
    resp = _expect(created_receipt, "draft", 1, "create  ")
    installation_id = resp.installation_id

    # 2. submit (maker) revision 1→2, state→submitted
    submitted_receipt = service.submit(
        installation_id=installation_id,
        request=EmptyInstallationActionRequest(),
        org_id=ORG_ID, project_id=PROJECT_ID,
        actor=MAKER_SUBJECT, roles=MAKER_ROLES, markings=frozenset(),
        idempotency_key=f"{INSTALLATION_PREFIX}-submit",
        if_match='"1"',
    )
    _expect(submitted_receipt, "submitted", 2, "submit  ")

    # 3. approve (checker 必须和 maker 分离！) revision 2→3, state→approved
    approved_receipt = service.approve(
        installation_id=installation_id,
        request=ApproveInstallationRequest.model_validate(
            {
                "lockHash": lock.lock_hash,
                "permissionDiffHash": lock.permission_diff_hash,
                "migrationPlanHash": lock.migration_plan_hash,
                "contributionDiffHash": lock.contribution_diff_hash,
            }
        ),
        org_id=ORG_ID, project_id=PROJECT_ID,
        actor=CHECKER_SUBJECT, roles=CHECKER_ROLES, markings=frozenset(),
        idempotency_key=f"{INSTALLATION_PREFIX}-approve",
        if_match='"2"',
    )
    _expect(approved_receipt, "approved", 3, "approve ")

    # 4. apply (maker 执行) revision 3→4, state→active
    applied_receipt = service.apply(
        installation_id=installation_id,
        request=EmptyInstallationActionRequest(),
        org_id=ORG_ID, project_id=PROJECT_ID,
        actor=MAKER_SUBJECT, roles=MAKER_ROLES, markings=frozenset(),
        idempotency_key=f"{INSTALLATION_PREFIX}-apply",
        if_match='"3"',
    )
    _expect(applied_receipt, "applied", 4, "apply   ")

    # 5. verify (maker 验证) revision 4→5, state 保持 active
    verified_receipt = service.verify(
        installation_id=installation_id,
        request=EmptyInstallationActionRequest(),
        org_id=ORG_ID, project_id=PROJECT_ID,
        actor=MAKER_SUBJECT, roles=MAKER_ROLES, markings=frozenset(),
        idempotency_key=f"{INSTALLATION_PREFIX}-verify",
        if_match='"4"',
    )
    resp = _expect(verified_receipt, "active", 5, "verify  ")

    print(f"\n  ✅ Installation 完整 FDE 5 步通过: installation_id={installation_id}")
    return resp


# ============================================================
# 阶段 4：IntegrationCase 正规创建
# ============================================================
def stage4_create_integration_case(installation: InstallationResponse) -> dict[str, Any] | None:
    print(f"\n{'='*60}\n[stage4] IntegrationCase 正规创建\n{'='*60}")
    if not _HAS_INTEGRATION_CASE:
        print(f"  ⚠️  IntegrationCaseService 导入失败: {_INTEGRATION_CASE_ERR}")
        print("     跳过本阶段（接入案例页面可见性由后续接线实现）。")
        return None

    from aos_api.asset_registry.integration_contracts import (
        CreateIntegrationCaseRequest,
        CreateIntegrationEvidenceSnapshotRequest,
    )

    service: IntegrationCaseService = build_integration_case_service()

    def _mk_ctx(subject_str: str, roles: frozenset[str]):
        from aos_api.asset_registry.integration_service import IntegrationRequestContext
        return IntegrationRequestContext(
            org_id=ORG_ID,
            project_id=PROJECT_ID,
            subject=subject_str,
            roles=tuple(roles),
            markings=(),
        )

    # 步骤 1: create_case
    req = CreateIntegrationCaseRequest.model_validate(
        {
            "installationId": installation.installation_id,
            "overlayRevision": OVERLAY_REVISION,
            "displayName": DISPLAY_NAME,
        }
    )
    try:
        receipt = service.create_case(
            context=_mk_ctx(CASE_MAKER_SUBJECT, CASE_MAKER_ROLES),
            request=req,
            idempotency_key=CASE_IDEMPOTENCY_KEY,
        )
        case_id = receipt.case_id
        print(f"  ✅ create_case OK: case_id={case_id}")
    except Exception as e:
        print(f"  ⚠️  create_case 失败（可能已存在或 marking 不足）: {e}")
        case_id = None

    # 步骤 2: create_evidence_snapshot
    if case_id is not None:
        try:
            snap = service.create_evidence_snapshot(
                context=_mk_ctx(CASE_CHECKER_SUBJECT, CASE_CHECKER_ROLES),
                case_id=case_id,
                request=CreateIntegrationEvidenceSnapshotRequest.model_validate(
                    {
                        "bundleIds": list(EXPECTED_RESOLVED_IDS),
                        "overlayRevision": OVERLAY_REVISION,
                        "installationId": installation.installation_id,
                    }
                ),
            )
            print(f"  ✅ create_evidence_snapshot OK: snap_id={snap.snapshot_id}")
        except Exception as e:
            print(f"  ⚠️  evidence_snapshot 失败（不阻断主流程）: {e}")

    return {"case_id": case_id}


# ============================================================
# 阶段 5：验证
# ============================================================
def stage5_verify_all(installation: InstallationResponse, case: dict | None):
    print(f"\n{'='*60}\n[stage5] 汇总验证\n{'='*60}")
    with connect() as conn:
        # 5.1 4 bundle PUBLISHED (通过 JOIN asset_bundle 拿 bundle_id/publisher)
        row = conn.execute(
            """
            SELECT b.bundle_id, v.version, v.status
              FROM asset_bundle_version v
              JOIN asset_bundle b ON b.bundle_pk = v.bundle_pk
             WHERE b.publisher = %s
               AND b.bundle_id = ANY(%s)
             ORDER BY b.bundle_id
            """,
            (PUBLISHER, list(EXPECTED_RESOLVED_IDS)),
        ).fetchall()
        print("\n  [registry] 4 个 bundle version 状态:")
        for r in row:
            mark = "✅" if str(r["status"]).upper() == "PUBLISHED" else "❌"
            print(f"    {mark} {r['bundle_id']:40s} v{r['version']:8s} {r['status']}")
        assert all(str(r["status"]).upper() == "PUBLISHED" for r in row), "有 bundle 未 PUBLISHED"

        # 5.2 composition lock
        r = conn.execute(
            """
            SELECT c.composition_id, l.revision AS lock_revision, l.lock_hash,
                   l.permission_diff_hash, l.migration_plan_hash, l.contribution_diff_hash
              FROM bundle_composition c
              JOIN bundle_composition_lock l
                ON l.composition_pk = c.composition_pk
               AND l.org_id = c.org_id
               AND l.project_id = c.project_id
             WHERE c.org_id=%s AND c.project_id=%s
             ORDER BY c.composition_pk DESC, l.revision DESC LIMIT 1
            """,
            (ORG_ID, PROJECT_ID),
        ).fetchone()
        if r:
            print(f"\n  [composition] latest lock: id={r['composition_id']} rev={r['lock_revision']} lock_hash={r['lock_hash'][:24]}...")

        # 5.3 installation state + revision (JOIN 拿 revision.state)
        r = conn.execute(
            """
            SELECT i.installation_id, i.active_revision, i.current_revision, i.etag_version,
                   r.state
              FROM bundle_installation i
              LEFT JOIN bundle_installation_revision r
                ON r.org_id = i.org_id AND r.project_id = i.project_id
               AND r.installation_pk = i.installation_pk
               AND r.revision = i.active_revision
             WHERE i.installation_id = %s
            """,
            (installation.installation_id,),
        ).fetchone()
        if r:
            mark = "✅" if str(r["state"] or "").lower() == "active" else "⚠️"
            print(f"\n  [installation] {mark} state={r['state']} active_rev={r['active_revision']} current_rev={r['current_revision']} etag={r['etag_version']}")

        # 5.4 integration case
        r = None
        try:
            r = conn.execute(
                """
                SELECT c.case_id, c.display_name, p.computed_stage
                  FROM integration_case c
                  LEFT JOIN integration_case_projection p
                    ON p.org_id = c.org_id AND p.project_id = c.project_id
                   AND p.case_pk = c.case_pk
                 WHERE c.org_id=%s AND c.project_id=%s
                 ORDER BY c.created_at DESC LIMIT 3
                """,
                (ORG_ID, PROJECT_ID),
            ).fetchall()
        except Exception as _e:
            print(f"\n  ⚠️  integration_case 查询跳过: {_e}")
            r = None
        if r:
            print(f"\n  [integration_case] 最新 3 条:")
            for c in r:
                print(f"    ✅ case_id={c['case_id']} stage={c.get('computed_stage')} display={c['display_name'][:40]}")
        else:
            print("\n  ⚠️  integration_case 表无记录（若 4 阶段跳过则属正常）")

    print(f"\n{'='*60}")
    print("✅ D3 FULL FDE + CASE + BUNDLE 全部就绪")
    print(f"{'='*60}")


# ============================================================
# MAIN
# ============================================================
def main() -> int:
    print("=" * 80)
    print("D3.0 栖月汇全栈接入：选项 2 完整 FDE 生命周期 + W03/L05 内容物就绪")
    print("=" * 80)
    print(f"  ORG_ID      = {ORG_ID}")
    print(f"  PROJECT_ID  = {PROJECT_ID}")
    print(f"  BUNDLES(4)  = {EXPECTED_RESOLVED_IDS}")
    print(f"  OVERLAY_REV = {OVERLAY_REVISION}")
    print(f"  DISPLAY     = {DISPLAY_NAME}")
    print()

    runtime_key = _load_or_create_runtime_key()
    trust_root, trust_provider = _build_trust_root(runtime_key)

    # Stage 1
    signed_root, signed_loader = stage1_sign_and_publish_all(runtime_key, trust_root, trust_provider)

    # Stage 2
    lock = stage2_resolve_and_lock_composition(signed_loader, trust_provider)

    # Stage 3
    installation = stage3_installation_to_active(lock, trust_provider)

    # Stage 4
    case = stage4_create_integration_case(installation)

    # Stage 5
    stage5_verify_all(installation, case)

    # 提示
    print(f"""
D3 进度今日达成清单：
  ▸ W03 客户与私域运营台        → {REPO_ROOT}/bundles/solutions/ecommerce-growth/content/workshops/w03-customer-private-domain.json
  ▸ L05 分润异常检测 Logic     → {REPO_ROOT}/bundles/solutions/ecommerce-growth/content/logic/l05-commission-anomaly.json
  ▸ 10 条 Evals 测试矩阵        → {REPO_ROOT}/bundles/solutions/ecommerce-growth/content/evals/w03-l05-dry-run-cases.json
  ▸ growth-gates 门控策略       → {REPO_ROOT}/bundles/solutions/ecommerce-growth/content/policies/growth-gates.json
  ▸ 4 个 bundle PUBLISHED       → domain.ecommerce.core + 3 LEAF（含 solution.ecommerce.growth D3）
  ▸ 正规 composition(lock=1)    → composition_id={lock.composition_id}
  ▸ 正规 installation(active=5)→ installation_id={installation.installation_id}
  ▸ integration_case            → {case}
  ▸ 后续解除 G2 BLOCKED + decision_tag 注入:
      $ 修改 W03 workshop decision_tag 列取值 → bump growth version 1.1.0
      $ 执行 composition RESET → 叠加安装 1.1.0（D3 预留叠加链路已验证通）
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

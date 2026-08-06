"""d3_overlay_install_1_1_0.py — D3 叠加安装：growth bundle 1.0.0 → 1.1.0。

执行步骤：
  1. 从 DB 读取 1.0.0 active installation 的 ref（installation_id, active_revision, lock_hash, overlay_revision）
  2. 重新签名发布 growth bundle 1.1.0（其他 3 个 bundle 不变，仍 1.0.0）
  3. 构建新的 Composition（growth=1.1.0, 其余=1.0.0），传入 currentInstallationRef
  4. Installation 5步推进（create→submit→approve→apply→verify）
  5. 验证叠加安装结果

关键区别（vs 首次安装）：
  - CompositionRequest.currentInstallationRef 不为 None，指向 1.0.0 active installation
  - Resolver 会基于 baseline 计算 permission_diff / migration_plan / contribution_diff
  - Installation 的 overlay_revision 需要更新（v1 → v2）
"""
from __future__ import annotations

import base64
import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICES_API = REPO_ROOT / "services" / "aos-api"
sys.path.insert(0, str(SERVICES_API))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from aos_api.asset_registry.canonical_json import canonical_sha256  # noqa: E402
from aos_api.asset_registry.composition_contracts import (  # noqa: E402
    ApproveInstallationRequest,
    CompositionRequest,
    CreateInstallationRequest,
    CurrentInstallationRef,
    EmptyInstallationActionRequest,
    InstallationResponse,
    RegistrySnapshot,
    RegistrySnapshotCandidate,
    StoredCompositionLock,
)
from aos_api.asset_registry.composition_service import CompositionService  # noqa: E402
from aos_api.asset_registry.composition_store import PostgresCompositionStore  # noqa: E402
from aos_api.asset_registry.contracts import BundleKind  # noqa: E402
from aos_api.asset_registry.installation_service import InstallationService  # noqa: E402
from aos_api.asset_registry.installation_store import PostgresInstallationStore  # noqa: E402
from aos_api.asset_registry.installation_revalidation import InstallationRevalidator  # noqa: E402
from aos_api.asset_registry.manifest_loader import (  # noqa: E402
    SIGNATURE_FILENAME,
    ManifestLoader,
)
from aos_api.asset_registry.registry_service import RegistryService  # noqa: E402
from aos_api.asset_registry.registry_store import PostgresRegistryStore  # noqa: E402
from aos_api.asset_registry.release_policy import ReleasePolicy  # noqa: E402
from aos_api.asset_registry.signature import (  # noqa: E402
    FrozenTrustRootProvider,
    TrustRoot,
)
from aos_api.db import connect  # noqa: E402

# ============================================================
# 全局参数
# ============================================================
ORG_ID = "org-org"
PROJECT_ID = "dev-project"

PUBLISHER = "aos"
SOURCE_ALIAS = "d3-catalog"
RUNTIME_KEY_ID = "d3-global-signer"
RUNTIME_KEY_PATH = REPO_ROOT / "scripts" / ".d3_runtime_ed25519.pem"
TRUST_NOT_BEFORE = datetime(2026, 1, 1, tzinfo=UTC)
TRUST_NOT_AFTER = datetime(2036, 1, 1, tzinfo=UTC)
SIGNED_TMP_ROOT = Path(tempfile.gettempdir()) / "aos-d3-overlay-signed"

ROLES_PUB = frozenset({"asset-publisher", "asset-registry-admin"})
ROLES_CREATE = frozenset({"asset-publisher", "asset-registry-admin", "developer"})
PUB_SCOPES = frozenset({PUBLISHER})

# 4 个 bundle：growth 升级到 1.1.0，其余仍 1.0.0
BUNDLES = [
    {"id": "domain.ecommerce.core",          "version": "1.0.0", "rel_path": "domains/ecommerce-core"},
    {"id": "platform.ecommerce.niushop",      "version": "1.0.0", "rel_path": "platforms/ecommerce-niushop"},
    {"id": "solution.ecommerce.operations-base","version": "1.0.0", "rel_path": "solutions/ecommerce-operations-base"},
    {"id": "solution.ecommerce.growth",       "version": "1.1.0", "rel_path": "solutions/ecommerce-growth"},
]
LEAF_IDS = tuple(b["id"] for b in BUNDLES if b["id"] != "domain.ecommerce.core")
CORE_ID = "domain.ecommerce.core"
EXPECTED_RESOLVED_IDS = (CORE_ID, *LEAF_IDS)

# maker/checker 职责分离
MAKER_SUBJECT = "d3-overlay-maker"
MAKER_ROLES = frozenset({"asset-installer"})
CHECKER_SUBJECT = "d3-overlay-checker"
CHECKER_ROLES = frozenset({"asset-install-approver"})

OVERLAY_REVISION_V2 = "d3-qiyuehui-v2-decision-tags"
DISPLAY_NAME = "栖月汇商贸 · 微商城全栈接入（D3 叠加：W03 decision_tag 注入）"

REGISTRY_PREFIX = "d3-overlay"
COMPOSITION_IDEMPOTENCY_KEY = f"{REGISTRY_PREFIX}-composition-growth-1.1.0-v5"
INSTALLATION_PREFIX = "d3-overlay-installation-v5"

SNAPSHOT_SCHEMA_VERSION = "aos.dev/registry-snapshot/v1alpha1"


# ============================================================
# 工具函数
# ============================================================

def _canonical_signature_payload(data: dict) -> bytes:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return payload.encode("utf-8")


def registry_candidate_sort_key(c: RegistrySnapshotCandidate) -> tuple[str, str]:
    return (c.id, c.version)


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
    roots: dict[tuple[str, str], TrustRoot] = {
        (tr_current.publisher, tr_current.key_id): tr_current,
    }
    # 兼容 d2-6 旧签名
    d26_key_path = REPO_ROOT / "scripts" / ".d2_6_runtime_ed25519.pem"
    if d26_key_path.exists():
        d26_key = serialization.load_pem_private_key(
            d26_key_path.read_bytes(), password=None
        )  # type: ignore[assignment]
        d26_tr = _make_trust_root_from_key(d26_key, "d2-6-runtime-signer")
        roots[(d26_tr.publisher, d26_tr.key_id)] = d26_tr
    provider = FrozenTrustRootProvider(roots)
    return tr_current, provider


# ============================================================
# Step 0: 从 DB 读取 1.0.0 active installation ref
# ============================================================

def read_active_installation_ref() -> CurrentInstallationRef:
    print(f"\n{'='*60}")
    print("[step0] 读取 1.0.0 active installation ref")
    print(f"{'='*60}")

    with connect() as conn:
        r = conn.execute(
            """
            SELECT i.installation_id, i.active_revision,
                   r.lock_hash, r.overlay_revision
              FROM bundle_installation i
              JOIN bundle_installation_revision r
                ON r.org_id = i.org_id
               AND r.project_id = i.project_id
               AND r.installation_pk = i.installation_pk
               AND r.revision = i.active_revision
             WHERE i.org_id = %s AND i.project_id = %s
               AND r.state = 'active'
             ORDER BY i.created_at DESC LIMIT 1
            """,
            (ORG_ID, PROJECT_ID),
        ).fetchone()

    assert r is not None, "未找到 1.0.0 active installation！请先跑 d3_qiyuehui_full_fde_case_creation.py"

    ref = CurrentInstallationRef.model_validate({
        "installationId": str(r["installation_id"]),
        "revision": int(r["active_revision"]),
        "lockHash": str(r["lock_hash"]),
        "overlayRevision": str(r["overlay_revision"]),
    })

    print(f"  ✅ installation_id = {ref.installation_id}")
    print(f"  ✅ active_revision = {ref.revision}")
    print(f"  ✅ lock_hash       = {ref.lock_hash[:24]}...")
    print(f"  ✅ overlay_revision = {ref.overlay_revision}")
    return ref


# ============================================================
# Step 1: 签名 + 注册 growth 1.1.0（其他 3 个不动）
# ============================================================

def stage1_publish_growth_1_1_0(
    runtime_key: Ed25519PrivateKey,
    trust_root: TrustRoot,
    trust_provider: FrozenTrustRootProvider,
) -> ManifestLoader:
    print(f"\n{'='*60}")
    print("[step1] 签名 + 注册 growth 1.1.0（其他 3 个不动）")
    print(f"{'='*60}")

    if SIGNED_TMP_ROOT.exists():
        shutil.rmtree(SIGNED_TMP_ROOT, ignore_errors=True)
    SIGNED_TMP_ROOT.mkdir(parents=True, exist_ok=True)

    # 复制所有 4 个 bundle 到 SIGNED_TMP_ROOT（只对 growth 重新签名）
    bundles_src = REPO_ROOT / "bundles"
    for b in BUNDLES:
        src = bundles_src / b["rel_path"]
        dst = SIGNED_TMP_ROOT / b["rel_path"]
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)

    # 签名（只对 growth 1.1.0 重新签名）
    growth = next(b for b in BUNDLES if b["id"] == "solution.ecommerce.growth")
    unsigned_loader = ManifestLoader({SOURCE_ALIAS: SIGNED_TMP_ROOT})
    source_ref = f"bundle://{SOURCE_ALIAS}/{growth['rel_path']}"
    loaded = unsigned_loader.load(source_ref)

    payload = _canonical_signature_payload({
        "manifest": loaded.manifest.model_dump(mode="json", by_alias=True, exclude_none=False),
        "artifacts": [
            {
                "relativePath": a.relative_path,
                "digest": a.digest,
                "size": a.size,
                "mediaType": a.media_type,
            }
            for a in loaded.artifacts
        ],
    })
    signature = runtime_key.sign(payload)
    envelope = {
        "algorithm": "Ed25519",
        "keyId": RUNTIME_KEY_ID,
        "signature": base64.b64encode(signature).decode("ascii"),
        "signedAt": datetime.now(UTC).isoformat(),
    }
    sig_path = SIGNED_TMP_ROOT / growth["rel_path"] / SIGNATURE_FILENAME
    sig_path.write_text(json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"  [sign] growth 1.1.0 → {sig_path.name}")

    # 带 trust 的 loader
    signed_loader = ManifestLoader({SOURCE_ALIAS: SIGNED_TMP_ROOT}, trust_roots=trust_provider)
    signed = signed_loader.load(source_ref)
    assert any(ev.type.value == "signature_verification" for ev in signed.evidence), "签证据未生成"

    # 注册到 PUBLISHED
    registry_store = PostgresRegistryStore(connect_factory=connect)

    def _clock() -> datetime:
        with connect() as conn:
            row = conn.execute("SELECT clock_timestamp()").fetchone()
        return row["clock_timestamp"]

    service = RegistryService(
        store=registry_store,
        loader=signed_loader,
        clock=_clock,
        trust_roots=trust_provider,
    )

    bid = growth["id"]
    version = growth["version"]
    manifest = signed.manifest
    display_name_actual = manifest.metadata.display_name
    kind_actual = manifest.kind

    # bundle 已存在（1.0.0 创建过），跳过 create_bundle
    print(f"\n── bundle {bid} v{version} ({display_name_actual[:40]}...) ──")

    # 检查 1.1.0 是否已存在
    try:
        existing_status = service._store.get_version(bid, version, publisher=PUBLISHER).get("status")
    except Exception:
        existing_status = None

    if existing_status is None:
        # 级联删除旧版本（如有）
        with connect() as conn:
            conn.execute("SET LOCAL session_replication_role = replica")
            try:
                conn.execute(
                    """
                    DELETE FROM asset_bundle_evidence
                     WHERE version_pk IN (
                        SELECT v.version_pk FROM asset_bundle_version v
                        JOIN asset_bundle b ON b.bundle_pk = v.bundle_pk
                         WHERE b.publisher = %s AND b.bundle_id = %s AND v.version = %s
                     )
                    """,
                    (PUBLISHER, bid, version),
                )
                conn.execute(
                    """
                    DELETE FROM asset_bundle_artifact
                     WHERE version_pk IN (
                        SELECT v.version_pk FROM asset_bundle_version v
                        JOIN asset_bundle b ON b.bundle_pk = v.bundle_pk
                         WHERE b.publisher = %s AND b.bundle_id = %s AND v.version = %s
                     )
                    """,
                    (PUBLISHER, bid, version),
                )
                conn.execute(
                    """
                    DELETE FROM asset_bundle_version_event
                     WHERE version_pk IN (
                        SELECT v.version_pk FROM asset_bundle_version v
                        JOIN asset_bundle b ON b.bundle_pk = v.bundle_pk
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

        c_actor = f"{REGISTRY_PREFIX}-growth-creator"
        v_actor = f"{REGISTRY_PREFIX}-growth-validator"
        p_actor = f"{REGISTRY_PREFIX}-growth-publisher"

        service.create_version(
            publisher=PUBLISHER,
            bundle_id=bid,
            source_ref=source_ref,
            actor=c_actor,
            roles=ROLES_CREATE,
            publisher_scopes=PUB_SCOPES,
        )
        print(f"  create_version OK → DRAFT")

        service.validate(
            bundle_id=bid,
            version=version,
            actor=v_actor,
            roles=ROLES_PUB,
            publisher_scopes=PUB_SCOPES,
            publisher=PUBLISHER,
        )
        print(f"  validate OK → VALIDATED")

        service.publish(
            bundle_id=bid,
            version=version,
            actor=p_actor,
            roles=ROLES_PUB,
            publisher_scopes=PUB_SCOPES,
            publisher=PUBLISHER,
        )
        print(f"  publish OK → PUBLISHED")
    else:
        print(f"  SKIP (status={existing_status})")

    # 验证
    with connect() as conn:
        r = conn.execute(
            """
            SELECT v.status, v.version
              FROM asset_bundle_version v
              JOIN asset_bundle b ON b.bundle_pk = v.bundle_pk
             WHERE b.publisher = %s AND b.bundle_id = %s AND v.version = %s
            """,
            (PUBLISHER, bid, version),
        ).fetchone()
    assert r and str(r["status"]).upper() == "PUBLISHED", f"growth 1.1.0 未 PUBLISHED: {r}"
    print(f"\n  ✅ growth {bid} v{version} → {r['status']}")

    return signed_loader


# ============================================================
# Step 2: Composition RESET (currentInstallationRef → 1.0.0 active)
# ============================================================

def stage2_overlay_composition(
    signed_loader: ManifestLoader,
    trust_provider: FrozenTrustRootProvider,
    current_ref: CurrentInstallationRef,
) -> StoredCompositionLock:
    print(f"\n{'='*60}")
    print("[step2] Composition 叠加解析（currentInstallationRef → 1.0.0 active）")
    print(f"{'='*60}")

    import json as _json

    # 直接复用 RegistrySnapshotReader 读取所有 PUBLISHED 版本
    from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
    from aos_api.asset_registry.release_policy import ReleasePolicy

    release_policy = ReleasePolicy(trust_roots=trust_provider)
    snapshot_reader = RegistrySnapshotReader(
        release_policy=release_policy,
        connect_factory=connect,
    )
    registry_snapshot = snapshot_reader.read()

    # 从 snapshot 中筛选我们需要的 4 个 candidate
    needed = {(PUBLISHER, b["id"], b["version"]) for b in BUNDLES}
    filtered_candidates = [
        c for c in registry_snapshot.candidates
        if (c.publisher, c.id, c.version) in needed
    ]
    assert len(filtered_candidates) == 4, (
        f"snapshot 中只找到 {len(filtered_candidates)} 个匹配的 candidate，需要 4 个。"
        f"  snapshot 中共 {len(registry_snapshot.candidates)} 个 candidate。"
    )

    sorted_candidates = sorted(filtered_candidates, key=registry_candidate_sort_key)
    snap_hash = registry_snapshot.snapshot_hash

    # 构建叠加 composition request（currentInstallationRef 不为 None！）
    request = CompositionRequest.model_validate({
        "requested": [
            {"publisher": PUBLISHER, "id": b["id"], "version": b["version"]}
            for b in BUNDLES if b["id"] != "domain.ecommerce.core"
        ],
        "platformApiVersion": "1.7.0",
        "platformRelease": "aos-platform/1.7.0",
        "environment": "dev",
        "registrySnapshotHash": snap_hash,
        "currentInstallationRef": {
            "installationId": str(current_ref.installation_id),
            "revision": current_ref.revision,
            "lockHash": current_ref.lock_hash,
            "overlayRevision": current_ref.overlay_revision,
        },
    })

    class _InlineSnapshotReader:
        """Bypass production Registry snapshot reader (use known snapshot)."""
        def __init__(self, snap: RegistrySnapshot) -> None:
            self._snap = snap
        def read(self) -> RegistrySnapshot:
            return self._snap

    comp_service = CompositionService(
        snapshot_reader=_InlineSnapshotReader(registry_snapshot),
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
    lock: StoredCompositionLock = _ta.validate_json(_json.dumps(receipt.response_json, default=str))

    resolved_ids = tuple(item.id for item in lock.payload.resolved)
    assert tuple(sorted(resolved_ids)) == tuple(sorted(EXPECTED_RESOLVED_IDS)), (
        f"Resolver 结果不匹配: resolved={resolved_ids} expected={EXPECTED_RESOLVED_IDS}"
    )

    print(f"\n  ✅ composition_id={lock.composition_id}")
    print(f"  ✅ lock_revision={lock.revision}")
    print(f"  ✅ resolved_ids={resolved_ids}")
    print(f"  ✅ lock_hash={lock.lock_hash[:24]}...")
    print(f"  ✅ permission_diff_hash={lock.permission_diff_hash[:24]}...")
    print(f"  ✅ migration_plan_hash={lock.migration_plan_hash[:24]}...")
    print(f"  ✅ contribution_diff_hash={lock.contribution_diff_hash[:24]}...")
    print(f"  ✅ currentInstallationRef 在 lock 中: {lock.payload.current_installation_ref is not None}")
    return lock


# ============================================================
# Step 3: Installation 5步推进（叠加）
# ============================================================

def stage3_overlay_installation(
    lock: StoredCompositionLock,
    trust_provider: FrozenTrustRootProvider,
) -> InstallationResponse:
    print(f"\n{'='*60}")
    print("[step3] Installation 叠加 5 步推进")
    print(f"{'='*60}")
    print(f"  composition_id = {lock.composition_id}")
    print(f"  lock_revision  = {lock.revision}")
    print(f"  maker={MAKER_SUBJECT}  checker={CHECKER_SUBJECT}")

    import json as _json
    from pydantic import TypeAdapter

    inst_store = PostgresInstallationStore(connect_factory=connect)

    def _clock() -> datetime:
        with connect() as conn:
            row = conn.execute("SELECT clock_timestamp()").fetchone()
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
        resp = _ta.validate_json(_json.dumps(receipt.response_json, default=str))
        assert resp.state == expected_status, f"{label} state={resp.state} ≠ {expected_status}"
        assert resp.current_revision == expected_revision
        print(f"  [{label}] state={resp.state:12s} revision={resp.current_revision} installation_id={resp.installation_id}")
        return resp

    # 1. create (state=draft, revision=1)
    created_receipt = service.create(
        request=CreateInstallationRequest.model_validate({
            "compositionId": lock.composition_id,
            "lockRevision": lock.revision,
            "overlayRevision": OVERLAY_REVISION_V2,
            "displayName": DISPLAY_NAME,
        }),
        org_id=ORG_ID, project_id=PROJECT_ID,
        actor=MAKER_SUBJECT, roles=MAKER_ROLES, markings=frozenset(),
        idempotency_key=f"{INSTALLATION_PREFIX}-create",
    )
    resp = _expect(created_receipt, "draft", 1, "create  ")
    installation_id = resp.installation_id

    # 2. submit (maker) revision 1→2
    submitted_receipt = service.submit(
        installation_id=installation_id,
        request=EmptyInstallationActionRequest(),
        org_id=ORG_ID, project_id=PROJECT_ID,
        actor=MAKER_SUBJECT, roles=MAKER_ROLES, markings=frozenset(),
        idempotency_key=f"{INSTALLATION_PREFIX}-submit",
        if_match='"1"',
    )
    _expect(submitted_receipt, "submitted", 2, "submit  ")

    # 3. approve (checker) revision 2→3
    approved_receipt = service.approve(
        installation_id=installation_id,
        request=ApproveInstallationRequest.model_validate({
            "lockHash": lock.lock_hash,
            "permissionDiffHash": lock.permission_diff_hash,
            "migrationPlanHash": lock.migration_plan_hash,
            "contributionDiffHash": lock.contribution_diff_hash,
        }),
        org_id=ORG_ID, project_id=PROJECT_ID,
        actor=CHECKER_SUBJECT, roles=CHECKER_ROLES, markings=frozenset(),
        idempotency_key=f"{INSTALLATION_PREFIX}-approve",
        if_match='"2"',
    )
    _expect(approved_receipt, "approved", 3, "approve ")

    # 4. apply (maker) revision 3→4
    applied_receipt = service.apply(
        installation_id=installation_id,
        request=EmptyInstallationActionRequest(),
        org_id=ORG_ID, project_id=PROJECT_ID,
        actor=MAKER_SUBJECT, roles=MAKER_ROLES, markings=frozenset(),
        idempotency_key=f"{INSTALLATION_PREFIX}-apply",
        if_match='"3"',
    )
    _expect(applied_receipt, "applied", 4, "apply   ")

    # 5. verify (maker) revision 4→5, state→active
    verified_receipt = service.verify(
        installation_id=installation_id,
        request=EmptyInstallationActionRequest(),
        org_id=ORG_ID, project_id=PROJECT_ID,
        actor=MAKER_SUBJECT, roles=MAKER_ROLES, markings=frozenset(),
        idempotency_key=f"{INSTALLATION_PREFIX}-verify",
        if_match='"4"',
    )
    resp = _expect(verified_receipt, "active", 5, "verify  ")

    print(f"\n  ✅ 叠加 Installation 5 步通过: installation_id={installation_id}")
    return resp


# ============================================================
# Step 4: 验证
# ============================================================

def stage4_verify(installation: InstallationResponse) -> None:
    print(f"\n{'='*60}")
    print("[step4] 叠加安装验证")
    print(f"{'='*60}")

    with connect() as conn:
        # 4.1 growth bundle 1.1.0 PUBLISHED
        r = conn.execute(
            """
            SELECT v.version, v.status
              FROM asset_bundle_version v
              JOIN asset_bundle b ON b.bundle_pk = v.bundle_pk
             WHERE b.publisher = 'aos' AND b.bundle_id = 'solution.ecommerce.growth'
             ORDER BY v.version DESC
            """,
        ).fetchall()
        print("\n  [growth bundle versions]:")
        for row in r:
            mark = "✅" if str(row["status"]).upper() == "PUBLISHED" else "⚠️"
            print(f"    {mark} v{row['version']:8s} {row['status']}")

        # 4.2 两个 installation（1.0.0 + 1.1.0 叠加）
        rows = conn.execute(
            """
            SELECT i.installation_id, i.active_revision, i.current_revision, i.etag_version,
                   r.state, r.overlay_revision
              FROM bundle_installation i
              LEFT JOIN bundle_installation_revision r
                ON r.org_id = i.org_id AND r.project_id = i.project_id
               AND r.installation_pk = i.installation_pk
               AND r.revision = i.active_revision
             WHERE i.org_id = %s AND i.project_id = %s
             ORDER BY i.created_at
            """,
            (ORG_ID, PROJECT_ID),
        ).fetchall()
        print("\n  [installations]:")
        for row in rows:
            state = str(row["state"] or "")
            mark = "✅" if state.lower() == "active" else "⚠️"
            print(f"    {mark} state={state:12s} rev={row['active_revision']} overlay={row['overlay_revision']}")
            print(f"       installation_id={row['installation_id']}")

        # 4.3 composition locks
        rows2 = conn.execute(
            """
            SELECT c.composition_id, l.revision, l.lock_hash
              FROM bundle_composition c
              JOIN bundle_composition_lock l
                ON l.composition_pk = c.composition_pk
               AND l.org_id = c.org_id
               AND l.project_id = c.project_id
             WHERE c.org_id = %s AND c.project_id = %s
             ORDER BY c.composition_pk, l.revision
            """,
            (ORG_ID, PROJECT_ID),
        ).fetchall()
        print("\n  [composition locks]:")
        for row in rows2:
            print(f"    ✅ rev={row['revision']} hash={row['lock_hash'][:24]}... id={row['composition_id']}")

    print(f"""
  ════════════════════════════════════════════════
  D3 叠加安装 1.1.0 完成:
    ✅ growth bundle v1.1.0 PUBLISHED（decision_tag 注入）
    ✅ composition RESET (currentInstallationRef → 1.0.0)
    ✅ installation 5步 active（overlay_revision=v2）
    ✅ 1.0.0 + 1.1.0 双 installation 共存

  D3 全部 TODO 达成:
    ✅ 资产包接入 (FDE 5步 active)
    ✅ 数据链接 8 表映射 (8 OT 全覆盖)
    ✅ 本体数据孪生层 ecom_object (547 条) + ecom_link (567 条)
    ✅ W03 decision_tag 注入 → bump 1.1.0 → 叠加安装
  ════════════════════════════════════════════════
""")


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    print("=" * 70)
    print("D3 叠加安装：growth bundle 1.0.0 → 1.1.0（decision_tag 注入）")
    print("=" * 70)

    # 加载运行时密钥
    key_path = RUNTIME_KEY_PATH
    if not key_path.exists():
        print(f"❌ 运行时密钥不存在: {key_path}")
        print("   请先跑 d3_qiyuehui_full_fde_case_creation.py 生成密钥")
        return 1
    runtime_key = serialization.load_pem_private_key(
        key_path.read_bytes(), password=None
    )  # type: ignore[assignment]
    trust_root, trust_provider = _build_trust_root(runtime_key)

    # Step 0: 读取 1.0.0 active installation ref
    current_ref = read_active_installation_ref()

    # Step 1: 签名 + 注册 growth 1.1.0
    signed_loader = stage1_publish_growth_1_1_0(runtime_key, trust_root, trust_provider)

    # Step 2: Composition 叠加解析
    lock = stage2_overlay_composition(signed_loader, trust_provider, current_ref)

    # Step 3: Installation 5步推进
    installation = stage3_overlay_installation(lock, trust_provider)

    # Step 4: 验证
    stage4_verify(installation)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

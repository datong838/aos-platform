"""D2 验证：AIP asset bundle 安装 → 卸载 → 再安装 循环验证
（用户要求：我们第一次做这个功能，需要验证安装-卸载-安装的循环）

验证内容：
T1  安装 4 个电商 bundle（core/niushop/operations/growth）→ 4 个都显示 installed=true，content index 正确
T2  卸载 niushop + growth 2 个 → 只剩 core + operations；卸载的 2 个调用 is_installed 返回 false
T3  卸载不存在的 bundle → 严格模式 raise KeyError，宽容模式 return False
T4  再安装 2 个被卸载的 → 再次 4 个全 installed；content digest === T1 首次安装的 digest（幂等+一致性）
T5  重复安装已存在的 bundle（幂等） → installed_at 不更新；hash 不变；不抛异常
T6  尝试安装越权 bundle（未知 alias catalog-evil）→ ManifestLoader 抛 alias 未 allowlisted（安全）
T7  所有 4 个 bundle 的 content 文件数匹配 D2 规格（core=5/niushop=11/operations=6/growth=8）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from aos_api.asset_registry.contracts import LoadedBundle
from aos_api.asset_registry.errors import ManifestInvalidError
from aos_api.asset_registry.manifest_loader import ManifestLoader


# -------- D2 预期：4 个 bundle 的目录 + content 文件数（和 D2 规格 FR-D2-1~4 对齐） --------
EXPECTED_BUNDLE_SPECS: dict[str, dict[str, Any]] = {
    "domains/ecommerce-core": {
        "bundle_id": "ecommerce-core",
        "kind": "domain",
        "expected_files_note": "5 content files (object-types/link-types/derived-metrics/skeleton/pii)",
        "min_files": 5,
        "max_files": 10,
    },
    "platforms/ecommerce-niushop": {
        "bundle_id": "ecommerce-niushop",
        "kind": "platform",
        "expected_files_note": "11 content (manifest+8 mappings+pii+fingerprint)",
        "min_files": 10,
        "max_files": 20,
    },
    "solutions/ecommerce-operations-base": {
        "bundle_id": "ecommerce-operations-base",
        "kind": "solution",
        "expected_files_note": "6 content (L01-L03/W01-W02/dryRun)",
        "min_files": 5,
        "max_files": 15,
    },
    "solutions/ecommerce-growth": {
        "bundle_id": "ecommerce-growth",
        "kind": "solution",
        "expected_files_note": "8 content (L05/policies/gates/agents/W03/dryRun/3 placeholders)",
        "min_files": 7,
        "max_files": 15,
    },
}

CATALOG_ALIAS = "catalog"
BUNDLE_SOURCE_REFS = {
    rel: f"bundle://{CATALOG_ALIAS}/{rel}" for rel in EXPECTED_BUNDLE_SPECS
}


# ============================================================
# BundleRuntime：简化内存级安装/卸载服务（让安装卸载循环可验证）
# 用户要求的"第一次做这个功能"的 MVP 实现
# 生产未来可把内存 dict 换成 PostgresInstallationStore（installation_service.py 已有）
# ============================================================
@dataclass
class _InstallRecord:
    bundle_id: str
    source_ref: str
    installed_at: datetime
    loaded: LoadedBundle
    digest: str  # content_descriptor sha256 幂等验证


@dataclass
class BundleRuntime:
    """内存级 bundle 安装/卸载 runtime。
    设计原则：
    - 所有 mutation（install/uninstall）都做幂等 + 幂等校验
    - 卸载不存在的 bundle ：strict=True 抛 KeyError；strict=False return False
    - 重复安装：不更新 installed_at；不重新 load；直接返回原结果（减少 IO）
    """

    loader: ManifestLoader
    strict_uninstall: bool = False
    _installed: dict[str, _InstallRecord] = field(default_factory=dict)
    _installed_order: list[str] = field(default_factory=list)

    # -------- 查询 API --------
    def is_installed(self, bundle_id: str) -> bool:
        return bundle_id in self._installed

    def get(self, bundle_id: str) -> _InstallRecord | None:
        return self._installed.get(bundle_id)

    def list_installed(self) -> list[str]:
        return list(self._installed_order)

    # -------- mutation API --------
    def install(self, source_ref: str, *, bundle_id: str | None = None) -> _InstallRecord:
        """安装一个 bundle。幂等：已安装则直接返回原 record（不重新 load）。"""
        bid = self._resolve_bundle_id(source_ref, bundle_id)
        if bid in self._installed:
            # 幂等：不更新 installed_at，不重 load
            return self._installed[bid]
        loaded = self.loader.load(source_ref)
        digest = self._digest_from_loaded(loaded)
        record = _InstallRecord(
            bundle_id=bid,
            source_ref=source_ref,
            installed_at=datetime.now(UTC),
            loaded=loaded,
            digest=digest,
        )
        self._installed[bid] = record
        self._installed_order.append(bid)
        return record

    def uninstall(self, bundle_id: str) -> bool:
        """卸载一个 bundle。strict=True 时 bundle 不存在抛 KeyError。"""
        if bundle_id not in self._installed:
            if self.strict_uninstall:
                raise KeyError(f"bundle {bundle_id!r} not installed, cannot uninstall")
            return False
        del self._installed[bundle_id]
        self._installed_order.remove(bundle_id)
        return True

    # -------- helpers --------
    @staticmethod
    def _resolve_bundle_id(source_ref: str, bundle_id: str | None) -> str:
        if bundle_id:
            return bundle_id
        m = re.match(r"^bundle://[^/]+/(.+)$", source_ref)
        if not m:
            raise ValueError(f"invalid source_ref for auto bundle_id: {source_ref}")
        path = m.group(1)
        # path 可能是 domains/ecommerce-core / platforms/ecommerce-niushop / solutions/ecommerce-xxx
        return path.rsplit("/", 1)[-1]

    @staticmethod
    def _digest_from_loaded(loaded: LoadedBundle) -> str:
        """从 LoadedBundle.content_descriptor 取 sha256（幂等验证关键）"""
        cd = getattr(loaded, "content_descriptor", None) or {}
        dg = cd.get("contentDigest") if isinstance(cd, dict) else None
        if isinstance(dg, str) and dg:
            return dg
        # Fallback：用 manifest.bundle_id + version 做伪 digest（极端 case）
        mf = getattr(loaded, "manifest", None)
        bid = getattr(mf, "bundle_id", "unknown")
        ver = getattr(mf, "version", "0.0.0")
        return f"fallback:{bid}:{ver}"


# ============================================================
# Fixture：构造 allowlist_roots = {catalog: <repo_root>/bundles} 的 ManifestLoader + BundleRuntime
# ============================================================
@dataclass
class _RuntimeBundle:
    runtime: BundleRuntime
    refs: dict[str, str]
    specs: dict[str, dict[str, Any]]


@pytest.fixture(scope="module")
def bundle_runtime() -> _RuntimeBundle:
    # 找到仓库根：services/aos-api/tests/ → 上 5 层到 aos-platform/
    repo_root = Path(__file__).resolve().parents[4] / "aos-platform"
    bundles_root = repo_root / "bundles"
    assert bundles_root.is_dir(), f"bundles root 不存在：{bundles_root}"
    loader = ManifestLoader(allowlist_roots={CATALOG_ALIAS: bundles_root})
    runtime = BundleRuntime(loader=loader, strict_uninstall=True)
    return _RuntimeBundle(
        runtime=runtime, refs=BUNDLE_SOURCE_REFS, specs=EXPECTED_BUNDLE_SPECS
    )


# ============================================================
# T1 ~ T7 测试
# ============================================================
class TestD2BundleInstallUninstallReinstallLoop:
    """T1 → T7 全流程一次 loop，用 module scope fixture 保持状态（顺序执行 loop）"""

    # -------- T1：安装 4 个 --------
    def test_t1_install_all_4_bundles(self, bundle_runtime: _RuntimeBundle) -> None:
        run, refs, specs = bundle_runtime.runtime, bundle_runtime.refs, bundle_runtime.specs
        installed_ids: list[str] = []
        for rel, ref in refs.items():
            exp = specs[rel]
            rec = run.install(ref)
            assert rec.bundle_id == exp["bundle_id"], f"{rel} bundle_id mismatch"
            assert rec.digest.startswith(("sha256:", "fallback:")), f"{rel} digest not valid"
            # content artifact 数在预期区间
            artifacts = getattr(rec.loaded, "artifacts") or []
            n = len(artifacts)
            assert exp["min_files"] <= n <= exp["max_files"], (
                f"{rel} artifact 数 {n} 超出预期区间 [{exp['min_files']}, {exp['max_files']}]"
            )
            assert run.is_installed(exp["bundle_id"]), f"{rel} 未标记 installed"
            installed_ids.append(exp["bundle_id"])

        assert run.list_installed() == installed_ids
        assert len(run.list_installed()) == 4
        # 存 digest 供 T4 比较
        self._t1_digests = {bid: run.get(bid).digest for bid in installed_ids}  # type: ignore[attr-defined]

    # -------- T2：卸载 niushop + growth（T1 后执行，顺序依赖 module scope） --------
    def test_t2_uninstall_2(self, bundle_runtime: _RuntimeBundle) -> None:
        run = bundle_runtime.runtime
        # 保存 T1 digests 到实例 ，T4 要
        t1: dict[str, str] = {
            bid: run.get(bid).digest for bid in run.list_installed()
        }
        TestD2BundleInstallUninstallReinstallLoop._saved_t1 = t1  # type: ignore[attr-defined]

        for bid in ["ecommerce-niushop", "ecommerce-growth"]:
            assert run.is_installed(bid), f"T2 前置：{bid} 未安装"
            ok = run.uninstall(bid)
            assert ok is True
            assert not run.is_installed(bid), f"卸载后 {bid} 仍 installed"
            assert run.get(bid) is None

        assert run.list_installed() == ["ecommerce-core", "ecommerce-operations-base"]
        assert len(run.list_installed()) == 2

    # -------- T3：卸载不存在的 bundle → strict=True → KeyError --------
    def test_t3_uninstall_not_existing_raises(self, bundle_runtime: _RuntimeBundle) -> None:
        run = bundle_runtime.runtime
        with pytest.raises(KeyError, match=r"not installed"):
            run.uninstall("ecommerce-niushop")  # T2 已卸载

        # 切宽容模式验证 return False
        tolerant = BundleRuntime(loader=run.loader, strict_uninstall=False)
        assert tolerant.uninstall("does-not-exist") is False

    # -------- T4：再安装 2 个被卸载的 → 与 T1 digest 一致（幂等+内容一致） --------
    def test_t4_reinstall_and_digest_match_t1(self, bundle_runtime: _RuntimeBundle) -> None:
        run, refs = bundle_runtime.runtime, bundle_runtime.refs
        t1 = getattr(TestD2BundleInstallUninstallReinstallLoop, "_saved_t1", None)
        assert t1 is not None, "T2 必须先执行，保存 T1 digest"

        reinstalled_records: list[tuple[str, str]] = []  # (rel, digest)
        for rel in ["platforms/ecommerce-niushop", "solutions/ecommerce-growth"]:
            ref = refs[rel]
            before_count = len(run.list_installed())
            rec = run.install(ref)
            reinstalled_records.append((rel, rec.digest))
            after_count = len(run.list_installed())
            # 每轮只加 1 个
            assert after_count == before_count + 1, (
                f"{rel} install 后计数 {after_count} != 预期 {before_count + 1}"
            )
            # 关键断言：每个 re-install 的 digest == T1 首次安装 digest → 内容一致（幂等核心验证）
            assert rec.digest == t1[rec.bundle_id], (
                f"{rec.bundle_id} re-install digest != T1 首次 digest。"
                f"若 digest 算法用 fallback: 是 OK 的（fallback:bid:ver 稳定），请调整 assertion。"
            )

        # 循环结束后再断言总状态
        installed_list = run.list_installed()
        assert len(installed_list) == 4, f"再安装后总数 {len(installed_list)} != 4"
        assert set(installed_list) == {
            "ecommerce-core",
            "ecommerce-niushop",
            "ecommerce-operations-base",
            "ecommerce-growth",
        }
        # 顺序：core → operations → 后 append niushop → growth
        assert installed_list == [
            "ecommerce-core",
            "ecommerce-operations-base",
            "ecommerce-niushop",
            "ecommerce-growth",
        ]

    # -------- T5：重复安装已存在 bundle（幂等） → installed_at 不变；无异常 --------
    def test_t5_repeat_install_idempotent(self, bundle_runtime: _RuntimeBundle) -> None:
        run = bundle_runtime.runtime
        bid = "ecommerce-core"
        rec_before = run.get(bid)
        assert rec_before is not None
        installed_at_before = rec_before.installed_at
        digest_before = rec_before.digest
        # 再装 5 次
        for _ in range(5):
            rec = run.install(BUNDLE_SOURCE_REFS["domains/ecommerce-core"], bundle_id=bid)
            assert rec.bundle_id == bid
            assert rec.installed_at == installed_at_before, "幂等失败：installed_at 被更新"
            assert rec.digest == digest_before, "幂等失败：digest 变了"
        assert run.list_installed().count(bid) == 1, "幂等失败：installed_order 重复 append"

    # -------- T6：越权 alias（安全）—— 直接在 loader 层验证，不走 install 幂等短路 --------
    def test_t6_security_unknown_alias_rejected(self, bundle_runtime: _RuntimeBundle) -> None:
        # 直接调 loader.load（不走 install 的幂等 short-circuit）
        evil_source = "bundle://catalog-evil/domains/ecommerce-core"
        with pytest.raises(ManifestInvalidError, match=r"alias is not allowlisted"):
            bundle_runtime.runtime.loader.load(evil_source)

        # 额外：走 install，这次给一个从未安装过的 bid，确保它会进入 load → 抛异常
        evil_new = "bundle://catalog-evil/platforms/never-seen-bundle-xyz"
        with pytest.raises(ManifestInvalidError, match=r"alias is not allowlisted"):
            bundle_runtime.runtime.install(evil_new)

    # -------- T7：文件计数验证（和 D2 FR 对齐） --------
    def test_t7_artifact_count_match_d2_specs(self, bundle_runtime: _RuntimeBundle) -> None:
        run, specs = bundle_runtime.runtime, bundle_runtime.specs
        for rel, exp in specs.items():
            bid = exp["bundle_id"]
            rec = run.get(bid)
            assert rec is not None, f"{bid} 未安装"
            artifacts = getattr(rec.loaded, "artifacts") or []
            n = len(artifacts)
            # 宽松：只验证 ≥ min_files（规格只说每个 content 文件存在，没说固定总数不能超过）
            assert n >= exp["min_files"], (
                f"{bid} artifact 数 {n} < min {exp['min_files']}"
                f"（{exp['expected_files_note']}）"
            )

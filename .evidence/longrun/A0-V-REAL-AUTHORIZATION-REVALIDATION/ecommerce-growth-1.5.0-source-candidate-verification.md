# Ecommerce growth 1.5.0 source candidate 验证

日期：2026-09-12

## 结论

新增 fail-closed 单用途生成器和 `solution.ecommerce.growth@1.5.0` 源候选。生成器先校验不可变 1.4.0
完整/backend tree hash 与 reviewed author backend hash，目标已存在即拒绝；随后复制完整 base、整体替换
backend、提升 manifest version/displayName，并将八个 workshop/analyst-template 自有 bundleRef 精确提升到
1.5.0。任一输入或自引用集合漂移都会删除未完成目标并失败。

1.5.0 共 87 个源文件，tree hash
`sha256:34cd4bc2e9f6bc9c2d9ceb0cf8bee16a93232bce374396e075c3afae9c5b43d8`；backend hash
`sha256:0d9a0b6988c1ffbfb79ff4ab2389f4038d81385ab2735389a8a800901c85c302`，与当前作者 backend exact。

## 实测

- generator、runnable candidates、builder qualification fixtures、stage-review 五消息与 structure case：51 passed。
- builder no-argument preflight：PREFLIGHT_GREEN，4 bundles、3 runtime members、8 modules、12 operations；growth
  coordinate 为 1.5.0，schema compatibility hash 保持 `0ae03d...`。
- `py_compile`、`git diff --check` 通过。
- AR2-7 closure：1786 Python modules、156 classified、93 migrated，全部错误数组为空。

## 一致性与风险

- 1.4.0 完整 tree/backend hash 测试已独立固化，工作区对 1.4.0 零修改。
- 1.5.0 保留 1.4.0 的 production profiles、media templates、cost contracts；只替换 backend 与自有版本引用。
- schema compatibility/requirements 与 1.4.0 字节相同，未夹带 package migration。
- 本波仅产生 unsigned source candidate；尚无 runtime image index、OCI image、签名、Registry publish 或
  Installation upgrade，真实租户与 Provider 均未触碰。

## 下一波

在 `colima-aos-extension` 隔离引擎、临时本地 Registry 与仓外输出目录构建四包 candidate，生成新的 build
Receipt；随后用 ephemeral signing qualification 验证 image/config/dependency lock/SBOM/backend/schema tamper
反证。结果只作为 candidate qualification，不发布或安装。

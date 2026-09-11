# Ecommerce growth 1.5.0 candidate 审计验证

日期：2026-09-12

## 结论

确认 1.4.0 是不可变历史快照，当前作者树已产生需要 1.5.0 承载的 14 新增、3 修改 backend delta。
现有构建器仍固定 1.4.0，现有 runnable 测试中“candidate backend 等于作者 backend”单项失败，其余 manifest、
registration、composition/schema 与 fail-closed 四项通过。该失败已定位为版本测试契约过期。

## 证据

- 1.4.0：73 files，tree `4dc6cf...`；backend 20 files，tree `959f15...`。
- 当前作者 backend：34 files，tree `0d9a0b...`。
- `git status` 显示 1.4.0 与作者 bundle 均无本波修改。
- `git log --follow` 确认 1.4.0 由 `4f8ffd61` 首次版本化，后续作者树变化没有修改该快照。
- delta 重算验证通过；AR2-7 closure 扫描 1786 个 Python 模块、156 个分类模块、93 个迁移模块，全部
  错误数组为空；`git diff --check` 通过。

## 风险与下一步

不能通过更新 1.4.0 快照或放宽 exact backend 检查消除失败。下一波必须新增 1.5.0，单独固化 1.4.0 hash，
再将“与作者树相等”移动到 1.5.0。候选通过前不执行 OCI build、签名、Registry publish 或 Installation upgrade。

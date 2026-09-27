# W5CB4 当前源码持久签名包核验（2026-09-27）

## 结论与边界

- 按 `w5cb4-current-code-persistent-signing-plan-20260927.md`，最新四个电商候选包形成可独立校验的本地持久签名树：`SIGNED_TREE_GREEN`。这**不是** Registry 发布、Installation active、Runtime Host ready 或八页可用。
- 本轮没有读商城源、重放旧 12 Run、调用 Provider、迁移原 `aos_meta_head`、启 worker、删除业务数据或覆盖旧签名/构建。

## 可重复的事实

1. 首次签名发现 `ReleasePolicy` 对 growth `1.11.0` 的 `bundle_evals` 缺项正确拒绝；此前一次时钟顺序错误造成 manifest evidence 拒绝。两份失败签名状态均保留在原目录，未重试覆盖。专项真实运行 `test_ecommerce_growth_1_11_candidate.py`、`test_ecommerce_content_capability_budget_runtime.py`、`test_ecommerce_content_review_pending.py` 得 `39 passed, 7 warnings`；据此补充限定为合同测试的 `bundle-evals.json`，明确 Runtime 仍 blocked。
2. 加签名前置：当前四包版本、15 operation/8 module、源树哈希、构建内容哈希、输出树哈希与零效果 Receipt 精确一致；错仓库路径、坏 Receipt、已有 state 拒绝。新增测试连同增长专项/当前构建 profile 累计 `45 passed, 7 warnings`，使用 `AOS_TEST_RETAIN_DATABASE=1`。
3. 新建并保留 `/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ`，重新 `--build --retain-artifacts` 得 `BUILD_GREEN`：构建 Receipt SHA256 `231b4d1482dac9382f3c7e9e214e16383df82fb8308c2ec773815892fefd62a8`，输出树 `sha256:961d4877de640a533d3123ea8234af0d66c5a12ee4be32c56d4959f7b97e3d3e`。旧构建树与两份失败签名状态均保留。
4. 全新 `signing-state` 得签名 Receipt SHA256 `1530d5fb03fa052d70a90f89f7ec09d7301455459e2e3034f41998a178369886`，签名树 `sha256:b6aa0dbd0c9d720a8167349d90a9dfbc48b3c689aa4a1746a654aeaa9e0d144d`，trust-root revision `sha256:0a99db8bcb5a2b7ff44ba974c29525cc83b5ad92acd268bf0179add93ab95752`。四个包均通过 ManifestLoader 与 ReleasePolicy；私钥和 trust-roots.json 模式 `0600`、state 目录 `0700`，私钥正文不入 Git/证据。
5. 构建和签名 Receipt 的 Registry/Installation/Provider/外部发布计数均为 0。脚本编译、`git diff --check` 通过。8080/8434 的既有隔离预览不因签名而改动，目录 `MANIFEST_INVALID` 尚未由新安装修复。

## 方案/代码一致性与后续风险

- 补充 eval 是为实际 ReleasePolicy 门禁提供真实专项证据，不宣称自然业务运行或发布资格已全满足。源候选的 `UNBUILT_UNSIGNED` provenance 仍正确描述源树；新外置构建/签名树由独立 Receipt 表达。
- 当前签名工具首次成功路径不覆盖已有 state；未知或部分 state 必须只读对账，不自动覆盖。旧构建 Receipt 记录其构建时 HEAD；下一波 Registry/Installation 应同时核新 Receipt、四包内容哈希和当前 m1 提交，不只信任旧 HEAD 字段。
- 下一波：先细化全新隔离库与正式 Registry/Composition/Installation 的文件级方案，再创建新库/备份和发布，独立读回权限与代次；不得把签名树直接绑定当前恢复库或放宽页面校验。

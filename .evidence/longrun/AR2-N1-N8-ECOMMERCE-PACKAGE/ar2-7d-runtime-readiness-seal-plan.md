# AR2-7D D4 runtime readiness 显式封印

基线 `m1@7df53bc2`。Rules：m1 独占串行、方案先行、最小更改、Red-Green、逐步留证并提交；不 push，230 L0 挂起。

## 已核实问题

`build_runtime_ecommerce_growth_registry()` 只检查九个类名及 `revalidate/execute/verify_receipt` 可调用。当前 `ReviewAdvanceHostService` 虽有这些方法，但生产 `_review_lineage()` 固定拒绝，尚未接通 Decision→Handoff→Task→Brief；因此“类存在”不等于真实权威已闭合。若后续仅补两个 content 类，现有门禁会误启用整体 runtime registry。

## 修改范围

- 维护 `services/aos-api/aos_api/ecommerce_growth_host_composition.py`：增加宿主维护的固定 `RUNTIME_WIRING_PROVEN_OPERATIONS`，初值仅包含已有完整接线证据的 describe、case、schedule put/trigger、data fulfill 五项。AnalysisAdvance 仍为 START-only，resume/reconcile 未接线，不能提前列入。生产 factory 要求该顺序与固定九 operation 完全一致，否则统一 `AR2_7D_RUNTIME_WIRING_REQUIRED`。
- 维护 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_runtime_registry.py`：即使把缺失 content 类替换为形状完整的服务，只要 readiness seal 缺 review/content，仍必须 fail-closed；只有测试内同时提供九类及完整 seal 才验证 registry 绑定结构。
- 新增 verification，记录 registry/HostService 邻接、闭包和独立复核。

该 seal 是宿主代码审查门，不由请求、环境变量、插件或服务类自报；每完成一项真实 authority 接线后才在对应提交中追加。此次不修造 Review/Handoff，不实现 content，不启用 registry，不改变 operation 集合或 Receipt 合同。

## 验证

先运行“九类存在但 seal 不完整”反例，确认旧 factory 会错误构造；修复后运行 runtime registry、canonical router、HTTP、host ports 及六个已接线 HostService 邻接，随后运行 `verify_closure.py --phase ar2-1`、memory validate 和 `git diff --check`。

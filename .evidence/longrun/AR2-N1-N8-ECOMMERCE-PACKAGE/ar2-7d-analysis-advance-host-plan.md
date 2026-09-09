# AR2-7D AnalysisAdvanceHostService（START）

基线 `w1-aip@2478e1ed`。生产 registry 仍会因 review/content 缺项 fail-closed。本切片只补齐 `ecommerce_growth_analysis_advance` 的命名 HostService：接受包合同 `runtime.analysis.start`，回读 Occurrence/Case/Profile，提交可恢复 PREPARING `AnalysisRuntimeReceipt`。`RESUME_DATA` / `RECONCILE_UNKNOWN` 未接线前 fail-closed。不 push，不前推 `AOS-000571`，不宣称整波 7D GREEN。

## 文件

- 维护 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_analysis_advance_host.py`

## 行为

- 命令包络与包内 `build_start_command` 一致，另带 `requestHash`；hash 覆盖去掉 `requestHash` 后的正文，算法与包内 `canonical_command_hash` 相同。
- 禁止租户/dispatch 覆盖键（由 HostPort 已拦）；本服务拒绝未知字段、START 声称先验运行权威、hash 漂移。
- 回读：Occurrence 当前权威哈希与 `occurrenceRef` 一致；Case 当前精确引用与 `caseRef` 一致；Case 上的 `investigationProfileRef` 与 `profileRef` 一致。
- execute：由 `_start_lineage` 取得已存在的 Run/Compilation/Plan/TaskRun 精确引用（不发明假引用、不启动 TaskRun）；构造 incomplete PREPARING Receipt；同事务写入后 `verify_receipt` 原样回读。
- 返回必须含且仅以 `receiptRef` 作为 adapter 目标 Receipt；`completed` 恒为 false；START 不得带 checkpoint/data 谱系。
- 不把旧 investigation HTTP 改成 Canonical 别名；不改 Workshop。

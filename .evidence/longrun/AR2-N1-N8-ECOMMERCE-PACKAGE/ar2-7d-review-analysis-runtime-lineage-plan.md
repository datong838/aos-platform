# AR2-7D Review Analysis / Plan / Run 权威

基线 `m1@10318104`。依据 231-6 AR2-5 exact 输入，Review 必须证明其 `AnalysisRuntimeReceipt` 来自 analysis host 的不可变 runtime Receipt，且其中 BusinessInvestigationRun、CompilationReceipt、当前批准 Plan、AIP TaskRun 与四 Artifact 的 TaskRun 是同一条真实链。

## 修改范围

- 维护 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：按 target receipt exact ref 直读 `public.ecommerce_growth_runtime_command_receipt` 的 analysis operation，重算 AnalysisRuntimeReceipt 正文摘要并核 response/target/request；直读 current BusinessInvestigationRun、`public.aip_business_investigation_compile_receipt` 与 public AIP Task/Plan/TaskRun/Checkpoint，复用 canonical runtime binder 校验当前完成 authority；START Receipt 的历史 TaskRun ref 保持不可变，只用稳定 TaskRun ID、Task、Plan 与 Compilation 身份回链当前 `SUCCEEDED` authority，不用当前状态重建历史 binding hash；要求命令 Run/currentPlan、analysis response、compilation、当前 runtime 与四 Artifact TaskRun一致。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_review_analysis_runtime_authority.py`，并维护 Review Host 纯编排替身：以 public 表返回形状做确定性完整链组合，正例明确覆盖历史 PAUSED v1 START ref 保持不变、当前 TaskRun 已推进到 SUCCEEDED v2，反例覆盖 receipt/case/run/state/compilation/plan/task-run/artifact-run/tenant 漂移和可变 authority 锁；既有 Review Owner PG 测试继续承担事务回滚、tenant 与 TEMP 邻接验证。

## 边界与退出

只读已存在 authority，不创建 Analysis Receipt、BusinessInvestigationRun、Plan、TaskRun、Checkpoint 或 Artifact。`completed=false` 的 N4 Receipt 只作 immutable lineage anchor；可评审产出须另外由同一当前批准 Plan 的 `SUCCEEDED` AIP TaskRun、稳定 Run state 与四类 immutable Artifact 共同证明。本切片证明 exact lineage 与最小完成 Owner，不证明业务结论质量；Review readiness seal 仍须等待完整时序/状态裁决。专项、邻接、closure、memory validate、diff check和独立只读复核通过后提交；无 Provider、Approval、发布或外部业务写入，230 L0挂起。

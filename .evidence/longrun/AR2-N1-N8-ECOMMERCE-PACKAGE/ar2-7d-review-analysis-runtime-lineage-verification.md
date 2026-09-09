# AR2-7D Review Analysis / Plan / Run 权威验证

日期：2026-09-09。基线 `m1@10318104`；方案 `ar2-7d-review-analysis-runtime-lineage-plan.md`。

## 结果

- Review revalidate 以 `public.ecommerce_growth_runtime_command_receipt` 中不可变 Analysis START Receipt 为历史锚，重算正文摘要并逐项核对 response、target exact ref 与 request hash。
- 当前 BusinessInvestigationRun 与 state head 从 `public` Owner 回读；Run/State 原始 JSON 必须与 DTO canonical JSON 等价，正文摘要、tenant、Run、Case 和稳定控制态必须一致，state head 以 `FOR SHARE` 锁定。
- CompilationReceipt 从 `public` Owner 回读，原文、tenant、Run 与当前 Plan exact ref 必须一致；当前 TaskRun、Task 分别锁定，canonical binder 复核当前批准 Plan、Task、Compilation 血缘，并要求 TaskRun 为 `SUCCEEDED`。
- START Receipt 中历史 PAUSED v1 TaskRun ref 保持不变；它只按严格 exact-ref 形状、稳定 TaskRun ID 与版本不倒退回链当前 SUCCEEDED v2 authority，不用当前状态重建历史 binding hash。四类 Artifact 必须来自同一 TaskRun。
- Review Host 仍是 ACCEPT-only 且未加入 readiness seal。本切片没有 Provider、Approval、发布、生产迁移或外部业务写入；230 L0 继续挂起。

## Red / 修正

1. 原 Review Host 未回读 Analysis Receipt、Run、state、Compilation、Plan 或 TaskRun，调用方可拼接 refs。
2. 首版加入 exact 回读后，独立评审发现 START `completed=false` 不能单独证明完成、state 未判定且 mutable authority 未锁；补入当前 `SUCCEEDED` TaskRun、四 Artifact、稳定 state，以及 state/Task/TaskRun 锁。
3. 复核继续发现 Case 未回链、Run 原 JSON 未核、Compilation tenant 未显式限定；逐项 fail-closed。
4. 首轮完成 Owner 又错误地要求 START 历史 TaskRun binding 等于当前完成 binding，真实 PAUSED→SUCCEEDED 生命周期会被拒。最终分离历史 exact ref 与当前完成 authority，并补 PAUSED v1→SUCCEEDED v2 正例。
5. 终审确认最后一项可达性 blocker 关闭，无剩余 blocker。

## 验证

- 专项：Analysis runtime authority + Review Host，`24 passed, 7 warnings in 3.22s`。
- 扩大回归：全部 `test_ecommerce_review_*.py`，`51 passed, 7 warnings in 3.63s`。
- `py_compile` 与 `git diff --check` 通过。
- AR2-1 closure：1707 scanned、91 classified、57 migrated，五类错误数组全空。
- memory validate：`AOS-000571` / `GREEN`，Delivery Receipt 865、Event 2226、Task Receipt 846。
- 独立只读终审：历史/当前 TaskRun 生命周期 blocker 已关闭，无剩余 blocker；实现 SHA-256 `8392c3eb9bd7301c485db9fbdd220ca501debee6bb3bbbe4891458e374291b45`。

## 文件摘要

- `ecommerce_growth_runtime_adapters.py`：`8392c3eb9bd7301c485db9fbdd220ca501debee6bb3bbbe4891458e374291b45`
- `test_ecommerce_review_advance_host.py`：`6b7deff8897b87a30f1c45b3b6197fe8032acafb748c3f1998731de45de5424e`
- `test_ecommerce_review_analysis_runtime_authority.py`：`5d5be11b4b8c538ec22cf88a710a02e0425c810812877ab0ca14841e81e36759`
- 方案：`3d36cad7bd96d3be2135fbcf6e50dbba807031064cae81545cd7a58939f92280`

## 边界与下一步

本切片证明 immutable START anchor 到 current completion authority 的 exact lineage；确定性组合测试没有冒充完整 PG 生命周期。Review readiness seal 还须按清册核完剩余时序、状态裁决与 sealed wiring；230 L0 不在本授权。下一切片继续清册下一未满足退出条件。

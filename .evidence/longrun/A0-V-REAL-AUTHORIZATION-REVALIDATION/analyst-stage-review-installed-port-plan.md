# 经营参谋阶段评审已安装运行端口方案

日期：2026-09-12

基线：`5583a8a6`

状态：实施完成，command 事务分段待办

## 目标与边界

新增异步宿主端口 `InstalledGrowthStageReviewPort`：只接受四种包侧评审 kind、原生 JSON payload
和显式 expected response；固定调用 `ecommerce_growth_review_advance`，每次仅 await 一次注入的
已安装会话调用，并要求响应 exact 相等。

异常、超时、取消、未知结果及旧 1.4.0 的 PermissionError 原样上抛；禁止重发和本地作者树回退。
端口不发现 Installation、不缓存授权、不持有 TenantScope/事务。同步 StageReviewCommand 的事务
分段与 current 重验证下一波另行设计。

## 文件

- 新增 `services/aos-api/aos_api/ecommerce_analyst_stage_review_package_port.py`。
- 新增 `services/aos-api/tests/extension_runtime/test_analyst_stage_review_installed_port.py`。
- 新增 files/verification 并更新 closure manifest。
- 验证参考 `extension_runtime/session_supervisor.py` preHash
  `6b2800505c5904c30a797b0ab98a559f61f85d9421208c3082aa24eaaa9cf63d`；不修改该文件。

## 退出与下一门

四 kind、exact response、非 JSON、异步依赖、旧包拒绝、异常/取消单次调用、编译和 AR2-7 closure
全绿后提交。下一波设计 transaction prepare → IPC → transaction commit/revalidate 三段式 command；
第 9 节、1.5.0 Candidate 和 Installation 仍 PENDING。

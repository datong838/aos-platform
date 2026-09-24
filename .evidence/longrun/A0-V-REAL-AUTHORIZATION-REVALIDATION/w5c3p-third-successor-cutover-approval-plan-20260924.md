# W5c3p 第三继任者九路 Cutover 仅审批方案（2026-09-24）

## 起点

W5c3o `a014b5e2`：第三安装 active/etag5、binding rev4/epoch3 ready/enabled/unfenced，正式 successor registration Receipt `7861c44a-94b4-4e7a-8898-1d9f70a3d214`，hash 需从原 0600 result 精确读回；Receipt 非执行。九路 group `6a402d31-83ad-546c-807f-508c87498ce1` rev365、route rev338、9/9 legacy/fenced。Host PID17302/三 held 资源；12 调度 off、canary0、业务计数 claims40/runs53。W5c3n 对新增 Owner 的旧结论已由 W5c3o 明确纠正。

## 本波范围

只复用既有 cutover policy/审批 Owner，创建 `externalEffectsAllowed=false`、`fallbackAllowed=false`、checkpoint `canonical-router@1` 的新审批，目标固定新安装/generation/epoch3/runtime rev4、九路 group rev365、新注册 Receipt；不 prepare/pause/commit/validate/resume，不改九路/调度，不读商城源。

## 串行步骤

1. 读回注册 Receipt 与 W5c3m live audit、Host/三 held 资源、四来源/预算、九路/12 调度/attempt/canary/业务计数，确认尚无本波 approval、policy 或 cutover operation。
2. 复习 `ecommerce_growth_cutover` 的 prepare/approval 契约、原 `_approve` 的授权身份/租约路径及现行凭据；构造唯一 policy ID 和全新审批键，并冻结 0600 intent。若原审批租约不可用，只读核现有合法恢复机制；不伪造审批。
3. 原审批 Owner 一次提交；独立读回 approval/ref、hash、target、externalEffectsAllowed=false/fallbackAllowed=false。结果未知只读对账，绝不重发。
4. verification、测试、m1 commit。下一波独立 prepare；其后 pause→commit→validate→resume 各自停在正式 Receipt 再进入下一波。12 新 selection/control/definition 另波。

## 停止条件

任何注册/Runtime/Host/资源/预算/九路/调度/在途/canary 漂移、审批身份/租约不当前、旧键存在、提交边界未知或策略允许外部效果，均停写；不借历史审批，不手工 run_definition。

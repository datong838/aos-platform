# W5c3pR Cutover 审批权限恢复方案（2026-09-24）

## 起点与边界

W5c3p `3be8e904`：旧 `_approve` 在 action-type 读取 `meta_action_type` 权限拒绝，`reconcile` 已证明 proposal0/cutover0、九路仍 group365。原私有 intent 保留且不得同键重发。本波先做只读权限与审批路径审计，识别缺口，再最小修复/验证；任何审批提交必须另用全新键与新 intent，且不得绕过 maker/checker、当前 policy、权限或直接写表。

## 串行步骤

1. 对照当前 AIP Action 产品/技术契约、API/Store/DB Role，查 `aos_runtime` 对 action-type、object-type、proposal/draft/approval 与会员/策略表的有效权限；同时核 8080 是否同样受影响。只读，不输出凭据。
2. 明确是部署权限漂移、旧 `_approve` 非现行路径，还是服务真实缺陷；优先原 Owner/现有合法身份。若需迁移，先写文件级修复方案和反例测试，最小授予审批正常路径必需的权限，不开放其它租户或通用写表。
3. 克隆/定向测试与主库应用分别有独立停止条件、提交边界与 Receipt；不得在当前部分波中直接重试旧键。
4. 只有合法现行审批入口、maker/checker 与权限独立验证后，另波新键执行审批。九路、12 调度、商城源始终不动。

## 停止条件

无法证明授权身份、权限过宽、审批模型要求人类确认、任何旧键状态非零、主库变更边界未知，停写并报告；不冒用 checker 或用管理角色强行造票。

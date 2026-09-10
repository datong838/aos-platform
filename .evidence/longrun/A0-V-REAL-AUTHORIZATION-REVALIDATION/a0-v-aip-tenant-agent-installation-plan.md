# A0-V AIP 租户 Agent 安装方案

## 1. 目标

在 18435 隔离恢复克隆中，使用 canonical `POST /v1/aip/agents/install-ecommerce` 为正向租户 `org-org/dev-project` 安装 ecommerce-growth 的 6 个 AgentInstance。安装结果只允许为 provisioning，不创建或激活 Skill/Capability Binding，不触发模型或 Provider。

该动作是 2026-09-10 隔离重建，不是从丢失运行库恢复出的原配置。

## 2. 前置

- 静态目录已由当前 bundle 幂等发布并精确回读 6/37/10；
- 正向与 canary 当前 installed/runnable 均为 0，Binding 均为空；
- API 只连接 `127.0.0.1:18435/aos_meta_head`，migration/QYH Cron/Logic automation/Provider health maintenance 均 disabled/inactive；
- `A0-V-AIP-TENANT-AGENT-INSTALLATION` Task/Lease 在写入前登记。

## 3. 执行

1. 使用固定幂等键 `a0-v-ecommerce-agent-install-v1` 对正向租户执行一次安装；
2. 首次结果必须是 6 created、0 existing、0 runnable，所有实例 status=provisioning；
3. 用同一幂等键重放，必须不新增实例，结果为 0 created、6 existing；
4. 正向 `/v1/aip/agents` 必须精确 6 个，canary 必须 0 个；
5. 对稳定排序首个正向 instanceId 做正向 200、canary 404 exact-id 反查；
6. runtime readiness 的 Skill/Capability Binding 计数必须继续为 0；
7. 重采 A0-V 并记录 installed blocker 的关闭与 runnable/available blocker 的保留。

## 4. 停止规则

- 已有正向实例数量不是 0 时先停止并重新归类为恢复/重放，不执行首次安装断言；
- canary 出现实例、实例直接 active/runnable、Binding 自动新增或数量不为 6 时停止；
- 不在本阶段创建 Binding、刷新 Binding 健康、激活 Agent、物化责任计划或调用 Provider。

## 5. 完成标记

`A0V_AIP_TENANT_AGENT_INSTALLATION_GREEN` 只表示正向租户的 6 个 provisioning AgentInstance 已通过 canonical API 幂等安装且 canary 隔离成立。runnable、Capability available、调查 authority 和真实首链继续 blocked。

# A0-V AIP 租户 Agent 安装验证

## 1. 结果

`A0V_AIP_TENANT_AGENT_INSTALLATION_GREEN`。

正向租户 `org-org/dev-project` 已通过 canonical API 幂等安装 6 个 ecommerce AgentInstance，全部保持 provisioning；canary `dev-org/dev-project` 保持 0 个实例。没有创建 Binding、激活 Agent 或触发 Provider。

## 2. 执行证据

- 目标：`127.0.0.1:18435/aos_meta_head` 隔离恢复克隆；
- API：`POST /v1/aip/agents/install-ecommerce`；
- 幂等键：`a0-v-ecommerce-agent-install-v1`；
- 首次：HTTP 201，created=6、existing=0、runnable=0，status 集合仅 `provisioning`；
- 重放：HTTP 201，created=0、existing=6、runnable=0；
- 仓库外记录：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/logs/a0v-aip-tenant-agent-installation.json`；
- 记录 SHA-256：`fcefdf2161f87a5da0dbb9b7efeaf95dd28970fe6f21dbab7e67bf55e5f9203b`。

## 3. 隔离与无越界检查

| 检查 | 结果 |
|---|---|
| 正向 AgentInstance | 6 |
| canary AgentInstance | 0 |
| 稳定首个 exact ID 正向读取 | HTTP 200 |
| 同一 exact ID canary 读取 | HTTP 404 |
| CapabilityBinding | 0 |
| SkillBinding | 0 |
| active Capability/Skill Binding | 0/0 |
| runnable Agent | 0 |
| Provider/费用/外部副作用 | 0 |

## 4. A0-V 重采

`a0-v-readiness-result.json` 于 `2026-09-10T12:03:37.030282+00:00` 对提交 `ecfc1baed99263d0945a4e6f01e7c0c1bfee04e9` 采集，SHA-256=`74b7d533780130987eb2a385479c582c946d2961a85bf16aeabc71df69321d79`。

- 结果：`A0_V_BLOCKED_WITH_ACTIONABLE_GAPS`；
- blocker：19 降至 17，关闭正向 installedCount 的两处重复投影；
- unverified：1 降至 0，由真实 AgentInstance exact-id 正向 200/canary 404 关闭；
- runnableCount、Agent item readiness、Capability availableCount 继续失败关闭。

阶段验证器输出：`A0_V_EVIDENCE_VALID blockers=17 unverified=0`。

## 5. 一致性与下一步

本次执行严格停在 provisioning，与方案“安装不等于激活”一致。下一步必须先按 exact Agent/Skill/Capability 依赖读取 Binding 创建契约与模型/工具健康要求；不得为了把 6 个 Agent 标成 runnable 而制造空 Binding、伪造健康或绕过 activation service。

恢复库仍来自 2026-08-05 历史备份，本次 6 个实例属于 2026-09-10 隔离重建结果。

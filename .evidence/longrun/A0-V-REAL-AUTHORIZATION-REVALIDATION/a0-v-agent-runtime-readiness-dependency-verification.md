# A0-V Agent Runtime 准备依赖审计验证

## 结论

2026-09-10 对隔离恢复库 `aos-a0v-recovery-pg/aos_meta_head` 完成两次只读审计。两次结果除 `observedAt` 外完全一致，mutation、Provider invocation、external publication 均为 0；`dev-org/dev-project` 七类 tenant-scoped runtime authority 计数全部为 0。

当前结果为 `A0V_AGENT_RUNTIME_READINESS_BLOCKED`，首个未满足门为 `capabilityEvalAndW0b`，确定性下一动作是 `MATERIALIZE_CAPABILITY_EVAL_AND_W0B_AUTHORITY`。

## 当前依赖事实

- 6/6 AgentTemplate 已发布；6/6 AgentInstance 仍为 `provisioning`。
- 37/37 canonical SkillTemplate 为 `evaluated`，published 为 0。
- 10/10 canonical CapabilityRevision 已发布，但 10/10 均保留 `eval_pack_unavailable`、`w0b_contracts_unavailable`、`provider_unknown`、`aip7_route_authority_unavailable`。
- 七类 A0-V configuration policy/head 已存在且 exact 计数为 7。
- active ProviderInstance、current healthy Provider observation、active ModelRoute、frozen EvalContract、current passed EvalGate、LogicPublication、fresh CapabilityBinding、fresh SkillBinding、active AgentInstance、frozen ResponsibilityPlan 当前均为 0。

这说明 Agent 激活不是当前可直接执行节点。应先复用 W-D1～W-D3 正式 Store/合同建立 EvalPack 与 W0B authority；Provider/route 两项在其后独立重验，不能用 Prime 的 GitHub OAuth、环境变量或人工说明代替。

## 验证

- 纯合同测试：5 passed。
- 实际首次/重放：除 `observedAt` 外 JSON 完全一致。
- 首次结果 SHA-256：`7fe16eac1d926456d894c82e321d54baeae9fb35a55874bf1bb01e1e6e124c62`。
- 重放结果 SHA-256：`34b9e2b35ba86c55b34df69a750b4199f3b3015e0965ea8644e2ceff9a712eea`。
- API：`/v1/health` 与 `/v1/ready` 均正常；Web 8434 返回 200。

## 边界与风险

本阶段只读，无数据库 mutation、无 Provider 调用、无外部发布。审计 GREEN 仅代表依赖全部存在；当前仍是 BLOCKED，不是 Agent runtime ready、A0-V GREEN 或首条真实业务链完成。下一阶段写入前必须复核 W-D1～W-D3 脚本是否能绑定当前 10 个 canonical capability revision，并保持固定租户、隔离库、幂等重放与 canary 零污染。

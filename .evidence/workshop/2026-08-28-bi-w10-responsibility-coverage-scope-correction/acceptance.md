# BI-W10-02 职责 Capability coverage 精确收口验收

- 验收时间：2026-08-28 19:31 Asia/Shanghai
- 代码影响：仅职责 coverage 只读计算
- 页面影响：无，浏览器验收 `N/A`
- Provider/secret/Case/Run/Pipeline/Cron/DLQ/业务写入：均未触发

## 修复结论

- 每个 Responsibility Slot 只检查其 `requiredCapabilityIds` 对应的 assignee-owned CapabilityBinding。
- 同一数字同事的其他 active SkillBinding 即使 blocked/stale，也不再污染当前职责。
- 同一个 required Capability 有多个候选时，只要至少一个候选 active、healthy、operational 且 fresh 即形成 coverage；阻断候选不会抹去可用候选。
- required Capability 没有任何匹配 binding、只有 inactive、只有 non-operational 或只有 stale 候选时，仍分别失败关闭。

## 验证

- store、authority、composition、readiness 专项：`35/35 GREEN`。
- 生意探究、SourceReadiness、AIP production contract、OpenAPI 累计：`204/204 GREEN`。
- `git diff --check`：GREEN。
- 真实 `org-org/dev-project` 只读重算：六职责仍均未覆盖，唯一 blocker 为 `CAPABILITY_BINDING_NOT_OPERATIONAL`；这是 required Capability 自身受 Provider Health 过期影响，不再包含非 required 能力的污染。
- `dev-org/dev-project` 没有该计划，租户隔离保持失败关闭。

## 风险边界

本修复没有把当前真实计划改绿或冻结。下一步必须处理 required text Route 的真实 Provider Health 门，禁止伪造 Health、延长 TTL 或绕过 resolver。

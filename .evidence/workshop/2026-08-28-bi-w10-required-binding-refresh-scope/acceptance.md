# BI-W10-02 required-only Binding readiness 刷新验收

- 验收时间：2026-08-28 19:45 Asia/Shanghai
- 真实租户：`org-org/dev-project`
- 负向隔离租户：`dev-org/dev-project`
- 页面影响：无，浏览器验收 `N/A`
- Provider 调用、secret 解析、Case/Run/Pipeline/Cron/DLQ、真实业务数据写入、迁移、发布：均未触发

## 方案与实现一致性

- 协调器先按 ResponsibilityPlan 的每个 agent-instance Slot 汇总 `requiredCapabilityIds`。
- 只保留该 assignee 的 active SkillBinding 所引用、且 Capability 资产 ID 属于其 required 集合的 CapabilityBinding。
- 同一个 CapabilityBinding 被多个 Slot 或 SkillBinding 复用时只读取、刷新一次。
- D01 r2、D02 r2、D03 r4 的 exact revision/hash 选择、Capability 先于 Skill 的求值顺序、fresh-skip 非滑动 TTL 与计划失败关闭语义均保持不变。

## 自动化验证

- 专项：`6/6 GREEN`，覆盖 unrelated Capability 排除与共享 Binding 去重。
- 生意探究、SourceReadiness、AIP production contract、OpenAPI 累计回归：`192/192 GREEN`。
- `compileall`、`git diff --check`：GREEN。

## 真实租户只读/元数据验证

- 首次刷新仅评价 3 个 required CapabilityBinding：`material.collect`、`strategy.plan`、`content.review`；不再评价图像、视频、文案或效果类非 required 能力。
- 随后精确评价 D01/D02/D03，共 `6` 项；立即重入为 `6/6 fresh-skip`，全部 before/after version 相同，证明没有 TTL 滑动或重复更新。
- required text Route 仍诚实返回 `MODEL_ROUTE_BLOCKED`、`PROVIDER_HEALTH_UNAVAILABLE`；三个 SkillBinding 返回 `CAPABILITY_BINDING_NOT_ACTIVE`。
- ResponsibilityPlan 保持 `draft/blocked`，blocker 为 `CAPABILITY_BINDING_NOT_OPERATIONAL`，没有伪造 GREEN 或冻结。
- `dev-org/dev-project` 因没有唯一 BI ResponsibilityPlan 而失败关闭，租户隔离保持。

## 风险边界

本切片只收窄 readiness 评价集合，不改变 required 能力、Route、Health、职责计划或外部运行门。下一步继续核验可安全闭合的 BI-W10/BI-W11 缺口；自然 P07/P08 仍由既定时间窗和长时监控取证，不手工补跑。

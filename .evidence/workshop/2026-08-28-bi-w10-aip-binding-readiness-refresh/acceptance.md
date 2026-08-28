# BI-W10-02 精确 Binding readiness 刷新验收

- 验收时间：2026-08-28 19:14 Asia/Shanghai
- 真实租户：`org-org/dev-project`
- 负向隔离租户：`dev-org/dev-project`
- 页面变更：无，浏览器验收 `N/A`
- 外部副作用、Provider 调用、secret 解析、业务数据写入：均为 0

## 实现与专项验证

- 新增 tenant-scoped readiness 协调器：从当前六职责计划解析 assignee 的 active SkillBinding，先刷新 9 个 CapabilityBinding，再精确刷新 D01 r2、D02 r2、D03 r4 SkillBinding。
- 新鲜结果采用 `fresh-skip`，不会通过重入连续延长 TTL；幂等键绑定 binding id 与 before version。
- 职责计划仅在重新计算得到 `READY` 时冻结；blocked 原因不吞并、不伪造。
- 专项与邻接测试：`35/35 GREEN`。
- 生意探究、SourceReadiness、AIP production contract、OpenAPI 累计回归：`201/201 GREEN`。
- `compileall`、`git diff --check`：GREEN。

## 真实租户 governed 刷新结果

首次运行对 9 个 CapabilityBinding 与 3 个 exact SkillBinding 共 12 项执行 canonical evaluator；第二次立即重入为 `12/12 fresh-skip`，所有 version 保持不变，证明没有重复更新或 TTL 滑动。

真实求值没有调用 Provider，却从现有 authority 得到一致结论：

- 三条 Route 的唯一 blocker 均为 `provider_health_unavailable_or_stale`；最新文本 Health 已于 `2026-08-28T08:01:04Z` 过期，图像与视频 Health 分别停留在 8 月 23 日并已过期。
- 9 个 CapabilityBinding 均为 `blocked`，稳定原因是 `MODEL_ROUTE_BLOCKED` 与 `PROVIDER_HEALTH_UNAVAILABLE`。
- D01/D02/D03 SkillBinding 均为 `blocked`，稳定原因为 `CAPABILITY_BINDING_NOT_ACTIVE`。
- ResponsibilityPlan `responsibility-plan-27275a595e604fd7bdf9@1` 诚实保持 `draft/blocked`，blocker 为 `CAPABILITY_BINDING_NOT_OPERATIONAL`，没有被伪造为 frozen。
- `dev-org/dev-project` 没有该 ResponsibilityPlan，租户隔离保持失败关闭。

## 后续施工结论

本切片已经把“历史 available 但 freshness 过期”收敛为可重复、可审计的 canonical 评价结果。下一切片继续修复职责 coverage 对 assignee 非 required CapabilityBinding 的过宽耦合，并独立处理 Provider Health 的真实安全门；不得用伪造 Health、超长 TTL 或跳过 Route resolver 的方式把状态改绿。

# R3-05 日常任务总控十项共享能力与贡献链验收

- Task：`WORKSHOP-R3-05-COCKPIT-SHARED-CAPABILITY-CHAIN`
- 租户：`org-org/dev-project`
- 页面：`/workshop/cockpit`
- 结论：`WORKSHOP_R3_05_COCKPIT_SHARED_CAPABILITY_CHAIN_GREEN`

## 方案与实现一致性

1. 底部能力带固定呈现 10 个已评审 canonical Capability，不再从任务 blocker 推导两个泛化标签。
2. 能力状态来自 `/v1/aip/capability-catalog` 的 CapabilityRevision；贡献关系只来自 `/v1/aip/agent-registry` 中 SkillTemplate 的 `requiredCapabilities`、`canonicalLogicId` 与 AgentTemplate。
3. 每个能力胶囊可点击、重复点击收起，并支持详情关闭按钮与 Escape；详情展示 exact capability revision、Skill revision、Logic、数字同事与任务总控贡献边界。
4. 目录失败时仍保留 10 个产品能力名称，状态为待核对；没有 canonical 关系时明确显示没有可验证关系，不回退到 blocker，也不补造运行记录。
5. 能力带保持单行并只在内部横向滚动，未抬高或覆盖明日预告、同事列和任务流。

## 自动化验证

- Task Cockpit 专项：`25/25` 通过。
- Web 累计回归：`271 files / 2430 tests` 通过。
- Web production build：`369 modules transformed`，构建通过；仅保留既有 chunk-size 提示。

## 内置浏览器逐项验收

在当前真实租户逐一点击 10 个能力胶囊并读取详情：

| 产品能力 | canonical ID | CapabilityRevision | readiness | canonical 贡献关系 |
| --- | --- | ---: | --- | --- |
| 素材采集 | `material.collect` | 5 | 暂不可用 | 有 |
| 策略规划 | `strategy.plan` | 5 | 可用 | 有 |
| 文案生成 | `copy.generate` | 5 | 暂不可用 | 有 |
| 脚本撰写 | `script.compose` | 5 | 暂不可用 | 有 |
| 语音合成 | `speech.synthesize` | 4 | 暂不可用 | 无；页面未补造 |
| 视频合成 | `video.compose` | 4 | 暂不可用 | 无；页面未补造 |
| 内容审核 | `content.review` | 5 | 暂不可用 | 有 |
| 直播编排 | `live.orchestrate` | 4 | 暂不可用 | 无；页面未补造 |
| 平台适配 | `platform.adapt` | 5 | 暂不可用 | 有 |
| 数据复盘 | `performance.review` | 5 | 暂不可用 | 有 |

内置浏览器确认：10 项顺序与视觉稿一致；横向滚动可访问全部胶囊；策略规划与素材采集详情显示多条真实 Skill/Logic/数字同事链；其余能力逐项打开无报错；关闭按钮和 Escape 均有效；窄视口中详情层没有遮挡底部能力带或明日预告。

## 安全边界

- 本项只读取当前租户能力与数字同事目录，不创建或修改业务数据。
- 未创建 Plan/TaskRun，未调用 Provider，未派发、发送、发布、改价或触发任何真实外部副作用。
- 未读取或修改 `apps/web/src/api/ecommerceWorkshop/parser.ts` 及其测试中的用户未提交内容。


# 今日头条 24 篇技术文章发布方案与状态台账

## 目标

将掘金创作者中心现有 24 篇已发布技术文章，整理为今日头条独立发布稿并逐篇提交。今日头条与掘金分开记录标题限制、正文格式、封面要求、声明选项、提交状态和审核结果，不直接套用掘金审核经验。

## 公开边界

- 不出现真实客户、真实业务数据、账号、密钥、内部路径、服务地址或部署拓扑。
- 不把设计目标描述成已经上线的事实。
- 不为适配平台而捏造案例、收益、测试结果或技术细节。
- 标题和正文可以做平台化排版调整，但不改变技术结论。

## 单篇流程

1. 从源稿复制到本目录并完成脱敏复核。
2. 按 `00-style-and-review-checklist.md` 重写为头条干货稿，不能只做机械换标题或去 Markdown。
3. 提交前记录标题、正文长度、封面、声明和可见性选项。
4. 单篇提交后进入作品管理核验真实状态。
5. 单篇未通过、出现平台限制、验证码或要求不明确时，暂停后续文章。
6. 审核通过后再继续下一篇，并把观察写入本台账。

## 2026-08-04 策略调整

前 2 篇完成试投并已发布。根据头条官方规范，平台明确治理标题低质、题文不符、排版混乱、批量重复或无信息增量、作品声明错误和 AI 生成的虚假低质内容。因此从第 3 篇开始暂停机械搬运，改成“逐篇头条化重写 → 自检 → 发布 → 状态核验”。

该调整是内容质量策略，不代表前两篇存在违规，也不意味着某种写法必然通过审核。

## 文章清单

| 序号 | 今日头条稿件 | 来源 | 状态 |
|---|---|---|---|
| 01 | 01-agent-auditable-decision.md | juejin-series-228/02-evidence-driven-decisions.md | 已发布（2026-08-04 13:34） |
| 02 | 02-agent-task-dag.md | juejin-series-228/03-task-dag-handoff.md | 已发布（2026-08-04 13:41） |
| 03 | 03-agent-memory-governance.md | juejin-series-228/04-memory-governance.md | 待整理 |
| 04 | 04-connector-unknown-state.md | juejin-series-228/05-connector-unknown-state.md | 待整理 |
| 05 | 05-controlled-action.md | juejin-series-228/06-controlled-actions.md | 待整理 |
| 06 | 06-composable-assets.md | juejin-series-228/07-composable-assets.md | 待整理 |
| 07 | 07-enterprise-agent-engine.md | juejin-series-228/08-enterprise-agent-engine.md | 待整理 |
| 08 | 08-ecommerce-agent-loop.md | juejin-series-228/01-operating-loop.md | 待整理 |
| 09 | 09-data-advisor-loop.md | juejin-series-digital-colleagues/01-data-advisor-operating-loop.md | 待整理 |
| 10 | 10-content-order-relay.md | juejin-series-digital-colleagues/02-content-to-order-relay.md | 待整理 |
| 11 | 11-safe-user-context.md | juejin-series-digital-colleagues/03-repeat-purchase-collaboration.md | 待整理 |
| 12 | 12-campaign-guardrails.md | juejin-series-digital-colleagues/04-campaign-decision-guardrails.md | 待整理 |
| 13 | 13-complaint-feedback.md | juejin-series-digital-colleagues/05-complaint-feedback-learning.md | 待整理 |
| 14 | 14-minimal-handoff.md | juejin-series-digital-colleagues/06-safe-handoff-minimal-context.md | 待整理 |
| 15 | 15-governed-memory.md | juejin-series-digital-colleagues/07-governed-memory-evolution.md | 待整理 |
| 16 | 16-action-control-plane.md | juejin-series-digital-colleagues/08-controlled-actions-maturity.md | 待整理 |
| 17 | 17-enterprise-ai-four-layers.md | juejin-series-aos-four-layers/01-aos-four-layer-architecture.md | 待整理 |
| 18 | 18-agent-data-layer.md | juejin-series-aos-four-layers/02-data-operating-system.md | 待整理 |
| 19 | 19-agent-ontology.md | juejin-series-aos-four-layers/03-ontology-digital-twin.md | 待整理 |
| 20 | 20-agent-decision-runtime.md | juejin-series-aos-four-layers/04-aip-decision-runtime.md | 待整理 |
| 21 | 21-agent-workbench.md | juejin-series-aos-four-layers/05-agent-workbench-runtime.md | 待整理 |
| 22 | 22-four-layer-decision-loop.md | juejin-series-aos-four-layers/06-agent-decision-four-layer-loop.md | 待整理 |
| 23 | 23-four-layer-governance.md | juejin-series-aos-four-layers/07-four-layer-governance-spine.md | 待整理 |
| 24 | 24-why-enterprise-ai-os.md | ../../../../docs/palantier/articles/01-why-enterprise-ai-needs-os.md | 待整理 |

## 今日头条审核观察

首篇已形成以下界面观察，尚不能推断内容审核偏好：

- 标题输入框明确限制 2～30 字；首篇使用 23/30 的平台计数后允许提交。
- 发布项支持单图、三图和无封面；首篇选择无封面。
- “头条首发”和“同时发布微头条”在首篇表单中默认开启；因文章已在掘金发布，首篇均主动取消。
- 作品声明提供“引用 AI”等选项；首篇如实勾选“引用 AI”。
- 点击“预览并发布”后仍需在手机预览页点击“确认发布”。
- 确认发布后进入作品管理，首篇显示“审核中”；不能把跳转成功当作审核通过。
- 首篇随后在作品管理页变为“已发布”，未显示驳回原因或整改提示；首篇流程可以作为本批后续文章的操作基线。
- 第 2 篇采用同一选项组合后也直接进入“已发布”；作品管理页存在数秒列表刷新延迟，提交后第一次读取可能仍只显示上一篇，刷新后才出现新文章。

以下项目继续逐篇记录，不能提前写成平台规则：

- 标题长度及敏感表达提示；
- 代码块、英文缩写和特殊符号的编辑器处理；
- 封面图与“无封面”是否允许；
- 原创声明、广告声明及其他发布选项；
- 提交成功、审核中、已发布、未通过的状态名称；
- 审核时间与平台提供的具体原因。

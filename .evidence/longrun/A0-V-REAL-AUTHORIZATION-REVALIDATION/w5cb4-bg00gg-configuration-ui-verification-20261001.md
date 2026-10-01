# BG00GG 费用配置UI与恢复 verification

基线AOS-001047/e5405ddb，复习231-5、440及现有预算面板。仅改现有前端3文件；无API/数据库迁移、正式服务重启。

## 实现和复审
- CostRef configure映射configuration-request，恢复URL只保留原提议ID/operation/attempted；POST仍apiPostUnqueued，不自动提交。
- consume严格解析后保留BudgetRevision exact ref；configure要求完整三类引用及proposal/hash/decision、固定Receipt格式，price/policy ID与Receipt digest后缀相同且revision1；有source时核对提议/决定/预算版本，有consumed时核budget内容hash。浏览器不重建SQL权威hash，最终权限与来源仍由service/DB核验。
- 当前maker、批准未撤销未过期、原消费已observed、配置not_attempted且无attempt、明确确认同时满足才可点。load来源→消费GET→配置GET；身份epoch变化清空来源与消费，迟到结果丢弃；已有attempt/unknown只查询不重发。
- 展示price/policy历史引用，明确不是当前运行权或业务已启用；预算草稿/审批/消费旧路径保留，共用request guard不复制状态机。

## RED和验证
- RED新增5 failed/原13 passed，exit1，/tmp/aos-gg-red.log。
- 最小实现18 passed，exit0，/tmp/aos-gg-focused.log。
- 扩展专项25 passed；初相邻命令两个文件名不匹配，实际只执行本面板，未把它当累计通过；随后核对真实路径重跑。
- 最终累计命令（repo根，使用本机bundled Node PATH）：
`pnpm --dir apps/web test src/pages/s2/BudgetCostReviewPanel.test.tsx src/pages/s2/BudgetActivationReviewPanel.test.tsx src/pages/s2/BudgetRevisionSetupPanel.test.tsx`
3文件/35 passed，exit0，/tmp/aos-gg-regression-final.log。覆盖正常精确提交、消费缺失/unknown/conflict、消费引用漂移、配置Receipt漂移、URL只查、响应丢失不重发、身份切换、checker/撤销/过期禁入。Vitest使用transport替身，仅合同/交互证据，不冒正式业务。
- `pnpm --dir apps/web exec tsc --noEmit`最终exit0，/tmp/aos-gg-tsc-final.log为空；精确git diff --check exit0。

## browser-pilot 实测
已读Kitewright Skill，用engine_adapter.BrowserPilot独立8097临时Chrome，当前8434由node PID59876监听。导航/aip/capacity，wait费用审核操作；SDK点击预算审批select→Escape→Tab3滚入费用select→select configure→Tab2聚焦确认。
- 页面tenant org-org/dev-project；无提议ID/合法来源，生成费用配置禁用。
- extract选择器 `[aria-label="费用风险审核与恢复"] button.btn-primary:disabled`返回matches1，文字“生成费用配置”。
- 截图w5cb4-bg00gg-browser-20261001.png为191584bytes，已view_image核看；相邻txt留提取证据。未填假账号/提议、未点业务提交；页面其他区域“未观测/缺少凭证”不当全部核心业务通过。
- pilot.close后session77366 exit0，8097 lsof无监听（exit1）。未手写CDP，未触碰共享浏览器。

## 未完成和下一波
真实库未连接/写入/迁移/重启，代码a0v128不代表当前库版本。Host/worker/Provider未启；商城源、旧12Run、手工Run、230L0未动。正式自然首链/八工作台/观察/发布未完成，Watchdog仍未部署，Goal未改。
下一BG00GH复习Model/Task预算风险联合路径，以GE真实派生引用替代孤立历史price夹具进入现有合法配置/准入链，先列现存缺口再最小实现与隔离联合证明；正式实例另波核身份、备份恢复、克隆全链与零执行窗口。

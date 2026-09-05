# R5-M03 媒体内部任务状态机设计验收

- source visual truth: `/Users/ddt/work/projects/ai_agent/docs/palantier/foundry/html/workshop-media-studio.html`
- implementation: `http://127.0.0.1:5173/workshop/media-studio`
- tenant: `org-org/dev-project`
- viewport: 1280 × 720 CSS px
- browser: Codex 内置浏览器

## 视觉与结构

- 视觉稿与实际页已在同一浏览器、同一视口组合比对；页头、经营摘要、三媒体页签、左侧任务流、中部生产中心、右侧建议/证据/交付区和底部批量操作结构一致。
- 页面使用真实栖月汇内部任务和正式 authority 空值，不复制视觉稿中的演示生产数量、素材、费用或发布结论。
- 完整八菜单和 AIP 侧栏可滚动、折叠与恢复；任务列表、表单和动作区没有被底部区域或浮层遮挡。

## 功能与数据

- 从页面创建“栖月汇微商城会员种草任务”，并对既有任务完成保存输入、补证据、改派、批量、样片、模板、排期、直播准备、暂停、继续和退回。
- 页面刷新后能回读两个任务；既有任务版本从 13 连续推进至 25，新任务为版本 1。
- 浏览器验收中发现并修复 `draftRef` 超集提交问题，修复后只提交精确四字段引用并在原页面成功保存。
- `dev-org/dev-project` 负租户返回 404 模块未安装；未调用 Provider，未扣费，未生成外部媒体，未发布，未 release。

final result: passed

# AOS 项目执行规则

## 开工门

1. 先读 `/Users/ddt/work/projects/ai_agent/docs/palantier/AOS项目开发上下文/01-当前项目状态.md` 与同目录的 `06-当前执行检查点.md`。
2. 在本仓运行 `scripts/memory/memory-status --json` 和 `scripts/memory/memory-validate --json`。
3. 任一强一致投影为 `STALE/AHEAD/DRIFTED/UNAVAILABLE/UNVERSIONED` 时，停止依赖记忆的状态变更；先按 authority 修复投影。
4. 项目事实只由 `docs/palantier/AOS项目开发上下文/memory/authority.json` 经 CAS 版本推进；投影不能反写 authority。

## 开发边界

- **最小开发、最小优化**，避免过度设计。
- **业务功能优先**，沿最短可用路径推进。
- **所有模块先查历史数据；没有就用明确标注的样例完成功能开发和自测，通过即可完成功能项，不再等真实数据。** 达人、视频、直播都适用。功能自测与真实业务验证分别记录，不把样例结果标为真实业务结果。
- **维护技术债台账**，按天记录延期事项。
- **凡不影响目标推进的任务，直接记技术债并跳过**，包括但不限于非功能需求、历史附加事项、辅助工具优化和形式性门禁；不因任务曾登记过而继续消耗时间，不反复加固辅助工具。跳过须记录范围与后续处理条件，不冒充已完成。
- **未经本人明确要求，不得自行暂停或停止长期 Goal**；单项受限只限制该项，继续推进已授权主线，不把非关键任务或工具问题当作整体停工理由。
- 真实业务租户只认 `org-org/dev-project`；`dev-org/dev-project` 仅用于隔离 canary。
- 当前 AIP 状态为 `PAUSED_BEFORE_E5` 时，不得绕过评审门进入 AIP-5 E5 编码。
- 先方案、后编码；最小更改；完成后执行针对性测试、方案一致性复核、浏览器验收（涉及页面时）。
- 任务开工登记 Task Receipt/Lease，交付写 Delivery Receipt；authority 更新后执行确定性 sync 与 Prime 回读。
- API Key、Token、Cookie、密码和客户敏感数据不得进入命令参数、环境、日志、提交、Receipt 或共享记忆。

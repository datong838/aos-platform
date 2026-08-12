# AOS 项目执行规则

## 开工门

1. 先读 `/Users/ddt/work/projects/ai_agent/docs/palantier/AOS项目开发上下文/01-当前项目状态.md` 与同目录的 `06-当前执行检查点.md`。
2. 在本仓运行 `scripts/memory/memory-status --json` 和 `scripts/memory/memory-validate --json`。
3. 任一强一致投影为 `STALE/AHEAD/DRIFTED/UNAVAILABLE/UNVERSIONED` 时，停止依赖记忆的状态变更；先按 authority 修复投影。
4. 项目事实只由 `docs/palantier/AOS项目开发上下文/memory/authority.json` 经 CAS 版本推进；投影不能反写 authority。

## 开发边界

- 真实业务租户只认 `org-org/dev-project`；`dev-org/dev-project` 仅用于隔离 canary。
- 当前 AIP 状态为 `PAUSED_BEFORE_E5` 时，不得绕过评审门进入 AIP-5 E5 编码。
- 先方案、后编码；最小更改；完成后执行针对性测试、方案一致性复核、浏览器验收（涉及页面时）。
- 任务开工登记 Task Receipt/Lease，交付写 Delivery Receipt；authority 更新后执行确定性 sync 与 Prime 回读。
- API Key、Token、Cookie、密码和客户敏感数据不得进入命令参数、环境、日志、提交、Receipt 或共享记忆。

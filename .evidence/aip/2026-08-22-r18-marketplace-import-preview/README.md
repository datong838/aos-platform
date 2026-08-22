# AIP R18-A 市场与导入治理交付证据

- 代码提交：`f9ce09a`
- 结论：`CODE_GREEN_OPERATIONAL_BLOCKED`
- 正向租户：`org-org/dev-project`
- 负向 canary：`dev-org/dev-project`

R18-A 已闭合真实市场目录、不可派发原因与修复入口、Agent/Capability 导入预检、确定性安全扫描、严格 SDK 与 OpenAPI 契约。页面不会把“可发现”表述为“可安装”，预检不会创建 ImportJob，也不会调用 Provider、外部市场或真实数据库写入。

## 验证

- 后端累计回归：29 passed
- Web 累计回归：201 files / 1984 tests passed
- Web build：GREEN
- OpenAPI：13 passed，重复导出确定性 GREEN
- 内置浏览器：市场、智能体列表、智能体导入、能力导入四页；最终干净会话主区域错误 0、console error 0
- 安全样例：受控输入返回 `external_required`；动态执行输入返回 `blocked`

## 后置边界

R18-B 的 ImportJob/Event/Artifact/Receipt 权威持久化必须取得唯一 migration Lease。当前 Data SourceReadiness Lease 虽已过期但未由 owner 合法释放，且 P02/P04 实时失败；本波不抢 Lease、不修改 Data 权威、不拼接旧 EvidencePack、不执行真实数据库写入。

# 固定生成绑定检查点

基线9c519f44，2026-09-11，m1串行、不push、230 L0挂起。

- 固定v1提示词绑定完整Decision正文（包括不确定性）、exact来源、明确计划budget及workflow taskType。重算Decision canonical hash，超16000字符拒绝而非截断。
- 复用原AipAgentRunExecutor._request_hash，按attempt捕获参数重建ExecuteAgentRunRequest；请求变化不接受旧答复。
- 仅SUCCEEDED且具备完成时间、Provider/Usage/Artifact引用时转换，核对原answer UTF-8 hash；草稿ID由tenant+attempt稳定生成，createdAt使用原完成时间。
- 草稿保存逐项exact EvidenceBundle与生成Artifact。模型无法填写预算/权限/审批字段。原人工审批会保留新增引用，仍声明externalEffectsAllowed=false。
- 新增10例先失败（尚无函数），实现后及追加配置/长度/审批回归共58 passed，exit0。既有7warnings及退出日志警告不变。
- 限制：纯函数，无DB读写、无Provider调用、没有公开入口。仅exact来源引用与Decision风险正文，尚不包含EvidenceBundle详情；不等于来源真实性核验或语义质量验收。未验证数据库保存/并发重放，未生成栖月汇真实计划。
- 下一波：受信数据库来源读取与当前head/marking/撤销校验，AgentRun D03输入/Artifact存储核验，现有Owner事务保存及隔离克隆重放；若来源详情纳入生成prompt须新协议/新attempt，旧答复不得重标。

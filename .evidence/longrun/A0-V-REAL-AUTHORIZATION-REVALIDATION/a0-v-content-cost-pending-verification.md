# 内容已完成与费用待核算的消费端验证

Task A0V-CONTENT-COST-PENDING-RECEIPT，基线 07b14348。

新增成功用例先失败于 COMPLETED 只能 SETTLED；修复允许 COMPLETED+COST_PENDING+actualFen=null，保留全部来源、Provider、Usage、Artifact、retry NONE 和一次调用的既有校验。数值零、缺结果、缺用量、缺产物、可重发指令和 UNKNOWN 均拒绝。

最终两测试文件 38 passed，7 warnings。包括隔离端口模拟回放只保留一次调用及相同可读 Artifact、旧 no-effect Host 合同。没有真实 Provider 调用，不能将 fixture 中的 provider_calls=1 当作远端执行事实。diff check 通过；既有 schema/deprecation warnings 与 JDBC 退出 logger 问题未处理。

仅更新 bundles/solutions 开发源码，未修改封存 candidates/releases，未更换安装 digest；真实环境不会自动获得本变更。下一步须完成短事务 enqueue、事务外 worker、持久化结果和原子 Artifact/Usage/费用状态承接，再形成新候选包升级验证。现有 HostCommitter 要求锁定事务内同步执行，禁止在该事务里等待媒体生成。这个约束已写进真实执行方案。

与产品目标对账：本步消除成功产物被未知金额阻断的合同缺口；完整生成、人工评审后自动续跑、真实首链、八工作台均尚未完成，不推进 A0-V authority。

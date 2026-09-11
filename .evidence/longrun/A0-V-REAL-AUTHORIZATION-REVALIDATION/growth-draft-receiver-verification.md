# 受信草稿接收检查点

2026-09-11，基线8f72134a。m1单写者，无push，230 L0挂起。

- 接收端显式connect_factory，tenant+attempt事务advisory lock；读取原SUCCEEDED attempt、同租户D03 AgentRun和已保存Artifact（type/hash/contentRef/run/source一致）。
- 新接收要求Run声明exact Decision/Insight/Decision Evidence输入，调用当前来源校验及固定请求转换，再由同连接既有GrowthPlan Owner最后保存/提交。无新公开route、无Provider调用。
- 同attempt回读原r1草稿，核对actor/decisionRef/budget/taskType/Artifact及保存正文hash，避免重复生成。原来源后来失效不导致已保存草稿被复制；回读不是新执行授权。
- Red：新模块不存在；Green：累计93 tests passed，exit0。包含显式开启的独有克隆数据库集成验证。
- 集成测试仅aos_upgrade_check_f1dc452abade，创建随机临时schema，真实Owner三张表LIKE现有表，Artifact用最小投影测试表；source/AgentRun/attempt模拟。两线程同时接收同结果+再次重放，唯一plan head/revision/receipt各1，可回读中文正文/来源，预算漂移拒绝。finally清理本次schema。没有向真实业务schema写fixture。
- 限制：尚未实库验完整真实来源/原Run/产物图；未接实际模型返回调用点或UI；真实栖月汇业务计划未生成。现有审批服务仍待当前来源重验。相同事务读只是时点校验，后续撤销必须由审批/执行继续验证。
- 下一波：完整隔离正向来源/Run/Artifact图验证与接收失败回滚；随后接真实生成调用点及答复持久恢复，源/安装/技能绑定就绪后才跑真实业务。保留无重复未知调用原则。

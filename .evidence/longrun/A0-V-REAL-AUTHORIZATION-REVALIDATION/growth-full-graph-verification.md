# 增长草稿完整数据库依赖图验证

2026-09-11，基线b32af219，m1串行、不push、230 L0挂起。

- 显式开关AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1，从固定独有克隆aos_upgrade_check_f1dc452abade建立随机一次性DB。真实表、FK、CHECK及触发器保留。合成前置记录仅在一次性DB，未调用Provider，未使用实际runtime业务图。
- Bundle通过现有ProductionContractStore建立；Decision/Insight经既有Owner保存。Receiver/来源读器/原AgentRun和attempt读器/Artifact读取/GrowthPlan Owner均使用真实数据库与实现，无mock。
- 第一次发现fixture成功attempt缺invoking_at，被DB CHECK正确拒绝；补fixture时间，未改变产品约束。
- 正向保存可回读中文正文、逐项来源和产物；重复接收不新增版本。
- 注入Owner最后commit前异常（代理仅故障注入，其余SQL真实执行），head/revision/receipt全数回滚为0，随后原请求可成功重试。
- 三个独立一次性DB验证底层Evidence经Owner撤销、超过配置时效、markings不足，首次接收均被拒绝且无plan head。
- 累计97 tests passed，exit0，7既有warnings及退出JDBC日志警告不变。之后只读确认a0v_growth_graph_test_%残留数据库数0。
- 限制：fixture前置采用直接SQL，并非通过真实安装/治理授权/Provider调用形成，故不能宣称真实业务链或技能运行已验收。当前API服务尚未重载本次代码，无真实计划生成。
- 下一波：实际模型答复的持久恢复与生成调用点接线；现有text Artifact仅保存hash/长度，接收前进程退出会丢正文，必须先解决可恢复产物。随后审批来源重验，再转实际source/安装/技能就绪与真实首链。

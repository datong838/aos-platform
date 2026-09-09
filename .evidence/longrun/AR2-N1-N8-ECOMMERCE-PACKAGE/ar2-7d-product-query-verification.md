# AR2-7D D1 固定商品比较QueryResult验证

- 基线58f39af8/AOS-000571；沿用m1 Task/Lease。新增固定ProductComparisonQueryService与测试，复用实际MetricDefinitionRevision、QueryJob及QueryResult Owner；无新表/迁移，无真实源调用。
- 稳定request包含完整观察Evidence及三个选择exact refs，窗口仅实际正时长读取区间；零时长拒绝，不补窗口。事务锁后重放先复验rows hash，再回读原结果，不重算当前规范库。首次保存三个字段计数行，99规范+1观察来源上限，partial/unknown及固定无评分声明；通用QueryJob SUCCEEDED仅指计算完成。
- read_exact回读固定Metric、原QueryOwner、原观察Evidence；校验定义/请求/列/分区/来源/固定confidence/时间政策。独立复核发现result_json.revision=true可被DTO归一为1，真实Red为DID NOT RAISE；增加原result_json/request_json规范摘要校验，未修改通用旧QueryResult哈希。
- 旧快照并发实测可收到23505/aip_analyst_query_job_pkey，测试仅接受该约束或40001；整个旧事务退出后新事务重放成功。服务不吞错误、不在原事务重试。fixture finally仅清自身Shop/Product，避免失败污染。
- 初9专项通过；原Query/Metric四文件回归20 passed/1 failed。失败为旧MetricStore自定义schema用法：全局public限定破坏其父租户关系。恢复通用Metric方法原行为，新固定服务仅以原_append_contract辅助方法指定固定public表写入并完整exact回读；不存在任意table输入。修复后新服务+Query宿主事务+旧MetricStore **24 passed, 7 warnings in 6.96s**。原API测试此前已通过，无API逻辑变化。
- 最后补空人口、零区间和同名临时Metric/Query表反例后，专项 **12 passed, 7 warnings in 4.53s**。包括外层回滚、不同actor/同key换观察冲突、rows漂移、两连接旧snapshot、新事务重放、canary、撤销、confidence/计数/原JSON篡改拒绝。
- 中断后复核测试落盘结果，闭包ar2-1扫描1701/分类87/迁移57，五类错误零，diff --check通过，memory-validate AOS-000571 GREEN。实现SHA256 f2fd13bb8d021df51e0b9cfac22483f6b26bc9a5a40e6012a755b6a7b28d71b0。
- 边界：所有PG在本次18434一次性库串行；不启动旧18432、不读真实源/Provider、不发布、不push，230 L0挂起。结果仅固定字段比较，不能据三个字段覆盖整个Product或全店Profile；后续仍需明确Requirement事实策略和DataFulfill，D2-D4/7E未完成。
- 最终独立只读复核确认通用Metric Store无差异、固定helper的表/列/定义/actor均不可由调用方控制，外层事务未提交；无剩余阻断。QueryStore SHA256 9811bc815b61ecc1c04dfcd8ec50d50f2104621cc6906df19fddd79541e6457d。本地审查不是外部Prime PASS。

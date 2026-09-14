# 完整组来源Evidence验证

### SC4-5l3 完整组来源Evidence验证

新增AnalysisSnapshotSourceEvidence，原字段上下文只抽私有_run支持原snapshot组合，公开参数不变。在原field/pending/current source与current projection守卫内构造完整Evidence，绑定原requirement、4策略、manifest、全部control draft引用与完整事件证明；source rows仍在原input，不复制raw客户行。原aip_evidence/w4撤销表、hash决定id、冲突不更新、精确列回读，2MB上限拒绝不截断。run_current按保存selection重入全部当前Owners并重建body，消费后再次查撤销。

Red模块不存在。首轮8项均在测试原AIP DDL缺twa_workspace依赖处setup失败；引入原TWA_SCHEMA_SQL的org/workspace两段后8 passed/23.81秒，生产表约束未改。增加当前base覆盖、写入后策略改变回滚及容量边界后，新10 PG+1纯容量+原field8 PG共19 passed/42.87秒（7warnings）。真实Store/Evidence/撤销/隔离/事务回滚，分析/pending为明确named doubles。892 entries只是序列化不截断与超2MB拒绝测试，未声称892行真实Owner组合验收；真实大组仍须后续主环境执行。source calls仍1，无主库/安装/源或模型动作。

AR2扫描1936/188/93五类错误为空；强投影CURRENT、memory-validate GREEN，authority AOS-000573。当前读取接口故意要求原pending任务仍有效；未来Fulfillment状态写入不得塞在这个只读consumer里，否则前后状态守卫会拒绝，应由原Fulfillment Owner负责其预期转换；历史产物展示与新执行授权须区分。

下一波SC4-5l4：使用原AipAnalystQueryStore固定查询存证，单完整来源Evidence作为source_ref，不截掉逐行来源。原requirement窗口/截止/到期，固定metric定义/列与12类计数，明确字段结构/引用覆盖边界，查询结果完整hash回读、稳定幂等与撤销/过期拒绝。先补精确方案；正式质量variant/population适用性与原Outbox/Fulfillment仍后续，真实首链/八工作台与持续观察未完成。

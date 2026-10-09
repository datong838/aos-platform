# 跨事务阶段核验与方案复审

基线 dc4c914d7 / AOS-001663。新原生只读核验 `cross-phase-native-result-r2-1663.json`：隔离 cluster 7694680278363095064 / aos_test_bcd5c43891be_ti4_test，SERIAL READ ONLY；当前 xid27900/pid79541，诊断事务独立回读 ABORTED。原 whole 准备 xid27485 为 ABORTED，原两父行0。原独立 Judge hold 的 xmin27487 已知 COMMITTED，不能满足新caller xid27900 的 fresh predicate；该 hold 的 ID/hash 与 whole 原父引用不同，不声称它是合法 durable v2 plan parent。manifest/result/certificate均0、target origin表未安装。

这是原生事务来源与代码阶段条件对账，不是已经调用未来 consumer 的 RED，也不声称 prepared guard 有产品 bug。原 fresh 校验器正确保护共同准备，未来 durable 消费须另入口与原 immutable provenance，禁止放松旧门或重新创建父行。当前 v2 签名纯逻辑已通过的285项不证明 trusted root/current epoch/真实 transport/Source终态/业务准入；本波不重复该纯测试。无前后端修改或业务调用，浏览器验收不适用。产品四文件哈希与旧 reader 恢复哈希保持不变，原证据末次检查未变化。

首轮只读查询与 ROLLBACK 均完成，结果输出时 UUID 不能直接 JSON 序列化而 exit1，保留 `cross-phase-native-result-1663.json` 部分文件（不是成功结果，不可当完整证据）。最小修复仅把原 UUID 精确 str 化、序列化先完成再 exclusive-create r2；Lease时钟改为 aware datetime 比较。r2 实际 exit0/0.26s，原 native SELECT、事务状态、row0、来源差异与 READ ONLY 断言全过。没有数据库重发写入或未知效果重放。

方案符合性：P0/P1及P3/P4来源身份与当前caller分开；预算只mint一次，原等待Intent不改、晚绑定追加；未知保持风险/actualoccupation，真实Usage与费用缺失不得释放；Source实际提交终态仍待协议，不能用 committed事务状态代替提交结束时间。两个已登记候选及依赖已落盘，下一文件级计划是原 v2 Target private producer/consumer 与可信根/current epoch、实际 transport receipt/committed joint provenance组合。共同终结器在token/费用/Source事实缺失时保持拒绝。完整Task/Goal不完成、不暂停、不blocked，无本波Delivery。

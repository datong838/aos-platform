# 普通容量池预留的调用者事务内核

基线 m1 d032a639 / AOS-001463，Task gt-capacity-pool-transaction-20261007。依据231/GT-b4完整组合事务要求。先计划后代码；只隔离PG，不改正式资源。

原普通 reserve 自开连接、成功插入后显式commit；replay直接返回，外层context退出负责原提交。Model Eval hold已用caller SERIAL事务。新方法 reserve_pool_in_transaction(conn,scope,resolution,run_id)只提供原池算法在caller内的调用，不授物理Source或Start，不用作sharedoccupation替代。必须原生psycopg.Connection、autocommit=false、实际aos_runtime/精确tenant/SERIALIZABLE/read-write；检查前验证scope/run/resolution。禁止代理连接或管理身份、错scope、非SER、readonly/autocommit。保持旧reserve输入检查在开连接之前；共享原算法，旧wrapper仍只对新写显式commit，旧replay和异常语义保持。算法以private内核返回reservation_id及是否发生写入；新方法不打开/关闭连接、不commit/rollback，不在失败后接管caller恢复。

精确运行文件 services/aos-api/aos_api/aip_model_capacity_reservation.py；新测试 services/aos-api/tests/aip/test_capacity_pool_transaction_pg.py；本证据目录。日志沿当前原同ownerpublication证据范围保存。先真实PG RED，后最小抽取，最后旧unit/concurrent101/Content调用者相邻。真实测试fixture仅手插旧池/READY，用作事务和拒绝门，不作经营正向。每例独立池ID；rollback/COMMIT用新observer连接证明；reader-first持有真实pool head锁，writer设置短lock_timeout并获得55P03后caller rollback可原生UPDATE再rollback。外层异常也要回滚reservation/event。数据全部保留，不删除DB/卷。

未来完整实现必须同caller Source当前性/用途审批、全域physicalAccount共享occupation、原Budget账本和一次Intent，不沿用本pool/revision计数当物理上界。旧unknown外部义务不能自动TTL清零；此代码不改变旧TTL或正式启用行为。Source issuer-only身份与runtime兼容合同、正式配置/安装、COMMITTTL独立pending。本Task仅事务内核，可以局部Delivery但不得收口父Source/sharedoccupation/业务Goal；本轮不修改AgentRun/Content运行接线，无页面变化，浏览器不适用。

最终验证：RED10FAILED6.49s，均因缺reserve_pool_in_transaction而失败；首轮24PASS/2XFAIL8.67s。补同caller幂等、新连接重入及10个native连接拒绝门后，专项+普通unit/101并发+原sharedRED+Content相邻65PASS/2XFAIL/7existingwarnings8.81s，无SKIP。两原shared xfail保持严格，未用局部内核消除或改成PASS。独立verify.py回读三保留隔离库，pool-txn仅真实callerCOMMIT的3预留/3events，回滚与异常无残留、canary0、Source0；原池算法AST除return增加写入标志/移除内核commit且SQL缩进归一外完全一致，其他原方法AST不变。新方法仅查询原生事务身份后复用内核，未调用连接工厂或结束caller事务；原wrapper新写仍commit，replay不新增显式commit。

收尾文档同步范围另登记gt-capacity-pool-transaction-docs-20261007：docs/palantier/20_tech/电商平台接入/231-工作台业务闭环长程开发路径与波次实施计划.md与微商城电商接入方案/D-waves/2026-10-01-W5CB4-BG00gt首次模型评测授权清单.md，仅追加本局部验证及完整后继，不能改原未完成项或历史证据。

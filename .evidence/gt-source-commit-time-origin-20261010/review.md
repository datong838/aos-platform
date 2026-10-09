# 提交时间戳候选复审

原隔离库 aos_test_2ac00c0e0559_ti4_test、cluster7694680278363095064 的真实Source保留行再次核hash/C签名/原来源/finalized，原xid22251 COMMITTED。当前track_commit_timestamp=off，原xid查询真实55000，在READ ONLY savepoint回滚后继续只读审计；没有更改参数、重启、重签发或新业务写入。

原已冻结 REL_16_14 源码 hash与先前boundary-audit一致。新增顺序核验：XactLogCommitRecord使用GetCurrentTransactionStopTimestamp→TransactionTreeSetCommitTsData写该时间→XLogFlush→CLOG提交树→SyncRepWaitForLSN。xactStopTimestamp源码定义为记录提交/中止WAL的时间，非持久化/客户端确认完成时间。复制origin存在时还可能记录origin时间，不接受跨来源时间直接作为本机终态证明。

结论COMMIT_TIMESTAMP_IS_NOT_ACTUAL_END：打开该参数也不能补上严格实际结束证明；本次没有打开参数或测量新的WAL慢写反例，不把源码结构当本实例该分支已延迟的证据。已有Source自身跨期提交反例仅核证据hash，绝不重放。

官方文档另确认：该参数只能在启动时设置、默认off；提交时间只覆盖启用后事务，并会经vacuum清理。文档为条件说明，实际结束结论依据上述原版本源码。来源：https://www.postgresql.org/docs/16/runtime-config-replication.html#GUC-TRACK-COMMIT-TIMESTAMP 与 https://www.postgresql.org/docs/16/functions-info.html#FUNCTIONS-COMMIT-TIMESTAMP。

方案/代码一致性：只有本Task审计脚本新增，SQL均SELECT/SHOW及read-only会话事务/savepoint，未改产品/配置或权限；原产品/晚提交证据hash不变。无浏览器适用，无Prime模型PASS声明。独立审计Task只交付此候选判定；原Source完整Task和完整Goal仍未验收。

下一已登记安全主线：原Source trusted-end继续完善非调用者可伪造的完成确认来源、未知终态与严格拒绝语义，不能填入本commit timestamp作为actual-end；Model可信token来源/独立Judge仍pending。若外部新协议或内核变更需要授权，不暗中采用。本Goal保持active，不扩局部RED为全面停工。

# 下一门：实际 Source COMMIT 截止边界只读调查

既有真实反例在原issuer同xid提交过期Source；不重放，资料为 gt-source-body-expiry-commit-native-20261009/independent-verification.json。当前require_pending_source_finalized只检查unfinished，未执行截止门；完整386项绿也不能覆盖反例。

PG16 SET CONSTRAINTS 文档说明可提前执行并耗尽pending constraint trigger；因此增加一条普通deferred日期检查仍需early SET/结束通道负矩阵。CREATE TRIGGER字母序仅针对同kind同event，不能代替整个事务所有事件队列尾部证明。

上游PG16 CommitTransaction在完整deferred-trigger与portal循环后调用XACT_EVENT_PRE_COMMIT，再执行parallel/ON COMMIT/pending sync/Notify/SERIAL处理，最后RecordTransactionCommit持久化；PrepareTransaction独立调用PRE_PREPARE。因此原生C事务callback是比单个SQLtrigger更靠后的候选决策点，但不等于WAL或客户端确认截止保证，且有PREPARE/parallel/subxact/回滚/多callback顺序/可信授权与绑定等新审计要求。现阶段只是候选，未授权安装，未实现，不能以它静默缩小实际COMMIT要求。

下一波必须保持真实反例，不替换Source/JWTTTL为长时限、不调整全局时钟，不声称延期function内final_checked_at等于实际提交完成。先冻结精确结束语义/可信安装与失败语义，结合真实原资料构造RED；相关必要锁与全部后续可等待步骤须纳入验收。保留正式发送独立门。

依据：
- https://www.postgresql.org/docs/16/sql-set-constraints.html
- https://www.postgresql.org/docs/16/sql-createtrigger.html
- https://raw.githubusercontent.com/postgres/postgres/REL_16_14/src/backend/access/transam/xact.c （2067 callback；2125 RecordTransactionCommit；2298 PRE_PREPARE）

本波只读调查不授业务权限；不得在全量运行时改业务输入或改实验室扩展。

已另核原生实验室对应PG16.14发布标签源码，相同阶段顺序；源码证据不是已加载binary callback安装证据。

# Source 原提交时间戳候选验收计划

Rules：231、原 Source 严格实际结束合同、m1 单写、先方案后实现；当前库只读、Host/worker/Provider关闭。原Model token来源已实证缺失，原Source可信结束协议已登记；本次选择Source提交时间戳候选，判定它是否可作为实际完成证明，不扩大TTL或把WAL记录时间偷换为完成时间。

精确新增文件仅本目录 plan.md、audit.py、task.json、audit-result.json、review.md及context-sync.json。独立同owner Task/Lease范围仅本证据目录；产品、内核、扩展安装及所有库配置不修改。原Source/main完整Task不Delivery。

输入：原已冻结 REL_16_14 xact.c及原boundary-audit SHA；当前desktop隔离lab精确container/cluster；原完整累计verification选定一个真实签名且COMMITTED Source库；原签名Source跨期已提交反例证据只读hash不重放。

实际调查：SERIALIZABLE READ ONLY核当前track_commit_timestamp、fsync、synchronous_commit、server version、原Source hash/C签名/来源/xid；在read-only savepoint下调用原xid的pg_xact_commit_timestamp，记录当前参数关闭时真实错误，不改配置。若参数已开则如实记录值，不把存在值宣称完成时间。核源码GetCurrentTransactionStopTimestamp→XactLogCommitRecord→TransactionTreeSetCommitTsData→XLogFlush→CLOG→SyncRepWaitForLSN顺序，确认记录时间先于持久化和确认。

退出条件：精确库、源码、原Source与原产品hash相符，记录native timestamp能力及源码语义，判定COMMIT_TIMESTAMP_IS_NOT_ACTUAL_END或反证；该判定只关闭提交时间戳候选，不关闭原实际结束协议，不宣称Source修复。所有SQL仅读/会话事务控制；不增加库/卷/服务，不重发旧未知结果。浏览器不适用。

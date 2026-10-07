# 普通池调用者事务内核验证

真实隔离PG：原登记RED为10FAILED/6.49s；最终专项与相邻65PASS/2XFAIL/7existingwarnings/8.81s，无SKIP。结果来自pool-caller-transaction-adjacent-r1.log，不把2个物理共享未实现xfail算通过。

新接口在actual SERIAL/read-write/aos_runtime/精确tenant的psycopg连接上执行原pool预留，不自开连接或提交。原生xid调用前后不变，新observer在callerCOMMIT前看不到；rollback/外层异常后reservation/event为0，明确COMMIT后各1。真实pool UPDATE lock_timeout=150ms得到55P03，caller回滚后UPDATE可成功再回滚。重入前后仍同xid，无重复event；新事务重入旧COMMIT预留也不结束事务。10拒绝门为非SER、错tenant、管理role、proxy、autocommit、connection readonly、SQL readonly、closed、idle、tuple rowfactory；均无新占用。原pool100容量下101并发最多100成功；Content原受控入口相邻保持通过。

独立verify.py绑定log/代码SHA，SER READ ONLY回读三个保留隔离库及固定container/cluster：3条callerCOMMIT新预留+3events，未提交/回滚不留行，dev-org0，signedSource0。原pool算法AST除caller归属所必需的写入flag/commit位置和SQL空白完全一致；其他旧方法AST不变。默认原入口调用方式、计数/TTL/错误与租户边界保留，不改变现有正式运行。

风险限制：该接口只是普通池事务内核，原READY/pool夹具不代表经营合法正向；pool/revision计数仍不能当物理容量。尚无独立Source occupation身份、全域共享账本、旧义务切换、submitted/unknown保留、预算+容量+一次Intent原子门。原actualCOMMITTTL和正式配置安装来源pending。原AgentRun/Content尚未切换本接口，不声称正式业务已修复共享缺口。无迁移/页面/正式库/服务/Provider变更，浏览器不适用。只收口本局部Task，父Source/sharedoccupation与长程Goal保持ACTIVE。

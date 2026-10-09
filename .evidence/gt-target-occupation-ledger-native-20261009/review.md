# Target 占用账本准备：方案与代码复审

仅修改 services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py，追加显式隔离安装工件；旧代码前缀逐字保持，不加入默认迁移。

本轮实现可信原 Target call 派生的不可变根记录和首事件。由数据库构造 hash、租户、原父额度、物理账户、token 上界及原调用 xid/pid；不接收客户端费用或计数参数。根仅 prepared_only、counts_as_inflight=false；首事件仅 seq=1、previous=NULL、prepared_only。精确重放校验内容、hash 和事务来源，写后重新核对原 Source/两项正式批准父额度/Suite/bucket facts。

两表 FORCE RLS、原 NOLOGIN Owner、runtime/PUBLIC 无直接表权限，独立 deferred 提交拒绝门；没有真实 admission、费用分配、状态转换、transport 或 finalizer。

原生 RED 85.56 秒：真实原 Target call 就绪，新接口缺失 42883。最小追加后 GREEN 95.76 秒：根/事件实际插入与精确重放；10 项直接 DML 42501；两张表各自独立门 23514；实际 inflight 前后为零；原 prepared debit 仍一条、10000 tokens，没有重复扣计。原完整 Source/Judge 节点回归通过。相邻 318 项通过，0.73 秒。

独立连接只读确认原事务 aborted，六张准备表为零，Source 一条，原 Owner 无 LOGIN/成员，临时 test_ledger 探针为零、新准备接口已移除，31 个原容器身份、启动时间、挂载和端口未变。正式库、原保留库和数据未修改。

风险与限制：首事件仅准备，不证明实际占用或首链；全局等待锁顺序、并发 admission、unknown 不按 TTL 释放、费用/Usage/独立释放和最终 COMMIT deadline 均待后续真实验证。原五个父 Task 保持进行中。未改变长期 Goal，也未补造任何权限。

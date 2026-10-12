# 受限权限部署原型验收

维护helper只接受未切角色aos_app、caller SERIALIZABLE/非autocommit、明确DB/cluster/schema161，核Run/event owner与ENABLE/FORCE RLS以及旧writer无Run列UPDATE。现有finisher须无LOGIN/继承/特权/member/parent/现存grant/对象所有权/role policy，命名policy冲突拒绝。所有验证在新授权之前；保存点建NOLOGIN角色，无会员授予，无LOGIN/密码或凭证创建。

Run仅SELECT/4列UPDATE，event仅SELECT/INSERT，四许可操作policy及两只TO finisher的RESTRICTIVE双tenant策略；旧角色ACL/列ACL/所有旧policy、owner/RLS标志与行计数原生前后守恒。表权限有限、成员0和事务rollback可读回。未知role grant/schema grant/policy、unsafe-role/member、资源/隔离级别/owner、旧writer UPDATE拒绝，未静默清理它们。

最终59专项/身份/私密连接/原子终结相邻PASS0skip、7既有warnings（10.10s），13项新原生bootstrap案例。新标准完整UUID clone，仅本轮原型角色，外部真库不接写；测试后新库/角色清理。此前8pass、57/58累计用于增量历史，最终以59为本次证据。初始RED仅新模块缺失，不宣称真实部署失败。

此为显式维护部署原型，不是Alembic升级、真实权限安装或生产者授予。真实资源仍需独立零执行/一致双备份/完整恢复/Owner审批门与部署合同；此helper没有自动入口。RLS限制策略的本次验证是原生目录和旧权限守恒，不以空表目录检查宣称完整经营隔离场景。finisher有限SQL角色仍需可信来源与所有签名/预算/Scope准入；未启动Host/worker/Provider或实际Target/Judge，不push、未改真库或八台入口。原Goal/完整恢复保持未完成。

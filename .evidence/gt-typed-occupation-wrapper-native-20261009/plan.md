# 原SQL占用准备的同连接严格包装

复习231、AOS-001617与typed-occupation-wrapper-plan。候选①原SQL严格包装已有atomic授权及可信root/event合同；候选②实际准入/Judge结果链依独立风险与真实结果。选①。

唯一产品修改 services/aos-api/aos_api/aip_physical_capacity_occupation.py，追加prepare_target_occupation，原前缀保留。参数真实psycopg原SCRAM conn、正向scope、原消费command和严格UUID plan/intent/call。先检查原caller事务/连接/role/UTC/tenant/xid/pid，再复用原消费当前Source与原packet编码，调用原窄SQL，解析已有DTO并与原connection、plan/Intent/call和Source physical account逐项核对；再读现场identity。绝不commit/rollback/retry/DDL/dispatch或向日志打印凭证。

先真实原Source/两正式批准/四腿plan/Target Intent/call/root准备链中包装缺失RED。最小实现后新独立库正向原DTO重放、错误scope/conn/command/UUID/plan/Intent/call引用负向、实际callerCOMMIT拒绝、独立六表零/Source1/xid aborted/原31资源保留。不重复旧10DML/constraint矩阵耗原Judge50秒，不延长期限。相邻349保留并复验产品变化。无运行路由/默认迁移，不启actual admission/费用/unknown/Judge结果/transport/finalizer。浏览器不适用未接运行入口工件。

GREEN R1实际包装正向/重放/10负向均通过，完整原生66.49秒后段原Judge current approval期限失败；独立xid aborted/六表0/Source1/探针0/原31资源未变。R2仅移除已封存1610完整计划重复4负测/ACL/即时提交门，保持包装10负测与原完整manifest回归，原50秒期限和产品不变。

# S08 原批准事件生产模块 SQL 投影

基线ca798369/AOS-001383；publication及formal-boundary两个已有Task串行，唯一m1写者，lease20:00/16:00有效，方案先更新。仅production publication_store.py、formal-boundary PG测试及两Task证据目录。

CAPACITY_APPROVAL_EVENT_PROJECTION_SQL窄命名参数读原public.aip_action_approval_event，精确双租户/事件、UTC、positive scope、原version>=1、nullable hash形状及finite/UTC Python年份1..9999门，投影原13字段含null、固定actor user和UTC整秒/六位微秒，原canonical函数与SHA256输出。返回快照，不证明原批准合法/当前/未撤回，不授容量；后继完整guard必须要求恰一行、expectedref相同及完整原identity/Owner/唯一事件/提案/撤回/期限/Provider/Evidence锁，不回退旧缓存。

原生READ ONLY日期实验已证±infinity→to_char NULL、BC1→AD1同字串、year10000超Python；查询拒全部非法域。9 RED均缺SQL常量；首轮9专项通过16.22s。新增四微秒边界和NULL expiry/三nullable hash/slot/空reason原模型精确字节/hash，沿临时原表型、pg_temp/pg_catalog search_path，隔离事务rollback。完整正规Source及allocation批准fixtures+private SCRAM/RLS核两精确refs和dev-org/缺event/时区漂移零行。TEMP负例只证明计算域，不能作为正式批准或权限证据。

独立route_supervisor要求固定builtin schema；已显式pg_catalog函数/C collation，原表/canonical/digest固定public；其只读复审确认修订及四例设计，无新增重大问题，最终累计日志当时未终结故未替代验收。之后同一进程终结：formal-boundary+publication+Source/auth共360 passed、7既有警告、98.98s。git diff --check通过，无页面/服务接口变更，浏览器不适用这项纯SQL投影，不能以此宣称业务首链。

不新增迁移/SQL函数/角色/grant，不改当前权威库/服务，不开放完整Source入口。隔离fixture保留其正式测试审批来源，不重用历史Run。本Task无完整Delivery，Goal/Task ACTIVE；S11完整request JSON及原动态事实仍后续，COMMIT时钟/晚提交归属裁决pending，不自行放宽。

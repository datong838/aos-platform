# 三新增Skill日志表历史默认ACL最小修复

唯一m1写者，AOS-001950，已登记qyh-skill-journal-acl-repair-20261012 Task/Lease；来自真实最新副本native-acl-red，而非假设问题。用户持续栖月汇恢复授权及231原最小权限合同，不重新要求审批。

文件：新增services/aos-api/alembic/versions/a0v_161_skill_dispatch_acl.py（down_revision160），新增services/aos-api/tests/aip/test_signed_skill_dispatch_default_acl_pg.py，证据本目录。原160/旧表/全局defaultACL/业务代码保持，不迁移真实159或开启业务。

RED：真实source aos_app/public默认aos_runtime arwd；原160新intent/dispatch/observation三表继承默认INSERT/UPDATE/DELETE，GRANT SELECT不撤回既有权限。已有FORCE RLS可保留另一保护层，但不能代替SQL最小权限。新增测试必须实际构造同原defaultACL并通过原160产生过宽native ACL，再对原161修复检查，不能用空默认新库作唯一正向。

候选修复仅对三新增日志表清除runtime和PUBLIC的额外表权限，显式还原runtime SELECT；不改变writer原SELECT/INSERT、仅intent.version列UPDATE、不授Run UPDATE。先确认source/public额外role/列权与预期role集合，未知授予须拒绝或另登记，不能静默清除非目标身份。保留NOLOGIN/NOINHERIT/SUPER/bypass拒绝、FORCE RLS/原policy/trigger不变；新迁移不可破坏性降级。

专项：三表所有runtime非SELECT权限拒绝、PUBLIC无权限、writer权保持及双scope强制策略保持；结构与数据/owner/policy/trigger逐项保留。native负门含直接INSERT/UPDATE/DELETE/列权/跨租户，测试数据仅独立实验数据库、事务回滚或明确fixture生命周期，不回放真实Run。相邻运行原journal/atomic writer/readonly reconcile/causal dispatch相关原native测试，核默认授权和旧表ACL没有被变更。继而在ACTIVE fresh160 owned clone迁移161再对照最新647数据、12序列与授权delta，直到完整native门收口再Delivery。

风险：历史PUBLIC或第三role/列级grant会导致单纯runtime REVOKE仍保留有效权，需实际权限检查；必须不借扩大writer或删除RLS让测试通过。正式签名包schema兼容、连续零执行真库迁移窗、OIDC/独立publisher/安装配置/八页及自然首链继续独立pending。

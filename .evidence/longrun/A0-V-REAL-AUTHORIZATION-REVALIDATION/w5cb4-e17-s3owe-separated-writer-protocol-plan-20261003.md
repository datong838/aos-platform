# W5CB4 E17-s3o-w-e｜Plan 与内容共享 Receipt 的隔离发行协议

日期：2026-10-03。依据 231-3/4/5/9、栖月汇执行方案、s3o-w-d RED。原 `aos_runtime` 对 Plan head 及共享 Receipt 的写权会导致配置准入失败；但 `content_draft.register` 是合法共享 Receipt 写者，故不能整表撤权后仍使用同一运行登录。

## 文件级施工与退出

1. 仅新增 `services/aos-api/tests/extension_runtime/test_plan_receipt_writer_protocol_pg.py` 的独立 PG 临时 schema 协议验证。沿用真实 `w2_001/w2_002` 表形状；创建 Plan 与 Content 两个互不继承的非 owner 测试登录，runtime 对 Plan 与 Receipt 只读，Plan 登录仅持 Plan head/revision 和本表 Receipt 必要写权，Content 登录只持共享 Receipt 必要写权。测试中代行 `SET SESSION AUTHORIZATION`，实际 `session_user/current_user` 都须是各自登录，租户 GUC 精确。
2. 数据库层 Plan head 全 `INSERT/UPDATE/DELETE`、Plan revision INSERT、共享 Receipt INSERT 以触发器按真实 session identity、operation、TenantScope 防伪。Plan 写者与只读 runtime 共用 `(org,project,planId)` 事务 advisory 锁；读者普通 SELECT 不要求 UPDATE 权。验证 runtime 直写、两 issuer 相互冒用、跨租户、内容正向、同键并发等待与提交后新版本。
3. 此波仅证明隔离 SQL 协议，不把 test-only 登录、临时 trigger 或测试内容 Receipt 当当前正式签发。原 generic/BI/successor Store 的连接工厂和完整前置依赖仍需下一波接入；当前业务库不迁、不切、不启 Host。正式 migration 必须在新全备、ACL-faithful 克隆全链及零执行窗口后另波发行。

验收：专项和 s3o-w-d RED/原只读锁相邻回归不退化；角色对称误用与 trigger 缺口不得以代码注释代替断言。方案/代码复审与 verification 记录每条实测 SQL、退出码和残留限制。

本次执行完成步骤1及步骤2的隔离 SQL 协议证明；没有运行原 generic/BI/successor Store 的完整前置依赖与事务，也没有覆盖共享 Receipt 其它 operation。正式发行合同仍在步骤3所列独立波，不能以探针 GREEN 代替当前配置正向。

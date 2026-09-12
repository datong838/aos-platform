# 登记回执不可变存储验收

2026-09-13，基线d7574e54。施工范围为a0v_026_dispatch_registration_receipt.py与test_dispatch_registration_receipt_pg.py；主库未迁移。

- RED：六项隔离PG用例因迁移文件不存在失败。
- GREEN：基础六项通过；补充重算hash后的错租户/安装/组/schema/receipt身份拒绝及真实runtime写入拒绝后，11 passed（4.93s），7项既有警告。
- 测试使用18432独立随机数据库，复用description fixture的真实canonical JSON函数和pgcrypto。runtime binding仅有被引用键的最小结构；不把此测试当作完整安装或真实路由登记验收。
- 验证内容摘要匹配、列与payload身份一致、tenant/idempotency和tenant/group唯一、RLS跨租户不可见；runtime四类写权限均不存在，真实INSERT/UPDATE/DELETE/TRUNCATE均InsufficientPrivilege；Owner的常规UPDATE/DELETE/TRUNCATE也被历史触发器拒绝。
- Alembic唯一head=a0v_026；git diff --check通过。没有增加可执行SECURITY DEFINER函数，也没有创建路由或授予路由写权限。仅新增回执表的runtime SELECT。

自审与方案一致：此表是后续原子登记事务的持久化基础，不是接受任意payload的产品API。九操作完整性、当前权限和配置复核、并发组登记、写入函数、撤销/卸载、exact切换均尚未完成。新增schema未进入主库，API进程不重启，原安装/源数据不变；未来迁移部署前还需针对性权限评审与实际Owner整链验证。downgrade明确拒绝破坏历史。

下一波：实现受限的完整九项默认fenced登记入口，让当前权限检查、路由创建与本回执在同一事务内完成；验证普通runtime不可直写、幂等重放、已有部分组拒绝、双写者竞争原子性及撤销路径。不能借用恢复库宽ACL登记。

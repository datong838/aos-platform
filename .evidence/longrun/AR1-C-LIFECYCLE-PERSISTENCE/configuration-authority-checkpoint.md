# AR1-c 不可变配置版本检查点

2026-09-06；基线80479217/AOS-000531；主生命周期Lease有效。

新增ar1_002从属配置版本表：租户/安装/代次FK、不可变版本与前hash、完整配置摘要、请求摘要/幂等键/actor/DB时间；FORCE RLS、运行角色仅SELECT/INSERT、UPDATE/DELETE/TRUNCATE拒绝。ConfigurationDocument只存有界role/data/budget/policy精确引用，拒绝同源多版本歧义、超Bigint、额外字段和实例绕过。append/read每次通过宿主严格同步的当前权限/引用reader；重放先于新CAS但不免当前权限；Installation→binding锁串行保护版本链。配置hash含scope/安装/代次/ID/revision/previous/actor/document；只暂存，不改变binding.config_ref、epoch或enabled。

测试只在专用18432临时schema应用ar1_002；引用reader使用显式test_configuration_refs/actors测试权威，不是正式业务权威接线，不创建真实预算。初次缺迁移Red21 setup errors→21passed/8.93s；DTO歧义/上限Red4，Prime发现测试reader漏authority后反证Red4，均修复。最终三个配置文件67passed/11.62s；最后累计595passed/6既有warnings/97.50s/exit0，含真实隔离OCI及PG。静态Alembic唯一head ar1_002，无数据库升级命令；git diff --check通过。独立Prime最终只读审查无新增实质问题，未替代测试运行。

无共享迁移、真实业务写、Provider、费用或发布；无页面改动、在线后端重载或新增页面验收结论。新增业务场景0，AR1-c整波IN_PROGRESS；下一段真实引用适配及配置生效（先fence/排空），启用和持久派发仍独立完成。

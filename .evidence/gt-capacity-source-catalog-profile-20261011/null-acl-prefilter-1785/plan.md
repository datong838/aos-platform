# 列ACL空值前置过滤等价优化

Rules231、原完整Source与联合准入§3/§11.3；原catalog Task同Owner唯一scope续期，未交付。候选一当前实测original_fact_boundary反复耗时，候选二完整native结束/Root仍依赖正式来源。选一，以减少单次扫描成本保留所有调用及等锁后验证。

精确产品文件：services/aos-api/aos_api/aip_provider_capacity_catalog_audit_profile.py；测试services/aos-api/tests/aip/test_provider_capacity_catalog_audit_profile_pg.py；证据本目录。先只读A/B同原库比较列权限查询结果与EXPLAIN成本，固定old/new/new/old四次，不更改旧库。若无实际扫描改善不盲改。

假设：现有COLUMN_AFTER的EXISTS(aclexplode(a.attacl))在NULL输入必无行，显式外层a.attacl IS NOT NULL与原谓词等价，但让规划器先筛列ACL。仅此两处predicate编译结果改变；原已发布SQL/迁移、所有角色/默认ACL/表权限/列权限/RLS/trigger/currentness检查以及完整调用次数不变，保留VOLATILE，禁止缓存、跳过检查或延长TTL。完整fixed private/public/occupation摘要自然随同编译，不自动安装。

RED旧查询实际扫描成本；新增真实PG列ACL矩阵包含NULL、owner/PUBLIC SELECT/UPDATE/INSERT/REFERENCES、grant option与撤销，比较原优化谓词和新谓词结果；完整native身份/partial hybrid/ACL拒绝与事务回滚、旧生成器hash和相邻测试；然后新鲜原Source完整路径验证期限成本。未完成完整COMMIT仍无Delivery。

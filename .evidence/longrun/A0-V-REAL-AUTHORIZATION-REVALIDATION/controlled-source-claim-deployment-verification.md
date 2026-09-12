# a0v_024 实际部署与连续性验证

2026-09-12，脚本提交 b6ebf045，独立迁移Lease A0V-CONTROLLED-SOURCE-CLAIM-LOCAL-MIGRATION-20260912。

部署脚本5项拒绝性测试通过。固定colima-aos-extension/aos-a0v-recovery-pg；备份4,895,547字节，sha256:3a5f24199d6627ec2d3f90fe712975062d5bd1e9498712c3098f706561a68d58，0600保留在恢复目录，不入Git。

15:51:04Z克隆 aos_source_claim_20260912_ti4_test 完整恢复并正常Alembic 023→024；11张关键业务/批准历史表行数与摘要相同。迁移hash sha256:13907e0e5467b8dcb7cfaa097414f182b8921ade46446dd77893c09f2023fc52。新表空、RLS强制、runtime仅SELECT/INSERT、不可变UPDATE/DELETE/TRUNCATE触发器、两个validated外键引用检查通过。

15:52:12Z重新核对克隆、备份、hash、独占Lease、主库023与备份数据基线后，在advisory lock下主库 aos_meta_head 正常升级024。没有stamp、覆盖或删除业务数据。升级后11表行数/摘要一致；新表仍空，ACL/RLS/触发器检查通过。批准写入0、源读取0、业务写入0。

15:52:49Z真实连续性：实例afd792de-e85e-4680-86d0-c83404824fb3运行5480秒，88次续租，3容器running，binding ready/enabled，canary安装0。5173/ontology、8434/、18181/v1/health均HTTP200。API进程仍旧代码基线，本迁移并未热加载新执行器；后续正式入口装配及受控API重启仍需完成。

下一波：检查批准过期后的原任务恢复协议与正式调度入口装配，不换run绕过未知源结果；随后创建exact批准并执行真实P01首链。领域包真实经营闭环与八工作台验收仍未完成。

# a0v_024 主库受控部署方案

2026-09-12，d1653e4c。迁移本身已提交 d7eb3cf8，隔离 schema 完整性及默认 ACL 收口已有验证，本轮完整持久层链路通过。正式部署仍先备份恢复。独立任务 A0V-CONTROLLED-SOURCE-CLAIM-LOCAL-MIGRATION-20260912 已获得 m1 Lease，范围为新脚本、主库 exact a0v_024 和新隔离克隆；不包含源读取/业务派发。

新增 scripts/a0v_controlled_source_claim_deploy.py，沿用既有 pipeline control 部署脚本的固定环境、受保护备份、隔离恢复、迁移 hash 和 advisory lock。主库只能 aos_meta_head，Docker 只能 colima-aos-extension/aos-a0v-recovery-pg，克隆只能 aos_source_claim_20260912_ti4_test。新备份目录 state/controlled-source-claim-deployment，既有路径一律不覆盖。

prepare：主库必须 a0v_023，完整 pg_dump 带 owner/ACL，0600保留；克隆撤销PUBLIC CONNECT、无服务/调度接入；恢复后关键业务表与批准历史表行数/摘要必须一致；克隆仅升级 a0v_023→a0v_024。新表必须空、强制RLS、双不可变触发器、runtime仅SELECT/INSERT；验证FK引用既有exact历史，不引入业务写入。

apply：重新核对 Lease/m1、迁移hash、备份hash、克隆验证及主库当前版本；持有独占数据库advisory lock并限制锁等待/语句时间。只运行Alembic正常upgrade，不stamp、不删库、不替换行。部署后关键表行数/摘要相等、版本024、新表ACL/触发器通过，保存落盘证据。失败保留备份/克隆/诊断，不自动重建或破坏性降级。

脚本策略专项测试目录 services/aos-api/tests/test_a0v_controlled_source_claim_deploy.py：固定目标、版本与迁移范围、未知action/旧证据拒绝、Lease失效拒绝。真实克隆演练验证完整DDL和数据保留。主库升级本身不会启动P01或创建批准，后续正式入口/批准续期恢复另波次。

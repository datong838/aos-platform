# 审批历史备份与隔离恢复验证

2026-09-12，基线1612d558。固定colima-aos-extension/aos-a0v-recovery-pg；未使用其他Docker上下文。

完整pg_dump（含ACL/owner）保存于受保护目录，4,833,085字节，SHA256 9987cfa90679ebc5441b662fa11433faa28116ae10c4b525fa8478aad652477d。备份不入Git。新建aos_pipeline_control_20260912_ti4_test并撤销PUBLIC CONNECT；没有启动API、Host、调度或源连接。恢复a0v_021后9张关键表与主库快照的行数/摘要一致。

初次真实克隆执行Alembic a0v_021→022→023成功，但权限检查发现旧default privileges额外授予UPDATE/DELETE。保留失败证据pipeline-control-restore-drill.json、备份和克隆。两项模拟旧default privileges的独立PG测试均RED；两份尚未在主库部署的迁移补REVOKE ALL FROM PUBLIC,aos_runtime后仅GRANT SELECT,INSERT。相关34项通过。

10:52:21Z在同一保留克隆上只重跑两迁移的权限收口函数，未删除重建或覆盖业务行；重验9表行数/摘要与主库一致，新两表为空、强制RLS、不可变触发器齐全，aos_runtime无UPDATE/DELETE/TRUNCATE/TRIGGER/REFERENCES。证据pipeline-control-restore-drill-repaired.json。此为修复后验证，非声称首次无失败。

下一动作：持有独占任务及数据库advisory lock，主库严格a0v_021、备份hash/两迁移hash不变时，Alembic升级到a0v_023；不stamp、不触碰其他业务表。完成后再验证数据基线、空历史表和Host连续性。当前提交时主库仍未迁移，P01未启用，不push，230 L0挂起。

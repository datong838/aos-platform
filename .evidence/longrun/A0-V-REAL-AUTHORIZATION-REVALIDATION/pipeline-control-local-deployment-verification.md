# 本地审批存储部署完成

2026-09-12，基线64b0b6e0。10:53:46Z在独占本地恢复库aos_meta_head持有migration advisory lock，校验两Lease、备份hash、两迁移hash、克隆a0v_023和当前主库a0v_021后，调用Alembic command.upgrade至a0v_023。没有stamp或删除/重建现有表。

结果LOCAL_PIPELINE_CONTROL_SCHEMA_DEPLOYED；两张新表为空，强制RLS和不可变触发器存在，运行身份只SELECT/INSERT。9张关键表迁移前后计数/摘要一致；approvalsWritten/sourceRowsRead/businessWrites均0。详见pipeline-control-local-deployment.json。

10:54:06Z独立只读运行观察：3容器running，当前binding ready/enabled/unfenced，306次续租，elapsed18634.124秒，canary安装0。fencedConfigurationProven=false，故不把此连续性观察冒充专门配置围栏实验。5173/ontology、8434/、18181/v1/health均200。AR2 ar2-7 1797/158/93五类错误空。

备份、原失败克隆、修复验证均保留；没有改旧Docker.raw或恢复文件。新服务代码尚未通过API进程重启加载，也未公开运行入口；P01仍禁用，真实经营首链未完成。下一波正式运行入口、当前控制消费与ScheduleRun/Ingress统一接线；实际批准/执行需重新检查当前时窗。不push，230 L0挂起。

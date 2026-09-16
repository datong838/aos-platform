# Y6a 完整源组迁移克隆演练

2026-09-16，基线84db3600。Rules：方案先行、m1唯一迁移者、不push、保留原数据；只允许隔离克隆升级，主库仍061。

新增 scripts/a0v_snapshot_schedule_clone.py 和 services/aos-api/tests/test_snapshot_schedule_clone.py。复用原 installed-bootstrap-action_deploy/storage 的凭据内存连接、exported snapshot备份、exact Alembic chain事务升级与hash工具，不运行旧已消费apply/prepare。profile覆盖当前专用lease/state/clone、SOURCE061/TARGET066、五迁移精确顺序；脚本无主库apply入口，升级函数外包固定clone核验，无法误传主库。

备份来自主库 REPEATABLE READ READ ONLY 同一 exported snapshot；所有public旧表行数/行摘要和pg_dump共享该快照。备份600、目录700；clone aos_snapshot_schedule_20260916_test 源于template0，撤销PUBLIC CONNECT，不改主库连接。不覆盖已有备份/克隆/intent，遇到残留先读回诊断。

恢复后旧表逐表摘要相等；仅clone 061→062→063→064→065→066，同事务验证旧表不变和7张新表空。新表全部ENABLE+FORCE RLS；runtime SELECT/INSERT允许，UPDATE仅definition_head允许、DELETE仅current_member允许，TRUNCATE全部禁止；核immutable触发器/完整性约束和066恢复专用围栏存在。部署器及迁移文件hash绑定私有proof。

新增表：pipeline_snapshot_schedule_claim/member，pipeline_snapshot_schedule_definition_revision/member/head，pipeline_snapshot_schedule_current_member，pipeline_snapshot_group_recovery_receipt。这里只排除这些新增空表，不排除任何旧业务表。测试先验证profile固定clone拒绝main、源目标/链/文件hash配置及验证合同，再实做克隆。输出同目录 y6a-clone-migration-verification.json（只含摘要/权限/版本，不含客户明细）；private dump和完整proof保留于 .aos-recovery-20260916/state/snapshot-schedule-clone。

失败回滚clone迁移事务并保留克隆/备份用于检查，不删旧证据、不升级主库。下一波Y6b主库受控升级前必须读回该proof和备份hash，重新核对当前源版本/单写lease，另立方案；Y5d审批窗口和组定义、真实执行仍在后续。

## 验收结果

克隆已实际从061升级066；同导出快照恢复前后以及迁移事务前后544张旧public表摘要完全一致。七新增表为空，RLS/权限/延迟完整性触发器与恢复专用围栏通过；独立连接再次核验版本、全部旧表、schema、备份和执行文件hash。主库仍061，无主库迁移，无源调用。私有备份及prepare.json保留，公开结果y6a-clone-migration-verification.json。

新增目标保护与hash绑定2项 passed / 3.58s；原RecoveryReceipt/恢复专用围栏/定义生命周期真实隔离PG累计36 passed / 150.35s（/tmp/aos-y6a-contracts.log）。每套隔离库串行执行，无跨测试并发迁移。memory强一致投影均CURRENT，整体GREEN_WITH_WARNINGS（异步投影提示），不作为业务完成证据。

下一波Y6b主库升级方案已登记sc4-5l6y6b-main-migration-plan.md；部署拓扑新发现同文登记：原独立Host目前没有snapshot worker，而Y4绑定main生命周期，真实启用前需单Host切换方案，不能把新worker孤立启动或新增第二Host。Y5d和真实经营链继续保留。

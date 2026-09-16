# Y3c-4 原十二停止失败Run恢复

## 实施验证（2026-09-16）

已实现；原RED allfailed被原路由拒绝（1 failed，12.00s），首项原子恢复14.96s通过。14项恢复/运行负例组合118.78s通过，另错group锁或policy不重领1项10.69s、原普通Completion混合终态和锁竞争2项10.70s通过。日志`/tmp/aos-failed-group-red.log`、`/tmp/aos-failed-group-final.log`、`/tmp/aos-failed-group-targets.log`、`/tmp/aos-failed-group-ordinary.log`；diff检查通过。

真正经原Completion入口持同组session锁，原claim_failed_run在同一外事务生成十二原recovery claim并将原十二Run转running，Store步骤用明确停止seam拦住。第十二条失败使全组回滚；外COMMIT确认丢失后新实例只观察原allrunning，无新claim；同审批第二次失败拒绝；未停止/无finished/混合及普通实例拒绝。新组ID或另一policy不能借原固定Authority重领。夹具源仍一次，Store零写入。

本波只是运行状态恢复，不把停止seam视为完整Store通过。C5方案已列，接真实隔离failed→Store→完成→重放。主库未迁移、主服务未加载，不push、230L0挂起。

目标不是创建替代Run，而是正式恢复已证明停止且有完整原input的原十二Run。

计划改pipeline_snapshot_group_completion.py、pipeline_snapshot_group_recovery_runtime.py；新增tests/extension_runtime/test_snapshot_group_failed_recovery_pg.py，并调整C3c运行负例为未确认停止的失败（正式全停止失败将成为允许分支）。不得改变普通Completion实例的失败拒绝行为。

固定恢复实例才可识别全failed且executor_stopped=true、finished_at非空；全running/全succeeded仍沿原分支，混合与unknown一律拒绝。preflight只识别不改状态；真正重领必须在原Completion.complete的同组session advisory锁内、当前安装/恢复Authority包围的一次元数据库事务中。

复用ec_ingress_claim.claim_failed_run，给它只yield同一个已授权conn的内部contextmanager，使原函数自己的transaction成为同一外事务的savepoint，而非十二独立COMMIT。每个ControlledIngressJournal固定当前controlRef和原runId，saved_recovery=True；原parentHash/previousRun/原恢复claim表不新造平行台账。claimId=namespace UUIDv5(scope/group/RecoveryRef/run)确定值。十二成员按稳定顺序重领，之后必须全部running；每个原claim函数仍检查停止/finished/原parent与schedule。回调前后当前Authority全验，不调用Store。

同一个RecoveryRef的failed claim已经使用过、Run后来再次失败时，原claim重放不重新置running，整体明确拒绝并要求新的正式续期回执；不根据猜测生成新claimId。若唯一一次外COMMIT确认丢失，读回原十二Run全running即可由同一固定ref继续，零新Run/SourceClaim，不重发源。

原Completion的session锁覆盖元数据库重领及后续Store/最终十二Run完成，避免先重领释放锁后另一个执行器介入。任何第N个成员失败或权限变化使整组回滚，不能留下部分running。

PG验收：十二停止失败→十二原Run running/十二原recovery claim，无源重读；第十二个失败全回滚；相同ref已消费后再次失败不重领；未停止/finished缺失/混合拒绝；普通实例不放行；模拟外COMMIT确认丢失后新连接读回原状态。C5随后完整failed→原Store/Link/Projection/完成重放，才考虑产品执行API与worker。

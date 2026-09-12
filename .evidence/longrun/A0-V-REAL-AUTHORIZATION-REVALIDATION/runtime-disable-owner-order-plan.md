# 停用提交与进程资源释放顺序修复

2026-09-13 04:13。真实停用操作 e578ff09-b0ba-4de8-979e-ee4f7e13d6a3 仍 accepted@1；旧 Host v15 已因 RuntimeRevisionConflict 退出，三个当前容器实际不存在，旧绑定@5/epoch4 enabled=false、fenced=true、desired=enabled、observed=unknown。这是故障，不是停用完成。原命令不重发、原事件不覆盖。

根因：RuntimeHost._consume 对 disable 先 lifecycle.revoke→PreparedJob.stop→ResourceJournal.record_cleanup，清理把绑定@4变@5；之后 RuntimeDisableExecutor.begin_disable 仍要求请求中的@4，必然拒绝。原真实 OCI 测试直接调用 executor 后再 job.stop，未经过 Host 顺序；主机单测只验证了错误顺序。

修复路径：先由既有 disable consumer 完成正式 fence→GenerationDrainReader→disabled_committed；仅当前操作 succeeded 后才撤销进程 Owner。未知/失败/未完成结果不得先释放资源。提交的 resourcesRetained=true 对应提交时事实，后续资源清理保留独立证据。保留赋权变化检查和串行执行。清理失败必须报告异常，但不能抹掉已提交停用。

修改文件：services/aos-api/aos_api/extension_runtime/runtime_host.py；services/aos-api/tests/extension_runtime/test_runtime_host.py；services/aos-api/tests/extension_runtime/test_ecommerce_growth_signed_lifecycle_pg.py。先将实际签名 OCI 场景接入 Host._consume + 实际 disable consumer + 实际 job.stop，复现版本冲突；再改顺序并验证正路径、未完成不清理、后清理失败保留已完成停用。

当前已损坏的 accepted 请求需单独正式恢复协议：不得放宽原 binding CAS、改写原请求、直接 UPDATE 成功或强制启用。该修复仅阻止同一缺陷再次发生，现有操作恢复另立证据后执行。旧数据/Receipt/源配置保留，230L0挂起，无push。

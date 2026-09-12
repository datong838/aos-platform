# 已受理停用目标失效的失败终结

2026-09-13，基线c6ebd051。原停用请求e578ff09冻结binding@4，实际资源清理已将同代推进@5，原请求不能成功。禁止改变其target/hash/事件，禁止放宽fence CAS，禁止把失败改为成功。

技术方案：RuntimeDisableExecutor在accepted阶段、原Owner事务及当前权限/安装etag/operation版本锁检查下，读取原不可变target并锁对应binding。如果当前binding版本严格大于原target，将原operation终结为failed，failure_code=DISABLE_TARGET_STALE，追加记录原/当前版本、同generation与installationId的事件。仅写operation和事件，不改binding、源数据、安装、权限或资源。相同版本走既有begin/finish；缺失、倒退、错租户、错权限、非accepted或hash损坏拒绝。已失败由consumer读取终态并ACK，不能重复终结。

修改文件：services/aos-api/aos_api/extension_runtime/disable_commit.py、disable_executor.py；新增tests/extension_runtime/test_disable_stale_settlement_pg.py。隔离18432真实事务验证失败事件与绑定未改、tenant/permission/CAS/hash/rollback等反例；原Host/OCI停用流程回归。

真实恢复先使用既有consumer处理原operation，确认failed并保留原target@4，然后以新action/key和冻结binding@5请求保守停用，确认真实drain与disabled_committed。这是明确失败后的新命令，不是未知结果重发，不复用原key。随后才能启动新版、prepare/verify/configure/enable。旧Host当前已退出，无需再次杀进程。对外不发布、不push，230L0挂起。

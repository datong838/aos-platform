# 实际执行器投影完成门验证

2026-09-11，基线548fefad，A0V-PROJECTION-DRAIN-20260911。

project_pending改为同事务真实scope未投影计数，包含其他工作器暂时锁住的记录。新增project_until_caught_up按既有事务批量推进，批前/后检查monotonic deadline与取消；无可租用行时短等待。实际ec_live_executor调用新入口，成功返回才发布Dataset。取消/期限在事务之间合作检查，不能中断正在执行的SQL事务；精确语句超时后续完善。

验证：新增6测试先失败，实现后模拟+实际executor阶段顺序12通过；隔离PG新增1组合后13通过。PG验证limit=1处理后pending=1、另一连接锁住剩余行时projected=0/pending=1、解锁续批后pending=0、dev-org canary未投影；真实SQL写入隔离obj_instance2条。隔离最小表/RLS，无生产Owner触发器证明，不是public或真实源实测。diff-check通过。

范围与风险：scope清空观察不等于exact批逐对象证明；并发其他写入可能造成保守超时。API未重载，新代码仅已接入执行路径。当前Dataset仅存元数据/历史行数，无raw行保存，之前“恢复Dataset需完整raw列”推断撤回；待幂等记录及阶段对账。恢复初始保存/claim、实际真实首链与八工作台仍未完成。不push，230 L0挂起。

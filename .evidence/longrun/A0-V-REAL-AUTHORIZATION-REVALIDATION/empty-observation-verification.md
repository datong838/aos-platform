# 空源观察持久恢复验证

2026-09-11，基线02adc71d，A0V-EMPTY-OBSERVATION-20260911。

新增empty_observation_v1原Journal包络，command=null/outputRows=[]，仍绑定run/source配置/图。正常BatchCommand协议保持；共用不可变INSERT/hash/RLS。空观察保存空派生清单，不调用Store，不推进checkpoint或删除对象，不消费无关投影；finalizer以原有事务生成0行Build及不可变结果。actual executor仅源读取与转换均为空时选此路径，有源行但转换空仍拒绝。返回empty_observation区别本次空观察；不证明源全量为空或所有业务无变化。

验证：新合同与恢复测试修改前2失败3通过；最终30 SQLite/Mock专项通过，隔离PG Journal/Dataset组合4通过。PG证明跨连接保存/重放、同run替换非空命令拒绝、空派生/零行结果恢复及canary隔离；用Mock Store断言零调用，非真实源或全PG调度证明。所有parent.command消费点检查分支，原非空恢复专项保持通过，git diff --check通过。既有Pydantic警告及pytest退出JDBC日志closed-file问题未在此修复。

限制：记录的是一次0行观察；不对远端删除作推断。Dataset处理行数沿既有本批语义，产品真实界面尚未验收。public未迁移、API未重载；失败run claim、关联输入来源版本、真实数据首链与八工作台仍未完成。不push，230 L0挂起。

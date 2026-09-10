# 实际调度原批次路径接线验证

2026-09-11，基线455e8b91，A0V-SCHEDULED-INGRESS-WIRING-20260911。

持久claim后的QYH调度显式durable_ingress，Engine仅该模式向executor传标记；实际ec_live_executor选择新路径。首次运行锁run、读取持久图并与实际节点/写模式核对，核验当前run/schedule/source，versioned源读ref核对，共享原transform，保存规范原输入/命令并提交后才进入基础/派生恢复、投影与Dataset finalizer。已保存run跳过源与transform。旧非调度路径保持原选路。新增合作取消/期限检查（无法中断已执行中的SQL/网络）。

发现聚合旧缺口并修复：统一Store scope GUC，消除字符串拼接workspace错误参数；只读目标tenant/niushop/site1非删除订单，缺Store或读取异常固定失败，不伪造0订单。辅助源版本仍未形成完整来源证明。

验证：新增durable3用例先失败；最终六文件39通过，覆盖首次保存提交顺序、已保存跳过源、源ref/图漂移、取消、actual executor选路、Engine参数传递、QYH调度、原阶段顺序/恢复及SQLite聚合隔离/失败。Journal/连接/source/投影/finalizer在durable编排测试中为mock；不能作为真实PG整链或SSH证据。diff-check通过；既有告警保留。

限制：public尚未应用a0v002-007，API未重载，cron原恢复禁用状态未改变。空批次暂明确INGRESS_EMPTY_BATCH_UNSUPPORTED；ignored基础项仍须对账（不能把重复/过旧/悬挂一概当完整成功）；失败run重新claim、全PG接线及真实源SSH未完成。完整真实经营首链与八工作台未完成。不push，230 L0挂起。

下一步：无变更/ignored的安全对账和原run恢复claim、全PG端到端验证，再恢复真实源运行。

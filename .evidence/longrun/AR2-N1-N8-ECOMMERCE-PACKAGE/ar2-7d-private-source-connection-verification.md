# AR2-7D D1 配置观察独占连接验证

- 施工基线 4b6d2e5f；m1 串行、最小修改、不 push，230 L0 挂起。实现及范围见同名 plan。
- configured observed 显式 reuse_cache=False，新建连接和隧道，不访问、写入或驱逐全局缓存；旧入口默认缓存行为保持。配置 expected ref 仍在 Runtime 构造前核验。SSH 密码模式转发使用实际 remote_host。
- 清理逐资源尝试，失败资源保留引用且 pending 禁读；进程 terminate/wait 超时后 kill/wait，确认回收后清空。Runtime 在 open 前持有隧道；原始 KeyboardInterrupt/SystemExit 不被普通清理异常替换。新路径日志用固定代码。
- 第一轮 74 passed；本地只读复核发现清理中断及进程回收问题，3 条反例真实失败，修复后 79 passed；二次补齐构建期所有权和中断优先级。最新 HEAD `11a22ce1` 上最终 **84 passed, 7 warnings in 3.52s**，日志 `/tmp/ar2-private-source-latest-head.log`。五文件：test_jdbc_private_source_connection.py、test_jdbc_connector_runtime.py、test_configured_source_observation.py、test_ec_source_observation.py、test_ec_source_adapter_jdbc_ssh.py。
- 本地只读终审无剩余阻断；不代表外部 Prime PASS。实现 SHA256：jdbc_connector_runtime.py d1c1a1c0ab00c6e3db4fd3f8b61436a741bc6271b4022bebb844ce5760355830；ec_source_adapter.py 37618da67c597c35cbaee779bf54a7908a3e031e8bc6594e74d43d10c813b8a3。
- 验证期间曾发现另一执行器写入 m1，按串行规则暂停；用户确认其已停止。对其 Router 生成清单缺口以独立提交 `11a22ce1` 对账后，本会话恢复独占。
- `diff --check` 通过。`verify_closure.py --phase ar2-1`：扫描1707、分类91、迁移57，五类错误均为空；`memory-validate` 为 `AOS-000571 / GREEN`，未推进权威。
- 全程 JDBC/SSH 替身；配置Owner测试仅自有18434一次性PG。未连接真实源、未调用Provider、未发布。此切片不证明服务器身份、Secret版本或同一源快照，相关unknown标志不变；D1/DataFulfill及AR2-7D整波仍未完成。

# 精确配置源探针验证

基线df340754。新增source_connection_probe与POST /v1/sources/{source_id}/test；输入只有UUID expectedConfigurationRevision，scope来自principal。FOR SHARE锁住当前源行，检查version/type/status，再以校验后的存储配置开启private runtime；只读发现配置库表，结束资源后返回版本/延时/tables/truncated。连接异常固定503，不含异常原文；不自动重试。通用Jdbc层原有日志未整体审计，不能宣称整个传输链无敏感日志。

执行test_source_connection_probe.py、test_configured_table_discovery.py、test_source_registration_persistence.py共17 passed；git diff --check通过。6探针场景覆盖成功/缺源/旧版本/停用/异type/传输异常，前四类拒绝无连接，连接结束且DB上下文结束。使用模拟DB/runtime，不是PG锁或实际SSH/MySQL验证；本轮未取得红阶段。

方案一致：不接受客户端任意SQL或原始连接参数，不读取业务行，不共享缓存，不改变source状态/执行接入；probe结果不是新鲜度或履约证明。FOR SHARE期间配置更新会等待，既有网络timeout尚需真实运行观测。完整history/PG锁行为、HTTP权限、前端向导均需继续验收。旧7警告/JDBC退出问题仍在，未重载API、未push，230 L0挂起，完整首链仍未运行。

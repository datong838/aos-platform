# 费用待核算 SQL 迁移验证

基线 80d6323b。新增 a0v_002（down_revision=a0v_001），扩展状态 CHECK 和 guard，保留原不可变身份、revision、hash 与时间检查。

在命名恢复容器的随机 schema 中执行真实 PostgreSQL DDL，全部事务回滚。固化 test_a0v_cost_pending_schema.py，显式 AOS_A0V_SCHEMA_TEST=1 执行 1 passed，包含多个断言：submitted→cost_pending→settled 合法；重复用量、pending 重发/释放、更换用量或身份非法；存在 pending 时拒绝 downgrade，settled 后可 downgrade。非法转换同时使用合法递增 revision/hash，避免仅因版本不变产生假阳性。

没有升级 public schema、没有迁移原数据、无 Provider 调用。只验证数据库 guard，不验证 Store 或业务续跑。SQL 与 Python cost_pending 形状一致，后续必须实现 Store 同事务记录完成回执、用量和 pending 状态。既有测试警告与 JDBC 退出日志问题未处理。

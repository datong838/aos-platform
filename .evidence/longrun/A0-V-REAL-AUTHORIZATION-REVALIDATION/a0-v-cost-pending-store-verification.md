# 待核算完成路径实现与验证边界

基线 2737300f。新增 complete_cost_pending，锁原 reservation，检查 price 开发授权和提交 Provider，逐项验证 UsageReceipt，记录 completed Provider Receipt、cost_pending Reservation、completed Invocation。同内容重放只读，不同用量冲突。无金额参数，不写 settled 金额或释放预算桶。

Store 替身编排与状态合同 11 passed。首次失败是测试误传带 sha256 前缀的结果 hash，按既有 _digest 的 64 位原始摘要合同修正后通过。覆盖 submitted/unknown、pending 重放/漂移、held/released/settled 拒绝、授权失败无写入。没有验证真实 Store SQL、并发、回滚、授权读取函数内部或完整租户隔离，下一切片补 PostgreSQL 集成。

仍未开放 active 未核价记录和实际业务入口，商业预算行为不变。Provider model 与价格引用匹配由既有 Host exact Model/Price 绑定检查负责；本 Store 不发起模型调用。后续须证明该 Host 与本方法实际相连，不能仅凭方法存在宣称首链运行。既有警告和 JDBC 退出日志问题未处理。

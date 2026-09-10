# 费用待核算状态合同验证

基线 0134f72a。新增 cost_pending 区分业务结果已知但金额未核算，与 unknown（执行结果未知）分离。必须有请求/结果 Receipt 和非空唯一 UsageReceipt，actualMinor=null。

新增测试先红于状态不支持，实施后预算状态合同与开发授权合同 27 passed。覆盖零金额伪结算、缺请求/结果、空或重复用量拒绝；现有状态测试继续通过。无 DB mutation、迁移或 Provider 调用。现有 SQL 不支持新状态，Store 也未开放转换，故此结果只证明合同层，不能称运行闭环完成。

下一施工为 SQL/Store 一致性：持久化 cost_pending，回读执行完成且费用未结清，后核价只结账不重新调用。保留既有警告和 JDBC 测试退出日志问题，不 push。

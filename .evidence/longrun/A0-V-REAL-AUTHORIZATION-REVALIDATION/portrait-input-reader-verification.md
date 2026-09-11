# D01统一输入读取验证

2026-09-11，基线9040e237，AOS-000573。

当前D01运行声明完整Method/Metric/Eval/QueryResult/Bundle清单后，同conn复用Owner权威和L3查询材料读取，统一截止/总大小/唯一指标，重复Bundle正文冲突拒绝，返回固定portrait_prompt可用输入。没有Provider派发、额外授权或业务ready声明。

新增12项纯组合测试；与画像生成、方法、权威metadata、Query/L3读取器回归合计104个不同测试通过（103+新增冲突1），包含既有一次性PG Owner验证。git diff --check通过。框架7警告/退出JDBC日志错误沿用，退出码0。

边界：真实质量与对账不能由这组引用替代；真实源未恢复，首链未跑通。无主库写入、迁移或push。下一波原始成功产物接收、幂等Insight保存、历史读回与治理执行。

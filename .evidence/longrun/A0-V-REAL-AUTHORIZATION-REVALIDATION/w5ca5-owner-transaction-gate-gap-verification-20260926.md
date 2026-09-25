# W5ca5｜Owner 门缺口审计验证

1. 复习 231、230 L0、W5c5g/W5c7t/W5ca4。
2. 文件级只读方案先提交 `m1@c815b702`。
3. 静态审 `a0v_091`、服务和旧 W3/W4 prepare/apply，区分 DB 内角色锁与外部全机授权。
4. 复核 W5c4x/y/z、W5c6i 隔离测试已有范围；未运行 PG 测试，不触真实库写事务。
5. 本波无新代码专项；历史隔离测试/ W5c9y 29 passed 不能冒充原组正式关闭验收。
6. 明确现有 SERIALIZABLE/actor membership/Receipt+Run 同事务已存在，缺的是全机 Fleet/Host fence/旧入口禁启与历史独立 row proof；不提出伪修复。
7. 8080 业务浏览器离线，18181 本地文档服务不构成业务验收。
8. audit/verification/D-waves/AOS CAS/Prime 收口，原十二 Run/attempt 不变。
9. 下一步需可信外部 Fleet 控制面与历史行证明或正式不接受结果退休决策；这些输入到位后才可规划真正 Host-fenced Owner 关闭。当前不自动进入有副作用波次。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。

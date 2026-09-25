# W5c9e｜18181 租约自停守卫验证收口

1. 复习 W5c9a/d、租约治理、AOS-000692 与当前 PID/PG。
2. 方案先提交 `m1@40235b40`。
3. PID26881 唯一 18181、精确租约有效、唯一 PG、8080/job 缺席，前检通过。
4. 最小新增专用 wrapper 守卫，不修改旧调用方/worker/DB。
5. RED 7 failed→隔离负例与 serve 接线；相关累计 30 passed、7 既有 warning，py_compile 通过。
6. 精确 SIGTERM 旧 PID，18181 释放；单次新 PID28077 启动，18181 唯一本机监听、四零执行旗标、sourceCalls/runsCreated=0、`/docs` 200；PG/8080 边界不变。
7. 真正租约到期现场自停未发生，不能称 live expiry GREEN；8080 业务浏览器仍离线。方案/代码边界一致。
8. audit/verification/code 精确提交，D-waves/AOS CAS/Prime 更新。
9. 自动 W5c9f：在不借本机诊断授权 closure 的前提下，复审外部 Fleet/Owner 证据来源与可实现的离线负例/安全债；任何缺口仍 no-authority。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 run_definition、m1 单写不 push、不读商城源。

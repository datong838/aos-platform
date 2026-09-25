# W5c9d｜重启安全无授权诊断验证收口

1. 复习 231/231-9、W5c7t、W5c9b/c、AOS-000691；全机权威来源缺失。
2. 方案先提交 `m1@fa8405ac`。
3. 唯一 PG、18181 受控进程、8080/job 缺席及原十二 Run 边界新鲜前检。
4. 新增只读诊断，避开旧独立 worker PID 门但固定三授权旗标 false；不改 effect 路径。
5. RED 6 ERROR（脚本缺失）→专项 6/6，相关累计 21 passed、7 既有 warning；py_compile 通过。
6. 真实阈值过线后输出 `ELIGIBLE_NO_AUTHORITY`，known local Host=0、原 Run=12，`topologyComplete=false`、`closureAuthorized=false`。时间/本机安静均不等于全机/Owner 权威。
7. 8080 业务浏览器离线；18181 `/docs` 非业务验收；方案/代码一致。
8. audit/verification/code 精确提交，D-waves/AOS CAS/Prime 更新。
9. 自动 W5c9e：优先补 18181 租约到期后进程仍可能运行的安全债（当前 lease 至 2026-09-27 04:00 CST）；方案先行、隔离测试自停与旧调用兼容，绝不借此真实关闭原组。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 run_definition、m1 单写不 push、不读商城源。

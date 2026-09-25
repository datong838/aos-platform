# W5c9a｜纯 HTTP 18181 零执行验证收口

1. 复习 AT/AS、W5c8z 与 AOS-000688，旧租约到期先 STOP。
2. 方案 `m1@f09b2c3e` 先提交，私有路径发现后补充 `m1@3eeda20c` 才增 wrapper。
3. 正式新建精确 m1/18181 租约；旧任务不续、不复活。唯一 PG/8080 job/端口新鲜前检通过。
4. 最小代码：固定新 task 白名单、精确 scope 校验、独立当前私有路径 wrapper；原 Product/default 行为不变。
5. RED 2 个预期失败→专项累计 15 passed、7 既有 warning，py_compile 通过；纯 HTTP preflight 四旗标零执行、sourceCalls/runsCreated=0。
6. 单次 serve PID26881、唯一 127.0.0.1:18181 listener；运行进程 preflight 四旗标零执行，8080/job 仍缺席，Docker 仍唯一 PG。
7. `/docs` 200；`/openapi.json` 首次 5 秒超时，不能填全 HTTP/业务浏览器 GREEN。未进行业务 UI 验收，8080 仍离线；方案/代码一致。
8. audit/verification 与代码精确提交，D-waves/AOS CAS/Prime 更新。
9. 自动 W5c9b：先方案，只读原 authority/definition、12 Run/Receipt、执行主体读回；未知状态冻结，不启动自然 worker、不重发或手工 run_definition。OpenAPI 慢端点单列非业务性能债。

230 L0 挂起、dev-org 零 canary、m1 单写不 push、不读商城源。18181 进程租约到 2026-09-27 04:00 CST；届时必须停止或重新正式授权，不得让过期进程继续视为有效授权。

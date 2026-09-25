# W5c8n｜有界历史组只读报告验证

## 判定

本波**隔离 PG 单组分页/跨事务游标拒绝 GREEN，多组第二页未验证**。方案 `m1@807ce6c2` 先行；没有真实扫描、sidecar SELECT/INSERT、Writer、Worker、ACK 或原 attempt 重发。真实库未迁 a0v_096/097，真实 profile 停止。

## 第 1/9—9/9 步

1. 复习 W5c8m 分类、`a0v_045/097` 原组主键与 created_at、m1/AOS-000675/专用 PG；真实 Run 当前状态仍未知。
2. 文件级方案 `807ce6c2` 先提交，限定单只读事务、每页 1–12 与额外 1 键、无自动全量循环。
3. 新测试先因模块缺失 RED（collection `ModuleNotFoundError`）。
4. 新页 API 先核精确 `aos_runtime`/租户/`REPEATABLE READ READ ONLY`，以 `(created_at,group_id)` keyset 只读原 claim，最多取 `page_size+1`，逐组在同一连接调用 W5c8m 分类。返回状态计数/处理数与仅供同一事务继续的 typed cursor，不返回 JSON/源行或授权。游标绑定租户、snapshot、事务时间和 backend PID；不暴露 sidecar。
5. 原保存组 PG 单页、错误租户/可写连接/页界/伪造及真实跨事务旧游标拒绝：`1 passed, 7 warnings in 129.26s`。W5c8i–m 相关短累计 `32 passed, 3 deselected, 7 warnings in 10.54s`；`py_compile`、`git diff --check` 通过，disposable `aos_test_*` 数据库数 0。
6. 本波无 UI 改动；真实目录此前不可用，IAB localhost 被客户端阻断，未取得业务页浏览器验收，**不判真实 UI GREEN**。未读商城源、未点业务动作。
7. 复审：单组 fixture 只证明第一页与游标拒绝；**真实 PG 多组/第二页/并发插入尚无覆盖**，不能声称全量报告或稳定跨页生产扫描。cursor 是事务内连续性标记，不是认证令牌；READY_CANDIDATE 不是回填/ACK 权限。真实历史未扫，sidecar 仍空且不可由 runtime 写。
8. verification 与代码 m1 提交；再更新 D-waves、AOS CAS/Prime 回读。`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false` 不变。
9. 自动进入 W5c8o：先构造隔离 PG 多组与并发变更负例，证明第二页/租户边界和短事务时限；受控 backfill writer/真实扫描另立门，仍不建 ACK。

230 L0 挂起、商城源不读、dev-org 仅零 canary、unknown 不重发/不手工 `run_definition`；m1 单写不 push、不动其他分支。

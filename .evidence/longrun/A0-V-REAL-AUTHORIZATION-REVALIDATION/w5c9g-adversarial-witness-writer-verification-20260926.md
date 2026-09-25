# W5c9g｜恶意自洽输入写门验证收口

1. 复习 231、W5c8q/r、W5c9f 与 AOS-000694。
2. 方案先提交 `m1@d210bb40`。
3. 静态确认 a0v_098/sidecar 无应用运行时读取点，隔离 DB/专用 operator 身份限定。
4. 一次性 PG：错误租户拒绝；精确 operator 对错误 row 语义但合法原输入返回 `INSERTED`，sidecar 仅原 canonical 字节与 hash。
5. 首轮 admin tuple 回读错误，修测试后专项 1 passed、7 warning；相关无 PG 30 passed，测试 DB/临时角色残留 0。
6. 方案/代码复审：canonical-only，不证明业务行语义、ACK/closure/真实回填；生产函数/迁移/授权均未改。
7. 8080 业务浏览器离线，不把 18181 `/docs` 当业务验收。
8. audit/verification/test 精确提交，D-waves/AOS CAS/Prime 更新。
9. 自动 W5c9h：先方案设计独立 row semantic proof 与消费侧拒绝门；无独立源证据时保持 NO_AUTHORITY，不读商城源或触发 ACK。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 run_definition、m1 单写不 push、不读商城源。

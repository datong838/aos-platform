# W5c8z｜唯一恢复 PG 容器验证收口

1. 复习 AT/AS、W5c8x/y 与 AOS-000687，原 attempt/商城源 no-effect 边界保留。
2. 方案先提交 `m1@4e1fa83c`。
3. 目标容器 image/restart/本机端口、另外两容器/8080 job/端口新鲜前检成立。
4. 唯一 `docker start aos-a0v-recovery-pg` 成功，未启动其它容器/服务。
5. 即时专项：`docker ps` 仅目标 Up、18435 仅 loopback、8080/18181 free、8080 job 缺席、`pg_isready` accepting；不查询数据库业务数据。
6. 无代码改动，本波不把历史 13/82 tests 冒充新运行时 GREEN。
7. 8080 API 离线，业务浏览器不能验收；方案/运行边界一致。
8. audit/verification 精确提交，D-waves/AOS CAS/Prime 更新。
9. 自动 W5c9a：先方案复核 18181 受控启动器和 DB/migration/Host 旗标，单次纯 HTTP 启动后读回 Cron=false、snapshot worker=false、第二 Host=0；偏差冻结并停止安全可辨的 HTTP 进程。再下一门才可能只读原 Run/Receipt。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 run_definition、m1 单写不 push、不读商城源。

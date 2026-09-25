# W5c8z｜唯一恢复 PG 容器受控启动与零执行回读

## 上位边界

承接 W5c8x/y `m1@ce8cf684`/`dd6613b0` 和 AOS-000687。真实 VM Running、Docker running 0，旧 8080 launchd job bootout，宿主活动 actor 无直接 PG/worker 配置证据；仍无法排除间接行为。旧 8080 plist Host/snapshot/Cron/migration 不安全，禁止 bootstrap。原 12 Run/Receipt 未知，禁止重发或手工 run_definition。PG 自身启动可能执行 WAL 恢复，是数据库服务正常效果，**不视为业务 Worker 授权**。

## 文件级及唯一状态变更

- 只新增 plan、audit、verification；不改生产代码/配置/其它分支。不读商城源或数据库业务表。
- 新鲜前检 `colima list` 真实 profile Running；明确 `docker --context colima-aos-extension ps` 为空；`docker inspect` 白名单核对目标精确名称 `aos-a0v-recovery-pg`、镜像 `postgres:16-alpine`、restart=`no`、绑定端口仅预期 `127.0.0.1:18435->5432`，另两个 PG exited；8080/18181/18435 free；8080 launchd job 缺席。偏差 STOP。
- 唯一变更：`docker --context colima-aos-extension start aos-a0v-recovery-pg` **一次**。命令响应未知不得重发，先只读 `ps`/`inspect` 对账。
- 即时只读回读：运行容器必须只有目标，另外两个 PG 仍 exited；目标端口只在 127.0.0.1:18435，8080/18181 free，8080 job 仍缺席。仅用 `pg_isready`/健康状态，不查业务表、原 Run 或商城源。若出现额外容器/worker、8080 listener/job、端口越界或未知启动结果，STOP 冻结，不自动停止未知 actor；如目标单独启动失败且无其他运行者，记录并研究，不盲目重启。
- 本波不启动 18181；下一波先计划纯 HTTP 零执行启动和运行态 flag 读回，再触及真库只读 Run 证据。无真实迁移、回填、ACK。

## 九步

1. 复习 AT/AS、W5c8x/y、产品/技术 no-effect 边界。
2. 本方案先提交。
3. 新鲜唯一容器/端口/launchd 只读前检。
4. 单次目标 PG start；未知只读对账。
5. 专项容器/端口/`pg_isready` 回读；无代码测试不冒充。
6. 累计回归核对 W5c8y 13 tests 与既有 PG 82 tests 的历史范围。
7. 8080 离线，业务浏览器不可验收；方案/运行态一致性复审。
8. audit/verification、m1、D-waves/AOS CAS/Prime。
9. 自动下一波：若只一 PG 且无 actor，计划纯 HTTP 18181 零执行 profile；否则冻结查因。

230 L0 挂起、dev-org 仅零 canary、m1 单写不 push。

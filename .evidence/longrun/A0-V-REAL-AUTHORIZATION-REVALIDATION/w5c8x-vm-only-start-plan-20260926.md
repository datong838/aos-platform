# W5c8x｜真实 profile 仅 VM 启动与即时运行态读回

## 上位方案与已证边界

承接 W5c8v/w `m1@b001b5c8`/`ed407a11` 与 AOS-000685。三个现存 PG Docker 容器 restart=no；停止 VM 的 OS 离线审计未见自定义 PG/AOS worker 的 systemd/cron/cloud-init 启动命令，但标准 Docker/guestagent 和宿主其它 AOS job 存在。8080 launchd 已精确 bootout；原 8080 plist 的 Host/snapshot/Cron/迁移旗标仍不安全，绝不 bootstrap。原 12 Run/Receipt 状态未知，任何未知结果不重发、不手工 run_definition。

## 文件级清单与单次操作

- 只新增本 plan、运行态 audit 与 verification；不改生产代码、配置、数据库或其他分支。
- 新鲜只读前检：确认 m1/HEAD、真实 `aos-extension` stopped、测试 VM 仍独立；8080/18181 无监听；`com.aos.a0v-api-8080` launchd job 缺席；无残留只读 loop/mount；`colima` profile 名称唯一。若任一不符，STOP，不执行启动。
- 唯一状态变更：`colima start -p aos-extension` 一次。不同时启动任何容器，也不使用默认 Docker context。若命令超时/未知，先只读 `colima list` 和明确 context 读回，不重发 start。
- 立即用 `docker --context colima-aos-extension ps` 仅输出容器 ID/名称/状态/端口，不输出 Env、Mount、Logs；核对 8080/18181、launchd 8080 job、`colima list`。预期三个原 PG 容器均未 running 且无其它业务容器 running；若出现任何意外运行，冻结，不做数据库/Run/商城源读写。若 Docker daemon 尚未 ready，只读有界等待，不能自动 docker start。
- 如 VM 运行且 `docker ps` 为空、端口仍 free，本波只证明 VM-only 安全起点；下一波单独计划 PG-only/纯 HTTP 零执行的读回门。保留 VM running 供下一波，但原 8080 job 不恢复。若启动失败且无容器运行，可精确 `colima stop -p aos-extension`；存在未知运行态时不擅自 stop，先冻结。

## 九步与退出

1. 复习 AT/AS、W5c8v/w、上位产品/技术边界及现场 HEAD。
2. 本方案先提交。
3. 运行前精确只读核验；偏差 STOP。
4. 单次 VM-only start；未知结果只读对账。
5. 专项只读 `docker ps`/端口/launchd/VM 复核；无代码测试不冒充。
6. 累计回归：W5c8q/r 已有隔离 PG 82 passed，不作为本波运行态 GREEN。
7. 8080 离线时浏览器验收不可执行；方案/实际能力一致性复审。
8. audit/verification 落盘、m1 提交、D-waves/AOS CAS/Prime 更新。
9. 自动下一波：若全部预期成立，计划 PG-only 且 Cron=false/snapshot=false/Host=0 的纯 HTTP 读回；否则冻结并优先补异常原因，不重发 attempt。

230 L0 挂起、dev-org 仅零 canary、m1 单写不 push、不读取商城源数据。

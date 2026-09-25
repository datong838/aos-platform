# W5c8w｜VM 启动路径只读审计收口

1. 复习 W5c8v、AT/AS 与 AOS-000684；真实 profile 停止、8080 bootout。
2. 方案先提交 `m1@2dc8a2fe`。
3. OS disk 路径/inode/mtime/大小、测试 VM sudo/loop、真实 VM/端口前检成立。
4. `RO=1`、`ro,noload` 离线 OS 审计：标准 docker/containerd/guestagent enabled，无发现自定义 Docker run/start、Postgres/AOS worker unit/cron/cloud-init 文本命令；宿主非 8080 AOS job 仍在，分类不夸大。详见 audit。
5. 精确卸载/解绑，`losetup -l` 空；真实 profile stopped、8080/18181 free、disk metadata 未变。
6. 本机 8080 API 暂不可用，业务浏览器不能验收。
7. W5c8v Docker restart=no + 本波 OS 启动审计支持下一波**仅 VM 启动候选**，不授权 DB 容器启动、真库迁移、Worker/ACK；guestagent/宿主其它 job 效果仍需运行时观察。
8. audit/verification 精确提交、D-waves/AOS CAS/Prime；无代码/专项测试，本波 `git diff --check` 通过。
9. 自动 W5c8x：制定并执行可停止的 VM-only start 与即时 `docker ps`/端口只读回读；任何意外容器启动则冻结，绝不触碰原 Run/商城源。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 `run_definition`、m1 单写不 push。

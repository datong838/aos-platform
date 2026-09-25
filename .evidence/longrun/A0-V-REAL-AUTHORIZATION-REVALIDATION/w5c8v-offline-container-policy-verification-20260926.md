# W5c8v｜离线容器策略只读取证收口

1. 复习 W5c8u/AT、AOS-000683 和真实 VM/端口/磁盘现场。
2. 方案先提交 `m1@bddc9e39`；只允许停止盘的只读 loop/mount 与 Docker metadata 白名单提取。
3. 预检真实 VM stopped、两个 regular disk 精确路径/大小、测试 VM 的 `losetup`/`mount`/非交互 sudo；条件成立。
4. OS 盘 RO=1、`ro,noload` 挂载后确认容器元数据为空并清理；数据盘同条件挂载，读取 3 个 `hostconfig.json`/`config.v2.json` 的白名单字段。全部 `postgres:16-alpine`、restart=`no`，详见 audit；无数据库卷、Mall 源或环境值输出。
5. mount/loop 全部清理，`losetup -l` 空、无专用挂载；真实 VM stopped、8080/18181 空闲、数据盘 mtime/size/inode 未变。
6. 8080 因 W5c8u 停用而不可用，业务浏览器不验收。
7. 结论限于 Docker restart policy；VM 内自定义 systemd/cron 等启动机制与宿主其他自动拉起仍需查，故本波**不启动真实 profile**、不迁真库、不回填/ACK。
8. audit/verification 落盘精确提交，D-waves/AOS CAS/Prime 更新；本波无代码/专项测试，静态差异检查通过。
9. 自动 W5c8w：离线只读审查 VM OS 自启动机制和宿主进程，再形成 DB-only profile 启动/恢复执行序列；没有全套证据继续 STOP。

230 L0 挂起、商城源不读、dev-org 零 canary、unknown 不重发/不手工 `run_definition`、m1 单写不 push。

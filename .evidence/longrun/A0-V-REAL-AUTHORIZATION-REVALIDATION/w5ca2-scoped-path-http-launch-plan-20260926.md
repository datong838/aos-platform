# W5ca2｜专用子进程最小 PATH 的可观察 HTTP 启动

## 上位与现状

复习 231/230 L0、W5c9a/e、W5ca0/1。W5ca1 已证 `launchctl submit` 确实进入 wrapper，托管预检在调用 `docker` 处 FileNotFoundError；交互式 Docker `/Users/ddt/.docker/bin/docker`，launchd PATH 空。失败 label `com.aos.a0v-http-w5ca1` 的 exit=256，仅可读诊断，不应复用；W5ca0 shell 后台消失原因仍未知。本波只给新进程注入 `PATH=/Users/ddt/.docker/bin:/usr/bin:/bin`，不改 `launchctl setenv`/全局配置/业务代码。

## 精确门禁与动作

- 新鲜核 m1/HEAD、精确有效 m1/18181 lease、18181/8080 无 listener、无 wrapper PID、唯一恢复 PG Up；旧失败 label 无 PID，精确移除该已失败 label 后读回缺席。新 label `com.aos.a0v-http-w5ca2` 与四个独立输出路径必须不存在。任何不一致停止。
- 同专用 wrapper `check` 再读回 Host=0、Cron/snapshot/Logic/health/JDBC=false、migration disabled、sourceCalls/runsCreated=0。不得输出身份/凭据。若不绿，不提交启动。
- 一次 `launchctl submit`：以 `/usr/bin/env` 为新进程入口，仅传上面的 PATH、绝对 Python/专用 wrapper、`serve --output`，stdout/stderr 分离。不得 KeepAlive/重试。读回 label 当前 PID、唯一 127.0.0.1:18181、serve preflight 与独立 check 同一零执行旗标、旧 8080 仍离线。失败则本波冻结，不再提交。
- 成功后用有界只读 `/docs` 与 `/openapi.json` 验收当前文档：2706 paths、已知 10 exact/7 shape 后置方法隐藏；冷启动可仅重取一次 GET，不发业务 endpoint。服务成功不授权原组 ACK/closure 或商城源。
- audit/verification、D-waves/AOS CAS/Prime 收口；无业务代码修改，本波专项是运行态读回，W5c9y 离线 29 passed/2 子测试仅历史累计基线；8080 业务浏览器验收仍离线。

## 九步与停止

1. 上位复习；2. 本方案先提交；3. 新鲜门禁/check；4. 清理确已退出的失败 label、单次子进程 PATH 启动；5. 只读 HTTP 专项；6. no-effect 复审；7. 8080 浏览器离线；8. 证据/记忆；9. 自动下一波。任何 unknown/flag 漂移/服务退出立即冻结，不重发启动或原 definition。

230 L0 挂起、dev-org 零 canary、商城源不读、m1 单写不 push。

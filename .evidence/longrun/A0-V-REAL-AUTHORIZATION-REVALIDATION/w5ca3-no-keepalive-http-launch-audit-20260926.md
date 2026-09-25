# W5ca3｜无 KeepAlive 单次托管与 18181 当前文档验收

方案 `m1@764e53f1`。本机 `launchd.plist` 手册与 task plist 双重静态核查；两个配置 `plutil -lint` 和 `plistlib` 合同通过，均 `RunAtLoad=true`、`KeepAlive=false`、无任何周期/路径触发。隔离 `/usr/bin/printf` 探针在 `gui/501` bootstrap 一次，状态 `not running`、`runs=1`、exit=0、stdout 恰一行；3 秒后仍 `runs=1`/一行，随后精确 bootout，label 缺席。W5ca1 失败 label 已缺席，不复用 `launchctl submit`。

真实 18181 前门：m1、精确 m1/18181 ACTIVE lease 至 2026-09-27 04:00 CST；旧 wrapper/18181/8080 listener、新 label/output 均缺席，唯一恢复 PG Up。独立专用 wrapper `check` 为 `CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN`，Host=0、Cron/snapshot/Logic/health/JDBC=false、migration disabled、sourceCalls/runsCreated=0、productionWebIdentityComplete=false。一次 `launchctl bootstrap gui/501` 专用 `w5ca3-http-only.plist`，只对该子进程提供 Docker PATH；新 PID36529，`runs=1`、唯一 `127.0.0.1:18181` listener；serve preflight 重复确认相同零执行旗标。3 秒后 PID/runs 均未变化，8080 无监听、恢复 PG 仍唯一 Up。

只读 `/docs` HTTP 200/1006B；`/openapi.json` 在 30 秒界内一次 HTTP 成功，路径 2706，已知 10 组 exact 文档 tags 均为前置 handler，7 组 shape 后置方法均不可见。未访问业务 GET/PUT/POST endpoint，未调用商城源、Worker、迁移、原 definition。W5c9n-y 代码现已在本地诊断 HTTP 文档层生效；这不提供正式 Web 身份、业务浏览器或原 A0-V closure 权威。真实租约到期自停尚未发生，不预报为 GREEN。

下一波 W5ca4 优先只读复核本次服务上线后的原组/全机 Host/Fleet/Owner/row proof 关键缺口与 18181 租约到期处置，不因文档 GREEN 重放原 attempt。

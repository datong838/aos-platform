# W5ca0｜受控 18181 刷新未知启动边界，fail closed

方案 `m1@00c70ca3`。新鲜前检 m1/HEAD、旧 PID28077 唯一 `127.0.0.1:18181`、命令为专用 wrapper `serve`/PPID1；8080 无监听与旧 API launchd job 缺席；`aos-extension` 仅恢复 PG Up。唯一 m1 精确 `local-process/aos-api-18181` lease ACTIVE、至 `2026-09-27T04:00:00+08:00`。专用 wrapper `check` 返回本地诊断 GREEN、Host=0、Cron/snapshot/Logic/health/JDBC=false、migration disabled、sourceCalls/runsCreated=0、productionWebIdentityComplete=false。未打印凭据/身份全文。

对**精确**旧 PID28077 一次 SIGTERM；读回 PID 与 18181 listener 均消失。确认临时 preflight/log 目标不存在后，按方案对专用 wrapper 发起**一次**后台 `serve` 命令。命令 shell 返回 0，但随即两次只读读回均没有新 wrapper 进程或 18181 listener，preflight JSON 未创建，日志为 0 字节。不能据 shell 返回值断言新服务启动，也不能推断具体消失原因；这是**未知启动边界**，本波没有第二次 serve、不访问 `/docs`/`/openapi.json`、不运行 Worker/业务请求。

最终已知安全态：旧 PID 已退出，18181/8080 均无监听，恢复 PG 仍唯一 Up，精确 lease 仍 ACTIVE 但未被解释为业务权威。W5c9n-y 的代码尚未获得在线 HTTP 验收。下一波 W5ca1 应先只读诊断后台进程托管方式、确定可观察的单次受控启动/失败输出与 stop rule，再新鲜门禁；不在本波重试或手工运行原 definition。原十二 Run row proof/Fleet/Owner/ACK/closure 仍无权威。

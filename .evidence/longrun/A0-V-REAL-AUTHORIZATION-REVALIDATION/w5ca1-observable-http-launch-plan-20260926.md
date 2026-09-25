# W5ca1｜受控 18181 可观察单次托管启动

## 上位与失败归因边界

复习 231/230 L0、W5c9a/e 与 W5ca0：shell 后台 `serve` 返回 0 却无 PID/监听/preflight、空日志，原因未知，不据此重复同一命令。`launchctl help submit` 只读显示支持精确 label、stdout/stderr 文件与命令；本波选择独立一次性 label 托管，以便把进程/退出状态与日志变成可观察边界。它不是五分钟唤醒定时任务，不自动重试，专用 wrapper 仍在 lease 失效时自停。绝不 bootstrap 旧 8080 plist。

## 文件级与动作

- 不改业务代码。先精确检查 m1/HEAD、`A0V-W5C9A-HTTP-ONLY-20260926` 唯一有效 owner/scope/expiry，18181/8080 无监听、无任何旧 wrapper PID、唯一恢复 PG Up、`com.aos.a0v-http-w5ca1` label 不存在、三个 `/tmp/aos-w5ca1-*` 输出目标不存在。任何不符冻结。
- 同专用 wrapper `check --output /tmp/aos-w5ca1-check-20260926.json`，只对白名单字段读回 Host=0、Cron/snapshot/Logic/health/JDBC=false、migration disabled、sourceCalls/runsCreated=0；失败不提交启动。
- 一次 `launchctl submit -l com.aos.a0v-http-w5ca1 -o /tmp/aos-w5ca1-stdout-20260926.log -e /tmp/aos-w5ca1-stderr-20260926.log -- <absolute python> <absolute wrapper> serve --output /tmp/aos-w5ca1-serve-preflight-20260926.json`。不加 KeepAlive，不重试。随后读回 label/PID/唯一 listener/preflight；如果任何未知，冻结本波，检查文件仅做只读诊断，不再提交第二次。
- 只有明确启动 GREEN 才以只读 HTTP 检查 `/docs` 与 `/openapi.json`（有界冷启动超时、最多一次只读重取），核 2706 paths 与已知 10 exact+7 shape 后置文档不可见。无 GET 业务端点，更无 PUT/POST。
- audit/verification、D-waves/AOS CAS/Prime 精确收口。浏览器 8080 离线，不把 `/docs` 当业务验收。若启动 GREEN 后服务意外退出，先冻结而非再次提交。

## 九步

1. 上位复习；2. 方案先提交；3. 新鲜只读门禁/`check`；4. 单次可观察启动；5. 只读 HTTP 专项与 W5c9y 累计基线区分；6. 零执行复审；7. 业务浏览器离线；8. 证据/记忆；9. 自动下一波。未知启动结果、不一致或 lease 过期停止；不手工 `run_definition`、不触原十二 Run。

230 L0 挂起、dev-org 零 canary、商城源不读、m1 单写不 push。

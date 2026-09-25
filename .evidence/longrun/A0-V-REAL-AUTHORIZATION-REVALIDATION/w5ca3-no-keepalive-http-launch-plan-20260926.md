# W5ca3｜显式无 KeepAlive 的受控 18181 单次托管

## 上位/进入事实

复习 231 九步/230 L0、W5c9a/e 与 W5ca1 自动重启补证/W5ca2 停止证据。`launchctl submit` 对失败预检产生 20 次自动拉起，已经精确移除，不得复用。现场手册 `launchd.plist` 明示 `KeepAlive` 默认 false、true 才持续保活，`RunAtLoad` 仅装载时启动一次，`EnvironmentVariables` 限定该 job。先做无业务进程负例，不凭手册文字直接启动 API。

## 文件级计划和门禁

- 新增本波 task 专用配置 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5ca3-once-probe.plist`：`/usr/bin/printf` 只写一次固定标记，`RunAtLoad=true`、`KeepAlive=false`、无 StartInterval/StartCalendarInterval/WatchPaths/QueueDirectories，输出独立 `/tmp`。`plutil -lint` 与 Python `plistlib` 静态断言后在 `gui/501` 精确 bootstrap，至少两次读回输出仅一条且 PID 已退出，再精确 bootout。若自动重启或失败，不启动 API。
- 新增 `.evidence/.../w5ca3-http-only.plist`：唯一 label、绝对 Python/专用 wrapper `serve`、`WorkingDirectory` 为 m1 仓库、子进程 `PATH=/Users/ddt/.docker/bin:/usr/bin:/bin`、`RunAtLoad=true`、`KeepAlive=false`、独立 stdout/stderr/preflight。禁止全局 `launchctl setenv`，不含凭据或业务请求。
- 再新鲜核 m1/HEAD、lease 唯一有效、无 wrapper/PID/18181/8080、唯一恢复 PG Up、旧失败 label 缺席、专用新 label 和输出路径不存在；独立 wrapper `check` 零执行旗标全绿。任何不符冻结。
- 仅一次 `launchctl bootstrap gui/501 <task plist>`；读回唯一 PID/18181、preflight Host=0/Cron/snapshot=false/migration disabled/sourceCalls/runsCreated=0。失败时检查是否自重启；如活失败 job，精确 bootout 防重复，不二次 bootstrap。
- 成功后只读 `/docs` 和 `/openapi.json` 有界验收 2706 paths、已知 10 exact/7 shape 后置方法不可见。无业务 endpoint/商城源/worker。audit/verification、D-waves/AOS CAS/Prime 精确提交。8080 业务浏览器仍离线。

## 九步与停止

1. 复习上位；2. 本方案先提交；3. 创建/静态测试隔离 plist；4. 一次 probe + 一次条件满足后的受控 API bootstrap；5. 只读 HTTP 专项，W5c9y 29 passed 仅历史累计；6. 零执行一致性；7. 8080 浏览器离线；8. 证据/上下文；9. 自动下一波。任一边界未知、重复 PID、预检失败即停止且隔离 label，不重发原 attempt。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不手工 `run_definition`、m1 单写不 push。

# W5ca1｜托管预检失败验证

1. 复习 231、230 L0、W5c9a/e、W5ca0 未知后台边界。
2. 文件级方案先提交 `m1@0aa7b13a`。
3. PID/端口/租约/PG/label 与独立 wrapper `check` 全部满足零执行门禁。
4. 单次 `launchctl submit` 真实进入 wrapper，但 preflight `STOPPED_FOR_INSPECTION`、LastExitStatus=256，18181 不监听；没有第二次提交。
5. 本波无代码修改、无线上 HTTP 专项通过；W5c9y 离线 29 passed/2 子测试仅历史基线。读回异常链 FileNotFoundError 落在启动 `docker` 子进程处，交互式 docker 在 `/Users/ddt/.docker/bin`、launchd PATH 空；仅支持托管 PATH 缺口诊断，不把它当已修复。
6. 18181/8080 仍离线、唯一恢复 PG Up；没有源调用、业务写、worker 或 definition replay。
7. 浏览器和 `/docs`/`/openapi.json` 未验收。
8. audit/verification/D-waves/AOS CAS/Prime 记录 `STOPPED_LAUNCHD_PREFLIGHT_DOCKER_PATH`，保留失败 label 供下一波精确处理。
9. 下一波 W5ca2：方案先行、检查失败 label 无活 PID、专用子进程最小 PATH 的受控单次启动；不改全局环境，不重放原组。

230 L0 挂起、dev-org 零 canary、商城源不读、m1 单写不 push。

# W5c9e｜18181 专用进程租约自停守卫审计

方案 `m1@40235b40`。只修改 W5c9a 专用 wrapper：精确读取唯一 `A0V-W5C9A-HTTP-ONLY-20260926`、owner=m1、ACTIVE、scope=18181、时区化未来 expiry；缺失、重复、错误字段、坏 JSON、过期一律 fail-closed。仅 `serve` 起守卫线程，至多 30 秒复核提前撤销，距到期不足 30 秒则按剩余时间等待；失效向**本进程**发 SIGTERM，让 Uvicorn 优雅退出。不自动续租、不新建 Codex 定时任务；旧 Product/API/其它 wrapper 不变。

RED 新行为 7 failed，最小实现后新增单元/参数化测试覆盖有效、过期、缺失/重复/坏 JSON、错误 owner/scope/status、提前撤销/到期回调、仅 serve 接线；与 W5c9a/W5c9d 相关累计 **30 passed、7 既有 warning**，py_compile 通过。测试的终止动作采用注入回调，没有杀真实进程。

真实重载前新鲜确认旧纯 HTTP PID26881 唯一监听 127.0.0.1:18181、新 lease 有效、唯一恢复 PG Up、8080 无监听/job。仅一次 SIGTERM 精确停止 PID26881，读回 PID/18181 消失，PG 不变；新 wrapper 单次启动 PID28077，唯一 127.0.0.1:18181 listener。新进程 preflight `CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN`，Host=0、Cron=false、snapshot=false、migration disabled、sourceCalls/runsCreated=0；`/docs` HTTP 200。8080/job 仍缺席，Docker 仍只有恢复 PG。

**尚未经历 2026-09-27 04:00 CST 真正到期**：现场自停结果不能预报为已验收，只能陈述代码/隔离测试及本次重载接线。租约到期若进程仍活，必须按异常冻结并精确停进程，不能把过期 18181 当授权。原组 12 Run/closure 不变，本波未查商城源或触发业务写入。

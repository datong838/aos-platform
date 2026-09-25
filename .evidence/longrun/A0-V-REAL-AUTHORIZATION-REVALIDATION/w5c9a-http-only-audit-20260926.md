# W5c9a｜新租约与纯 HTTP 18181 运行态审计

方案 `m1@f09b2c3e`，失效私有路径补充 `m1@3eeda20c`。新鲜发现旧受控 API 租约已过期；正式 `memory-receipt task-start` 以 AOS-000688 为 expected revision 创建 `A0V-W5C9A-HTTP-ONLY-20260926`，owner=m1、精确 scope=`local-process/aos-api-18181`、有效至 2026-09-27 04:00 CST。未复活旧 task；新任务只代表进程所有权。

新增受控启动器 task 精确白名单与 scope 检查、独立 W5c9a wrapper。旧默认凭据/trust/bundle 路径不存在，第一次直接只读 preflight 返回 `HostBlocked CREDENTIAL_FILE_INVALID`，没有启动 18181。wrapper 精确引用现存 BM mode 0600 私有凭据/信任根和 BN canonical signed-bundles 根（含 Niushop 1.23.2）；不修改/打印凭据，原 Product/default wrapper 不变。RED 新 lease 测试 1 failed、RED wrapper 文件缺失 1 failed，最小实现后定向累计 **15 passed、7 既有 warning**，py_compile 通过。

wrapper 的未启动服务 preflight 返回 `CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN`：Host=0、Cron=false、snapshot worker=false、migration=disabled、sourceCalls=0、runsCreated=0。新鲜确认唯一 PG Up、8080/18181 free、旧 8080 launchd job 缺席、租约有效后，单次启动 wrapper `serve`，PID 26881；同一 PID 唯一监听 `127.0.0.1:18181`。进程写出的 preflight 白名单仍为上述四 flag 与 0/0；8080 无监听/job，Docker 仍唯一 PG。

只读 HTTP `/docs` 返回 200（约 1ms）；首次 `/openapi.json` 5 秒超时，不把该端点当 GREEN，也不据此运行任何业务操作。18181 是本地诊断纯 HTTP，不能代表生产 Web 身份/商城源/原 12 Run closure；业务浏览器 8080 仍离线。旧 8080 plist 继续禁止 bootstrap，下一波先只读授权/Run/Receipt 对账方案，仍不执行定义、Worker、迁移、回填或 ACK。

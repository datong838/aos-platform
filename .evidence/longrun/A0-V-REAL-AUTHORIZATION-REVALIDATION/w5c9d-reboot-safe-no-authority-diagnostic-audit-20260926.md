# W5c9d｜重启安全 Host no-authority 诊断审计

方案 `m1@fa8405ac`。新增纯只读 `scripts/a0v_w5c9d_reboot_safe_host_diagnostic.py`，仅复用 W5c4t 精确原组 READ ONLY 分类、W5c5f 受管目录 REPEATABLE READ READ ONLY 分类、本机 exact Host launcher PID 解析；不调用过期 W5c4q 独立 snapshot-worker 状态，不生成 closure intent/key 或调用 Owner/Worker。输出始终带 `automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`；错误/漂移返回 FROZEN，不打印 `ps args`、DSN/Env/商城源。

RED 新脚本缺失 6 ERROR，最小实现后本波专项 6/6、与 W5c9a 受控 API 相关累计 **21 passed、7 既有 warning**，py_compile 通过。覆盖 24h 未到/已到、本机 Host 存活、目录漂移、基线漂移、错误 action flag；即使全部本机读数看似平静仍不授权全机 closure。

2026-09-26 04:00:45 CST 真实只读诊断输出：`LOCAL_QUIET_NO_GLOBAL_AUTHORITY`、`timeGate=ELIGIBLE_NO_AUTHORITY`、knownLocalHostCount=0、runningOriginalRuns=12、三授权旗标均 false；明确缺 `FULL_MACHINE_HOST_TOPOLOGY`、`FRESH_SINGLE_TRANSACTION_OWNER_GATE`、`SEPARATE_REAL_CLOSURE_PLAN_AND_UNIQUE_KEY`。同时 Docker 仍唯一恢复 PG Up、18181 PID26881 存活、8080/job 缺席。时间已到**只改变时间分类**，绝不授真实关闭。

# BI-W10-01 SSH 隧道生命周期整改验收

## 自然事实

- `2026-08-29 03:00 Asia/Shanghai` P02 自然运行 `scr-0b90904bc6604280` 成功，写入 `124` 行。
- `2026-08-29 04:00 Asia/Shanghai` P03 自然运行 `scr-458fbc8eba534693` 在业务读取前因 SSH 本地隧道未在有界窗口内就绪而失败，写入 `0` 行。
- 未手工执行 P03/P07/P08，未重放 DLQ，未修改源系统或真实业务数据。

## 实现与安全边界

- `services/aos-api/aos_api/jdbc_connector_runtime.py`：有界 SSH 握手、keepalive、超时子进程回收、stderr 稳定分类、启动预建输出去敏。
- `services/aos-api/aos_api/main.py`：只读 SSH 预建移出 schema bootstrap 分支，`managed` 与 `legacy_bootstrap` 共用。
- `services/aos-api/tests/test_jdbc_connector_runtime.py`、`services/aos-api/tests/aip/test_w2c_cron_guard.py`：覆盖命令参数、超时回收、诊断去敏、预建去敏和 managed 启动。
- `services/aos-api/tests/test_domain_router_manifest.py`：将先前已交付的 canonical `GET /case-selection` 纳入路由基线；本整改未新增路由。
- 未增加 Pipeline/DB 重试，未延长就绪总窗口，未触发 Provider、迁移、发布或业务外部效果。

## 测试与运行时回读

- 专项：`48 passed, 2 subtests passed`。
- 累计：`158 passed, 2 subtests passed`，仅有既有 7 条 warning。
- `compileall` GREEN；`git diff --check` GREEN。
- `2026-08-29 04:39 Asia/Shanghai` 精确重载 PID `34859`，唯一监听 `127.0.0.1:8080`。
- managed 启动预建 `1/1` 成功，隧道监听 `127.0.0.1:56887`；新启动日志仅含哈希 key、本地端口、耗时和认证模式，不含 endpoint/user/remote 原文。
- `org-org/dev-project` GET-only SourceReadiness 为 `9/12`：P01/P02/P04/P05/P06/P09/P10/P11/P12 ready，P03/P07/P08 failed。状态未被修复逻辑伪造为 GREEN。
- 本切片无页面修改，因此新浏览器截图 `N/A`；同一连续执行回合中已完成八菜单逐页打开、点击、无横向溢出与 console error 为零的复验，未因本后端修复改变页面合同。

## 结论

代码、测试、精确运行时与日志去敏证据闭合；P03/P07/P08 的业务 readiness 仍须由各自下一自然 slot 提供新事实，本验收不把代码修复改名为业务运行成功。

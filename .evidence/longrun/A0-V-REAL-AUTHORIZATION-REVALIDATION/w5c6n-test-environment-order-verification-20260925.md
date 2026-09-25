# W5c6n 组合测试环境顺序与 skip 可验证性验证（2026-09-25）

## 第 1/9～4/9 步：复习、方案、复现、最小改动判定

- 方案 `067e2856` 先提交；复习 `services/aos-api/tests/conftest.py` 的 session 级一次性 `aos_test_*_ti4_test` 数据库、旧 Runtime Host/恢复配置函数环境夹具与 AR1-c 专用 18432 测试开关。
- Runtime Host 与 W5c5i PG 两文件正反顺序均 `23 passed`；加入恢复配置目标三文件组合 `42 passed`。目前未复现 `AOS_DATABASE_URL` 污染；不对共享 fixture 做猜测性修改。本波无生产/测试代码改动。
- `test_generation_attempts_pg.py` 默认 `17 skipped` 的原因是 `test_lifecycle_pg.py` 显式 `AOS_EXTENSION_PG_TEST=1` 门，且测试自身固定 `127.0.0.1:18432`。按原设计启动现存专用隔离 `aos-extension-pg`、加 `--noconftest` 后 `17 passed`；对象旧专项同条件 `8 passed`。这些通过只证明隔离临时 schema，不证明真实运行。

## 第 5/9～7/9 步：累计回归、浏览器与一致性复审

- W5c5k–z/W5c6a–m 累计 `80 passed`；两个测试 PG 已停止。运行结束存在既有 JDBC cache 日志器向已关闭捕获流输出的 `ValueError`，不影响测试 exit 0，但保留为下一波可修测试噪声。
- 浏览器只读整组采集列表：A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`。有待同步写操作 1，未冲刷/保存/运行。
- 真实门只读 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`closureAuthorized=false`、`runningOriginalRuns=12`、`stalledClosureReceipts=0`，到线 `2026-09-25T20:00:04.800482+00:00`。方案与实际一致：未知环境污染未伪修、默认 skip 未算绿、专用库未和真实库混用。

## 第 8/9～9/9 步：上下文与下一波

- verification 提交后 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆并读回；提交见 docs context55。
- 下一波 W5c6o：先计划，复现并最小消除 JDBC cache 退出时写已关闭日志捕获流的测试噪声；若不可安全修，保留明确债，不动 A0-V 真门。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。

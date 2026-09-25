# W5c6q 旧 Schedule 单项长时路径有界观察（2026-09-25）

## 第 1/9～4/9 步：方案与独立单项

- 上位 W5c6p 确认 17 项中唯一未终态测试；方案 `3c8c4759` 先提交。本波无代码改动，不改变断言、事务或生产 deadline。
- 单项 `test_claim_ack_and_input_ack_loss_recover_original_group_once` 独立运行，pytest setup 15.11 秒；到约 10 分 39 秒仍未完成，按 600 秒预算附近中断，exit 2，不能算通过。采样/控制延迟使实际 wall time 超出 600 秒约 39 秒，此偏差保留，不冒充严格上限执行成功。
- 隔离测试库只读序列：约 1 分钟 5 对象/5 receipt，2 分 37 秒 11/11，3 分 21 秒 12/12；约 4 分钟达到 12 对象、13 ingest receipt、1 link；10 分钟时 12 Run 仍 running。进程持续约 50% CPU，PG 查询文本/连接持续变化，不能直接认定死锁。中断栈在 psycopg connection；先前 W5c6p 单点栈在 canonical JSON，两者都不足以定根因。一次性数据库在 SIGINT 后自动删除。

## 第 5/9～7/9 步：累计、只读验收与复审

- W5c5k–z/W5c6a–m 加 JDBC 累计 `111 passed`；本长时单项不在该通过集合。测试 PG 已停止。
- 浏览器只读 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`，未保存/运行/冲刷待同步写操作。真实门仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0。
- 方案/实际一致：本波仅观察测试库，未把中间写入等同测试通过，也未把终态未知作为重发许可。由于单项未终态，旧三模块 17/17 仍不绿。

## 第 8/9～9/9 步：上下文与下一波

- verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回；提交见 docs context58。
- 下一波 W5c6r：先制定精确文件级诊断方案，给旧单项的三次 `execute`/12 来源每阶段加测试专属单调计时或只读 profiler，定位 10 分钟运行时间来自何段；在取得根因前不改生产热路径或放宽断言。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。

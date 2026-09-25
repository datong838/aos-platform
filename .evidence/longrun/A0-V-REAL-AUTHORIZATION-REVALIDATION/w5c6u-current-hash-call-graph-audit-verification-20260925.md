# W5c6u Current/哈希调用图安全审计验证（2026-09-25）

## 第 1/9～4/9 步：方案与无效应合同

- 复习 W5c6r–t 计时与 Object/Link/Retirement 原代码后方案 `03beb16a` 先提交；仅新增静态合同 `f6543842`，未改生产/DB/部署。
- Object 在 12 个成员循环里，每次 `single.resume_saved` 前重读 `_journal.read_current`，结束时再 `run_current` 验证投影；此循环成本与 12 次成员执行不能混为一项。
- Link/Retirement 均在准备、独立 Store 效应提交后、投影及完成读回间重新验证 current；跨独立提交的重读是防止权威漂移的安全边界，不能用测试运行慢为由直接缓存/删除。静态合同 3 passed，只锁关键顺序，不宣称性能根因。

## 第 5/9～7/9 步：回归、浏览器与复审

- W5c5k–z/W5c6a–u、JDBC 与计时合同累计 `115 passed`；测试 PG 已停。
- 浏览器只读 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`，待同步写操作 1 未冲刷。真实门 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、12 原 Run running、stalled Receipt 0、`closureAuthorized=false`。
- 方案/代码一致性：静态调用图只证明边界仍存在。可优化候选需先量化同事务重复的次数/耗时，并证明原数据库时钟、RLS、幂等、投影读回不弱化；本波没有这样的证明，故没有生产改码。旧长时单项仍未终态。

## 第 8/9～9/9 步：上下文与下一波

- verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回；提交见 docs context62。
- 下一波 W5c6v：先方案，用测试专属聚合计数/耗时统计 Object/Link/Retirement `read_current`、canonical JSON 与投影子段，不输出业务内容；取得具体热函数和安全等价性前不改生产。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。

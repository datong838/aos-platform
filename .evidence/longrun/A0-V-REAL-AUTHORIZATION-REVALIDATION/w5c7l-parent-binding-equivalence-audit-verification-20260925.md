# W5c7l Parent Binding 等价性审计 verification（2026-09-25）

## 第 1/9～4/9 步：方案与审计

- 方案已先行提交：`c48bc5a9`；只读查询/事务审计已提交：`894edcc4`。
- 审计将 `_bound_parent` 拆成 envelope、current claim/control、Run/Schedule/Graph/Source 绑定与 completed 守卫，逐项保留 RLS、`FOR SHARE`、事务及错误语义。
- callback 前后两次 `_load` 不得合并；同一 `_load` 内可能复用 claim 读回仅是待证假设，尚未授权生产优化。

## 第 5/9～7/9 步：验证与复审

- 相关 Host/closure、W5c5k–z/W5c6a–z/W5c7c/e/f/h/j/JDBC 累计回归：219 passed；测试 PG 用后已停。
- 浏览器只读 `/data/schedules`：A0-V Canonical 版本 4「已配置 · 已停用」，运行状态「数据组已停用」，核对时间 2026/9/25 16:16:13；未保存、未运行、未冲刷待同步写操作。临时 5174 Vite 已停。
- W5c7k 旧 12-source 长测正式结果仍为 `MONOTONIC_TIMEOUT`/124，绝非 GREEN；本波未重跑、未更改生产代码/DB/索引。
- 真实 A0-V closure gate 仍是 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`：定义 rev4 disabled、12 原 Run running、stalled closure Receipt=0。24 小时时间条件尚未到；到时也不自动授权，还需完整 Host universe 与真实 Owner gate。旧自然 attempt 不重发、不手工 `run_definition`。
- 商城源行未读；230 L0 继续挂起；dev-org/dev-project 仅零 canary；m1 单写、不 push。

## 第 8/9～9/9 步：交接

本文件提交后，将 CAS 更新 docs/AOS 跨对话上下文及 Prime 独立长记忆，读回一致性。下一波 **W5c7m**：方案先行，做测试专属 `_bound_parent` 子段透明计时与失败门合同；不改生产查询，不以性能探针推导真实 closure 授权。

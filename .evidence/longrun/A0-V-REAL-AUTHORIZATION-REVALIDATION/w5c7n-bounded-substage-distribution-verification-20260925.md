# W5c7n 有界 Parent 子段分布诊断 verification（2026-09-25）

## 第 1/9～4/9 步：唯一长测与分布

- 上位 231/231-5、W5c7k/l/m、旧 ACK-loss 测试及单调 runner 已复习。方案 `b03cf036` 先提交；本波未改生产/测试代码、DB、索引或部署。
- 隔离 PG，`AOS_TEST_SCHEDULE_TIMING=1`，旧 12-source ACK-loss 用例**只运行一次**，runner 单调上限 900 秒、宽限 5 秒。正式结果：pytest **1 passed**、7 warnings、784.95 秒；runner `CHILD_EXITED`、`timedOut=false`、`childExitCode=0`、`runnerExitCode=0`、单调 794.823 秒。与 W5c7k 的超时诊断是不同批次；本次长例可记 GREEN，不回写旧超时事实。
- 完成时最终聚合：`_bound_parent` 2880 次/498.139 秒；其内部 envelope read 4224 次/3.347 秒，current claim 2208 次/383.229 秒，completed claim 672 次/105.341 秒，running binding 4416 次/8.157 秒，completed binding 1344 次/5.993 秒。计数大于 parent 次数系嵌套读/绑定复核；时间也是嵌套，**不可相加**。热点在重复的 current/completed claim 权威读回，不在 envelope 或基础 schedule binding。
- 同次 Object execute 111.750 秒、Link execute 196.858 秒、Retirement execute 590.335 秒、第一次 Completion complete 673.153 秒；均为嵌套/阶段间数据，不能相加。最终 Retirement Input `_load` 178 次/458.246 秒，仍逐成员复查。

## 第 5/9～7/9 步：清理、只读验收、等价性复审

- 测试临时 `aos_test_%` 数据库读回 **0**；相关短回归继承 W5c7m 同代码版本 224 passed，本波无代码变更；测试 PG 用后已停。
- 真实 gate 再读回：`REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；全机 Host topology、新鲜单事务 Owner gate、独立真实 closure 计划/key 仍缺。
- 浏览器 `/data/schedules` 只读 A0-V Canonical rev4「已配置 · 已停用」，运行状态「数据组已停用」（2026/9/25 16:52:03），当前身份无权启用；待同步写操作 1 未冲刷。临时 Vite 已停。
- 结果仅定位 claim 验证成本，不证明 W5c7l 所述同一 `_load` 内复用等价。callback 前后 `_load`、每成员 running/completed 及 RLS/锁序/错误码必须保留；不能凭一次 GREEN 变更真实 closure 权限或重发旧 attempt。
- 商城源行未读；230 L0 挂起；dev-org/dev-project 仅零 canary；m1 单写、不 push。

## 第 8/9～9/9 步：交接

本 verification 提交后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立长记忆并读回。下一波 **W5c7o**：方案先行，围绕同一 `_load` 内 claim 的可能复用建立锁序/并发变化/完成态/恢复态/错误码负例与隔离 PG 对抗测试；未证明前不优化生产，不动真实 closure。

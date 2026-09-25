# W5c7k 单调有界旧 Schedule 长测诊断核验（2026-09-25）

## 九步结果

1. 复习 W5c6u–z、W5c7i/j、旧 12-source ACK-loss 用例与单调 runner 合同。
2. 方案 `10ab29b0` 先提交；本波只新增本核验，没有生产/测试代码修改。
3. 隔离 PG 单次运行，`AOS_TEST_SCHEDULE_TIMING=1`、runner 900 秒上限/5 秒宽限。正式摘要：`MONOTONIC_TIMEOUT`、`runnerExitCode=124`、`childExitCode=2`、`monotonicSeconds=903.437`（含中断宽限）；pytest `KeyboardInterrupt`、`7 warnings in 892.89s`，**无正式 pass/fail，不计 GREEN**。未重跑本波。
4. 分段计时：Object execute 120.579 秒、Link execute 222.088 秒、Retirement execute 653.712 秒、Completion complete 一次 779.076 秒；这些是嵌套区间，不可相加。InputOwner `_bound_parent` 2808 次/567.392 秒，Retirement Input `_load` 172 次/516.191 秒，Retirement claim completed current 46 次/25.915 秒；慢点集中在 Retirement 反复完整 12 成员读回。此为热点证据，不是删校验授权。中断后 `aos_test_%` 临时数据库读回 **0**。
5. 不含旧长例的 Host/closure + W5c7c/e/f/h/j + W5c5k–z/W5c6a–z/JDBC 累计 **219 passed**。真实 gate 仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`closureAuthorized=false`、12 原 Run running、stalled closure Receipt=0。
6. 2026-09-25 16:01 CST 浏览器只读：A0-V Canonical “已配置 · 已停用 · 版本 4”，运行状态“数据组已停用”，当前身份无权启用；待同步写操作 1 未冲刷。临时 Vite/测试 PG 已停。
7. 一致性与风险：仍保留 callback 前后 `_load`、每成员 `_bound_parent` 和 running schedule 校验。下一步须证明同事务批量化/索引等价、错误码与并发失效不弱化；未证明前不动生产。真实库 `a0v_092`、全机 Host/worker fence/Fresh Owner 门未齐，无真实 closure 授权。
8. 本文件提交后 CAS 更新 docs/AOS 上下文与 Prime 独立长记忆并读回，docs 提交另记。
9. 下一波 W5c7l：先方案，审计 `_bound_parent` 的 DB 查询结构、事务可见性与逐成员 running 绑定，设计保持授权语义的批量化/索引切片及负例；不直接删读回。

旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读；230 L0 挂起；dev-org 零 canary；m1 单写不 push。

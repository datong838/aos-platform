# W5c7j 单调计时有界隔离测试 Runner 核验（2026-09-25）

## 九步结果

1. 复习 W5c7i 计时冲突、W5c6t–z 与旧 Schedule fixture；本波不再运行旧长例。
2. 方案 `39be010e` 先提交；文件级仅测试 runner、专项测试及本核验。
3. 实现 `4c0740be`：只执行显式命令一次，`time.monotonic()`/`subprocess.wait(timeout)` 限预算，独立进程组；正常保留子退出码，超时先 SIGINT、宽限后 SIGKILL，返回 124 并输出机器可读摘要。无文件/网络/DB/真实 Host/closure 接线。
4. 短命令专项 **8 passed**：成功、非零原样返回、超时、无重发、非法预算阻止启动、启动失败明确 125。没有把旧长例当作本波专项通过。
5. Host/closure + W5c7c/e/f/h/j + W5c5k–z/W5c6a–z/JDBC 累计 **219 passed**；真实 gate 仍 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`automaticAction=false`、`closureAuthorized=false`、12 原 Run running、stalled closure Receipt=0。旧长例仍未有正式终态。
6. 2026-09-25 15:40 CST 浏览器只读：A0-V Canonical “已配置 · 已停用 · 版本 4”，运行状态“数据组已停用”；1 条待同步写操作未冲刷。临时 Vite/测试 PG 已停。
7. 一致性与风险：runner 只保证有界测试执行，不修复旧 Schedule 性能/逻辑，也不提供真实 closure 权威。真实库 `a0v_092`、全机拓扑/worker fence/Fresh Owner 门均未齐。下一次长测须另 plan 且使用本 runner。
8. 本文件提交后 CAS 更新 docs/AOS 上下文与 Prime 独立长记忆并读回；docs 提交另记。
9. 下一波 W5c7k：先方案，隔离 PG 中用 runner + 有界分段诊断旧长例；若仍未终态，转向不削弱授权的查询批量化设计。

旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读；230 L0 挂起；dev-org 零 canary；m1 单写不 push。

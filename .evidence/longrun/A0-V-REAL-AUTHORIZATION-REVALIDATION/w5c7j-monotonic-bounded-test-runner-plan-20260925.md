# W5c7j 单调计时有界隔离测试 Runner 方案（2026-09-25）

W5c7i 的旧长测没有终态，`ps etime` 与 pytest duration 不一致；靠人工墙钟观察不能稳定实施 900 秒上限。本波仅补测试执行工具，不再运行长例，不改变生产安全读回。

## 文件级九步

1. 复习 W5c7i、旧 Schedule 测试、W5c6t–z 与脚本约定；确认隔离 PG/fixture 清理边界。
2. 本方案先提交。新增 `scripts/a0v_w5c7j_monotonic_test_runner.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5c7j_monotonic_test_runner.py`、verification；不改旧测试或生产代码。
3. Runner 只执行显式 `--` 后命令，以 `time.monotonic()` 计预算、独立进程组运行；正常退出原样保留子退出码；超时先 SIGINT 并给短宽限，再 SIGKILL，明确返回 124，打印机器可读结束摘要。不能根据墙钟跳变延长预算；不中途自动重试。
4. 用短命令专项验证 success、非零退出、超时、有界宽限和无隐式重发；不触碰真实 A0-V 状态或商城源行。
5. 跑 Host/closure、W5c5k–z/W5c6a–z/W5c7c/e/f/h/JDBC 累计回归；临时 PG 用后停。
6. 浏览器只读 rev4 disabled，不保存/运行/冲刷队列。
7. 复审 runner 只是测试控制，不是旧 Schedule 已通过；没有生产优化/真实 closure 授权。
8. verification 提交后 CAS 更新 docs/AOS 上下文与 Prime 独立长记忆并读回。
9. 下一波 W5c7k：先方案，使用已验证单调 Runner 在隔离 PG 做带分段诊断的长例，不超过严格预算；如仍未终态，转向不削弱授权的查询批量化设计。

m1 单写不 push；不重发旧真实 attempt、不手工 `run_definition`；商城源行不读、230 L0 挂起、dev-org 零 canary。

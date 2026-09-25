# W5c6o JDBC 退出清理日志生命周期验证（2026-09-25）

## 第 1/9～4/9 步：方案、红测与最小实现

- 复习 D2.6 JDBC 通用运行时、FastAPI shutdown/atexit 双入口和 AR1-c 既有 closed-stream 噪声；方案 `8d3d697a` 先提交。
- 新测试先得 `1 failed, 1 passed`：`_cleanup_all_cached_at_exit` 不存在，原进程退出在 pytest 捕获流关闭后抛 `ValueError: I/O operation on closed file`。
- 代码 `d03de0d6` 只在 atexit wrapper 关闭日志发射，原 `_cleanup_all_cached` 的锁、连接/隧道 close/clear 顺序不变；FastAPI `jdbc_runtime_shutdown` 仍默认有信息/失败日志。退出路径即使连接 close 报错仍尝试关闭隧道并清空缓存；无新增外部调用、权限或业务读取。

## 第 5/9～7/9 步：测试、页面与复审

- JDBC 专项 `31 passed`；W5c5k–z/W5c6a–m 加 JDBC 累计 `111 passed`，exit 0，进程尾部没有 closed-stream traceback。测试 PG 已停止。
- 浏览器只读 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`；待同步写操作 1 未冲刷。真实门只读 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、12 原 Run running、stalled Receipt 0、`closureAuthorized=false`，严格到线 UTC `2026-09-25T20:00:04.800482+00:00`。
- 一致性复审：正常 shutdown 保留日志；解释器退出时日志 handler 可能被测试/运行框架拆卸，故只在该阶段静默，不改变资源释放。退出 close 失败本来仅 warning 且继续；此阶段 warning 不再可靠，需依赖正常 shutdown/进程监控观测。此权衡未扩大到通用日志框架或 A0-V 效应。

## 第 8/9～9/9 步：上下文与下一波

- verification 提交后 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆并读回；提交见 docs context56。
- 下一波 W5c6p：检查旧 Schedule 长时组合回归及余下测试债，先方案/明确上限，再作最小修复；真实 closure 仍需独立新计划、全机拓扑和同事务 Owner 门。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。

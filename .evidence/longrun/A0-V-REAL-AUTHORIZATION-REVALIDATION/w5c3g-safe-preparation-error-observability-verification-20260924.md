# W5c3g Prepare 失败安全观测验证（2026-09-24）

## 结论

**GREEN，限安全诊断代码和空载 Host。** 原 `PreparedJob._watch` 在保留原 finalize/re-raise 语义的前提下，仅记录有界异常类型、仓库相对代码位置/函数/行号；不记录异常值、参数、frame locals、SQL、artifact 或身份字段。唯一 Host 定向重载为 PID17302，`RUNTIME_HOST_ACTIVE`、`liveTargets=[]`。此波没有新安装/prepare/verify。

## 验证与运行边界

- 方案 `aa762371`；`test_preparation_safe_diagnostics.py` 与既有 `test_preparation_worker.py` 合计 9 passed，包含含有伪敏感字符串的异常，断言诊断日志完全不含该值、失败仍原码 finalize。`git diff --check` 通过。
- 重载前 W5c3f 独立 audit GREEN、未终态 runtime operation0、相关 active attempt0、Host PID15014 空载；旧 job bootout 后正式输出 STOPPED 并退出。首次相对路径 bootstrap 报 launchd code5；只读回读确认 label 不存在、旧 PID/进程不在后，使用绝对路径一次 bootstrap 成功，不存在双 Host。新 PID17302 状态 ACTIVE/positive tenant 唯一/canary0/liveTargets 空。
- 两次失败安装均已卸载，九路 legacy/fenced、12 schedule off，未读商城源、不触发业务 Run。安全诊断路径尚未遇到下一次真实失败，不能称根因已解决。

## 下一波 W5c3h

先方案，创建全新 predecessor-free approved 安装；保持隔离。下一独立波才单次自然 prepare，若再失败，使用私有 Host 日志中的安全异常分类定位并正式退休，绝不重发或在失败安装上 verify。

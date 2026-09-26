# W5cac｜旧 Schedule 三模块 17 项同会话有界累计方案

## 上位与安全边界

复习 231 A0-V→A1、230 L0 挂起、W5c6p 的 16/17 分拆结果、W5c7n 单个长例 1 passed/794.823 秒、W5c7o–s 未获准优化 claim 的结论、W5ca5 原组 closure no-authority。当前 AOS-000726 `incomplete` 仍保存“完整 17/17 未绿”的历史债；两个批次单独通过不等于本代码版本同会话累计通过。

## 文件级/运行清单

- 只读三文件：`services/aos-api/tests/extension_runtime/test_snapshot_schedule_runtime_pg.py`（7）、`test_pipeline_snapshot_schedule_claim_pg.py`（9）、`test_pipeline_snapshot_schedule_recovery_pg.py`（1）；只读 `scripts/a0v_w5c7j_monotonic_test_runner.py`、W5c6p/W5c7n verification 和当前 m1/专用测试 PG 状态。
- 原则上不改生产/测试代码。使用 `colima-aos-a0v-test-only:5433`、`aos-a0v-test-pg`、项目 `.venv`、`AOS_DOTENV_DISABLED=1`、`AOS_TEST_USE_SHARED_DATABASE` 非 1、标准自动创建销毁 `aos_test_*_ti4_test` fixture。不得连接 18435 真库或读商城源。
- 单次运行上述三文件，`a0v_w5c7j_monotonic_test_runner.py` 硬界 1500 秒、SIGINT 5 秒宽限；不得并行重复。正式结果只认 runner `CHILD_EXITED/childExitCode=0` 且 pytest 17 passed。若 timeout/失败，冻结该结果、收集有限诊断和测试库残留，不自动重试，不把旧 W5c7n 单项通过冒充本波通过。
- test DB 余量 0、18181 原 PID/8080 离线、`git diff --check`。本目录 audit/verification、D-waves/AOS 上下文/Prime CAS、精确提交；若超时或测试库残留，先处置仅该测试资源的安全清理，不能碰真实进程。

## 九步

1. 上位复习；2. 本方案先提交；3. 三文件/runner/环境静态预检；4. 单次有界执行；5. 正式终态/测试库/累计核验；6. 业务浏览器离线、18181 文档只读；7. 方案/结果及 no-effect 复审；8. verification/上下文/Prime/提交；9. 自动下一波。

本波不授权真实 Schedule enable、原组 ACK/closure、Store effect、商城源读取或旧 attempt 重发；230 L0/dev-org 零 canary/m1 单写不 push 均不变。

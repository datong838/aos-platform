# W5ca0｜受控刷新停在未知启动边界

1. 复习 231/230 L0、W5c9a/e/z 进程租约和 no-authority。
2. 精确方案先提交 `m1@00c70ca3`。
3. 唯一旧 PID、lease、PG/8080 和独立 `check` 全部通过零执行前检。
4. 一次 SIGTERM 精确停 PID28077，端口释放；一次后台 `serve` shell 返回 0，但无新进程/监听/preflight 且日志 0B。依据停止条件冻结，绝不在本波再次启动。
5. 无代码修改；W5c9y 离线 29 passed/2 子测试仅为历史基线，本波线上专项未通过，不能称累计/部署 GREEN。
6. 二次只读确认 18181/8080 均无监听，恢复 PG 唯一 Up；没有 Worker、迁移、源读取、定义运行或业务写请求。
7. 浏览器验收未开展；`/docs` 与 `/openapi.json` 因服务未启动未请求。
8. audit/verification/D-waves/AOS CAS/Prime 记录 `STOPPED_UNKNOWN_START_BOUNDARY`，不隐匿 shell 0 与实际失败的差异。
9. 下一波 W5ca1：只读诊断可靠进程托管/启动观察机制，先方案和新鲜门禁再考虑单次新尝试；原 A0-V 不重放。

230 L0 挂起、dev-org 零 canary、商城源不读、unknown 不重发/不手工 `run_definition`、m1 单写不 push。

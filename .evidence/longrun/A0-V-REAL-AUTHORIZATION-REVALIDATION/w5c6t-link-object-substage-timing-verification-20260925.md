# W5c6t Link/Object 子阶段测试专属计时验证（2026-09-25）

## 第 1/9～4/9 步：方案、透明合同、硬超时

- 上位 W5c6s 与 Link/Object/Single 原实现复习后方案 `c1d48bce` 先提交；仅测试 opt-in 探针 `dc217f9c`，无生产/DB/部署改动。
- 透明合同 `1 passed`：默认不装探针、参数/返回/异常不变；输出只有标签/秒数，无 run/ref、凭据或源行。
- 单项受 300 秒进程级硬超时，测试 exit 2、pytest wall 293.68 秒；不计通过。12 次 `single_resume_saved` 各约 1.6–3.4 秒，合计约 33 秒；`objects_execute` 110.094 秒，说明 Object 内除 Single 恢复外仍约 77 秒；`links_execute` 198.614 秒，说明 Link Object 后仍约 89 秒；`retirement_execute` 到中断 263.731 秒、`completion_complete` 269.205 秒，`completion_finish` 未进入。中断栈在 canonical JSON 只能指示采样位置。一次性测试库自动清理。

## 第 5/9～7/9 步：回归、浏览器与一致性

- 旧三模块排除长时项 `17 passed, 1 deselected`（含探针合同）；安全累计 `112 passed`；长时项仍无正式终态，不能宣称 17/17。测试 PG 已停。
- 浏览器只读 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`，待同步写操作 1 未冲刷。真实门 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、12 原 Run running、stalled Receipt 0、`closureAuthorized=false`。
- 复审：多层反复 current/准备/投影存在累积成本迹象，但尚未测出每项调用次数/热函数，不能据此删除校验或修改生产；测试 opt-in 不改变授权/事务/失败注入。

## 第 8/9～9/9 步：上下文与下一波

- verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回；提交见 docs context61。
- 下一波 W5c6u：先方案，审计 Object/Link/Retirement 重复 current/哈希调用图与安全必要性；可用测试专属统计而不重复长跑，找到可证明的最小优化前不改生产。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。

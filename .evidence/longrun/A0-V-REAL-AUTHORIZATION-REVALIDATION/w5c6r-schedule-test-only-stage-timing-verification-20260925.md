# W5c6r 旧 Schedule 单项测试专属阶段计时验证（2026-09-25）

## 第 1/9～4/9 步：方案、透明探针与定位

- 上位 W5c6p/q、Runtime `execute` 三阶段复习后方案 `e8af812c` 先提交；测试文件最小实现 `160e385a`，生产代码/DB schema/部署不改。
- 仅 `AOS_TEST_SCHEDULE_TIMING=1` 安装透明 wrapper，输出阶段名/单调秒数，不输出参数、租户行或凭据；默认路径原样。合同测试证明默认不安装、参数/返回值原样、异常原样传播，`1 passed`。
- 隔离单项观察：三次 claim 分别约 0.341/0.271/0.127 秒；两次 ingress.prepare 约 6.963/3.803 秒；`completion.complete` 到中断时约 370.965 秒仍未终态。实际测试 wall time 394.58 秒（控制/轮询延迟超过计划 360 秒上限约 35 秒），exit 2，不计通过。中断栈在 canonical JSON，只说明当时位置；慢段已缩至 completion，但其内部 `_retirement.execute`、`_finish` 等仍需分开诊断。一次性数据库 SIGINT 后自动删除。

## 第 5/9～7/9 步：回归、页面与一致性

- 旧三模块排除长时项后 `17 passed, 1 deselected`（含新透明探针合同）；W5c5k–z/W5c6a–m、JDBC 与新合同累计 `112 passed`。长时项仍未计绿。测试 PG 已停。
- 浏览器只读 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`；待同步写操作 1 未冲刷。真实 closure 门 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、12 原 Run running、stalled Receipt 0、`closureAuthorized=false`。
- 方案/代码复审：只增加测试 opt-in 观察，不改变真实 Schedule/Store/Owner、测试断言或失败注入顺序。阶段完成不等于整组完成；旧 17/17 仍未获同次或单项正式终态。

## 第 8/9～9/9 步：上下文与下一波

- verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回；提交见 docs context59。
- 下一波 W5c6s：先计划，沿测试专属 opt-in 进一步拆 `completion.complete` 的 retirement execute 与 finish/Owner 子段，采用明确可执行的硬超时；拿根因证据后才讨论最小优化。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。

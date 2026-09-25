# W5c6s Completion 内部测试专属计时验证（2026-09-25）

## 第 1/9～4/9 步：方案、透明探针与硬超时

- 复习 W5c6r 与 Completion/Retirement/Link 原代码，方案 `69cfd7d4` 先提交。仅测试文件扩展 opt-in 探针，代码 `a7057fd6`；不改生产、DB schema、部署或断言。
- 透明合同 `1 passed`，默认无探针；参数/返回/异常原样。进程级控制器 300 秒后发 SIGINT，测试 exit 2，pytest 报 293.36 秒；没有把中途阶段结果计为测试通过。一次性测试库自动清理。
- 计时：claim 0.199/0.166/0.147 秒，ingress.prepare 7.778/3.629 秒；`links_execute` 在中断时 241.289 秒，包裹它的 `retirement_execute` 261.140 秒、`completion_complete` 267.143 秒。`completion_finish` 未进入。由此确定前约 4 分钟主耗时在 Link executor 内，尚未区分其 12 Object 执行与 Link 自身；SIGINT 栈在 JSON decode，不能单凭栈判根因。

## 第 5/9～7/9 步：回归、浏览器与一致性

- 旧三模块排除长时项 `17 passed, 1 deselected`（含透明探针合同）；安全累计 `112 passed`。长时项仍未终态，17/17 不绿。测试 PG 已停。
- 浏览器只读 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`，待同步写操作 1 未冲刷。真实门 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、12 原 Run running、stalled Receipt 0、`closureAuthorized=false`。
- 方案/代码复审：硬超时只针对隔离测试进程，不扩大真实 A0-V deadline；只输出标签/秒数，无参数/源行；没有用“进度”替代正式终态。

## 第 8/9～9/9 步：上下文与下一波

- verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回；提交见 docs context60。
- 下一波 W5c6t：先计划，将 Link 的 `_objects.execute` 和 Link preparation/Store/projector 分段定位，随后才决定是否需改生产热路径；正式 closure 始终 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。

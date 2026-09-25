# W5c6v Current 重读聚合计时验证（2026-09-25）

## 第 1/9～4/9 步：方案和最小实现

- 复习 W5c6u 调用图与 Object/Link/Retirement 跨 Store 提交边界；先提交方案 `5da5f0ea`。
- 仅改测试专属 `AOS_TEST_SCHEDULE_TIMING=1` 探针 `13034577`：四个 journal current 方法聚合次数/单调耗时；Completion 外层 `finally` 一次性打印标签、次数、秒数。默认未启用零包装，参数/返回/异常透明，不输出业务数据；生产/DB/部署无改动。
- 透明性专项 `1 passed`，含原异常传播。

## 第 5/9 步：累计与长时测量

- W5c5k–z/W5c6a–v、JDBC、探针合同累计 `115 passed`；旧 Schedule 非长时 `17 passed, 1 deselected`。
- 长时原组单项隔离 PG、300 秒外部硬上限触发，SIGINT 后退出码 2、`KeyboardInterrupt`，**未过正式终态，不计 GREEN**；临时 `aos_test_%` 库读回为空。
- 本次输出：Object `read_current` 13 次、总 55.338 秒；Object `run_current` 1 次、12.053 秒；Link `read_current` 6 次、73.614 秒；Retire `read_current` 在中断前 2 次、45.909 秒。外层 Object 96.296 秒、Link 179.533 秒、Retire 269.104 秒、Completion 274.152 秒。计时含测试环境/事务等待及探针开销，非生产 SLA；Retire 样本被硬中断截断。

## 第 6/9～7/9 步：浏览器、真实门、复审

- 浏览器只读 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`，运行状态 `数据组已停用`；待同步写操作 1 未冲刷，未保存/运行。
- 真实门 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`automaticAction=false`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格时钟须晚于 `2026-09-25T20:00:04.800482+00:00`，且 Host 全机器拓扑等缺口仍在。
- 聚合证实 journal current 是测量热区，但不能证明缓存/删除安全。Object 逐成员重读与 Link/Retire 跨独立 Store 提交重读须保留；下一波先拆分 journal 内部 canonical/DB/校验耗时，再判断同事务等价候选。测试 PG 已停。

## 第 8/9～9/9 步：记忆与下一波

- 本文件提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回；提交见 docs context63。
- 下一波 W5c6w：先方案，只做最热 journal 内部测试专属分段计时与合同；不改真实执行路径，真实闭环仍 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。

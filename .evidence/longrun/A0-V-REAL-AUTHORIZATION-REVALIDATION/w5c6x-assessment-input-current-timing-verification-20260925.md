# W5c6x Assessment/Input Current 实际分支计时验证（2026-09-25）

## 第 1/9～4/9 步：方案、实现、专项

- 复习 W5c6u–w、Assessment/Input/Policy/Group current 原实现；方案 `eb31c190` 先提交。
- 仅测试专属探针 `a2737c6a`：Object/Link/Retire 的 Assessment `_run`、Input `_run`/`_load`、Policy `_load`、Group `run_current` 聚合次数/inclusive 单调耗时；默认关闭、参数/返回/异常透明、不输出业务内容。生产/DB/部署零改。
- 透明性专项 `1 passed`。

## 第 5/9 步：累计与有界测量

- W5c5k–z/W5c6a–x、JDBC、探针合同累计 `115 passed`；旧 Schedule 非长时 `17 passed, 1 deselected`。
- 长时原组单项隔离 PG、300 秒硬上限触发，SIGINT 后退出码 2、`KeyboardInterrupt`，**未过正式终态，不计 GREEN**；临时 `aos_test_%` 库读回为空。
- 本次 Object：Assessment/Input `_run` 各 15 次/69.427 秒，Input `_load` 30 次/61.376 秒，Policy `_load` 43 次/0.024 秒，Group `run_current` 45 次/80.140 秒。
- Link：Assessment/Input `_run` 各 14 次/112.301 秒，Input `_load` 28 次/64.709 秒，Policy `_load` 35 次/0.026 秒，Group `run_current` 42 次/123.251 秒。
- Retire：Assessment/Input `_run` 各 17 次/258.640 秒，Input `_load` 32 次/77.511 秒，Policy `_load` 44 次/0.028 秒，Group `run_current` 49 次/271.847 秒；本段被硬中断截断。Group/Assessment/Input 均嵌套 inclusive，不可相加为总耗时，也非生产 SLA。

## 第 6/9～7/9 步：浏览器、真实门、复审

- 浏览器只读 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`，运行状态 `数据组已停用`；待同步写操作 1 未冲刷，未保存/运行。
- 真实门 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`automaticAction=false`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格时钟须晚于 `2026-09-25T20:00:04.800482+00:00`，Host 全机器拓扑缺口仍在。
- Policy `_load` 在此次测试仅毫秒级；Input `_load` 两次/Assessment 且循环 12 parent，是下一波更窄分段候选。不能把嵌套 Group inclusive 当独立 DB 等待，也不能删 current。测试 PG 已停。

## 第 8/9～9/9 步：记忆与下一波

- 本文件提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回；提交见 docs context65。
- 下一波 W5c6y：先方案，仅测试专属拆 Input `_load` 的 claim/read parent/hash/DB 子段；真实 closure 仍 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。

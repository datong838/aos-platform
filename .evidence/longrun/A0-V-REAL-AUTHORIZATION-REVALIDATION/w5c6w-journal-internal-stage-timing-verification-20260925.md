# W5c6w Journal 内部分段计时验证（2026-09-25）

## 第 1/9～4/9 步：方案、实现、专项

- 复习 W5c6u/v 与 Relationship/Link/Retirement 原调用链；方案 `c9a53ee2` 先提交。
- 仅测试专属探针 `fb0b468b`：在 Object/Link/Retire Relationship journal 的 `_run_current`、`_load`、`_restore`、Assessment `materialize_current`，以及 Link/Retire `_operate` 做次数/inclusive 单调耗时聚合；默认关闭，参数/返回/异常不变，不输出业务内容。生产/DB/部署零改。
- 透明性专项 `1 passed`；静态 `_restore` 实例包装合同通过。`_run_current`/`_operate` 嵌套 inclusive 总数不能相加。

## 第 5/9 步：累计与有界测量

- W5c5k–z/W5c6a–w、JDBC、探针合同累计 `115 passed`；旧 Schedule 非长时 `17 passed, 1 deselected`。
- 长时原组单项隔离 PG、300 秒硬上限触发，SIGINT 后退出码 2、`KeyboardInterrupt`，**未过正式终态，不计 GREEN**；临时 `aos_test_%` 库读回为空。
- 本次 Object journal：`_run_current` 15 次/67.941 秒，`_load` 14 次/0.014 秒，`_restore` 13 次/0.001 秒，`materialize_current` 0 次。
- Link Relationship：`_run_current` 14 次/102.254 秒、`_load` 7 次/0.006 秒、`_restore` 7 次/约 0.000 秒、`materialize_current` 0；Link command `_operate` 7 次/73.863 秒。
- Retire Relationship：`_run_current` 22 次/268.163 秒、`_load` 8 次/0.010 秒、`_restore` 8 次/0.001 秒、`materialize_current` 0；Retire `_operate` 3 次/97.404 秒。外层 Object 95.232 秒、Link 169.180 秒、Retire 266.628 秒、Completion 272.191 秒。Retire 样本在上限处截断，所有嵌套耗时为 inclusive，非生产 SLA。

## 第 6/9～7/9 步：浏览器与复审

- 浏览器只读 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`，运行状态 `数据组已停用`；待同步写操作 1 未冲刷，未保存/运行。
- 真实门 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`automaticAction=false`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格时钟须晚于 `2026-09-25T20:00:04.800482+00:00`，Host 全机器拓扑缺口仍在。
- `_load`/`_restore` 仅毫秒级，不能归为热因；当前测试走 Assessment `_run`/Input `run_current`，所以 `materialize_current=0` 不等于 Assessment 零成本。下一波沿实际调用链细分 Assessment `_run`、Input current、policy load/哈希；绝不删跨提交重读。测试 PG 已停。

## 第 8/9～9/9 步：记忆与下一波

- 本文件提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回；提交见 docs context64。
- 下一波 W5c6x：先方案，仅对实际 Assessment/Input current 测试专属分段计时；真实 closure 仍 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。

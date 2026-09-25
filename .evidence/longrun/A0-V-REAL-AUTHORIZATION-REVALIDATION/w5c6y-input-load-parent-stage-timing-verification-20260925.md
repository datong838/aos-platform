# W5c6y Input `_load` Parent 子段计时验证（2026-09-25）

## 第 1/9～4/9 步：方案、实现、专项

- 复习 W5c6u–x 与 InputOwner `_load`、GroupClaim、`_bound_parent` 原调用链；方案 `7c5b2ff5` 先提交。
- 仅测试专属探针 `a1f56034`：三条 Input Owner 的 GroupClaim `read_current`/`read_completed_current`，以及 InputOwner 模块 `_bound_parent`/`_digest` 聚合次数和单调耗时；默认关闭、参数/返回/异常透明、不输出业务内容。生产/DB/部署零改。
- 透明性专项 `1 passed`。

## 第 5/9 步：累计与有界测量

- W5c5k–z/W5c6a–y、JDBC、探针合同累计 `115 passed`；旧 Schedule 非长时 `17 passed, 1 deselected`。
- 长时原组单项隔离 PG、300 秒硬上限触发，SIGINT 后退出码 2、`KeyboardInterrupt`，**未过正式终态，不计 GREEN**；临时 `aos_test_%` 库读回为空。
- `_bound_parent` 跨所有 Input 调用合计 1357 次/172.268 秒；InputOwner 模块 `_digest` 1470 次/0.057 秒。该全局合计包含嵌套层，不能归给单个 Object/Link/Retire。
- Object/Link/Retire GroupClaim `read_current` 分别 30 次/9.579 秒、28 次/9.775 秒、56 次/16.427 秒；`read_completed_current` 各 0。三链 Input `_load` 分别 30 次/55.942 秒、28 次/58.259 秒、56 次/94.059 秒；本次 Retire 被中断截断。哈希不是热因，`_bound_parent` 是明确热点，但不构成缓存/删除授权。

## 第 6/9～7/9 步：浏览器、真实门、复审

- 浏览器只读 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`，运行状态 `数据组已停用`；待同步写操作 1 未冲刷，未保存/运行。
- 真实门 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`automaticAction=false`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格时钟须晚于 `2026-09-25T20:00:04.800482+00:00`，Host 全机器拓扑缺口仍在。
- `_bound_parent` 热点横跨每次 Input current 与完整 12 成员读回。下一波先审其安全契约与 1357 次来源，区分跨事务必需与同事务重复；不能凭测试内累计时长修改生产。测试 PG 已停。

## 第 8/9～9/9 步：记忆与下一波

- 本文件提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回；提交见 docs context66。
- 下一波 W5c6z：先方案，对 `_bound_parent`/InputOwner 静态调用边界和重复来源审计，必要时补无效应合同；真实 closure 仍 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。

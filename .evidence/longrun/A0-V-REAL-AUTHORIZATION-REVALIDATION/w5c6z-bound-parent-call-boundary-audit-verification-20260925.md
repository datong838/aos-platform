# W5c6z Bound Parent 调用边界安全审计验证（2026-09-25）

## 第 1/9～4/9 步：方案与无效应合同

- 复习 W5c6u–y、InputOwner `_run`/`_load` 与 `_bound_parent` 原实现；方案 `b3bf3a4d` 先提交。
- 仅新增静态无效应合同 `17f88800`，3 passed，锁定 callback 前后各 `_load`、每次 `_load` 遍历 12 成员并调用 `_bound_parent`、后者先读保存 parent 再核验 running schedule。生产/DB/部署零改。
- W5c6y 计数对账：Input `_load` 三链 30+28+56=114 次，若全部完成则 `114×12=1368` 次 parent；300 秒硬中断前观测 1357 次，相差 11 次。该差额符合中断截断，**不是漏读 bug 证明**。InputOwner 模块包装的计数没有混入其他模块各自导入的 `_bound_parent`。

## 第 5/9～7/9 步：回归、浏览器、复审

- W5c5k–z/W5c6a–z、JDBC、探针合同累计 `118 passed`；本波无运行路径变化，不重复长时单项，前波 W5c6y 仍未终态。测试 PG 已停。
- 浏览器只读 A0-V Canonical 首装 `已配置 · 已停用 · 版本 4`，运行状态 `数据组已停用`；待同步写操作 1 未冲刷，未保存/运行。
- 真实门 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`，`automaticAction=false`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格时钟须晚于 `2026-09-25T20:00:04.800482+00:00`，Host 全机器拓扑缺口仍在。
- callback 前后重读与每成员 schedule 绑定是既有一致性/授权机制；任何缓存或合并必须证明 callback 期间原始保存数据、数据库时钟、权限和每成员 running binding 均等价，且失败模式不弱化。本波没有此证明，不提出生产删减。

## 第 8/9～9/9 步：记忆与下一波

- 本文件提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立记忆并读回；提交见 docs context67。
- 下一波 W5c7a：先方案，优先重新审视真实 Host 全机器拓扑/closure 前置缺口，若无法建立可信 fleet 清单则只做无效应门与证据；真实 closure 不越权。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。

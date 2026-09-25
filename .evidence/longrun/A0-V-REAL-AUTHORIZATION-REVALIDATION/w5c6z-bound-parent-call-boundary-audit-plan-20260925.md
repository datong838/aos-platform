# W5c6z Bound Parent 调用边界安全审计方案（2026-09-25）

上位 W5c6y：隔离长时测试 `_bound_parent` 1357 次/172.268 秒，Input `_load` 三链 30+28+56=114 次；每次 `_load` 对 12 成员执行 `_bound_parent`，理论完整数 1368，中断截断为 1357，差 11 次与中断位置相符。不能把 1357 次称为无意义重复。

## 文件级九步

1. 复习 W5c6u–y、InputOwner `_run`/`_load`、`_bound_parent`、original schedule verification 与 A0-V no-effect 边界。
2. 本方案先提交。仅新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c6z_bound_parent_call_boundary_audit.py` 静态无效应合同及 verification；生产/DB/部署零改。
3. 合同锁定：Input `_run` 对 callback 前后各 `_load`，每次 `_load` 遍历绑定的 12 成员并调用 `_bound_parent`；`_bound_parent` 先读保存 parent，再验证 running schedule binding。这是防 callback 期间权威/输入漂移的机制，不可未经等价性证明删除。
4. 对 W5c6y 计数做算术对账，并声明硬中断截断，不能用差 11 证明漏读 bug；区分 InputOwner 引用与其他模块的 `_bound_parent` 引用。
5. 静态合同专项和 W5c5k–W5c6z/JDBC 安全累计回归；本波不重复长时单项，因为无运行路径变化且前波上限诊断已充分。
6. 浏览器只读 rev4 停用及真实 closure 拒绝，不保存/运行/冲刷队列。
7. 复审方案/代码一致性：可优化候选需证明 callback 不变更 original saved parent/current grant、数据库时钟和权限不弱化，并给出失败时精确等价性；本波不提出生产删减。
8. verification 后 CAS 更新 docs/AOS 跨对话上下文与 Prime 独立记忆并读回。
9. 下一波 W5c7a：先方案，回到最重要的真实 Host 全机器拓扑/closure 前置缺口，或对 `_bound_parent` 读/验证两子段作有限测试专属计时；继续 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 仅零 canary。

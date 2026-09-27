# W5CB4 D01 完整包选择 Owner B 子波验证（2026-09-27）

## 结果与边界

按 `w5cb4-d01-complete-packet-selection-plan-20260927.md` 的 B 子波，新增 a0v_107 append-only proposal、approval、revocation 历史与受检写函数，Runtime 对三张底表仅有 SELECT。Python `D01SourceSelectionStore` 在原 HostTransaction 中做原 Plan/Task/Run/SourceSelection 前置核验、单一提案、独立 checker 批准、撤销及每阶段独立行/Receipt 读回；自身不提交事务。相同 key/payload 原 Receipt 回放，漂移冲突；maker 不能自批，同一事务不能提案并批准。

隔离 PG 测试先 RED（缺三表／函数），随后 8 passed：RLS FORCE、不可变触发器、底表直写拒绝、受检写函数、独立 checker 事务、撤销、同键幂等与漂移、跨租户零读、无权撤销拒绝。Python Store 测试先 RED（模块缺失），随后 4 passed：scope/actor 写前拒绝、原批准 Plan input 集合漂移拒绝、写后独立读回、maker 自批拒绝、审批和撤销均不重发提案。专项合计 **12 passed, 7 warnings**。

D01 Atomic／Issuer／合同／Store／隔离 PG／原链 Task／AgentRun 邻接累计命令核准测试文件名后为 **82 passed, 7 warnings**；第一次累计命令误写不存在的测试文件，退出 4、未运行，不计成功。`py_compile` 与 `git diff --check` 通过。浏览器在本子波无注册入口；本轮 8080 和 8434 有监听，18181 无监听，8434 根路径 200；不把 UI 预览计为 D01 Owner 使用成功。

## 方案/代码一致性复审和未完门

三张表是引用/决策历史，不存商城源数据、Evidence 正文或 Secret；迁移 downgrade 显式拒绝删除历史。写函数要求 serializable、同租户、原 Plan/Run/Task 和 membership；approval 要求当前批准 Plan 的独立 checker。Python 读回重算提案 canonical hash；但 SQL 直接调用者提供的提案 hash 并非数据库独立重算，因此 **C 的运行时读取必须继续重算并 fail closed**，此 B 不能作为 Host 准入。审批/撤销 Receipt 在 SQL 计算并独立行读回。

当前实例未迁移 a0v_107，当前安全预览仍按最近独立证据的 a0v_106 运行；本波仅在隔离测试库建表与写入测试行，没有读取商城源表、没有开放 Host/Provider、没有人工 `run_definition`、没有重放原 12 Run。现有工作树中 `test_ecommerce_content_review_pending_pg.py` 及两份 w5c8i 测试文件非本波修改，不纳入提交。

**下一波 C**：先方案细化 `read_current` 的同事务、当前批准、撤销、原 Owner/Grant/cutoff 和重复/未知边界，RED 后只让 D01 Atomic 消费 exact 批准包，隔离 PG 证实正负例；不得把本波隔离库通过写成当前实例自然首链完成。

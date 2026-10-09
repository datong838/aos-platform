# 可信结束协议草案与下一 RED

安装边界原生 READ ONLY 核查通过：现有 verifier 的具体 C 符号、库引用、Owner、ACL 与配置原样绑定于 trust-audit.json。runtime/issuer/policy publisher 均无 Source 私有 schema CREATE、pending 表写权或私有 pending guard EXECUTE；不将这些目录事实称作实际越权攻击已跑过。现有 verifier 是否注册未知 callback 不由 pg_proc 推断。

候选协议必须由独立受控安装建立不可被普通角色选择或移除的事务门，不能在 Python 返回前检查后允许 caller 任意 COMMIT，也不能仅通过 current_query 字符串判断结束。签发/联合 finalize 的成功事实需要明确注册同一 native top xid/pid/session 和已核签名原事实的 obligation；每条 deadline 取原 Source/JWT/approval/budget 上界的最小值，不能扩大 TTL。

子事务要求：ROLLBACK TO 移除该子事务新增 obligation；RELEASE 合并到父状态，不能消失或更换原引用；整个 ABORT 清空本事务状态。PREPARE 必须在未取得完整两阶段合同前明确拒绝有 obligation 的事务。COMMIT/END、AND CHAIN、simple/extended protocol、事务内多语句及显式提前 SET CONSTRAINTS 都不能绕过注册 obligation。任何修改安装、可信 Owner 或 verifier hash 必须使 currentness 失效；不接受调用者提交的身份断言替代原 session。

最后可回滚检查必须在所有原必要锁、读取与 deferred/portal 工作之后执行，且不能有随后未经审核的其他 callback 读取或等待。即使这些条件证明，普通 PRE_COMMIT 仍先于原 WAL 持久化，不能兑现严格“持久化/确认完成未过期”。该需求不被本草案改写；数据库内核或外部新协议属于另行完整设计范围，本波不安装或改内核。

下一 RED 必须从原签名 Source 正常流程产生原 obligation，单次已登记新尝试；覆盖正常提交、检查前跨期、后置等锁跨期、提前 SET、PREPARE、子回滚/子提交、AND CHAIN 与未知断联。不得只用合成 callback 代替真实 Source 身份，不回放现有已提交过期反例。新的 test-only 安装实验如实施，须先独立精确资源 Task/Lease及方案；当前只有只读调查授权，不伪称原型已实现。

独立安全候选仍是已登记 typed Model/Route Owner/签名来源、原预算与 unique Intent 接线；严格截止 RED 不扩大为长期 Goal 停工。当前 Task 保持 ACTIVE，后续完善确切最小实现范围和可验证失败语义。

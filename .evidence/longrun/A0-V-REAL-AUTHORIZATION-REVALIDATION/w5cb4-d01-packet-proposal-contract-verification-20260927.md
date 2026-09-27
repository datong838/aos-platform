# W5CB4 D01 完整包候选合同 A 子波（2026-09-27）

## 结果与未完成门

依据 `w5cb4-d01-complete-packet-selection-plan-20260927.md`，新增 `D01SourceSelectionProposal`：只持有同租户 TaskRun/Plan/原 SourceSelection exact 引用、Plan hash、完整 `D01SourcePacket`、提案人和时点；同 Run/Plan 的选择 ID 稳定。空/错资源类型、缺修订、错原选择类型、无提案人、晚于提案时点的 cutoff 均拒绝。该对象明确没有 `approved_by`，不能自行授权任何 AgentRun。

RED：新测试在目标模块缺失时 collection ERROR；实现最小合同后专项 6 passed。累计 D01/原链/Task/AgentRun 70 passed、7 既有 warnings。此切片无数据库 migration、无提案写入/审批/撤销/Receipt/Host 注册；所以**完整 packet 选择权威仍未建立**，A1 自然 D01 未通过。

方案/代码复审：合同通过原 `D01SourcePacket` 检查 exact 包形态；Stable ID 故意只按 tenant+TaskRun+Plan 计算，使不同 payload 无法绕过后续同键冲突门。实际同键冲突/独立 checker/CAS/RLS/撤销须由 B/C 子波隔离 PG 证明。当前安全预览不接该合同，浏览器验收不适用；18181/Host/Provider 保持关闭。当前用户既有工作树测试改动未触及。

下一子波 B：先给 proposal→独立 checker approval→revocation 的 append-only 表、Receipt 与同租户约束写 RED，隔离 PG 验证两阶段、重复 key 和并发，再做最小 Owner；不得迁移当前实例或把候选合同当作批准。

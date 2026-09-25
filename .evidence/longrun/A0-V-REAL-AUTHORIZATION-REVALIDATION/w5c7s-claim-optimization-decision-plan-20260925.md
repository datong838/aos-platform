# W5c7s Claim 优化可行性裁决与主线回归方案（2026-09-25）

## 上位与决策缘由

231/231-5 以自然运行、当前授权、真实 Receipt/业务产物为准。W5c7n 旧 12-source 长例 1 passed/单调 794.823 秒，不再是 900 秒预算内的测试阻断；W5c7l–r 收敛了 ClaimLoop、历史行、Schedule/Run/Installation 锁和后置时间窗，但未证明生产 claim 复用的 completed/saved recovery、派生权限/预算/发布依赖与错误语义等价。真实 A0-V closure 仍缺全机 Host topology、新鲜 Owner、独立方案/key。

## 文件级九步

1. 复习 231/231-5、W5c7l–r、`PipelineSnapshotGroupInputOwner._run/_run_recovery/_load`、GroupClaim/ControlledIngressJournal completed 与原 PG 负例。
2. 本方案先提交；本波只新增综合裁决审计和 verification，不改生产/测试代码、DB、索引或部署。
3. 列出 running/completed/saved recovery 三路径的 claim/parent/receipt/时间窗与异常行为；区分 W5c7o–r 已证与未证。尤其不把原始 running 的同事务锁证据外推到 completed/recovery。
4. 对照原 PG 目标跑 completed 只读/未完成成员拒绝/当前发布变动与 saved recovery 当前权限复核，确保没有误读现有行为。
5. 跑相关短累计并读回真实 closure gate/测试临时库；用后停隔离 PG。旧长例不重复。
6. 浏览器只读 rev4 disabled，不保存/运行/冲刷队列。
7. 裁决：若无完整等价证明且长例已在预算内 GREEN，明确**延期生产性能优化、保留全部重验**；下一波回归 Host topology/Owner/closure 主线，不把测试 GREEN 当业务完成。
8. verification 提交后 CAS 更新 docs/AOS 上下文与 Prime 独立长记忆并读回。
9. 下一波 W5c7t：先方案，围绕全机 Host universe/worker coverage 的真实可部署控制面来源做文件级实现清单与 fail-closed 接入前提；不得凭本地进程/DB session 推断完整 topology 或启动真实 closure。

旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push。

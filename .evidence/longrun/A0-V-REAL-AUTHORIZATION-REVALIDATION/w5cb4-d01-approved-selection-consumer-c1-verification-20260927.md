# W5CB4 D01 C1：批准选择同事务读门（2026-09-27）

依据 `w5cb4-d01-approved-selection-consumer-plan-20260927.md`，`D01SourceSelectionStore.read_current` 只按同租户 exact TaskRun/Plan 读一个不可变提案及其独立批准、无撤销，再验证提案 canonical hash、原 Task/Plan/Run 现时状态、批准 checker、原 SourceSelection、获批 portrait 引用集合、审批时序和 Receipt。`NaturalD01AtomicCoordinator` 在原 `AnalysisContinuationOrigin.run_current` 的同一 serializable 事务、AgentRun Owner 写前消费该包；外部 packet 不相等即拒绝。当前 Method/Query/Bundle/Grant 仍由原 `require_current_d01_sources_in_transaction` 同事务校验，未删旧安全门。

RED：先新增无批准／已撤销测试，缺 `read_current` 失败 2；Atomic 新负例在未接选择 Store 时失败 3。GREEN：Python 选择读门正负 7 项、Atomic 与 Store 邻接 26 项；真实隔离 PG 一次提案→独立 checker 批准→Runtime 只读同事务读取→撤销后拒绝通过。测试期间发现 `SELECT FOR SHARE` 对只具 SELECT 的 Runtime 被 PostgreSQL 拒绝；决策表本身 append-only 且事务 serializable，改为纯 SELECT 后隔离 PG 正向通过。D01/原链/Task/AgentRun 累计 **92 passed, 7 warnings**；`py_compile` 和 `git diff --check` 通过。

浏览器适用性：新读门未注册 Host 或 UI；8434 安全预览根路径 200，18181 无监听，均不是 D01 自然运行证据。当前库最近独立身份仍为 a0v_106，本子波没有迁移它、没有商城源读取、没有 Provider 调用、没有人工 `run_definition` 或旧 12 Run 重放。

一致性与剩余风险：C1 隔离 PG 证明真实两阶段决策的读回，但尚未在**同一个真实隔离 PG 测试**贯通原 AnalysisContinuationOrigin、现时 Method/Query/Bundle/Grant 与 AIP AgentRun Owner Receipt；Atomic Owner 零写和正向接线目前是独立单元测试。故 C 总门不封闭，不可称首链成功；C2 必须补此联合正向及失败/未知提交边界，之后才评估 D 当前库迁移。外部 `test_ecommerce_content_review_pending_pg.py` 及 w5c8i 文件保持原样，不纳入本波提交。

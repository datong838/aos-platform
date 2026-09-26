# W5can｜第 1–3/6 步中间证据（非波次完成）

方案 `w5can-a1-atomic-d01-owner-plan-20260926.md` 已复习 231 A1、231-9 BG-02/03、栖月汇经营参谋目标及原 `AnalysisContinuationOrigin`/AIP Owner 事务边界。RED：借用事务的 Owner 方法缺失，随后来源 reader 借用事务入口缺失。GREEN：公开 `AipAgentRunService.create` 仍自有连接提交；新增 `create_in_transaction(HostTransaction,...)` 核对事务租户、复用原锁/Receipt/资产检查但不提交；D01 来源 reader 可在相同 `HostTransaction` 上核验成员、marking、DB 时钟与来源包。隔离 PG 验证新 AgentRun 与 Receipt 随外层异常回滚，且原公开 create 正例仍过。

专项/累计相关测试：D01 issuer、stage discovery、portrait inputs/worker、AIP6 capability handoff，63 passed、3 skipped；`py_compile` 与 `git diff --check` 通过。AIP AgentRun HTTP API 套件另因本地 `.aos-recovery-20260913/state` 不存在而 5 项 setup error，未记为全绿；不为此修改应用权限或伪造 allowlist root。上波原链 PG fixture 的 2 项 chronology error 待查。

尚未完成：`AnalysisContinuationOrigin` 回调内组合当前 TaskTimeline、exact D01 packet 和 Owner 无提交写；原 Receipt/当前 Plan/cutoff 绑定；同事务独立 Receipt 回读；隔离 PG 撤权/重复/未知提交；Host/浏览器真实自然验收。**当前不得注册 D01 Host worker 或调用 Provider。** 下一步继续 W5can 第 3/6 步实现 coordinator，先 RED 后最小改动；若当前原链接口不支持，同步更新方案并 fail closed。旧 12 Run 不重播、不读商城源，230 L0 挂起，dev-org 仅零 canary。

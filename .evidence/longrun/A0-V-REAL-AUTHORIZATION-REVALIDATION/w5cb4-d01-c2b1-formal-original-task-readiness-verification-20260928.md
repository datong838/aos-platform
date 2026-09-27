# W5CB4 D01 C2b1：正式原 Task/Plan 准入负向证据（2026-09-28）

## 结论

**仅负向前置通过，D01 正向仍未通过。** 新增隔离 PG 测试在真实 `AnalysisContinuationOrigin` 下读到已批准三阶段正式 Plan，三步均 `inputRefs=[inputSchemaRef]`；原 TaskRun 为 `paused`。从无内部会话的普通 AIP Task Owner 请求 resume，明确返回 `ANALYSIS_BOOTSTRAP_CONTINUATION_AUTHORITY_REQUIRED` 且仍保持 paused，不能用直写状态绕门。

进一步复核真实数据恢复测试：无 fulfillment 的 `_AnalysisDataResumeSession.resume()` 正式拒绝；快照恢复正例 `test_original_task_and_domain_resume_once_under_snapshot_session` 在自身注释里明确使用 named snapshot stage fixture，只证明 Task/Domain 状态 Owner 合成能力，不能称真实十二来源/当前实例准入。原完整 C2b 联合正向仍未得到。

## 验证与影响

- 新增测试初次收集因漏导入间接 fixture 报 ERROR，修正导入后首次断言因 approval status 为 str 而非 Enum 失败；校正断言后新测试通过。真实原链、数据恢复缺失、快照状态 Owner 3 项专项 `3 passed, 7 warnings`；D01/原链/Task/Portrait/AIP Owner 相邻十文件累计 `109 passed, 7 warnings`。这些是控制面测试，不是自然 D01 业务成功。
- 只新增 `test_ecommerce_analyst_d01_formal_ready_pg.py` 负向守门；生产代码不改。C2a 后的 8080/8434 安全预览及浏览器禁入已经验证，本波无 UI 改动；当前库仍 a0v_106，a0v_107 未迁移，18181/Host/worker/Provider 仍关。
- C2b1 正向待真实 current fulfillment/readiness 和合法专用恢复会话；C2b 全链待唯一 AgentRun Owner Receipt。**下一波转 BG-00 首链最小合法绑定/配置或独立 D01 产品审批入口，不等待失败快照逐行修复。** 不读商城源、不碰旧 12 Run、不删卷。

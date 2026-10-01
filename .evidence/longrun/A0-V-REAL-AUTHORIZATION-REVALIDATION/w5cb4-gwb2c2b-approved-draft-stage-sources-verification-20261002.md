# GW-b-2c2b 获批历史 draft 与阶段来源受限复验

2026-10-02 约 07:00 CST。基线 `AOS-001103` / `m1 b68a713b`。复习 231-5 §9、231-9 原增长链和 GW-b 清单；文件级方案见 `w5cb4-gwb-accepted-stage-handoff-plan-20261002.md`。

隔离 PG RED：获批 successor 后直接调用原 `read_stage_review_eval_source_authority`，因 draft 非当前报 `current growth draft unavailable`；新显式参数首次运行因接口不支持 `approved_stage_source` 而失败（pytest exit 1）。最小实现仅在 solution-design Handoff 使用原 `read_approved_stage_handoff_source` 的历史 draft，核 Decision、获批 successor priorRef、draft exact hash/revision/租户；原人工评审默认仍要求当前 draft。宿主在当前 Occurrence/Case、原 Owner、原 Analysis 后顺序读阶段 Runtime、责任 reviewer 与 Eval 来源，`execute` 仍拒绝。

隔离 PG 正反证：显式获批来源能越过 draft current 检查，随后因 fixture 缺原 Decision/Insight 报 `current analyst exact source unavailable`；篡改 draft hash 被拒；缺原 TaskRun 报 `stage review run unavailable`。九文件相邻回归 134 passed、7 warnings、退出 0。`py_compile`/精确 diff check 提交前回读。

局限：本 fixture 的 StageDecision 为测试发布，不是真人授权；原 Case/Occurrence/Analysis/Stage/Eval/permission 完整生产者 PG 正向、Eval 验证执行器、Task/Brief v3、内容生成/评审和当前实例自然首链仍未证明。当前真实库只读，Host/worker/Provider 关闭，无商城源读取、手工 Run 或旧 12 Run 重放。

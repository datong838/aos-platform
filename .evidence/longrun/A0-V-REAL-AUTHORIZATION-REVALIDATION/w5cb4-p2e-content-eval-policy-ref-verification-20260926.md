# W5CB4 P2e｜内容 Eval 策略引用精确绑定验证（代码门，非生产激活）

## 基线与范围

- m1 单写者；方案先行提交 `ceb77e3b`。本段只处理正式内容 Eval 的 `gatePolicyRef` 类型及其与冻结 EvalContract 的 exact 绑定，不注册 Suite/Contract、不中途运行生产 Eval、不启 worker/Provider、不读商城源、不触碰旧 12 Run。
- 上位依据：`231-5` 的来源/评审/恢复边界、`231-9` BG-04、栖月汇产品方案与 W5CB4 计划 P2a/P2c/P2e。内容可读 Artifact/生成 StepRun 已由此前代码门提供，正式内容政策尚未在实例中配置。
- 原约束仅承认 `MediaGatePolicyRevision`；P2a 的 `fixture-policy` 是测试夹具，不能证明内容策略权威。内容合同的 `gate_policy` 本已受冻结合同 `content_hash` 保护；以同一 exact `EvalContractRevision` 引用它，不新增审批源。

## RED → 最小修复 → GREEN

1. 先把隔离内容 Eval 测试改为 exact 内容合同策略 ref；RED：`EvalGatePolicyRef` 拒绝 `EvalContractRevision`。模型扩展后又 RED：克隆测试库原 `ck_eval_run_gate_policy_w7_004` 拒绝该 ref。两层都已实际复现。
2. `aip_eval_contracts.py` 仅增加 `EvalContractRevision` 类型；`aip_eval_runner.py` 在写入 EvalRun 前要求 content 主体的策略 ref 与合同 ref 的 ID/revision/hash 相同。新 `a0v_105` 只替换 EvalRun/Report 两处 JSONB 类型约束，保留旧媒体 ref 合法性，不修改历史 `w7_004`。隔离测试库显式执行该迁移；生产 `aos_meta_head` 未迁移，不能声称生产可用。
3. `AipProductionContractStore` 内容 ReviewIssue 门和 `ContentReviewHostService` 回读门均要求报告的策略 ref 与其合同 ref 完全相同；媒体策略别名不得作为内容 EvalReport 进入人工决策。原 StepRun/Artifact/latest attempt、人类事件与 ReturnDecision 校验不放宽。
4. 正反测试：内容 Eval 精确合同策略成功产生同主体报告并建立 ReviewIssue；媒体夹具策略在 EvalRun 写前拒绝；伪媒体策略报告在 ReviewIssue/Host 门拒绝。媒体/文本原路径累计回归保持。

## 测试与残余风险

- 专项与邻近累计：`test_aip_ecommerce_content_eval_input.py`、`test_ecommerce_content_review_authority_feedback.py`、`test_aip_eval_runner.py`、文本 Eval、分析阶段 Eval/Review、ReviewIssue PG：`94 passed`。
- 业务调查 Artifact/Review 与 W7 媒体门补充测试：`15 passed, 3 errors`；3 个错误均发生在 W7 测试客户端 setup，因既有 allowlist 指向不存在的 `/Users/ddt/work/projects/ai_agent/.aos-recovery-20260913/state`，未执行到本次代码逻辑。此环境缺口不记为 GREEN，列后续受控回归；不为测试擅自重建历史恢复目录。
- 未改前端，无浏览器验收项。`git diff --check` 通过。此次只证明代码/隔离库；原 Plan 尚无 exact 内容 EvalContract，正式 Publication/ReleaseGate/Suite 与当前安装证据不足，故待办/自然闭环仍 blocked，不得造真实审批或启动生产评估。

## 下一步

继续 W5CB4 P2：在原批准 Plan 上建立受控内容 EvalContract exact 引用的设计与 RED；以当前已发布 Skill、Suite、Publication/ReleaseGate、冻结 READY 合同为硬门，再建只读待办/正式 ReviewIssue。若实例仍无合法权威，只做默认关闭代码门并明确 blocked；不从 fixture 或任意合同推断激活。

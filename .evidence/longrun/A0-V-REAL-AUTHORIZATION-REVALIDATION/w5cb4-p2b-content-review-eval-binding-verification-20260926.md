# W5CB4 P2b — 内容 ReviewIssue 与 EvalReport 同主体绑定验证

- 状态：局部代码门 GREEN；W5CB4 总波次仍未完成，未启生产、未发生人类审批或外部副作用。
- 上位计划：`w5cb4-content-review-taskrun-feedback-plan-20260926.md` P2a 第三项。前置 P2a 为 `919fa613`，只允许 exact `ecommerce_content` Artifact 成为 Eval 主体。
- RED：新增同库测试先证明公共 `create_review_issue` 仅分别校验 Artifact 和 EvalReport 存在；相同内容哈希、不同 Artifact ID 的内容可错误借用前者报告（1 failed，`DID NOT RAISE`）。
- 最小修复：`services/aos-api/aos_api/aip_production_contract_store.py` 在内容类型的 ReviewIssue 创建前核对报告的 exact subject Artifact ID/hash、原 Run、`content_generate` 最新 StepRun ID/attempt/inputHash、EvalContract 与 GatePolicy Ref 存在。其他 Artifact 类型的既有评审路径不改。
- 专项与邻接回归：`test_aip_ecommerce_content_eval_input.py`、`test_w2a_production_contract_store.py`、`test_w2b_production_contract_store.py`、`test_ecommerce_review_issue_eval_authority_pg.py`、`test_aip_text_stage_eval_subject.py`、`test_aip_text_eval_input.py` 合计 54 passed、7 个既有 warning。测试使用隔离临时数据库与 fixture，无商城源读取。
- 方案一致性：满足“只有评估了这份可读内容的正式报告才可供内容 ReviewIssue 使用”；本段不生成内容合同/政策，不替代正式人类 resolve/return 事件，不替代 TaskRun 终态。无 UI 改动，本段无需浏览器验收。
- 风险/下段：当前测试的 EvalContract/GatePolicy 仍为 fixture；需独立完成内容 Eval 激活硬门与待办 Owner，才可评估下一步人类界面。原 12 Run、230 L0 与生产 Effect 均保持原隔离边界。

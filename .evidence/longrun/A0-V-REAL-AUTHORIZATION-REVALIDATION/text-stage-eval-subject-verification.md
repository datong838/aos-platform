# 正式Eval文字产物边界验证

2026-09-11，基线caf3803b，AOS-000573。

`AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1 services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/test_aip_text_stage_eval_subject.py services/aos-api/tests/test_aip_business_investigation_eval.py -q --tb=short`

18 passed，0.62s，退出0；已有7项告警与退出JDBC logging提示。隔离PG用真实Task/Plan/Run/StepLease/Artifact Owner证明明确文本类型可进入subject核验，默认媒体拒绝文本、错hash/Run/attempt及跨租户拒绝；纯替身验证合同先解析和默认媒体仅variant规则。完整实际评测及原文读取未在此执行。

精确合同gate_policy.subjectKind允许media_variant（缺省）或agent_text_output，未知类型失败。文字要求artifact_type=agent_text_output且family_role=NULL；同租户/Run/最新StepRun/hash仍保留。方案与实现一致，不改变报告或评测执行流程，不代表文字已被实际评测。

下一波实际报告、合同有效性、阶段产物和当前人工职责联合核验，随后接产品命令。主库未改、未调用Provider，真实首链未完成。

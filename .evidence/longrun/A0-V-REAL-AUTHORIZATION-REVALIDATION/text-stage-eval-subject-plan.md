# 正式Eval文字阶段产物入口

2026-09-11，基线caf3803b，AOS-000573。沿用产品12/技术160的画像、诊断、方案人工决策，不创建第二套评测结果。

发现 AipEvalRunner 的所有subject固定要求family_role=variant，而D01-D03原始文字Artifact是agent_text_output/family_role=NULL，真实阶段Eval会失败。修改 services/aos-api/aos_api/aip_eval_runner.py：在exact frozen ready合同解析后，从contract.gate_policy.subjectKind读取明确类型；缺省/媒体沿用media_variant，新增agent_text_output，未知值拒绝。文字仅允许artifact_type=agent_text_output且family_role=NULL，仍需同租户、同Run、原始内容hash和最新exact StepRun；其他报告、合同、目标与评测执行机制不变。这个入口只验证metadata；真正评测仍须既有执行器获得正文并执行，不能凭metadata宣布通过。

新增 services/aos-api/tests/test_aip_text_stage_eval_subject.py：默认媒体保持variant约束、明确文本可通过、未声明/未知类型/跨Run/旧attempt/hash漂移拒绝，验证run入口解析合同后传入类型。优先隔离PG原始subject/StepRun表边界，执行器替身只用于检测路由、不证明真实评测完成。不迁移主库、不调用Provider、不发布。后续仍要完整Eval/产物/职责联合核验及宿主接续。

# 内部阶段决定命令验证

2026-09-11，基线25ab0531，AOS-000573。

`AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1 services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/test_ecommerce_analyst_stage_review_command.py services/aos-api/tests/test_ecommerce_analyst_stage_decision_store.py services/aos-api/tests/test_ecommerce_analyst_stage_review_authority.py services/aos-api/tests/test_ecommerce_analyst_stage_review_runtime.py services/aos-api/tests/test_ecommerce_analyst_stage_eval_report.py -q --tb=short`

46 passed，8.80s，退出0；已有7告警和退出JDBC logging提示。新命令21项：实际隔离StageDecisionOwner/Receipt保存、重放、撤销、四核验失败无写、外层回滚、过期拒绝。命令组合测试以明确替身提供编译/职责/运行/正文/Eval源；这些Reader独立实际隔离验证随本次回归运行，未声称完整全图真实业务。

来源辅助函数测试覆盖当前subject原Artifact、成功生成、Provider receipt、Skill、正文访问、当前合同/输入协议、失效gate、报告Suite与时间等拒绝；无编译记录不得任择职责。正向完整compile receipt/gate发布图仍须后续实测。

命令内部同事务，当前职责来自原compile receipt；非撤销再检查当前runtime、分析subject父链与原文、Plan精确EvalContract和报告。重放返回历史，撤销不依赖失效源，均不启动后继。与方案一致，没有HTTP装配/主库迁移/Provider调用。

关键未完成门：现有Eval循环只输入Suite样例，subject只是metadata。本命令要求subjectInputMode=text-envelope-v1；下一波实现实际正文受控输入再验证，当前不可据此宣称评测了真实产物。随后联合全图及产品入口/worker门。真实首链未完成。

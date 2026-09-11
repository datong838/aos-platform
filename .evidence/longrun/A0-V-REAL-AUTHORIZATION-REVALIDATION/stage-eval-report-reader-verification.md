# 当前阶段Eval报告核验

2026-09-11，基线bbb391ad，AOS-000573。

`AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1 services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/test_ecommerce_analyst_stage_eval_report.py services/aos-api/tests/test_aip_text_stage_eval_subject.py services/aos-api/tests/test_aip_business_investigation_eval.py -q --tb=short`

22 passed，1.46s，退出0；已有7项告警及退出JDBC logging提示。新增4项实际隔离PG测试使用正式EvalRun状态流转与Report追加：通过回读、绑定漂移/跨租户拒绝、新失败报告取代旧通过、未成功执行拒绝。不可变报告的内容损坏在读取边界替身注入，验证实际hash而非仅保存字段；未修改数据库历史报告。

调用方显式事务，FOR SHARE锁定报告/Run，原JSON与typed哈希一致，实际执行状态/时间/谱系一致，同stageAttempt最新报告。只证明报告快照；当前合同有效性、产物正文和人类职责仍需最终入口联合读取。方案一致，无自行提交，无主库改动，无真实模型评分和业务首链证明。

下一波联合合同与产物来源、当前职责，接正式阶段决定命令。真实数据连接/质量对账和首链仍未完成。

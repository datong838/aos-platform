# 阶段评审运行谱系验证

2026-09-11，基线17679e95，AOS-000573。

`AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1 services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/test_ecommerce_analyst_stage_review_runtime.py services/aos-api/tests/test_ecommerce_analyst_stage_decision.py services/aos-api/tests/test_aip_business_investigation_eval.py -q --tb=short`

41 passed，1.74s，退出0；已有7告警和退出JDBC logging提示。新增6项含实际隔离PG正式Task/Plan/Run/claim/四阶段Evidence/complete/checkpoint，覆盖三阶段成功、exact漂移/跨租户、后继开始、缺少前序；缺失checkpoint以读取边界替身模拟。观察subject是测试引用，不是真实分析产物，未做真实业务评审。

保持当前Plan/hash/批准与Task-Run状态一致；锁定Run/Task/Plan、步骤和checkpoint，检查最新Step、前序完成、后继未开始、实际input/dependency/hash、observe Evidence原body与被评subject一致。命名只在契约入口兼容已知两种方案阶段写法，实际运行核验仍逐字匹配真实Step，不改写历史exact引用。

与方案一致。只读来源，不授予人员或运行权限。当前合同、正文、职责、报告仍需最终命令联合校验；主库未改，真实首链未完成。

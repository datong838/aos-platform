# 实际文字正文输入Eval验证

2026-09-11，基线c3ce8ea0，AOS-000573。

`AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1 services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/test_aip_text_eval_input.py services/aos-api/tests/test_aip_text_stage_eval_subject.py services/aos-api/tests/test_ecommerce_analyst_stage_review_command.py -q --tb=short`

42 passed，4.46s，退出0；已有7告警及退出JDBC logging提示。新增8项，实际隔离PG安装012/013后用Task/Step/原文Artifact、EvalRegistry/Run/Report：target收到本次原文及exact引用；原文漂移、错误引用、权限不足、超2MiB时target未调用且本次Run failed无Report；原普通Eval仍成功；协议未声明拒绝，每个case输入深拷贝隔离。合同resolver为测试替身，target/judge是固定测试评分逻辑，无真实商业分析质量证明。

旧克隆有5份既有报告，断言限定本次scope/Run，不删除旧数据也不把旧报告计入本次结果。正文只来自受权Resolver并核验原始UTF8 SHA，规则仍来自原Suite。报告保持metadata/hash，不保存正文。方案一致；补改既有text subject路由测试声明新输入协议。

没有主库修改、外部Provider调用或实际商家链路。下一波正式阶段评分规则及联合全图，随后产品入口/人工决定/自动续跑。真实首链仍未完成。

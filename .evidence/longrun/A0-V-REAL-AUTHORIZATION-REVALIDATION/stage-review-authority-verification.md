# 人工阶段职责核验验证

2026-09-11，基线25a57fce，AOS-000573。

`AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1 services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/test_ecommerce_analyst_stage_review_authority.py services/aos-api/tests/test_w2b_production_contracts.py services/aos-api/tests/aip/test_aip_responsibility_template_authority.py -q --tb=short`

25 passed，1.15s，退出0，已有7告警及退出JDBC logging提示。新增8项：human空能力合法/机器空能力拒绝，真实PG AssigneeResolution和ResponsibilityPlan Owner创建冻结后读取；当前exact/actor/阶段/租户、移除成员、过期/漂移回执拒绝。创建时模板resolver为测试替身，不代表真实安装模板已具备人工槽。

发现并修正契约冲突：human解析拒绝机器能力，而职责槽原来强制非空；现在仅human允许空，机器依旧非空，既有非空列表序列化不变。测试时间取DB时钟，过期样本保持created<expires数据库约束；未放宽未来或过期授权。

只读当前职责核验，锁定head/revision/member/receipt，不自行提交；未接API、未迁移主库、未执行真实评审。与方案一致。下一波实际Eval、阶段attempt与产物来源核验，然后接产品命令。真实源连接、事实质量/对账和首链仍未完成。

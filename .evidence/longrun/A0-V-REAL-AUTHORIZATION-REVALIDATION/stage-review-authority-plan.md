# 当前人工阶段评审职责核验

2026-09-11，基线25a57fce，AOS-000573。复核231-5首链、产品12生意探究工作区和技术160第12节：画像、问题机会、方案比较都有人类决策门。

## 发现与最小修改

ResponsibilitySlot.required_capability_ids现要求至少1项，但AssigneeResolutionStore对human_principal只允许无机器能力的租户成员，二者使合法人工职责不可配置。修改 services/aos-api/aos_api/aip_production_contracts.py：列表允许空，仅human_principal允许空，其他kind维持非空约束；不改变现存非空序列化/hash，不放松解析器。

新增 services/aos-api/aos_api/ecommerce_analyst_stage_review_authority.py：显式HostTransaction/Scope，只读当前ResponsibilityPlan，FOR SHARE锁head/revision和membership/receipt；Owner回读frozen/ready/complete及真实canonicalhash。阶段固定职责槽analyst.portrait.review、analyst.diagnosis.review、analyst.solution-design.review，independent_review、return_stage等于对应阶段，human_principal version1、actor匹配；不从其他槽推断许可。选择人当前仍为同租户成员；既有Owner验证resolution，额外检查回执当前时间和实际snapshot/body hash。仅人员职责核验，不自证Eval、业务产物或Run当前性，不调用Provider、不提交事务、不安装主库。

新增 services/aos-api/tests/test_ecommerce_analyst_stage_review_authority.py：合法human空cap、机器空cap拒绝、原有cap序列化兼容；隔离PG使用真实AssigneeResolution/ResponsibilityPlan Owner构建人工槽（模板resolver测试替身明确记录），校验当前精确ref、actor、成员移除、回执过期、错误阶段、plan hash漂移及跨租户拒绝。下一波实际Eval/阶段产物核验与产品命令。

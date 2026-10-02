# E17-s3o-d｜AgentInstance 当前性与来源门文件级计划

基线 `m1@eb440d30`、`AOS-001188`；真库 `aos_current_preview_20260927@a0v_135` 只读。复习 231/231-9、49-W6-01、原 Resolver、W5CB4 E17-s3l 来源门和 D-waves。原无 Receipt 的 Agent 路径已有 Skill 发布与 create/evaluate/update 来源检查；canonical Receipt 路径只复核 Receipt 自身，需验证是否绕过该门。

1. `services/aos-api/tests/test_ecommerce_analyst_stage_review_authority.py`：只在 disposable PG 形成同租户 AgentInstance、SkillBinding、CapabilityBinding 和原 Resolver Receipt。先以 draft Skill/无正式绑定 Receipt 测 Plan 创建禁入 RED；再用隔离夹具保存发布和绑定来源的最小记录作下游当前撤销测试，不把夹具称为正式发行验收。检查实例、Skill、能力当前失效后的 GET/freeze 与无新冻结 Receipt，并发写准入锁。
2. `services/aos-api/aos_api/aip_production_contract_store.py`：在原 `_require_exact_assignee_resolution` 复用 Resolver 候选判断，比较不可变 exact Binding refs；只对原 Receipt 涉及的 SkillBinding 复用现有来源条件。写准入锁本实例/相关 SkillBinding/CapabilityBinding；GET 无写锁。若来源检查需抽共用逻辑，先保持既有 legacy 行为并加相邻测试。
3. `services/aos-api/aos_api/aip_assignee_resolution_store.py` 仅当判定本身遗漏当前 exact 来源而消费点不可安全复用时改动；不引入第二身份目录、不回填旧 Receipt。RED→GREEN→专项/相邻、方案复审、verification、m1 精确提交、Task/Authority/Prime/01/06/D-waves 收口。独立 issuer/ACL 与正式配置/首链仍另证。

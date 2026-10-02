# E17-s3o-d｜AgentInstance 当前来源与撤销门 verification

基线 `m1@eb440d30`、`AOS-001188`。仅 `org-org/dev-project` 的 disposable PG；当前真库只读。上位方案和文件级计划见同前缀 plan。

| 检查 | 命令与新鲜结果 |
|---|---|
| 来源 RED | 原 AgentInstance + draft Skill + active/available SkillBinding + CapabilityBinding 可生成 resolved Receipt；Plan 旧码仍写入，`pytest -k agent_receipt_cannot` → `DID NOT RAISE ProductionContractDependencyBlocked`，exit1。 |
| 来源 GREEN | 原 Plan 消费点检查每个 Receipt 引用 SkillBinding：精确同租户/同实例/版本、当前 published 且发布租户正确、家族最新仍 published、create/evaluate/update 三个 applied Registry Receipt 齐全。draft 或缺任何一个来源时 create 禁入。Agent 来源专项含3个逐项缺 Receipt 负例，13 passed。 |
| 当前性 GREEN | 隔离夹具中保存发布元数据与三种 Registry Receipt，仅作为代码负例/正向对照，不代表正式 issuer/ACL 验收。当前实例 status/version、SkillBinding status/freshness、CapabilityBinding status/policy 漂移令 GET/freeze BLOCKED；freeze Receipt 0。三组两连接250ms锁测证实写准入锁住精确实例/Skill/Capability 行到提交，提交后撤销可使只读 GET BLOCKED。 |
| 相邻回归 | `pytest -q tests/test_ecommerce_analyst_stage_review_authority.py tests/aip/test_w6_01_exact_assignee_resolution.py tests/aip/test_w_l20_assignee_resolution.py tests/test_w2b_production_contract_store.py tests/extension_runtime/test_ecommerce_content_repair_action_binding.py --tb=short` → exit0，76 passed/7 warnings。`py_compile`、目标 diff check exit0。 |

夹具第一次试跑因 published Skill 缺 LogicRevision、发布来源列而触发 PostgreSQL CHECK；补齐字段后才形成有效正向对照。未调用 Provider、未读商城源、未启 Host/worker。独立受限发行身份与数据库 ACL 尚未证明；现有 `aos_runtime` 直写 Receipt 风险不能由应用层来源查询消除。最新模板家族 append-only 并发插入与正式六绑定/八配置/首链也留后续波。旧 RETURN 正向测试冲突仍独立对账，不声称全量业务 GREEN。

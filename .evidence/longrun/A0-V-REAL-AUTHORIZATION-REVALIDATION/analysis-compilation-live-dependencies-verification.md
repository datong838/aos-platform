# CF2-4 当前技能依赖与编译兼容性核查

基线3bffb2bc。2026-09-14 07:20 CST对恢复主库aos_meta_head只读查询（事务READ ONLY，无写入），确认D01/D02/D03技能发布r2对应各Logic r1；三项active绑定readiness字段available但TTL已于2026-09-12 03:27 UTC过期，不是当前可用。D03历史r4不可照搬。阶段模板stage-template-ea53ff98fc1644c392ff@2冻结，profile=ecommerce.business-investigation；职责responsibility-plan-63c82d2a75614e1b95f1@2冻结，profile=ecommerce.business-investigation.readonly。

正式编译器要求两者及context同profile，因此补run_with_stage一致性拒绝，不放宽编译器。Red2 failed/10 passed，Green34 passed，AR2 1889/171/93所有错误为空，memory validate GREEN/AOS-000573，diff --check通过。阶段Store测试仍为替身，真实只读快照不表示运行许可。

下一波CF2-5设计并实现SkillBindingSetRevision精确集合合同及当前来源解析，已有编译器仅引用此类型，尚无对应生产Store。37技能拆分表是planned_not_published，不作映射权威。之后版本化映射、新阶段准备、CF3 Task/Brief/Context、CF4真实START、CF5安装、CF6真实业务。当前真实首链未完成；未改旧冻结记录、主库或外部系统，不push，230 L0挂起。

```text
BEGIN
          observed_at          
-------------------------------
 2026-09-13 23:20:05.490215+00
(1 row)

      graph_id       | graph_revision |                            graph_hash                            
---------------------+----------------+------------------------------------------------------------------
 ecommerce.logic.D01 |              1 | 0dd33b6e75ee443ddb4a0aa0cc1490206edd6c1aaa9685301c7c504956e084e5
 ecommerce.logic.D02 |              1 | 16ff73fc9464601f94dfba71b06327b0f9f2e29c4170ba7217db3bd8d034a774
 ecommerce.logic.D03 |              1 | e1d4817d77cf10dffd0bc23a0734ccab8f285bc745c334978da7c9c48af0adaa
(3 rows)

      skill_id       | skill_revision | status | readiness |     readiness_expires_at      | current_ready 
---------------------+----------------+--------+-----------+-------------------------------+---------------
 ecommerce.skill.D03 |              2 | active | available | 2026-09-12 03:27:43.877132+00 | f
 ecommerce.skill.D02 |              2 | active | available | 2026-09-12 03:27:43.812407+00 | f
 ecommerce.skill.D01 |              2 | active | available | 2026-09-12 03:27:43.742906+00 | f
(3 rows)

                 plan_id                  | revision |                  profile                  | lifecycle 
------------------------------------------+----------+-------------------------------------------+-----------
 responsibility-plan-63c82d2a75614e1b95f1 |        1 | ecommerce.business-investigation.readonly | draft
 responsibility-plan-63c82d2a75614e1b95f1 |        2 | ecommerce.business-investigation.readonly | frozen
(2 rows)

             template_id             | current_revision |             profile              | lifecycle |                                                                                          source_bundle_ref                                                                                           
-------------------------------------+------------------+----------------------------------+-----------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 stage-template-ea53ff98fc1644c392ff |                2 | ecommerce.business-investigation | frozen    | {"revision": 1, "resourceId": "ecommerce.initial-store-analysis", "contentHash": "267e3ec1a06662793ef1c71a7a70cc4952fbe3833e910caa63bc8e5399ae96fb", "resourceType": "InvestigationProfileRevision"}
(1 row)

COMMIT
```

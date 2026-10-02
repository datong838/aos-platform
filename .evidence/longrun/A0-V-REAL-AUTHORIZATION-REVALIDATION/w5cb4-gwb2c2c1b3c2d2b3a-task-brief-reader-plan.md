# GW-b-2c2c1b3c2d2b3a｜生成宿主 Task/Brief v3 独立读者

基线 `AOS-001126` / `m1 af6e7de7`。复习 231-5 §1/§9、栖月汇六同事统一 Task/Handoff、BG00GW 清单。原 ReviewAdvanceHostService 已在隔离 PG 写出 v3 Task.goal/Brief.spec 的 17 项 exact 来源；包命令与宿主 strict parser 接受单原 Artifact，但 Host 三入口仍禁入。下一段必须由原 Owner/Receipt 提供独立 expected lineage，再核 Task/Brief；不能直接信任 Task/Brief 自带的字段。

本切片只改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 中 `ContentGenerateHostService._task_brief`：增加显式 `source_kind`/`source_lineage` 调用参数（旧默认保持），accepted-stage 必须由调用方提供非空、17 项 exact lineage；同事务核 Task.goal 与 Brief.spec 均等于该独立 expected，schema 必为 v3、单原 Artifact 与 GrowthPlan/Handoff/Task 精确一致。原 v1/v2 字段与销售方法分支不变。**本波不把 Task/Brief 自身当 expected，也不接入 Host.revalidate，因为原 Review Receipt/Stage Owner 尚未齐备。**

测试在 `services/aos-api/tests/extension_runtime/test_ecommerce_review_task_brief_authority_pg.py` 先 RED：用原 Review Task/Brief Owner 于一次性 PG 写出 v3，再由生成读者接受独立 expected；篡改 expected、Task.goal、Brief.spec 的来源或 schema 均拒绝。相邻旧 handoff lineage、内容生成/budget/return 回归；py_compile、diff-check、浏览器只读禁入复验。源码与证据精确提交、AOS/Prime/D-waves 更新。后续 d2b3b 接原 Review Receipt/StageDecision Owner，继续 Host 禁入。

真实库只读，无商城源/旧Run/手工Run/dev-org写、无 Host/worker/Provider/push。当前正式 OIDC、八配置、Host assignment/binding、Growth1.13 当前发布仍独立 P0。

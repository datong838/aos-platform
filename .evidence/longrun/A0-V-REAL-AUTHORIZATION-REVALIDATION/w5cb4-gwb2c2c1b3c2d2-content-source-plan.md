# GW-b-2c2c1b3c2d2｜原阶段内容生成与评审同源接线方案

基线 `AOS-001122` / `aos-platform/m1 0c78b3c2`。先复习 231-5 §1/§9、栖月汇六同事统一 Task/Handoff 产品方案及 d1 Task/Brief v3 的 exact `sourceLineage`。当前 Host 仍以 `accepted stage Handoff ... not wired` 失败关闭，内容生成和评审的旧合同只接受四个 `ArtifactRevision`、ReviewIssue；这不是可以通过删掉长度检查解决的问题。

## 文件级顺序

1. **包内生成命令来源歧视**：`bundles/solutions/ecommerce-growth/backend/ecommerce_growth/content_capability_runtime.py` 的 `ContentCapabilityRequest` 增显式 `accepted-stage-v1` 选择，只允许一个原 `Artifact`，并把来源种类进入命令 hash；默认旧路径的字段和四引用输出保持原样。`services/aos-api/tests/extension_runtime/test_ecommerce_content_capability_budget_runtime.py` 先 RED：原单 Artifact 被拒；新分支只接受一个、拒混四引用/伪造旧种类，旧请求字节形状保持。**执行函数在 Host 消费者未接线前先拒绝该新分支，不调用 port；**宿主也仍拒绝其命令，不能称生成已执行。
2. **宿主生成准入**：`services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 的 `_strict_content_generate_command`、`_review_receipt`、`_task_brief` 和后续原 Source Owner 读取必须识别 v3；核同租户当前 StageDecision/Plan/Attempt/Eval/Artifact/permission、cutoff、GrowthPlan、Task/Brief 与签名安装/预算；不能仅凭包传的 `sourceLineage` 信任。隔离 PG 正反例先行；Host 及 Provider 在完整链前仍不开。
3. **可读产物和人工评审**：`bundles/solutions/ecommerce-growth/backend/ecommerce_growth/content_artifact_review.py`、宿主 `ContentReviewHostService` 及其原内容评审 Owner 读者增加 v3 独立 envelope 与单原 Artifact 同源核验，旧四源/ReviewIssue 分支不放宽。新产物仍需真实文本、商品事实、人工评审与预算 Receipt；无来源/撤销/到期、跨租户和跨分支重放负例。
4. 最后以原 Case/Occurrence/Analysis/Stage/AgentRun/Eval/权限生产者在一次性 PG 做完整正反联合，重看 Runtime Host/正式实例准入，才评审打开 Handoff/生成/评审相应执行门。正式 OIDC/三身份、八配置、Growth1.13 正式信任根/绑定仍是当前实例独立 P0，不以本地测试替代。

本轮先执行第1项 RED 与最小命令切片，后续消费者留在同一 d2 登记项，绝不凭语法 GREEN 宣称内容产物或首链。专项覆盖请求语法及邻接预算/Artifact 测试；`py_compile`、差异检查、verification、m1 精确提交、AOS/Prime 和 D-waves 收口。真实库只读、无商城源/旧Run/手工Run/dev-org写/Host/Provider/push。

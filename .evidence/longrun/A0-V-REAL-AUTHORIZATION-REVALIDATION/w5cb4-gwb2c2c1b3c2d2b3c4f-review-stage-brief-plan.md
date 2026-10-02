# d2b3c4f｜内容评审原阶段、Review Receipt 与 v3 Brief 同截面读者

基线：AOS-001137、m1 `dad540c6`、当前真实库 `a0v_135` 只读。复习 231-5 §9、231-9 内容首链和 BG00gw d2b3c4f。当前内容评审已能读单个原 `Artifact`，但 `_task_brief_authority` 只核 Task/Brief 的少数字段；新来源在 Host revalidate 入口直接报 `not wired`。本波只使入站重验读取原阶段 Owner、持久 Review Receipt 与 v3 Task/Brief 的同一组 exact refs，并保留末端禁入。

## 文件级施工顺序

1. `services/aos-api/tests/extension_runtime/test_ecommerce_review_task_brief_authority_pg.py`：先 RED。用原 Review Owner 在可销毁 PG 写出的 v3 Task/Brief，构造 accepted-stage 内容评审命令；缺当前原 Stage Owner 或缺持久 Review Receipt 必须拒绝，不能仅凭 Task/Brief 形状通过。覆盖错来源种类、错单原 Artifact、跨租户与已过期截面。测试 fixture 不代表真人批准。
2. `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：在新来源分支复用原 `ContentGenerateHostService._accepted_stage_owner_refs`、`_review_receipt`、`_task_brief`，并用当前数据库时间核 cutoff/expiry；新读者从 Task.goal 取 Handoff 和原 lineage 候选，但独立原 Owner 与持久 Receipt 必须逐项确认，不能把 Task.goal 当最终 authority。旧 Issue 分支保持原行为。接入 `ContentReviewHostService.revalidate`，最后继续显式 `Host is not wired`；`execute/verify_receipt` 不放行。
3. `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_authority_feedback.py`：原单元断言新分支在任何 DB read 前直接拒绝，入站读者接线后该断言过时；改为证明 revalidate 仅取当前数据库时间、调用新读者并仍报 `Host is not wired`，而 execute/verify 继续在任何 DB 操作前禁入。测试 seam 不能充当正式 Receipt 来源。
4. 先跑专项与相邻 Review/生成回归，再在浏览器只读核 `/aip/skill-publish` 禁入。复审 231-5 §9、精确来源和权限、当前真实库零写，落 verification；m1 精确提交，AOS/Prime/D-waves 同步。若原生产者联合正向尚缺，必须在验证中明确为待办，不得报告首链 GREEN。

现有外部 OIDC、八配置、Growth1.13 正式发布和 Host assignment 缺口各自保留门；不启 Host/worker/Provider，不读商城源，不回放旧 12 Run，不手工 Run，不改当前真实库。

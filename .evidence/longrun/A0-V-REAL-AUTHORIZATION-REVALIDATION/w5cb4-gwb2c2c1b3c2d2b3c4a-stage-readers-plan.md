# d2b3c4a 原 Stage Owner 与生成双读者接线方案

上位：231-5 §9、D-waves d2b3c4。当前原 Analysis producer 因正式 Skill Eval 来源缺失不能作为全链正向；本波只补生成 Host 的读者接线和失败封闭证据，不放行 execute/Provider，不虚称当前实例 GREEN。

## 最小接线

1. 修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 的 `ContentGenerateHostService.revalidate` 新来源分支：先校验 dispatch；按租户和 `handoffRef` 只读唯一原 Review Receipt，抽取受限 `sourceLineage` 候选。候选仅是路由线索，不是权威。
2. 同一 `HostTransaction` 复用原 `ReviewAdvanceHostService` 的 StageDecision/获批 successor、Case/Occurrence、原 Analysis Runtime、Stage TaskRun/Plan/Eval/permission 读者；比较 cutoff、expiry、租户与 exact refs。再用独立原 Owner expected 调用现有 `_review_receipt` 和 `_task_brief`；不得由 Task/Brief 自身充当 expected。
3. 读者检查后仍显式拒绝 `accepted stage content Host is not wired`；`execute`/`verify_receipt` 的前置禁入不动，旧四 Artifact/ReviewIssue 分支不动。

## RED/验收文件

- 修改 `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_handoff_lineage.py`，先证明目前新分支在任何来源读取前直接拒绝；改为验证同租户唯一 Receipt 缺失、伪造来源、错类型与跨租户均失败封闭，且 `execute` 仍无 DB/Provider 触达。
- 修改 `services/aos-api/tests/extension_runtime/test_analyst_stage_handoff_source_pg.py`，在可销毁 PG 原 Owner fixture 上核能从原 Decision 重建阶段 exact refs；缺原 Stage runtime 时停于对应具体门，不得以 fixture 当业务通过。
- 跑专项及相邻合同回归、语法/diff、适用时浏览器。原 G2 Eval、OIDC、八配置、正式发布和当前 Host 身份缺口另门。

风险：若现有 Receipt 尚无正式持久化原来源，则新路径只会更早给出权威缺失，不能把此切片当成可运行功能。预期下一波补原 producer 联合正例及生成/人工评审两消费者，再决定解除最后的执行禁入。

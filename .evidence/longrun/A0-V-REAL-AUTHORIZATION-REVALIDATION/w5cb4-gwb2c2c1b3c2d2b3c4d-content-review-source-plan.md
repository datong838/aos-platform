# d2b3c4d 已接受阶段内容人工评审同源方案

上位：231-5 §9、BG00gw d2b3c4c。当前 m1 99317636 的结果消费者已让可读内容 Artifact 保留 `accepted-stage-v1`，但 bundle `ContentReviewRequest` 仍在新来源入口报 `Host is not wired`；宿主 `_strict_content_review_command`、`_artifact_authority`、`_task_brief_authority` 只接受四个 `ArtifactRevision`，故不能拿旧 Issue 分支解释新来源。正式 G2 Eval 与原 AnalysisRuntimeReceipt producer 仍缺，当前库与 Host 维持禁入。

## 文件级实施顺序

1. `services/aos-api/tests/extension_runtime/test_ecommerce_content_capability_budget_runtime.py` 和 `test_ecommerce_content_review_authority_feedback.py`：先写新来源 RED。要求 `sourceKind=accepted-stage-v1` 精确进入命令与哈希；`sourceArtifactRefs` 仅一个原 `Artifact`；ReviewIssue 必须是**内容生成产物**的独立 Eval/人工决策来源，不能复用阶段 Handoff Issue。错分支、四旧引用、旧 Issue、跨租户和篡改均拒，旧 Issue Review 合同不变。
2. `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/content_artifact_review.py`：仅对新来源生成判别式命令，保留实际内容 ReviewIssue、ReviewerAuthority、ACCEPT/RETURN 与 receipt exact refs。现有 1.13 签名候选不可变；后续新版本按独立 build/sign/qualification 流程，不原地改旧签名树。
3. `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：新来源 `_strict_content_review_command`、内容 Artifact、v3 Task/Brief 和原 Stage/Review Receipt 读者同源校验；内容 Eval/ReviewIssue 及人类事件由原 Owner 精确读回。旧四来源分支保留。补 `execute`、`verify_receipt` 与 feedback/ReturnDecision 相同的分支与 exact 哈希；不能只放通入口。
4. `services/aos-api/aos_api/ecommerce_content_review_step_owner.py` 及隔离 PG 联合测试：Receipt-first、未知效果只读对账；ACCEPT 后原 Run/Task 终态，RETURN 后准确回内容生成，重复命令不重做外部效果。检查预算、租户、当前安装/绑定与状态机，不把 fixture 造的人工事件当正式来源。
5. 专项、旧 Issue 相邻回归、PG 正反链、适用时浏览器、方案/代码复审、verification、m1 精确提交、AOS/Prime/D-waves 同步。当前真实库只读，正式 G2/身份/八配置/Host 未齐前所有当前执行与自然 Provider 保持关闭。

## 本波先行 RED 的边界

先只写第1项的严格命令测试并定位失败节点。若原内容专属 Eval/ReviewIssue 的生产者不可用，不为让测试变绿而捏造正式权威；记录受限结果并继续可独立的合同与读者实现。验收成功必须有原生产者、持久人工事件、内容 Artifact、Receipt、原 Run/Task 状态和浏览器正向证据；单个构造请求或受控 PG 不算首链。

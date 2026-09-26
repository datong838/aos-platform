# W5CB4-P1｜内容人工决策事件门与退回步骤映射中间验证

## 结论

P1 代码门 GREEN，**W5CB4 整波未完成**。`ContentReviewHostService` 过去接受仍 `open` 的 ReviewIssue，就可以形成 ACCEPT/RETURN Receipt；责任槽不等于人类已作决定。现在 Host 只接受与 exact Artifact 同源的 `resolved`/`returned` issue，并独立核对对应不可变事件、版本、actor、payload hash。ACCEPT 要求人类 resolve 的 `resolutionRefs` 明确含当前 Artifact；RETURN 要求真实 `ReturnDecision` 与事件的 Run、step、attempt 产物、hash 和 actor 一致。业务 `returnStage=content_generation` 不再误当公共 Run step key；公共退回目标必须是 `content_generate`。

## RED→GREEN 与复审

- 新断言先证明 `open` issue 被旧 Host 接受、仅有 returned event 而无 ReturnDecision 也被接受；两项 RED 后最小修复。错误事件 hash/actor、缺 exact Artifact resolution、错 step key 均拒绝。
- 邻近 Host/反馈组件合计 **31 passed，7 既有 warnings**（加入领域包和 SDK 测试路径）；`compileall`、`alembic heads=a0v_104`、`git diff --check` 通过。两次测试收集失败只是缺领域包/SDK 路径，补齐后通过；未改生产依赖或代码以迁就收集器。
- 仍仅是 mock authority＋既有组件测试。尚未证明当前 EvalReport→ReviewIssue 自动创建、真正人类页面决策、TAOR StepRun/TaskRun 终态或反馈自然续跑；无浏览器改动。生产 Worker/Provider 继续关闭，旧 12 Run 与商城源未触及。

## P2 入口

先建立可读 Artifact 的当前待人工评审投影与合法 Eval/ReviewIssue 创建路径，再让人类决策事件自然到 Review Host；最后用公共 TAOR Owner 达到原 TaskRun 正式终态，验证反馈消费。若 canonical ReviewIssue 路径在 exact 内容下不可用，保留禁入并先修通该路径，不以 Host Receipt 代替人类决定。

# W5CB4｜可读内容产物→人工 exact 评审→Run 终态／反馈续跑（施工前）

## 上位方案与现场

- 231-5 §1/4/5/7、231-9 BG-04 与栖月汇产品方案要求：真实可读内容产物先供人核事实、敏感数据、禁用表达和格式；人工 ACCEPT/RETURN 是业务决策，不由 worker 代批。ACCEPT 后同一 TaskRun 应有正式终态，反馈进入总控复盘及 Wiki 候选，不自动发布或触达。
- W5CB3 只达到隔离受控 Artifact 代码门。现有 `ContentReviewHostService`、`BoundEcommerceGrowthFeedbackPort`、`CurrentFeedbackConsumer` 已有 exact 评审/反馈合同；但缺少从 W5CB3 的 Artifact 自动形成**可供人评审的当前待办**、评审后 Run 终态到反馈的同库自然证明。不得把旧假 Artifact、PENDING 预算或开发者手填命令当审批。
- 生产 `a0v_104` 未应用；Worker/Provider 关闭，原 12 Run 与商城源读不在本波。无当前合法 Artifact 时只做默认关闭代码与受控验收，不补造真实审批。

## 文件级清单与顺序

1. 先审 `ecommerce_growth_runtime_adapters.py` 的 ContentReview Host、`ecommerce_growth_feedback_port.py`、`ecommerce_growth_feedback_consumer.py`、公共 TaskRun／ReviewIssue Owner 与 `apps/web` 现有工作台入口；逐一记录 Artifact Ref、ReviewerAuthority、ReviewIssue、Task/Brief、Run 终态的当前归属和缺口。禁止发明第二审批体系。
2. 优先给 `services/aos-api/tests/extension_runtime/` 新增 RED：同库 W5CB3 Artifact 被识别为唯一待人工评审项；仅人类当前授权的 exact ACCEPT/RETURN 可进入 Host，未决/过期/错租户/旧安装均不推进；ACCEPT 后原 TaskRun 终态及反馈段独立读回；RETURN 只生新内部目标、不重用旧 Provider 结果或自动再发。若已有代码覆盖，则只做组合回归及最小接线。
3. 仅针对 RED 暴露的断点修改相应 Owner／API／必要的最小 UI，默认关闭任何新 worker。专项、累计回归、完整 schema 隔离 PG；如涉及页面，必须浏览器验收。复审方案/代码一致性和不可越权副作用。
4. verification 落盘→m1 精确提交→D-waves/AOS/Prime 记忆更新。生产激活仍须先通过 W5CB2/3 的完整同库自然链及当前安装、审批、预算、来源、权限和独立 Receipt。

## 复审修订：先封人工决策门，再接终态

- 现场发现 `ContentReviewHostService._issue_authority` 目前只接受 `ReviewIssueStatus.OPEN`，因而它证明的是“待评审存在”，**不是人类已决策**。正式 `resolve_review_issue`/`return_review_issue` API 才检查评审角色并写不可变事件；必须要求当前 issue 的 `resolved`/`returned` 终态与同 issue 的对应人类事件、版本、actor、payload 和 exact Artifact 一致，才能由 Review Host 产生业务 Receipt。不得把责任槽 `ReviewerAuthorityRevision` 单独当人类批准。
- 退回命令的业务 phase `content_generation` 与公共 TaskRun 步骤 `content_generate` 是两种不同标识；公共 `return_review_issue` 必须接实际 step key，Host 回馈继续保留业务 phase。明确映射，不全局改既有 Plan step key，也不降低 ReturnDecision 的当前 Run/版本/attempt 检查。
- W5CB4 分 P1/P2：P1 先做上述人类决定/退回映射的 RED→GREEN 和邻近测试；P2 再做 Artifact→待办、TAOR StepRun/TaskRun 终态及反馈同库自然接线。P1 通过绝不称本波完成，verification 只在 P2 或清楚记录未完成后落盘。

## 退出／下一波

本波最多证明受控 Artifact 后的“待人评审→exact 决策→Run/反馈”代码链；没有真实人类审批不得声称自然闭环。下一波按本波证据补生产激活硬门与当前实例自然观察，而非回到旧 12 Run 的逐行补数。

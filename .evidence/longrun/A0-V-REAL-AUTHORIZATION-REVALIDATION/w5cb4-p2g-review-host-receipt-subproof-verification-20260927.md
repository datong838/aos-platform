# W5CB4 P2g｜评审 Host Receipt 同库子证明（2026-09-27）

## 结论与边界

- 在正式 `a0v_105` 迁移的一次性数据库中，原 Task/Run/已结算 Artifact/成功生成 StepRun/主体 EvalReport/ReviewIssue、人类 ACCEPT 事件、四来源 Artifact、正式 Brief 组成同一对象链。新增 canonical 人类 AssigneeResolutionReceipt 与 frozen READY/COMPLETE ResponsibilityPlan；`ContentReviewHostService.revalidate → execute → verify_receipt` 对该对象成功，独立连接读回唯一 content.review runtime Receipt 与唯一 feedback command。
- 此为**隔离子证明**。ResponsibilityTemplate resolver 是测试接缝而非已签名安装的 Bundle；人工 `fixture-reviewer`、来源与 Provider 响应均为受控材料。测试直接调用 Host service，未经过完整九操作锁/当前实例，未完成 `content_review` StepRun/TaskRun，未自然消费反馈；不代表真实栖月汇人工审核或首链闭环。当前实例不迁移、不启 worker、不外发。

## RED、最小修复与测试

- RED 1：READY/COMPLETE `content.review` slot 的人类 assignee 与 ReviewIssue 第 2 号决定事件 actor 不一致，原 Host 仍放行。`_reviewer_authority` 现要求事件存在、actor 非空且为该唯一当前 slot 的 `human_principal.resourceId`；错 actor/缺 actor fail closed。
- RED 2：`_strict_content_review_command` 要求 `ReviewIssueRevision` ref 无 `receiptId:null`，但 `_issue_authority` 的内部 expected ref 曾保留 null，合法命令无法同时通过两门。仅将内部 expected 规范为 `exclude_none=True`，不放宽 exact ref/hash/Issue 约束；现有测试调用同步使用 canonical ref。
- 专项：`test_ecommerce_content_review_authority_feedback.py` + `test_ecommerce_content_review_pending_pg.py` 为 18 passed；单条完整链 1 passed、6 deselected。
- 累计：内容相关与反馈选择器 `303 passed, 35 skipped, 7 warnings`。跳过项目不计通过；后端安全门与一次性库无需浏览器验收。`git diff --check` 通过。

## 方案/代码一致性及下一步

- 符合 231-5 的“人工评审→系统自动续跑”顺序，但目前只到正式 Host service Receipt/feedback enqueue 子门。Receipt 和反馈本身不是原 Run 终态。
- 下一波立即实现 `ecommerce_content_review_step_owner.py`：从当前 exact Receipt/feedback 读取原 Run，在九操作锁和完整 Host 复验下完成 `content_review` 四相 StepRun/checkpoint 与原 TaskRun；独立回读后才允许现有反馈消费者自然拾取。若签名模板/当前安装门无法组成，只报告子证明并保持 worker 关闭，不能用测试接缝代替生产授权。
- 旧 12 Run 退休、失败快照逐行补齐与 230 L0 继续作为后置队列；未知边界不重发，商城源数据未读取。

# W5c3w Cutover Validate 门禁失败验证（2026-09-24）

## 结果：未通过，未调用第二次

W5c3v 原子 Commit 仍为正式终态；本波在私有 0600 intent 固定 finalize 请求 `a0v-w5c3w-third-successor-cutover-finalize-20260924-v1`/hash `sha256:547855d32bb5eb76e8d9bd55c2eb7f75c59376967e0f9c74e84be9b03f28d4fa` 后，原 Owner **一次**调用 `validate_activation`，返回 `EcommerceGrowthCutoverBlocked: active exact cutover ActionApprovalEvent is required`。没有 Validate Receipt，operation 仍 committed，claims 仍 paused；绝不按同一 key 重试。

只读核查表明审批 proposal `proposal-acf0531dcc7d42f598a8` status approved、expires_at 07:37:15 UTC，但其精确 ActionApprovalEvent `approval-9a7388ca0ddd44e497c8` 在 **07:07:15 UTC 已过期**；调用时间 07:13 UTC。脚本 preflight 只检查 proposal 期限，遗漏 event 期限。`refresh_activation_approval` 的正式 API 只允许 prepared/draining，operation committed 后不可用。这是本波阻断的确切原因，不能把 proposal 有效当作审批事件有效。Commit 发生于事件过期前，但 validate 已越过事件期限。

脚本最初只读预检曾引用不存在的 finalize 专表，导入/SQL 阶段失败，修正为正式 `extension_dispatch_cutover_receipt` 后预检成功；没有状态写入。正式 validate 调用失败后未生成 result。当前只允许只读对账、正式安全恢复或经方案/测试后的核心修复；不得直接 resume、手工 Run、重发 validate 或放开 claim gate。

## 下一波

先制定独立 post-commit 失效审批的安全恢复方案，检视 rollback 与正式审批刷新契约，确定可验证的最小修复/回退路径，再另波执行。路由已 extension 但 claims paused，不是业务成功。

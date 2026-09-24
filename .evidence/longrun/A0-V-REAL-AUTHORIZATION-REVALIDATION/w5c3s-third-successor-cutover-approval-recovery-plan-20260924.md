# W5c3s 第三继任者 Cutover 主库审批恢复方案（2026-09-24）

## 起点与修复边界

W5c3p `3be8e904` 旧库误连、prewrite rejection；旧键 intent 保留、proposal0/cutover0。W5c3pR `73d37351` 已证明原 `AipActionStore` 在 `aos_meta_head` 的精确租户 `aos_runtime` 连接可读当前 cutover action type，未需 GRANT。此波只包装原 `_approve` 的连接工厂为已验证主库连接，不改审批政策/Store/身份，不在旧键上重试。

## 串行步骤

1. 只读复核 W5c3p 旧键 proposal0、第三安装/Host/lease、注册 Receipt 与九路 group365 legacy/fenced、12 schedule off、零在途/canary、业务计数、四来源/预算、主库 action-type revision hash；新键 proposal/approval0。
2. 新 `scripts/a0v_w5c3s_cutover_approval_recovery.py` 与定向测试，只改变本进程的 `_web_connection` 指向 W5c3pR 经验证的 `head_action_connection`，固定新键 `a0v-w5c3s-third-successor-cutover-approval-20260924-v1`，复用 W5c3p 的无外部效果 policy/目标 payload。私有 0600 intent 先冻结。
3. 原 AIP `_approve` 对现有 maker/checker 执行一次正式审批。中间任何异常/未知不整体重发，按 proposal key/approval event 只读对账，必要时正式撤回或新波恢复；不得创建新的 checker 身份或跳过独立批准。
4. 独立读回 proposal approved、两位原 checker 的有效批准、policy/hash/期限/target、九路/调度/业务计数不变；verification 与 m1 commit。下一波仅 prepare cutover，随后各阶段独立波。

## 停止条件

主库或 runtime role 不精确、旧/新键已占用、maker/checker 不合法、审批政策变化、Host/资源/预算/九路/调度/在途/canary 漂移、提交边界未知，停写对账。绝不手工 run_definition 或读取商城源。

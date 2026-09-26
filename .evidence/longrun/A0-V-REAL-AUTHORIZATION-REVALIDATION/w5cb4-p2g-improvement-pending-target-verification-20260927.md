# W5CB4 P2g｜反馈第二段待观察目标回执（2026-09-27）

## 结论与范围

- 在原 `a0v_106` 正式迁移的一次性数据库中，同一原 Task/Run/内容 Artifact/模拟人类 ACCEPT/Host Receipt/feedback command 先完成第一段 `DailyReviewReceipt`，再由非超级、serializable `aos_runtime` 的 `CurrentImprovementConsumer.run_once` 选择并消费第二段。`claim_current → require_current_origin → BoundImprovementPendingTarget.put → read_receipt → acknowledge` 同事务写唯一 `ImprovementPendingReceipt`；独立 SQL 读回 body/数据库 hash/Receipt，第二段 `acked`/attempt=1/checkpoint=2，第三段仍 `pending`/attempt=0；重复 `run_one` 仅回读 `ALREADY_ACKED`。
- 第二段目标是 `effectStatus=AWAITING_COMPARABLE_EVIDENCE`，含原 exact review/artifact/task/brief、第一段 Receipt 与安装代次。它不是 `EffectReview` 已完成、增长效果已验证或 Wiki 已入库。当前实例不开新 worker、不迁移主库、不读微商城源、不重放旧十二 Run。
- 负例：第一段未 ack、原 Run 改为非终态、当前 dispatch fence、第一段目标 body/hash 漂移，均不创建第二段目标；目标函数还校验唯一当前原 review Receipt、同租户/安装/runtime、原 Run 与 Task 终态、第一段已 ack 的精确回执、第二段唯一 claim/lease/checkpoint。测试 `dev-org` scope 的 RLS 读回为零。

## 权限 RED 与修复

- 权限探针首先发现迁移默认 ACL 为 `aos_runtime=arwd`；`REVOKE ... FROM PUBLIC` 并未撤销运行角色直授的 INSERT/UPDATE。`a0v_106` 明确收回第一段 `ecommerce_growth_daily_review_target` 和新第二段 `ecommerce_growth_improvement_target` 的直接写权限，保留 SELECT 与受限函数 EXECUTE。隔离数据库 `has_table_privilege` 证实两目标表对运行角色均为 SELECT=true、INSERT/UPDATE=false；第一、二段正式函数消费仍通过。未给运行角色扩大表级权限。

## 验证及未完成门

- 专项同库 `1 passed, 6 deselected`；内容/反馈累计 `318 passed, 12 skipped, 7 warnings`；`alembic heads` 仅 `a0v_106`；`compileall`、`git diff --check` 通过。跳过项不计成功。纯后端、当前实例默认关闭，本波无可适用的浏览器验收对象。
- 测试内容、Provider 响应、责任模板、模拟 reviewer 与 Host Receipt 仍有受控接缝；这不是栖月汇的真实效果观察或自然业务闭环。第二段 selector/worker 尚未接应用启动，第三段 `memory_candidate` 仍未接线；正式 AIP EffectReview、总控可读回流、Wiki 候选治理及签名安装真实人类决定均未证明。

## 下一波

- 先按 231-5、231-9 在原反馈命令上设计并接第三段 `memory_candidate` 的**待治理**内部回执，不直接发布 Wiki；独立验证第二段回执与 checkpoint=2 才能继续。之后把三段消费者按同一默认关闭的运行时门接自然启动，再把待观察目标接正式 EffectReview 的证据/成熟度机制和总控投影；没有真实效果样本不得标 mature/增长有效。

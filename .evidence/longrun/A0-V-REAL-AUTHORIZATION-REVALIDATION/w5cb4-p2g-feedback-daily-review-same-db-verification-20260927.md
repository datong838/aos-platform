# W5CB4 P2g｜同一原 Run 的反馈第一段 target Receipt（2026-09-27）

## 结果

- 只扩 `test_ecommerce_content_review_pending_pg.py` 的原 `a0v_105` 一次性数据库测试，没有生产规则改动或第二条反馈命令。在原 TaskRun 尚 running 时，`CurrentFeedbackConsumer.list_pending` 为零；自然 Review Owner 在非超级 serializable `aos_runtime`/九操作锁下完成原 Run 后，消费者选择唯一原 feedback command。
- 正式 `CurrentFeedbackConsumer.run_once → DailyReviewFeedbackWorker` 经 claim/current origin/`BoundDailyReviewTarget.put`/ack 写唯一 `DailyReviewReceipt`。独立 SQL 读回 target `body`/Receipt，数据库计算 hash 与 Receipt contentHash 相同，第一段 `acked`/attempt=1/checkpoint=1；第二、三段仍 `pending`/attempt=0/无 target Receipt。重复同 command 返回 `ALREADY_ACKED`，target 行数仍 1。
- 源内容、Provider 响应、reviewer 与责任模板仍为一次性库受控对象；Host Receipt 由 fixture 的 service 接缝先行持久，不是当前实例自然产生。此证明仅覆盖反馈第一段；`improvement_observation` 与 `memory_candidate` 目前仍是 `_unwired_target`，EffectReview、总控和 Wiki 治理链均未贯通。当前实例所有相关 worker 仍默认关闭。

## 验证与一致性

- 专项同库用例 `1 passed, 6 deselected`；内容链累计 `318 passed, 35 skipped, 7 warnings`；`git diff --check` 通过。后端目标 Receipt/数据库门无浏览器验收对象。跳过用例不算通过。
- 符合 231-5 的 TaskRun 正式终态后才反馈，Receipt-first、幂等、租户和无外部效果仍保持；没有读商城源、回放旧十二 Run、手工 `run_definition` 或推进 230 L0。

## 下一波

- 先审 231-5/231-9 的反馈含义和现有 EffectReview/总控/Wiki 候选接口，确定第二、三段各自最小目标与严格的“待观察/待治理”语义，避免把尚无业务结果的内容写成效果已验证或 Wiki 已发布。方案先行后做两个正式 target Receipt、checkpoint 2/3 的自然继续；真实签名安装/人类决定仍独立门禁。

# 栖月汇 P11 自然调度验收证据

- 任务：`BI-W10-01-P11-NATURAL-RUN-CHECKPOINT-20260828`
- 真实租户：`org-org/dev-project`
- 隔离 canary：`dev-org/dev-project`
- 调度：`sch-P11-product-review-qyh`，`0 12 * * *`（Asia/Shanghai）
- 触发方式：`cron`
- scheduled_for：`2026-08-28T04:00:00+00:00`
- started_at：`2026-08-28T04:00:03.108848+00:00`
- finished_at：`2026-08-28T04:00:03.394702+00:00`
- 状态：`succeeded`
- rows_written：`20`
- error_code：空

## 同 cutoff 聚合核验

- `ProductReview` source count：`5`
- `ProductReview` projection count：`5`
- 全部 12 个 canonical pipeline 已注册。
- `dev-org/dev-project` ecommerce source count：`0`
- `dev-org/dev-project` ecommerce projection count：`0`

## 测试与边界

- `test_qyh_cron_scheduler.py`、`test_ec_live_executor.py`、`test_ec_d1_5_p08_pipeline.py`、`test_ec_d4_p11_product_review.py`：`61 passed`。
- 未执行 manual trigger、replay、retry、timeout bump、真实业务写操作或发布。
- 本证据只证明 P11 在本次 cutoff 的自然调度成功，不把 P07/P08 或后续 P12 状态推断为 GREEN。

结论：`P11_NATURAL_CRON_GREEN_AT_2026-08-28_CUTOFF_NO_MANUAL_REPLAY_NO_RELEASE`

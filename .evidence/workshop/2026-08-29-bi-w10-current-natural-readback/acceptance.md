# BI-W10 当前自然 SourceReadiness 精确回读

## 边界

- 租户：`org-org/dev-project`；`dev-org/dev-project` 仅作隔离 canary。
- 只执行 canonical GET、真实调度历史 GET 与 DLQ 元数据 GET。
- 未手工运行或重放 P01～P12，未读取 Secret/PII，未修改源端或真实业务数据，未调用 Provider，未执行迁移或发布。

## 当前权威快照

- `checkedAt/cutoffAt`: `2026-08-29T12:38:47.489467Z`
- 聚合状态：`failed`
- `ready`: P01、P02、P04、P05、P06、P08、P09、P11，共 8 条。
- `failed`: P03、P07、P10，共 3 条。
- `stale`: P12，共 1 条。
- 十二条 source/projection 对账差异均为 0；失败与过期没有被既有计数伪装成成功。

## 失败事实

- P03：最新自然时槽 `2026-08-28T20:00:00Z`，`0` 行，DLQ 稳定事实为 SSH tunnel 在 50 次有界探测内未就绪；该运行早于当前有界握手与启动预建修复加载。
- P07：最新自然时槽 `2026-08-29T00:00:00Z`，`0` 行，DLQ 稳定事实为 MySQL 查询期间连接丢失并超时；该运行早于 exact cached tunnel 驱逐修复加载。
- P10：最新自然时槽 `2026-08-29T03:00:00Z`，`0` 行，DLQ 稳定事实为 SSH 子进程 `CONNECT_TIMEOUT`；这是修复加载后的新传输失败事实，不能由 P10 前一日成功覆盖。
- P12：最新成功仍是 `2026-08-28T05:00:00Z`、`420` 行；当前 API owner 于 `2026-08-29 20:14:08 Asia/Shanghai` 才启动，晚于当日 13:00 自然时槽，因此没有当日 run，按 policy 正确为 stale。

## 隔离与运行连续性

- `dev-org/dev-project` 返回独立 `blocked` 的 12 条空权威，不读取正式租户 pipeline/schedule/object facts。
- 当前 8080 唯一 owner 为 PID 96826，启动于 `2026-08-29 20:14:08 Asia/Shanghai`；P01～P12 调度 `12/12 enabled`。
- 当前代码未发现允许人工补跑、catch-up、自动重试或放宽 connect/read timeout 的授权；下一自然时槽继续产生独立 run。

## 裁决

结果为 `CURRENT_NATURAL_SOURCE_READINESS_EXACT_FACTS_VERIFIED_8_READY_3_FAILED_1_STALE_NO_MANUAL_REPLAY`。本结果关闭当前事实回读，不关闭 BI-W10-02，也不把等待自然时槽变成停工。下一确定性施工是把传输失败的去敏稳定分类沿调度运行与 SourceReadiness 合同投影，避免笼统 `PIPELINE_EXECUTOR_FAILED` 阻碍后续当场修复；不得泄露原始异常、端点或凭据。

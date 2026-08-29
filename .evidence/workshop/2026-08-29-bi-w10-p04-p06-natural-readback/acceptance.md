# BI-W10 P04～P06 自然时槽只读验收

- 验收时间：2026-08-29T10:04:33+08:00
- 真实租户：`org-org/dev-project`
- 负向隔离租户：`dev-org/dev-project`
- 代码基线：`aos-platform/m1@1925c890`
- 数据边界：仅通过 canonical `SourceReadinessService` 的 repeatable-read/read-only 事务读取；未手工运行 Pipeline、未重放 DLQ、未修改源系统或真实业务数据。

## 精确事实

| Pipeline | 自然运行截止 | rowsWritten | source/projection | quality | reconciliation | readiness |
| --- | --- | ---: | ---: | --- | --- | --- |
| P04 Category | 2026-08-29T05:00:13.525475+08:00 | 11 | 11/11 | pass | pass | ready |
| P05 Order | 2026-08-29T06:00:07.757306+08:00 | 372 | 124/124 | pass | pass | ready |
| P06 OrderLine | 2026-08-29T07:00:11.140348+08:00 | 936 | 234/234 | pass | pass | ready |

`rowsWritten` 是本次 Pipeline 写入动作计数，不能冒充当前唯一对象数；权威对账口径为同一只读快照中的 source/projection 数量。

负向隔离租户三项均为 source/projection `0/0`、latest run `unknown`、readiness `blocked`，没有读取到真实租户数据。

## 结论

P04～P06 自然时槽与 canonical SourceReadiness 证据闭合，可完成 `BI-W10-01-P04-P06-NATURAL-SLOT-READBACK`。十二来源整体仍为 `10/12`；P03 与 P07 最新自然运行保持 failed，不因本收据改判，也不授权 BI-W10-02、外部效果或发布。

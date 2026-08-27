# BI-W10-01 修复加载后自然运行 P01 只读检查点

- 核验时间：`2026-08-27T18:06:31Z`（上海时间 `2026-08-28T02:06:31+08:00`）
- 租户：`org-org/dev-project`
- 代码：`aos-platform/m1@60e0c3ef`
- 运行边界：只读查询 `meta_schedule_run`、对象/投影聚合与 DLQ 元数据；未人工触发 Pipeline，未重放 DLQ，未修改业务数据，未执行 Provider、迁移或发布。

## 新自然运行事实

| Pipeline | startedAt | status | rowsWritten | errorCode |
|---|---|---:|---:|---|
| `P01-shop-qyh` | `2026-08-27T18:00:04.481042+00:00` | `succeeded` | 1 | 空 |

该运行晚于修复后 API/自然 Cron worker 重载时刻 `2026-08-27T10:48:58Z`，可作为当前代码加载后的新鲜 P01 运行事实。P02～P12 的 latest run 仍属于上一自然序列，不能与本 P01 合并宣称同一新截止面 GREEN。

## 同次只读对账

- `Shop` source count=`1`，projection count=`1`，unexplained delta=`0`。
- `org-org/dev-project` 的 12 类 source/projection 聚合计数逐类相等。
- `dev-org/dev-project` canary：source=`0`，projection=`0`。
- P01 没有产生新的失败 error code；既有 DLQ 历史不删除、不重放，也不因本次成功而改写。

## 当前裁决

`P01_POST_RELOAD_NATURAL_RUN_GREEN / BI_W10_01_SEQUENCE_IN_PROGRESS / NO_EXTERNAL_EFFECT / NO_RELEASE`

正式 BI-W10-01 仍需 P02～P12 在当前修复加载后的各自自然计划点形成新 run，并逐项对读 latest run、DLQ 与 SourceReadiness。下一检查点为 P02 上海时间 03:00 自然运行；禁止人工执行或用旧 run 补齐。

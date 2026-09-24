# W5c4o disabled definition rev2 续期方案（2026-09-24）

W5c4n `615f8308` 的 12 最新 Binding 指向 rev2 Control/Selection，旧 definition `38c5d08c-ee40-4167-b129-8f95276e0c7a` 仍 disabled rev1/current member12，schedule off。新 key `a0v-w5c4o-disabled-definition-renewal-20260924-v1`。

1. 只读核新 Binding、旧 definition exact rev1/hash、Host/三 held、窗口/预算、业务/canary/attempt、schedule off；从正式 `SnapshotScheduleService.options` 取得当前 12 memberRef 与唯一 policyRef，必须与 W5c4n 一一匹配且被本定义占有；新 key0。
2. 0600 intent 固定原 definition ID、expectedRef rev1、原 cron/唯一 policy、12 最新 memberRef 和 key；经原 `configure` 调用一次，立即保存结果。未知结果冻结，按 key/head 只读对账，不重复调用。
3. 独立审计定义 rev2/state disabled、12 current members=新 Binding、12 schedule off、业务不变。verification/commit。下一波才可单独审启用条件；不得在本波 enable/手工 Run/读商城源行。

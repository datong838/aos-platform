# Recoverable Store 续窗 request identity 修复方案

## 1. 问题与边界

- 累计回归的两个真实 PostgreSQL 场景证明：原 Store 已部分提交且应答丢失后，同一
  installation/generation/epoch/group 在新控制窗恢复时被 `recoverable runtime attempt request drifted` 拒绝。
- 现有 hash 包含每次续窗必然变化的 recovery ref、current definition ref 和 control refs。这些是
  当前执行授权，不是原幂等 Store 工作的业务身份。
- 当前 AM 仍 running；本修复不重启、热替换、终止或重发 AM，仅保护之后的合法恢复。

## 2. 身份规则

1. attempt 数据库分区继续固定 tenant、installation、generation、execution epoch、operation key。
2. request hash 升为 `aos.recoverable-store-attempt-request/v2`，首跑与续窗恢复共用同一 helper，
   只包含两条路径共同持有的原始冻结业务身份：tenant、group、actor、original source claim hash、
   input manifest hash、exact policy ref 的 content hash 和排序后的 12 个原 run id。source claim hash 已经内含原
   controls/drafts/runs 的完整 binding。
   这里不能使用 assessment 的语义 hash：它是规范化策略文档的 hash，而续窗 recovery receipt 保存的是
   已通过当前权威校验的导出文件 exact ref；首跑和恢复必须共同使用 exact ref 的 content hash。
3. current recovery ref、current definition ref 和 control refs 仍必须通过
   `attempt_target_current` 和 `run_current` 的当前权威检查，但不改变同一 Store 工作的 request hash。
4. 历史 v1 attempt 不做宽松兼容；若存在旧 hash，仍按 drift fail closed，走正式 retire/direct successor。
5. Store Receipt 缺失不是重发许可；未知结果仍必须先查原 key。

## 3. 文件级清单

- `services/aos-api/aos_api/pipeline_snapshot_group_completion.py`：仅替换 recovery attempt request hash 的
  canonical payload，不改 claim、heartbeat、settle、Store 或 completion 顺序。
- `services/aos-api/tests/extension_runtime/test_snapshot_group_recovery_runtime_pg.py`：现有 running/stopped-failed
  部分 Store 提交恢复场景作为 Red/Green 主证；补查两个 attempt 的 request hash 相同。
- 只精确 stage 上述 hunk 和本波证据，不夹带相关文件内已有未提交施工。

## 4. 验证与退出

1. Red 为现有两分支均报 request drift；Green 必须两分支都完成且恢复后再次调用为 replay。
2. 断言同 operation 的第一个 failed attempt 与第二个 succeeded attempt 的 request hash 一致；Store
   只使用原 idempotency key 返回既有结果。
3. 恢复 authority、link/retirement/completion 相邻回归、静态编译与差异检查通过。
4. dev-org 零副作用，AM 现场边界不变，浏览器门禁仍独立判定。

## 5. Red / Green 实绩

- 原累计回归 Red：running、stopped-failed 两路均在续窗恢复时抛出
  `RuntimeConflict("recoverable runtime attempt request drifted")`。
- 第一版只缩减 recovery payload 仍为 Red，因为首跑和恢复使用两套算法。
- 第二版共享 helper 仍为 Red；复核确认首跑使用规范化策略语义 hash，而 recovery Receipt 只能取得已经过
  exact ref 校验的导出策略文件 hash。
- 最终最小修复让两路共同使用 `current.policy_ref.content_hash` / recovery `policyRef.contentHash`，并把
  canonical 字段明确命名为 `policyContentHash`。
- 真实 PostgreSQL 主证：running 与 stopped-failed 两路 `2 passed, 7 warnings in 1788.78s`；测试同时断言
  首笔 failed attempt 与第二笔 succeeded attempt 的 request hash 完全一致，恢复后再次调用命中 replay。
- 相邻 attempt/Lease 回归：`11 passed, 3 skipped, 35 deselected`；静态编译和 `git diff --check` 通过。
- 浏览器只读复验：AOS v1.6.5 正常加载；电商工作台仍为“暂无可见工作台入口”，没有点击重读，门禁继续
  NOT GREEN。

## 6. 提交边界说明

`pipeline_snapshot_group_completion.py` 中被修复的逻辑位于尚未提交的 recoverable Store parent feature 内；
单独把四行子修复提交到当前 HEAD 会形成缺少 a0v084-a0v088、attempt Owner 与 transfer chain 的不可运行提交。
因此本波先提交完整方案、Green 证据与现场状态；代码 hunk 保持在 m1 单写者工作树，下一波先清点并验证 parent
feature 的最小闭包，再与本修复一并提交，禁止为了“有 commit”制造破损中间态。

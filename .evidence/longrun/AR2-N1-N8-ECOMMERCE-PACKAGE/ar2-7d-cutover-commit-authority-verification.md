# AR2-7D D5B 整组切换 commit 权威验证

日期：2026-09-09
基线：`m1@2e9ee8c8`
结论：`AR2_7D_CUTOVER_COMMIT_AUTHORITY_GREEN_CLAIMS_REMAIN_PAUSED`

## Rules 与验证结论

- 以 closure manifest、231-6 D5 和 D5B 施工方案为权威；m1 单人串行、先方案后编码、隔离 PostgreSQL、证据后提交；不 push，230 L0 挂起。
- 新增 tenant/group claim gate。pause 是独立、可回读提交：它先与 runtime attempt insert 的共享锁串行化，再把 target runtime 推进为 disabled/fenced revision N+1；gate 可见前 dispatch 仍为 legacy，gate 可见后 occurrence claim 与新 runtime attempt 均被阻断。commit 后 gate 继续 paused、runtime 继续 fenced，D5C 验证前不会自动进入执行。
- commit 仅接受 exact prepare Receipt；再次锁定并验证九项旧快照、目标 runtime、Approval/Proposal/draft/payload，重新读取 occurrence/dispatch attempt/runtime attempt。claimed/running 和 prepare 中非空 pending target Receipt refs 均阻断；UNKNOWN 只记录 reconcile-only 身份，不改状态、不重放。
- 九项 dispatch 只由固定 SECURITY DEFINER 函数一次更新；函数自行执行上述数据库权威检查。任一行漂移更新数不等于九，整事务回滚；成功后九项均为同 installation/generation/epoch/group revision。
- pause/commit 状态变化受 deferrable history trigger 约束；直接调用函数但不写对应不可变 Receipt 时，事务提交失败，gate、状态和九项 CAS 一并回滚。
- 当前生产 Router factory 不注册 legacy compatibility service；legacy 指针在本阶段是 fail-closed，因而没有该 Router 可接受但未登记的旧业务调用。若未来增加 legacy compatibility service，必须先新增持久 attempt Owner 并纳入 drain，不能复用本结论放行。

## 实现与方案一致性

- `services/aos-api/alembic/versions/ar2_014_ecommerce_growth_cutover_commit.py`：新增 claim gate、pause/commit 受限函数、审批三表锁、事件/Receipt 扩展和延迟历史约束；pause 原子设置 target runtime disabled/fenced，普通 runtime 只获得 gate SELECT，dispatch/runtime UPDATE 未向普通或 maintainer 角色开放。
- `services/aos-api/aos_api/ecommerce_growth_cutover.py`：新增严格 commit 请求与 phase Receipt，实施 begin/pause、当前事实快照、drain 门、九项 CAS、9/9 读回、事件/Receipt/拆列重验和稳定 replay。
- `services/aos-api/aos_api/automation_occurrence_store.py`：仅在 `claim_next` 候选 SQL 增加组级 paused gate 条件；创建、结算、过期转 UNKNOWN 和 Receipt reconcile 状态机未改变。
- 两个 PostgreSQL 测试文件改为读取既有 18434 环境参数，旧默认值保留；旧 occurrence fixture 只补最小 gate 表与 schema 参数，不绕过生产迁移验证。

## 测试证据

- D5A+D5B cutover 与 occurrence PostgreSQL 专项：`27 passed, 7 warnings in 7.07s`。
- Router/Host/occurrence 非 opt-in 邻接：`39 passed, 7 warnings in 2.81s`。
- 完整 `tests/extension_runtime`（未开启 PostgreSQL opt-in）：`741 passed, 496 skipped, 7 warnings in 20.14s`。
- Alembic：单一 head `ar2_014`；自有 schema 实测空迁移 downgrade 可恢复 ar2_013 约束，非空 gate 阻断 downgrade。
- Python compile、`git diff --check`：通过；当前环境未安装 ruff，未将“未执行”记为通过。
- Closure：`1708 scanned / 93 classified / 57 migrated`；`hashErrors`、正反向未分类依赖、跨层 import、动态引用错误均为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。

## 关键反例

- gate paused 时 pending occurrence 无法 claim；测试手工打开 gate 后同一 occurrence 才可领取。
- active occurrence claim/dispatch attempt 阻断 9/9 CAS；转 UNKNOWN 后只保留原 attempt 并允许切换，未再次调用 handler。
- pause 会等待并发 runtime attempt 的共享锁；该 attempt 提交后 pause 才落 disabled/fenced 屏障，随后 commit 能稳定枚举并阻断。running attempt 进入明确 terminal 后才允许提交。
- prepare pending target Receipt refs 非空时阻断，九项仍为 legacy。
- pause 后任一 dispatch revision 漂移时 0/9 切换。
- runtime 角色不能调用 commit 函数；maintainer 直接调用但缺 pause/commit Receipt 时，延迟约束在提交点回滚全部变化。
- pause Receipt 或 event/hash/request/prepare ref 漂移在 replay 时失败关闭；审批状态漂移由 Python 与 commit 函数各自独立拒绝。
- commit 成功为 9/9 `extension`、revision 5→6、group revision 11→12，claim gate 仍为 paused、target runtime 仍为 disabled/fenced；相同请求稳定重放同一 Receipt。

## Red/修复轨迹

- 首次新 claim 回归因测试 runtime 角色缺自有 schema USAGE，出现 1 failed/17 passed；只补 fixture schema 权限后转绿，生产权限未放宽。
- 一次邻接命令遗漏 `AOS_DATABASE_URL`，39 项在 setup 误连 5433，零测试逻辑执行；补既定 18434 DSN 后 39 passed。
- SQL 完整审批自证初版 CASE 表达式缺括号，Alembic head setup 语法失败；修正后全迁移链通过。
- Python 直接 `FOR SHARE` Approval/Draft 需要 UPDATE 权限，18 项正确暴露权限不足；没有扩大 maintainer 表权限，改为增强既有受限 definer 锁函数同时锁定 Approval/Proposal/Draft，再由只读查询重验。
- 锁等待跨 expiry 的错误文本一度变化导致 1 项断言失败；恢复明确 `active exact` 原因码路径，未改变门槛。
- 静态复核继续补齐 nullable impact/source 三列一致性、phase event 回读、claimed attempt 独立枚举，以及直接函数调用必须具备同事务 Receipt 的延迟约束。
- 首个并发 attempt 回归证明仅在 commit 函数内等待 runtime 锁仍会受 SERIALIZABLE 旧快照影响并错误放行；改为 pause 原子设置 runtime fence 后，既有 attempt insert guard 成为入口屏障。中间两轮分别暴露不存在的 `updated_at` 列和 `enabled=true + fenced=true` 表约束冲突，最终按既有 runtime 合同采用 `enabled=false + operation_fence=true + revision+1`，未放宽约束。

## 内容摘要与保留边界

- `ecommerce_growth_cutover.py` SHA-256：`b880331cb0eaa9ba61cbd8232aa3e99dfad8302e865b164879930af8f3401d66`
- `automation_occurrence_store.py` SHA-256：`0dbc96fb79a999d04ee21b5ed7376a4606f46d8a16fa9a15e5fff61b8ccee234`
- `ar2_014` SHA-256：`d6d61f35664a70596d29250e6957019f510d90d105c5dc55a7d0a92973b6fbac`
- D5B 只完成 activation commit 权威；claim 仍暂停且 target runtime 保持 disabled/fenced。D5C 还需受控 9/9 新入口验证、失败时保持 fence 并做 0/9 rollback CAS、UNKNOWN/新 epoch 排空、成功后显式恢复 runtime 与 claim。
- 未执行任何真实 cutover、真实租户写入、共享/生产迁移、真实源读取、Provider、费用、发布或 push；AR2-7D 与 AR2 整波仍未封板。

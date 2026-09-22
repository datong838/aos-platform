# W2 业务恢复波 — verification (2026-09-23)

## 结论速览

| 步骤 | 状态 | 结果 |
|---|---|---|
| 1/6 budget 续租 | ✅ 完成 | rev12 发布，24h 窗口至 2026-09-23T16:17:45Z |
| 2/6 attempt_target 重放 | ✅ 完成（否定发现） | 旧冲突消失，暴露新结构性冲突 |
| 3/6 解卡 12 僵尸 run | ❌ **结构性阻断** | 平台无合法「running→failed」收敛通道 |
| 4-6 definition 启用/dispatch/浏览器验收 | ⏸ 未执行 | 被 3 阻断，执行无意义 |

## 第 1 步：budget 续租 GREEN

- evidence profile 修正：`text-readiness-v2`（plan.json 实锤，legacy-v1 全组合不匹配）
- evidence 过期（`EVAL_EVIDENCE_OUTSIDE_WINDOW`：09-20 19:55 + 24h < 当前）→ 全新目录重生成
- attempt1 瞬时失败（source case UNCLASSIFIED，探针直调验证 healthy 归档保留）；attempt2 三 case 全 PASS（77/80/84 tokens）
- 冻结 plan：`planHash 95ae0eee…`，budget rev11→12，expected versions 全对齐
- apply：model/route rev11 + 双 eval gate（`gate-1c546fad…`/`gate-ace4829b…`）全过
- evidence 目录：`.aos-recovery-20260920/state/q-advisor-baseline/br-text-governance-renewal/text-evidence-20260923-v2`
- plan/apply 落盘：`replacement-dq/w2-budget-renewal/plan.json` + `apply-result.json`

## 第 2 步：重放验证 — 治理耦合实锤

续租后重放（`a0v_rc_conflict_replay.py --json`）：

| 阶段 | W1（续租前） | W2（续租后） |
|---|---|---|
| attempt_target | `recovery definition is not current enabled authority` | 同（head 268 disabled，预期内） |
| relationship_read | 同上 | 同 |
| link_command_read | 同 | 同 |
| projection_completion | `budget policy is not effective` | **`runtime policy reference is not current and exact`** |

**结构性事实**：续租推进 runtime policy head rev11→12 + budget head rev12；恢复链（receipt 88 → definition 267 → control refs rev2 → source selection → configuration）内嵌的治理 refs 冻结在 rev11。`aip_runtime_configuration_sources._load_runtime_policy` L359 要求 `current_revision == value.revision`。

**推论（治理-恢复死锁定理）**：budget 按日续租 → 治理 head 每日前移 → 任何冻结 >24h 的恢复链 refs 必然失配。字母链若继续「续租→重试恢复」只会无限复现此冲突。

## 第 3 步：僵尸组死锁全景（全库只读测绘）

组 `c5ff1926-45b0-56de-b6b3-07d5b7d053a1`（claim 冻结 2026-09-17 01:38:57）：

| 事实 | 值 | 含义 |
|---|---|---|
| 12 runs 状态 | `running / executor_id='' / stopped=false / finished=null` | 被认领但**从未执行** |
| schedules | 12 全部 `enabled=false` | DQ 暂停时关停 |
| source_claim / ingress_command / derived_command / dataset_receipt | 各 **12** | 组已接受 + **source 效应已写** |
| group_claim / group_input / link_command | 1 / 1 / 1 | 组链完整 |
| closure_receipt | 0 | 尚未（也无法）关闭 |
| definition head | 268 disabled（installation d2d3c478…，gen b15f1733…） | DQ 权威链 |
| recovery receipt | rev88（executor `a0v-ecommerce-growth-1.4-runtime-owner`） | 冻结 rev11 治理 refs |

### 全部收敛通道逐条排除

| 通道 | 要求 | 结果 |
|---|---|---|
| `claim_failed_run`（ec_ingress_claim L28） | run = failed+stopped+finished | ❌ runs 是 running |
| `_persist_schedule_result` | 只有执行器自身调用 | ❌ 执行器不存在（executor_id=''） |
| `pipeline_snapshot_unaccepted_group_close_a0v_083` | **全部 effects 表 = 0** + runs 干净 + head disabled 链 | ❌ effects 全非 0（`snapshot group accepted or has source effects` 必中） |
| `ecommerce_unaccepted_analysis_close_a0v_060/082` | — | ❌ 不碰 meta_schedule_run |
| definition `retire`（definition.py L241-244） | 无 running/unknown runs | ❌ 12 running 挡 |
| definition `enable` | — | 无意义：dispatch 被 pending 挡 + worker 撞过期 refs |
| pg_proc 全函数扫描 | — | **无任何「running→failed」收割函数** |

### 死锁定理

```
执行器死亡（或从未启动）
  + 唯一终态写者 = 执行器自身（无看门狗/租约收割）
  + unaccepted_closure 要求 effects=0（本组 effects≠0）
  + retire 被 running runs 挡
  + current_member 占用挡新 definition 复用 12 schedules
  = 12 schedules + 1 definition + 1 group 永久锁死
  = 治理续租（每日）与恢复链冻结（rev11）结构性失配
```

## 对上位方案的修正

- W2 plan 第 3b 后备路径（`claim_failed_run` 状态收敛）**不可达**——其前置终态本身无写者。
- RC 波结论「先根因后恢复」正确，但根因比 IngressJournalConflict 子码更深一层：**平台缺失 executor-death 收割通道**（产品级缺陷，非数据问题）。
- 「不手改库」纪律下，本波到此为止。

## W3 建议（下一波清单）

1. **平台补丁：stalled-group 收割通道**（产品代码，非数据操作）
   - 新 maintenance DB 函数（仿 `unaccepted_group_close_083` 的 SECURITY DEFINER + SERIALIZABLE + admin 校验模式）：`pipeline_snapshot_stalled_group_close_a0v_084`
   - 前置校验：runs running + executor_id='' + 效应表**快照在案**（不要求为 0，但要求 link_command/derived_command 一致性 hash 已冻结）+ definition head disabled + 治理 refs 过期证明
   - 效果：runs → failed+stopped+finished（error_code=`EXECUTOR_NEVER_STARTED_STALLED_GROUP`）+ closure receipt 落盘（区别于 unaccepted：`STALLED_AFTER_SOURCE_EFFECTS`）
   - 需：源码 + SQL 迁移 + 单测 + 评审（走 D-waves 登记）
2. **retire 解锁**：收割后 12 runs 终态 → retire definition cb0dba8c → 释放 current_member 占用
3. **新 definition + 恢复自然 dispatch**：新 definition（新 UUID，同 12 schedules，刷新 control/selection/治理 refs 到 rev12+）→ enable → worker 自然 dispatch → 12/12 succeeded
4. **浏览器验收**：调度页 12 schedule enabled + 最近 run succeeded 截图
5. **回归**：BG-01→BG-04 主线恢复；797 字母脚本归档提案

## 证据文件

- `scripts/a0v_w2_policy_ref_survey.py`（新建，只读测绘）
- `replacement-dq/w2-budget-renewal/plan.json` + `apply-result.json`（续租权威记录）
- `br-text-governance-renewal/text-evidence-20260923-v2/`（新鲜 evidence）
- `br-text-governance-renewal/text-evidence-20260923-attempt1-transient-failure/`（失败证据保留）

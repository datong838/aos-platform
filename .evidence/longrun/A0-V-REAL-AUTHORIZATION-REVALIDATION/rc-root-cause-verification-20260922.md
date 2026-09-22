# RC 根因定位波 — verification (2026-09-22 23:5x)

## 结论（一句话）
字母链 64 次 `IngressJournalConflict` 的结构性根因是：**恢复链的每个权威校验点都要求「当前恢复上下文与 09-17/09-18 冻结的原始 claim/journal 完全一致」，而每波"换新 installation 重试"恰恰改变了上下文（binding/definition revision），于是在 attempt 内 90 秒内的某个校验点必然撞死；attempt 表不落子码导致 77 波无人知道具体死点，只能盲改重试。**

## 连库实锤证据链
1. **12 个僵尸 run**（group `c5ff1926…`）：全部 `status=running`、`executor_id 为空`、`executor_stopped=false`、`finished_at NULL`，自 2026-09-17 01:39 UTC 冻结至今；claim 绑定**已退休安装 `277fe01c` / gen `f576ea28`**（09-17 01:39:03-05 批量认领，actor=a0v-ecommerce-growth）。
2. **attempt 侧**：64 个 failed 全部 `terminal_error_type=IngressJournalConflict`、`terminal_reason_code=RECOVERABLE_EXECUTION_EXCEPTION`，每次耗时 1:20~1:50；每波换新 installation（60+ 个不同 inst）各试一次即 fail；retirement journal 0 行（死在 retirement.prepare 之前）、link command journal 1 行（09-18 05:51 冻结，1168 links，store 侧 0 落地）。
3. **outbox**：1741/1741 全部 projected，0 积压——排除「投影积压」假设。
4. **只读重放**（`scripts/a0v_rc_conflict_replay.py`，当前暂停态下）：
   - `[receipt] OK rev=88`
   - `[definition] OK state=disabled`（当前暂停态）
   - `[attempt_target] CONFLICT ValueError: recovery definition is not current enabled authority`
   - `[relationship_read] / [link_command_read] CONFLICT 同上`
   - `[projection_completion] CONFLICT PermissionError: budget policy is not effective`

## 根因结构图
```
每波脚本 enable definition → 唯一自然 attempt（90s）
  └─ attempt 内校验链（_route→attempt_target→relationships→link→retirement）
       ├─ A. definition/binding 与冻结 claim 上下文一致性校验
       │     （每波换 install → binding revision 变 → 撞 *_DRIFT / *_CHANGED 子码族）
       ├─ B. 12 run 状态校验：全部 running-not-stopped 中间态
       │     （_route 只认 all-running 或 all-failed-stopped；中间态两条路都进不去）
       └─ C. attempt 失败 → 字母链脚本 disable definition → 下一波
            （= 每波自己制造下一波的 "not current enabled authority"）
```
- **子码黑洞性**：attempt 表无 `terminal_error_detail` 列 → 77 波无人知道子码 → 违反 231 §7 的循环得以持续。
- **预算独立障碍**：`budget policy is not effective`（aip_runtime_configuration_sources 守护策略 effective_until 过期）是第二条独立故障线，恢复前需单独处理。

## 与初心的对照
- 字母链 = 231-9 BG-00 的脚本侧入口验证；BG-01~11 零开工。
- 12-OT 业务数据管道自 09-17 冻结 5.5 天——首链（BG-02/03/04）依赖的「真实数据自然触发」第一环已断。
- 业务影响：`meta_schedule` 12 条 schedule enabled=False；最后一次成功同步 09-17 00:18 UTC。

## 下一波（W2）任务清单
1. **解卡 12 僵尸 run**：走 `claim_failed_run` 合法路径（INGRESS_STOPPED_FAILED_RUN_REQUIRED 线），不改库——需要先以恢复权威身份将 12 run 转 failed+stopped+finished（通过 products API 的 runtime 恢复入口，不用 SQL）。
2. **budget policy 续期**：找到 budget guard policy 的 effective_until 并通过权威 API 续期（或确认它是否依赖 DQ 安装的运行时配置）。
3. **DQ recovery 走 UI**（BG-00 收口）：经产品入口（workshop/definitions 页面）enable definition 268→natural attempt→观察；不再用脚本直接操作。
4. **797 字母脚本归档**：`scripts/a0v_[letter]_*.py` → `scripts/archive/letter-chain/`（git mv 保留历史），保留 `a0v_rc_*.py` 与非字母 a0v 工具。
5. **三 worker 同步 m1**：w1-aip / w2-workshop / w3-data-readiness merge m1（当前分别落后 681ebdc7 / fec03c99 / c308707b）。
6. **回 BG 主线**：BG-01 首登记 → BG-02 自然触发首个 Case/Run（依赖管道复活）。

## Receipt
- 本波零写操作（services/ 零改动；DB 只读；git 仅新增 evidence 两文件 + 一个只读脚本）。
- 只读脚本：`scripts/a0v_rc_conflict_replay.py`（可重复执行，幂等）。

# RC 根因定位波 — plan (2026-09-22)

## 上位方案复习
- 字母链 77 波（AP→DQ）同因循环：每波换新 installation 重试同一 `snapshot-group-completion` 操作，64 次 attempt 全部 `IngressJournalConflict`，**子码从未落库**（`extension_runtime_execution_attempt` 无错误详情列）。
- `ap-direct-successor-verification-20260919.md` 自认根因未查明即续跑——违反 231 §7 铁律「同一问题最多两次同路径尝试后进入根因定位」。
- 本波为 231 §7 义务的偿还：只读定位，零写操作，产出确切子码与死点。

## 本波文件级清单
1. `scripts/a0v_rc_conflict_replay.py`（新建，只读）：在回滚事务内重放 `resume_saved` 的校验前缀（receipt→definition→bindings→attempt_target→relationship→link_command→projection_completion），捕获 IngressJournalConflict 确切子码。
2. `.evidence/.../rc-root-cause-plan-20260922.md`（本文件）+ `rc-root-cause-verification-20260922.md`。
3. 零代码改动（services/ 不动）。

## 退出条件
- 能一句话说出冲突对象与产生条件；
- 只读重放输出各阶段 OK/CONFLICT 清单；
- 不改变任何权威状态（definition/binding/attempt 均不动）。

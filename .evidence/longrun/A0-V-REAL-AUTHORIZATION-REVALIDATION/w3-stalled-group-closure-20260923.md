# W3 平台补丁波：stalled-group 收割通道（2026-09-23 00:50 封板）

## 波次结论

W3 全 GREEN。A0-V 恢复库新增 stalled-group 收割通道（a0v_091），僵尸组 c5ff1926 十二个 run 合法终态化，dispatch pending 归零。

## 交付物清单

| 文件 | 类型 | 作用 |
|---|---|---|
| `services/aos-api/alembic/versions/a0v_091_snapshot_stalled_group_closure.py` | 迁移 | 新表 `pipeline_snapshot_stalled_group_closure_receipt` + 函数 `pipeline_snapshot_stalled_group_close_a0v_091` + trigger `snapshot_stalled_group_terminal`（与 083 trigger 正交：只拦新错误码） |
| `services/aos-api/aos_api/pipeline_snapshot_stalled_group_closure.py` | 服务 | `StalledSnapshotGroupClosureService`（SERIALIZABLE + maintainer 角色 + receipt readback 校验，镜像 083 模式） |
| `services/aos-api/aos_api/pipeline_snapshot_schedule_dispatch.py` | 修改 | inspect SQL 增 LEFT JOIN stalled 收割表 + `g.group_id IS NULL`（3 行改动） |
| `scripts/a0v_snapshot_stalled_group_closure_deploy.py` | 部署器 | 备份→迁移→函数回读校验（deploy result：migrationHash `f3324716…`，备份 14MB） |
| `scripts/a0v_w3_stalled_group_close.py` | 执行器 | prepare/apply/audit 三段式 |

## 收割执行记录

- **prepare GREEN**：12 run（earliest 09-17 01:38:57，均 stalled>24h）、original ref rev2 / current head rev268 disabled、效应如实记录（groupClaim 1 / input 1 / member 12 / sourceClaim 12 / ingress 12 / derived 12 / dataset 12）
- **apply GREEN**：receipt `54fbf214-c7cb-48ff-a19b-4c3948551201`，requestHash `b6ca0cbc…`，contentHash `0f6c4e7a…`，12 run → failed/`STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS`/finished/executor_stopped
- **audit GREEN**：stalled=0 / closed=12 / canary(dev-org)=0；12 schedule 的 last_run 更新为新 failed 终态
- **dispatch 排除验证**：pending 组 1 → 0（僵尸组不再阻塞新 dispatch）

## 设计决策记录

1. **reasonCode `STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS`**：与 083 的 `SOURCE_BUDGET_REJECTED_BEFORE_GROUP_CLAIM` 正交，两者 trigger 互不干扰
2. **不要求效应为零**：与 083 相反，本函数接受“组已接受+效应已写”的僵尸组——效应如实记入 receipt（effectEvidence），不做删除
3. **staleness 证明**：12/12 run `started_at < now-24h` + `executor_id=''` + schedule disabled + definition head disabled，四重条件
4. **不要求 original enabled**：字母链期间 original rev2 已被多次链式 disable，只要求 head disabled（防止收割后立即再 dispatch）
5. **087 基座复用**：deploy 沿用 `a0v_snapshot_prior_recovery_anchor_deploy` 的备份/事务/校验骨架（monkey-patch 参数），alembic 单链 heads=[a0v_091] 校验通过

## W4 任务清单（下一波）

1. 新 definition（12 members，governance refs 刷新到 rev12+）→ enable
2. 自然 dispatch 观察（worker tick 15s；definition due 后建新组 claim，12 schedules 重新绑定）
3. 12/12 run succeeded 验证（数据链 P01-P12 真实跑通）
4. 浏览器验收（workshop 调度页截图：12 schedules 状态 + 新组 runs）
5. 回归 BG-01→BG-04 主线；登记 D-waves 清单（091 补丁 + W4）
6. 每日续租维持（budget rev12 窗口至 09-23T16:17:45Z，约 UTC 16:17 前）

## 遗留风险

- dispatch worker（Host 32752）尚未加载新 SQL（需 tick 重载或重启后生效；m1 代码与库 schema 已同步，重启无风险）——W4 首步验证 worker 是否已用新排除逻辑
- budget rev12 到期不续租则恢复链再次失配（每日续租纪律）

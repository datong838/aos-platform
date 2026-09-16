# Y5f-F4 同代次配置接续真实部署方案

日期：2026-09-16

基线：m1 `a7b82984`

Task Receipt：`SC4-5L6Y5F4-REFRESH-DEPLOY-20260916`

## 目标

把 F2/F3 已在隔离 PostgreSQL 验证的 a0v067/a0v068 精确迁移先部署到由主库 a0v066 一致快照恢复的新克隆，再在保全、ACL、RLS、不可变性和租户隔离全部通过后部署主库。随后只对 `org-org/dev-project` 执行一次独立 R2 maker-checker 审批绑定的同代次九路 dispatch 配置接续，并证明该接续仍可禁入、detach 和恢复。

这不是自然经营 Run。接续请求必须固定 `externalEffectsAllowed=false`、`resumeBusinessRuns=false`；不得读取商城源、启动 schedule/worker、发送消息、发布内容或触碰 230 L0。

## 固定控制路径

1. 由固定 clone executor 在主库只读、可重复读快照中导出 0600 私有备份，恢复到从未存在的新数据库；禁止覆盖或复用旧 clone。
2. executor 校验当前 HEAD、迁移文件和 executor 哈希、m1、有效 Task Receipt、主库唯一 head=a0v066、无迁移 advisory-lock 冲突。
3. clone 事务只允许执行精确链 `a0v067 -> a0v068`。已有业务表逐表行数与 canonical JSON 摘要迁移前后必须一致；新 Receipt 表必须为空。
4. 校验新表双租户强制 RLS、不可变/禁止 truncate、运行角色只读；校验两个安全定义函数 owner、PUBLIC/role EXECUTE、search_path 与返回合同。负向租户探针只在 clone 事务内执行并回滚。
5. 主库执行器只接受仍保持原样的 retained clone attestation 和备份哈希；重新导出主库一致快照备份，写入独占 intent 后才执行相同精确迁移。提交结果未知时只回读 head、schema 和 retained intent，不重新提交。
6. API 必须在确认主库 a0v068 后按当前 HEAD 重启；旧进程先记录、再停止、再启动，并验证 `/health` 与产品读取。

## 真实刷新前置条件

- 当前 installation/generation、runtime binding、最近 configure/enable operation、九路 dispatch 与最新 activation/refresh 链必须从主库只读重建，不使用过期证据推断。
- maker、checker、executor 必须是三个精确角色约束下的当前成员；checker 不能等于 maker；审批 payload 由 F1 canonical request 重算，不接受客户端自报批准。
- source revision/epoch/group revision 必须与九路当前值完全一致；target 必须等于已经 configure+enable 成功且 ready/unfenced 的当前 binding。
- 幂等键、request hash 和 approval ref 在 intent 中一次写定。未知结果只按原 key/Receipt 回读，禁止换键重试。
- `dev-org/dev-project` 只做零行可见性/零写入证明。

## 接续后的生命周期证明

真实 refresh Receipt、九路 target epoch/group revision 和旧 epoch 无新 claim 通过后，走正式 lifecycle Owner：fence -> drain/readback -> detach。任何 running/claimed/unknown occurrence 阻断 detach。随后按既有安装恢复路径恢复到可配置、可启用状态并核对最新 refresh authority ref，不启动自然经营 Run。

## 文件范围

- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/sc4-5l6y5f4-refresh-deployment-plan.md`
- `scripts/a0v_dispatch_configuration_refresh_clone.py`
- `scripts/a0v_dispatch_configuration_refresh_main_deploy.py`
- 后续真实接续固定 executor 与 F4 verification/JSON 证据
- `docs/palantier/AOS项目开发上下文/memory/leases.json` 中新增 Task Receipt

## 验收与停止规则

1. clone 必须来自当前 a0v066 主库新快照，迁移后既有业务指纹完全一致。
2. schema/ACL/RLS/immutability/SECURITY DEFINER 与 clone 负向租户检查全部通过；主库迁移前仍为 a0v066。
3. 主库 fresh backup、intent、事务内前后指纹与提交后 readback 形成完整证据；主库唯一 head=a0v068。
4. 真实刷新仅一次，九路原子同进同退；同 key 重放零二次变更；canary 零可见、零写入。
5. disable/detach/recover 证明配置可更新后仍可禁入、恢复、卸载重装；外部副作用与自然业务 Run 均为零。
6. 同一阶段相同根因失败两次、基线漂移、角色/审批不足、未知提交无法回读或出现非零外部副作用时立即停止真实动作并保留证据。完成后进入 Y5d/Y6d：由真实商城变化自然触发 Case/Run 与数字同事分析首链。

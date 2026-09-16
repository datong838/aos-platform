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
3. 第一轮 clone 事务只允许执行精确链 `a0v067 -> a0v068`。真实拓扑预检发现 event-control 共组后，第二轮从当前 a0v068 主库新快照只允许执行 069 scope fix。两轮已有业务表逐表行数与 canonical JSON 摘要迁移前后必须一致；新 Receipt 表必须为空。
4. 校验新表双租户强制 RLS、不可变/禁止 truncate、运行角色只读；校验两个安全定义函数 owner、PUBLIC/role EXECUTE、search_path 与返回合同。负向租户探针只在 clone 事务内执行并回滚。
5. 主库执行器只接受仍保持原样的 retained clone attestation 和备份哈希；重新导出主库一致快照备份，写入独占 intent 后才执行相同精确迁移。提交结果未知时只回读 head、schema 和 retained intent，不重新提交。
6. API 必须在确认主库 a0v068 后按当前 HEAD 重启；旧进程先记录、再停止、再启动，并验证 `/health` 与产品读取。

## 真实刷新前置条件

- 当前 installation/generation、runtime binding、最近 configure/enable operation、九路 dispatch 与最新 activation/refresh 链必须从主库只读重建，不使用过期证据推断。
- 2026-09-16 实时重建确认 J binding 与九路 dispatch 都仍在 revision 6 / epoch 3，尚不存在可接续的新 target。不得伪造 6→6 空刷新。先以当前四类权威来源重新签出同 configuration family 的 revision 2，走正式 configure/enable 把 binding 推进到新 revision/epoch；这次重签只更新内部配置 authority，不改变数据范围、预算、网络、角色或外部副作用授权。
- 首次复用首装 stage 入口生成了一个未绑定的新 family revision 1；它没有 configure/enable 权限且按不可变历史保留。正式 successor stage 必须显式提交当前 `e2fdde1f-ebdb-4863-b158-7204735f3fe8@1` 为 `previous_ref`，只接受同 ID revision 2。不得删除未采用候选或把它改写为成功证据。
- maker/executor 使用已经持有当前 installation apply 权限的固定 runtime owner，checker 使用独立 admin 成员且不能等于 maker；审批 payload 由 F1 canonical request 重算，不接受客户端自报批准。R2 只需一位独立 checker，不沿用 R3 cutover 的双 checker。
- 固定 executor 只能复用 `aos_ecommerce_registration_control` 保护身份及
  `scoped_cutover_connection(registration_connection)`；该登录必须保持
  `NOINHERIT/NOSUPERUSER/NOBYPASSRLS`，且只拥有
  `aos_runtime/aos_extension_maintainer` 两个无登录角色。禁止复用 Web、runtime worker
  或主库超级用户连接执行 Owner。
- ActionType 仅允许以正式 API 补建
  `ecommerce_dispatch_configuration_refresh`；若同 ID 的名称、对象类型或声明字段不同则
  fail closed。审批必须是该 canonical payload 的一位独立 admin checker，有效期覆盖执行时刻。
- source revision/epoch/group revision 必须与九路当前值完全一致；target 必须等于已经 configure+enable 成功且 ready/unfenced 的当前 binding。
- `ecommerce_growth_event_control` 即使与九路共用 group，也不属于 F1 固定 operation set；069 后它必须在 refresh 前后保持原 revision、epoch 和 group revision，不能被九路接续连带修改。
- 幂等键、request hash 和 approval ref 在 intent 中一次写定。未知结果只按原 key/Receipt 回读，禁止换键重试。
- `dev-org/dev-project` 只做零行可见性/零写入证明。

## 接续后的生命周期证明

真实 refresh Receipt、九路 target epoch/group revision 和旧 epoch 无新 claim 通过后，走正式 lifecycle Owner：fence -> drain/readback -> detach。任何 running/claimed/unknown occurrence 阻断 detach。随后按既有安装恢复路径恢复到可配置、可启用状态并核对最新 refresh authority ref，不启动自然经营 Run。

真实 J 预检补充：九路 refresh 后，event-control 按设计仍保留旧 epoch/group revision；旧 a0v054 只接受十路完全同 epoch/revision，无法表达“业务九路已接续、事件入口待独立退出”。a0v070 必须只在存在最新、有效 Refresh Receipt 时接受该过渡态：runtime binding 精确等于 refresh target，九路精确等于 refresh target epoch/group，event-control 精确等于 refresh source epoch/旧 group。fence 仍以组级 CAS 把十路 group revision 汇合并只围栏 event-control；shrink 在 drain 为零后按原组级 CAS 删除 event-control。无 Refresh 的旧路径保持原合同。

真实 fence 后排空补充：J 留有 12 条 `needs_attention/unknown` 的旧 epoch 初始化，逐条目标幂等键下业务命令 Receipt 和 Investigation Run 都为 0，必须走正式 UnacceptedAnalysisClosure，禁止直接改状态。旧 a0v060 又要求当前 runtime epoch 等于 fence/source epoch，无法表达 refresh 后 runtime 已在 target epoch 的合法状态。a0v071 只能在 fence Receipt 带有且精确匹配最新 Refresh Receipt 引用时接受：fence epoch 等于 refresh source、当前 runtime revision/epoch/config 等于 refresh target、九路/事件控制快照仍等于 fence afterSnapshot。其余原始事件、过期 unknown、零目标 Receipt/Run、不可变 closure Receipt 和旧无刷新路径保持原合同。

## 文件范围

- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/sc4-5l6y5f4-refresh-deployment-plan.md`
- `scripts/a0v_dispatch_configuration_refresh_clone.py`
- `scripts/a0v_dispatch_configuration_refresh_main_deploy.py`
- `scripts/a0v_j_configuration_successor_refresh.py`
- `scripts/a0v_j_dispatch_configuration_refresh.py`：固定重建、ActionType、审批、Owner、
  同 key 重放、正负租户回读；每个写阶段均先落 0600 O_EXCL intent，未知结果只进入 inspect。
- `services/aos-api/alembic/versions/a0v_070_event_control_after_configuration_refresh.py`：
  让 event-control lifecycle 只在最新 Refresh Receipt 证明的混合 epoch 过渡态下继续。
- `services/aos-api/alembic/versions/a0v_071_unaccepted_closure_after_configuration_refresh.py`：
  让未被业务接受的旧 epoch 初始化只在同一 Refresh/Fence 证明下正式闭包。
- F4 verification/JSON 证据
- `docs/palantier/AOS项目开发上下文/memory/leases.json` 中新增 Task Receipt

## 验收与停止规则

1. clone 必须来自当前 a0v066 主库新快照，迁移后既有业务指纹完全一致。
2. schema/ACL/RLS/immutability/SECURITY DEFINER 与 clone 负向租户检查全部通过；主库迁移前仍为 a0v066。
3. 主库 fresh backup、intent、事务内前后指纹与提交后 readback 形成完整证据；主库唯一 head=a0v068。
4. 真实刷新仅一次，九路原子同进同退；同 key 重放零二次变更；canary 零可见、零写入。
5. disable/detach/recover 证明配置可更新后仍可禁入、恢复、卸载重装；外部副作用与自然业务 Run 均为零。
6. 同一阶段相同根因失败两次、基线漂移、角色/审批不足、未知提交无法回读或出现非零外部副作用时立即停止真实动作并保留证据。完成后进入 Y5d/Y6d：由真实商城变化自然触发 Case/Run 与数字同事分析首链。

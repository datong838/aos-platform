# Y3c-1b 保存输入恢复回执持久化

收口：17项Receipt PG验证124.41秒，97项原守卫/控制/续期合同回归19.03秒（/tmp/aos-recovery-receipt-regression.log）通过，git diff --check通过。065只在测试隔离库迁移；主库061/主服务不变。当前表是历史事实存储，C2管理权限与saved-only领取围栏尚未实现、恢复执行未开放。方案已统一原观察/当前执行窗口的正确区别；下一波先完成066新周期禁入围栏，再接正式RecoveryOwner与API。

当前验收：新模块缺失Red；首轮11 passed/84.35秒，补充后14 passed/106.31秒，最终17 passed/124.41秒（/tmp/aos-recovery-receipt-complete.log）。真实隔离065库核验新连接读回、跨会话时区、重算hash的错误关联拒绝、已批准控制增预算拒绝、原source claim存在但无input拒绝、负租户RLS、原key唯一、temp shadow、精确前驱链及runtime/表所有者均不能UPDATE/DELETE/TRUNCATE。原输入来自具名模拟源一次，未恢复执行、未新增源读取。结构审查新增createdAt不晚于当前DB时刻、后继Receipt的新definition revision严格前进；body输出统一UTC，避免会话时区误报hash漂移。

后续C2详细接缝与saved-only围栏见sc4-5l6y3c2-recovery-owner-plan.md；尚未实现。C1b没有管理授权Owner/API，不能将该历史表当许可。纯合同涵盖的其他业务字段漂移不是每个都重复做一项PG用例；数据库统一对旧/新draft移除窗口和selection后做完整JSON等值比较，现已用真实增预算负例验证该路径，C2还要复核权限/代次与实际来源。

本波仅建立不可变Receipt存储与读/解码合同，不接恢复执行或授权API。承接C1a已验证的窗口差异合同；主库061不迁移，隔离库迁移到065后验证。

## 文件与存储

新增services/aos-api/alembic/versions/a0v_065_snapshot_group_recovery_receipt.py、aos_api/pipeline_snapshot_group_recovery_receipt.py、tests/extension_runtime/test_snapshot_group_recovery_receipt_pg.py。先完成结构与数据库负例，再接C2正式Owner；本波不提供绕过Owner的产品写入口。

单一pipeline_snapshot_group_recovery_receipt历史表，以org/project/group/revision为PK，保留previous_revision/hash FK链、每组idempotency key唯一、当前definition revision唯一。引用原schedule claim、原source group claim/hash、原input manifest/hash及同一definition family的原/新revision/hash。原/新definition成员表已经持久化全部十二binding，原schedule/source group成员已经持久化全部Run；不重复创建第二套member索引。Receipt body精确包含这些refs/hash、scope/group/revision/priorRef、manager actor、原executor、policyRef和createdAt、mode=saved-input-only；body与request均有canonical hash。

表强制RLS，runtime仅SELECT/INSERT；UPDATE/DELETE/TRUNCATE触发拒绝。使用原canonical_bundle_control_sha256和固定public schema，避免临时表遮蔽。恢复记录不可转移group/tenant/definition family，也不改变原控制、输入、业务回执或运行状态。

## 数据库关联校验

请求稳定性细化：request只绑定scope/group/manager、expectedDefinitionRef、expectedRecoveryRef、inputManifestHash及用户请求的新notBefore/expiresAt；不包含运行时生成的新definition hash/createdAt，避免提交响应丢失后重算新hash导致伪冲突。body绑定原/新definitionRef、三个原事实hash、requestHash和createdAt。request.expectedDefinitionRef须等于新definition.body.priorRef，expectedRecoveryRef须等于Receipt.priorRef；新十二控制使用同一请求窗口，原十二观察窗口分别验证。原始成员映射由两个定义的固定成员行与原claim成员共同确定，无需复制一张新member表。

1. 精确body/request形状与hash、scope/group/actor、前驱引用、original/current definition refs与列一致；原schedule record必须v2，其definitionRef必须等于original ref，executor必须与原claim/新旧定义一致。
2. 完整原source group count=12及input存在，输入manifest与原hash一致；原schedule 12 Run集合必须等于原source group 12 Run集合，不能挂另一组input。
3. 原/新definition为同installation/generation、同executor、同cron/timezone/policy，member schedule与pipeline集合完全相同；新definition必须是明确renew_saved_group请求，revision大于原，且Receipt与其新revision唯一绑定。原/新十二binding、control、selection同family后继，除notBefore/expiresAt/sourceSelectionRef外draft完全一致；起点不得前移，到期严格后移，窗口均≤24小时。
4. 原input采样起止必须位于每个原控制窗口；新控制共同窗口非空，但不要求覆盖历史采样时间。每个成员的source claim须匹配原控制与原Run。角色与实时安装权限、当前head/窗口有效、输入父信封完整语义由C2/C3原Owner逐事务复核，本表不是可离线使用的许可。

## 验证与后续

隔离完整PG正例保留原真实Owner生成的schedule/source claims/input（具名模拟源）；续期控制由原Selection/Control/Binding Owner追加。新definition测试夹具调用原_save，明确不代表正式恢复授权Owner已实现。测试插入后回读/新连接读取、幂等键/前驱、缺input、改hash且重新签hash、跨租户、错成员/源claim、改变budget/策略/代次/时间窗、UPDATE/DELETE/TRUNCATE与temp shadow拒绝。

C2必须增加saved-only定义领取围栏（原组恢复可以处理已存input，普通ScheduleClaim/SourceClaim不可据此创建新读取）；若恢复后要自然恢复周期，应由另外的明确配置启用/审批产生新版本，不能自动继承续期授权。C3将原观察group与当前执行group分开传递，C4状态恢复，C5完整回放，再进入Y4。任何尚未实现的项不得列为完成。

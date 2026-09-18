# SC4-5L6Z U 十二源新代权威与自然完整组方案

日期：2026-09-17

## 当前权威

基线 `d7157701`，m1 单写者，不 push，230 L0 挂起。U
`277fe01c-ece7-4c8f-9500-fc1ba0d5f050` 已完成九路 successor 切换，generation
`f576ea28-7c2b-4032-8b4c-9d196df6228e`，binding revision6/epoch3，ready/enabled/unfenced；
唯一 Host 持续续租。九路 routeRevision36/groupRevision63，S/T 退役，零在途、canary0。

S 的 definition rev9 已 disabled，历史 group/claim/selection/control 只作为审计，不得作为 U 的执行权威。
十二个 meta schedule 仍是同一租户的调度对象，必须保持 disabled；只把 ingest 固定为已有
`pipeline-live-v1`，由新的 U control binding 授权组调度器使用。

## 第 1/6：U current preview

新增 `scripts/a0v_u_twelve_source_snapshot.py`。复用只读 `a0v_snapshot_current_controls.preflight`，仅在
调用范围内将 installation/generation 固定为 U；要求 12 个成员、U active@5、binding revision6/epoch3、
当前签名 Niushop 1.23、来源配置和关系策略均可读、所有 schedule disabled。preview 不读商城行、不写权威。

## 第 2/6：schedule ingest 与十二套 control

逐 schedule 先读后写：仅当 disabled 且 ingest 不等于 exact `pipeline-live-v1/pipelineId` 时 PATCH 一次，
再 GET 确认；未知结果只读、不重发。P01-P12 全部为 U 新建 selection/control；每个 draft 的
installation/generation/epoch/config/package/source/graph/rowLimit/timeout/maxSourceCalls/有效期必须来自本次 preview。
schedule binding 使用最新 S binding 作为 previousRef，原子推进到 U control；每项独立 U 幂等键。

## 第 3/6：释放已卸载前代并创建 disabled definition

实现复核发现十二个 schedule 仍归属 S 的 disabled definition；Definition Owner 正确拒绝第二定义抢占。
新增通用的 released-retirement 守卫：只有旧定义 disabled、旧安装当前状态为 uninstalled、操作者仍是本租户
admin、且所有成员无 running/unknown 时，才允许通过原 transition 正式 retire；其他 retired 路径仍要求当前安装权限。
随后使用基于 U installation 的全新 definition id，读取 U options；要求 ready、12 members、关系策略非空，
并逐项核对 freshly confirmed binding。以 `* * * * *` 配置 disabled definition；不复用 S definition id/ref。
退休与新建各有独立不可变收据；若新建失败，schedule 仍 disabled，重跑只继续新建，不恢复旧安装权限。

## 第 4/6：自然 worker 执行

确认 18181 独立 snapshot API/worker 健康后 enable 一次。禁止直接调用 `run_definition`、手工写 group/run/claim
或改调度水位。允许因真实 MySQL/模型延迟等待多个 worker 周期；同一成员失败按原 recovery/重试合同处理，
不复制旧 claim。只接受一个属于 U definition/controls 的 group，12/12 succeeded，输入、claim、关系质量和
完成审计齐全。

若独立 worker 在 input manifest 已提交、组未完成时退出，只允许调用现有 `read_recovery_context` 与
`renew_saved_group`，为同一组生成 saved-input recovery receipt 并由 worker 自动续跑；不得重新读取商城源、
创建第二组或手工改变 run 状态。

### 系统重启后的真实恢复修订

首次 saved-input 恢复完成 2/12 后，承载 Host 的会话退出且 U 三项租约越过到期时间。新 Host 正确把
U binding 推进为 `unknown/fenced/epoch4`；两个仍可定位的 OCI 资源完成删除，growth 资源已在引擎中
消失但 journal 保持 `uncertain`。worker 命中 `runtime request is not currently admitted` 是预期拒绝，
不得改 binding、run 或 Receipt 绕过。

修复 `ExpiredResourceRecovery` 的确切缺口：普通 `remove_owned` 遇到 name 不存在仍返回 False，保持
create-time unknown 的既有安全语义；只有 recovery 已持有持久化 container id 时，新增 cleanup-only
双标识缺失确认，同时在同一固定 engine context 检查资源 name 与原 container id 均为 `no such`。
任一对象存在、身份不符、引擎错误或隔离检查失败都保持 uncertain。双缺失确认后仍由既有
`ResourceJournal.record_cleanup` 在 runtime role/租户事务内写 released，不允许脚本直改表。

三资源全部正式 released 后，通过原 Disable Owner 和九路 lifecycle 将 U disable/detach，再正式
处理 U runtime 前，先在 exact 原组、manifest 与 recovery Receipt 均存在且 U 已 fenced 的前提下，用
当前 definition ref 正式 disable 调度定义，避免 successor 恢复期间再次派发。随后建立干净 V
installation/generation，依次 apply、verify、configure、enable、successor
registration 与九路 cutover。V 为 P01-P12 新建 selection/control/binding，definition 推进到 V ref，
原 recovery Receipt 以新一 revision 续期。恢复执行仍只消费原 manifest
`sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，`sourceReads=0`。

### V saved-input 定义接管合同

普通 `configure` 继续永久禁止跨 installation/generation 转移。新增的
`transfer_saved_recovery` 只服务于同一未完成原组的灾难恢复，并以一笔事务推进 disabled definition：

1. definition 必须为 disabled，expectedRef 必须是当前 ref；原 claim、唯一保存输入和当前 recovery
   Receipt 必须属于同一 definition/group，manifest hash 不变，且组恰有十二个未结束原 run；
2. 前代 installation 必须仍是 active lineage head，但 runtime 已 disabled/fenced/unknown，三项持久化资源
   全部正式 released，并存在 exact disable succeeded 与 dispatch detach Receipt；
3. 目标 installation 必须是 active 的直接 replacement，composition lock 的
   `currentInstallationRef` 精确指向前代；目标 runtime 必须 ready/enabled/unfenced，九路 current dispatch
   全部指向目标 generation/epoch，且完成 prepare/commit/validate/resume Receipt；
4. 目标 P01-P12 binding 必须全部为当前 binding、同一目标 installation/generation/actor，schedule 集合与
   原 definition 完全相同，source group 仍为 canonical 十二源；操作者必须拥有目标当前配置权限；
5. 成功只生成同 definition 的下一 revision，状态仍 disabled，并原子替换十二个 current members；不创建
   group/run，不读取源。之后通过既有 `renew_saved_group` 生成 recovery rev2，再 enable definition；worker
   只能领取原 group 的 saved manifest。任何门槛不满足均整笔回滚。

数据库 head advance 触发器只为带有 `transfer_saved_recovery` 审计 intent 的相邻 disabled→disabled
revision 放行 installation/generation 改变；Owner 仍负责上述实时权威验证。head 同时更新新的
installation/generation，避免只换 revision 而留下旧权威身份。

接管后的 `renew_saved_group` 不把 rev5 当成普通同安装续租。Recovery Owner 必须先读取 rev5 的不可变
request，并精确确认 `intent=transfer_saved_recovery`、`expectedRef=rev4`、同 group、同 recovery rev1、
`settings=null`，才允许当前 definition 与原保存事实的 installation/generation 不同。旧 U controls 与当前
V controls 必须保持十二 pipeline、source、mapping、schema、mask、graph 和读取边界等业务语义一致；只允许
replacement 必然改变的 installation/generation/epoch/config/package、selection/control family 和执行窗口更新。
新续租 control 必须从当前 V control 派生并沿 V family 推进，不能从 U control 复制旧运行权威。

续租事务本身生成 definition rev6（enabled）和 recovery rev2，因此后续 `enable` 步骤只做只读确认，禁止再发
一次 transition。执行端识别 replacement recovery 时同样验证 transfer request，并以 V 当前安装权限和 V controls
消费原保存输入；普通同安装恢复仍沿用原有 family 连续性校验。

数据库 recovery receipt 的延迟完整性触发器也同步收窄扩展：普通 recovery 继续要求原/新
installation、binding、control、selection family 连续；只有 renewed definition 的直接前代是上述精确
transfer revision 时，才允许 family 更新，并改为校验原 U source claim 与最终 V control 的业务字段等价、
V identity 与 renewed definition 一致、窗口推进且 recovery priorRef 正是 transfer 中声明的 rev1。该迁移须先
备份并验证四类权威表指纹不变，不能通过脚本临时关闭约束。

### 重启后三资源健康时钟修复

V 的 Host 重启真实暴露了健康时间合同缺口：Owner 在三资源探测前读取数据库时钟，全部探测完成后才提交，
而数据库只接受三秒内的 health observation；探测耗时超过三秒会把健康资源误判为 stale，Host 安全退出，
随后租约自然到期并把 V 推进为 unknown/fenced。修复不扩大三秒窗口：探测前仍先读可信数据库时钟，阻止时钟
不可用时进行资源探测；探测全部成功后再读一次数据库时钟，以第二次单调且不早于第一次的时间作为 commit
observation。任一探测、二次时钟或单调性失败都不续租。

已经正式 fenced 的 V 不允许原地复活。修复验证后必须走与 U→V 相同的清理、disable/detach、direct replacement、
九路 successor cutover 和 saved definition transfer，下一代再生成 recovery rev2；不得直接改 binding 或 lease。

### W replacement 与九路接管实施

V 已通过原 Disable Owner 形成 operation `f822ddde-d122-47e5-ae43-ef2565594cb7`，其 detach Receipt
`229698c4-8653-49be-9280-a6653a91e7ab` 将九路恢复为 legacy routeRevision41/groupRevision68。W 必须以 V 为
direct replacement，经原 apply/verify/configure/enable 链达到 binding revision4/epoch3、ready/enabled/unfenced；
Host 的 apply operation revision 至少跨一个租约周期继续推进，作为双时钟修复的真实验证。

W successor registration 只能引用上述不可变 detach Receipt，并在租户零在途、W 三资源未释放、四项 lifecycle
operation succeeded 的条件下登记 groupRevision68。随后使用独立 operation/idempotency/policy namespace，依次生成
approve、prepare、pause、commit、validate、resume Receipt，把九路原子推进到 W，预期终态为
routeRevision42/groupRevision69；commit 完成路由推进，validate/resume 固化验证与恢复 Receipt，不再改 route revision。每相位先冻结 intent；未知结果只读 activation
history，禁止重发或直接改 route 表。完成 W 路由权威后才允许创建 W 的 P01-P12 controls 并转移 saved definition。

真实执行进一步暴露连续替换窗口：V 已把 disabled definition 从 rev4 转为 rev5，但在生成 recovery rev2 前再次
因租约过期退役；recovery rev1 因而仍指向 rev3，不能假装它已随 rev5 更新。Definition Owner 对第二次 transfer
必须沿不可变 revision history 回溯：当前每一层都必须是 `transfer_saved_recovery`、expectedRef 精确指向前一
revision、group 与 expectedRecoveryRef 全程不变、settings 为 null，最终锚定 recovery 声明的 current definition
revision/hash。只允许严格递减且无环的同 definition 链；任何普通编辑、断链、换组或换 Receipt 都拒绝。当前
drained predecessor、direct replacement、资源释放、九路路由和 controls 仍按本次 V→W 独立验证，历史 transfer
链本身不授予当前执行权。

数据库 delayed recovery Receipt 约束必须镜像相同链规则：从 renew 的直接前代开始，逐层要求 disabled transfer、
相邻 revision/hash、同 actor/group/recoveryRef，并最终落到原 enabled definition 所属 installation/generation；目标层
必须属于 renewed installation/generation。新增 a0v086 只替换约束函数，部署前备份并要求 definition/head/current
member/recovery receipt 四表指纹前后完全一致；不得临时关闭或绕过 a0v085 约束。

`renew_saved_group` 会为十二个 control/selection/binding 合法生成新 revision，因此 renew 后的只读 enable 确认不能再
拿 transfer 前冻结的 bindingRef 当作当前 options。该步骤只读取当前 runtime status 与 recovery context，并要求二者
共同指向 renew Receipt 声明的 enabled definition/recovery ref；transfer 与 renew 本身已分别完成旧 controls、当前
controls 和业务语义验证，确认步骤不重复授予权限或写入 transition。

W 的首轮真实续租进一步证明双时钟仍不充分：资源探测后的数据库时间虽然新鲜，但 renew transaction 在执行安装锁、
权限、lock package 与 current-condition 重校验后才调用 `_fresh_health`，远程隔离库的合法校验耗时可能超过三秒。
修复仍不扩大三秒窗口：事务先取得 installation、operation 和 binding 当前锁，确认它们仍是本 generation 的可续租
对象，随后立即以数据库时钟校验 `healthCheckedAt`；只有新鲜才继续同一事务内的 revalidator、资源注册、配置条件和
lease CAS。验证提交同样在取得 operation/binding 当前锁后、重校验前做 freshness gate。这样等待锁和资源探测都计入
三秒门槛，而锁内确定性重校验耗时不会把已经在提交入口被确认的新鲜探测误判为陈旧；任一后续条件变化仍整笔回滚。
已被围栏的 W 不复活，继续按正式 retirement 与 direct replacement 生成下一代并做跨周期续租实证。
W 围栏后若 saved definition 已处于 renew 生成的 enabled revision，须先验证原组仍是 12 个 resumable run、唯一保存
输入、recovery rev2、W binding unknown/fenced 且三资源全部 released，再通过 Definition Owner 将当前 ref 正式
disable；不得因 runtime 不可用而直接改 definition head。随后才能执行 W disable/detach 和下一代安装。

### X replacement 与修复实证

W 已由 Disable Owner 形成 succeeded operation `60b31712-982e-49bb-be8c-8a4294e87d71`，fence Receipt
`7f78dd96-8ac9-45bb-a81b-9746e43a6c4c` 与 detach Receipt
`0b079aa6-8233-45b2-9b9b-dcb661f376bd` 均为不可变权威；九路已回到 legacy
routeRevision44/groupRevision71。X 只能以 W active lineage head@5、binding revision9/epoch5 的
disabled/unknown/fenced 终态及三资源 released 为 direct predecessor。安装脚本固定读取上述 W disable operation
的 fence/detach phases，禁止复用 V 的 installation、generation、operation 或 route revision。

X 按正常 approved → prepare → verify → stage → configure → enable 生命周期建立；Runtime Host 必须在最新
freshness-order 实现加载后承载 X。X ready/enabled/unfenced 后至少跨越一个完整租约周期，要求 apply operation
revision 自然推进且 binding 始终未围栏，才证明提交入口 freshness gate 修复真实有效。未完成该观察不得登记 successor、
转移 saved definition 或启动 worker。后续九路 registration/cutover 必须引用 W detach Receipt，saved definition
从当前 rev8 disabled 转入 X controls，再由原 saved manifest 自然完成十二个 run；不得手工调用 definition 执行入口。

X 的首次 renew 由数据库约束安全拒绝，证明 a0v086 的链终点仍错误固定为最初 recovery 的 original definition。
当上一张 recovery 已成功推进到 W rev7 时，下一次替换的权威锚点必须是 recovery rev2 声明的
`currentDefinitionRef=W rev7`；W rev8 是同 installation/generation 上由 Owner 生成的精确 disable，X rev9 才是
引用 recovery rev2 的 transfer。新增 a0v087：从 prior recovery Receipt 读取 current revision/hash，只允许每个
transfer 使用同一张 prior recovery，并允许 transfer 的直接前代通过一个严格相邻、同身份、同成员、请求字段精确的
disable revision 回到该锚点。普通编辑、连续 disable、跨身份 disable、哈希断链或未到 prior recovery 锚点一律拒绝。
迁移部署继续执行私有备份、四表指纹不变和零业务写/零源读验证；失败的 renew 已整笔回滚，部署后使用原冻结请求重试。

X 的长观察进一步暴露锁争用语义：recovery rev3 的合法长事务与 Host 续租重叠，Host 在等锁后才执行三秒 freshness
gate，因此资源探测虽成功，时间戳却因锁等待变旧；通用 control 监督把该事务回滚当作资源失联，关闭 Owner 并释放资源。
修复仍保持三秒窗口：`_fresh_health` 仅把正向超时分类为专用 stale，未来时钟和非法时间继续硬失败；续租 Owner
捕获 stale 后，在三资源仍被原 Owner 持有且任务未 closing 的条件下重新执行完整三资源 health probe、重新读取两次数据库
时钟并重试一次。每次 lease transaction 都整笔回滚后才重探；不复用旧观察、不跳过 permission/lock/condition/CAS。
第二次仍 stale 或任一重探失败时沿原路径关闭、清理、围栏。verify/enable 及其他 control 不获得此重试语义。
已经围栏的 X 不原地恢复；修复验证必须使用正式 pause、disable/detach 后的下一代 Y，并在制造一次合法锁争用的同时确认
renew operation 自然推进、runtime 未围栏，再接回同一 saved group。

X 的退役入口固定为 installation `651dcf7c-08c1-4511-ae23-6e5e864f2b68`、generation
`0663a082-ea85-4110-9730-e13c230cd95c`、lock
`sha256:f3c437275227085f25d559e13b8a572a1ffce81b8777e68ed364683aca37a0f8`。Definition Owner 已将
rev10 enabled 正式推进为 rev11 disabled；退役前只接受 binding rev7/epoch4 disabled/unknown/fenced、三资源 released、
九路仍指向 X routeRevision45/groupRevision72、十二个 run 仍为 resumable running 且无 extension execution 或 occurrence
在途。Disable Owner 只能据此形成新的 disable operation，预期 fence 后 detach 到 binding rev9/epoch5 和 legacy
routeRevision47/groupRevision74；不得修改 snapshot run、saved input 或 recovery Receipt。Y 只能把该 X detach Receipt 作为
direct predecessor，且在 Host 重新加载本轮 stale re-probe 代码后开始 prepare。

X 的 Disable Owner 已生成 operation `d09d734e-be97-4317-999b-77c96b560be0`；fence Receipt
`28c788e0-206e-4abf-84e3-b8ebec34a48b` 与 detach Receipt
`490cce1d-9fc7-42bf-b8ca-aaaa9ac260fc` 已冻结，detach content hash 为
`sha256:9de42b1380b18c504ac6258d5099c8b2bc9191852c6085579c48b3b3d78e7f4b`。Y 安装前置检查必须同时验证
operation succeeded、Receipt phases 精确为 fence/detach、X active lineage head@5、binding rev9/epoch5 disabled/unknown/fenced、
三资源 released 以及九路 legacy rev47/group74。

Y 的 stale retry 实证使用一次无数据变更的数据库行锁争用：执行器先固定 Y installation/generation、ready/enabled/unfenced
binding、三份 pending lease、当前 apply operation 和最新 `runtime_lease_renewed` sequence；在下一续租到期前只对 Y 的
`bundle_installation` 当前行执行 `SELECT ... FOR UPDATE`，不执行 UPDATE/INSERT/DELETE。独立观察连接必须看见非本执行器
会话在该行锁上等待，随后继续持锁至少四秒，使第一次续租 health observation 必然超过三秒门槛，再提交空事务释放锁。
执行器随后只读等待新的 lease-renewed event，要求新 event 的 `healthCheckedAt` 晚于锁释放时间、三资源 expiry 同步推进、
apply operation revision/sequence 单调增加、Y binding 仍为 ready/enabled/unfenced，且无失败 operation、无资源释放、canary0。
若未观测到真实等待、锁未按时释放或终态不满足则不得把该轮记为通过。真实 Host 周期包含两秒轮询及其他 worker，
已观测相邻续租可在 60–68 秒间浮动；因此从上一事件后 50 秒进入窗口，锁最长三十秒，但一旦观测到 Host 等待仅再持有
4.25 秒即释放。该上限仍远短于 180 秒资源 lease，且失败轮次只回滚空事务，不生成通过证据。
PostgreSQL 的统计视图会在观察事务中缓存快照；每次轮询 `pg_stat_activity` 前必须调用
`pg_stat_clear_snapshot()`，否则真实被阻塞会话也可能在同一观察事务中不可见。通过证据只接受刷新后的实时 Lock wait。

Y 已按正常生命周期建立为 installation `c76d26b9-8a93-4476-a6fe-206e10930bc9`、generation
`87cd4104-999d-4224-b1ee-772b22a05445`、lock
`sha256:ec4ee4c8552258cafd607524eeaa2655776172c4c5df8f91ada38985960f2c9e`、configuration
`77f8fae9-13eb-4064-a0d7-33446ba2a303@1`（hash
`sha256:68598137a390d260342f61e807abfdbf28f599cdb05b24eacc38590a319b53fb`）。真实争用实证已观测 Host backend
`1212672` 在 `transactionid` Lock wait：锁于 `05:58:54.782976Z` 取得，Host 于 `05:59:06.642671Z` 进入等待，
保持超过 4.25 秒并于 `05:59:10.984140Z` 释放；续租随后以全新 `healthCheckedAt=05:59:11.296574Z`
成功，apply sequence/revision 29→30，三资源同步推进，binding 保持 rev4/epoch3 ready/enabled/unfenced，canary0、业务写0、
源读0。Y successor registration 必须引用 X detach Receipt 与 legacy group74；cutover 后才允许创建 Y controls 并转移
rev11 disabled saved definition，随后以 recovery rev3 为锚点生成 recovery rev4，不重读十二源。

若原 snapshot worker 对 saved recovery 安全拒绝，诊断不得手工调用 `run_definition`。Worker 可在保持原 catch/unknown
语义不变的前提下，只把源码内显式登记且不含任何运行时插值的固定守卫消息映射为固定 reasonCode；不得依据字符集、
长度或异常类型放行任意异常正文。未登记消息统一只记异常类名。日志不得包含商城正文、SQL、标识集合、凭据或 traceback。
登记表仅覆盖 saved recovery 的 current definition、Receipt、controls、schedule membership、original claim/input 与
source binding 守卫，不接受通用数据库或外部依赖消息。加载后只由原 15 秒轮询自然复现，再根据精确守卫修复方案。

Y 自然轮询精确拒绝为 `SAVED_RECOVERY_CONTROL_FAMILY_DIFFERS`：恢复 Authority 已在同一事务内验证完整十二项
successor controls、current definition、recovery Receipt、原 group/run、permission、schedule membership 与保存的
读取语义，但 SourceClaim Owner 的单项重放守卫仍只接受同 control family 的普通窗口续期。修复必须让该守卫使用同一
次 `run_current` 返回的 Authority 结论区分 renewal 与 successor transfer：renewal 继续要求 control resourceId 相同且
revision 单调递增；successor 仅在原安装/代际与当前整组安装/代际不同、且 Authority 已完成
`validate_saved_group_successor_transfer` 时允许 control family 改变。两条路径都必须加载原 control revision、核对原
claim ref/actor，并比较除执行窗口、selection 以及 successor 身份字段外的读取语义；不得把一个布尔调用参数、Receipt
文本或单项 ref 当作跨 family 授权。修复后仍由自然 worker 消费，不手工调用恢复。

第二次自然拒绝为 `SAVED_RECOVERY_CONTEXT_DIFFERS`。停止 Worker 后的只读字段级核对确认十二项原 claim ref、actor、
保存事实与原 control revision 全部一致，successor 仅变化 installation、generation、configuration、selection 与窗口，
排除这些明确允许字段后无任何读取语义差异。根因是 SourceClaim Owner 加载原 revision 时仍用当前 successor control ID
配原 claim revision；该查询只在同 family 续期下成立。跨 family 路径必须从 `record.control_ref` 解析原 control ID，再按
原 revision 加载，并继续要求其完整 ref 与保存事实相等；当前 ref 仍由 current Owner 独立锁定和验证。

修正原 control 查询后，自然 Worker 继续拒绝为 `SOURCE_CLAIM_CURRENT_BINDING_DIFFERS`。终态守卫仍把原 claim 的
installation/generation 与当前 successor draft 直接比较。跨 family 恢复必须改为双锚：原 claim 的 installation、
generation、pipeline 与 actor 精确匹配已验证的原 control/保存事实；当前 draft 继续由 current Owner 和整组 Authority
精确匹配 Y。普通 renewal 仍要求原 claim 与当前 draft 的 installation/generation 相同；只有同一 Authority 返回的
successor admission 才允许两侧身份不同，run、pipeline、actor、call ordinal 与 max source calls 均不得放宽。

SourceClaim 修复后，自然 Worker 首次进入关系评估并在 `assess_snapshot_relationships` 固定校验拒绝；随后 Y 租约失效，
Host 已将 binding 围栏为 rev5/epoch4 disabled/unknown/fenced，后续 `run_guarded` 拒绝符合无越权预期。对同一保存输入与
1.23.0 不可变策略做纯函数复算可合法形成 1,168 条候选关系，证明业务数据和策略未漂移。失败根因是 Assessment Owner
以 `zip(current successor controls, original parents)` 按两个不同 control family 的 UUID 排序位置配对，导致对象类型
与原 parent 错配。修复必须按不可变 pipelineId 显式连接：当前 group 的每一 pipeline 映射到唯一原 parent，双方集合精确
相等后才建立 objectType→outputRows；重复、缺失或多余 pipeline 全部拒绝。普通同 family 顺序不得成为隐含契约。
修复完成后不复活 fenced Y；按既有退役/替换流程产生下一干净 successor，再由自然 Worker 使用同一 recovery Receipt 链。

Y 退役基线已只读确认：installation `c76d26b9-8a93-4476-a6fe-206e10930bc9`、generation
`87cd4104-999d-4224-b1ee-772b22a05445`、lock
`sha256:ec4ee4c8552258cafd607524eeaa2655776172c4c5df8f91ada38985960f2c9e`，head etag5 active，
binding rev7/epoch4 disabled/unknown/fenced，三资源 released，definition rev14 disabled，九路仍为 extension
routeRevision48/groupRevision75/epoch3。Disable Owner 必须从该精确状态生成唯一 accepted operation，随后预期 binding
rev9/epoch5 disabled/unknown/fenced、九路 legacy routeRevision50/groupRevision77，Receipt phases 仅 fence/detach。
下一 Z 安装只能引用该 detach Receipt 作为 direct predecessor；版本仍为 core1.4/niushop1.23/growth1.10/operations1.2。

Y 已由常驻 Host 自然完成退役：Disable Owner operation
`c08d78ed-6e28-4933-8ed4-9aa7d2f7e6bd` succeeded，fence Receipt
`ff847625-0ff2-4951-99a8-42cef3c924b7`、detach Receipt
`0c5b83ce-7374-43ce-802e-799748c08802`，detach content hash 为
`sha256:687502feb843694ba376f11defbba84ba6efc24ca85d8df239a57701a07c8570`。终态精确为 binding
rev9/epoch5 disabled/unknown/fenced、三资源 released、九路 legacy routeRevision50/groupRevision77、definition rev14
disabled、零运行/未决/canary。Z 的 create intent 必须把这张 Y detach Receipt 形成的 current installation ref 作为唯一
direct predecessor；安装状态目录固定为 `replacement-z/z`，仍走 approved→prepared→verified→staged→configured→enabled
正常 Owner 链，不允许直接改 runtime binding。Z 成功启用并由 Host 观测 ready 后，才允许登记 successor、执行九路原子
cutover 和 saved recovery rev5；任何阶段失败均保留 Y 的 legacy 路由且不得启动 snapshot Worker。

Z 已由正常生命周期建立为 installation `cd426e3a-f5e8-45a2-b6a8-8991294b467e`、generation
`d49fe4fd-55c8-4688-9602-5dbff946bc36`、lock
`sha256:6259239db5ddff1cc5156955d445673e3063640df30c7410448aa206d826a5cf`、configuration
`05ff8817-661a-4dce-80ed-d7419fe5db2f@1`（hash
`sha256:8eb5279948d9a3e0031d20f4c3b036da3bbf03fa00eb8b95d4ef1f95ffda60ad`），终态 binding
rev4/epoch3 ready/enabled/unfenced、三资源 pending、四个生命周期 operation 全部 succeeded、canary0。下一阶段固定为：
以 Y detach Receipt 和 legacy group77 登记 Z successor business；九路一次 cutover 后必须成为 Z extension routeRevision51/
groupRevision78/epoch3；随后创建 Z 十二项 controls，把 rev14 disabled definition 转移为 rev15 disabled，并以 recovery
rev4 为唯一 prior anchor 生成 recovery rev5 和 rev16 enabled。完成前 snapshot Worker 保持 bootout，禁止手工调用
`run_definition`。
Z cutover operation 命名空间固定为 `9228aba3-3421-40a9-bbe7-b89179c2b295`，不得复用 Y 或更早代际的
operation/idempotency key；approve、prepare、pause、commit、validate、resume 每相位各自冻结 intent/result，存在 intent 时只
允许 inspect，不重发。

Z successor registration Receipt 已冻结为 `81c05c8f-9a6e-4a4e-a9b3-bb1d56578ca9`；cutover 六相位完成后九路精确为
extension routeRevision51/groupRevision78/epoch3，claim resumed。十二项 Z controls 均由当前 binding 新建并绑定；definition
rev15 由 Y rev14 disabled 转移，recovery rev5
`sha256:79133cc39102bb9c8a3908b9ef5fce49257f84572f6b1636009cac49d739f249` 以 recovery rev4 为 prior，生成并确认
rev16 enabled，`sourceReads=0`。下一动作只允许重新加载通用 snapshot schedule Worker，由其十五秒轮询自然消费原 group；
验收要求十二 run 全部 succeeded、每项 output/facts/claim completion 齐全、group assessment 成功且不新增 source claim call。
任何固定守卫拒绝或 Z runtime fencing 都立即停 Worker、冻结诊断，不手工执行 definition。

Z 自然执行已暴露新的运行时边界：十二 run 在约十分钟内始终原子保持 `running`，未出现部分成功；Worker 的长事务持有
installation/runtime control 当前锁，Host 续租在 installation `FOR UPDATE` 等待。Store 阶段结束前资源 lease 到期，随后
`run_guarded` 以 `RUNTIME_REQUEST_NOT_CURRENTLY_ADMITTED` 拒绝，事务回滚；Host 取得锁后把 Z 正确推进为 binding
rev7/epoch4 disabled/unknown/fenced 并释放三资源。该结果证明围栏与无越权边界有效，同时证明“把完整 Store 恢复包在当前
授权锁事务”不能支撑真实数据量；单纯把 180/300 秒租约调大只会延后同一故障，不是修复。

修复采用现有 execution-attempt/drain 语义的 recoverable Store 扩展，而不放宽当前授权：

1. 新增独立 `recoverable_store` attempt kind。它只能由当前 enabled/unfenced binding、精确 installation/generation/epoch、
   固定 group operation key、canonical request hash 在租户 runtime 事务内登记；同一 operation key 以事务级 advisory lock
   串行分配 attempt ordinal。live attempt 禁止第二执行者，succeeded 禁止重放，只有 failed/abandoned 才允许下一 ordinal。
2. attempt 初始 lease 保持五分钟上限，执行期间由独立 runtime 连接按固定周期 CAS heartbeat；heartbeat 不授予新执行，
   只证明原执行者仍在。围栏后禁止新 attempt，但已登记 attempt 可继续心跳并进入 terminal；GenerationDrainReader 必须等
   所有旧 epoch attempt terminal 后才允许 disable/configure 完成。进程失联则原 recovery worker 只把过期 running attempt
   标记 abandoned，绝不代跑 Store。
3. saved Store 恢复拆为“当前授权读取 exact saved command → 提交元数据事务 → attempt 覆盖下执行原幂等 Store command →
   新事务重新验证当前 saved authority/command hash 后保存下一阶段”。base、derived 与 projection 各阶段均不得在
   installation/control 锁事务内调用 Store；每个 committed prefix 仍由原 idempotency Receipt 证明，失败或围栏后的下一代
   只能按相同 command hash 回放已提交前缀并继续，不能产生第二次 source read。
4. attempt terminal settlement 使用 exact owner token/revision；成功仅在完整 group completion 持久化后结算 succeeded。
   任一异常结算 failed；若 fence 已发生，后续 current-authority 复验必须失败，但 Store 已提交前缀保留为可恢复事实。
5. Z 保持 fenced，不复活。先把 rev16 definition 正式 pause，再完成 migration、Owner、heartbeat、阶段拆分及并发/崩溃/
   fence-drain/租户隔离测试；随后按正常退役流程产生新 successor，最后只由自然 Worker 重新消费 recovery Receipt。

上述修复已落为 a0v088：`recoverable_store` attempt 约束、retry ordinal、独立 heartbeat Owner 与 group completion 包络均由
专项 PostgreSQL 测试验证；一个“原 Store 已提交但确认丢失”的十二成员集成用例连续运行 9 分 44 秒并最终单次成功，证明
执行跨越五分钟仍可持续心跳。stopped-failed 恢复通过；attempt commit 确认丢失时，新执行器只观察 live attempt 并拒绝进入
Store。base/derived、relationship link 与 retirement Store 写均已移出 installation/control 当前锁事务，调用前后重新验证
original saved authority。a0v088 已在 `aos_meta_head` 从 a0v087 单步部署，迁移前备份 hash
`sha256:a6de655b666f9fc99f97feaf6c9de0acd44e5b6dd95abc7362f04ec4db5c2786`，两张 attempt 表行指纹保持不变，
businessWrites=0、sourceReads=0。

Z definition 已由 rev16 enabled 正式 pause 为 rev17 disabled。Z 随后由常驻 Host 自然完成退役：disable operation
`e907f30d-063e-4ea4-9c1c-8fb339ce7610` succeeded，终态 binding rev9/epoch5 disabled/unknown/fenced、三资源 released、
九路 legacy routeRevision53/groupRevision80、definition rev17 disabled、零运行 attempt/未决/canary。下一 AA 安装必须只把该
operation 的 detach Receipt 作为 direct predecessor；AA 仍走 approved→prepared→verified→staged→configured→enabled，
然后登记 successor、九路 cutover、definition transfer、recovery rev6 与 enabled definition rev19。新版 Host 重载并确认
a0v088 preflight 前，禁止启动自然 snapshot Worker。

AA 已按上述正常生命周期建立：installation `d0476259-7e04-4cf6-ba94-9d7da1c73db0`、generation
`44236c8a-cf56-451c-b620-21c63e48d87e`、lock
`sha256:bb484830d142b122bea47770a49724b404e2ffa8f5296d0e5083d80da70017f1`、config
`01e151d6-cddb-4588-97ce-5e044d25af97@1`/`sha256:bf6c99c143141f1d0892ad92903c667e1f9efdd37262258c65446bd7f8aeeef2`；
终态 binding rev4/epoch3 enabled/ready/unfenced，apply/verify/configure/enable 四个 operation 均 succeeded，canary0。
successor registration 只能引用 Z detach Receipt `ede1ac24-57d2-419b-b647-fc7e115109f4`/
`sha256:9efe92c4e070f69cbc4c422f32a4363ac635f2c960687dd5ac7b858c844447f4` 和九路 legacy
routeRevision53/groupRevision80；AA cutover 使用全新 operation namespace，完成后预期九路 extension
routeRevision54/groupRevision81/epoch3。随后将 rev17 disabled definition 转移为 AA rev18 disabled，以 Z recovery rev5 为
唯一 prior 产生 recovery rev6 并确认 rev19 enabled；全过程 sourceReads=0，任何现有 intent/result 都只读不重发。

实际部署闸进一步证明 Runtime Host 的正常退出不是 live generation 的无缝进程交接：新 Host PID `545` 已加载 a0v088 并
ACTIVE，但旧 Host 退出按 Owner 语义把 AA 推进为 binding rev7/epoch4 disabled/unknown/fenced，并释放三项资源。AA 的九路
cutover 已完成为 routeRevision54/groupRevision81，definition 只转移到 rev18 disabled，recovery rev6 尚未生成，snapshot
Worker 保持 IDLE，所以该围栏没有 source read、run 或部分 Store。不得复活 AA。先用原 disable Owner 把 AA 正式 detach，
预期 legacy routeRevision56/groupRevision83；再由 detach Receipt 创建 AB。AB 走完整正常生命周期、successor/cutover 和
rev18→rev19 transfer、recovery rev6→rev20 enabled；Host 已是新代码，此后禁止在真实长任务完成前再次重载 Host。

AA disable operation `139b08cd-211d-4595-b3bb-90527fe6f2f5` 已由新 Host 自然完成，detach Receipt
`a15bc392-0981-4b29-9a63-f02439726c0c`/
`sha256:309a63ff9331f71610137aa6302d02ccf0f2e4babd712e25797d10d7a49f58ab`，终态符合 legacy
routeRevision56/groupRevision83、binding rev9/epoch5、三资源 released、definition rev18 disabled、零 running/unresolved/
canary。AB 已由该 direct predecessor 建立为 installation `b57e5f93-f075-45f1-a42c-4340255e4f74`、generation
`00fba2de-a505-49f1-a3e6-696d7415fc79`、lock
`sha256:95dcd233ecf514889f4d57ed56e2c2c9c68e54dfbdb4c651d642f4641c28e3ae`、config
`7eb46fea-6a5c-4039-bb4c-691e2c4bfda7@1`/`sha256:df21b6ab28beefefa0dc710b761f62d930694b22bc0c4f87df1b213780906717`，
正常生命周期四项 succeeded，binding rev4/epoch3 enabled/ready/unfenced。AB successor 必须以 group83 登记，cutover 后
预期 extension routeRevision57/groupRevision84/epoch3；随后才允许建立 rev20 enabled recovery。

AB 实际恢复揭示 Host 与独立 snapshot Worker 是两个必须分别装载新代码的进程：Host PID `545` 已装载 a0v088，
但 Worker PID `251` 在 a0v088 落盘前启动，因此 AB 的自然恢复仍使用旧 completion 实现。AB 在约九分钟长事务后由
Host 健康期限安全围栏，Worker 只得到 `RUNTIME_REQUEST_NOT_CURRENTLY_ADMITTED`；十二 run 原子保持 running，
source claim 仍为 28、canary0、sourceReads=0。AB 已在 members12/running12/savedInput1/recovery6/
fencedBinding1/releasedResources3 的精确守卫下，把 rev20 enabled 正式 pause 为 rev21 disabled。该次运行只证明旧进程
安全拒绝，不作为 a0v088 实证。不得复活或重放 AB。

新增固定部署闸：任何同时依赖 Runtime Host 与独立 snapshot Worker 的代码修复，必须在 definition disabled、无活动
Store attempt 且当前 generation 已围栏/释放的窗口分别重载两个进程，并记录 PID 与 loaded source hash。随后正式 detach
AB，创建 AC direct successor，完成 successor/cutover、rev21 transfer、recovery rev7 与 enabled definition；仅由重载后的
自然 Worker 消费。AC 运行期间必须可见 committed `recoverable_store` attempt、30 秒心跳推进与不超过 120 秒的 current
lease；若 attempt 不可见或心跳不推进，立即按未知结果处理，不将 Run 终态当作修复证据。

AC 已由 AB detach Receipt `19cd00c5-25e1-4d8c-befd-618c8035e172`/
`sha256:077b8a25e595754b7b687c6b1ca1fa67d97e708edb919d5e77299eb1ac1a71bc` 建立为 installation
`4fbd0873-dede-4c3c-9db8-29c3e14c2c48`、generation `cdfa92eb-a695-46e7-9ed4-35a296321403`、lock
`sha256:dc6b4bd74d95fb6b0109ec6e9e8708177a697e608d93c702e207cefce41d0761`，四项生命周期均 succeeded。
successor registration Receipt `a7e0404d-fd2f-4109-a63a-fc1ce8f225e7` 已引用 AB exact detach；cutover operation
`69e0d35c-5aca-462c-afa7-1ba538e4e20e` 的 prepare/pause/commit/validate/resume 全部闭合，九路为 AC
extension routeRevision60/groupRevision87/epoch3，claim resumed。rev21 disabled definition 已以 `sourceReads=0` 转移为
AC rev22 disabled，并由 recovery rev7 `sha256:819e6906aadf85704ef2d9a588837d8ee52c850e0766b2e6bd6602b61ee6e2ef`
推进为 rev23 enabled。独立 Worker PID `4058` 正由 15 秒自然轮询消费；当前十二 run 仍原子 running、source claim 28、
canary0，长关系评估仍在进行。只有 AC committed attempt 及其 heartbeat/lease 实证出现后才能进入完成判断。

AC 自然运行最终精确定位 a0v088 的包络仍晚了一层：关系评估从 `10:01:13Z` 到 `10:11:22Z` 持续约十分钟，期间
一直处于 attempt 之前的元数据事务并持有 installation 当前锁；Host 续租从 `10:01:37Z` 等待到该事务提交。AC
`recoverable_store` attempt `116390b7-caab-423e-b077-327c5772430a` 虽在提交点成功登记，却在
`10:11:24Z` 由 `run_guarded` 以 `RUNTIME_REQUEST_NOT_CURRENTLY_ADMITTED` 结算 failed，revision2、无 heartbeat；
Host 已将 AC 围栏并释放三资源。十二 run 仍原子 running、saved input1、recovery7、source claim28、canary0，definition
已按精确守卫从 rev23 enabled 暂停为 rev24 disabled。该次失败证明 Store 写阶段拆分正确但 attempt 开始位置仍不足。

下一修复保持同一 Authority，不新增旁路参数：Completion 在 recovery 路径先用已有 `SnapshotGroupRecoveryAuthority.run_current`
完成轻量 current Receipt/definition/control/run/permission 守卫，从其 `CurrentSavedGroupRecovery.execution` 提取唯一
installation/generation/epoch，并用 recovery ref、current definition ref、input manifest、policy ref 与十二个 exact
control/run pair 形成 canonical attempt request hash；随即在同一短事务登记 attempt 并提交。昂贵的完整 relationship
assessment 只允许在 `with attempt` 内由原 Retirement execute 再次执行，继续保留前后 current authority/policy 复验，
不得缓存评估结果或跳过 Store 前守卫。普通非 recovery 路径保持原逻辑。专项测试必须证明 recovery 的第一次 assessment
入口已经可见 committed running attempt；heartbeat/失败结算、未知 commit、防重与 fence drain 语义继续通过。AC 不复活，
修复后由 AC detach 创建 AD，再以 recovery rev7 为 prior 生成 rev8 做自然验收。

专项 PostgreSQL 全量闸补跑还发现一项同族续订兼容性回归：普通 `resume_saved` 不配置 group recovery authority，
其 admission 按设计为空；successor 扩展后的校验却在区分同族/跨安装之前无条件要求 recovery admission，导致合法的
同一 control resource revision 续订被拒绝。最小修复先独立校验 original claim/control 一致性；同一 resource id 继续只接受
revision 单调增加并比对除时间窗与 source selection 外的不可变字段，允许 admission 为空；只有跨 resource/安装 successor
才要求 exact `_SavedRecoveryAdmission` 及十二成员 authority facts。不得因此允许新增 source call、未知结果恢复或跨租户读取。

AC 退役前置已以 binding rev7/epoch4 fenced、三资源 released、definition rev24 disabled、唯一 attempt failed rev2、
零 running attempt/未决/canary 通过。disable operation `ae8ad4c2-af80-4d2f-82ed-ec421c8e0975` 已由 Owner 接受；
首次冻结结果的 outcome 展示标签因模板把 `DISABLE` 中的 `AB` 误替换而写成 `DISACLE`，operation kind、Receipt、
expected binding revision 与数据库状态均为正确 disable 语义。后续脚本标签已修正，原冻结文件保留不改作为审计事实。

AC disable 已由 Host 自然完成：operation succeeded rev6，lifecycle 为 fence/detach，两张 Receipt；终态 binding
rev9/epoch5 disabled/unknown/fenced、三资源 released、九路 legacy routeRevision62/groupRevision89、definition rev24
disabled、零 running/unresolved/pending/canary。安全空窗内已分别重载 Host 与独立 Worker：Host PID `8807`、Worker PID
`8820`，18181 已恢复监听且 Worker preflight 为 green。两进程启动时关键源码 hash 为 completion
`sha256:88072494e3736b2d69933beaa0d2bf00c5cb936fb28004fe0de8cbd135c0ae34`、attempt
`sha256:c8b52ac07d9ec7fd61eecdb5ad729cdeb8851e3a065e37219e46b99c42482223`、source-claim
`sha256:19fc70596e2a597b2eb5a800a905ded570900faa1a3cddd97daf5adadaf29501`。AD 必须以 AC detach Receipt 为 direct
predecessor，完成正常生命周期、group89 successor、九路 cutover，随后 transfer rev24、以 recovery rev7 产生 rev8 并启用。

AD 已按该路径完成正常安装、successor 与九路 cutover：installation
`42d9f8bd-11b0-4f8d-8c4d-75458ab23c94`、generation `7a2f5483-8ff6-4672-b174-f273885e99d0`，
successor Receipt `e2761023-76f3-4953-b20d-eea8cb4b5801`，cutover operation
`01e46def-0d00-4e56-bbe4-1f5898e0805f`，当前九路为 extension routeRevision63/groupRevision90。
definition 已由 rev24 以 `sourceReads=0` 转移，并由 recovery rev8
`sha256:fda09f51945fe05bf548c9e4bef1e2ecaf59a1f7b8ded14adffaf66319bafa14` 推进为 rev26 enabled。
自然 Worker 再次揭示前述修复设计判断错误：所谓“轻量” `_recovery_attempt_target` 仍调用完整
`SnapshotGroupRecoveryAuthority.run_current`，而该入口首先加载 saved manifest/十二份父输出并解析当前 policy/mapping，
所以 AD 长关系计算开始后 attempt 表仍为空。AD 不得计为成功或 replay 证据；待其自然失败并由 Host 围栏后，按精确事实暂停、
正式 detach，再以新替换 AE 验收。

下一最小修复在同一 `SnapshotGroupRecoveryAuthority` 增加只供 attempt 登记的 current target 读取，不增加旁路授权，也不复用为
Store 许可。该读取必须在一个短事务内完成：校验 exact recovery ref 与 executor；锁定并校验 receipt 指向的当前 enabled
`renew_saved_group` definition、policy、installation/generation permission；读取 definition 保存的十二个 binding 并要求它们仍是
latest；用不可变 `pipeline_snapshot_schedule_member` 的 schedule→run 关系证明传入的十二个 control/run pair 完整且精确；校验
十二 schedule 仍 enabled 且属于当前 definition；逐条解码 exact control revision，要求 control draft 与 definition member 一致，
并且十二个 draft 只形成一个 installation/generation/executionEpoch。该入口明确禁止读取 saved parent `outputRows`、禁止关系评估、
禁止 Store，也不取代原 `run_current`。

Completion 用这份轻量 target 形成原 canonical attempt request hash，先提交 running attempt；只有进入 `with attempt` 后才允许
原 Retirement 调用完整 `run_current`，继续复验原始 saved facts、transfer 链、source claim、mapping、policy、关系和 Store 前后
current authority。专项 PostgreSQL 测试必须直接钩住完整 `run_current`/saved facts 入口，证明其第一次调用时数据库已可见 committed
running attempt；仅钩住更深层 relationship assessment 不再算充分。现有 heartbeat、失败结算、未知提交、防重、围栏 drain 与
同族 renewal 回归测试必须继续通过。实现文件限定为
`services/aos-api/aos_api/pipeline_snapshot_group_recovery_authority.py`、
`services/aos-api/aos_api/pipeline_snapshot_group_completion.py` 和对应专项测试；AD 运行中的旧进程不重启、不强杀。

实现复核又把边界前移了一步：`stopped_failed` 的十二 Run 恢复原先也在 attempt 之前调用完整恢复权威。最终顺序固定为：
同一 advisory group lock 下先只读判路；非 replay 路径用轻量 target 登记并提交 attempt；进入 `with attempt` 后，若为
`stopped_failed` 才在独立原子事务恢复十二 Run，然后执行完整 authority/assessment/Store。attempt 提交回执未知时，原 Run
保持 failed/stopped 且零 recovery claim，重试只看到 live attempt 并拒绝，不会重复恢复。专项 PostgreSQL 10/10 已证明完整
`run_current` 第一次调用时 running attempt 已由另一连接可见，并覆盖十二项回滚、未知提交、防重及混合状态拒绝。

AD 旧代码自然运行于 `11:08:39Z` 后结算为 `RUNTIME_REQUEST_NOT_CURRENTLY_ADMITTED`，未产生完成事实；Host 已围栏并释放
三资源。精确暂停守卫确认 members12/running12/savedInput1/recovery8/fencedBinding1/releasedResources3/sourceReads0，
definition 已由 rev26 enabled 推进为 rev27 disabled。下一步只允许用现有 disable Owner 正式 detach AD；预期九路 legacy
routeRevision65/groupRevision92、binding rev9/epoch5、零 live attempt/未决/canary。随后在空窗分别重载 Host/Worker 的本次
源码，再由 AD detach Receipt 创建 AE，完成正常生命周期、successor/cutover 和 rev27 transfer、recovery rev9 自然验收。

AE preflight 与 direct predecessor 守卫通过；installation `d02f90f2-eb0e-4859-ad58-35b17ddbcd6a` 已 approved，generation
`36a57887-4f28-45e7-8515-2d94a343b5ed` 已完成 apply/verify 并处于 ready disabled。stage 的当前四源配置授权在写入前以
`budget policy is not effective` 关闭，未生成 stage 结果、未配置、未启用。该策略于
`2026-09-17T11:18:04.157170Z` 到期，不能延长旧行或绕过校验。

恢复路径复用已评审的固定 `text-readiness-v2` 三个公共合成探针和正式 policy renewal Owner：在全新私有 journal 目录中每例只
允许一次 Provider 调用，失败/未知不重试；通过后由 `a0v_formal_text_model_renewal.py` 先冻结新 budget/runtimePolicy/model/route
候选，再以各 head CAS 和原发布 Owner 应用。该动作只刷新开发自测模型治理权威，不包含商城数据、业务 Run 或外部发布；费用沿用
用户“不看成本、功能优先”的授权。AE stage 重试必须重新生成配置并引用新 current exact refs，不能复用失败前的内存候选。

续期已在私有 journal 中以 `text-readiness-v2` 完成 3/3 公共合成探针（恰好三次 Provider 调用，零业务写入），冻结计划
`72db8f5ba6d3eb89e5de19e7d2f2cd4d15b1f014f002d3bb176a1585603d6414`。正式应用前备份
`aos_meta_head`（8564310 bytes，SHA-256 `726d6e93638af13461f0018b6b62579c02391f8776e7a291f0b8ffe77a920b0b`），
随后用原 head CAS 发布 budget/runtimePolicy rev7、price/model/route rev6；应用阶段 ProviderCalls=0、businessRuns=0。
AE 重新 stage 得到 config `ccfbc451-e594-42a9-958d-f7bae72c1a86` rev1/hash
`13b477bc045568b9dd8e5ce7b2c74de0ecbdaee3bc357ecf45e06ab8ba13d53a`，其 policyRef 精确指向 rev7；Host 已自然完成
configure `826c52ee-7a0f-47ed-82a7-8a7cb1dced9d` 与 enable `4ae61076-b16c-4acf-848c-04514ae3a4dc`。
当前 binding rev4/epoch3 为 ready+enabled+unfenced，三资源 held、canary0。下一动作只允许以这份 current readback 建 AE
successor business 与九路原子 cutover；不得复用 AD 的 installation/generation/config 或构造伪回执。

AE successor registration Receipt `0aad1b40-7742-4bc9-9722-28264cc8f7c5` 已从 AD detach Receipt
`9723047a-7922-4f3a-af11-384aec92752e` 注册；cutover operation
`ef574984-5d7c-450f-b877-fbd20c11221c` 已依次完成 approve/prepare/pause/commit/validate/resume，九路 current
route 为 extension rev66/group93，target runtime rev6，claimPaused=false，零 claimed/unknown/running cutover attempt。
保存定义已从 AD rev27 disabled 迁移为 AE rev28 disabled，再以 recovery rev9 推进到 rev29 enabled；十二个新 control 均精确引用
AE installation/generation/config，保存 manifest 保持 `03cccc…35e01`，迁移和续期 sourceReads=0。

Worker 在 `2026-09-17T11:34:09.892622Z` 自然提交 recoverable_store attempt
`1842fff5-fe8b-4fdb-a73f-e83378cd895b`，随后才进入完整 authority/Store；另一连接在长计算期间可见 running，heartbeat 已连续推进，
十二 Run 保持 running/executorStopped=false。只读 runtime API 因 current installation 行锁按预期 fail closed，不能据此中断或手工续跑；
必须等待 attempt 自然结算，并以 attempt terminal、十二 Run terminal、completion/assessment/manifest 一致性作为本阶段退出条件。

AE attempt 的终态进一步暴露独立的锁边界缺口：attempt 心跳从 accepted 连续推进至 revision20，但关系评估事务仍持有
`bundle_installation` 当前行锁约十分钟，Host 的 preparation lease 续订线程因同一行锁阻塞。资源租约越过 180 秒后，长事务释放时
Host 只能把过期健康观察判为 stale 并安全退出；attempt 于 `2026-09-17T11:44:13.452956Z` 以 revision21 failed 结算。
十二 Run 仍为 running、未产生部分完成，证明失败无越权副作用；该失败不是模型或 Store 错误，不得通过延长租约、放宽新鲜度或
重放 AE 规避。

根因固定在 `PipelineSnapshotGroupAssessmentOwner`：确定性的 `assess_snapshot_relationships` 会遍历十二份已保存父输出，实际约耗时
十分钟，却被 `PipelineSnapshotGroupInputOwner.run_current` 的当前安装/permission/definition 锁事务包围；后续 relationship、link、
audit journal 的 current read 还会重复同一计算。最小修复只作用于 saved recovery：

1. attempt 已提交后，用一个短 current transaction 加载并冻结完整 `CurrentSnapshotGroupInput` 与 exact compiled policy；事务退出前后
   继续由原 Authority、source claim、control、schedule、permission 和 policy loader 复核，禁止在锁外读取商城源；
2. 事务完全提交后，在锁外对冻结的不可变父输出运行原 `assess_snapshot_relationships`，形成 canonical payload/hash；不调用 Provider、
   不写 Store、不形成授权；
3. 第二个短 current transaction 重新加载完整 input/policy，要求与冻结值逐字段相等，再以现有唯一键写入或比对不可变 relationship
   preparation。若 definition/control/policy/claim/manifest/父输出任一漂移，整笔失败且不写 preparation；
4. saved recovery 后续层每次仍进入原 current Authority，但只加载、验签并重建这份不可变 assessment，不再重复十分钟计算；普通非
   recovery 路径继续在原事务内即时评估。已存在 preparation 必须精确绑定 manifest、policy ref/hash、payload/hash，否则 fail closed；
5. 专项 PostgreSQL 测试必须证明锁外评估期间另一连接可取得 installation current 行锁/Host 可续租，并证明评估期间 current 输入或策略
   漂移会阻止持久化；原 attempt heartbeat、未知提交、防重、Store 前后复核测试继续通过。

AE 已因租约到期成为不可恢复代际。修复通过后只能按精确终态暂停、正式 disable/detach AE，在 Host 与 Worker 的安全空窗重载源码，
再创建 direct successor AF 并以 recovery rev9 生成下一 revision，继续同一 saved manifest 的自然恢复；不得原地复活或 replay AE。

AE 已在 members12/running12/savedInput1/recovery9/fencedBinding1/releasedResources3 的精确守卫下暂停，并由 Host 自然完成
disable operation `f2ac688e-dac3-433a-859c-3e3424957064`。终态为 binding rev9/epoch5 disabled/unknown/fenced、
三资源 released、definition rev30 disabled、九路 legacy routeRevision68/groupRevision95，零 running/unresolved/pending/canary；
detach Receipt `0f1dd7dd-12ed-4efe-a2c3-49b3f931c1c9`/
`sha256:abc43a8f6d577e33bef5e9f7a0df4a74b4bf04a4845f0b2fce2043c11a8d0c0f` 是 AF 唯一合法 direct predecessor。

安全空窗内 Host 与 Worker/API 已分别重载为 PID `17529` 与 `17531`，均于 `2026-09-17 20:09:39 +0800` 启动；本次锁外
评估关键源码 hash 为 assessment-owner `sha256:c91be86743a0dbbf3797df5b6105ebdcf55a78f17ec02a695e4b7a214e09cac5`、
relationship-journal `sha256:1868f7f2163039a4b6fe26bc7738136561d4e81c320f109fdf5a0a5571aeb64b`、
object-executor `sha256:84a7e2cbb7122a2cd972e5a9ae13cda8a3a3bb189250f214ef3a27e3a202fece`。
专项测试已证明评估期间另一连接可取得 installation 行锁，输入或 policy 漂移会拒绝持久化；扩展相关测试 47/47 通过。

AF 已按 direct successor 路径完成安装、配置、启用与九路 cutover：installation
`0bf928a9-877a-4b97-9778-7f678d6cd7d4`、generation `173e267c-f031-4fda-b801-bc9e0a0d2264`、lock
`sha256:d7d847a08bf9091e72e4d0e5bb1337e827788b88951d104e01956af2f752580c`、config
`e0330817-daec-444b-85da-fa56ce56b1f7@1`/`sha256:a7774ff81587977b124927941c06a953a776c348346c685cd5cd85cb00e8d97b`。
successor Receipt `fdaedad8-74c0-4513-9d45-7d38cdca78e4` 精确引用 AE detach；cutover operation
`f1579b09-cc65-449d-b144-1f43f1683e8f` 已闭合 approve/prepare/pause/commit/validate/resume，九路为 extension
routeRevision69/groupRevision96/epoch3，claim resumed 且零 in-flight。AF 十二源 preview、schedule ingest 与 control 已冻结，
所有 control 精确指向 AF。下一动作只允许把 AE rev30 disabled definition 以 `sourceReads=0` 转移到 AF，再由 recovery rev9
生成 rev10 并由自然 Worker 消费；不得手工运行 definition。验收必须同时看到 committed recoverable_store attempt、持续 heartbeat、
Host lease 在约十分钟评估期间继续推进、immutable relationship preparation 落盘，以及十二 Run 原子完成。

AF 已完成 rev30→rev31 transfer，并由 recovery rev10 生成 rev32 enabled，manifest 仍为
`sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，全过程 `sourceReads=0`。自然 Worker
于 `2026-09-17T12:27:08.353166Z` 提交 attempt `dc000c9a-6a08-4aec-bb5d-269f08609b4a`，heartbeat 持续到
revision19；但 PostgreSQL 锁图证明上一修复的边界仍不完整：已有 relationship preparation 时虽不再执行关系算法，
`materialize_current` 仍在一个事务里通过完整 recovery authority 重复编译十二个 SourceSelection。Worker backend 在该事务中
持有 `bundle_installation` 行锁约九分钟，Host 续租 backend 被该 transaction id 阻塞；三资源于
`2026-09-17T12:29:33.574856Z` 过期。锁释放后 Host 正确围栏并释放三资源，attempt 于
`2026-09-17T12:36:19.894282Z` revision20 failed。十二 Run 原子保持 running，definition rev32 enabled，canary0，
未产生新的源读取。AF 不得复活或重放。

下一修复不再扩大 snapshot 业务代码，也不延长固定 TTL。`recoverable_store` attempt 本身是 disable/drain 所依赖的当前在途事实，
因此 Host 的资源续租增加一条严格的 in-flight 快路径：在常规 installation current 锁之前，用短事务锁定 exact binding，要求
binding enabled、unfenced、generation/epoch 精确一致，且恰有一个同 installation/generation/epoch 的 running
`recoverable_store` attempt，其 `lease_until` 仍在未来并已有新鲜 accepted/heartbeat；同时要求 runtime 健康探针不超过三秒、
resource handle 精确指向原 preparation operation、三项资源仍 pending/unreleased 且 handle proofs 完全一致。满足时只把这三项
资源 `expires_at` 原子推进固定 180 秒并记录专用 renewal event；它不更新 installation、definition、control、attempt 或任何业务数据，
也不授予新的 Store/Source 执行。binding 一旦被 fence/disable、attempt terminal/过期、资源已过期或集合漂移，快路径必须拒绝，
随后沿用原 fail-closed 行为。没有 live recoverable attempt 时，现有完整 current permission/revalidation 续租路径保持不变。

专项 PostgreSQL 测试必须用另一连接持有 installation 行锁，证明 live exact attempt 下 Host 仍能在三秒健康窗内续租；并覆盖
attempt terminal/过期、binding fenced、epoch 漂移、resource proof 漂移、资源已过期均不允许快续租。原 lease renewal、attempt
heartbeat/drain、disable fence 与 47 项 snapshot recovery 回归必须继续通过。实现限定在
`services/aos-api/aos_api/extension_runtime/lease_renewal.py` 与对应测试；AF 自然失败事实冻结后先暂停 rev32，再正式 detach，
安全空窗重载 Host/Worker，创建 direct successor AG，以 recovery rev10 生成 rev11 做自然验收。

AF 的正式 disable operation `5ae15307-bb70-41ff-925d-8c8a25ec252c` 已由 Host 自然完成；其 detach Receipt 为
`8d157372-308e-468a-876e-d1e03dd0dc56`，content hash
`sha256:234013cd6ba39173c4ef3e7a73a9b544604bf99c8ab1b7698fcd0524750385b5`。AG 只能以该 Receipt 在
legacy route revision71/group revision98 上完成 successor registration，并使用独立 cutover operation
`afbe29fa-c61c-4d81-adad-5fc84e74b551` 推进到下一组；不得直接修改 route。首次批准在 prepare 前发现 policyId
仍沿用 AF 名称，已作为零副作用废弃批准保留；正式链改用 `qyh-clean-generation-ag-activation` 与独立 v2 状态目录，
不重发 registration。切换后才允许创建 AG 的十二项 control，
把 AF rev33 disabled definition 转移为 AG rev34 disabled，并由 recovery rev11 生成 rev35 enabled。自然 Worker
执行期间必须观察 Host 的 `runtime_inflight_lease_renewed` 事件和同一三资源租约延长；只有十二 run 原子成功、
`sourceReads=0`、无 canary/越权副作用，才能判定长事务期间续租修复成立。

AG 自然验收又发现快路径锁粒度仍过大：attempt `912c10d2-e5d8-423c-8875-e4695b79e11a` 开始后，Worker
长事务持有 current binding 行版本，Host backend `1400592` 在 `_renew_live_recoverable_store` 的 binding
`FOR UPDATE` 等待该事务，未能在 `2026-09-17T13:06:39.639462Z` 前续订三资源。该运行继续按过期资源
fail closed，AG 不得补写、复活或重放。下一最小修复把 binding 改为普通 current read，attempt、preparation operation
与三资源仍在短事务内加锁；资源 UPDATE 额外用 exact binding enabled/unfenced/ready、generation、epoch 与 handle
的 `EXISTS` 条件作 statement-time CAS。并发 disable 即使在该语句快照之后开始，也会沿原 drain/fence/release 顺序
最终释放资源；快路径不修改 binding、不授予新执行。测试必须由另一连接真实持有 binding 行锁，证明续订不等待，
并覆盖 statement-time binding 漂移时零更新、整笔回滚。AG 失败事实冻结和正式 detach 后，用 direct successor AH
加载修复并以 recovery rev11→rev12 重跑。

AG 已在精确失败终态下暂停并通过 disable operation
`45789d11-145e-4b4b-84a2-13e6d6fed5b6` 正式退出；detach Receipt
`fc5e9725-e32d-4e54-b3fb-eba4f969aaf8`/`sha256:e726a6fd8d36d62ce8b747812f31afce1d2d5d2abc9ac3a26d66cb7701b86b88`
是 AH 唯一合法 direct predecessor。AH installation
`9fe97ea8-275a-47d0-a0f1-d2064a8d62c6`、generation
`f2d43d1d-af4e-477d-afd3-4f1174404734` 已完成正常安装、配置、启用、successor registration 与九路原子 cutover；
保存定义由 AG rev36 disabled 转移为 AH rev37 disabled，并由 recovery rev12 生成 rev38 enabled，全程
`sourceReads=0`。自然 Worker 于 `2026-09-17T13:27:11.579666Z` 提交 attempt
`a73ed613-a7a3-43be-9177-c40dbe44c2d3`。Host 已在 Worker 持有长事务期间连续写入
`runtime_inflight_lease_renewed`，attempt heartbeat 与三项资源到期时间持续推进，且越过前三代约十分钟的过期失败窗口；
该运行必须继续自然完成，不因耗时延长而重发。只有 attempt terminal succeeded、十二 Run 同批完成、保存产物/关系/manifest
一致且无 canary/越权副作用，才允许执行第 5/6 的立即禁用与终态验证。

AH 自然运行已证明 installation/binding 锁规避和专用租约续订生效：attempt
`a73ed613-a7a3-43be-9177-c40dbe44c2d3` 的 heartbeat 与 `runtime_inflight_lease_renewed` 连续推进约四小时，
十二份 dataset receipt 自然落下十一份；但在 P11 完成、P08 等待执行期间，Runtime Host 的会话健康检查以 `TimeoutError`
退出，关闭流程于资源原到期时间之前主动释放三资源，attempt 随后以
`RUNTIME_REQUEST_NOT_CURRENTLY_ADMITTED` revision517 failed。十二 Run 仍同批 running、无部分 completion、无新 source read，
因此 AH 不得重放或补写。

直接根因位于 `RuntimeSession.check_health` 的预算边界。同一持久会话用 `RuntimeSession.lock` 串行化 business invoke 与 heartbeat；
invoke 已由 `_exchange(..., timeout=30)` 严格限制，但 health 当前把等待该本地锁也包含在三秒协议预算中。只要三秒心跳恰逢一个合法的
三至三十秒 business invoke，health 尚未发出 heartbeat 就把 session 标记 failed 并清理容器。这不是远端 runtime 不健康，且重试
Provider 或延长资源 TTL 都不能修复。

下一最小修复只调整 `services/aos-api/aos_api/extension_runtime/session_supervisor.py` 及专项测试：health 先等待同一 session lock；
由于持锁者只可能是已有三十秒上限的 invoke 或已有三秒上限的 heartbeat，该等待本身有既存硬上界。取得锁后才开始三秒 heartbeat
协议预算，继续严格校验 nonce/protocol/status；实际 heartbeat 超时、协议错误、进程退出或清理不确定仍立即 fail closed 并释放资源。
测试必须证明 health 在合法在途 invoke 持锁时不会提前发 heartbeat、不会关闭 session，锁释放后完成 exact heartbeat；同时保留
真实 heartbeat 超时会标记 failed 并清理的回归。修复通过后暂停 rev38、正式 detach AH，在安全空窗重载 Host/Worker，并用 direct
successor AI 以 recovery rev12→rev13 继续相同 manifest 的自然验收。

实现已严格限制在 `session_supervisor.py` 与 `test_session_health.py`：本地锁等待移出三秒 heartbeat 预算，协议交换与 exact response
校验仍在三秒内。专项 session/owner/persistent supervisor 为 29 passed、5 skipped；扩大到 Runtime Host、preparation worker、
owned verification/control、live installation owner、runtime Store、正式 Host 脚本与签名生命周期为 69 passed、8 skipped。
所有跳过项均为测试既有的环境条件跳过，无失败；方案所述真实 timeout 清理和合法在途 invoke 串行等待均已有直接回归。

系统重启后原 `m1` 控制 API 与 canonical install 租约已越过 `2026-09-17T23:59+08:00`，脚本先按设计拒绝执行；依据用户继续
独占 `m1` 的明确授权，只把这两条原 scope、原排除项租约续签到 `2026-09-20T23:59+08:00`，没有扩大到 push、230 L0、
外部发布或 canary 写入。随后 AH 以 members12/running12/savedInput1/recovery12/fencedBinding1/releasedResources3 的精确事实
暂停 rev38，得到 rev39 disabled，`sourceReads=0`。正式 disable operation
`414e0c58-a252-48f6-b834-4fcdd6f5cbba` 已闭合 fence/detach；九路为 legacy rev77/group104，binding rev9/epoch5，
零 running/unresolved/pending/canary。detach Receipt `9b50a8eb-ed85-4c7b-9010-16e0bbea5875` /
`sha256:adc874873a141d0d925c06c0b5cc844a52e281780096a85e7a5d9ca5ea866396` 是 AI 唯一合法 direct predecessor。

安全空窗重载后 Host PID `37869`、Worker/API PID `38214`；18181 已监听，Host status 为 active/liveTargets0/canary0。
Worker 第一次重载也因原 `A0V-NATURAL-CHAIN-MAIN-UPGRADE-20260915` 租约到期而拒绝启动，按相同用户授权只续签原 scope/
原排除项到 `2026-09-20T23:59+08:00` 后恢复，未扩大副作用权限。

AI 已走完整 direct successor 生命周期：installation `59d91f1c-efd7-4097-8ce0-1d4fa9452c0f`、generation
`3512c4da-841c-4bd6-a711-343c163b0632`、lock
`sha256:4873953acc7c69863fc034dd57b3c681eb67e05c5be2090abd913365d73daada`、config
`1ceda024-1a6b-4714-9541-0327ab81a16f@1` / `sha256:901a8b27886f830afc15ebe106194bbed65ddd7708f6220d851eb07b2eaa0ed6`。
successor Receipt `71c013e7-4022-4faa-9914-27a73ad52795` 精确引用 AH detach；cutover operation
`bbe417ce-4cbe-4cc3-a674-3005b618f32d` 已闭合 approve/prepare/pause/commit/validate/resume，九路 current 为
extension rev78/group105，target runtime rev6、claim resumed、零在途。

保存定义已从 AH rev39 disabled 转移为 AI rev40 disabled，再以 recovery rev13 生成 rev41 enabled；十二 control 均绑定 AI，
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，全过程
`sourceReads=0`。下一动作只能等待自然 Worker 提交新 recoverable_store attempt；不得调用 `run_definition` 或重发恢复。
验收重点是业务 invoke 持锁超过三秒时 Host 不再误杀 session，三资源续租持续，并最终看到 attempt succeeded、十二 Run 原子完成。

AI 自然 Worker 于 `2026-09-17T18:10:05.282637Z` 提交 attempt
`4cf91136-4d6b-4e02-b817-04d8cec404cb`。本次 session health 修复已被真实长运行验证：四小时以上业务计算期间
attempt heartbeat 与三项资源租约持续推进，Host 没有再因合法 invoke 持锁超过三秒而误杀 session；十二份
`ecommerce_ingress_dataset_receipt` 最终于 `2026-09-17T22:04:45Z` 前后全部自然落账，未重复读取商城来源。

但完整组尚未成功。attempt 在 `2026-09-17T22:27:10.053009Z` 以 revision508 failed 结算，Worker 只记录
`PermissionError`、`error_origin=_operate`；十二 Run 仍全部 `running/executorStopped=false/finishedAt=null`。只读阶段核对证明
`pipeline_snapshot_group_relationship` 已存在唯一当前行，而 `pipeline_snapshot_group_link_command` 与
`pipeline_snapshot_group_retirement` 均为零行，因此失败边界位于不可变 relationship preparation 之后、link command
持久化之前。12/12 dataset Receipt 是已提交事实，不等于 Run 或组完成；当前禁止 disable definition、补写 Run、重放
`run_definition` 或创建新 attempt。

下一最小诊断/修复切片限定在完成链的 current-authority 读取边界：先用隔离 PostgreSQL fixture 复现 saved-successor recovery
已写 relationship、12/12 dataset Receipt、Run 仍 running 的 exact 状态，要求 link preparation 首次读取走 completed immutable
input 且仍由 current recovery authority、当前 control、原 source claim 与 Store projection completion 联合校验。先形成能稳定暴露
具体 PermissionError 分支的 RED；只有该 RED 证明确定性代码缺口后，才最小修改对应 Owner，并验证零新 source read、零第二份
dataset Receipt、原 relationship 精确复用、link/retirement/十二 Run 在一个原完成协议内收口。真实 AI attempt 维持失败事实，
不作为修复后的可执行授权；修复后若需 successor，仍须沿暂停、disable/detach、重载和 direct successor 正式路径推进。

隔离 PG RED 已把生产故障收敛为 successor control 排序缺口。`PipelineSnapshotGroupOwner` 按当前 control resourceId
确定性排序；跨安装 successor 会生成一组新的 control UUID，因此当前组顺序可以不同于原始组。恢复输入此前直接保留
`facts.parents` 的原顺序，却同时按当前组顺序生成 claim records；后续 link preparation 将二者 `zip` 后，会拿当前 control
去核对另一个原始 Run，确定性触发 `PipelineSourceClaimOwner._operate` 的 `saved recovery fixed member differs`，与真实日志的
`PermissionError/error_origin=_operate` 和 relationship 已写、link command 未写边界完全吻合。同安装 renewal 因 control identity
不变而无法覆盖这个缺口。

最小修复只落在 `pipeline_snapshot_group_input_owner.py`：先验证原 `facts.parents` 的 runId 集合与固定 recovery bindings
一一相等，再按当前 group member 对应的固定 runId 重排 parent，随后一起构造 claim records 与 current input；任何缺失、重复
或额外 parent 均 fail closed 为 `GROUP_RECOVERY_PARENT_MEMBERS_DIFFER`。新增 PG 回归先稳定 RED（反转当前 control 顺序时首个
parent runId 错配），修复后 GREEN；没有放宽 current authority、没有新增 source read、没有改变原始 parent 内容或 Receipt。
主库只读逐位对账进一步确认真实 AI 组正好命中该缺口：原 immutable parent 顺序与 successor 当前 control UUID 排序后的
固定 Run 顺序在十二个位置上 `0/12` 相同，而两侧 Run 集合完全相同。因此这不是推测性修补；它解释了为什么十二份对象
Receipt 均可独立完成，而完成链首次把当前 control 与 parent 成对复核时必然拒绝。

### AI 失败后的 AJ 正式接续方案（2026-09-18）

`9bfc5438` 已修复 successor parent/current-control 排序缺口，但 AI attempt
`4cf91136-4d6b-4e02-b817-04d8cec404cb` 是不可变 failed 事实，运行中的 Host/Worker 也仍为修复前进程。因此不得在 AI 上
重放、补写或直接热加载。重启后新鲜只读事实证明 Host 仍健康持有 AI，binding rev6/epoch3 ready、三资源仍 pending，且没有
running attempt；等待 recovery 窗口本身不会让健康 Host 退出。接续固定为：先在 attempt failed rev508、members12/running12、
savedInput1/recovery13、datasetReceipt12、relationship1/link0/retirement0、canary0 的 exact 状态下把 definition rev41 正式暂停为
rev42 disabled；随后由原 disable Owner 以 AI 当前 binding revision 和 installation etag 完成 fence/detach，九路必须
全部回到 legacy 且无 running/unresolved/pending/canary。

空窗形成后停止并重启 Host 与独立 Worker，使 `9bfc5438` 成为实际加载代码。AJ 必须是 AI detach Receipt 的 direct successor，
走原安装、配置、启用、successor registration、九路原子 cutover 全流程；不得复用 AI generation 或绕过生命周期表。保存定义只从
rev42 disabled 转移到 AJ disabled，再以 recovery rev13 的 exact ref 续签 rev14 并启用；原 group、manifest、十二 Run 与已落账的
十二 dataset Receipt 全部复用，`sourceReads=0`。自然 Worker 是唯一可创建新 recoverable_store attempt 的入口。

AJ 验收必须同时证明：新 attempt terminal succeeded；十二 Run 同批 `succeeded/executorStopped=true/finishedAt!=null`；原 dataset
Receipt 仍每个 Run 一份且总数不增加；relationship 精确复用，link command 与 retirement 只各落唯一合法记录；definition 随即
禁用；无 dev-org 写入、无外部动作、无手工 `run_definition`。任一 exact precondition 不符即停止在当前阶段，不猜测修表。

执行 pause 前发现旧 Worker 已在第一笔 failed 后于 `2026-09-17T22:27:38.255561Z` 自然创建第二笔 attempt
`17ab28a9-7623-45fc-ba15-c0cb38c17ea5`，并持续 heartbeat 到本次有序停机；此前只读状态脚本固定查询第一笔 attempt，因而漏报。
pause-failed 门禁正确拒绝了在途状态，没有写 definition。Host/Worker 已通过原 launchd job bootout 停止，第二笔 lease 于
`2026-09-17T23:45:28.294609Z` 到期。当前优先走系统原生 `ExpiredSignedReadAttemptRecovery`：新 Worker 只能先把过期 running
attempt 标为 abandoned，再由 current enabled binding 和同一 operation/request hash 创建下一 ordinal；这不重读来源，也不重放
外部动作。Host 先加载 `9bfc5438` 并恢复 current target，Worker 后启动；若自然下一 attempt 成功则无需 AJ，随即按完整组路径
disable definition。只有再次 terminal failed 且无 running attempt 时，才进入上段 AI→AJ 正式接续。

AJ 已按上述正式路径完成安装、successor registration 与九路 cutover：installation
`cc6b62cf-1d0c-4f6c-bf6f-5cfc80679244`、generation `6dc4f34a-5cc6-4b20-bfb8-8a002a7dcd76`，九路为
extension routeRevision81/groupRevision108，claim resumed。保存定义由 AI rev42 disabled 转移为 AJ rev43 disabled，
再由 recovery rev14 生成 rev44 enabled；manifest 与十二份 dataset Receipt 全部复用，`sourceReads=0`。自然 Worker 于
`2026-09-18T00:07:37.489280Z` 创建 attempt `cc6db008-f9fa-4400-bed2-7585fcd159cd`，证明重启后的自然接管入口有效。

本轮为排查权限读取的 installation 行锁，先后短暂停止 Host 与 Worker。Worker 停止后 AJ attempt 在 lease
`2026-09-18T00:15:10.078923Z` 到期，并由原生过期恢复于 `2026-09-18T00:15:26.924957Z` 标为 abandoned revision13；
Host 空窗跨过资源租约后按 fail-closed 规则释放三项资源，并把 AJ binding 推进为 revision7/epoch4、disabled/fenced/unknown。
十二 Run 仍为 running，relationship1/link0/retirement0，未增加 dataset Receipt 或 source read。该事实说明系统没有在重启窗口
越权续跑，但 AJ 已失去执行权，不能原地复活。rev44 已在 members12/running12/savedInput1/recovery14/fencedBinding1/
releasedResources3 的 exact 守卫下暂停为 rev45 disabled。

下一步固定为 AJ→AK direct successor：先由正式 disable Owner 对 AJ 完成 fence/detach，取得唯一 detach Receipt，并确认九路回到
legacy、无 running/unresolved/pending/canary；随后在当前源码上创建 AK，走安装、配置、启用、successor registration、九路原子
cutover。保存定义只能从 AJ rev45 disabled 转移到 AK disabled，再以 recovery rev14 的 exact ref 续签 rev15 并启用，仍保持
`sourceReads=0`。本次不再中断 Host/Worker；自然 AK attempt 运行期间只用不争用 installation current 行锁的 runtime 只读查询观察
attempt heartbeat、三资源续租和完成产物。只有 attempt succeeded、十二 Run 原子完成、dataset Receipt 总数仍为12、relationship1/
link1/retirement1 且 canary0，才允许立即 disable definition。

### AK 睡眠中断后的 AL 正式接续方案（2026-09-18）

AK 已证明 `9bfc5438` 的 successor parent/current-control 排序修复越过原 AI 确定性故障点：自然
`recoverable_store` attempt `47787577-c2a4-401e-ace2-540304f79ef4` 从
`2026-09-18T00:36:38.589944Z` 连续运行，revision 508 及以后仍保持 running，最终在睡眠前推进到
revision 683。原 relationship 精确复用；唯一 link command 已提交，`linkCount=1168`、command hash
`sha256:f16b566f1974831e0c662ea67049c77acc1febd12c7bd8ff98e9651d0d396970`。该事实证明完成链已越过
AI 的 `saved recovery fixed member differs`，不是原 PermissionError 重现。

本次未完成的直接外因由 macOS 电源日志精确确认：机器电量降至 1% 后，于
`2026-09-18 14:21:38 +0800` 因 `Clamshell Sleep` 睡眠，`14:29:41 +0800` 转入 `Low Power Sleep`，
到 `15:25:55 +0800` 才从 Hibernate 唤醒。Attempt 最后 heartbeat 为
`2026-09-18T06:21:11.390155Z`，lease 于 `06:23:11.161153Z` 到期；Host 按既有 fail-closed 规则停止
会话、释放三项资源并把 AK binding 推进到 revision7/epoch4 disabled/fenced/unknown。唤醒后原线程不能再取得当前
运行权，于 `2026-09-18T07:26:04.132058Z` 以 revision684 failed 结算。该失败属于宿主休眠越过实时租约，不能通过
延长 TTL、补写 heartbeat、复活 AK 或直接重放规避。

失败终态保持原子：十二 Run 仍全部 running/executorStopped=false/finishedAt=null；dataset Receipt 仍为12，
relationship1、link command1、retirement0。link command 虽已不可变持久化，但 Store 尚未应用，正向租户
`ecom_link=0`，因此不存在未知提交或需要猜测重发的外部副作用；definition rev47 仍 enabled，保存 manifest 与 recovery
rev15 不变，canary0。后续执行必须先在 members12/running12/savedInput1/recovery15/fencedBinding1/
releasedResources3 的 exact 事实下暂停 rev47，再由正式 disable Owner 完成 AK fence/detach；九路回到 legacy 且零
running/unresolved/pending/canary 后，detach Receipt 才能成为 AL 的唯一 direct predecessor。

AL 继续沿原不可变 successor 路径：创建全新 installation/generation/config，完成安装、验证、配置、启用、successor
registration 与九路原子 cutover；保存定义只允许从 AK disabled revision 转移为 AL disabled，再以 recovery rev15 的 exact
ref 生成 rev16 enabled，`sourceReads=0`。原 group、manifest、十二 dataset Receipt、relationship 及 link command 全部按
各自 exact hash 重放；Store link batch 只能使用已持久化 command 的原 idempotency key，禁止另造 command 或手工调用
`run_definition`。自然 Worker 是唯一 Attempt 入口。

本轮实现清单固定为：先新增 `scripts/a0v_al_replacement_recovery.py` 与
`services/aos-api/tests/extension_runtime/test_a0v_al_replacement_recovery.py`，只完成 AK detach Receipt 直接后继的标准安装生命周期；
取得实际 installation、generation、lock、config 后，再新增 `scripts/a0v_al_successor_business.py`、
`scripts/a0v_al_successor_cutover.py`、`scripts/a0v_al_saved_snapshot_recovery.py` 及三个同名专项测试。generation 与
configuration 身份必须采用原 preparation/configuration Owner 返回并由数据库提交的不可变值，不允许执行器预分配或替换；
cutover operation 固定使用新的 `239d8393-05ac-4797-9e9d-eeddd756e100`，并由原 cutover Owner 校验和落账。

AL 验收须同时满足：Attempt terminal succeeded；十二 Run 同批 succeeded/executorStopped=true/finishedAt 非空；dataset
Receipt 总数仍为12；relationship/link/retirement 各唯一一条；Store 当前 link 为原 command 的 1,168 条且 projection
completion pending=0；definition 随即禁用；canary0、无新源读取、无越权外部动作。执行期间必须保持机器接入电源并阻止系统
睡眠；该环境保护只维持现有进程运行，不修改产品租约、授权或失败语义。任一 exact precondition 不符即停止当前阶段并诊断。

AK 的正式退役已于 `2026-09-18T07:46:57Z` 完成：definition 先精确暂停为 rev48 disabled，随后原 Disable Owner
接受 operation `6d44d780-3a8e-4311-8bd5-be028e6e098b`。fence Receipt
`44fa2b0b-0835-4527-a79b-9d4ad8c5b777`（`sha256:0e16397a9f17700db9a43dd7bbff5cb2f15e8bb88c1fc767fe860cf281d799b5`）
与 detach Receipt `ec99c80b-ad80-47aa-af4a-4fb45fd0602d`
（`sha256:150a01e8b8eda58d8ed74736a3283c509d2af06e143a82b0faaed88f38351ae9`）均已不可变提交。九路为
legacy routeRevision86/groupRevision113，AK binding rev9/epoch5 disabled/fenced/unknown，三项资源 released，
running/unresolved/pending/canary 均为0；执行器确认 `resendDisable=false`、`externalEffects=0`。该 detach Receipt 是
AL 唯一允许的 direct predecessor。

AL 已沿该 direct predecessor 完成标准生命周期：installation
`071e1c31-c464-4735-952e-17adf0ac97f7`、generation `d50a7eed-18e1-491a-9323-ab3ca693dc3a`、lock
`sha256:49d7d8b367e19f3c7f8c920d061757477af9a0bf6bc3847101ca7ce348006608`、configuration
`4dae773b-1938-4419-b1d8-0ffc32f52dd0` / `sha256:025bacc0c4ece109bda582f5fc280610f7ed81db5e12b81d714c6f5d17ed8d5c`。
runtime-apply、verify、configure、enable 四个 operation 均由原 Host 成功结算；binding rev4/epoch3 ready，三资源 pending，canary0。
successor registration Receipt `cffd46f0-3c95-46bd-be11-01efb0526e49` 以 AK detach Receipt 为唯一前驱；cutover operation
`239d8393-05ac-4797-9e9d-eeddd756e100` 已完成 prepare/pause/commit/validate/resume，九路为 extension
routeRevision87/groupRevision114，claim resumed，且切换窗口无 claimed/unknown/running attempt。

保存输入随后只复用原十二源：definition rev48 disabled → rev49 AL disabled；recovery rev15 → rev16
`sha256:c742a6a8d65025354ec0779fdcabb567250eda8ba6e3e0e2fc7e241af8ebed99`，同时生成 definition rev50 enabled，
manifest 保持 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，`sourceReads=0`。自然 Worker 于
`2026-09-18T08:09:23.025906Z` 创建 recoverable_store attempt `3e319ca5-9e8d-4b0e-a034-295cd3e5b645`；
执行期间由独立 `caffeinate -dimsu` 保护宿主不休眠，该进程不修改 AOS 租约或授权。

## 第 5/6：立即 disable 与终态验证

完整组确认后立即用当前 ref disable definition。验证 definition disabled、无 pending/claimed/unknown、U 资源与
Host 正常、canary0；组完成时间与十二源新鲜度满足 24 小时经营参谋窗口。保存完整只读 JSON，不包含凭据或商城正文。

## 第 6/6：下一波

以新 U 完整组重建经营参谋 Case/once Policy v3 和 SchedulePolicyControlReceipt；计划为空时由 baseline worker
自然产生 occurrence → Case/Run/暂停分析链，随后继续 exact 评审、内部内容任务、能力预算审批、产物评审续跑、
总控复盘与 Wiki 候选。不得手工创建 occurrence、Run、Evidence 或 Fulfillment。

### AL 执行期间的重启恢复与 Prime 长记忆辅助（2026-09-18）

宿主休眠唤醒后先按数据库权威状态核对 AL attempt、Lease、binding、十二 Run 与完成链事实；只要原 attempt 仍为
`running`、心跳和 Lease 持续推进，就不得切换 successor、重发 Store 或重启 Host/Worker。重新启动独立
`caffeinate -dimsu` 仅保护宿主环境，不改变产品租约和执行权限。

Prime Agent 只作为开发过程的独立长记忆辅助，不进入 AOS 产品逻辑，也不提供业务授权。当前用户级 launchd
安全启动器所引用的 WorkBuddy `22.22.2` 目录已被升级替换为 `22.22.2-2`，而新目录不再安装 Prime CLI。
最小恢复限定为 `scripts/prime-agent-safe-daemon.sh`：使用该目录的 Node 执行仓库内已构建的
`prime-agent/packages/coding-agent/dist/bundle/cli.js`，继续只从权限 `0600` 的 `~/.prime/agent/auth.json`
读取认证。`--check` 必须同时验证认证文件、Node 与 CLI 入口；验证只允许安全预检、daemon 状态回读和共享记忆
健康回读，不得写 AOS 数据库或替代本文件、Receipt、数据库与浏览器证据。

本切片文件级清单仅包含本方案文档与 `scripts/prime-agent-safe-daemon.sh`。若任一运行入口缺失则 fail closed，
不得回退为命令行明文密钥或环境变量凭据。

重启恢复执行记录：宿主于 `2026-09-18T15:25:55+08:00` 从 Hibernate 唤醒，Docker `colima-aos-extension`
中的 `aos-a0v-recovery-pg` 保持运行，8434 与 5173 均恢复。只读数据库复核至
`2026-09-18T09:42:52Z` 时，AL attempt 仍为 `running@revision186`，heartbeat/Lease 持续推进；固定 definition
`cb0dba8c-803f-5caf-8011-b763d349f2ba` 为 rev50 enabled 并绑定 AL installation/generation。十二 Run 均为
`running/executorStopped=false`，dataset Receipt=12、relationship=1、link command=1（1,168 links）、
retirement=0、当前 `ecom_link`=0、projection pending=0、三资源 pending、canary=0。因原 attempt 仍健康，未重启
Host/Worker、未切 successor、未重发 Store；已恢复独立 `caffeinate -dimsu`。

浏览器只读验收确认 `org-org/dev-project` 的本体管理页完整加载，AOS v1.6.5、对象类型与图谱健康可见；电商工作台
目录仍显示暂无可见入口，按当前阶段记录为未完成，不以页面可访问替代经营闭环验收。AL 专项 5 tests passed；
session/resource health 与 link/retirement 累计回归 9 passed、41 个需独立 PostgreSQL fixture 的用例 skipped。
全局 closure verifier 仍报告工作树中既有经营链文件的 hash drift，因此本波不宣称全局 closure green，也不吸收或
覆盖这些既有改动。

Prime 安全启动器已改用 WorkBuddy `22.22.2-2/bin/node` 与仓库内构建 CLI；`--check`、shell 语法、socket 持有者
和 `prime-agent status --json` 均通过，daemon 为 `current`、协议版本7、版本0.7.1。修复已以 m1 提交
`4ba931c4` 固化且未 push；Prime 继续只作为独立开发长记忆辅助。

### AL 完整组后的经营参谋 Policy v3 自然首链方案（待 AL GREEN 后执行）

主库只读盘点确认当前经营权威不是空白：`case-qyh-advisor-baseline-20260917` 为 ACTIVE rev4；
`schedule-qyh-advisor-baseline-once-20260917` 为 enabled rev2。rev1/rev2 两个 schedule occurrence 均已
cancelled，对应 dispatch attempt 均为 `closed_unaccepted`；两份不可变 closure Receipt 都声明
`businessAccepted=false`、target runCount=0，当前该 Case 下 AnalysisRun=0，dev-org Case/occurrence=0。
因此不得另建平行 Case，也不得重开旧 occurrence。

AL 完整组 terminal succeeded、十二 Run 原子完成、definition rev51 disabled 且最新快照仍满足经营时间窗后，才允许
新增 `scripts/a0v_al_advisor_baseline_v3.py`。它必须先冻结以下 exact 前置：Case rev4/hash、Policy rev2/hash、两份
closure Receipt、AL installation/generation/epoch3、完整组/manifest/十二父 Run 引用、当前角色与
`ecommerce_growth_schedule_put` Action snapshot。随后以 maker/checker 分离的短时 Approval，按
`expectedPolicyRevision=2`、`expectedCaseVersion=4` 提交同一 Policy 的 v3；Policy 必须引用 Case rev4，并由 canonical
router 绑定当前 AL runtime。不得直接 INSERT/UPDATE 权威表。

Policy v3 保存后只能由 `BaselineAssessmentWorker` 的 15 秒自然轮询生成新的 once occurrence；禁止脚本创建 occurrence、
claim、AnalysisRun、Evidence 或 Fulfillment。验收先等待 occurrence 自然出现并由 Worker 受理，再验证它引用 Policy v3、
AL generation/epoch、最新完成快照组及当前 SchedulePolicyControlReceipt。若 Worker 返回 `needs_attention`，先按 Receipt
和 unknown/reconcile 规则诊断，不续签 Policy v4，不手工重放。

当前波文件级清单预定为：本方案；`scripts/a0v_al_advisor_baseline_v3.py`；
`services/aos-api/tests/extension_runtime/test_a0v_al_advisor_baseline_v3.py`；以及 closure manifest 的对应分类/哈希。
实现只复用现有 Case/Policy/Approval/router/自然 Worker，不修改业务服务；只有专项测试证明 exact CAS、旧 closure、
AL runtime 与 canary 守卫后才可在主库执行。

### AL 预算治理窗口到期后的失败边界与 AM 正式接续方案（2026-09-18）

#### 第 1/6：失败原点与提交边界

AL 自然 `recoverable_store` attempt `3e319ca5-9e8d-4b0e-a034-295cd3e5b645` 从
`2026-09-18T08:09:23.025906Z` 持续运行到 `2026-09-18T11:21:54.803374Z`，最终以 revision382
`failed` 结算。Worker 安全日志把失败固定为 `PermissionError/error_origin=_load_governance_policy`；当前 budget policy
`a0v-ecommerce-budget-policy-v1@7` 的有效期精确终止于 `2026-09-18T11:21:54.706218Z`，比 attempt 终态早约
97 毫秒。quota policy 仍有效。因此本次失败是长任务跨过既有预算治理时间窗后的当前授权拒绝，不是模型、商城来源、
关系计算或 Store 性能错误，不允许通过放宽有效期判断、改系统时钟或伪造旧策略继续。

失败边界已经完整只读对账：十二 Run 仍为 `running/executorStopped=false/finishedAt=null`；dataset Receipt=12；
relationship=1；link command=1、`linkCount=1168`、command hash
`sha256:f16b566f1974831e0c662ea67049c77acc1febd12c7bd8ff98e9651d0d396970`；retirement=0。
该 command 对应的 `ecom_ingest_receipt=0`、当前 `ecom_link=0`、authoritative link outbox=0、projection pending=0，
所以失败发生在不可变 link command 提交之后、Store batch 提交之前，不存在未知 Store 提交或可猜测重发的副作用。
dev-org canary=0，且 AL generation 下没有第二笔 running attempt。definition rev50 仍 enabled，Worker 后续周期只在
当前治理读取处失败关闭，没有新增 attempt 或业务写入。

#### 第 2/6：先暂停失败 definition

先给 `scripts/a0v_al_saved_snapshot_recovery.py` 增加 `pause-failed`，只接受上述 exact 失败事实：attempt id/revision382、
零 running attempt、members12/running12、savedInput1/recovery16、dataset12、relationship1、link1/linkCount1168、
retirement0、Store receipt/link/outbox/pending 全零、AL binding rev6/epoch3 ready+enabled+unfenced、三资源 pending、canary0。
守卫全等后才允许用原 Definition Owner 将 rev50 推进为 rev51 disabled；任一事实漂移均在写前停止。不得手工
`run_definition`、不得另造 link command、不得把 failed attempt 改写为 succeeded。

#### 第 3/6：正式续签治理权威

沿已评审的 `text-readiness-v2` 路径建立全新私有 evidence/journal：三个公共合成探针各最多一次 Provider 调用，
不读取商城正文、不修改业务 Run、不发送外部消息。三例通过后由 `a0v_formal_text_model_renewal.py` 冻结并按 head CAS
发布新的 budget/runtimePolicy/price/model/route revision；失败或未知结果不换 key 重发。新策略必须具有足以覆盖 AM
完整恢复和后续经营参谋观察的有限窗口，仍保持费用暂不计价、无 fallback、一次模型 attempt 的既有约束。

#### 第 4/6：AL 正式 detach 与 AM direct successor

rev51 disabled 后只使用原 disable Owner 完成 AL fence/detach，要求九路回到 legacy、binding disabled/fenced/unknown、
三资源 released、running/unresolved/pending/canary 全零，并取得唯一 detach Receipt。AM 必须以该 Receipt 为唯一 direct
predecessor，走安装、验证、使用新治理 ref 重新 stage 配置、configure、enable、successor registration 与九路原子 cutover；
不得复用 AL configuration 或 generation。

#### 第 5/6：保存输入恢复与完整组验收

definition 只从 AL rev51 disabled 转移为 AM disabled，再沿 recovery rev16 的 exact ref 生成 rev17 enabled；原 group、
manifest、十二 Run、十二 dataset Receipt、relationship 与 link command 全部精确复用，`sourceReads=0`。自然 Worker 是
唯一新 attempt 入口；Store 只能用原 command 的原 idempotency key。GREEN 必须同时看到 attempt succeeded、十二 Run
同批 succeeded/stopped、Store Receipt 与 1,168 links 落账、retirement 唯一、projection pending0、definition 立即 disabled、
canary0。

#### 第 6/6：下一波

AM 完整组 GREEN 后重新校验快照新鲜度，再执行已写好的经营参谋 Policy v3 方案；若 AM 仍失败，先按其不可变
attempt、Receipt 和 Store 边界重新诊断，不把本节授权外推为重发许可。本波文件级清单为本方案、
`scripts/a0v_al_saved_snapshot_recovery.py`、
`services/aos-api/tests/extension_runtime/test_a0v_al_saved_snapshot_recovery.py`，随后才按相同书面门禁新增 AM 生命周期文件。

#### AL detach 文件级施工清单（2026-09-18 续）

当前只读基线已固定：AL installation head 为 etag5 active、lock
`sha256:49d7d8b367e19f3c7f8c920d061757477af9a0bf6bc3847101ca7ce348006608`；binding rev6/epoch3
enabled+unfenced+ready；三资源 pending；九路 extension rev87/group114；definition rev51 disabled；全租户 running attempt=0、
AL unresolved occurrence=0、pending runtime operation=0、dev-org canary=0。

新增 `scripts/a0v_al_failed_retirement.py`，动作固定为 `preflight/request-disable/process-disable/audit`。preflight 只接受上述
完整基线和 failed attempt revision382、十二 Run running、Store 零提交；request 使用原 Runtime Disable Owner、etag5 与
bindingRevision6，先冻结唯一 intent；process 只 claim 该 operation 的既有 outbox delivery，禁止重发。终态必须为 binding
rev8/epoch4 disabled+fenced+unknown、三资源 released、九路 legacy rev89/group116、definition 仍 rev51 disabled、零
running/unresolved/pending/canary，且 lifecycle 恰有 fence/detach 两张 Receipt。

新增 `services/aos-api/tests/extension_runtime/test_a0v_al_failed_retirement.py` 固定身份、前后 revision、Definition/Run/Store
守卫、单次 outbox claim 与 direct successor 所需 detach Receipt。退休 GREEN 后才新增 AM replacement 文件，避免把尚未取得的
AL detach Receipt 写入后继安装权威。

#### AM direct successor 文件级施工清单（2026-09-18 续）

AL 已通过 operation `c9328938-3b56-4a8d-ac38-54f7abf70416` 正式 detach；唯一 detach Receipt 为
`bd92aa48-77b6-4c34-82f9-0ede171083b3`，hash
`sha256:b8990ed467aed1bdfc40e5fb56e4455e2ece7114045f37a15f8f4099a313e1df`。AL 终态固定为
binding rev8/epoch4 disabled+fenced+unknown、三资源 released、九路 legacy rev89/group116、definition rev51 disabled。

新增 `scripts/a0v_am_replacement_recovery.py`，仅允许上述 AL 终态作为 direct predecessor；使用与 AL 相同的四包正式版本和
当前受信 signed bundle 树，新建唯一 AM approved installation。动作固定为
`preflight/create-am/prepare-am/verify-am/stage-am/configure-am/enable-am/observe`，每一步依赖前一步私有 immutable result；
create 前冻结数据库备份和 predecessor ref，未知结果不得再次创建。

stage/configure 必须读取刚续签的 budget/runtime policy rev8 与 model/route rev7，不得复用 AL 的旧 configuration ref；enable
终态要求新 generation ready+enabled+unfenced、三资源 pending、零 canary。新增
`services/aos-api/tests/extension_runtime/test_a0v_am_replacement_recovery.py` 固定 direct predecessor、版本、唯一 create intent、
动作顺序和禁止手工 `run_definition`。AM enable 后再单独形成 successor registration 方案和代码，不在安装脚本中偷做九路切换。

#### AM successor registration 与 cutover 文件级清单（2026-09-18 续）

新增 `scripts/a0v_am_successor_business.py`：严格读取 AM installation
`fd28d180-db24-4568-a848-101fcd3aa3c5`、generation `d6bc117e-d19d-4413-beb4-02884206e290`、
lock `sha256:f2bcef04d615b0c6a19b2a0465be392130eb6a85627135a8c58a1177901942cc`、config
`05602ff4-db16-4519-bb68-ed790307fa5b@1` 与 binding rev4/epoch3 ready；父权威只接受 AL detach Receipt
`bd92aa48-77b6-4c34-82f9-0ede171083b3` 及 hash
`sha256:b8990ed467aed1bdfc40e5fb56e4455e2ece7114045f37a15f8f4099a313e1df`。注册 expectedGroupRevision=116，
九路必须全为 legacy rev89/group116，且 running/unresolved/runtime pending/canary 均为零。

新增 `scripts/a0v_am_successor_cutover.py`，固定 cutover operation
`23bc8ec0-1a67-4ae8-9210-de67114f7a6a`，依次执行 approve/prepare/pause/commit/validate/resume；每阶段先冻结
immutable intent，已有 intent 时只允许 inspect，不允许重发。resume 后九路必须精确指向 AM generation、epoch3、unfenced，
revision90/group117；AL 保持 detached，definition 保持 rev51 disabled。

新增 business/cutover 两个专项测试，固定 AM/AL/ref/group/revision、禁止 fallback/外部效应和阶段跳跃。浏览器验收只在 AM
九路路由已注册且保存输入尚未启用时做只读检查，不触发业务动作；完成后再进入 definition/recovery 转移。

## 文件与验证

- 新增 `scripts/a0v_u_twelve_source_snapshot.py` 与专项测试；在 Definition Owner 仅增加已卸载前代的严格退休守卫。
- 每阶段冻结 intent/result，存在结果时只读，不重发。
- 定向测试、原 schedule/source-control 测试、AR2-7、`git diff --check`、方案/实现一致性均须通过。

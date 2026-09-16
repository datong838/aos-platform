# SC4-5L6Z-P：released runtime 的 occurrence 正式退役方案

日期：2026-09-17

## 当前权威现场

P installation `9950e057-5cb4-4849-a499-35837d8d0fb6`、generation
`df883b18-0170-410b-8424-442c7cdd60b4` 的 runtime 已是 revision7/epoch4、
disabled/fenced/unknown，三项资源均 `released + observed_release=true`。源 schedule 已 disabled，
但 Policy11 event binding revision1 仍 enabled；十路 dispatch 仍指向 P epoch3/group revision49，
且未 fence。P 有 65 个 event occurrence：5 个 `needs_attention` 搭配已过期的 unknown attempt，
60 个 pending；全部目标 runtime Receipt 和 BusinessInvestigationRun 为零，closure Receipt 为零，
`dev-org/dev-project` canary 为零。

此前 Policy11 disable 已冻结带 approval 的 intent，但没有 result，数据库也没有对应 command
Receipt，binding 仍是 revision1/enabled。该结果已只读对账为“未提交”，不得重发原 intent；
released recovery 使用新的负向专用幂等键和无 approval 命令。

## 合约死锁

现有 `ReleasedProductEventControlService` 与 `a0v_074` event fence 都要求 unknown attempt 为零；
现有 `ecommerce_unaccepted_analysis_close_a0v_060` 又要求先有 verified fence，且只接受
`needs_attention + unknown`，不接受从未领取的 pending。于是当前真实 released 现场无法通过
任一合法顺序收口，不能用直接 UPDATE 绕过。

## 最小前向修复

新增 `a0v_076`，只扩展负向退役，不增加任何 enable、重试或业务接受能力：

1. released Policy disable 和 released event fence 可以容忍一组“安全 unknown”：必须是同一
   installation/generation 的 event analysis occurrence，状态 needs_attention、attempt unknown、
   claim 已过期、occurrence/attempt receipt 均为空，且目标 command Receipt 和计算得到的
   BusinessInvestigationRun 都不存在。任何 claimed、未过期 unknown、非分析 occurrence、目标
   Receipt/Run 或运行中的 runtime execution attempt 都继续 fail closed。
2. verified released fence 之后，UnacceptedAnalysisClosure 可在 released runtime 模式下工作：
   runtime 必须保持更高 epoch 的 disabled/fenced/unknown，三资源全部 released，fence Receipt
   必须声明 released recovery，Policy binding 必须 disabled，当前 dispatch 必须与 fence 的
   afterSnapshot 完全一致。
3. 同一逐 occurrence Closure Receipt 同时支持两种原态：
   `needs_attention + expired unknown attempt`，或 `pending + 不存在 dispatch attempt`。pending
   的 target key 固定为 `automation-occurrence:{occurrenceId}`；两种模式都再次检查零目标
   Receipt/Run，写入 businessAccepted=false Receipt，把 occurrence 置 cancelled，并只在存在
   attempt 时置 closed_unaccepted。不得批量无 Receipt 更新。

同步修改 `services/aos-api/aos_api/ecommerce_released_event_control.py` 的应用层镜像检查，新增
PostgreSQL 合约测试覆盖安全 unknown、claimed/未过期/已有目标权威拒绝、released fence 后
unknown 与 pending 收口、同键重放、租户隔离。先隔离库验证，再使用冻结哈希、单步 revision、
业务表指纹不变的两阶段脚本升级 main。

真实执行 preflight 后首次 disable 在事务内被 qualified owner 拒绝，未写入 Receipt：外层
`ReleasedProductEventControlService` 已采用上述安全 unknown 判定，但组合链中的
`ProductEventControlQualifiedOwner.run_without_source` 仍把所有 unknown 视为未 drain。该处必须
使用同一组安全 unknown 条件，且只影响 runtime 已推进到更高 epoch、disabled/fenced/unknown、
三资源完全 released 的既有负向分支；正常同 epoch disable 和任何 enable 路径不变。补充组合
测试证明 expired/no-target unknown 可通过，claimed、未过期、已有 target Receipt/Run 仍拒绝，
然后才允许重放同一 v6 disable intent。

系统重启后通用 Web 连接回落到本机默认开发库，首次 fence 审批在读取 ActionType 前即因表不存在
停止，未生成 Proposal/Approval。P 退役执行器必须从已验证的 `aos_meta_head` 连接提取当前进程
连接参数，只在 `_approve` 调用范围内显式设置 `AOS_DATABASE_URL` 并在 finally 恢复；不得依赖终端
残留环境，也不得把连接字符串写入公开证据或日志。

首次 closure apply 又在首条事务前发现重启后 registration credential 环境尚未由受控 launcher
恢复；私有、0600 的既有 main identity 及其验证 proof 均仍存在。执行器必须先调用 P 的受控
`setup()` 完成 identity preflight，再构造 `registration_connection`；不得生成新身份、复用 owner
直连或绕过 `aos_extension_maintainer/aos_runtime` 双角色约束。

该身份失败发生在第一条 closure 的 identity 文件校验阶段，尚未打开数据库连接；因此只留下
occurrence `018cec86-17b4-577c-965f-d371afecce78` 的 intent，没有 result 或 Receipt。恢复前冻结
一份 exact presubmit recovery proof，要求目录中恰好这一份孤立 intent、数据库同键 Receipt 为
零、intent 与 closure plan 完全一致。apply 只对这一个 proof 允许继续；若提交后结果文件未写成，
后续只能回读同键 Receipt，仍不得再次调用 closure。

## 执行顺序

1. 以新 recovery key 正式 disable Policy11，得到 ProductEventControl Receipt；
2. 经现有 exact 审批形成 released event fence Receipt，十路中只 fence event-control route；
3. 逐一关闭 5 个 unknown 和 60 个 pending，每个 occurrence 保留独立 intent/result/Receipt；
4. 验证 65 cancelled、5 closed_unaccepted、60 无 attempt、零 target Receipt/Run、零 canary；
5. 继续现有 shrink/detach/uninstall 生命周期，禁止把任何 P occurrence 改绑给 Q。

## 停止条件

任一 target Receipt/Run 出现、unknown 未过期、dispatch/runtime/policy revision 漂移、closure
Receipt 数量与 terminal occurrence 不一致、canary 非零，立即停止写入并只读对账。测试绿色
不构成真实退役完成证明。

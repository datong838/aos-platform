# SC4-5L6Z T：S released 退役与 clean successor 恢复方案

日期：2026-09-17

## 当前权威

S installation `77b8e5c2-db96-4d55-a808-1b62e00163d2` 仍为 active/etag5，lock hash
`sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8`；唯一 binding
generation `e621100a-baea-440f-9075-ae8a5290845a` 已为
`revision7 / epoch4 / disabled / fenced / desired=enabled / observed=unknown`。三项资源均
`released / observed_release=true`，apply operation 已由正式清理收口为
`failed / succeeded / PREPARED_RUNTIME_RELEASED`，其余 verify/configure/enable operation 均终态。

九项经营路由仍以 group revision60 指向 S epoch3/unfenced；这是历史 activation 的不可变分派快照，
不能仅凭 runtime fence 手工改成 legacy。全部 product-event binding 已 disabled；经营参谋 v1/v2
occurrence 已各自通过不可变 closure 终结，Policy v1 binding disabled、Policy v2 once binding 已消费且
无 unresolved attempt；十二源 definition rev9 disabled。当前无 running runtime execution、无 claimed/
unknown occurrence dispatch，canary 为 0。

## 第 1/6：S released 负向退役

新增固定执行器 `scripts/a0v_s_released_retirement.py`，复用已部署的 released-owner settlement 与
`EcommerceGrowthDisableDependent`，但只接受上述 exact S 状态、九路 group60、无第十条 event route、
无 enabled product-event binding、两条已关闭经营参谋 occurrence、rev9 disabled snapshot definition。
执行器写前冻结 intent，正式 request disable 后由原 RuntimeDisableConsumer 领取一次，完成 fence → detach；
目标终态为 binding revision9/epoch5/desired=disabled、九路 legacy/fenced、group62。未知领取或回执不重发，
只读 operation/Receipt。若唯一 Host 已先领取并终结同一个 operation，执行器只冻结
`claimedByHost=true / resendDisable=false` 的恢复证明并读取相同终态，不再次 claim。

## 第 2/6：clean T 安装与运行生命周期

新增 `scripts/a0v_t_replacement_install.py`，沿已验证 reinstall profile 固定四包版本
`core1.4 / niushop1.23 / growth1.10 / operations-base1.2`：

1. S detach 后创建 approved T，并保留创建前数据库备份；
2. T approved 且未准备时，按正式 Installation Owner 卸载 S；
3. T 依次 prepare → verify → stage → configure → enable；每一步使用独立 idempotency key、exact etag/
   revision 和不可变私有 result；
4. 只接受 T active/ready/enabled/unfenced、binding revision4/epoch3、三资源 pending/unreleased、canary0。

禁止复用 S generation、resource、container、operation 或 source control。若 prepare/verify 中断，按既有
reset + clean successor 合同另建后继，不复活失败代。

### 第 2/6 真实 Red 与 U 恢复修订（2026-09-17）

T 创建时错误地把已经 detach、即将卸载的 S 作为 `currentInstallationRef`。S 随后按原计划在 T prepare
之前卸载；T apply 于 `2026-09-17T01:02:20Z` 成功，verify operation
`bb953ef8-f925-492c-bfcc-82a2e684159e` 于 `01:02:39Z` 被唯一 Host 领取。正式
`guard_replacement_activation_in_transaction` 发现 S 已无 active baseline，正确抛出
`CurrentInstallationStaleError`；Host fail closed，并于 `01:02:41Z` 起释放 T 三项资源。T 保持
`applied@4`、无 binding，verify 仍为 accepted，不能重发，也不能通过修改内核放宽前任当前性守卫。

这里的缺陷属于执行顺序，不属于 RuntimeHost 或安装校验器。修复不得修改
`runtime_host.py`、`runtime_directory.py` 或 `installation_store.py`。沿用 R→S 已验收的恢复协议：

1. 等待 T 原 verify deadline 到期，以正式 `reset_preparation` 将 T 回到 `approved@5`；
2. 创建不带 `currentInstallationRef` 的 clean U，冻结全新 installation id、数据库备份与四包 lock；
3. 只有 U 为 `approved@3`、T 已无未决 operation 且三资源 confirmed released，才正式卸载 T；
4. 唯一 Host 依次消费 U prepare、verify；随后 stage、configure、enable，要求
   `active@5 / ready / enabled / unfenced`、三资源 pending/unreleased、canary0；
5. T/S 均不得成为 U 的 runtime predecessor；业务 successor registration 仍只引用 S 的正式
   detach Receipt 与 group62，U 只提供新的安装/代次执行目标。

新增 `scripts/a0v_t_interruption_recovery.py` 及对应测试；T 原脚本和不可变输出保留为失败证据。
每个写动作前 exact 读取 T/U、operation deadline、资源、canary，未知结果只读恢复，不重发。

AR2-7 闭包复核另发现已提交的 `ecommerce_baseline_assessment_discovery.py` 引用了已迁移领域合同，
但尚未进入施工清册，因而报告一个 `unclassifiedReverseCaller`。该模块是当前 Host 事务内的只读资格发现，
不属于本轮 U 生命周期代码。只向 `closure-manifest.md` 追加其 Host 去向、边界和初始 hash；不移动文件、
不改模块实现、不授予 Case/Run 创建或 Provider/外部效果权限。

## 第 3/6：九路 successor 登记与切换

新增 `scripts/a0v_t_successor_business.py`、`scripts/a0v_t_successor_cutover.py` 和 verify：successor registration
必须绑定 S 正式 detach Receipt 与 group62；cutover 使用独立审批、operation id、policy id 和幂等命名，
逐阶段 prepare → pause → commit → validate → resume，把九路从 legacy/fenced 原子切到 T epoch3。
切换前不启用任何 source schedule、经营参谋 Policy 或 snapshot definition。

## 第 4/6：Host 冷启动接管验收

T live target 建立后先观察至少两次 `runtime_lease_renewed`。随后以 crash-rehydrate 验收换代唯一 Host：
强制终止旧进程但不停止容器、不改库，启动同一固定 Host；新进程必须追加
`runtime_lease_rehydrated`，并继续至少两次 `runtime_lease_renewed`。状态文件必须持续显示唯一 T
liveTarget。任一 rehydrate/renew 缺失即停止 source 恢复；不得以 Host 进程存活替代租约证据。

## 第 5/6：十二源新代权威

T 稳定后，为 P01-P12 以 T installation/generation/epoch 新建 selection/control/binding；旧 S control 只读
保留。definition 使用新 id，先 disabled configure，核对 SnapshotRelationshipPolicy 和 12 个 exact binding，
再短时 enable。独立 worker 自然生成完整 group；成功后立即 disable definition。禁止复制 S claim、直接调用
`run_definition` 或手工写 snapshot 表。

## 第 6/6：经营参谋自然续跑

只有恰好一个当前 T 完整十二源 group、12/12 succeeded、输入/member/claim lineage 完整、24 小时新鲜、
canary0 时，才续签 exact Case/Policy v3 审批并通过九路 runtime 自然写入。唯一 Host 必须自然产生新
occurrence → Case/Run；后续 exact 评审和内容任务另按原长程闭环继续。本波不把测试绿或页面可点计为业务完成。

## 代码与验证范围

- 新增上述四个固定执行器及对应测试；历史 Q/S 执行器不修改。
- 优先复用既有 Owner/Service，不新增迁移；若 exact preflight 证明现有 released settlement 无法处理 S，
  再单独补方案，不在执行器内绕过。
- 每步核对正租户、负租户、操作终态、Receipt、路由、资源、租约和零未授权副作用；`git diff --check`、
  定向测试、方案一致性检查通过后分步提交，不 push。

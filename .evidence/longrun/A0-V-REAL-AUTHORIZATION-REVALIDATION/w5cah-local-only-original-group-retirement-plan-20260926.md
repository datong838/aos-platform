# W5cah｜原 12 Run 本机范围正式退休方案（2026-09-26）

## 上位、业务选择与边界

复习 231 A0-V→A1、231-9 BG-00→BG-01/02、栖月汇双侧增长产品方案及 W5c4r/u、W5c7t、W5c9b、W5ca4/5。用户已选择原 12 Run **不接受本次业务结果、正式退休**，并确认本次执行部署全集仅当前 Mac/Colima；已有商品等历史数据保留，用其当前可信 Receipt/水位支持后续最小首链，不把本组失败写成成功，也不再以追齐商城全部表为开发主线。`PermissionError` 原抛出点未知，没有证据归因为商城 SSH/读库；Host `HealthObservationStale` 是另一路 AOS 内部栈。

本波只结算原 group `081cd331-cdf8-5bdc-891e-e3b82baa77c7` 的 12 Run，租户仅 `org-org/dev-project`。不读商城源行、不重发旧 attempt、不手工 `run_definition`、不删除已有数据/Store Receipt、不启用新真实 profile；230 L0 挂起，`dev-org/dev-project` 只作零 canary。m1 单写、不 push、不动别的分支。

## 串行步骤与文件级清单

1. **当前现场只读冻结。** 核对 m1 HEAD/工作树、真实 PG head、原 definition rev4 disabled、唯一 claim/attempt、12 running、closure Receipt 0、关联 effect 与 Dataset Receipt 0、租户 canary 0。核对 Mac `launchctl`/LaunchAgents、全部相关进程与 listener、Colima contexts/容器、PG 活跃会话；记录用户对部署全集的确认及证据局限。任何旧 Host/worker、自动重启入口、其他节点或状态漂移即 STOP。
2. **本机维护围栏。** 在明确目标后以可恢复方式停用可能重新启动旧 Runtime Host/调度 worker 的本机入口，读回停用、进程 0、PG 活跃执行会话 0；只保留纯 HTTP 诊断入口。不能从单次 `ps` 推断持续排他。若启动面无法枚举或围栏无法维持，STOP，不调用 closure。不得把本机核验谎称跨机控制面。
3. **最小执行器。** 仅在本方案提交后，参照 `scripts/a0v_w4_stalled_close.py` 写 `scripts/a0v_w5cah_stalled_close.py`：固定 group/actor/唯一 key，`prepare` 只读冻结精确 head/12 Run/effect 与 eligibility；`apply` 仅调用官方 `StalledSnapshotGroupClosureService.close` 一次；`audit` 用独立只读查询核对 12 failed、正式 Receipt、`businessAccepted=false`、canary 0。私有 proof 0600、O_EXCL；禁止在日志打印凭据、源行。当前真实 PG head `a0v_092`，不可照搬 W4 的 `a0v_091` 版本断言。
4. **专项与累计回归。** 先以隔离 PG/fixture 验证 wrong group、过早/启用定义、Run 或 effect 漂移、重复 key、未知提交边界拒绝，再运行 closure 邻接测试；只有现场再次全绿才允许真实 `prepare`。真实 `apply` 调用边界一旦未知，绝不重试，只做只读 DB 对账并冻结。
5. **正式执行与独立审计。** 真实 `prepare` 与围栏再读回；单次 `apply`；独立 DB 读回 Run、Receipt、definition、旧 attempt、Store 数据不被改动，`dev-org` 零。把旧 definition 后续正式退休/direct successor 作为独立下一波，不在本波暗中重启。浏览器仅做只读状态验收，不点击同步/执行。
6. **收口进入业务首链。** verification 先落盘再提交，精确更新 AOS 上下文、D-waves 清单和 Prime 记忆并读回。下一波先核对已有可信商品数据的 Receipt/水位及首链依赖，选择一个商品×一个人群×一个场景，按 231 A1/BG-01/02 实现最小自然触发闭环；缺少外部动作授权时开发/隔离验证可继续，真实副作用仍守门。

## 退出与停止

成功只代表这 12 个失败 Run 由正式 Owner 以“不接受业务结果”终结，**不代表 A0-V/A1 业务通过**。任意未知 Fleet 范围、旧入口未撤、第二执行者、定义/Run/Receipt 漂移、事务结果未知、测试/审计不一致即停止真实动作并保留现状；只读对账后另立方案。不凭表有数据补写本组成功，不自动重试失败的商城连接或旧 attempt。

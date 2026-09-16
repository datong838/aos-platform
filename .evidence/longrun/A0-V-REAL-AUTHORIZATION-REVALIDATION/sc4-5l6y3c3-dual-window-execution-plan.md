# Y3c-3 原输入双窗口恢复执行方案

## C3a验证结果（2026-09-16）

已新增固定回执当前准入Owner，未接SourceClaim或执行写入。Red缺模块；首项正例10.72秒，最终8项准入/原saved-only围栏通过62.68秒，日志`/tmp/aos-recovery-authority-red.log`、`/tmp/aos-recovery-authority-final.log`。覆盖十二新控制与原输入分离、错executor/租户/成员/run拒绝、操作中disable后验拒绝且savepoint回滚、已disable和被后继Receipt替代拒绝、真实隔离membership撤销拒绝、异步consumer关闭拒绝及回调中窗口到期拒绝。夹具源仍一次，无新增SourceClaim/Run。diff检查通过；主库061未变。

前置C2d已提交f1c1c72f，当前主库仍061。本方案不将审批成功当执行成功。原保存数据、原观察时间、SourceClaim/Run/assessment/Store幂等身份不变；新增执行窗口与精确恢复回执只约束当前动作。

## C3a 固定回执当前准入（先独立实施）

新增aos_api/pipeline_snapshot_group_recovery_authority.py、tests/extension_runtime/test_snapshot_group_recovery_authority_pg.py。构造时绑定一个规范SnapshotGroupRecoveryRevision，不接受allowRecovery布尔；每次run_current由tenant、actor、十二(newControlRef,originalRunId)和同步可信consumer进入。精确原Definition/Claim Owners与共享controls构造。

先runtime tenant检查，读该组最新Receipt并比较固定ref，再由C2b以回执内manager重新核验当前管理许可/原input，当前executor身份必须与回执一致且仍有权限。安装锁后锁definition head，要求其exact ref=回执currentDefinitionRef、enabled且持久intent=renew_saved_group。最新十二binding与definition一致，所有schedule仍enabled且current member属于同definition版本，caller pairs完整对应原schedule claim的Run。旧观察时间只用原窗口验证。

原PolicyOwner在新十二控制上执行当前资产/配置/权限/预算/window/映射检查；重读新控制并用C1a比较原语义，核验原父输入objectType与当前精确mapping。consumer前后重读Receipt/head/成员/原输入/manager，原GroupPolicyOwner前后保留其窗口与控制检查，异步结果拒绝。返回的是受同步回调包围的上下文，不是可脱离事务复用的执行permit。此阶段不修改SourceClaim/Run/Store、不接执行API。

测试具名隔离原input+正式C2c审批：完整当前回执可核验，源调用仍一次；错executor/负租户/缺成员/换Run/换control拒绝；定义disable、Receipt被新续期替代、回调中禁用或抛错/异步结果均拒绝；普通源reserve和原守卫不变。事务外重复使用需重新全验，无ContextVar权限缓存。

## C3b及以后接线（待C3a后列精确代码变更清单）

1. 原PipelineSourceClaimOwner增加固定RecoveryAuthority组成模式，reserve明确拒绝；原ControlOwner仍验证新control，保存恢复读返回原claim。不能给普通_guard_schedule加allow布尔；恢复分支只调用上述专用exact Owner。
2. 原GroupClaim/Input链拆开历史观察组与当前执行组，原claim body/hash不得按新draft重算。原input manifest/sample window属于旧组；执行与policy使用新组。ControlledIngressJournal用新授权control，信封/命令/Run/Store keys保持原值。completed-read与saved-recovery是原有独立模式，不能简单同时置true。
3. 原projection payload已有controlRef，必须继续写原事实controlRef以保持既有projectionHash和其下游幂等；当前授权ref单独存在上下文。原assessment只有原input/policy/hash/时间，仍保持原值。
4. RecoveryRuntime跳过ScheduleClaim及Ingress.prepare，固定原group与十二Run，调用原Completion同key锁路径。C4仅允许原全running、全succeeded只读、或全failed且明确stopped/finished的原十二Run；失败恢复沿原claim_failed_run，同一外事务/确定claim key，不独立十二次提交。混合/未知拒绝。
5. 必须验证原部分Store效果、重启/确认丢失、续期撤销/禁用/过期和完成重放零新增源调用/Receipt/Link，之后才接产品执行接口；Y4再接周期与停止确认，Y5真实十二来源、Y6克隆升级/主服务、Z原业务Run恢复。

# Y3c-2d 恢复审批产品服务与受保护接口

## 实施验证（2026-09-16）

已实现三接口及原服务方法，未加执行接口。Red：service缺少read_recovery_context（1 failed，11.15s）；Green首轮46 passed，20.39s；增加真实HTTP→原Owner→数据库提交/回执查回、只读模式当前权限与负租户、无input无重读，并回归既有配置PG与HTTP后，63 passed，86.82s。日志`/tmp/aos-recovery-service-red.log`、`/tmp/aos-recovery-service-final.log`；git diff --check通过。

提交确认丢失夹具在真实COMMIT后抛错，原key GET读回唯一Receipt，控制修订仍24而非36、原Run十二、夹具源调用一次。只读回执以controls=None构造服务仍检查当前管理许可，负租户不可见；未知源调用无input例保持零读取。真实app路由、严格请求字段、principal身份、缺key不建服务、敏感异常不回显、503不自动重试均覆盖。

当前仅审批准备阶段完成，executionStarted=false；上下文executionAuthorized=false，未冒充恢复执行成功。下一波C3/C4恢复原保存输入，C5整链，然后Y4–Y6/Z及真实经营观察。主库061、主服务未加载变更，不push、230L0挂起。

前置：C2c原子Owner完整通过并提交。继续沿原factory.build_snapshot_schedule构造服务；不开运行入口。新增审批结果明确executionStarted=false，不把回执描述为恢复成功。

文件计划：修改aos_api/pipeline_snapshot_schedule_service.py、aos_api/routers/pipeline_controls.py；新增aos_api/routers/pipeline_snapshot_recoveries.py、tests/test_pipeline_snapshot_recovery_http.py、tests/extension_runtime/test_snapshot_group_recovery_service_pg.py。工厂复用已存在source_controls模式，无新凭据/源调用。

接口前缀/v1/pipelines/snapshot-recoveries：GET /{groupId}读取恢复上下文；POST /{groupId}/renew以严格JSON接收expectedDefinitionRef、expectedRecoveryRef、inputManifestHash、notBefore/expiresAt，要求原Idempotency-Key；GET /{groupId}/receipts/{key}读取原审批回执，用于提交结果未知的确认。actor与tenant仅取principal，不允许请求注入actor、executor、source、任意draft或自动生成替代key。

上下文读取先当前管理权限，再由C2b核验已保存原输入，返回原/当前definitionRef、原manifestHash、最新RecoveryRef、原观察时间、当前窗口规则/Run状态摘要；不得返回原始业务行，不宣称当前执行已获准。无完整input返回明确冲突，不提供重读源兜底。回执只读模式无需构造可读取源的控制Owner，但仍按回执definition当前管理许可验证，负租户不可见。连接复用原consumer_connection保证成功返回发生在提交确认之后，保护表检查覆盖恢复台账。

错误处理沿既有HTTP安全模式：拒绝回显异常详情，业务冲突409、CAS412（若Owner使用其专用异常）、无权403/原权限错误码、找不到404、参数422；未知提交503明确保留原key查回执，无自动重试。原配置、禁用、删除接口行为不变。

验证包括严格契约/越权字段/缺key不构造服务、principal绑定、真实app路由、异常不泄漏；隔离PG服务真实提交跨连接回读、丢失提交确认后原key读回零额外审批、未知输入零源调用、负租户。此波之后C3双窗口原输入执行、C4原Run恢复与C5整链，UI真实运行状态及worker接线在Y4。

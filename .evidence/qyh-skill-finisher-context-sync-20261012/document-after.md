# 栖月汇 Skill 签名生产链增量施工清单

依据231 A1及BG00u/BG00ac；唯一m1写者thread01a107a2-e9e4-7670-bc44-1144fa9b27e2，不覆盖历史清单。

1. [x] 完整执行/派发/签名终结合同冻结：qyh-signed-skill-lifecycle-contract-20261012，d77c3a093。普通Report/Run分事务与旧writer成功前置不能直接拼接。
2. [x] 原Run CAS/event连接内提取：5c91a7a67；新9+原23=32PASS0skip；晚期rollback、并发、autocommit拒绝，旧标准事务保留。
3. [x] qyh-skill-durable-dispatch-20261012：intent store、候选a0v160、21native+32相邻=53PASS0skip；双scope/唯一派发/versionCAS/unknown留存/运行结束拒绝/RLS/最小role/不可变trigger。只隔离新库；原实验新表不存在，实验集群NOLOGIN role保留但依赖0/membership0。真实恢复库未迁移。
4. [ ] 新专用producer正式准入、全新Run/intent：真实EvalContract/Suite/脱敏Dataset、独立Target/Judge issuer、Owner/审批/预算/网络。资料缺失默认关闭，不用普通回调/测试key授权。
5. [ ] intent→Run锁顺序，SERIALIZABLE同事务完整双签名验证+原CAS/event+Receipt/Report/sidecar/intent终结，晚期全rollback；旧succeeded登记路径保留，不降低preflight。
6. [ ] 未知执行/登记只读对账，完整proof才COMPLETE；unknown不重发、不重执行、不提前释放预算，不自动publish/start。
7. [ ] 当前库独立迁移备份/全恢复/零执行窗口；OIDC/独立发布配置接入、当前安装配置/禁入恢复、八台真实交互、自然首条闭环/连续观察独立验收。

登录配置路径已请求；此清单不授Owner/issuer/Provider/Host/worker权限，不回放旧12Runs、不补签旧报告、不读商城源、不push。电商域栖月汇org-org/dev-project正向，dev-org零作用canary。完整Goal保持active。

## 原双签名登记同caller事务增量（2026-10-12）
- [x] qyh-signed-proof-caller-transaction-20261012：完整原preflight/Receipt/Report/sidecar提取到内部connection helper，无commit/retry；公开wrapper仍独立身份默认off。9native+51相邻=60PASS0skip；同隔离新Run/intent事务晚期失败全回滚，提交后原消费者全证通过；独立NOINHERIT test login原wrapper真实验证。
- [ ] 完整新producer与受限复合终结权限/完成receipt仍待；原writer无Run更新权，不用fixture admin切角色替代正式权限，不改变上方4～7未完成项。所有证明都是新隔离fixture，实际Target/Judge调用0，当前库/八台未完成。

## 全intent只读中断对账增量（2026-10-12）
- [x] qyh-signed-intent-reconciliation-20261012：旧完整Report proof不变；新入口还要求intent/Run/请求hash/版本、全case双dispatch及result_observed/hash/因果时间精确，未知不重发；12新native+60相邻=72PASS0skip，纯SELECT无外部执行。原Report COMPLETE但缺Judge/unknown/input漂移/倒置时间仍整体UNKNOWN。
- [ ] 正式producer/受限终结身份及自然首链仍待，COMPLETE只是本只读登记范围，不授发布或执行。Native clock统一为DB时钟，host偏差诊断保留，生产时间规则不放宽。

## Judge派发前因果应用门（2026-10-12）
- [x] qyh-judge-causal-dispatch-gate-20261012：claim在写前拒绝缺Target/未观察/unknown/不同case或input的Judge请求；6新native+72相邻=78PASS0skip，正向与replay保留，拒绝无行/版本变化。
- [x] 新owned fixture保留旧格式错序/错误输入消费者反例，整体reconcile UNKNOWN；不写旧业务记录。
- [ ] 应用门不等于DB不可绕过或正式签名授权；result_observed不代表Verified proof，后续完整producer须原签名/Owner/预算/审批/网络与受限终结权限，当前八台仍未恢复。

## 独立producer身份及受限原子终结（2026-10-12，隔离验收）
- [x] qyh-skill-producer-identity-20261012：新独立LOGIN与精确writer/finisher双角色图，12nativePASS0skip；原writer单角色检查保留并原生验证。代码1398f88c4，不授实际Run写或正式身份。
- [x] qyh-skill-atomic-finisher-20261012：内部caller SERIALIZABLE/SAVEPOINT完整终结，intent先锁、有限finisher复用原RunCAS/event，writer复用全双签名Receipt/Report/sidecar及intent CAS，角色恢复。85native专项/相邻PASS0skip；独立全intent消费者COMPLETE、晚期失败被caller捕获再commit仍全回滚、并发唯一提交；代码04ccc2e5c。
- [ ] 本角色/权限和生产者配置尚未正式部署；新Run初始正式Owner/预算/审批/网络/独立issuer及真实Target/Judge执行仍待。上述是新隔离完整签名夹具，不将其当真实经营链；原顶层4～7保持未完成。
- [ ] 新增API代码后旧冻结源码候选已过期，必须再冻结当前代码并真实消费；真实源159→161/aos重启仍需原卷独占维护门，不由接续提醒自动重启。

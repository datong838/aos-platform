# b80 正式八依赖evaluator整体实施方案

## 当前可复用实现与更正

基线821109b3、authority1329、schema唯一head135。b79关于“新建事务authority接口”的建议过宽：readiness_service195–209已有for_transaction(conn)，authority/model store/model resolver共享nullcontext(conn)，不提交/关闭外部事务。此次b45两个真实PG测试复验该接口对未提交Capability/License/撤销可见，外部连接不可见。它只共享可见性，不验证调用者身份，也没有赋予正式绑定写权；保留原接口，不再复制连接factory或聚合算法。

实际generic capability evaluate先get/readiness再进入写连接，private capability_lifecycle family明确拒eval。正式入口需独立身份/outer transaction，将现有for_transaction置入outer transaction与共同锁之后。b77全表事件trigger/pre-replay锁是算法证明，不是source发行。

补充缺口来自此次源码：resolve()只读Model/Provider/Policy/Route/Price/Health/Eval相关状态；capacity池统计有现成list_capacity_pools，但不是正式readiness内已核八维容量。snapshot_hash328–346只hash声明Capability/dependencies，不包含实际最新Health observation/Capacity使用/可信License issuance/head等证据。不能把这个旧hash重新命名为全事实证明，也不能改旧hash算法破坏现有preview/activate合同。

## 统一命令顺序

1. 正式连接验证session/current_user、独立role、exact命名DB、scope/GUC、serializable、超时、无superuser/BYPASSRLS/runtime/owner继承。默认缺正式配置拒绝；不借BI/Registry lifecycle身份。
2. 当前signed安装/registry及当前请求Binding exact/version检查，取得installation→registry/Binding来源锁。制品签名证据是EVIDENCE_ONLY_NO_START，只作为来源一致性输入，不能自升权。
3. 逐项映射八维原始authority：Provider/Model/Policy/Route/Eval/Health/Capacity/Price；另核Capability、License、Data、Tool、Budget。按稳定exact来源键排序取共同head锁，所有相应state writer必须同锁或事件驱动epoch；只锁不可变修订不能处理append-only最新状态。
4. caller-owned conn上AipBindingReadinessService.for_transaction(conn)重算原聚合；补正式Capacity/License issuance/current Health head及原source语义，不在服务外先preview当真源。时间单点checked_at，并将所有expiresAt/effectiveUntil限制入实际proof期限。
5. canonical formal source proof（版本化文档）：exact source refs/hash/current head epochs、发行Receipt、实际health observation、capacity pool revision/使用读、安装etag/registry/current Binding version、policy/eval/price有效期；排序hash。不覆盖legacy dependency_snapshot_hash。正式proof放独立append-only表/Receipt，并绑定tenant/Binding version及legacy hash；正式activate/start消费此proof重新锁与重算。普通preview/legacy hash保持既有语义。
6. 同事务CAS Binding、append-only正规Registry Receipt/正式proof；missing/unknown/stale返回确定原因且不标available。invalid scope/hash/identity/旧快照/版本冲突无更新或Receipt。所有写者一致锁序，whole transaction rollback。
7. 同key同request replay须原Receipt-first合同、同内容不额外更新proof/head；不同payload409。不得重算新事实后伪造旧key新结果，历史proof不可改。

Capacity准入只读证明是否满足规则，不在evaluate阶段调用Provider或扣预算；真实reservation/费用/AgentRun继续原独立执行门。evaluate available不是自然首链，也不是运行许可。

## 具体文件（新建或最小接线，先RED）

- 新 aos_api/aip_binding_evaluator_connection.py：借鉴既有身份审计形态但独立正式evaluator身份，不复制密钥/复用BI或lifecycle login；私有身份缺失默认阻断。
- 新 aos_api/aip_binding_evaluator_service.py：outer transaction+install/registry/source锁+复用for_transaction+CAS/Receipt/proof；不复制readiness源算法。
- 新 aos_api/aip_license_source_authority.py：trusted issuance/head exact初始化/受限锁；普通Evidence source不能自动mint可信head。缺真实issuance政策事实fail-closed。
- 新 aos_api/aip_binding_source_facts.py：同事务八维及License/Data/Tool/Budget的原authority映射和canonical proof；readiness/model runtime原API复用，不能另造第二authority。
- 新 alembic/versions/a0v_136_binding_source_authority.py（候选，实现前再核唯一头与命名）：issuer/proof/head schema、RLS/最小definer/事件约束；普通Evidence域兼容，旧行不backfill升权，迁移不在当前135库运行。
- 原 aip_production_contract_store.py：仅trusted License source域revoke的pre-replay锁，generic功能不变；eventtrigger按数据库可信issuance关联判别域，不能prefix/body声明。
- 原 routers/aip_bindings.py：显式正式evaluator dependency接线，既有preview和lifecycle身份边界不改；未配置不可用。response正式proof引用采用独立可选契约/新显式命令surface，不能破坏原response与hash。
- 原 aip_capability_binding_service.py：仅复用existing CAS/Receipt私有方法或提炼稳定共用操作，不放宽capability_lifecycle禁止eval，不混淆legacy普通模式。
- tests/aip/test_aip_binding_evaluator_connection.py、test_aip_binding_evaluator_service_pg.py、test_aip_license_source_authority_pg.py及原signed full-schema PG：实际角色/库/tenant/全source状态/共同锁/Receipt/新旧域。

路径均相对services/aos-api；生产实现先细化单个文件scope，不越过本设计阶段Task。

## RED与验收顺序

b81先正式HTTP准入/独立evaluator身份与当前schema缺口真实RED；身份模拟仅测试声明不算运行正式授权。然后disposable schema/RLS/issuer/proof/head，合法同事务初始化和拒绝ordinary source。再事务evaluator blocked路径与全八源exact positive，不能只跑empty/blocked即称available通过。全mutation race（每source双顺序）、freshness与snapshot proof drift/rollback/replay/canary；相邻普通Evidence/preview/hash/activate/lifecycle/schema升级唯一头/降级安全。

正式身份、发行政策、Owner original facts未满足时不生成available proof；可继续代码完善与独立W-L20，无整个Goal停工。生产runtime不会仅因调用者principal或nonempty license_summary获得权限。真实135迁移需备份完整恢复/零执行窗口独立门；真实Host/worker/Provider/商城源/发布仍独立授权。

## 风险与回滚

最大风险是漏source mutation head、将readiness旧hash冒充事实proof、误扩大issuer角色、泛化generic Evidence触发器及自动升权旧行。验收逐表writer inventory/ACL/真实PG并发，不以测试角色替代source可信性；已知缺口保留blocked reason，缺权限也继续其他安全项。仅新schema/显式新入口，默认未配置阻断；真库未迁移前可撤新接线，历史Receipt/proof不删不改。rollback migration不得默默宽授权。

本方案不是完成或部署批准；整体Goal active。下一b81对正式接口/issuer gate真实RED并开始最小生产文件实现，不再新增平行计划总数，不以503占位收尾。

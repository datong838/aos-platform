# b90 完整正式八依赖 evaluator 施工方案

2026-10-05 08:40；基线代码33c827b3，Authority AOS-001329。方案Task w5cb4-e17-s3owaob90-complete-evaluator-plan-20261005已登记。此为施工设计，尚无实现、RED或Delivery，不代表八实际配置或自然首链完成。

## 目标与当前源码证据

遵守231主计划、231-1四层合同、栖月汇11技术及12权威矩阵、用户AGENTS。m1唯一写者，不push/同步其他分支；真库135只读。整体交付必须包含正式身份、八事实当前性、来源许可、安装、预算、原绑定CAS/Receipt、proof及提交时有效期，不能以单独reader/DTO作为退出条件。

现有aip_capability_binding_service.evaluate先self.get及readiness.evaluate，再另开写事务；不能证明一个调用方事务内的权威快照。aip_binding_readiness_service的license_evidence_available仍读取license_summary，未消费b89发行。a136已有aip_binding_evaluation_proof八键JSON/原Receipt外键，但当前未找到运行写者。aip_model_runtime_resolver.resolve确实检查Route/Policy/Model/Provider/Price/Eval/Health，却没有Capacity检查；不能把READY解释为八依赖全过。

## 复用权威与必须冻结的事实

| 事实 | 原权威入口 | 必须核验/记录 |
|---|---|---|
| Provider | aip_model_runtime_store.get_provider | tenant、当前head、exact revision/hash、active；不读Secret明文 |
| Model | 同Store.get_model | 当前head、exact revision/hash、active、模态/能力、Provider/Price及Eval引用 |
| Policy | 同Store.get_policy及require_model_governance | 当前RuntimePolicy、kill switch、模型治理和guard当前头、预算引用 |
| Route | 同Store.get_route、原Resolver | 当前head、exact revision/hash、active、候选顺序/选中Model、绑定Policy/Eval |
| Eval | 原AipEvalAuthorityStore.require_exact_passed | Route/Model原evaluation_candidate_ref目标、当前通过决策/有效窗、冻结EvalContract |
| Health | aip_provider_health_observation | 同一exact Provider最新观测ID/observed_at/expiry/status；拒未来/到期/错revision/hash |
| Capacity | aip_model_capacity_authority及reservation原算法 | 当前pool head/version、active exact Route/Model/Provider、限额、有效reservation占用和剩余一个原量子 |
| Price | 同Store.get_price_snapshot及治理核验 | 当前head/精确引用、active、币种/单位/数值或原正式零价/延期授权、effective有效窗 |

Source额外复用read_license_source_fact：原初始化/head共享协调锁、issuance/epoch/installation etag/Receipt；再核验b89授权schema、原批准及完整用途范围、两当前Owner和当前签名Policy，不把历史table-owner夹具升级为正式许可。安装主表/当前revision必须active一致、精确etag；required Data/Tool与Capability仍按原权威精确核验。预算读原当前head/revision及窗口，不通过评估扣费或产生执行reservation。

Capacity在原head上使用与reserve相同FOR UPDATE协调，读取原有效占用；仅证明checked_at剩余额度，不许称为已预留。执行仍必须走原reserve，评估proof不给启动/额度持有权。

## 完整命令与锁/提交合同

新增正式JWT命令只收严格租户、幂等key、原binding id/version、installation id/etag、八exact引用及exact Source refs，禁止actor/roles/ready/facts/clock客户端供给。认证复用原签名验证；固定evaluator自身SCRAM/SERIAL权限，不借Registry或Source issuer身份。连接改动必须确认require_auth/used_password、双向无成员、实际schema与private文件原校验，不自行开LOGIN。

单native psycopg调用方事务：认证后身份回读→原幂等锁/Receipt→原binding锁与CAS→按稳定ID排序Owner/安装→按Source exact refs排序原初始化/head共享锁→按固定类型/id排序ModelRuntime各head/revision和Eval→Capacity原head排他协调→原Registry exact签名证据/Data/Tool→实际DB clock采集全部事实。最终锁序须与原issuer/Owner撤销/ModelRuntime/Capacity writer逐项对照；存在反向序则开码前修方案，不复制新协调域。

原Reader/Resolver/Store通过原TransactionBoundConnectFactory复用同native事务；不得提供任意callback或独立连接。facts hash必须覆盖八实际事实、Source epoch/issuance/Receipt、安装、预算及原引用，不以legacy_dependency_hash替代。有效窗取DB checked_at后的原ttl与所有实际有限expiry的最小值，缺必需expiry或过期即拒。

原capability_binding.evaluate Receipt、原binding readiness/version CAS、a136原proof同一事务写；响应先构造，真正COMMIT时原三记录关联与live期限检查，异常全回滚。samekey重新核验当前事实并对账原结果，不同hash冲突、不得凭旧AVAILABLE回放过期许可。SSI40001保持原错误，不自动重试。既有preview保持历史只读语义，不能赋予正式proof；既有正常API行为不得被顺带重构。

## 文件级完整实施包（编码前独立Task登记）

- 新增 services/aos-api/aos_api/aip_binding_formal_evaluator_contracts.py：严格正式命令/八事实输出合同。
- 新增 services/aos-api/aos_api/aip_binding_formal_evaluator.py：完整事务命令、原Store复用、当前事实/锁/原Receipt-CAS-proof。
- 修改 services/aos-api/aos_api/aip_binding_evaluator_connection.py：专用身份最小强化。
- 新增 services/aos-api/alembic/versions/a0v_143_binding_evaluator_boundary.py：默认NOLOGIN、最小scoped ACL/RLS、读锁DML保护、仅原binding/proof/Receipt权限及原三记录提交约束；不能授通用批准、Source发行/撤销或执行权。
- 新增 services/aos-api/tests/aip/test_binding_formal_evaluator_pg.py：实际隔离PG RED/GREEN与竞争/回滚。
- 修改 services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py：显式独立b90 opt-in实际signed安装/原来源发行/完整八事实消费者；默认b88/b89行为保持。必要fixture扩展先列精确文件、登记追加Task。

## 开码前仍需闭合的技术审查

08:44身份切面审查已闭合：先在原隔离PG fixture内以事务回滚的测试专用角色证明反向成员及搜索路径漂移未拒；不连接生产、不赋予正式业务权利。连接只最小强化双向成员/search_path/require_auth SCRAM及实际used_password/private passfile单link；新增测试文件的identity部分是完整evaluator施工中间状态，不作为整波退出。此切面登记独立Task后可RED/修复，完整facts/ACL/命令开码仍须下面审查完成。

源码补证：AipModelRuntimeStore._publish内部conn.commit，正式命令仅复用_get/各get与require_model_governance读取，不调用publish。CapacityReservationGate.reserve先FOR UPDATE pool head再reservation；evaluator同head锁只读取占用，不调用reserve、expire、consume。Eval require_exact_passed读取原decision并核验decided_at/expiry、exacttarget/hash，通过同事务factory复用；不能把裸decision JSON当通过。

固定搜索路径补强为pg_catalog,public,pg_temp（与原Source专用调用一致）；显式把临时schema放末位，避免共享读取器的未限定表名被临时表抢先解析。正式evaluator仍应对新增SQL显式限定public。原模型治理BudgetPolicy读取在部分分支只读head，完整evaluator须显式锁所有选中的治理budget/quota头，再复用原有效期/正式费用授权校验，不能依赖preview布尔值。原Source issuer顺序已查：Proposal→Approval→两Owner→安装→初始化独占→Registry协调/证据→guard原draft；evaluator须先锁所有相关原Proposal/Approval/Owner再安装/Source/Registry，不在持有Source锁后倒序请求这些行锁。

08:54完整审查新发现：Health原record_health只追加observation/原receipt，没有当前头或协调锁；锁住已有observation不能阻挡新健康降级观测，SERIALABLE也不能无条件保证提交时仍latest。须先独立实际PG反例，a143再定义所有raw INSERT/原Store共用的中性协调（无健康真源复制、无旧观测backfill），证明post-snapshot竞争原40001或阻塞，并把Health实际观测及epoch绑定proof。单纯在末尾重读同SERIAL快照不修此问题。SourceRequest原reader仍仅允许runtime/两Source角色，完整消费者若复用需追加精确固定evaluator身份的最小Source reader合同及相邻测试；不得伪造原maker Principal，原授权/immutable核验应抽取纯复用函数后使用存储maker而实际evaluator仍按自身认证和Owner核验。上述文件增补须Task先登记，完整代码仍未开工。

逐项读ModelRuntime各head更新与Eval/Budget/治理原Store SQL、binding现有trigger/metadata操作约束、原Source与Registry全锁序；确认原proof是否需额外Source关联字段（优先facts内schema，不新建第二权威）。准确列a143每表权限/锁列/tenant规则与原写者冲突关系后登记代码Task。以上未闭合前不宣称方案已可开码。

## RED、验证与退出

先实际PG证明现有事务分裂/缺Source及Capacity不产生正式proof；新增入口缺模块仅收集RED，不能称业务拒绝实证。专项必须覆盖：八项逐一缺失/旧head/错hash、Source撤销/到期/Owner失权/错用途、canary零写、installation漂移、Capacity不足/竞争、同key原回放及参数冲突、多事务writer阻塞图/SSI、响应失败与真实COMMIT失败/到期三写全回滚。完整正向必须由原正式Store在一次性隔离库建立可追溯事实，不直接INSERT假READY冒充通过。

PG测试串行避免集群共享role DDL竞争；保留旧49测试库。角色清理只在安全属性/双向成员/共享依赖均0后精确drop，无DROP OWNED。专项后做相邻累计、编译、精确diff与方案代码复审；无UI更改浏览器不适用。证据/Delivery、m1精确提交和AOS/Prime上下文收口之后立即下一安全波。正式权限、135迁移独立门、自然首链和发布仍pending；每日09重启验收职责独立，不以隔离测试代替。

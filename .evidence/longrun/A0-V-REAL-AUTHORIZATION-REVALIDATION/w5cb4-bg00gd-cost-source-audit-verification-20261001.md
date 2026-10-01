# BG00GD 首链费用来源与部署缺口审计

基线AOS-001044/a500e728，代码a0v127。只读代码/配置审计与既有门测试，不新增业务代码/迁移，不声称首链完成。

## 事实矩阵
|链段|核验证据|结论|
|费用提议→独立批准→BudgetRevision|aip_budget_cost_consumer.sql、aip_budget_consumer_actor.sql、BG00GB/GC|已有代码级正式消费和原请求恢复；当前实例尚无正向证据|
|ModelPriceSnapshotRevision读取|aip_model_runtime_contracts.py:173；aip_model_runtime_store.py:75/169|development允许未知价格，但要求有界授权和当前active price head；不是0价格|
|价格快照发布|aip_model_runtime_store.py:212/414/504；routers/aip_model_runtime.py:493|通用publish校验scope/hash/CAS、写Receipt；_validate_dependencies只有model/route分支，没有从已消费费用批准派生价格授权的专用producer；路由存在不证明合法来源|
|BudgetPolicyRevision发布|aip_model_governance_policy_store.py:179|publish_budget直接active明确BudgetPolicyApprovalRequired；不能删此门或用seed绕过|
|模型治理关联|同store:104/132/160|开发policy必须当前active head、引用active BudgetRevision、在窗口内；price与policy的developmentCostAuthorization必须相等，且精确Provider/model/approval|
|费用运行门|aip_budget_cost_runtime.py|现有Receipt/decision/provider/head/成员/撤销/fence检查，并限制每次风险/总风险/次数；不能把这些读门当成来源producer|
|现有价格测试来源|tests/aip/test_budget_cost_consumer_pg.py:108 price_for|isolated_owner直接INSERT price head/revision；只证明消费方风险门，不证明正式producer|
|历史价格生命周期测试|test_a0v_deferred_price_pg.py|旧AOS_EXTENSION_PG_TEST=1 opt-in；本波不启用、不复用旧共享库；其synthetic approval不是正式来源|
|数据库写边界|aip7_002与aip10_003迁移|已有表FORCE RLS/append-only；aos_runtime有price与governance revision INSERT。未来producer必须明确直接写active开发来源的DB防绕过边界；不能只加Python if|
|独立身份检查|aip_budget_consumer_connection.py|固定caller/owner、15表manifest、函数/额外ACL精确检查；增加派生写权限必同步可审计manifest与权限回归，不能临时GRANT后跳过预检|

## 当前部署配置检查（只核文件，不是运行进程）
根.env：AOS_BUNDLE_ROOT有值且路径存在；AOS_BUDGET_CONSUMER_API_CONFIG、AOS_BUDGET_COST_API_CONFIG未提供非空值；AOS_REST_CONNECTOR_MOCK未提供值。没有打印凭证/读取私有passfile。未核查进程继承环境，故不能据此断言正式身份一定不存在，更不能以假账号补齐。
当前真实库本波未连接/查询/写入/迁移/重启，未实测其migration版本；代码127不是运行版本证明。Host/worker/Provider保持原禁入，本波无商城源/旧12Run/手工Run/230L0动作。

## 回归证据
工作目录services/aos-api，标准conftest独立测试库，无legacy opt-in：
`.venv/bin/python -m pytest -q tests/aip/test_aip_model_governance_policy_store.py tests/aip/test_aip_development_cost_authorization.py tests/aip/test_aip_development_model_binding.py tests/aip/test_budget_cost_consumer_pg.py --tb=short --show-capture=no`
58passed/19.31s，7已有warnings，exit0；/tmp/aos-gd-source-regression.log，原session49264已取回终态。
其中policy store/cost consumer有真实隔离PG；development授权/绑定包含纯值与替身读门，只证明合同检查，不能冒充真实生产联合链。
本波审计没有新增逻辑，RED/编码/浏览器不适用。没有改旧业务文件或锁文件。

## BG00GE 施工路线（先文件计划/RED，再写）
目标：从当前已消费费用批准派生一对一致价格/预算政策来源，而不是让调用者提交任意active payload。
1. 新 `aos_api/aip_budget_cost_configuration.sql` 与下一迁移 `alembic/versions/a0v_128_budget_cost_configuration.py`：沿用预算consumer caller/owner边界，新增独立派生/历史查询函数，输入原proposal/hash/decision和已验证actor；不可传price/policy任意body或角色。首次执行在同budget-cost-review锁内核原maker/checker当前资格、未撤销/有效批准、消费Receipt完整hash/target、当前budget/provider及窗口。价格数值保持null，授权Provider/model/approval/window只来自原批准；policy引用该BudgetRevision，hardStop/unknown block/不允许zero，ID按原消费身份稳定派生。两组head/revision和独立派生Receipt同事务，任一失败不留半对配置。
2. 数据库门：直接active开发price/对应development policy及派生Receipt只能经该受限函数；既有非development、历史读、撤回路径需明确兼容并回归。不改通用publish_budget active拒绝。迁移只在独立测试库，真实库另波。
3. 扩展 `aip_budget_consumer_connection.py`/schema manifest时精确增加表/函数/最小ACL，保留额外权限拒绝；不能整个更新snapshot掩盖非预期变化。派生只读查询保留历史Receipt并验证原actor，不能以写函数回放当查询。
4. 新 `tests/aip/test_budget_cost_configuration_pg.py`：真实独立caller/PG批准消费后派生；重复/并发一对一Receipt、篡改hash、错误actor/tenant、撤销竞争、过期、预算或Provider head变更、失败原子性、直接runtime写拒绝、历史查询、既有预算消费回归。
5. 后续有限service/IPC/product沿用原请求协议并保留unknown只对账；接实际Model/Task的治理及风险联合证明，不能留在SQL单点测试就宣称首链。

## 结论
已用当前代码事实收敛下一施工点，首链仍被正式来源生产链和部署/身份/配置证据缺口阻断；这不阻断独立研发。自然首链/八工作台/连续观察/发布未完成。Goal未改，Watchdog仍方案。所有恢复都要原请求对账，不新增未知副作用。

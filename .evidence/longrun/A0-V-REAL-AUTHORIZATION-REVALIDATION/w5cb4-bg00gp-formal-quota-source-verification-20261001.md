# BG00GP 验证记录（代码门收口，非业务首链）

基线AOS-001056/m1 4d3d5658；开工7strong CURRENT、validate GREEN（1516 Delivery /1514 Task /4031 events）。GP主Task与后续READER Task已登记；没有CAS、Delivery或本波提交。

## 当前真实边界

只对全迁移临时数据库写入；真实当前数据库、容器、Provider/Host/worker、商城源、旧12 Run、230 L0未操作。本波不是当日全面重启证据。租户正向org-org/dev-project，canary不作正向生产来源。测试签名身份和临时独立SCRAM角色不冒充正式客户身份。

## RED与实现

- /tmp/aos-gp-quota-red.log：2 failed /1 passed /4.80s /exit1。直接active Quota INSERT未拒绝，正式Quota metadata缺失；原Store文本approval依然拒绝。
- a0v130 additive边界后 /tmp/aos-gp-quota-boundary.log：3 passed /4.39s /exit0。Quota行限定触发器，不改Budget同表历史逻辑。
- /tmp/aos-gp-quota-maker-red.log：1 failed /3 passed /5.19s /exit1；GuardMakerCommand未接Quota。
- 固定Quota DTO/Action/原Store来源/独立checker接线后，与原Guard两组累计 /tmp/aos-gp-quota-maker-green.log：43 passed /28.68s /exit0。
- /tmp/aos-gp-quota-consumer-red.log：1 failed /4 deselected /5.03s /exit1，缺Quota consumer模块。
- 增加固定a0v130低权函数和既有认证单次消费封装后 /tmp/aos-gp-quota-consumer-green.log：5 passed /6.32s /exit0。原Store draft1→signed maker→signed checker→active2/head/一Receipt→原Governance reader；重复只读。
- 旧Quota来源改正式链、真实revision2引用、到期边界断言保留；/tmp/aos-gp-quota-compat.log：14 passed /8.51s /exit0。
- /tmp/aos-gp-quota-faults.log：16 passed /15.79s /exit0。错target/binding/actor/JWT/tenant、checker撤销、sourcehead推进、withdrawal均在attempt前拒绝；commit前/后连接故障均只写一次；消费期间审批到期实际到达Receipt后完整回滚、保留原Approval。

后续新增并发单Receipt、caller无表读取、Quota限额model_copy重验，21文件累计/tmp/aos-gp-quota-regression.log正在执行。不能提前当作通过。

复审新发现Quota reader未核当前head，已补方案与暂停/换版后旧active应拒绝测试，待首次累计结束后单独RED；不以仅source生产正向掩盖当前性缺口。核源码时曾猜测_model_policy_history_fixture.py不存在，实际为_model_governance_history_fixture.py，后已读取；无写入错误路径。

## 剩余

Quota当前性反证/修复、完整累计与方案/代码复审、精确提交/上下文/D-waves尚未完成。HTTP/UI、真实身份与当前实例独立恢复部署、完整Review→AgentRun→首生审批→Capacity→GE held、自然经营首链、八场景与观察发布均未证明。Goal active；watchdog保障方案尚未部署。

## 累计与当前性补门

- 首轮21文件累计 /tmp/aos-gp-quota-regression.log：241 passed /7既有warnings /157.90s /exit0。覆盖GO原16组与Quota、治理Store/contracts/API、Budget runtime配置组，不证明完整业务来源。
- /tmp/aos-gp-quota-head-red.log：2 failed /24 deselected /6.03s /exit1。真实签名Quota active2后通过原Store发布suspended3/draft3，旧引用仍被require_exact_active接受，失败为DID NOT RAISE。
- 最小reader实现当前head/revision/hash/lifecycle比对，读写事务FOR SHARE OF h、READ ONLY仅观察；/tmp/aos-gp-quota-head-green.log：2 passed /24 deselected /5.76s /exit0，历史get仍可回读active2。
- 追加真实双连接：事务绑定reader持head锁直到外层结束；SERIALIZABLE旧快照面对已提交新版必须SerializationFailure；最终同21组 /tmp/aos-gp-quota-final-regression.log正在执行，未宣称通过。

方案复审：Quota为固定第三类，不开放任意表/函数参数；旧129迁移与SQL未修改。130只增加Quota metadata/行限定安全门与固定消费函数，复用原Guard角色和批准表；consumer caller无表权限，owner新增治理RLS只允许quota及对应publish/activate Receipt，不扩Budget行。原Store active文本approval继续拒绝；原Budget历史read夹具仍不计正式来源。原Guard/Network/Budget行为通过累计核验，完整当前实例与自然首链仍待证明。diff --check和compileall exit0（最终收口前再回读）。

## 最终代码门结果

/tmp/aos-gp-quota-final-regression.log：245 passed /7既有warnings /160.58s /exit0。命令为仓库根 `services/aos-api/.venv/bin/python -m pytest`，GO verification列出的16个tests/aip文件（均加services/aos-api/前缀）再加：test_quota_policy_activation_pg.py、test_aip_model_governance_policy_store.py、test_aip_model_governance_policy_contracts.py、test_aip_model_governance_policy_api.py、test_budget_configuration_runtime_pg.py，参数`-q`。不与此前241/16/14/43相加。

真实锁反证均通过：当前head共享锁阻断另一个连接UPDATE；旧SERIALIZABLE快照面对外部已提交suspended3抛SerializationFailure；历史get仍读active2。Quota新增24个来源/消费/边界/并发/无表权限/输入限额测试，另加4个当前性与锁测试，共28个本文件测试。不同身份私有passfile沿GO独立保存，签名请求每次校验，attempt只包含公开refs/hash不含token。

最终复审确认方案与实现一致：固定Quota DTO/Action/闭合表名与函数；原Action/Draft/Approval/Receipt；仅Quota行新增消费权限；原Budget行为未扩；生产Store active仍拒文本批准；当前reader不让历史Quota代替当前active，绑定执行事务锁由外层持有。完整端到端首链仍缺合法Provider/费用/模型/Review组合，不能把这些测试和观察函数当执行许可。下一波BG00GQ从旧Budget prepared的占位Provider直接INSERT改合法Guard→原Provider Store来源，继续模型/费用/Review联合，不读取商城或调用Provider。

本波无UI改动，browser不适用；当前实例未接触，migration130仅临时库。watchdog保障方案未部署。上述代码门可收口，真实安装/首链/八场景/发布未完成，Goal保持active。

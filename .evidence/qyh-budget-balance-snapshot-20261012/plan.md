# 栖月汇内容预算恢复：原三桶只读快照

Rules：231/231-1 原费用来源与 fail-closed，AOS工程交付，先方案、最小新增、保护用户预算 writer 改动。基线93486c679/AOS-001900，新Task仅两个精确服务/测试文件与本证据目录。前波确认 Content readiness 缺余额，但请求尚缺 canonical费用/预留身份；不通过本快照替代 Cost authority 或给未知费用放行。

新增 aos_api/aip_budget_balance_snapshot.py：read(scope,原ReserveBudgetRequest)接受请求仅作为桶地址观察输入，不作为费用上界已获批准的证明。原 connect_read_only 在tenant scope应用前开启原生REPEATABLE READ/READ ONLY；核 current_user aos_runtime/tenant/transaction，当前Budget head+原 AipBudgetAuthorityStore.get 在同一连接读取并核 exact ref/lifecycle/effective window/hardStop。原 derive_bucket_authorities 生成三个精确桶地址/周期/limit（任务、日、试点月桶），不能凭调用者自定义账户。只SELECT原 aip_budget_bucket，不调用会INSERT/锁桶的writer。缺桶、limit/currency/period漂移、未知占额、负值/超额分别标记；完整桶exposure包括held/submitted/settled/unknown。快照值及请求/时间绑定hash；executionAuthorized固定false，costUpperBoundAuthorized固定false。未初始化桶不当零；时间由reader取当前awareUTC，调用者不指定过去时钟。

新增 tests/aip/test_budget_balance_snapshot.py：先RED，验读取完整值/未知/缺桶/跨tenant/过期/当前head漂移、无DML与不调用writer。原生连接门还需在绑定隔离PG实际复验，不以mock当PG成功；实现后专项/相邻预算与内容readiness测试、语法/源码一致性和秘密扫描。保持当前Content readiness原拒绝，无router/API/数据库/权限/页面改动。

该组件只是正式余额接线所需读模型，完整Content登记仍需真实Task/AgentRun与费用上界关联、对象字节治理、独立Source和正式身份。不能以组件完成缩小Goal；不发布、不重放旧Run、不触碰原用户writer文件。后续仍需真实PG正反及上述原业务接线，当前新Task在全部输出成立前ACTIVE。

实际PG准备不能直接INSERT active：原public预算激活trigger以BUDGET_ACTIVATION_CONSUMPTION_REQUIRED正确拒绝。保留r2失败，不禁用/改动原trigger。读模型测试改用标准session独立aos_test_*_ti4_test库内唯一test_balance_* schema的LIKE原三表观察夹具（不含正式激活trigger），角色仍aos_runtime/同tenant、原生RR/READ ONLY；正向只证明字段/快照读取，不证明授权或正式active来源。另加原public直接INSERT依旧拒绝验证。正式当前库不连接，原预算owner/审批/消费不改变。

同一RR快照补充并发验证：原native scope读取已开始后另一连接提交账本变更，首次Reader必须仍读取旧三桶，同scope下一新连接观察新值。snapshotStartedAt使用原transaction_timestamp，checkedAt使用当前clock_timestamp用于当前有效期/周期判断，二者同时绑定结果hash；不把任一快照授予费用或执行权限。补实际expired来源拒绝与错误隔离级别拒绝。通过专项后按新改动跑相邻原预算/内容readiness，不扩大为完整Content或业务准入。

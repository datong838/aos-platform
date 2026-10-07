# GT-b4 普通预算 caller-owned 事务内核

基线 m1@9bc6ef7b / AOS-001470，同唯一施工writer；Task gt-budget-caller-transaction-20261007 已ACTIVE至21:00。承接已批准b4c原三桶与Source/共享物理occupation/一次Intent组合，不新增外部效果授权。

文件：services/aos-api/aos_api/aip_budget_reservation_store.py、tests/aip/test_budget_caller_transaction_pg.py、tests/aip/test_aip_budget_reservation_pg.py（仅owned schema保留开关）及本目录。

现状：reserve使用自己connect_factory的SERIAL事务，方法内部没有显式COMMIT，但factory退出时结束事务；不能把它顺序调用成原子Source/physical/budget/Intent。Eval hold已有caller入口但普通Task预算缺同等入口。计划新增reserve_in_transaction(conn,scope,request,actor)，原生psycopg Connection、非autocommit/非readonly、INTRANS、实际SERIAL/read-write/aos_runtime/精确tenant；request精确原ReserveBudgetRequest并严格重验，禁止伪造Eval Task/代理连接。不打开/关闭/提交/回滚caller。原reserve保持旧输入/actor/hash/factory与commit/replay语义，将完整原预算算法纯缩进移动到私有_reserve_in_transaction，原Task/price/approval/桶限额/costRisk/事件保持逐语句一致，不改持锁顺序或三桶算法。

先真实PG测试缺API RED，再最小实现，原预算专项与ModelEval相邻按变化范围复验。复用原ar2预算schema夹具和原seed真实SQL审核资料；仅在当前owned SCRAM PG lab的aos_meta中新建随机测试schema。AOS_TEST_RETAIN_DATABASE=1时保留自己schema，默认清理语义不改；不得删库/卷/备份。runner只传0600 passfile路径，不在命令或env打印密码。

验收：caller xid不变、observer提交前不可见、实际callerCOMMIT后一次reservation/一次prepared invocation/三桶held与一次event一致；callerROLLBACK及后置异常全零；replay同ID不重占、payload漂移仍Conflict；连接/角色/tenant/isolation/autocommit/readonly/IDLE/facade、raw修改request和actor负门零副作用。保留原unknown/settle/reconcile/concurrency/临时同名表相邻行为。独立SER READ ONLY核保留schema账本与canary0。

风险及边界：这只是组合所必需的普通预算内核，不是假Task Eval预算，不是共享物理occupation或singleIntent的完整实施；新入口不会授予Provider发送。预算单独kernel不得定义全局Source→physicalAccount→budget→route/Intent锁序，完整联合合同仍先冻结。正式库/迁移/安装/服务/Host/worker/Provider不动，完整Goal ACTIVE。

初次red-r1为root session autouse默认5433连接拒绝（3ERROR0.41s），未进入预算fixture/事务业务，不计RED。修正独立runner AOS_DATABASE_URL为owned5434无密码URL，libpq只从既有0600 PGPASSFILE取密码（路由127.0.0.1:5434:*:aos_app已核）；AOS_EXTENSION字段已同ownedlab绑定，不传密码到argv/env，不改全局配置。继续red-r2。

本次复审：原reserve全部with-body与私有内核AST一致（仅SQL多行文本行首缩进规范化）；其余原类方法AST全部一致。新caller入口无connect/commit/rollback/close调用；只读独立15保留schema回读1COMMIT预留/14空账本，canary0。初步专项15PASS6.94s；原预算/ModelEval相邻初次21PASS1FAIL39.01s和单项复验失败均发生在预算调用前的原内容夹具双时钟竞态；独立Task gt-content-fixture-clock-20261007 已按实际DB时间修复，累计37PASS39.91s/7既有warnings/noSKIP。正式系统跨时钟创建/消费契约另保留风险，不以夹具修复消除它。

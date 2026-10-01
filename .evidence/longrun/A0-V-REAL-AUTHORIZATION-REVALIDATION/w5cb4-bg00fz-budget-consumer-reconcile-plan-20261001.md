# BG00FZ 原maker消费与只读历史对账计划

基线AOS-001040/7cb444ed，复习231-5审批费用恢复、433、network121/122参考和预算126/FY连接。7强一致CURRENT。正式库仍只读；仅隔离全迁移库验证。

## 合同与文件
- alembic a0v127 + aos_api/aip_budget_consumer_actor.sql：固定预算caller/owner，原maker且当前owner/admin；exact scope/proposal/hash/decision。共享actor校验仅owner可执行。写包装调用126原消费，不复制预算算法；撤销caller直接126 EXECUTE以免跳过actor。只读STABLE函数必须transaction_read_only=on，核验原Receipt/hash/active revision/fence及原批准，返回observed历史而非当前运行授权。撤销/过期/head变化不妨碍历史对账，失去当前成员权则拒绝。
- aip_budget_consumer_connection.py/schema.json：固定入口换actor包装、允许精确4个owner函数；manifest只隔离127candidate审阅，126body和表结构不改，仅旧EXECUTE收窄和新增定义。
- aip_budget_consumer_service.py：严格请求+SecretStr，fresh external OIDC，不接受actor字段；subject从JWT解析。inquiry只读；consume先查询，再复用私有O_EXCL/fsync AttemptReceipt（稳定proposal槽，不换key），只新marker可一次写，任何未知仅独立只读回查，不重试。无HTTP或自然worker。
- tests/aip/test_budget_consumer_service_pg.py：真实TLSJWT/独立PG连接，正向消费/历史恢复、错误身份/跨租户/篡改hash/撤销/当前权限、原始函数不可直接调用、已有或损坏attempt不写、commit回执丢失只对账。
- test_budget_cost_consumer_pg.py仅公共consume测试适配到原maker包装，保留原业务断言；test_budget_consumer_connection_pg.py漂移函数签名适配127。

## 验证与后续
RED缺模块→隔离migration/schema candidate→专项与FX/FY/issuer累计→复审verification→精确提交/Delivery/CAS/434/D-waves。无UI改动browser不适用。风险：服务JWT证明不等于正式OS peer；有限进程/启动预检/产品自然投递是下一BG00GA，未接前不能暴露消费入口。正式127迁移仍需独立备份克隆零执行窗口；不启Provider、不读商城源、不重放旧Run。

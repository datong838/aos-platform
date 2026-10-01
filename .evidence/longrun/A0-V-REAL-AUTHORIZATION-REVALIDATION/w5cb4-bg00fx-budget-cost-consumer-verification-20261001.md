# BG00FX verification — 2026-10-01

## 结论
独立低权限数据库consumer在真实隔离PG中同事务写BudgetRevision active、head、唯一Receipt与运行风险版本行。运行预留/提交入口已接成本风险核验。当前真实库无连接/写/迁移/重启，无正式身份配置/消费进程部署，无Provider调用，无商城源/旧12Run/手工Run/230L0/no push。不是自然首链或发布通过。Goal未更改，Watchdog仍仅方案。

## 基线与变更
m1@3e22b3ee，AOS-001038，7强一致CURRENT，validate GREEN1493delivery/1491task/3965events。Task W5CB4-BG00FX-20261001。
- 新a0v126：专用call/owner默认NOLOGIN/NOINHERIT/无membership/无高权限；call仅消费函数EXECUTE，不授表查询/DML。owner仅受RLS的必要SELECT、锁列与head更新及revision/Receipt/fence INSERT。共享API store和active INSERT仍拒绝。
- 函数参数只有scope/proposal/decision refs；READ COMMITTED及同issuer advisory锁，current maker/checker、精确原提议/hash/账户期间/严格整数、当前draft head/target、Provider source、原批准未撤销/时效；最后clock检查。原proposal稳定Receipt键，同事务head/revision/Receipt/fence，重复只历史回读；不同decision冲突。无任意payload/actor/key入口。
- runtime gate关联精确Receipt/proposal/decision/hash、当前budget Head、当前成员/Provider、模型价格development authorization的Provider/model/decision/window；per-call hold精确等于批准风险。累计计数与risk不按state过滤，不因unknown或release清零；fence列UPDATE序列化并发。
- revoke触发器同事务推进fence；旧SERIALIZABLE快照锁行会40001，经原事务回滚，无内部自动重试。预留在bucket锁等待后检查，submit在provider Receipt前检查；历史查询/原提交回读与对账不再授权新执行。
- issuer catalog manifest纳入fence表与两个trigger函数；旧issuer guard和旧immutability定义未变。新表默认权限实测附带runtime整表INSERT/UPDATE/DELETE，显式REVOKE后仅SELECT及UPDATE(version)，已真实ACL断言。manifest仅隔离aos_test_*迁移candidate，逐项diff复审；hash 993d2c44cb8726c5f6c67c7baf661c614c1f8d7298cd82d529d11ce29c188c70。pyproject增加*.sql供安装打包。

## RED与失败快照
1. 新test_budget_cost_consumer_pg.py首次exit1：8error，角色不存在（尚未迁移/实现）。实现原子consumer后8passed exit0。
2. 加runtime/source后首跑2failed/8passed：测试BudgetExactRef缺sha256前缀；catalog baseline仍旧125故正确拒绝。修测试ref格式，补真实price head外键fixture，审核新catalog后20passed。
3. manifest复审发现default privilege多授整表权限；加REVOKE再生成隔离candidate，仅fence ACL变化，其他旧表/function逐项一致。加ACL/并发/旧快照检查后23passed。
4. 最后补current budget head、错model/provider、期限测试；消费函数重入核fence存在/decision对应。最终16passed/16.78s，exit0。

## 可复核命令
在services/aos-api：
- `.venv/bin/python -m pytest -q tests/aip/test_budget_cost_consumer_pg.py --tb=short --show-capture=no` → 16passed，exit0。
- `.venv/bin/python -m pytest -q tests/aip/test_budget_cost_consumer_pg.py tests/aip/test_budget_cost_preflight_pg.py tests/aip/test_budget_cost_issuer_pg.py tests/aip/test_budget_cost_product_pg.py tests/aip/test_budget_cost_review_pg.py tests/aip/test_aip_budget_store.py tests/aip/test_aip_budget_activation_consumption_precheck_pg.py tests/aip/test_aip_model_governance_policy_store.py --tb=short --show-capture=no` → 72passed/37.51s，exit0。后续新增4项及runtime head改动在最终16专项中覆盖。
- `.venv/bin/alembic heads` → a0v_126(head)，exit0，仅代码头。
repo根：compileall runtime/preflight/reservation/migration exit0；git diff --check exit0。

真实测试边界：临时独立caller密码只在私有pgpass，cleanup恢复NOLOGIN/password NULL；issuer真TLSJWT/PG。测试风险并发使用真实PG结构化hold fixture，不执行Provider；已验证运行gate接线方法，但尚未证明完整真实Task→reserve→submit→Provider业务调用。模型实际选择仍由既有运行Owner联验；本波价格fixture不能替代正式配置Producer。无UI变更，浏览器不适用；FW截图仍仅历史UI禁入证据。

## 下一波 BG00FY
独立预算consumer连接/完整schema函数身份封板/有限进程及只读原请求恢复，复用已有私有传输不借network身份；补真实Task入口风险预算联合回归，费用提议发起UI与合法开发价格/预算政策配置来源。正式当前实例先重新核卷/版本，一致备份、克隆全链、零执行窗口后单独迁移；不以代码126冒充已恢复当前服务。

# BG00FR verification · 2026-10-01

基线AOS-001032/955f5b37；Task W5CB4-BG00FR-20261001。

## 实现与边界
- a0v_124新增aip_budget_cost_proposal及独立proposal_receipt，scope FK、FORCE RLS、不可变UPDATE/DELETE/TRUNCATE触发器，runtime仅SELECT/INSERT；status固定proposed、source_verification固定pending、activation_eligible固定false。无批准字段/后填历史/worker，旧预算激活门不变。
- Store要求OIDC原maker、同scope当前maker/checker owner/admin；SERIALIZABLE、同actor/key advisory lock、原hash幂等。当前draft/head/empty ledger、next target与DB时间复验后同事务写提议+Receipt。并发最多一份Receipt，发生serialization failure不盲重试，保留原请求查询。
- canonical来源envelope读回重建并精确核对accounts/currency/period及hash、maker/checker/budget/scope、createdAt/到期。GET仅当前maker或checker；Inquiry仅原maker/key/body hash、READ ONLY/repeatable-read/aos_runtime双scope，返回observed/unresolved/conflict；DB故障503，不误报missing。历史记录不表示当前执行许可。
- POST /v1/aip/budgets/cost-proposals；GET /cost-proposals/{id}；POST /cost-proposals/inquiry分别201、200和200/202/409；成功/查询状态响应no-store。外部账单Owner未接，写external引用明确SOURCE_AUTHORITY_UNWIRED。development Provider/model仍是待审核候选，sourceVerification=pending，不证明真实可执行。
- 原Store只提取read_initial_budget_target供复用，旧preview原hash/目标比较/Receipt不变。新提议没有生成旧批准，也不能进入现有consumer。独立签发者/决定/撤销与受限原子consumer后续BG00FS，不直接复用network issuer权限。

## RED与新鲜回归
首次RED新Store缺失，collection error/0.41s/exit2。一次apply_patch目标路径漏aos_api目录，工具在验证阶段失败，回读确认未改文件；修正路径后实施，未影响用户旧dirty。
首轮4文件75 passed/11.92s/exit0。复审补DB伪批准/verified/activationEligible拒绝和503失败分类，最终9文件131 passed/7既有warnings/46.18s/exit0（新文件17项）。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_budget_cost_proposal_pg.py services/aos-api/tests/aip/test_budget_cost_basis.py services/aos-api/tests/aip/test_aip_budget_activation_authority.py services/aos-api/tests/aip/test_aip_budget_activation_consumption_precheck_pg.py services/aos-api/tests/aip/test_aip_budget_activation_store_pg.py services/aos-api/tests/aip/test_budget_preview_inquiry_pg.py services/aos-api/tests/aip/test_budget_activation_product_pg.py services/aos-api/tests/aip/test_budget_activation_review_reads_pg.py services/aos-api/tests/aip/test_aip_budget_api.py --tb=short --show-capture=no
services/aos-api/.venv/bin/python -m compileall -q services/aos-api/aos_api/aip_budget_cost_basis.py services/aos-api/aos_api/aip_budget_cost_proposal_store.py services/aos-api/aos_api/aip_budget_activation_store.py services/aos-api/aos_api/routers/aip_budgets.py services/aos-api/alembic/versions/a0v_124_budget_cost_proposals.py
git diff --check
```
全部exit0；services/aos-api目录 .venv/bin/alembic heads → a0v_124 (head)/exit0。

新集成使用标准conftest独立aos_test_*_ti4_test及真实本地TLS签名JWT HTTP，无Store/Principal替换。涵盖原request回读、并发、maker/checker、canary只读、role移除、目标/head漂移、canonical篡改、RLS/不可变、真实PG Receipt触发器故障整笔回滚。只在隔离测试中DDL注入失败，完成后清除自有trigger/function。查询503用连接故障注入，仅验证错误分类。其余合同/相邻用例含纯数据/替身；都不证明当前正式身份、费用来源或自然首链。

## 风险/下一波
迁移代码124仅在测试库跑；当前真实库未连接/未写/未迁/未重启。此前实测live118为旧证据，118→124需独立一致备份可恢复、克隆全链及零执行窗口后切换，不能宣称最新全栈已运行。接口源码新增不等于当前API部署。
BG00FS预算专域独立签发/checker：正式来源核验、精确提议决定/撤销/Inquiry与权限门，不能信任runtime可写的proposed输入直接执行；之后独立consumer原子激活、产品持久请求、当前身份与自然首链。
Host/worker/Provider未启，无商城源/旧12Run/手工Run/230L0/no push。无UI改动，浏览器不适用。Goal未改状态，看护方案未部署。

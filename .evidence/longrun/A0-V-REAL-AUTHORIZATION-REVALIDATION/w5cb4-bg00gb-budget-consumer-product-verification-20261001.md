# BG00GB 预算消费产品请求验证

基线 AOS-001042 / 42a3525c / a0v127；m1 单写，不push。复习231-5第5/6/7节、435及本波文件计划。7强一致CURRENT后续接原工作树。

## 实现及复审
- 新API POST/GET cost-proposals/{proposal_id}/consumption-request，只接受proposalHash/decisionId；fresh externalOIDC/current member与原maker约束，首次保存前再次读取当前批准/hash/decision/撤销/到期。
- API稳定slot按scope/actor/proposal绑定，0600文件O_EXCL+文件及目录fsync后仅fresh可execute_once；原body变化409，损坏/写失败保留文件；unknown/重复/刷新只inquiry，不重发。
- 私有consumer client固定不同UID，发送前核验socket/内核peer；响应exact schema/Receipt/proposal/hash/decision/requestDigest，activationEligible必须false。JWT只在wire，不保存到slot。
- 复用原cost product私有原请求状态机及单帧传输；diff逐项复核旧审核业务、错误码、一次派发和查询分支保持原语义。新增before_reserve只由新消费路径使用；SQL仍作最终事务内当前批准检查，API检查不能替代SQL授权。
- 路由no-store，observed200/not_attempted200/unresolved202/conflict409/blocked503；没有前端变更或正式API reload。

## 可复核测试
工作目录 services/aos-api。
- RED: pytest tests/aip/test_budget_consumer_product_pg.py 在模块不存在时ImportError，exit2；原日志 /tmp/aos-gb-red.log。
- 首轮 product+原cost product/client：38 passed /26.61s，exit0；/tmp/aos-gb-first.log，原session26448已取回终态。
- 累计命令：`.venv/bin/python -m pytest -q tests/aip/test_budget_consumer_client.py tests/aip/test_budget_consumer_product_pg.py tests/aip/test_budget_cost_product_pg.py tests/aip/test_budget_cost_client.py tests/aip/test_budget_consumer_service_pg.py tests/aip/test_budget_consumer_process.py --tb=short --show-capture=no`
- 104 passed /53.70s，exit0；/tmp/aos-gb-regression.log，session72753终态exit0。7项已有schema字段/Starlette弃用warning。
- 新client覆盖socketpair单帧/丢响应无重发、exact Receipt跨引用拒绝、异常JSON、sameUID kernel peer拒绝；产品真实隔离PG/TLSJWT/HTTP覆盖首次/刷新/并发、commit前后丢响应、fsync失败、损坏slot、checker拒绝、批准撤销后fresh无文件无dispatch、历史查询仍可读。
- compileall 新client和测试exit0；git diff --check services/aos-api exit0。

## 证据边界与后续
隔离PG用真实schema/事务/TLS JWT；产品测试transport适配器不等于正式跨UID正向通信，socketpair仅传输证明，不当真实业务验收。真实当前库本波没有连接/写入/迁移/重启；不能把代码a0v127当成当前库版本。Host/worker/Provider未开启；商城源/旧12Run/手工Run/230L0未动。正式首链及八工作台业务仍pending。
下一BG00GC接Capacity UI批准预算消费与刷新恢复；合法development价格/政策producer、实际Task预算风险联合证明及正式不同UID部署仍需完成。最新实例恢复须独立身份核验、一致备份可恢复、克隆全链和零执行窗口。Goal未修改，防停工Watchdog当前仍是方案，不能声称已部署。

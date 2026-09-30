# BG00FS verification · 2026-10-01

基线AOS-001033/a24568ba；Task W5CB4-BG00FS-20261001。

## 实现和复审
1. a0v125：aos_budget_cost_issuer默认NOLOGIN/NOINHERIT/无高权，仅SET ROLE aos_runtime；拒绝已有角色/成员漂移。decision/revocation/issuer_receipt同scope外键/唯一键/FORCE RLS/不可变；INSERT门强制独立session_user+runtime+GUC+安全角色属性，不复用network issuer。决定INSERT再核原提议hash/checker/expiry/当前DB时间。
2. aip_budget_cost_issuer.py：每个execute/inquire重验external-only配置与真实JWT，scope/subject严格一致；SecretStr token不入request hash、Receipt或日志。显式DB factory，无共享owner回退；事务验证独立login/current role/角色属性/GUC及serializable或read-only repeatable-read。
3. 决定：原独立checker和当前maker/checker成员，原proposal/hash/canonical/expiry，锁current预算head/空账本并匹配目标；批准再锁current exact Provider head，校验payload/hash/tenant/id/revision/active。source read后再读DB clock防锁等待过期。拒绝不制造source proof；一次proposal只一决定。同key回历史Receipt，不重跑授权。
4. 撤销：原maker/checker当前成员，approved决定、同proposal advisory lock，一次revocation+Receipt；不改历史。只读Inquiry按原actor/operation/key/hash读Receipt，核原proposal和decision/revocation字段，observed始终eligible=false；missing unresolved、漂移conflict、数据库错误unavailable。
5. 批准只是development风险批准，实际费用未知；Provider当前性不等于模型/secret/网络/价格/配额全部可用，也未发Provider调用。modelId是审核覆盖目标；后继模型注册/运行完整依赖仍必须核验。不存在外部账单Owner的替代证明。

## RED及新鲜验证
- 模块未实现：collection RED，exit2/0.41s。
- 首批独立PG登录/TLS-JWT 10 passed/11.56s/exit0。
- 复审来源读取耗时跨expiry：1 failed/10 deselected/5.82s/exit1，证明旧实现会过期后提交；补app后置clock和DB时效/绑定门。
- 最终6文件111 passed/7既有warning/33.01s/exit0，新文件16项。无全后端完成声称。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_budget_cost_issuer_pg.py services/aos-api/tests/aip/test_budget_cost_proposal_pg.py services/aos-api/tests/aip/test_budget_cost_basis.py services/aos-api/tests/aip/test_aip_budget_activation_consumption_precheck_pg.py services/aos-api/tests/aip/test_aip_budget_activation_store_pg.py services/aos-api/tests/aip/test_budget_activation_product_pg.py --tb=short --show-capture=no
services/aos-api/.venv/bin/python -m compileall -q services/aos-api/aos_api/aip_budget_cost_issuer.py services/aos-api/alembic/versions/a0v_125_budget_cost_issuer.py
git diff --check
```
均exit0。隔离tests使用aos_test_*_ti4_test；专域临时实际DB登录/private pgpass及真实TLS签名JWT，未用SET SESSION AUTHORIZATION冒充正向；每例最后恢复NOLOGIN/PASSWORD NULL并清除passfile，断言与原角色状态一致。Provider记录仅隔离fixture，没有调用外部服务；不证明正式OS/独立账户部署或供应商可用。expiry仅延迟真实Provider读取函数，rollback用测试库真实触发器故障，全部测试自有对象清除。

## 尚未完成
本波无共享HTTP直连issuer、无正式passfile/进程/IPC部署。BG00FT补独立私有连接配置、超时/身份/精确schema预检、进程IPC及产品原请求恢复；之后受限consumer同事务激活与唯一Receipt。
代码迁移头125，仅隔离测试迁移；当前真实库未连接/未写/未迁/未重启，旧live118要再读。118→125安全恢复独立一致备份/克隆全链/零执行窗口后才能切换。Host/worker/Provider未启，无商城源/旧12Run/手工Run/230L0/no push。无UI改动，浏览器不适用。Goal未改状态，看护方案未部署，首链pending。

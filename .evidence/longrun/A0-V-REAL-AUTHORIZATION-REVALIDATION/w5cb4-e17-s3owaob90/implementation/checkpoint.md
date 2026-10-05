# 完整 evaluator 施工检查点：合同与原内容核验复用

2026-10-05，基线 code 79744569 / Authority AOS-001331。完整 Task `w5cb4-e17-b90-full-evaluator-implementation-20261005` 保持 ACTIVE，不产生整波 Delivery，不改变当前八依赖 pending 状态。

## 已实施与复审

- `services/aos-api/aos_api/aip_binding_formal_evaluator_contracts.py`：schemaVersion=1；正向固定租户；版本/etag/revision StrictInt；canonical UUID；精确类型/原64位小写hash；Source非空；Data/Tool显式提供并仅支持原已知权威类型。同一资源不同revision也拒重复。unknown字段禁止，客户端不能提供actor/roles/ready/facts/clock/bearer/health。model instance重验涵盖嵌套model_copy/model_construct。传输合同不构成Owner、Source、预算或READY证明。
- `services/aos-api/tests/aip/test_binding_formal_evaluator_contracts.py`：合成输入只测合同；禁止字段、严格数字、canary/UUID/类型/hash/空来源、重复与未知权威、必需字段缺失、嵌套构造绕过均拒。
- `services/aos-api/aos_api/aip_license_source_proposal.py`：原公开入口仍先检查原runtime/approval issuer/source issuer身份，再复用内部内容核验；内部仍独立检查调用方事务/tenant并查询actual current_user选择原初始化锁模式。不接收identity/共享锁开关，不伪造Maker Principal，不新增许可入口或ACL。
- `services/aos-api/aos_api/aip_budget_cost_runtime.py`：只抽取原Receipt、Proposal、两Owner、当前Budget/Provider/Price、批准撤销、有效窗口和风险量核验。AST逐语句比较原内容与新私有helper完全相同。原wrapper保留原legacy None、Receipt入口检查、fence FOR UPDATE/version+1、新hold语义及原异常包装。新私有helper本身不授权限、不产生hold，完整formal caller尚未接入。

## 实际验证

| 证据 | 结果与界限 |
|---|---|
| contracts-red.log | exit2，缺模块导致收集失败；仅入口RED，不是业务拒绝证明 |
| contracts-green.log | exit0，33 passed/5.36s，最初合同集合 |
| contracts-source-green.log | exit0，71 passed/4.94s，合同及原Source相邻；后续新增合同负例由final覆盖 |
| source-signed-regression.log | exit0，1 passed/30.71s，原一次性PG/OCI签名Growth1.13，B88/B89消费原独立批准/来源发行；本地测试签名不等于正式生产安装授权 |
| budget-baseline.log | exit0，28 passed/55.17s；执行期间发生内容抽取，因此不用于不可变旧基线或最终hash验证，仅保留中间证据 |
| contracts-source-budget-final.log | exit0，122 passed/54.80s；四文件最终稳定输入，合同/Source/原Budget消费及ModelEval额度相邻 |

均为7个既有warnings。最终测试源hash见test-input-hashes.json；结束后重验相同。四文件py_compile通过、目标代码与方案diff检查通过。PG串行，conftest使用5433独立集群的一次性aos_test_*_ti4_test；不连接当前18435真库写业务，不清除历史测试库/卷。无UI改动，浏览器不适用。

## 剩余必要工作与风险

完整native evaluator尚未实现；已有Health helper仍不能当正式完整命令使用。a144默认NOLOGIN最小ACL/RLS/锁列DML拒绝及binding/Receipt/proof三延迟约束、原签名身份接线、八facts与Source/两Owner/安装/Budget全锁序、幂等重核验、实际COMMIT与并发/到期回滚、产品service/router均待本Task继续实施。私有核验复用必须由严格固定evaluator身份及实际原锁保护后调用，不能暴露为通用用户入口。当前数据库仍142，Host/worker/Provider关闭；本检查点不授权当前迁移、正式LOGIN或自然首链。Authority保持1331，不把施工检查点改写为全验收。

## 2026-10-05 12:35 完整Task内部Health消费修正

真实SCRAM/dict-row精确最新观测、DB时间、native身份及canary零epoch；真实并发writer阻塞和原40001实测。最终94passed/1strictxfail/7warnings/9.90s，详health-consumer-verification.md和tested-hashes。完整native命令仍缺失，整体Task ACTIVE，无当前142写入/LOGIN/业务启动。下一步原Source完整审批纯内容复用，不能伪造maker Principal。

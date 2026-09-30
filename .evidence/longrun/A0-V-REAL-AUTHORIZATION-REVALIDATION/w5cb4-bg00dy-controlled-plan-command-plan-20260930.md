# W5CB4 BG00dy｜认证 BI Plan 命令未知结果对账文件级方案

## 复习与问题

已复习 231-3/231-9、BG00ds–dx、`AipProductionContractStore.create_responsibility_plan_in_transaction` 和 `aip_production_contract_receipt`。写入同事务且 `(org,project,operation,idempotency_key)` 唯一，原 POST 每次先重验当前安装/权限后才回放。当前 Receipt 保存 actor、requestHash 与 Plan exact result_ref，**未单列原安装 ID/ETag**。网络结果未知时，不能生成新键重发；如果当前安装/权限已漂移，原 POST 的重放预检也可能拒绝，因此仅靠重发无法安全对账。

## 本波最小目标

先提供只读 `GET /v1/aip/production-contracts/responsibility-plans/bi-preparation/receipts/{idempotencyKey}`。只允许同租户正式 OIDC 且当前持久成员具配置角色的原 actor 读取自己、固定 `bi_responsibility_plan.prepare` 操作的 Receipt。按键查不到返回 404/unknown，**不代表未提交，也不授权重发**；命中时返回 receiptId、createdAt、requestHash 和 exact Plan result_ref，并明确原安装 ID/ETag 未被此表独立证明。查询使用 scoped read-only 连接，无锁、无 Receipt/outbox 写入。当前角色被撤销时拒绝读取，不退回 dev token 或高权限捷径。

前端 SDK 只加 GET 和严格解析；产品页仅在用户已经持有同一次命令的幂等键时才展示“只读对账”。本波不生成新的写键、不开放正式提交按钮，因为当前正式 OIDC/签名安装/六 active 实例缺失，且写入未知恢复的原安装上下文仍须后续加固。页面不能将 404、网络失败、请求哈希存在或只读候选等同于成功/可重发。

## RED、文件与验证

1. `services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py`：错租户/dev token、无成员/低角色、非原 actor、非 BI operation、无 Receipt 均 fail-closed；同 actor 命中只读 exact result_ref，未产生新记录。
2. `services/aos-api/aos_api/aip_production_contract_store.py`：窄只读 Receipt 查询，固定 operation/actor/tenant；`routers/aip_production_contracts.py`：认证 GET 与严格响应 DTO。
3. `apps/web/src/api/aipProductionContracts`：GET/parser 的字段与不重发约束测试；`ProductionContractsPage.tsx` 可先留只读入口或挂起 UI，绝不默认从 URL/本地生成一个可对账 key。
4. 专项与相邻回归、OpenAPI、当前只读正式来源审计、方案/代码复审；browser-pilot 可用时再截图。若必须增加原安装 ID/ETag 持久字段，另立迁移/克隆/备份零执行波，不在本波改当前 DB。

本波不写当前/clone DB、不启 Host/worker/Provider、不读商城源、不碰 dev-org 正向、不回放旧 12 Run、不手工 run_definition、不 push。

# BG00GF 费用配置受限产品接线方案

基线AOS-001046/m1@9a011c5c/a0v128；复习231-5费用与恢复合同、439、GE SQL和FZ/GA/GB既有接线。首链仍pending。

## 文件与合同
- aip_budget_consumer_service.py：BudgetConsumerRequest增加operation Literal consume/configure，默认consume保持旧请求；consume原hash与attempt namespace不变，configure使用SQL一致的aos.budget-cost-configuration/v1与独立attempt namespace。共享身份核验/一次执行/历史读取，SQL函数名固定映射不接受外部任意名称。
- service提供严格业务结果验证供client共用；configure精确校验proposal/hash/decision与确定性receipt、price/policy ID/revision、三类引用hash/type。所有observed永久activationEligible=false，不把历史当执行权。
- aip_budget_consumer_client.py：复用业务结果验证，保留帧大小、重复JSON key、schema/blocked固定码门。既有有限process自动解析受限operation，无新常驻入口。
- aip_budget_consumer_product.py：同一recover_private_product_request状态机；内部keyword operation默认consume，configure独立持久key。原maker/current approval首次核验、请求私有文件fsync、unknown仅inquiry；不持久化JWT。旧consume持久key/body保持兼容。
- routers/aip_budgets.py：新增明确POST/GET cost-proposals/{id}/configuration-request，固定configure，不允许用户提交任意operation/配置payload。沿用no-store和状态映射；原consumption-request保持默认consume。
- tests/aip/test_budget_configuration_product_pg.py：标准独立PG、真实TLS JWT与受限DB caller，先消费预算后派生。HTTP→持久请求→process dispatch→service→SQL，transport替身明确不冒跨UID证明。

## RED与验收
新配置HTTP路由缺失/请求拒绝为RED；验证正常双配置/哈希引用、consume与configure不同slot与attempt、响应丢失只读恢复、未消费/错误身份/撤销不写、撤销后历史、同请求并发一写、严格Receipt拒绝与旧consumer相邻回归。服务级commit回执丢失注入只对账；不把替身网络当正式IPC验收。
API-only本波不改UI，无浏览器业务验收；下一波接现有预算面板并对Model/Task联合证据逐项核实。正式实例迁移、启动与Provider调用仍独立授权波，真实库只读，不读商城源/旧12Run/手工Run/230L0。

## 复审与收口
核对operation不能跨用Receipt或marker；旧consume hash/key不变；不复制安全状态机。不配置正式凭证/重启API。专项与累计后verification、精确代码提交、Delivery/CAS/7强一致、440与D-waves，立即接下一波。

## 实现复审补充
配置HTTP与预算消费共享有限consumer配置与现有进程，调用次数仍由部署配置限定。旧consume请求hash、产品key与attempt namespace保持；新增operation默认consume，旧客户端省略字段仍可解析，正式部署必须协调API/consumer版本，不声称旧进程支持configure。
首次派生前消费未确认时，service只读核验失败且无service attempt；产品若已持久发出请求，仍按unknown处理，不删槽位重试。下一波UI必须先以原预算消费Receipt确认前置，再开放配置操作，并呈现既有unknown查询状态。这是禁止重发的边界，不能以伪成功消除。

# BG00FJ 有界单次持久投递方案

基线AOS-001024/m1@938b72c2，复习231-5§3/5/7、公共产品契约和417。Task W5CB4-BG00FJ-20261001。

## 现场约束
ConsumerApplicationConfig为API侧，仅endpoint+私有attempt目录；ConsumerDatabaseConfig为独立consumer侧。现有IPC只consume_once/inquiry，claim/finish不可把消费数据库凭据暴露API。BG00FH事件driver固定inquiry=False；即使PG认领已经是inquiry，若本地marker丢失仍可能尝试新Command，必须明确传只查询模式。

## 文件级顺序
1. aip_network_approval_event_driver.py增加严格bool inquiry选项，默认保持原合同；传入execute_consumer，查询模式不落marker、不发Command。test_network_approval_event_driver_pg.py用真实TLS签名/隔离PG+捕获IPC先RED锁定缺marker的强制Inquiry及非bool拒绝。
2. aip_network_consumer_contracts.py新增严格claim/finish身份请求和返回lease合同；不得包含DSN/actorId/权限/任意路径，JWT SecretStr不入repr。共用现有scope/JWT验证语义，保持旧Command/Inquiry字段和hash不变。
3. aip_network_consumer_auth.py复用外部OIDC验证源，新请求同样核真签名及scope，由验证结果取maker subject；不得取调用方actor字符串。
4. aip_network_consumer_service.py在独立进程内经原connect_consumer与_function_gate执行a0v123 claim/finish；服务端生成UUID；claim提交成功后才返回lease；finish只查PG Receipt，不收客户端成功布尔值。
5. aip_network_consumer_ipc.py/client.py增加精确claim_delivery/finish_delivery方法，保留真实peer UID门、大小/重复key/严格响应验证和一次send。响应未知不自动重发；claim响应丢失后等待持久租期，到期仅inquiry。
6. 新aip_network_delivery_driver.py仅有界单次函数：先验证配置和当前原maker OIDC→claim IPC→若得有效lease按持久mode调原事件driver→finish IPC回读PG确认。未知claim不调用业务；即使事件处理报错也只做可确认的finish/对账，无重发。不得持久JWT，不注册HTTP/默认worker、不自行供应假身份。
7. 新test_network_delivery_driver_pg.py组合真实隔离PG/TLS与原consumer服务证明首次/过期/unknown/响应丢失/确认；IPC合同补到现有test_network_consumer_ipc.py/client.py，清楚区分transport捕获和真实OS验收。

## 验收与边界
RED→最小实现→专项/旧consumer和producer相邻累计→复审→verification→m1精确提交→Delivery/CAS/418/D-waves。无新迁移；代码头仍123，当前真库只读。未具备正式原maker服务身份的实例仍禁入，无自然worker/Provider/Host启动。只查一个原maker的未来新事件，不扫描旧12Run或历史批准。未知结果绝不换key或自动重发。正式OS/身份部署、118到123独立安全恢复、真实自然首链仍单独待证。
